"""Definição do time: cada "papel" é uma persona (system prompt) que, somada
à fábrica de modelo, forma um agente especializado.

As personas são compostas em duas camadas: a descrição do papel (fixa,
abaixo) + os padrões de código do time, lidos de `standards/*.md` em runtime
(ver `_build_persona`). Isso separa "quem esse agente é" (código Python)
de "que convenções ele deve seguir" (arquivos .md editáveis sem tocar em
Python — mesma ideia de um CLAUDE.md).
"""

from pathlib import Path

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from agents.llm import build_chat_model
from agents.schemas import DesignPlan
from agents.usage import usage_handler

# Cada entrada é o "system prompt" que define o papel dentro do time.
ROLES: dict[str, str] = {
    "arquiteto": (
        "Você é o Arquiteto de Software do time. Decide stack, estrutura de "
        "pastas e o contrato (API/dados) entre backend e frontend. Não "
        "escreve código de implementação, só a forma do projeto — em poucos "
        "parágrafos, direto ao ponto."
    ),
    "dev_backend": (
        "Você é o Engenheiro Backend do time, especialista em Python/FastAPI. "
        "Foca em endpoints, modelos de dados e regras de negócio no servidor. "
        "Responda pela ótica do backend, sem se preocupar com a UI."
    ),
    "dev_frontend": (
        "Você é o Engenheiro Frontend do time, especialista em Next.js/React/"
        "TypeScript. Foca em componentes, chamadas à API e experiência do "
        "usuário. Responda pela ótica do frontend, sem se preocupar com o "
        "servidor."
    ),
}

# Quais arquivos de padrões (além de general.md, sempre incluído) cada papel
# recebe na própria persona. Um papel sem entrada aqui só vê general.md.
_ROLE_STANDARDS: dict[str, list[str]] = {
    "dev_backend": ["backend.md"],
    "dev_frontend": ["frontend.md", "design.md"],
}

_STANDARDS_DIR = Path(__file__).parent.parent / "standards"


def _read_standard(filename: str) -> str:
    """Lê um arquivo de padrões; devolve "" se ele não existir (opcional)."""
    path = _STANDARDS_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _build_persona(role: str) -> str:
    """Junta a descrição do papel aos padrões de código aplicáveis a ele.

    Sempre inclui `standards/general.md` (se existir) e, adicionalmente, os
    arquivos listados em `_ROLE_STANDARDS[role]`. O resultado é o system
    prompt final enviado ao modelo — os .md viram parte do prompt, não são
    lidos via tool (ver Aula/Passo sobre RAG para o padrão alternativo, de
    leitura sob demanda).
    """
    parts = [ROLES[role]]

    general = _read_standard("general.md")
    if general:
        parts.append(f"## Padrões gerais do time (sempre siga):\n{general}")

    for filename in _ROLE_STANDARDS.get(role, []):
        content = _read_standard(filename)
        if content:
            parts.append(f"## Padrões específicos ({filename}):\n{content}")

    final_persona = "\n\n".join(parts)

    # ChatPromptTemplate trata a string do "system" como um template
    # f-string por padrão: qualquer '{' literal (ex: exemplo de código com
    # `extra={"user_id": user.id}` nos .md de padrões) seria interpretado
    # como início de variável e quebra a montagem do prompt (bug real que
    # apareceu ao adicionar exemplos de código em standards/backend.md).
    # Escapamos aqui porque a persona é conteúdo literal, nunca um template
    # com variáveis de verdade — {task} continua funcionando porque vive
    # numa mensagem "human" separada, não dentro da persona.
    return final_persona.replace("{", "{{").replace("}", "}}")


def create_agent(role: str, output_schema: type[BaseModel] | None = None) -> Runnable:
    """Monta a chain LCEL (prompt | model | parser) de um papel do time.

    Args:
        role: uma chave de ROLES (ex: "arquiteto").
        output_schema: se informado, a chain devolve uma INSTÂNCIA desse
            modelo Pydantic (saída estruturada — ver
            `agents.schemas.ArchitecturePlan`) em vez de texto solto. Sem
            isso, o comportamento padrão (texto) é mantido.

    Returns:
        Um Runnable que recebe {"task": str} e devolve a resposta já sob a
        perspectiva daquele papel — texto (padrão) ou uma instância de
        `output_schema`, se informado.

    Raises:
        KeyError: se `role` não existir em ROLES.
    """
    persona = _build_persona(role)
    prompt = ChatPromptTemplate.from_messages([
        ("system", persona),
        ("human", "{task}"),
    ])
    model = build_chat_model()

    if output_schema is not None:
        chain = prompt | model.with_structured_output(output_schema)
    else:
        chain = prompt | model | StrOutputParser()

    # with_config "gruda" o callback de uso de tokens e a tag de papel em
    # QUALQUER invocação futura desta chain — quem chama .invoke() não
    # precisa saber que isso existe (ver agents/usage.py e dashboard.py).
    return chain.with_config(callbacks=[usage_handler], tags=[f"role:{role}"])


def create_agent_with_tools(role: str, tools: list[BaseTool]) -> Runnable:
    """Monta um AgentExecutor: a persona do papel + um loop de tool calling.

    Diferente de `create_agent` (chain fixa prompt -> model -> parser), aqui
    o modelo decide sozinho QUANDO e QUANTAS vezes chamar cada tool, dentro
    de um loop controlado pelo AgentExecutor — é o que permite ao papel agir
    de verdade (escrever arquivos, rodar comandos) em vez de só opinar.

    Args:
        role: uma chave de ROLES.
        tools: lista de tools (ex: write_file, read_file) que esse papel
            pode chamar.

    Returns:
        Um Runnable (AgentExecutor com callback/tag de uso já anexados)
        pronto para `.invoke({"task": ...})`.
    """
    persona = _build_persona(role)
    prompt = ChatPromptTemplate.from_messages([
        ("system", persona),
        ("human", "{task}"),
        # agent_scratchpad: onde o AgentExecutor injeta o histórico de
        # tool_use/tool_result de cada iteração do loop, dentro desta
        # mesma tarefa.
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    model = build_chat_model()
    agent = create_tool_calling_agent(model, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=40)
    # Mesma ideia de create_agent: cada chamada ao modelo dentro do loop de
    # tool calling também cai no usage_log.jsonl, marcada com este papel.
    return executor.with_config(callbacks=[usage_handler], tags=[f"role:{role}"])


def extract_agent_output_text(result: dict) -> str:
    """Normaliza o campo 'output' de um AgentExecutor pra string.

    A última mensagem do modelo pode vir como lista de content blocks
    (thinking + texto) em vez de string pronta — helper único pra não
    repetir esse `isinstance` em cada script de entrada (Passos 2-4).
    """
    output = result["output"]
    if isinstance(output, list):
        return "".join(block.get("text", "") for block in output if block.get("type") == "text")
    return output


def run_frontend_task(task: str, tools: list[BaseTool]) -> tuple[DesignPlan, str]:
    """Executa o dev_frontend em DUAS etapas, em vez de uma só.

    Etapa 1 (sem tools): o dev_frontend decide um DesignPlan estruturado
    (paleta, tipografia, conceito de layout — ver
    standards/design.md::"Decida a paleta e a tipografia ANTES do código").
    Etapa 2 (com tools): o dev_frontend implementa o código de verdade,
    recebendo o plano da etapa 1 já pronto (via `DesignPlan.to_brief()`)
    como parte da própria tarefa — não decide cor/fonte de novo componente
    a componente, só segue o que já foi decidido.

    Args:
        task: descrição da tarefa de frontend, em linguagem natural.
        tools: tools que a etapa de implementação pode usar (ex:
            write_file, read_file).

    Returns:
        Uma tupla `(plano_decidido, texto_de_saida_da_implementacao)`.
    """
    planner = create_agent("dev_frontend", output_schema=DesignPlan)
    plan = planner.invoke({
        "task": (
            "Antes de implementar qualquer componente, decida o design "
            f"system (paleta, tipografia, layout) para esta tarefa:\n{task}"
        )
    })

    implementation_task = f"{plan.to_brief()}\n\nTarefa:\n{task}"
    agent = create_agent_with_tools("dev_frontend", tools)
    result = agent.invoke({"task": implementation_task})

    return plan, extract_agent_output_text(result)
