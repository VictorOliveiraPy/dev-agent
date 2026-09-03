"""Definição do time: cada "papel" é uma persona (system prompt) que, somada
à fábrica de modelo, forma um agente especializado.

As personas são compostas em duas camadas: a descrição do papel (fixa,
abaixo) + os padrões de código do time, lidos de `padroes/*.md` em runtime
(ver `_montar_persona`). Isso separa "quem esse agente é" (código Python)
de "que convenções ele deve seguir" (arquivos .md editáveis sem tocar em
Python — mesma ideia de um CLAUDE.md).
"""

from pathlib import Path

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from agentes.llm import build_chat_model

# Cada entrada é o "system prompt" que define o papel dentro do time.
PAPEIS: dict[str, str] = {
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
        "Você é o Engenheiro Frontend do time, especialista em React. Foca em "
        "componentes, chamadas à API e experiência do usuário. Responda pela "
        "ótica do frontend, sem se preocupar com o servidor."
    ),
}

# Quais arquivos de padrões (além de geral.md, sempre incluído) cada papel
# recebe na própria persona. Um papel sem entrada aqui só vê geral.md.
_PADROES_DO_PAPEL: dict[str, list[str]] = {
    "dev_backend": ["backend.md"],
    "dev_frontend": ["frontend.md"],
}

_PADROES_DIR = Path(__file__).parent.parent / "padroes"


def _ler_padrao(nome_arquivo: str) -> str:
    """Lê um arquivo de padrões; devolve "" se ele não existir (opcional)."""
    caminho = _PADROES_DIR / nome_arquivo
    return caminho.read_text(encoding="utf-8").strip() if caminho.exists() else ""


def _montar_persona(papel: str) -> str:
    """Junta a descrição do papel aos padrões de código aplicáveis a ele.

    Sempre inclui `padroes/geral.md` (se existir) e, adicionalmente, os
    arquivos listados em `_PADROES_DO_PAPEL[papel]`. O resultado é o system
    prompt final enviado ao modelo — os .md viram parte do prompt, não são
    lidos via tool (ver Aula/Passo sobre RAG para o padrão alternativo, de
    leitura sob demanda).
    """
    partes = [PAPEIS[papel]]

    geral = _ler_padrao("geral.md")
    if geral:
        partes.append(f"## Padrões gerais do time (sempre siga):\n{geral}")

    for nome_arquivo in _PADROES_DO_PAPEL.get(papel, []):
        conteudo = _ler_padrao(nome_arquivo)
        if conteudo:
            partes.append(f"## Padrões específicos ({nome_arquivo}):\n{conteudo}")

    return "\n\n".join(partes)


def criar_agente(papel: str) -> Runnable:
    """Monta a chain LCEL (prompt | model | parser) de um papel do time.

    Args:
        papel: uma chave de PAPEIS (ex: "arquiteto").

    Returns:
        Um Runnable que recebe {"pedido": str} e devolve a resposta em
        texto, já sob a perspectiva daquele papel.

    Raises:
        KeyError: se `papel` não existir em PAPEIS.
    """
    persona = _montar_persona(papel)
    prompt = ChatPromptTemplate.from_messages([
        ("system", persona),
        ("human", "{pedido}"),
    ])
    return prompt | build_chat_model() | StrOutputParser()


def criar_agente_com_ferramentas(papel: str, tools: list[BaseTool]) -> AgentExecutor:
    """Monta um AgentExecutor: a persona do papel + um loop de tool calling.

    Diferente de `criar_agente` (chain fixa prompt -> model -> parser), aqui
    o modelo decide sozinho QUANDO e QUANTAS vezes chamar cada tool, dentro
    de um loop controlado pelo AgentExecutor — é o que permite ao papel agir
    de verdade (escrever arquivos, rodar comandos) em vez de só opinar.

    Args:
        papel: uma chave de PAPEIS.
        tools: lista de tools (ex: write_file, read_file) que esse papel
            pode chamar.

    Returns:
        Um AgentExecutor pronto para `.invoke({"pedido": ...})`.
    """
    persona = _montar_persona(papel)
    prompt = ChatPromptTemplate.from_messages([
        ("system", persona),
        ("human", "{pedido}"),
        # agent_scratchpad: onde o AgentExecutor injeta o histórico de
        # tool_use/tool_result de cada iteração do loop, dentro desta
        # mesma tarefa.
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    model = build_chat_model()
    agent = create_tool_calling_agent(model, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=15)
