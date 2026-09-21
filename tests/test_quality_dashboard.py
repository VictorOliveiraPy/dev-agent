"""Testes para a leitura/agregação de dados do dashboard de qualidade
(quality_dashboard.py). Só cobre a lógica pura — não inicializa o runtime
do Streamlit.
"""

import json

from quality_dashboard import accuracy_tier, load_quality, summarize_by_model


def _entry(**overrides) -> dict:
    base = {
        "timestamp": "2026-09-21T10:00:00+00:00",
        "role": "pesquisador",
        "model": "claude-sonnet-5",
        "items_proposed": 4,
        "items_valid": 3,
        "discarded_duplicate_slug": 1,
        "discarded_validation_error": 0,
        "images_discarded": 0,
    }
    base.update(overrides)
    return base


def test_should_return_empty_dataframe_when_log_file_does_not_exist(tmp_path):
    df = load_quality(tmp_path / "nao_existe.jsonl")

    assert df.empty
    assert "accuracy_rate" in df.columns


def test_should_parse_entries_and_compute_accuracy_rate(tmp_path):
    log_path = tmp_path / "quality_log.jsonl"
    log_path.write_text(json.dumps(_entry()) + "\n", encoding="utf-8")

    df = load_quality(log_path)

    assert len(df) == 1
    assert df.iloc[0]["role"] == "pesquisador"
    assert df.iloc[0]["accuracy_rate"] == 0.75


def test_should_skip_malformed_line_when_it_fails_schema_validation(tmp_path):
    log_path = tmp_path / "quality_log.jsonl"
    log_path.write_text(
        json.dumps(_entry()) + "\n" + '{"campo_invalido": true}\n',
        encoding="utf-8",
    )

    df = load_quality(log_path)

    assert len(df) == 1


def test_accuracy_tier_should_pick_highest_matching_threshold():
    assert accuracy_tier(1.0)[1] == "excelente"
    assert accuracy_tier(0.9)[1] == "excelente"
    assert accuracy_tier(0.89)[1] == "aceitável"
    assert accuracy_tier(0.7)[1] == "aceitável"
    assert accuracy_tier(0.69)[1] == "precisa atenção"
    assert accuracy_tier(0.0)[1] == "precisa atenção"


def test_summarize_by_model_should_aggregate_by_role_and_model(tmp_path):
    log_path = tmp_path / "quality_log.jsonl"
    lines = [
        _entry(
            model="claude-sonnet-5", items_proposed=4, items_valid=3, discarded_duplicate_slug=1
        ),
        _entry(
            model="claude-sonnet-5", items_proposed=2, items_valid=2, discarded_duplicate_slug=0
        ),
        _entry(
            model="deepseek-chat", items_proposed=5, items_valid=1, discarded_validation_error=4
        ),
    ]
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    df = load_quality(log_path)

    summary = summarize_by_model(df)

    sonnet = summary[summary["model"] == "claude-sonnet-5"].iloc[0]
    assert sonnet["items_proposed"] == 6
    assert sonnet["items_valid"] == 5
    assert sonnet["accuracy_rate"] == 5 / 6

    deepseek = summary[summary["model"] == "deepseek-chat"].iloc[0]
    assert deepseek["accuracy_rate"] == 1 / 5


def test_summarize_by_model_should_return_empty_with_right_columns_when_df_is_empty(tmp_path):
    df = load_quality(tmp_path / "nao_existe.jsonl")

    summary = summarize_by_model(df)

    assert summary.empty
    assert "accuracy_rate" in summary.columns
