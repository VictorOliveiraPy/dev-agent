"""Testes para o rastreamento de uso de tokens (agentes/usage.py) e sua
integração com agentes/team.py.

Usa um chat model falso (sem rede, sem custo de API) pra provar que o
UsageCallbackHandler é acionado de ponta a ponta quando um agente real do
time é invocado — não só testa a lógica isolada de parsing de tags.
"""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agentes import team
from agentes.usage import UsageCallbackHandler, _extract_role


class _FakeChatModel(BaseChatModel):
    """Chat model determinístico para teste — nunca faz chamada de rede."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        message = AIMessage(
            content="resposta falsa",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "fake"


def test_should_extract_role_when_tag_has_role_prefix():
    """'role:dev_backend' vira 'dev_backend'."""
    assert _extract_role(["role:dev_backend"]) == "dev_backend"


def test_should_return_unknown_when_no_role_tag_present():
    """Sem tag de papel, ou sem tags nenhuma, não derruba o rastreamento."""
    assert _extract_role(["outra_tag"]) == "desconhecido"
    assert _extract_role(None) == "desconhecido"


def test_should_log_usage_when_create_agent_is_invoked(tmp_path, monkeypatch):
    """Fim a fim: create_agent -> invoke -> uma linha nova em usage_log.jsonl,
    já com o papel certo — sem chamar a API de verdade.
    """
    log_path = tmp_path / "usage_log.jsonl"
    handler = UsageCallbackHandler(log_path=log_path)
    monkeypatch.setattr(team, "build_chat_model", lambda *args, **kwargs: _FakeChatModel())
    monkeypatch.setattr(team, "usage_handler", handler)

    agent = team.create_agent("arquiteto")
    agent.invoke({"task": "tarefa de teste"})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["role"] == "arquiteto"
    assert entry["total_tokens"] == 15
