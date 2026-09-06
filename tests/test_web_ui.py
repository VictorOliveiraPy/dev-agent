"""Testes para a lógica pura da interface web (web_ui.py).

Só cobre parsing de papel/avatar e soma de tokens — não inicializa o
runtime do Streamlit.
"""

import json

from web_ui import _avatar_for, _parse_speaker, _total_tokens


def test_should_extract_role_when_entry_has_speaker_prefix():
    assert _parse_speaker("[dev_backend] instrução: teste\nresultado: ok") == "dev_backend"
    assert _parse_speaker("[supervisor] próximo: arquiteto — motivo") == "supervisor"


def test_should_default_to_supervisor_when_entry_has_no_speaker_prefix():
    """Uma entrada mal formada não deveria acontecer (ver agents/supervisor.py),
    mas não pode quebrar a renderização do chat.
    """
    assert _parse_speaker("texto sem colchetes") == "supervisor"


def test_should_return_known_avatar_for_each_team_role():
    assert _avatar_for("arquiteto") == "🏛️"
    assert _avatar_for("dev_backend") == "⚙️"
    assert _avatar_for("dev_frontend") == "🎨"
    assert _avatar_for("supervisor") == "🧭"


def test_should_return_default_avatar_for_unknown_role():
    assert _avatar_for("papel_novo_desconhecido") == "🤖"


def test_should_return_zero_tokens_when_log_file_does_not_exist(tmp_path):
    assert _total_tokens(tmp_path / "nao_existe.jsonl") == 0


def test_should_sum_total_tokens_when_log_file_has_entries(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    entries = [
        {
            "timestamp": "2026-09-03T10:00:00+00:00",
            "role": "dev_backend",
            "model": "claude-opus-5",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        },
        {
            "timestamp": "2026-09-03T10:01:00+00:00",
            "role": "arquiteto",
            "model": "claude-haiku-4-5",
            "input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 30,
        },
    ]
    log_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")

    assert _total_tokens(log_path) == 180
