"""Aprofunda as entradas JÁ EXISTENTES de uma categoria do acervo.

Diferente de `research_concilios.py` (que cria entradas novas), aqui o
pesquisador recebe o texto atual de cada entrada e devolve uma versão mais
profunda de corpo/resumo/fontes/tags/imagem, apoiada em busca real. A
validação (`merge_enrichment`) só deixa passar campo permitido, corpo que
não encolheu e imagem que resolve de verdade; o que falha mantém o original.

Uso:
    python projects/enrich_category.py sacramentos --dry-run
    python projects/enrich_category.py sacramentos            # gasta API
    python projects/enrich_category.py santos --limit 6 --shortest-first
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[2] / "Acervo-Cat-lico-API"
sys.path.insert(0, str(BACKEND_PATH))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402

from agents.llm import current_provider  # noqa: E402
from agents.researcher import (  # noqa: E402
    _ENRICH_NOTE,
    _PERSONA,
    merge_enrichment,
    research_batch,
)

DATA_DIR = BACKEND_PATH / "app" / "data"
_CHUNK_SIZE = 3


def _model_for(category: str) -> type[models.ContentEntry]:
    """Acha a subclasse de `ContentEntry` cuja `categoria` default é esta."""
    for cls in vars(models).values():
        if isinstance(cls, type) and issubclass(cls, models.ContentEntry) and cls is not models.ContentEntry:
            default = cls.model_fields["categoria"].default
            if getattr(default, "value", None) == category:
                return cls
    raise SystemExit(f"nenhum modelo Pydantic para a categoria {category!r}")


def _build_task(batch: list[dict]) -> str:
    entries = json.dumps(batch, ensure_ascii=False, indent=2)
    return (
        "Aprofunde estas entradas existentes do Acervo Católico. Para cada "
        "uma, pesquise fontes confiáveis e devolva a entrada completa com "
        "'corpo' mais rico (3-5 parágrafos, tom enciclopédico e sóbrio, "
        "sem hipérbole), 'resumo' afinado se preciso, 'fontes' com "
        "referências reais e específicas, e 'tags' no formato natural do "
        "acervo. Procure o que o texto atual não diz: contexto histórico, "
        "personagens, números, controvérsias, fonte primária. Se a "
        "entrada não tiver imagem, procure uma real na Wikimedia Commons.\n\n"
        f"Entradas atuais:\n{entries}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("categoria", help="nome do arquivo em app/data, sem .json")
    parser.add_argument("--dry-run", action="store_true", help="só mostra as tarefas")
    parser.add_argument("--limit", type=int, help="máximo de entradas a processar")
    parser.add_argument("--shortest-first", action="store_true", help="começa pelos corpos mais curtos")
    args = parser.parse_args()

    data_file = DATA_DIR / f"{args.categoria}.json"
    data = json.loads(data_file.read_text(encoding="utf-8"))
    item_model = _model_for(data["_meta"]["categoria"])

    items = data["itens"]
    order = sorted(items, key=lambda i: len(i["corpo"])) if args.shortest_first else list(items)
    targets = order[: args.limit] if args.limit else order
    batches = [targets[i : i + _CHUNK_SIZE] for i in range(0, len(targets), _CHUNK_SIZE)]

    if args.dry_run:
        for n, batch in enumerate(batches, start=1):
            print(f"=== sub-lote {n}/{len(batches)} ({len(batch)} itens) ===")
            print(_build_task(batch), "\n")
        return

    persona = _PERSONA + _ENRICH_NOTE
    by_slug = {item["slug"]: item for item in items}
    updated = 0
    for n, batch in enumerate(batches, start=1):
        print(f"\n=== Sub-lote {n}/{len(batches)}: {[i['slug'] for i in batch]} ===")
        try:
            raw = research_batch(_build_task(batch), item_model, persona=persona)
        except RuntimeError as exc:
            print(f"  ✗ sub-lote falhou, pulando: {exc}")
            continue

        merged, warnings = merge_enrichment(
            raw, item_model, {i["slug"]: i for i in batch}, model=current_provider()
        )
        for warning in warnings:
            print(f"  ⚠ {warning}")
        for entry in merged:
            dumped = entry.model_dump(mode="json")
            by_slug[dumped["slug"]].clear()
            by_slug[dumped["slug"]].update(dumped)
        updated += len(merged)
        print(f"  {len(merged)}/{len(raw)} aprofundadas.")

        # grava a cada sub-lote: não perde progresso já pago se um posterior falhar
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n{updated} entradas atualizadas em {data_file}. Revise o diff antes de commitar.")


if __name__ == "__main__":
    main()
