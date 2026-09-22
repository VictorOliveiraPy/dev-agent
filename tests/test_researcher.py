"""Testes para agents/researcher.py.

Nenhum destes testes chama uma API de LLM real, a API da Tavily, nem faz
requisição HTTP de verdade: o modelo e a tool de busca são fakes locais
(ver `fake_model`/`fake_search`), e `_verify_image_url` é monkeypatchado
onde `validate_batch` precisaria dele.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, ConfigDict, Field

from agents import researcher


class _ScriptedFakeChatModel(BaseChatModel):
    """Chat model falso que devolve, em ordem, uma resposta por chamada.

    Cada resposta é uma `AIMessage` já pronta (com ou sem `tool_calls`) —
    permite simular "o modelo pesquisou mas ainda não chamou a tool final"
    seguido de "agora chamou", sem precisar de nenhuma chamada de rede.
    """

    responses: list[AIMessage] = Field(default_factory=list)
    call_count: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        message = self.responses[self.call_count]
        self.call_count += 1
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        """Fake não precisa processar o schema das tools — devolve a si
        mesma, como o `AgentExecutor` real esperaria de um `.bind_tools()`."""
        return self

    @property
    def _llm_type(self) -> str:
        return "fake-scripted"


class _Category(StrEnum):
    """Só para o teste imitar o formato real: Category.X.value vira o
    prefixo de 'id' (ex.: 'concilios:trento')."""

    TESTE = "teste"


class _ItemModel(BaseModel):
    """Modelo mínimo só para exercitar research_batch/validate_batch nos
    testes — não é o modelo real de nenhuma categoria do backend, mas tem
    'id'/'categoria' no mesmo formato de ContentEntry para exercitar a
    normalização de id em validate_batch."""

    model_config = ConfigDict(extra="forbid")

    id: str
    categoria: Literal[_Category.TESTE] = _Category.TESTE
    slug: str
    titulo: str
    imagem: str | None = None
    imagem_credito: str | None = None


def _submit_entries_message(itens: list[dict], call_id: str = "call_submit") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "submit_entries", "args": {"itens": itens}, "id": call_id}],
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _search_call_message(query: str, call_id: str = "call_search") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "tavily_search", "args": {"query": query}, "id": call_id}],
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _text_only_message(text: str) -> AIMessage:
    return AIMessage(
        content=text,
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _truncated_message(field: str = "stop_reason", value: str = "max_tokens") -> AIMessage:
    """Simula o bug real visto em produção: resposta cortada por limite de
    tokens antes de terminar o JSON da tool call. `field`/`value` permitem
    simular tanto o formato da Anthropic ("stop_reason"="max_tokens") quanto
    o de provedores OpenAI-compatíveis como o DeepSeek
    ("finish_reason"="length")."""
    return AIMessage(
        content="",
        response_metadata={field: value},
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _malformed_submit_message() -> AIMessage:
    """submit_entries chamada sem o campo 'itens' -- não deve estourar
    KeyError cru, e sim um RuntimeError com contexto."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "submit_entries", "args": {}, "id": "call_1"}],
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


class _FakeSearchTool:
    """Substitui `TavilySearch` nos testes: sem chamada de rede, sem exigir
    `TAVILY_API_KEY`. Registra cada chamada pra testes que precisam
    inspecionar o que foi pesquisado."""

    def __init__(self, result: Any = None) -> None:
        self.result = result if result is not None else {
            "results": [{"title": "Fonte", "url": "https://x.org/y", "content": "..."}]
        }
        self.calls: list[dict] = []

    def invoke(self, args: dict) -> Any:
        self.calls.append(args)
        return self.result


@pytest.fixture
def fake_model(monkeypatch):
    def _install(responses: list[AIMessage]) -> _ScriptedFakeChatModel:
        fake = _ScriptedFakeChatModel(responses=responses)
        monkeypatch.setattr(researcher, "build_chat_model", lambda *a, **kw: fake)
        return fake

    return _install


@pytest.fixture(autouse=True)
def fake_search(monkeypatch) -> _FakeSearchTool:
    """Autouse: NENHUM teste de research_batch deve depender de uma
    TAVILY_API_KEY real ou de rede — `_web_search_tool()` normalmente
    instancia `TavilySearch()`, que valida a env var na hora da construção
    (ver `langchain_tavily._utilities.TavilySearchAPIWrapper`), então até
    testes que nunca acionam a busca precisam desta troca. A troca acontece
    aqui, incondicionalmente (não dentro de uma fábrica que só monkeypatcha
    quando chamada) — testes que precisam inspecionar `.calls` só pedem
    `fake_search` como parâmetro normal; é a MESMA instância já aplicada."""
    fake = _FakeSearchTool()
    monkeypatch.setattr(researcher, "_web_search_tool", lambda: fake)
    return fake


def test_should_follow_active_llm_provider_like_the_rest_of_the_team(monkeypatch):
    """A busca deixou de depender de uma tool nativa exclusiva da Anthropic
    (agora é `TavilySearch`, client-side, funciona com qualquer provedor de
    tool-calling) — este papel não força mais nenhum provedor específico,
    igual ao resto do time (ver agents/team.py)."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    captured = {}
    fake = _ScriptedFakeChatModel(responses=[_submit_entries_message([{"slug": "x"}])])

    def fake_build(*args, **kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(researcher, "build_chat_model", fake_build)

    researcher.research_batch("pesquise 1 concílio", _ItemModel)

    assert "provider" not in captured


def test_should_return_items_when_model_calls_submit_entries_on_first_try(fake_model):
    itens = [{"slug": "niceia-ii", "titulo": "Concílio de Niceia II"}]
    fake_model([_submit_entries_message(itens)])

    result = researcher.research_batch("pesquise 1 concílio", _ItemModel)

    assert result == itens


def test_should_retry_when_model_does_not_call_submit_entries_first(fake_model):
    itens = [{"slug": "trento-ii", "titulo": "Segundo Concílio de Trento (fictício)"}]
    fake = fake_model([
        _text_only_message("Ainda estou pesquisando..."),
        _submit_entries_message(itens),
    ])

    result = researcher.research_batch("pesquise 1 concílio", _ItemModel)

    assert result == itens
    assert fake.call_count == 2


def test_should_execute_a_real_search_call_and_feed_the_result_back(fake_model, fake_search):
    """A busca agora é client-side: quando o modelo chama a tool de busca,
    research_batch precisa executá-la de verdade (via `search_tool.invoke`)
    e devolver o resultado como ToolMessage antes de insistir — diferente
    da antiga web_search da Anthropic, resolvida no servidor dela."""
    itens = [{"slug": "efeso", "titulo": "Concílio de Éfeso"}]
    fake_model([
        _search_call_message("Concílio de Éfeso 431"),
        _submit_entries_message(itens),
    ])

    result = researcher.research_batch("pesquise 1 concílio", _ItemModel)

    assert result == itens
    assert fake_search.calls == [{"query": "Concílio de Éfeso 431"}]


def test_should_stop_offering_real_searches_once_the_budget_is_exhausted(fake_model, fake_search):
    itens = [{"slug": "efeso", "titulo": "Concílio de Éfeso"}]
    fake_model([
        _search_call_message("busca 1", call_id="c1"),
        _search_call_message("busca 2", call_id="c2"),
        _submit_entries_message(itens),
    ])

    result = researcher.research_batch(
        "pesquise 1 concílio", _ItemModel, max_search_calls=1
    )

    assert result == itens
    # só a primeira busca foi executada de verdade — a segunda tool call de
    # busca recebeu o aviso de limite atingido, sem gastar outra chamada real.
    assert len(fake_search.calls) == 1


def test_should_raise_when_model_never_calls_submit_entries(fake_model):
    fake_model([_text_only_message("desculpe, não encontrei nada")] * 3)

    with pytest.raises(RuntimeError, match="submit_entries"):
        researcher.research_batch("pesquise 1 concílio", _ItemModel, max_iterations=3)


def test_should_raise_clear_error_when_response_is_truncated_by_anthropic_stop_reason(fake_model):
    """Bug real (ver ARCHITECTURE.md): lote grande demais corta a resposta
    no meio do JSON da tool call. Isso deve falhar alto e claro, não com
    um KeyError sem contexto na hora de ler call['args']['itens']."""
    fake_model([_truncated_message("stop_reason", "max_tokens")])

    with pytest.raises(RuntimeError, match="limite de tokens"):
        researcher.research_batch("pesquise 18 concílios de uma vez", _ItemModel)


def test_should_raise_clear_error_when_response_is_truncated_by_openai_finish_reason(fake_model):
    """Mesmo bug, formato do provedor OpenAI-compatível (DeepSeek): o campo
    é 'finish_reason'='length', não 'stop_reason'='max_tokens'."""
    fake_model([_truncated_message("finish_reason", "length")])

    with pytest.raises(RuntimeError, match="limite de tokens"):
        researcher.research_batch("pesquise 18 concílios de uma vez", _ItemModel)


def test_should_raise_clear_error_when_submit_entries_is_missing_itens(fake_model):
    fake_model([_malformed_submit_message()])

    with pytest.raises(RuntimeError, match="itens"):
        researcher.research_batch("pesquise 1 concílio", _ItemModel)


def test_should_force_id_convention_when_model_proposes_a_different_id(monkeypatch):
    """Bug real visto na prática: o pesquisador devolveu 'id': 'efeso' em
    vez de 'concilios:efeso' — a convenção usada em toda entrada existente
    do acervo. validate_batch nunca aceita o 'id' que o modelo propõe,
    sempre recalcula como '{categoria}:{slug}'."""
    monkeypatch.setattr(researcher, "_verify_image_url", lambda url, timeout=10.0: (True, "ok"))
    raw = [{"id": "efeso", "slug": "efeso", "titulo": "Concílio de Éfeso"}]

    valid, warnings = researcher.validate_batch(raw, _ItemModel, existing_slugs=set())

    assert warnings == []
    assert valid[0].id == "teste:efeso"


def test_should_discard_entry_when_slug_already_exists(monkeypatch):
    monkeypatch.setattr(researcher, "_verify_image_url", lambda url, timeout=10.0: (True, "ok"))
    raw = [{"slug": "trento", "titulo": "Concílio de Trento"}]

    valid, warnings = researcher.validate_batch(raw, _ItemModel, existing_slugs={"trento"})

    assert valid == []
    assert "já existe" in warnings[0]


def test_should_drop_image_but_keep_entry_when_image_url_fails_verification(monkeypatch):
    monkeypatch.setattr(
        researcher, "_verify_image_url", lambda url, timeout=10.0: (False, "HTTP 404")
    )
    raw = [{
        "slug": "niceia-ii",
        "titulo": "Concílio de Niceia II",
        "imagem": "https://upload.wikimedia.org/wikipedia/commons/x/xx/inventada.jpg",
        "imagem_credito": "Foto: Alguém — CC BY-SA 4.0",
    }]

    valid, warnings = researcher.validate_batch(raw, _ItemModel, existing_slugs=set())

    assert len(valid) == 1
    assert valid[0].imagem is None
    assert valid[0].imagem_credito is None
    assert "imagem descartada" in warnings[0]
    assert "HTTP 404" in warnings[0]


def test_should_discard_entry_when_pydantic_validation_fails(monkeypatch):
    monkeypatch.setattr(researcher, "_verify_image_url", lambda url, timeout=10.0: (True, "ok"))
    # "campo_inventado" não existe em _ItemModel (extra="forbid" barra).
    raw = [{"slug": "niceia-ii", "titulo": "Concílio de Niceia II", "campo_inventado": "x"}]

    valid, warnings = researcher.validate_batch(raw, _ItemModel, existing_slugs=set())

    assert valid == []
    assert "falhou validação" in warnings[0]


def test_should_add_accepted_slug_to_existing_slugs_when_entry_is_valid(monkeypatch):
    monkeypatch.setattr(researcher, "_verify_image_url", lambda url, timeout=10.0: (True, "ok"))
    raw = [{"slug": "niceia-ii", "titulo": "Concílio de Niceia II"}]
    existing: set[str] = set()

    valid, warnings = researcher.validate_batch(raw, _ItemModel, existing_slugs=existing)

    assert len(valid) == 1
    assert warnings == []
    assert "niceia-ii" in existing


def test_should_record_quality_with_discard_breakdown_when_batch_is_mixed(monkeypatch):
    """Fim a fim: validate_batch -> uma chamada a record_quality com a
    contagem certa por motivo de descarte (duplicado, imagem, schema)."""
    monkeypatch.setattr(
        researcher, "_verify_image_url", lambda url, timeout=10.0: (False, "HTTP 404")
    )
    recorded = {}
    monkeypatch.setattr(researcher, "record_quality", lambda **kwargs: recorded.update(kwargs))

    raw = [
        {"slug": "trento", "titulo": "Já existe"},
        {"slug": "niceia-ii", "titulo": "Com imagem ruim", "imagem": "https://x/y.jpg"},
        {"slug": "efeso", "titulo": "Ok", "campo_inventado": "quebra o schema"},
    ]

    valid, _ = researcher.validate_batch(
        raw, _ItemModel, existing_slugs={"trento"}, model="claude-sonnet-5"
    )

    assert len(valid) == 1
    assert recorded == {
        "role": "pesquisador",
        "model": "claude-sonnet-5",
        "items_proposed": 3,
        "items_valid": 1,
        "discarded_duplicate_slug": 1,
        "discarded_validation_error": 1,
        "images_discarded": 1,
    }


def test_should_not_call_network_when_entry_has_no_image(monkeypatch):
    """Confirma que _verify_image_url só é chamada quando há imagem —
    evita gastar uma checagem de rede à toa."""
    called = []
    monkeypatch.setattr(
        researcher,
        "_verify_image_url",
        lambda url, timeout=10.0: called.append(url) or (True, "ok"),
    )
    raw = [{"slug": "niceia-ii", "titulo": "Concílio de Niceia II", "imagem": None}]

    valid, _ = researcher.validate_batch(raw, _ItemModel, existing_slugs=set())

    assert len(valid) == 1
    assert called == []
