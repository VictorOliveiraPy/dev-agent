"""Rastreamento de qualidade/acertividade dos lotes propostos por um
agente, persistido em `quality_log.jsonl` na raiz do projeto — mesmo
padrão de `agents/usage.py`, mas em vez de tokens gastos, mede quanto do
que o agente propôs sobreviveu à autovalidação real (ver
`agents/researcher.py::validate_batch`).

Diferente de `usage.py`, isto não é um `BaseCallbackHandler`: não há
"chamada ao modelo" 1:1 com "lote validado" (um lote pode vir de várias
chamadas ao modelo, via os retries de `research_batch`). Por isso
`record_quality` é uma função simples, chamada uma vez por lote ao fim de
`validate_batch` — não um callback do LangChain.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from agents.schemas import QualityEntry

logger = logging.getLogger(__name__)

QUALITY_LOG_PATH = Path(__file__).parent.parent / "quality_log.jsonl"


def record_quality(
    *,
    role: str,
    model: str,
    items_proposed: int,
    items_valid: int,
    discarded_duplicate_slug: int = 0,
    discarded_validation_error: int = 0,
    images_discarded: int = 0,
    log_path: Path = QUALITY_LOG_PATH,
) -> None:
    """Valida uma entrada de qualidade contra `QualityEntry` e anexa ao log.

    Validar aqui (não só na leitura, no dashboard) garante que uma linha
    malformada nunca chega a ser escrita — mesmo raciocínio de
    `usage.py::_record`.
    """
    entry = QualityEntry(
        timestamp=datetime.now(UTC),
        role=role,
        model=model,
        items_proposed=items_proposed,
        items_valid=items_valid,
        discarded_duplicate_slug=discarded_duplicate_slug,
        discarded_validation_error=discarded_validation_error,
        images_discarded=images_discarded,
    )
    logger.info("Lote validado", extra=entry.model_dump(mode="json"))

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
