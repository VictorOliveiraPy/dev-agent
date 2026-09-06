"""Testes para o loop do Supervisor (agents/supervisor.py::run).

Só cobre o roteamento (quem decide o quê, na ordem certa) — nenhum destes
testes chama a API da Anthropic de verdade: o roteador (_router) e os
especialistas com tools são substituídos por fakes.
"""

from agents import supervisor
from agents.schemas import Decision


class _FakeRouter:
    """Substitui `agents.supervisor._router` — devolve uma Decision por vez,
    na ordem passada, em vez de chamar o modelo de verdade.
    """

    def __init__(self, decisions: list[Decision]):
        self._decisions = iter(decisions)

    def invoke(self, _inputs):
        return next(self._decisions)


class _FakeAgentWithTools:
    def __init__(self, output_text: str):
        self._output_text = output_text

    def invoke(self, _inputs):
        return {"output": self._output_text}


def test_should_yield_decision_then_summary_then_stop_when_router_concludes(monkeypatch):
    """Uma rodada com um especialista, depois 'concluido' — a ordem das
    entradas emitidas é: decisão do supervisor, resumo do especialista,
    aviso final de conclusão.
    """
    decisions = [
        Decision(next_role="dev_backend", instruction="crie o endpoint X", reasoning="motivo A"),
        Decision(next_role="concluido", instruction="", reasoning="tudo pronto"),
    ]
    monkeypatch.setattr(supervisor, "_router", _FakeRouter(decisions))
    monkeypatch.setattr(
        supervisor,
        "create_agent_with_tools",
        lambda role, tools: _FakeAgentWithTools("endpoint criado"),
    )

    entries = list(supervisor.run("tarefa de teste"))

    assert len(entries) == 3
    assert entries[0] == "[supervisor] próximo: dev_backend — motivo A"
    assert entries[1].startswith("[dev_backend] instrução: crie o endpoint X")
    assert "endpoint criado" in entries[1]
    assert entries[2] == "[supervisor] Deu a tarefa como concluída."


def test_should_stop_after_max_rounds_when_router_never_concludes(monkeypatch):
    """Se o roteador nunca devolver 'concluido', o loop para no limite de
    rodadas (MAX_ROUNDS) em vez de rodar pra sempre.
    """
    decision = Decision(next_role="dev_backend", instruction="crie X", reasoning="motivo")
    monkeypatch.setattr(supervisor, "_router", _FakeRouter([decision] * supervisor.MAX_ROUNDS))
    monkeypatch.setattr(
        supervisor,
        "create_agent_with_tools",
        lambda role, tools: _FakeAgentWithTools("feito"),
    )

    entries = list(supervisor.run("tarefa de teste"))

    # 2 entradas por rodada (decisão + resumo) + o aviso final de limite.
    assert len(entries) == supervisor.MAX_ROUNDS * 2 + 1
    expected_final = f"[supervisor] Parou por atingir o limite de {supervisor.MAX_ROUNDS} rodadas."
    assert entries[-1] == expected_final


def test_should_not_feed_supervisor_reasoning_back_into_router_history(monkeypatch):
    """A linha "[supervisor] próximo: ..." é emitida pra quem consome o
    gerador (ver web_ui.py), mas NÃO deve ser incluída no histórico
    reenviado ao roteador — ver o comentário em run() sobre por que isso
    poluiria o contexto com a própria justificativa do supervisor.
    """
    decisions = [
        Decision(next_role="dev_backend", instruction="crie X", reasoning="motivo A"),
        Decision(next_role="concluido", instruction="", reasoning="pronto"),
    ]
    fake_router = _FakeRouter(decisions)
    captured_history_texts = []

    def recording_invoke(inputs):
        captured_history_texts.append(inputs["history"])
        return next(fake_router._decisions)

    fake_router.invoke = recording_invoke
    monkeypatch.setattr(supervisor, "_router", fake_router)
    monkeypatch.setattr(
        supervisor,
        "create_agent_with_tools",
        lambda role, tools: _FakeAgentWithTools("feito"),
    )

    list(supervisor.run("tarefa de teste"))

    # Na 2ª rodada, o histórico enviado ao roteador tem o resumo do
    # dev_backend, mas não a linha "próximo: dev_backend — motivo A".
    assert "próximo:" not in captured_history_texts[1]
    assert "feito" in captured_history_texts[1]
