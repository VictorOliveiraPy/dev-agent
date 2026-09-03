"""Dashboard Streamlit: acompanha tokens gastos e atividade de cada agente
do time, lendo `usage_log.jsonl` (gerado por `agents/usage.py` a cada
chamada real ao modelo — ver `agents/team.py`).

Rodar: .venv/bin/streamlit run dashboard.py

`load_usage()` fica fora do bloco `if __name__ == "__main__":` de propósito
— é lógica pura e testável (ver tests/test_dashboard.py) que não depende
do runtime do Streamlit; todo o resto (gráficos, métricas) só roda quando
o arquivo é executado via `streamlit run`, nunca ao ser importado.
"""

import logging
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from agents.schemas import UsageEntry

logger = logging.getLogger(__name__)

USAGE_LOG_PATH = Path(__file__).parent / "usage_log.jsonl"

USAGE_COLUMNS = [
    "timestamp", "role", "model", "input_tokens", "output_tokens", "total_tokens",
    "cache_read_tokens", "cache_creation_tokens",
]


def load_usage(log_path: Path = USAGE_LOG_PATH) -> pd.DataFrame:
    """Lê o arquivo de log de uso inteiro e devolve como DataFrame.

    Cada linha é validada contra `UsageEntry` — o mesmo modelo usado por
    `agents/usage.py` pra escrever o log. Uma linha malformada (log antigo,
    edição manual) é ignorada com um aviso no log, não derruba o dashboard
    inteiro.

    Devolve um DataFrame vazio (mas com as colunas certas) se o arquivo
    ainda não existir — acontece antes da primeira chamada real ao modelo.
    """
    if not log_path.exists():
        return pd.DataFrame(columns=USAGE_COLUMNS)

    entries: list[UsageEntry] = []
    for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(UsageEntry.model_validate_json(line))
        except ValidationError as exc:
            logger.warning(
                "Linha inválida em usage_log.jsonl, ignorada",
                extra={"line_number": line_number, "error": str(exc)},
            )

    if not entries:
        return pd.DataFrame(columns=USAGE_COLUMNS)

    df = pd.DataFrame([entry.model_dump() for entry in entries])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _render() -> None:
    """Desenha a página do Streamlit. Só é chamado via `streamlit run`."""
    import streamlit as st

    st.set_page_config(page_title="dev-agent — Uso e Custos", page_icon="🤖", layout="wide")
    st.title("🤖 dev-agent — Uso de tokens por agente")

    df = load_usage()

    if df.empty:
        st.info(
            "Nenhum uso registrado ainda. Rode algum agente do time "
            "(ex: `.venv/bin/python main.py`) pra começar a ver dados aqui."
        )
        return

    total_input = int(df["input_tokens"].sum())
    cache_read = int(df["cache_read_tokens"].sum())
    # Taxa de acerto do cache: quanto do input total já veio do cache em
    # vez de ser cobrado no preço cheio — ver standards/backend.md e
    # ARCHITECTURE.md, seção "Custo". Denominador inclui o próprio cache
    # read porque ele É input (só que mais barato), não input adicional.
    cache_hit_rate = cache_read / (total_input + cache_read) if (total_input + cache_read) else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de chamadas", len(df))
    col2.metric("Tokens de entrada", total_input)
    col3.metric("Tokens de saída", int(df["output_tokens"].sum()))
    col4.metric("Taxa de acerto do cache", f"{cache_hit_rate:.0%}")

    st.subheader("Tokens por agente (papel)")
    role_columns = [
        "input_tokens", "output_tokens", "total_tokens",
        "cache_read_tokens", "cache_creation_tokens",
    ]
    by_role = df.groupby("role")[role_columns].sum()
    st.bar_chart(by_role["total_tokens"])
    st.dataframe(by_role, use_container_width=True)

    st.subheader("Tokens ao longo do tempo")
    by_time = df.set_index("timestamp")["total_tokens"].resample("1min").sum()
    st.line_chart(by_time)

    st.subheader("Chamadas recentes")
    st.dataframe(
        df.sort_values("timestamp", ascending=False).head(50),
        use_container_width=True,
    )

    st.caption(
        "Atualize a página pra ver dados novos — usage_log.jsonl é "
        "reescrito a cada chamada real ao modelo."
    )


if __name__ == "__main__":
    _render()
