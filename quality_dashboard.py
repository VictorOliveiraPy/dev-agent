"""Dashboard Streamlit: acompanha a ACERTIVIDADE de cada agente do time —
quanto do que ele propôs sobreviveu à autovalidação real —, lendo
`quality_log.jsonl` (gerado por `agents/quality.py`, chamado ao fim de
`agents/researcher.py::validate_batch`).

Rodar: .venv/bin/streamlit run quality_dashboard.py

Complementa `dashboard.py` (que mede CUSTO — tokens) sem duplicá-lo: os
dois lêem logs JSONL separados porque medem coisas diferentes (uma chamada
ao modelo vs. um lote validado) e nem toda chamada vira um lote.

Mesma separação de `dashboard.py`/`web_ui.py`: as funções puras (`load_quality`,
`accuracy_tier`, `summarize_by_model`) ficam fora de `_render()` — testáveis
sem o runtime do Streamlit (ver tests/test_quality_dashboard.py). Todo o
resto (gráficos Altair, métricas) só roda via `streamlit run`.
"""

import logging
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from agents.schemas import QualityEntry

logger = logging.getLogger(__name__)

QUALITY_LOG_PATH = Path(__file__).parent / "quality_log.jsonl"

QUALITY_COLUMNS = [
    "timestamp", "role", "model", "items_proposed", "items_valid",
    "discarded_duplicate_slug", "discarded_validation_error", "images_discarded",
]

# Paleta validada (ver skill dataviz, references/palette.md) — status
# palette fixa, nunca reusada como cor de série comum.
_COLOR_GOOD = "#0ca30c"
_COLOR_WARNING = "#fab219"
_COLOR_CRITICAL = "#d03b3b"
_COLOR_SEQUENTIAL = "#2a78d6"

# Faixas de acertividade -> emoji, pra dar leitura instantânea sem ler
# número nenhum. Ordem importa: primeira faixa cujo threshold é atingido
# vence (ver accuracy_tier).
_TIERS: list[tuple[float, str, str]] = [
    (0.9, "🏆", "excelente"),
    (0.7, "👍", "aceitável"),
    (0.0, "😬", "precisa atenção"),
]

# Rótulos em português das colunas exibidas — compartilhado pelas duas
# tabelas (by_model e lotes recentes) pra não duplicar o dict duas vezes.
_COLUMN_LABELS = {
    "emoji": "", "role": "papel", "model": "modelo", "timestamp": "quando",
    "items_proposed": "propostos", "items_valid": "válidos",
    "accuracy_rate": "acertividade",
}


def load_quality(log_path: Path = QUALITY_LOG_PATH) -> pd.DataFrame:
    """Lê `quality_log.jsonl` inteiro e devolve como DataFrame, com uma
    coluna `accuracy_rate` calculada (items_valid / items_proposed).

    Mesmo tratamento de `dashboard.load_usage`: linha inválida é ignorada
    com aviso, não derruba o dashboard; arquivo ausente vira DataFrame
    vazio com as colunas certas (acontece antes do primeiro lote validado).
    """
    if not log_path.exists():
        return pd.DataFrame(columns=[*QUALITY_COLUMNS, "accuracy_rate"])

    entries: list[QualityEntry] = []
    for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(QualityEntry.model_validate_json(line))
        except ValidationError as exc:
            logger.warning(
                "Linha inválida em quality_log.jsonl, ignorada",
                extra={"line_number": line_number, "error": str(exc)},
            )

    if not entries:
        return pd.DataFrame(columns=[*QUALITY_COLUMNS, "accuracy_rate"])

    df = pd.DataFrame([entry.model_dump() for entry in entries])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["accuracy_rate"] = [entry.accuracy_rate for entry in entries]
    return df


def accuracy_tier(rate: float) -> tuple[str, str]:
    """Emoji + rótulo pro nível de acertividade — leitura instantânea sem
    número. `rate` é uma fração 0.0-1.0 (não porcentagem)."""
    for threshold, emoji, label in _TIERS:
        if rate >= threshold:
            return emoji, label
    return _TIERS[-1][1], _TIERS[-1][2]  # inalcançável (0.0 sempre bate acima), só por segurança


def summarize_by_model(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega o log por (papel, modelo): soma de propostos/válidos/descartes
    e a acertividade recalculada sobre o total agregado (não a média das
    taxas por lote — um lote de 1 item não pode pesar igual a um de 20).
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "role", "model", "items_proposed", "items_valid",
                "discarded_duplicate_slug", "discarded_validation_error",
                "images_discarded", "accuracy_rate",
            ]
        )

    sum_columns = [
        "items_proposed", "items_valid",
        "discarded_duplicate_slug", "discarded_validation_error", "images_discarded",
    ]
    grouped = df.groupby(["role", "model"], as_index=False)[sum_columns].sum()
    grouped["accuracy_rate"] = grouped["items_valid"] / grouped["items_proposed"].replace(0, pd.NA)
    grouped["accuracy_rate"] = grouped["accuracy_rate"].fillna(1.0)
    return grouped


def _render() -> None:
    """Desenha a página do Streamlit. Só é chamado via `streamlit run`."""
    import altair as alt
    import streamlit as st

    st.set_page_config(page_title="dev-agent — Qualidade", page_icon="🎯", layout="wide")
    st.title("🎯 dev-agent — Qualidade e acertividade")
    st.caption(
        "Quanto do que cada agente PROPÕE sobrevive à autovalidação real "
        "(agents/researcher.py::validate_batch) — não confiança no que o "
        "modelo afirma, e sim no que passou no schema/checagem de verdade."
    )

    df = load_quality()

    if df.empty:
        st.info(
            "Nenhum lote validado ainda. Rode o pesquisador contra uma tarefa "
            "real (ex: `python projects/research_concilios.py`) pra começar a "
            "ver dados aqui."
        )
        return

    total_proposed = int(df["items_proposed"].sum())
    total_valid = int(df["items_valid"].sum())
    overall_rate = total_valid / total_proposed if total_proposed else 1.0
    emoji, label = accuracy_tier(overall_rate)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lotes validados", len(df))
    col2.metric("Itens propostos", total_proposed)
    col3.metric("Itens válidos", total_valid)
    col4.metric(f"Acertividade geral {emoji}", f"{overall_rate:.0%}", help=label)

    st.subheader("Acertividade por papel e modelo")
    by_model = summarize_by_model(df)
    by_model["rótulo"] = by_model.apply(
        lambda row: f"{row['role']} · {row['model'] or 'desconhecido'}", axis=1
    )
    by_model["emoji"] = by_model["accuracy_rate"].apply(lambda r: accuracy_tier(r)[0])

    accuracy_chart = (
        alt.Chart(by_model)
        .mark_bar(color=_COLOR_SEQUENTIAL, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "accuracy_rate:Q", title="Acertividade",
                axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]),
            ),
            y=alt.Y("rótulo:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("rótulo:N", title="Papel · modelo"),
                alt.Tooltip("items_valid:Q", title="Válidos"),
                alt.Tooltip("items_proposed:Q", title="Propostos"),
                alt.Tooltip("accuracy_rate:Q", title="Acertividade", format=".0%"),
            ],
        )
        .properties(height=max(120, 36 * len(by_model)))
    )
    st.altair_chart(accuracy_chart, width="stretch")
    st.dataframe(
        by_model[[
            "emoji", "role", "model", "items_proposed", "items_valid", "accuracy_rate",
        ]].rename(columns=_COLUMN_LABELS),
        width="stretch",
        hide_index=True,
        column_config={"acertividade": st.column_config.ProgressColumn(
            "acertividade", format="%.0f%%", min_value=0, max_value=1
        )},
    )

    st.subheader("Por que um item é descartado")
    reasons = by_model.melt(
        id_vars=["rótulo"],
        value_vars=["discarded_duplicate_slug", "discarded_validation_error", "images_discarded"],
        var_name="motivo",
        value_name="quantidade",
    )
    reason_labels = {
        "discarded_duplicate_slug": "slug duplicado",
        "discarded_validation_error": "falhou schema",
        "images_discarded": "imagem não resolveu (entrada mantida)",
    }
    reason_colors = {
        "slug duplicado": _COLOR_WARNING,
        "falhou schema": _COLOR_CRITICAL,
        "imagem não resolveu (entrada mantida)": "#898781",
    }
    reasons["motivo"] = reasons["motivo"].map(reason_labels)

    if reasons["quantidade"].sum() == 0:
        st.success("Nenhum descarte registrado ainda — só lotes 100% válidos até aqui. 🎉")
    else:
        reasons_chart = (
            alt.Chart(reasons)
            .mark_bar()
            .encode(
                x=alt.X("quantidade:Q", title="Itens descartados"),
                y=alt.Y("rótulo:N", title=None),
                color=alt.Color(
                    "motivo:N",
                    title="Motivo",
                    scale=alt.Scale(
                        domain=list(reason_colors.keys()), range=list(reason_colors.values())
                    ),
                ),
                tooltip=["rótulo", "motivo", "quantidade"],
            )
            .properties(height=max(120, 36 * len(by_model)))
        )
        st.altair_chart(reasons_chart, width="stretch")

    st.subheader("Acertividade ao longo do tempo")
    timeline = df.sort_values("timestamp")
    timeline_chart = (
        alt.Chart(timeline)
        .mark_line(point=True, color=_COLOR_SEQUENTIAL)
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y(
                "accuracy_rate:Q", title="Acertividade",
                axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]),
            ),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Quando"),
                alt.Tooltip("role:N", title="Papel"),
                alt.Tooltip("model:N", title="Modelo"),
                alt.Tooltip("accuracy_rate:Q", title="Acertividade", format=".0%"),
            ],
        )
    )
    st.altair_chart(timeline_chart, width="stretch")

    st.subheader("Lotes recentes")
    recent = df.sort_values("timestamp", ascending=False).head(50).copy()
    recent["emoji"] = recent["accuracy_rate"].apply(lambda r: accuracy_tier(r)[0])
    st.dataframe(
        recent[[
            "emoji", "timestamp", "role", "model", "items_proposed",
            "items_valid", "accuracy_rate",
        ]].rename(columns=_COLUMN_LABELS),
        width="stretch",
        hide_index=True,
        column_config={"acertividade": st.column_config.ProgressColumn(
            "acertividade", format="%.0f%%", min_value=0, max_value=1
        )},
    )

    st.caption(
        "Atualize a página pra ver dados novos — quality_log.jsonl é "
        "reescrito a cada lote validado de verdade (validate_batch)."
    )


if __name__ == "__main__":
    _render()
