"""Fábrica de modelo compartilhada pela maior parte dos agentes do time.

Centraliza a criação do chat model (carregamento do .env, seleção de
provedor, max_tokens) para que cada papel do time não duplique essa
configuração — e para que um ajuste futuro (trocar de modelo, mudar o
max_tokens padrão) aconteça em um lugar só.

Nota histórica: este arquivo já teve suporte a Ollama local e a um
OpenRouter opcional, removido de propósito depois de testar de verdade —
ver ARCHITECTURE.md, seção "Propostas descartadas". O motivo do descarte
foi tool calling não confiável em modelos pequenos (JSON de tool call
devolvido como texto solto). O suporte a DeepSeek abaixo NÃO é a mesma
ideia ressuscitada sem critério: foi validado de verdade antes de entrar
— loop completo do `AgentExecutor` (múltiplas tool calls reais, incluindo
escrita de arquivo) e `.with_structured_output()` (ArchitecturePlan,
DesignPlan) ambos testados contra a API real do DeepSeek e funcionaram
(ver PROGRESS.md pra data e detalhe do teste). A ressalva que continua
valendo: `agents/researcher.py` NUNCA usa o provedor ativo daqui — ele
sempre força `provider="anthropic"` explicitamente, porque depende da
tool `web_search` nativa da Anthropic, sem equivalente no DeepSeek.
"""

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek

load_dotenv()

_DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "deepseek": "deepseek-chat",
}


def current_provider() -> str:
    """Provedor ativo, lido de `LLM_PROVIDER` — "anthropic" se a variável
    não estiver definida (comportamento de sempre, sem mudar nada pra
    quem não configurou nada)."""
    return os.getenv("LLM_PROVIDER", "anthropic")


def build_chat_model(
    max_tokens: int = 8192,
    model: str | None = None,
    *,
    provider: str | None = None,
) -> ChatAnthropic | ChatDeepSeek:
    """Cria uma instância configurada do chat model do provedor ativo.

    Args:
        max_tokens: teto de tokens de saída. Evite valores baixos: com
            "thinking" + tool calls na mesma resposta, um teto pequeno corta
            a saída no meio do JSON de uma tool call (bug real que já
            apareceu no projeto de estudo).
        model: ID do modelo a usar. Se omitido, usa o default do provedor
            ativo (`_DEFAULT_MODELS`) — ver `agents/team.py::_ROLE_MODELS`
            para os papéis que usam um modelo diferente do padrão (só se
            aplica sob o provedor "anthropic": os IDs ali são específicos
            da Anthropic, e são ignorados sob "deepseek").
        provider: força um provedor específico ("anthropic" ou
            "deepseek"), ignorando `LLM_PROVIDER`. Uso normal é deixar
            `None` (segue a configuração global) — só passe isto quando um
            papel depende estruturalmente de um provedor específico, como
            `agents/researcher.py` (tool `web_search` nativa, exclusiva da
            Anthropic).

    Returns:
        Uma instância de `ChatAnthropic` ou `ChatDeepSeek`, pronta para uso
        em uma chain ou agent — as duas implementam a mesma interface
        `BaseChatModel` do LangChain, então quem chama não precisa saber
        qual das duas recebeu.

    Raises:
        ValueError: se o provedor resolvido não for "anthropic" nem "deepseek".
    """
    provider = provider or current_provider()

    if provider == "deepseek":
        return ChatDeepSeek(
            model=model or _DEFAULT_MODELS["deepseek"],
            api_key=os.environ["DEEPSEEK_API_KEY"],
            max_tokens=max_tokens,
        )

    if provider != "anthropic":
        raise ValueError(
            f"LLM_PROVIDER desconhecido: {provider!r} — use 'anthropic' ou 'deepseek'."
        )

    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    extra_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    return ChatAnthropic(
        model=model or _DEFAULT_MODELS["anthropic"],
        max_tokens=max_tokens,
        default_headers=extra_headers,
    )
