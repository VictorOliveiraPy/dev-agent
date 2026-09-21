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
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from agents.llm import build_chat_model, current_provider
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

# Papéis que usam um modelo mais barato que o padrão (Opus 5) — só o
# arquiteto, que apenas opina em texto (sem tools, sem escrever arquivo).
# dev_backend/dev_frontend ficam de fora de propósito: escrevem arquivo de
# verdade via tool calling (create_agent_with_tools), e um modelo mais fraco
# aí arrisca código pior ou tool call malformada — custa mais em retrabalho
# do que economiza em tokens (mesmo risco que já vimos ao testar Ollama
# local, ver agents/llm.py). Um papel sem entrada aqui usa o padrão da
# fábrica de modelo (Opus 5).
#
# IDs específicos da Anthropic — só fazem sentido sob esse provedor. Não
# existe hoje um "Haiku do DeepSeek" (o catálogo é bem menor), então sob
# `LLM_PROVIDER=deepseek` este mapa é ignorado de propósito (ver
# `_model_override_for`) e todo papel usa o default do provedor ativo.
_ROLE_MODELS: dict[str, str] = {
    "arquiteto": "claude-haiku-4-5",
}


def _model_override_for(role: str) -> str | None:
    """Resolve o override de modelo de um papel, só sob o provedor
    Anthropic — ver nota em `_ROLE_MODELS`."""
    if current_provider() != "anthropic":
        return None
    return _ROLE_MODELS.get(role)

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

    return "\n\n".join(parts)


def _system_message(persona: str) -> SystemMessage:
    """Constrói a mensagem de sistema com prompt caching explícito.

    A persona (papel + `standards/*.md`) é IDÊNTICA em toda chamada de um
    mesmo papel — e é reenviada inteira a cada iteração do loop de tool
    calling (ver `create_agent_with_tools`), então cacheá-la é o maior
    ganho de custo do projeto (ver ARCHITECTURE.md, seção "Custo").
    `cache_control` no bloco marca esse prefixo como cacheável; a mensagem
    "human" que vem depois (a tarefa, que muda a cada chamada) fica de
    fora do cache de propósito.

    Construir a SystemMessage diretamente (em vez da tupla `("system",
    persona)` do ChatPromptTemplate) tem um efeito colateral bom: essa
    tupla trata a string como TEMPLATE f-string, então chaves literais de
    exemplo de código (`extra={"user_id": user.id}`) precisavam ser
    escapadas — bug real que já apareceu. Uma SystemMessage já pronta não
    passa pelo motor de template, então o escape deixou de ser necessário.
    """
    return SystemMessage(content=[
        {"type": "text", "text": persona, "cache_control": {"type": "ephemeral"}}
    ])


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
        _system_message(persona),
        ("human", "{task}"),
    ])
    model = build_chat_model(model=_model_override_for(role))

    if output_schema is not None:
        chain = prompt | model.with_structured_output(output_schema)
    else:
        chain = prompt | model | StrOutputParser()

    # with_config "gruda" o callback de uso de tokens e a tag de papel em
    # QUALQUER invocação futura desta chain — quem chama .invoke() não
    # precisa saber que isso existe (ver agents/usage.py e dashboard.py).
    return chain.with_config(callbacks=[usage_handler], tags=[f"role:{role}"])


def create_agent_with_tools(
    role: str, tools: list[BaseTool], *, extra_callbacks: list[BaseCallbackHandler] | None = None
) -> Runnable:
    """Monta um AgentExecutor: a persona do papel + um loop de tool calling.

    Diferente de `create_agent` (chain fixa prompt -> model -> parser), aqui
    o modelo decide sozinho QUANDO e QUANTAS vezes chamar cada tool, dentro
    de um loop controlado pelo AgentExecutor — é o que permite ao papel agir
    de verdade (escrever arquivos, rodar comandos) em vez de só opinar.

    Args:
        role: uma chave de ROLES.
        tools: lista de tools (ex: write_file, read_file) que esse papel
            pode chamar.
        extra_callbacks: callbacks adicionais anexados só nesta chamada, além
            do `usage_handler` padrão — usado por `office/server.py` pra
            transmitir cada tool call individual em tempo real, sem exigir
            que quem não precisa disso (CLI, `web_ui.py`) saiba que essa
            opção existe.

    Returns:
        Um Runnable (AgentExecutor com callback/tag de uso já anexados)
        pronto para `.invoke({"task": ...})`.
    """
    persona = _build_persona(role)
    prompt = ChatPromptTemplate.from_messages([
        _system_message(persona),
        ("human", "{task}"),
        # agent_scratchpad: onde o AgentExecutor injeta o histórico de
        # tool_use/tool_result de cada iteração do loop, dentro desta
        # mesma tarefa.
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    # max_tokens maior que o padrão (8192): um loop agentic escrevendo
    # vários arquivos tem mais chance de estourar o teto padrão no meio de
    # uma tool call (o mesmo tipo de corte que já aconteceu antes — ver
    # ARCHITECTURE.md) do que uma chamada de texto/planejamento única.
    model = build_chat_model(max_tokens=16000)
    agent = create_tool_calling_agent(model, tools, prompt)
    # NÃO existe `handle_tool_error` no `AgentExecutor` desta versão do
    # LangChain (0.3.30) — só em `handle_parsing_errors`, que é outra
    # coisa (erro de PARSING da saída do modelo, não de execução da
    # tool). Passar `handle_tool_error=True` aqui seria aceito em
    # silêncio pelo Pydantic e não faria NADA — bug real que já
    # aconteceu nesta base de código. O lugar certo é por TOOL: ver
    # `agents/tools.py`, onde cada tool já sai com `handle_tool_error =
    # True` setado — é isso que faz uma `ToolException` (ex.: sandbox
    # violada) virar observação pro modelo em vez de derrubar o loop.
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=40)
    # Mesma ideia de create_agent: cada chamada ao modelo dentro do loop de
    # tool calling também cai no usage_log.jsonl, marcada com este papel.
    callbacks: list[BaseCallbackHandler] = [usage_handler, *(extra_callbacks or [])]
    return executor.with_config(callbacks=callbacks, tags=[f"role:{role}"])


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


def run_frontend_task(
    task: str, tools: list[BaseTool], *, extra_callbacks: list[BaseCallbackHandler] | None = None
) -> tuple[DesignPlan, str]:
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
        extra_callbacks: repassado à etapa de implementação (a única com
            tools) — ver `create_agent_with_tools`.

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
    agent = create_agent_with_tools("dev_frontend", tools, extra_callbacks=extra_callbacks)
    result = agent.invoke({"task": implementation_task})

    return plan, extract_agent_output_text(result)
