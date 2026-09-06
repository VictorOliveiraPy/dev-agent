"""Fábrica de modelo compartilhada por todos os agentes do time.

Centraliza a criação do chat model (carregamento do .env, header de
workspace, max_tokens) para que cada papel do time não duplique essa
configuração — e para que um ajuste futuro (trocar de modelo, mudar o
max_tokens padrão) aconteça em um lugar só.

Três provedores são suportados:

- **anthropic** (padrão): `ChatAnthropic`, via `ANTHROPIC_API_KEY`. Chamada
  direta à API da Anthropic — é o que o time usa em produção.
- **ollama**: `ChatOllama`, apontando para um servidor Ollama local (rodando
  na máquina ou via `docker compose up ollama` — ver `docker-compose.yml`).
  Sem custo por token, mas com qualidade de raciocínio bem menor — serve
  para papéis baratos/repetitivos (rascunho, auditoria só-leitura), não para
  os que precisam de tool calling confiável (`dev_backend`, `dev_frontend`).
  Testado com `llama3.1:8b` e `qwen2.5-coder:7b`: nenhum dos dois é
  confiável o bastante para escrever arquivo de verdade — o segundo, apesar
  do nome, sequer usou o canal de tool calling estruturado numa chamada
  simples (devolveu o JSON como texto solto). Ver ARCHITECTURE.md.
- **openrouter**: `ChatOpenAI` (biblioteca `langchain-openai`) apontando pro
  endpoint OpenAI-compatible do OpenRouter (https://openrouter.ai/api/v1).
  Uma chave só, troca de modelo (inclusive de outros provedores, ou opções
  gratuitas) mudando uma string. Uso opcional, papel a papel — não é o
  provedor padrão do time.

O provedor é escolhido por `LLM_PROVIDER` no `.env` (`anthropic`, `ollama`
ou `openrouter`), com override explícito via o parâmetro `provider` — útil
para um papel que *precisa* ficar preso a um provedor específico
independente da config global (ver `agents/researcher.py`, que depende de
uma tool server-side exclusiva da Anthropic e por isso nunca passa por
Ollama nem OpenRouter).
"""

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

load_dotenv()

_DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
_DEFAULT_OLLAMA_MODEL = "llama3.1"
_DEFAULT_OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def build_chat_model(
    max_tokens: int = 8192,
    model: str | None = None,
    provider: str | None = None,
) -> BaseChatModel:
    """Cria uma instância configurada do chat model (Anthropic, Ollama ou
    OpenRouter).

    Args:
        max_tokens: teto de tokens de saída. Evite valores baixos: com
            "thinking" + tool calls na mesma resposta, um teto pequeno corta
            a saída no meio do JSON de uma tool call (bug real que já
            apareceu no projeto de estudo).
        model: ID do modelo a usar. Se omitido, usa o padrão do provedor
            resolvido (`_DEFAULT_ANTHROPIC_MODEL`, `_DEFAULT_OLLAMA_MODEL` ou
            `_DEFAULT_OPENROUTER_MODEL`).
        provider: "anthropic", "ollama" ou "openrouter". Se omitido, lê
            `LLM_PROVIDER` do ambiente (padrão "anthropic") — permite trocar
            o time inteiro de provedor sem mudar código, e um chamador
            específico ainda pode forçar um provedor via este parâmetro.

    Returns:
        Uma instância de chat model pronta para uso em uma chain ou agent.

    Raises:
        ValueError: se `provider` (explícito ou via `LLM_PROVIDER`) não for
            "anthropic", "ollama" nem "openrouter".
    """
    resolved_provider = (provider or os.getenv("LLM_PROVIDER", "anthropic")).lower()

    if resolved_provider == "ollama":
        return ChatOllama(
            model=model or os.getenv("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            num_predict=max_tokens,
        )

    if resolved_provider == "openrouter":
        return ChatOpenAI(
            model=model or os.getenv("OPENROUTER_MODEL", _DEFAULT_OPENROUTER_MODEL),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", _OPENROUTER_BASE_URL),
            max_completion_tokens=max_tokens,
            # Opcionais, recomendados pela OpenRouter para identificar a
            # origem do tráfego nos rankings deles — não afeta o resultado.
            default_headers={
                "HTTP-Referer": "https://github.com/VictorOliveiraPy/dev-agent",
                "X-Title": "dev-agent",
            },
        )

    if resolved_provider != "anthropic":
        raise ValueError(
            f"Provedor de LLM desconhecido: {resolved_provider!r}. "
            "Use 'anthropic', 'ollama' ou 'openrouter' (LLM_PROVIDER no "
            ".env, ou o parâmetro provider)."
        )

    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    extra_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    return ChatAnthropic(
        model=model or _DEFAULT_ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        default_headers=extra_headers,
    )
