"""Testes para a montagem de persona do time (agents/team.py).

Só cobre lógica pura e determinística — nenhum destes testes chama a API
da Anthropic.
"""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agents import team
from agents.schemas import ColorToken, DesignPlan


class _RecordingFakeChatModel(BaseChatModel):
    """Chat model falso que grava as mensagens recebidas, pra inspecionar
    o que de fato chegaria à API — sem chamar a API de verdade.
    """

    received_messages: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.received_messages.append(messages)
        message = AIMessage(
            content="resposta falsa",
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "fake"


@pytest.fixture
def standards_dir(tmp_path, monkeypatch):
    """Aponta agents.team._STANDARDS_DIR para uma pasta de padrões isolada."""
    monkeypatch.setattr(team, "_STANDARDS_DIR", tmp_path)
    return tmp_path


def test_should_include_only_general_standards_when_role_has_no_specific_file(standards_dir):
    """Um papel sem entrada em _ROLE_STANDARDS só recebe general.md na persona."""
    (standards_dir / "general.md").write_text("Regra geral X", encoding="utf-8")

    persona = team._build_persona("arquiteto")

    assert "Regra geral X" in persona
    assert "Padrões específicos" not in persona


def test_should_include_role_specific_standards_when_file_exists(standards_dir):
    """dev_backend recebe general.md + backend.md na mesma persona."""
    (standards_dir / "general.md").write_text("Regra geral X", encoding="utf-8")
    (standards_dir / "backend.md").write_text("Regra de backend Y", encoding="utf-8")

    persona = team._build_persona("dev_backend")

    assert "Regra geral X" in persona
    assert "Regra de backend Y" in persona


def test_should_keep_curly_braces_unescaped_when_standards_contain_code_examples(standards_dir):
    """_build_persona NÃO escapa chaves — ela devolve texto literal.

    O escape só era necessário quando a persona passava pelo motor de
    template do ChatPromptTemplate (tupla ("system", persona), tratada
    como f-string). Isso mudou: agora a persona vira uma SystemMessage já
    pronta (ver `_system_message`), que não passa por esse motor — chaves
    de exemplo de código chegam intactas no prompt de verdade.
    """
    (standards_dir / "general.md").write_text('extra={"user_id": user.id}', encoding="utf-8")

    persona = team._build_persona("arquiteto")

    assert 'extra={"user_id": user.id}' in persona
    assert "{{" not in persona


def test_should_mark_system_message_as_cacheable():
    """_system_message anexa cache_control ao bloco — o system prompt (fixo
    por papel) é o maior alvo de prompt caching do projeto, reenviado
    inteiro em toda iteração do loop de tool calling.
    """
    message = team._system_message("persona de teste")

    assert message.content[0]["cache_control"] == {"type": "ephemeral"}
    assert message.content[0]["text"] == "persona de teste"


def test_should_send_cache_control_to_model_when_create_agent_is_invoked(monkeypatch):
    """Fim a fim: create_agent monta um prompt cuja mensagem de sistema
    chega ao modelo já marcada com cache_control — não só a unidade
    _system_message isolada, mas o wiring completo de create_agent.
    """
    fake_model = _RecordingFakeChatModel()
    monkeypatch.setattr(team, "build_chat_model", lambda *args, **kwargs: fake_model)

    agent = team.create_agent("dev_backend")
    agent.invoke({"task": "tarefa de teste"})

    assert len(fake_model.received_messages) == 1
    system_message = fake_model.received_messages[0][0]
    assert system_message.content[0]["cache_control"] == {"type": "ephemeral"}


def test_should_use_haiku_for_arquiteto_but_default_model_for_other_roles(monkeypatch):
    """arquiteto é o único papel em _ROLE_MODELS (só opina em texto, sem
    tools) — dev_backend/dev_frontend continuam no padrão da fábrica de
    modelo (Opus 5), por escreverem arquivo de verdade via tool calling.
    """
    captured_models = []

    def fake_build_chat_model(*args, **kwargs):
        captured_models.append(kwargs.get("model"))
        return _RecordingFakeChatModel()

    monkeypatch.setattr(team, "build_chat_model", fake_build_chat_model)

    team.create_agent("arquiteto")
    team.create_agent("dev_backend")

    assert captured_models == ["claude-haiku-4-5", None]


def test_should_ignore_role_models_override_when_provider_is_not_anthropic(monkeypatch):
    """_ROLE_MODELS guarda IDs específicos da Anthropic (ex.: claude-haiku-4-5)
    — sob LLM_PROVIDER=deepseek eles não fazem sentido, então o arquiteto
    também cai no default do provedor ativo, igual aos outros papéis."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    captured_models = []

    def fake_build_chat_model(*args, **kwargs):
        captured_models.append(kwargs.get("model"))
        return _RecordingFakeChatModel()

    monkeypatch.setattr(team, "build_chat_model", fake_build_chat_model)

    team.create_agent("arquiteto")

    assert captured_models == [None]


def test_should_return_empty_string_when_standard_file_is_missing(standards_dir):
    """Um arquivo de padrão que não existe não derruba a montagem da persona."""
    assert team._read_standard("nao_existe.md") == ""


def test_should_extract_text_when_agent_output_is_content_block_list():
    """O campo 'output' de um AgentExecutor pode vir como lista de blocks
    (thinking + texto) em vez de string pronta — extract_agent_output_text
    normaliza os dois formatos.
    """
    blocks = [
        {"type": "thinking", "thinking": "raciocínio interno"},
        {"type": "text", "text": "resposta final"},
    ]

    assert team.extract_agent_output_text({"output": blocks}) == "resposta final"
    assert team.extract_agent_output_text({"output": "já é texto"}) == "já é texto"


def test_should_pass_design_plan_into_implementation_task_when_running_frontend_task(monkeypatch):
    """run_frontend_task chama o planner (DesignPlan) primeiro e repassa o
    plano decidido como parte da tarefa do agente de implementação — a
    implementação não decide cor/fonte de novo.
    """
    fixed_plan = DesignPlan(
        colors=[
            ColorToken(name="accent", hex="#2A6F4D"),
            ColorToken(name="surface", hex="#F4F1EA"),
            ColorToken(name="text", hex="#1A1A1A"),
            ColorToken(name="muted", hex="#6B7280"),
        ],
        display_font="Fraunces",
        body_font="Source Sans 3",
        layout_concept="Sidebar fixa + conteúdo em cards de largura igual.",
    )

    class _FakePlanner:
        def invoke(self, inputs):
            assert "design system" in inputs["task"]
            return fixed_plan

    captured_implementation_task = {}

    class _FakeImplementer:
        def invoke(self, inputs):
            captured_implementation_task["task"] = inputs["task"]
            return {"output": "código gerado"}

    def fake_create_agent(role, output_schema=None):
        assert role == "dev_frontend"
        assert output_schema is DesignPlan
        return _FakePlanner()

    def fake_create_agent_with_tools(role, tools, *, extra_callbacks=None):
        assert role == "dev_frontend"
        return _FakeImplementer()

    monkeypatch.setattr(team, "create_agent", fake_create_agent)
    monkeypatch.setattr(team, "create_agent_with_tools", fake_create_agent_with_tools)

    plan, output_text = team.run_frontend_task("crie a tela de login", tools=[])

    assert plan is fixed_plan
    assert output_text == "código gerado"
    assert "Fraunces" in captured_implementation_task["task"]
    assert "crie a tela de login" in captured_implementation_task["task"]
