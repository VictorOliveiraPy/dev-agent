"""Roda o pesquisador para completar a categoria "concílios" — lote de teste.

Concílios foi escolhido como primeiro lote de verdade (ver PROGRESS.md)
porque é uma categoria FECHADA: existem exatamente 21 concílios ecumênicos
reconhecidos pela Igreja Católica, contra as centenas/milhares de santos ou
os 266 papas — dá pra chegar a 100% dela num lote só, e serve pra medir o
custo real por entrada antes de decidir se vale escalar para categorias
maiores (papas, santos).

A lista dos 21 concílios (com as datas) é dada ao pesquisador de propósito
— não se pede a ele para "descobrir quantos faltam", isso é fato estável
e verificável que eu já sei; deixar o próprio agente contar removeria uma
fonte de erro bobo (contagem errada) sem ganhar nada em troca.

Uso:
    python research_concilios.py           # roda de verdade (gasta API)
    python research_concilios.py --dry-run # só mostra o prompt, não chama a API
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# app.models é a fonte única de verdade do schema — importado do repositório
# irmão em vez de duplicado aqui, para nunca validar contra um contrato
# diferente do que o backend realmente aceita.
BACKEND_PATH = Path.home() / "Documentos" / "code" / "acervo-catolico-api"
sys.path.insert(0, str(BACKEND_PATH))

from app.models import Concilio  # noqa: E402

from agents.researcher import research_batch, validate_batch  # noqa: E402

DATA_FILE = BACKEND_PATH / "app" / "data" / "concilios.json"

# Os 21 concílios ecumênicos reconhecidos pela Igreja Católica, na ordem
# cronológica oficial — (posição, nome, ano, slug esperado no acervo).
# numero_ordem do modelo é essa mesma posição, 1-21.
_ALL_COUNCILS = [
    (1, "Niceia I", "325", "niceia-i"),
    (2, "Constantinopla I", "381", "constantinopla-i"),
    (3, "Éfeso", "431", "efeso"),
    (4, "Calcedônia", "451", "calcedonia"),
    (5, "Constantinopla II", "553", "constantinopla-ii"),
    (6, "Constantinopla III", "680-681", "constantinopla-iii"),
    (7, "Niceia II", "787", "niceia-ii"),
    (8, "Constantinopla IV", "869-870", "constantinopla-iv"),
    (9, "Latrão I", "1123", "latrao-i"),
    (10, "Latrão II", "1139", "latrao-ii"),
    (11, "Latrão III", "1179", "latrao-iii"),
    (12, "Latrão IV", "1215", "latrao-iv"),
    (13, "Lyon I", "1245", "lyon-i"),
    (14, "Lyon II", "1274", "lyon-ii"),
    (15, "Vienne", "1311-1312", "vienne"),
    (16, "Constança", "1414-1418", "constanca"),
    (17, "Basileia-Ferrara-Florença", "1431-1445", "basileia-ferrara-florenca"),
    (18, "Latrão V", "1512-1517", "latrao-v"),
    (19, "Trento", "1545-1563", "trento"),
    (20, "Vaticano I", "1869-1870", "vaticano-i"),
    (21, "Vaticano II", "1962-1965", "vaticano-ii"),
]


def _load_existing_slugs() -> set[str]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {item["slug"] for item in data["itens"]}


def _build_task(missing: list[tuple[int, str, str, str]], existing_slugs: set[str]) -> str:
    lista = "\n".join(f"- {ordem}º: {nome} ({ano})" for ordem, nome, ano, _slug in missing)
    return (
        "Complete a categoria 'concílios' do Acervo Católico. Estes são os "
        f"{len(missing)} concílios ecumênicos que FALTAM (a numeração é a "
        "posição oficial entre os 21 concílios ecumênicos reconhecidos "
        f"pela Igreja Católica):\n{lista}\n\n"
        f"Slugs já usados no acervo (não repita): {sorted(existing_slugs)}.\n\n"
        "Para cada concílio: pesquise o que ele definiu ou decidiu (o "
        "assunto central, não uma lista exaustiva de cânones), o número de "
        "participantes se for um dado conhecido e citado, e uma imagem "
        "real (pintura, afresco ou ícone histórico) que o represente na "
        "Wikimedia Commons, verificada por você numa busca de verdade. "
        "'numero_ordem' é a posição entre os 21 (já informada acima). "
        "'corpo' deve ter 2-3 parágrafos, no mesmo estilo dos concílios já "
        "existentes no acervo (tom enciclopédico, sóbrio, sem hipérbole)."
    )


# Tamanho do sub-lote por chamada. Bug real visto na primeira tentativa
# (ver ARCHITECTURE.md): pedir os 18 de uma vez gerou ~200k tokens de
# entrada (busca acumulada) e cortou a saída no meio do JSON por
# max_tokens. Sub-lotes pequenos custam mais chamadas, mas cada uma fica
# bem dentro do teto e uma falha isolada não derruba o lote inteiro.
_CHUNK_SIZE = 4


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _write_entries(entries: list) -> None:
    """Grava (append) entradas validadas no arquivo de dados, na hora —
    não espera o fim de todos os sub-lotes, pra não perder progresso já
    pago se um sub-lote posterior falhar."""
    if not entries:
        return
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data["itens"].extend(entry.model_dump(mode="json") for entry in entries)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    existing_slugs = _load_existing_slugs()
    missing = [council for council in _ALL_COUNCILS if council[3] not in existing_slugs]
    batches = _chunks(missing, _CHUNK_SIZE)

    if dry_run:
        for i, batch in enumerate(batches, start=1):
            print(f"=== sub-lote {i}/{len(batches)} ({len(batch)} itens) ===")
            print(_build_task(batch, existing_slugs))
            print()
        return

    total_written = 0
    for i, batch in enumerate(batches, start=1):
        print(f"\n=== Sub-lote {i}/{len(batches)}: {[c[1] for c in batch]} ===")
        task = _build_task(batch, existing_slugs)
        try:
            raw_items = research_batch(task, Concilio, max_attempts=3)
        except RuntimeError as exc:
            print(f"  ✗ Sub-lote falhou, pulando para o próximo: {exc}")
            continue

        valid, warnings = validate_batch(raw_items, Concilio, existing_slugs)
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print(f"  {len(valid)}/{len(raw_items)} itens passaram na validação.")

        _write_entries(valid)
        total_written += len(valid)

    print(f"\nTotal gravado em {DATA_FILE}: {total_written} entradas. Revise o diff antes de commitar.")


if __name__ == "__main__":
    main()
