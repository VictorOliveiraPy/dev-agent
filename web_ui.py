"""Interface web para rodar o time (Supervisor) e acompanhar a "conversa"
entre os papéis em tempo real, sem precisar do terminal.

Rodar: .venv/bin/streamlit run web_ui.py

Mesma separação de `dashboard.py`: as funções puras (`_parse_speaker`,
`_avatar_for`, `_total_tokens`) ficam fora do bloco `if __name__ ==
"__main__":` — são testáveis sem o runtime do Streamlit (ver
tests/test_web_ui.py). Todo o resto (formulário, chat ao vivo) só roda
quando o arquivo é executado via `streamlit run`.
"""

import logging
import re
from pathlib import Path

from dashboard import USAGE_LOG_PATH, load_usage

logger = logging.getLogger(__name__)

# Cada entrada do histórico do supervisor (ver agents/supervisor.py::run)
# começa com "[papel] ..." — usado tanto pra escolher o avatar quanto pro
# rótulo mostrado na bolha de chat.
_SPEAKER_PATTERN = re.compile(r"^\[(\w+)\]")

_AVATARS: dict[str, str] = {
    "supervisor": "🧭",
    "arquiteto": "🏛️",
    "dev_backend": "⚙️",
    "dev_frontend": "🎨",
}
_DEFAULT_AVATAR = "🤖"

_EXAMPLE_TASKS = [
    "Crie uma feature de login (email + senha) no projeto FastAPI + React.",
    (
        "Crie uma feature de 'lista de favoritos': endpoint no backend para "
        "adicionar, listar e remover um item por id (guardado em memória) e "
        "uma tela no frontend em React que lista os favoritos e permite "
        "adicionar/remover. Não rode comandos de instalação, apenas escreva "
        "os arquivos."
    ),
]


def _parse_speaker(entry: str) -> str:
    """Extrai o papel de uma entrada do histórico (`"[dev_backend] ..."` ->
    `"dev_backend"`). Devolve "supervisor" se a entrada não tiver o prefixo
    esperado — não deveria acontecer, mas evita que uma entrada mal
    formada quebre a renderização do chat.
    """
    match = _SPEAKER_PATTERN.match(entry)
    return match.group(1) if match else "supervisor"


def _avatar_for(speaker: str) -> str:
    """Emoji do avatar de um papel — `_DEFAULT_AVATAR` para um papel novo
    que ainda não foi adicionado a `_AVATARS`.
    """
    return _AVATARS.get(speaker, _DEFAULT_AVATAR)


def _total_tokens(log_path: Path = USAGE_LOG_PATH) -> int:
    """Soma de tokens (entrada + saída) já registrados em usage_log.jsonl.

    Reusa `dashboard.load_usage` (já testado) em vez de reabrir o arquivo
    na mão — a diferença entre duas chamadas a esta função, antes/depois de
    uma rodada do time, é quanto aquela rodada específica gastou.
    """
    df = load_usage(log_path)
    return int(df["total_tokens"].sum()) if not df.empty else 0


def _render() -> None:
    """Desenha a página do Streamlit. Só é chamado via `streamlit run`."""
    import streamlit as st

    from agents.supervisor import run

    st.set_page_config(page_title="dev-agent — Time ao vivo", page_icon="🤖", layout="wide")
    st.title("🤖 dev-agent — Rode o time e acompanhe a conversa")

    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("running", False)

    with st.sidebar:
        st.subheader("Exemplos de tarefa")
        for example in _EXAMPLE_TASKS:
            if st.button(example[:60] + ("…" if len(example) > 60 else ""), key=example):
                st.session_state["task_input"] = example
        st.caption(
            "Cada rodada faz chamadas reais à API (custo real). Ver "
            "`streamlit run dashboard.py` para o histórico completo de uso."
        )

    task = st.text_area(
        "Tarefa para o time",
        key="task_input",
        height=120,
        placeholder="Ex: crie uma tela de cadastro de usuário com nome e email.",
    )

    run_clicked = st.button(
        "▶️ Rodar",
        disabled=st.session_state["running"] or not task.strip(),
    )

    if run_clicked:
        st.session_state["messages"] = []

    for entry in st.session_state["messages"]:
        speaker = _parse_speaker(entry)
        with st.chat_message(speaker, avatar=_avatar_for(speaker)):
            st.markdown(entry)

    if run_clicked:
        st.session_state["running"] = True
        tokens_before = _total_tokens()

        try:
            with st.spinner("Time trabalhando… acompanhe abaixo"):
                for entry in run(task):
                    st.session_state["messages"].append(entry)
                    speaker = _parse_speaker(entry)
                    with st.chat_message(speaker, avatar=_avatar_for(speaker)):
                        st.markdown(entry)
        except Exception:
            # Erro real (rede, API key inválida, etc.) — mostra pro usuário
            # em vez de derrubar a página com uma stack trace, mas registra
            # o traceback completo no terminal (`streamlit run`) pra
            # debugar depois. Não silencia: o log + st.error cobrem os dois
            # lados (usuário e desenvolvedor) — ver standards/general.md.
            logger.exception("Falha ao rodar o time")
            st.error(
                "O time parou por um erro (ver o terminal onde rodou "
                "`streamlit run` para o detalhe técnico)."
            )
        finally:
            st.session_state["running"] = False

        tokens_spent = _total_tokens() - tokens_before
        st.metric("Tokens gastos nesta rodada", tokens_spent)


if __name__ == "__main__":
    _render()
