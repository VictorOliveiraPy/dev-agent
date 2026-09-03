"""Rastreamento de uso de tokens por chamada ao modelo, persistido em
`usage_log.jsonl` na raiz do projeto — é o que alimenta o dashboard
(`dashboard.py`).

`get_openai_callback` (langchain_community) não serve aqui: nem está
instalado no projeto (`langchain_community` não é uma dependência nossa),
e mesmo se estivesse só entende o formato de resposta da OpenAI. Usamos o
`usage_metadata` nativo que o `langchain_anthropic` já popula em toda
resposta (`input_tokens`/`output_tokens`/`total_tokens`), via um callback
handler próprio.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

USAGE_LOG_PATH = Path(__file__).parent.parent / "usage_log.jsonl"

_ROLE_TAG_PREFIX = "role:"


def _extract_role(tags: list[str] | None) -> str:
    """Extrai o papel de uma lista de tags, ex: 'role:dev_backend' -> 'dev_backend'.

    Devolve "desconhecido" se nenhuma tag de papel estiver presente — não
    derruba o rastreamento por causa de uma chamada sem tag.
    """
    for tag in tags or []:
        if tag.startswith(_ROLE_TAG_PREFIX):
            return tag[len(_ROLE_TAG_PREFIX):]
    return "desconhecido"


class UsageCallbackHandler(BaseCallbackHandler):
    """Grava, em um arquivo JSONL, os tokens gastos em cada chamada ao modelo.

    O papel (role) responsável pela chamada é lido das tags associadas ao
    Runnable — ver `agentes/team.py`, que já anexa `tags=["role:<role>"]`
    em `create_agent`/`create_agent_with_tools`. Uma instância desta classe
    é compartilhada por todo o time (`usage_handler`, no fim deste
    arquivo), então todas as chamadas caem no mesmo arquivo de log.
    """

    def __init__(self, log_path: Path = USAGE_LOG_PATH) -> None:
        self.log_path = log_path
        # Cada chamada tem um run_id próprio; guardamos as tags vistas no
        # início da chamada (on_chat_model_start) pra recuperar no fim
        # (on_llm_end), já que nem toda versão do LangChain repassa tags
        # para on_llm_end.
        self._pending_tags: dict[UUID, list[str]] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Guarda as tags da chamada que está começando, indexadas por run_id."""
        self._pending_tags[run_id] = tags or []

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        """Lê o usage_metadata da resposta e grava uma linha no log."""
        role = _extract_role(self._pending_tags.pop(run_id, []))

        for generation_list in response.generations:
            for generation in generation_list:
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None) if message else None
                if not usage:
                    continue
                model = getattr(message, "response_metadata", {}).get("model", "")
                self._record(role=role, usage=usage, model=model)

    def _record(self, *, role: str, usage: dict[str, Any], model: str) -> None:
        """Serializa uma entrada de uso e anexa ao arquivo de log."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "role": role,
            "model": model,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        logger.info("Chamada ao modelo concluída", extra=entry)

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Instância única compartilhada por todos os agentes do time — ver
# agentes/team.py, onde é anexada a cada Runnable/AgentExecutor criado.
usage_handler = UsageCallbackHandler()
