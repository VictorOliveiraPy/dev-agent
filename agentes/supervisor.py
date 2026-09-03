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

from langchain_core.prompts import ChatPromptTemplate

from agentes.llm import build_chat_model
from agentes.schemas import ArchitecturePlan, Decision
from agentes.team import create_agent, create_agent_with_tools
from agentes.tools import list_dir, read_file, run_command, write_file

logger = logging.getLogger(__name__)

DEFAULT_TOOLS = [write_file, read_file, list_dir, run_command]

# Só quem produz artefatos (código) precisa de tools; o arquiteto só opina
# (com saída estruturada — ver ArchitecturePlan).
ROLES_WITH_TOOLS = {"dev_backend", "dev_frontend"}

MAX_ROUNDS = 6


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

# O roteador usa saída estruturada (ver agentes/schemas.py::Decision) para
# que o "próximo passo" seja um objeto validado, não texto livre pra fazer
# parsing na mão.
_router = _ROUTER_PROMPT | build_chat_model(max_tokens=2048).with_structured_output(Decision)


def _run_architect(instruction: str) -> str:
    """Aciona o arquiteto com saída estruturada e resume o plano pro histórico.

    Diferente dos outros papéis (texto livre truncado), o arquiteto devolve
    um ArchitecturePlan de verdade — o resumo abaixo é montado a partir dos
    campos do modelo, não de um corte arbitrário de string.
    """
    agent = create_agent("arquiteto", output_schema=ArchitecturePlan)
    plan = agent.invoke({"task": instruction})

    files = ", ".join(f.path for f in plan.files) or "(nenhum arquivo listado)"
    return (
        f"[arquiteto] instrução: {instruction}\n"
        f"projeto: {plan.project_name} | stack: {plan.stack}\n"
        f"resumo: {plan.summary}\n"
        f"arquivos planejados: {files}"
    )


def _run_role_with_tools(role: str, instruction: str) -> str:
    """Aciona um especialista com tools (dev_backend/dev_frontend) e resume o resultado."""
    agent = create_agent_with_tools(role, DEFAULT_TOOLS)
    result = agent.invoke({"task": instruction})
    output_text = result["output"]

    # A última mensagem do modelo pode vir como lista de content blocks
    # (thinking + texto) em vez de string pronta — normalizamos aqui.
    if isinstance(output_text, list):
        output_text = "".join(b.get("text", "") for b in output_text if b.get("type") == "text")

    return f"[{role}] instrução: {instruction}\nresultado: {output_text[:500]}"


def run(task: str) -> list[str]:
    """Roda o loop supervisor -> especialista até a tarefa ser concluída.

    Args:
        task: descrição do que o time deve entregar.

    Returns:
        O histórico de ações executadas (uma entrada por rodada), na ordem
        em que aconteceram.
    """
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
            history.append("[supervisor] Deu a tarefa como concluída.")
            break

        if decision.next_role == "arquiteto":
            summary = _run_architect(decision.instruction)
        elif decision.next_role in ROLES_WITH_TOOLS:
            summary = _run_role_with_tools(decision.next_role, decision.instruction)
        else:
            agent = create_agent(decision.next_role)
            output_text = agent.invoke({"task": decision.instruction})
            summary = (
                f"[{decision.next_role}] instrução: {decision.instruction}\n"
                f"resultado: {output_text[:500]}"
            )

        history.append(summary)
    else:
        history.append(f"[supervisor] Parou por atingir o limite de {MAX_ROUNDS} rodadas.")

    return history
