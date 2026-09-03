"""Testes para a leitura de dados do dashboard (dashboard.py::load_usage).

Só cobre a lógica pura de parsing — não inicializa o runtime do Streamlit.
"""

import json

from dashboard import load_usage


def test_should_return_empty_dataframe_when_log_file_does_not_exist(tmp_path):
    """Antes da primeira chamada real ao modelo, o log ainda não existe."""
    df = load_usage(tmp_path / "nao_existe.jsonl")

    assert df.empty
    assert list(df.columns) == [
        "timestamp", "role", "model", "input_tokens", "output_tokens", "total_tokens",
        "cache_read_tokens", "cache_creation_tokens",
    ]


def test_should_parse_entries_when_log_file_has_lines(tmp_path):
    """Cada linha do JSONL vira uma linha do DataFrame, com timestamp parseado."""
    log_path = tmp_path / "usage_log.jsonl"
    entry = {
        "timestamp": "2026-09-03T10:00:00+00:00",
        "role": "dev_backend",
        "model": "claude-opus-5",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }
    log_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    df = load_usage(log_path)

    assert len(df) == 1
    assert df.iloc[0]["role"] == "dev_backend"
    assert df.iloc[0]["total_tokens"] == 150


def test_should_skip_malformed_line_when_it_fails_schema_validation(tmp_path):
    """Uma linha que não bate com UsageEntry é ignorada, não derruba o dashboard."""
    log_path = tmp_path / "usage_log.jsonl"
    valid_entry = {
        "timestamp": "2026-09-03T10:00:00+00:00",
        "role": "dev_backend",
        "model": "claude-opus-5",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }
    log_path.write_text(
        json.dumps(valid_entry) + "\n" + '{"campo_invalido": true}\n',
        encoding="utf-8",
    )

    df = load_usage(log_path)

    assert len(df) == 1
    assert df.iloc[0]["role"] == "dev_backend"
