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
    python projects/enrich_category.py --all                  # todas, retomável

Com `--all` o progresso fica em `projects/.enrich_done.json` (uma chave
"categoria:slug" por entrada já aprofundada, então rodar de novo pula o que
já foi feito) e cada categoria concluída vira um commit no repositório da API.
"""

from __future__ import annotations

import argparse
import json
import subprocess
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
    SearchUnavailableError,
    merge_enrichment,
    research_batch,
)

DATA_DIR = BACKEND_PATH / "app" / "data"
_CHUNK_SIZE = 3
DONE_FILE = Path(__file__).with_name(".enrich_done.json")


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


def _load_done() -> set[str]:
    if DONE_FILE.exists():
        return set(json.loads(DONE_FILE.read_text(encoding="utf-8")))
    return set()


def _save_done(done: set[str]) -> None:
    DONE_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=1), encoding="utf-8")


def enrich_category(
    name: str,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    shortest_first: bool = False,
    done: set[str] | None = None,
) -> int:
    """Aprofunda uma categoria; devolve quantas entradas foram atualizadas.

    `done` (chaves "categoria:slug") é mutado com o que foi aprofundado e
    persistido a cada sub-lote. Entradas já em `done` são puladas.
    """
    done = done if done is not None else set()
    data_file = DATA_DIR / f"{name}.json"
    data = json.loads(data_file.read_text(encoding="utf-8"))
    if "_meta" not in data or not data.get("itens"):
        print(f"{name}: sem _meta/itens, pulando.")
        return 0
    item_model = _model_for(data["_meta"]["categoria"])

    items = data["itens"]
    pending = [i for i in items if f"{name}:{i['slug']}" not in done]
    order = sorted(pending, key=lambda i: len(i["corpo"])) if shortest_first else pending
    targets = order[:limit] if limit else order
    batches = [targets[i : i + _CHUNK_SIZE] for i in range(0, len(targets), _CHUNK_SIZE)]

    if dry_run:
        for n, batch in enumerate(batches, start=1):
            print(f"=== {name} — sub-lote {n}/{len(batches)} ({len(batch)} itens) ===")
            print(_build_task(batch), "\n")
        return 0

    persona = _PERSONA + _ENRICH_NOTE
    by_slug = {item["slug"]: item for item in items}
    updated = 0
    for n, batch in enumerate(batches, start=1):
        print(f"\n=== {name} — sub-lote {n}/{len(batches)}: {[i['slug'] for i in batch]} ===", flush=True)
        try:
            raw = research_batch(_build_task(batch), item_model, persona=persona)
        except SearchUnavailableError:
            raise  # sem busca todo lote seguinte falharia igual: para a rodada
        except Exception as exc:  # um sub-lote ruim não derruba as 50 categorias
            print(f"  ✗ sub-lote falhou, pulando: {exc}", flush=True)
            continue

        merged, warnings = merge_enrichment(
            raw, item_model, {i["slug"]: i for i in batch}, model=current_provider()
        )
        for warning in warnings:
            print(f"  ⚠ {warning}")
        applied = 0
        for entry in merged:
            dumped = entry.model_dump(mode="json")
            current = by_slug[dumped["slug"]]
            # Corpo igual ao atual = o modelo devolveu o texto sem aprofundar
            # (visto quando a busca estava fora do ar): não conta como feito,
            # fica pendente para uma próxima rodada.
            if dumped["corpo"] == current["corpo"]:
                print(f"  ⚠ '{dumped['slug']}': corpo não mudou, segue pendente", flush=True)
                continue
            current.clear()
            current.update(dumped)
            done.add(f"{name}:{dumped['slug']}")
            applied += 1
        updated += applied
        print(f"  {applied}/{len(raw)} aprofundadas.", flush=True)

        # grava a cada sub-lote: não perde progresso já pago se um posterior falhar
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _save_done(done)

    print(f"{name}: {updated} entradas atualizadas.", flush=True)
    return updated


# Manifesto de datas de atualização da API (lastmod do sitemap do site). Ver o README da API.
MANIFEST_REL = "app/data/atualizacoes.json"


def _refresh_update_dates(name: str) -> None:
    """Regenera as datas de atualização da categoria antes do commit.

    Sem isto o `lastmod` do sitemap fica velho: a data vem do histórico do git e do que está
    editado agora (que ganha a data de hoje). API sem o script (versão antiga): não faz nada.
    """
    script = BACKEND_PATH / "scripts" / "gerar_atualizacoes.py"
    if not script.exists():
        return
    result = subprocess.run(
        [sys.executable, str(script), "--categoria", name],
        cwd=BACKEND_PATH,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ⚠ não atualizei atualizacoes.json: {result.stderr.strip()}", flush=True)


def _commit_category(name: str, updated: int) -> None:
    """Checkpoint no repositório da API: o JSON da categoria e o manifesto de datas, nada mais."""
    rel = f"app/data/{name}.json"
    git = ["git", "-C", str(BACKEND_PATH)]
    status = subprocess.run(
        [*git, "status", "--porcelain", "--", rel], capture_output=True, text=True
    )
    if not status.stdout.strip():
        return
    _refresh_update_dates(name)
    paths = [rel] + ([MANIFEST_REL] if (BACKEND_PATH / MANIFEST_REL).exists() else [])
    subprocess.run([*git, "add", "--", *paths], check=True)
    message = (
        f"Aprofunda {updated} entradas de {name} com pesquisa web\n\n"
        "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
    )
    subprocess.run([*git, "commit", "-q", "-m", message, "--", *paths], check=True)
    _push_main(git)


def _push_main(git: list[str]) -> None:
    """Envia os commits pendentes para a `main` remota (pedido explícito: um
    push por categoria concluída). Falha de push não derruba a rodada — o
    commit local fica e o próximo push leva tudo junto."""
    result = subprocess.run([*git, "push", "origin", "main"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠ push falhou (commits ficam locais): {result.stderr.strip()}", flush=True)
    else:
        print("  ↑ push para origin/main ok", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("categoria", nargs="?", help="nome do arquivo em app/data, sem .json")
    parser.add_argument("--all", action="store_true", help="todas as categorias, retomável")
    parser.add_argument("--dry-run", action="store_true", help="só mostra as tarefas")
    parser.add_argument("--limit", type=int, help="máximo de entradas por categoria")
    parser.add_argument("--shortest-first", action="store_true", help="começa pelos corpos mais curtos")
    args = parser.parse_args()
    if not args.categoria and not args.all:
        parser.error("informe uma categoria ou --all")

    done = _load_done()
    if args.all:
        names = sorted(f.stem for f in DATA_DIR.glob("*.json") if f.stem != "image-manifest")
    else:
        names = [args.categoria]

    total = 0
    for name in names:
        updated = enrich_category(
            name,
            dry_run=args.dry_run,
            limit=args.limit,
            shortest_first=args.shortest_first,
            done=done,
        )
        total += updated
        if args.all and updated:
            _commit_category(name, updated)

    print(f"\nTotal: {total} entradas atualizadas. Revise o diff antes de publicar.")


if __name__ == "__main__":
    main()
