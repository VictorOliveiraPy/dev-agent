"""Supervisor: decide qual especialista do time age em cada rodada.

Diferente dos Passos 2 e 3 (onde a escolha de qual agente chamar era manual,
no código Python), aqui quem decide é o próprio LLM, através de um
roteador com saída estruturada (ver Structured Output). O supervisor não
escreve código — ele só orquestra: lê a tarefa original + o que já foi
feito, decide o PRÓXIMO especialista a agir (ou que o trabalho terminou),
aciona esse especialista, registra o resultado, e repete. É o núcleo de um
sistema multi-agente: um "gerente" que delega, sem conhecer os detalhes de
implementação de cada área.
"""

import logging
from collections.abc import Iterator

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate

from agents.knowledge import search_standards
from agents.llm import build_chat_model
from agents.schemas import Decision
from agents.team import (
    create_agent,
    create_agent_with_tools,
    extract_agent_output_text,
    run_architect_task,
    run_frontend_task,
)
from agents.tools import list_dir, read_file, run_command, write_file
from agents.usage import usage_handler

logger = logging.getLogger(__name__)

DEFAULT_TOOLS = [write_file, read_file, list_dir, run_command, search_standards]

# Quem produz artefato (código) tem as tools completas; o arquiteto só
# CONFERE fato real (nunca escreve/roda nada) — ver ARCHITECT_TOOLS e
# agents.team.run_architect_task pro porquê disso não é a mesma coisa que
# ROLES_WITH_TOOLS abaixo (saída estruturada, não texto livre).
ARCHITECT_TOOLS = [list_dir, read_file, search_standards]

ROLES_WITH_TOOLS = {"dev_backend", "dev_frontend"}

# 6 bastava pra tarefas de teste (login, favoritos — 1 tela). Uma tarefa
# real com várias seções de conteúdo (ex: fe-catolica) plausivelmente
# precisa de mais idas e vindas entre arquiteto/backend/frontend.
MAX_ROUNDS = 10

# Teto do que volta pro HISTÓRICO reenviado ao roteador a cada rodada — não
# do que é exibido pra quem acompanha (ver `run`, que yield o texto
# INTEIRO). Um resultado de 5000 caracteres multiplicado por várias rodadas
# infla o contexto (e o custo) do roteador sem ganho real: ele só precisa
# saber "o que já foi feito", não reler o output completo de cada etapa.
_HISTORY_SUMMARY_LIMIT = 500


_ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Você é o Tech Lead que orquestra um time (arquiteto, dev_backend, "
        "dev_frontend). Dada a tarefa original e o histórico do que já foi "
        "feito, decida a PRÓXIMA ação. Regra geral: o arquiteto decide a "
        "forma antes do backend implementar, e o backend expõe a API antes "
        "do frontend consumi-la — mas pule etapas óbvias se o histórico "
        "mostrar que já foram cobertas. Só retorne 'concluido' quando a "
        "tarefa estiver de fato IMPLEMENTADA (código escrito de verdade), "
        "nunca apenas planejada ou parcialmente feita.",
    ),
    (
        "human",
        "TAREFA ORIGINAL:\n{task}\n\nHISTÓRICO DO QUE JÁ FOI FEITO:\n{history}",
    ),
])

# O roteador usa saída estruturada (ver agents/schemas.py::Decision) para
# que o "próximo passo" seja um objeto validado, não texto livre pra fazer
# parsing na mão.
#
# with_config aqui é a mesma peça que falta pra QUALQUER chamada real cair
# em usage_log.jsonl (ver agents/team.py::create_agent) — sem isso, o
# custo do próprio roteador (uma chamada real por rodada, sempre) nunca
# aparecia no dashboard nem no painel de tokens do escritório (bug real,
# achado testando office/server.py contra a API de verdade).
_router = (
    (_ROUTER_PROMPT | build_chat_model(max_tokens=2048).with_structured_output(Decision))
    .with_config(callbacks=[usage_handler], tags=["role:supervisor"])
)


def _run_architect(
    instruction: str, extra_callbacks: list[BaseCallbackHandler] | None = None
) -> tuple[str, str]:
    """Aciona o arquiteto com tools somente-leitura (ARCHITECT_TOOLS) e
    saída estruturada, e resume o plano.

    Diferente dos outros papéis (texto livre), o arquiteto devolve um
    ArchitecturePlan de verdade — o resumo é montado a partir dos campos do
    modelo, não de um corte arbitrário de string, então já é enxuto o
    bastante pra não precisar de truncamento separado (mesmo texto serve
    pra exibição e pro histórico do roteador). Ver
    `agents.team.run_architect_task` pro porquê de tools + saída
    estruturada juntos precisarem de um loop próprio, não
    `create_agent`/`create_agent_with_tools` direto.
    """
    plan = run_architect_task(instruction, ARCHITECT_TOOLS, extra_callbacks=extra_callbacks)

    files = ", ".join(f.path for f in plan.files) or "(nenhum arquivo listado)"
    text = (
        f"[arquiteto] instrução: {instruction}\n"
        f"projeto: {plan.project_name} | stack: {plan.stack}\n"
        f"resumo: {plan.summary}\n"
        f"arquivos planejados: {files}"
    )
    return text, text


def _run_role_with_tools(
    role: str, instruction: str, extra_callbacks: list[BaseCallbackHandler] | None = None
) -> tuple[str, str]:
    """Aciona um especialista com tools (hoje só dev_backend — dev_frontend
    tem seu próprio fluxo, ver `_run_frontend`) e resume o resultado.

    Returns:
        `(texto_completo, texto_pro_historico)` — o primeiro é pra quem
        acompanha a execução (ver `run`), sem cortar nada; o segundo é o
        que volta pro roteador na próxima rodada, truncado (ver
        `_HISTORY_SUMMARY_LIMIT`).
    """
    agent = create_agent_with_tools(role, DEFAULT_TOOLS, extra_callbacks=extra_callbacks)
    result = agent.invoke({"task": instruction})
    output_text = extract_agent_output_text(result)
    full = f"[{role}] instrução: {instruction}\nresultado: {output_text}"
    for_history = (
        f"[{role}] instrução: {instruction}\nresultado: {output_text[:_HISTORY_SUMMARY_LIMIT]}"
    )
    return full, for_history


def _run_frontend(
    instruction: str, extra_callbacks: list[BaseCallbackHandler] | None = None
) -> tuple[str, str]:
    """Aciona o dev_frontend em duas etapas (ver `agents.team.run_frontend_task`):
    primeiro decide um DesignPlan estruturado (paleta, tipografia, layout —
    standards/design.md), depois implementa já seguindo esse plano.

    O resumo que vai pro histórico do Supervisor inclui o plano decidido —
    assim, se o Supervisor mandar o dev_frontend fazer uma SEGUNDA tela
    depois, o histórico já mostra a paleta/tipografia escolhidas, em vez de
    cada tela decidir a própria identidade visual do zero.

    Returns:
        `(texto_completo, texto_pro_historico)` — ver `_run_role_with_tools`.
    """
    plan, output_text = run_frontend_task(
        instruction, DEFAULT_TOOLS, extra_callbacks=extra_callbacks
    )
    brief = plan.to_brief()
    full = f"[dev_frontend] instrução: {instruction}\n{brief}\nresultado: {output_text}"
    for_history = (
        f"[dev_frontend] instrução: {instruction}\n"
        f"{brief}\nresultado: {output_text[:_HISTORY_SUMMARY_LIMIT]}"
    )
    return full, for_history


def run(task: str, *, extra_callbacks: list[BaseCallbackHandler] | None = None) -> Iterator[str]:
    """Roda o loop supervisor -> especialista até a tarefa ser concluída.

    É um GERADOR, não uma função que devolve tudo de uma vez: cada entrada
    (decisão do supervisor, depois resultado do especialista) é entregue
    assim que acontece, o que permite acompanhar a "conversa" do time em
    tempo real (ver `web_ui.py`) em vez de só ver o resultado final depois
    de todas as rodadas rodarem. Quem só quer o histórico completo continua
    funcionando igual (`list(run(task))` ou um `for` simples — ver
    `team_supervisor.py`).

    Args:
        task: descrição do que o time deve entregar.
        extra_callbacks: repassado aos papéis com tools (dev_backend,
            dev_frontend) — usado por `office/server.py` pra transmitir
            cada tool call individual em tempo real. `None` (padrão) não
            muda nada pra quem já usava isto antes dessa opção existir.

    Yields:
        Uma entrada por evento: a decisão do supervisor (`"[supervisor]
        próximo: ..."`) e o resultado COMPLETO (sem truncar) de cada
        especialista acionado, na ordem em que acontecem.
    """
    # Histórico interno, passado de volta pro roteador a cada rodada — só
    # decisões de especialista (arquiteto/backend/frontend) e avisos
    # terminais entram aqui. A linha de "próximo: X — motivo" (yielded logo
    # abaixo) fica FORA de propósito: é comentário do supervisor sobre a
    # própria decisão, não um resultado de trabalho — incluí-la faria o
    # roteador ler sua própria justificativa anterior como se fosse um fato
    # já realizado.
    history: list[str] = []

    for round_num in range(1, MAX_ROUNDS + 1):
        history_text = "\n".join(history) if history else "(nada feito ainda)"
        decision = _router.invoke({"task": task, "history": history_text})

        logger.info(
            "Supervisor escolheu o próximo papel",
            extra={
                "round": round_num,
                "next_role": decision.next_role,
                "reasoning": decision.reasoning,
            },
        )

        if decision.next_role == "concluido":
            entry = "[supervisor] Deu a tarefa como concluída."
            history.append(entry)
            yield entry
            break

        yield f"[supervisor] próximo: {decision.next_role} — {decision.reasoning}"

        if decision.next_role == "arquiteto":
            display_text, history_text = _run_architect(decision.instruction, extra_callbacks)
        elif decision.next_role == "dev_frontend":
            display_text, history_text = _run_frontend(decision.instruction, extra_callbacks)
        elif decision.next_role in ROLES_WITH_TOOLS:
            display_text, history_text = _run_role_with_tools(
                decision.next_role, decision.instruction, extra_callbacks
            )
        else:
            agent = create_agent(decision.next_role)
            output_text = agent.invoke({"task": decision.instruction})
            display_text = (
                f"[{decision.next_role}] instrução: {decision.instruction}\n"
                f"resultado: {output_text}"
            )
            history_text = (
                f"[{decision.next_role}] instrução: {decision.instruction}\n"
                f"resultado: {output_text[:_HISTORY_SUMMARY_LIMIT]}"
            )

        history.append(history_text)
        yield display_text
    else:
        entry = f"[supervisor] Parou por atingir o limite de {MAX_ROUNDS} rodadas."
        history.append(entry)
        yield entry
