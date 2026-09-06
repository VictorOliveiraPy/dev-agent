"""Fábrica de modelo compartilhada por todos os agentes do time.

Centraliza a criação do `ChatAnthropic` (carregamento do .env, header de
workspace, max_tokens) para que cada papel do time não duplique essa
configuração — e para que um ajuste futuro (trocar de modelo, mudar o
max_tokens padrão) aconteça em um lugar só.

Nota histórica: este arquivo já teve suporte a rodar em cima de um Ollama
local e de um OpenRouter opcional (dois provedores extras, selecionáveis
por `LLM_PROVIDER`). Removido de propósito depois de testar de verdade —
ver ARCHITECTURE.md, seção "Propostas descartadas", pro motivo.
"""

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

_DEFAULT_MODEL = "claude-opus-5"


def build_chat_model(max_tokens: int = 8192, model: str | None = None) -> ChatAnthropic:
    """Cria uma instância configurada do modelo Claude.

    Args:
        max_tokens: teto de tokens de saída. Evite valores baixos: com
            "thinking" + tool calls na mesma resposta, um teto pequeno corta
            a saída no meio do JSON de uma tool call (bug real que já
            apareceu no projeto de estudo).
        model: ID do modelo Claude a usar. Se omitido, usa `_DEFAULT_MODEL`
            (Opus 5) — ver `agents/team.py::_ROLE_MODELS` para os papéis que
            usam um modelo diferente do padrão.

    Returns:
        Uma instância de ChatAnthropic pronta para uso em uma chain ou agent.
    """
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    extra_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    return ChatAnthropic(
        model=model or _DEFAULT_MODEL,
        max_tokens=max_tokens,
        default_headers=extra_headers,
    )
