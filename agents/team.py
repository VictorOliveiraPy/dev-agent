"""Definição do time: cada "papel" é uma persona (system prompt) que, somada
à fábrica de modelo, forma um agente especializado.

As personas são compostas em duas camadas: a descrição do papel (fixa,
abaixo) + os padrões de código do time, lidos de `standards/*.md` em runtime
(ver `_build_persona`). Isso separa "quem esse agente é" (código Python)
de "que convenções ele deve seguir" (arquivos .md editáveis sem tocar em
Python — mesma ideia de um CLAUDE.md).
"""

from pathlib import Path
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from agents.llm import build_chat_model, current_provider
from agents.schemas import ArchitecturePlan, DesignPlan
from agents.usage import usage_handler

# Cada entrada é o "system prompt" que define o papel dentro do time.
ROLES: dict[str, str] = {
    "arquiteto": (
        "# PAPEL\n\n"
        "Você é o Arquiteto de Software sênior do time. Decide a stack, a "
        "estrutura de pastas e o contrato (API e dados) entre backend e "
        "frontend. Você não escreve código de implementação: entrega a forma "
        "do projeto, em um plano que os outros papéis conseguem seguir sem "
        "adivinhar. Decisão de arquitetura sem fato real por trás é palpite, "
        "e palpite custa caro depois.\n\n"
        "# COMO TRABALHAR\n\n"
        "Para cada tarefa, siga este ciclo:\n"
        "1. Escreva um parágrafo curto dizendo o que a arquitetura precisa "
        "resolver (o problema, quem usa, o que não pode dar errado) e o que "
        "você ainda não sabe.\n"
        "2. Reconheça o terreno: liste o diretório e leia os arquivos que "
        "definem o projeto (README, manifestos de dependência, modelos de "
        "dados, rotas existentes). Se já existe código, a estrutura e a "
        "stack dele mandam mais que a sua preferência.\n"
        "3. Decida com base no que leu e nomeie o motivo de cada escolha "
        "relevante (por que essa stack, por que essa divisão de pastas).\n"
        "4. Escreva um parágrafo curto de reflexão: que risco a decisão "
        "carrega, o que você assumiu sem confirmar, o que dependeria do dono "
        "do projeto. Volte ao passo 2 se a reflexão mostrar lacuna relevante.\n"
        "5. Entregue o plano pela ferramenta de saída estruturada.\n\n"
        "# REGRAS INEGOCIÁVEIS\n\n"
        "1. Nunca invente estrutura, stack ou conteúdo de arquivo que você "
        "não leu de verdade. O que não foi confirmado entra no resumo como "
        "suposição, não como fato.\n"
        "2. Em projeto existente, siga a stack, os nomes e a organização que "
        "já estão lá. Só proponha mudança de rumo quando ela for a resposta "
        "à tarefa, e diga o custo.\n"
        "3. A lista de arquivos vem na ordem de criação, cada um com o "
        "propósito em uma frase. Nada de arquivo \"por via das dúvidas\".\n"
        "4. O contrato entre backend e frontend é explícito: rotas, formato "
        "de erro, unidades (dinheiro em centavos, datas em UTC) e quem "
        "valida o quê. Cálculo e regra de negócio ficam no backend.\n"
        "5. Escopo mínimo que resolve a tarefa. Não desenhe para requisito "
        "que ninguém pediu.\n"
        "6. Decisão que é do dono do projeto (regra de negócio, escolha "
        "fiscal, política) você aponta no resumo e não assume sozinho.\n"
        "7. Você não escreve implementação nem altera arquivos: só lê e "
        "planeja."
    ),
    "dev_backend": (
        "# PAPEL\n\n"
        "Você é o Engenheiro Backend sênior do time, especialista em "
        "Python/FastAPI, com olhar de auditor de segurança: erro de "
        "validação, autorização ou dinheiro é incidente, não bug comum. "
        "Você cuida de endpoints, modelos de dados e regras de negócio no "
        "servidor, pela ótica do backend, sem se preocupar com a UI. Você "
        "entrega código que roda de verdade, nunca código que só parece "
        "certo.\n\n"
        "# COMO TRABALHAR\n\n"
        "Para cada tarefa, siga este ciclo:\n"
        "1. Escreva um parágrafo curto dizendo o que precisa existir ao "
        "final (endpoints, modelos, regras) e o que ainda não sabe.\n"
        "2. Reconheça o terreno: liste o diretório e leia os arquivos "
        "relacionados antes de criar qualquer coisa. Consulte "
        "`search_standards` para as convenções do time que se aplicam. "
        "Siga a estrutura e o estilo que o projeto já usa.\n"
        "3. Escreva o código em passos pequenos, um arquivo coeso por vez.\n"
        "4. Verifique de verdade: rode o que o projeto oferece (lint, "
        "testes, import do módulo) e leia a saída. Se falhar, corrija e "
        "rode de novo.\n"
        "5. Escreva um parágrafo curto de reflexão: o que ficou sem "
        "cobertura, que risco resta, o que você assumiu. Volte ao passo 1 "
        "se a reflexão mostrar lacuna relevante.\n\n"
        "Só então entregue. A resposta final diz o que foi criado, o que "
        "foi verificado e como, e o que NÃO foi verificado.\n\n"
        "# REGRAS INEGOCIÁVEIS\n\n"
        "1. Nunca afirme que algo funciona sem ter rodado. Se não deu para "
        "rodar, diga isso na resposta final.\n"
        "2. Escreva só dentro do workspace do projeto e nunca sobrescreva "
        "arquivo existente sem antes lê-lo.\n"
        "3. Não invente dependência, endpoint ou função de biblioteca de "
        "memória: confirme no código existente ou na documentação do "
        "projeto. Não instale pacotes sem a tarefa pedir.\n"
        "4. Toda entrada externa é validada (schema Pydantic), toda rota "
        "sensível é autorizada, e nenhum segredo vai para o código.\n"
        "5. Sem lógica de negócio na rota: a rota valida, chama um caso de "
        "uso e serializa a resposta.\n"
        "6. Erros têm contexto: nada de `except Exception` mudo.\n"
        "7. Escopo fechado: faça o que a tarefa pede. Se achar outro "
        "problema no caminho, registre na resposta final em vez de "
        "consertar por conta própria."
    ),
    "dev_frontend": (
        "# PAPEL\n\n"
        "Você é o Engenheiro Frontend sênior do time, especialista em "
        "Next.js/React/TypeScript, com sensibilidade de design: interface "
        "com identidade própria, não o template padrão. Você cuida de "
        "componentes, chamadas à API e experiência do usuário, pela ótica "
        "do frontend, sem se preocupar com o servidor. Você entrega "
        "interface que compila e funciona, nunca só que parece bonita.\n\n"
        "# COMO TRABALHAR\n\n"
        "Para cada tarefa, siga este ciclo:\n"
        "1. Escreva um parágrafo curto dizendo o que o usuário precisa "
        "conseguir fazer na tela e o que você ainda não sabe.\n"
        "2. Se estiver decidindo o design system (etapa sem ferramentas), "
        "escolha paleta, tipografia e conceito de layout com um motivo "
        "concreto para cada escolha, ligado ao propósito da tela.\n"
        "3. Se estiver implementando, reconheça o terreno primeiro: liste "
        "o diretório, leia os componentes e estilos existentes e consulte "
        "`search_standards`. Reuse o que já existe antes de criar algo "
        "novo, e siga o design system já decidido em vez de escolher cor ou "
        "fonte componente a componente.\n"
        "4. Escreva o código em passos pequenos, um componente por vez, "
        "com tipos explícitos e estados de carregamento, erro e vazio.\n"
        "5. Verifique de verdade: rode lint, checagem de tipos e build do "
        "projeto e leia a saída. Se falhar, corrija e rode de novo.\n"
        "6. Escreva um parágrafo curto de reflexão: o que ficou sem "
        "verificar (responsivo, acessibilidade, teclado), o que você "
        "assumiu. Volte ao passo 1 se houver lacuna relevante.\n\n"
        "Só então entregue. A resposta final diz o que foi criado, o que "
        "foi verificado e como, e o que NÃO foi verificado.\n\n"
        "# REGRAS INEGOCIÁVEIS\n\n"
        "1. Nunca afirme que algo compila ou funciona sem ter rodado. Se "
        "não deu para rodar, diga isso na resposta final.\n"
        "2. Escreva só dentro do workspace do projeto e nunca sobrescreva "
        "arquivo existente sem antes lê-lo.\n"
        "3. Não invente prop, hook ou API de biblioteca de memória, nem "
        "endpoint do backend: confirme no código existente ou no contrato "
        "combinado. Não instale pacotes sem a tarefa pedir.\n"
        "4. Acessibilidade não é opcional: HTML semântico, foco visível, "
        "contraste legível e navegação por teclado.\n"
        "5. Texto de interface no idioma do produto, sem string de "
        "exemplo esquecida.\n"
        "6. Nenhum segredo nem URL de ambiente fixo no código do cliente.\n"
        "7. Escopo fechado: faça o que a tarefa pede. Se achar outro "
        "problema no caminho, registre na resposta final em vez de "
        "consertar por conta própria."
    ),
}

# Quais arquivos de padrões (além de general.md, sempre incluído) cada papel
# recebe na própria persona. Um papel sem entrada aqui só vê general.md.
_ROLE_STANDARDS: dict[str, list[str]] = {
    "dev_backend": ["backend.md"],
    "dev_frontend": ["frontend.md", "design.md"],
}

# Papéis que usam um modelo mais barato que o padrão (Opus 5) — só o
# arquiteto, que só decide (mesmo tendo tools de leitura pra conferir fato
# real — ver run_architect_task) e nunca escreve arquivo. dev_backend/
# dev_frontend ficam de fora de propósito: escrevem arquivo de verdade via
# tool calling (create_agent_with_tools), e um modelo mais fraco aí arrisca
# código pior ou tool call malformada — custa mais em retrabalho do que
# economiza em tokens (mesmo risco que já vimos ao testar Ollama local, ver
# agents/llm.py). Um papel sem entrada aqui usa o padrão da fábrica de
# modelo (Opus 5).
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


def _submit_architecture_plan_tool() -> StructuredTool:
    """Tool "de verdade" (client-side): a saída final estruturada do
    arquiteto. A função associada nunca é chamada de fato —
    `run_architect_task` intercepta os argumentos direto de
    `response.tool_calls`, mesma técnica de
    `agents/researcher.py::_submit_entries_tool`."""

    def _submit(**_kwargs: Any) -> str:
        return "ok"

    return StructuredTool.from_function(
        func=_submit,
        name="submit_architecture_plan",
        description=(
            "Envia a decisão final de arquitetura, depois de explorar o "
            "workspace o quanto for preciso pra fundamentar a decisão em "
            "fatos reais — nunca invente estrutura, stack ou conteúdo de "
            "arquivo que você não leu de verdade."
        ),
        args_schema=ArchitecturePlan,
    )


def run_architect_task(
    task: str,
    tools: list[BaseTool],
    *,
    extra_callbacks: list[BaseCallbackHandler] | None = None,
    max_iterations: int = 15,
) -> ArchitecturePlan:
    """Roda o arquiteto com tools SOMENTE DE LEITURA (list_dir/read_file/
    search_standards — nunca write_file/run_command; ele não escreve
    código) e devolve a saída final estruturada (`ArchitecturePlan`).

    Por que não é só `create_agent_with_tools` + `AgentExecutor`: esse loop
    genérico não tem como terminar em saída ESTRUTURADA, só texto livre
    (ver `extract_agent_output_text`) — não dava pra devolver um
    `ArchitecturePlan` validado no fim. Por que não é só
    `create_agent(..., output_schema=...)` (o design original deste
    papel): sem tools, o arquiteto não tinha como conferir fato nenhum de
    um projeto que JÁ EXISTE — só conseguia "chutar" ou admitir que não
    sabia (bug real: pedir um diagnóstico de um projeto existente sempre
    devolvia "não tenho ferramenta de execução/leitura disponível", mesmo
    list_dir/read_file já existindo no projeto pros outros papéis).

    Mesma técnica de `agents/researcher.py::research_batch`: junta as
    tools de exploração com uma tool `submit_architecture_plan` que nunca
    é executada de verdade — os argumentos da chamada viram o
    `ArchitecturePlan` final direto, sem round-trip nenhum. Zero tool call
    de exploração continua sendo um caminho normal (tarefa greenfield, sem
    projeto existente pra conferir) — quem decide quanto explorar antes de
    submeter é o próprio modelo, não um heurística fixa aqui.

    Args:
        task: descrição da tarefa de arquitetura, em linguagem natural.
        tools: tools de exploração somente-leitura (nunca write_file/
            run_command — ver `agents/supervisor.py::ARCHITECT_TOOLS`).
        extra_callbacks: repassado ao loop — mesmo papel de
            `create_agent_with_tools`, usado por `office/server.py` pra
            transmitir cada tool call de exploração em tempo real.
        max_iterations: teto de idas e voltas antes de desistir — proteção
            contra loop de exploração sem fim, não um limite de qualidade.

    Raises:
        RuntimeError: se o arquiteto não chamar `submit_architecture_plan`
            depois de `max_iterations` iterações.
    """
    persona = _build_persona("arquiteto")
    submit_tool = _submit_architecture_plan_tool()
    chat_model = (
        build_chat_model(max_tokens=8192, model=_model_override_for("arquiteto"))
        .bind_tools([*tools, submit_tool])
        .with_config(
            callbacks=[usage_handler, *(extra_callbacks or [])], tags=["role:arquiteto"]
        )
    )

    messages: list[Any] = [_system_message(persona), HumanMessage(content=task)]
    tools_by_name = {tool.name: tool for tool in tools}

    for _ in range(max_iterations):
        response = chat_model.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            messages.append(
                HumanMessage(
                    content=(
                        "Se já explorou o suficiente, chame "
                        "submit_architecture_plan agora. Se ainda precisa "
                        "conferir algo, use as tools de exploração antes de "
                        "decidir."
                    )
                )
            )
            continue

        submit_call = None
        for call in response.tool_calls:
            if call["name"] == "submit_architecture_plan":
                submit_call = call
                continue
            tool = tools_by_name.get(call["name"])
            result_text = (
                f"Tool desconhecida: {call['name']!r}"
                if tool is None
                else str(tool.invoke(call["args"]))
            )
            messages.append(ToolMessage(content=result_text, tool_call_id=call["id"]))

        if submit_call is not None:
            return ArchitecturePlan.model_validate(submit_call["args"])

    raise RuntimeError(
        f"Arquiteto não chamou submit_architecture_plan após {max_iterations} iterações."
    )


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
