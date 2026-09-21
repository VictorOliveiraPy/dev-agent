"""Testes para o escritório (office/server.py).

A maior parte cobre só a lógica pura (parse_entry, count_usage_lines,
read_new_usage_lines) — sem subir o servidor. O endpoint /config usa
`TestClient` (não abre socket de verdade) só pra confirmar o wiring HTTP;
nada aqui chama a API real nem abre WebSocket de ponta a ponta (isso foi
validado manualmente, ver PROGRESS.md).
"""

import json

from fastapi.testclient import TestClient

from office.server import (
    app,
    build_task_with_project_context,
    count_usage_lines,
    list_projects,
    parse_entry,
    read_new_usage_lines,
)


def test_should_classify_as_decision_when_supervisor_announces_next_role():
    result = parse_entry("[supervisor] próximo: dev_backend — implementar a API")

    assert result == {
        "role": "supervisor",
        "kind": "decision",
        "text": "próximo: dev_backend — implementar a API",
    }


def test_should_classify_as_info_when_supervisor_message_is_terminal():
    result = parse_entry("[supervisor] Deu a tarefa como concluída.")

    assert result["role"] == "supervisor"
    assert result["kind"] == "info"


def test_should_classify_as_result_when_entry_is_from_a_specialist():
    result = parse_entry("[dev_backend] instrução: crie o endpoint\nresultado: feito")

    assert result["role"] == "dev_backend"
    assert result["kind"] == "result"
    assert result["text"] == "instrução: crie o endpoint\nresultado: feito"


def test_should_fall_back_to_supervisor_info_when_entry_has_no_role_prefix():
    """Não deveria acontecer na prática (toda entrada de run() tem prefixo),
    mas não deve quebrar o streaming se acontecer."""
    result = parse_entry("texto sem prefixo de papel")

    assert result == {"role": "supervisor", "kind": "info", "text": "texto sem prefixo de papel"}


def test_should_return_zero_when_usage_log_does_not_exist(tmp_path):
    assert count_usage_lines(tmp_path / "nao_existe.jsonl") == 0


def test_should_count_existing_lines_in_usage_log(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    log_path.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")

    assert count_usage_lines(log_path) == 2


def test_should_return_empty_when_log_does_not_exist_yet(tmp_path):
    entries, offset = read_new_usage_lines(0, tmp_path / "nao_existe.jsonl")

    assert entries == []
    assert offset == 0


def test_should_read_only_lines_after_offset(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    entry_1 = {"role": "arquiteto", "total_tokens": 10}
    entry_2 = {"role": "dev_backend", "total_tokens": 20}
    log_path.write_text(json.dumps(entry_1) + "\n", encoding="utf-8")

    entries, offset = read_new_usage_lines(0, log_path)
    assert entries == [entry_1]
    assert offset == 1

    log_path.write_text(
        json.dumps(entry_1) + "\n" + json.dumps(entry_2) + "\n", encoding="utf-8"
    )
    entries, offset = read_new_usage_lines(offset, log_path)
    assert entries == [entry_2]
    assert offset == 2


def test_should_expose_active_provider_and_workspace_via_config_endpoint():
    """O front-end lê /config pra mostrar qual provedor e qual pasta estão
    ativos — nunca deve ficar implícito (ver docstring de office.server.config)."""
    client = TestClient(app)

    response = client.get("/config")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] in ("anthropic", "deepseek")
    assert body["workspace"]


def test_should_list_only_project_folders_when_listing_workspace(tmp_path):
    """Alimenta o seletor de projeto — pastas de dependência/cache (mesma
    lista de agents.tools._IGNORED_DIR_NAMES) e ocultas nunca aparecem
    como "projeto" pra escolher."""
    (tmp_path / "PsiEasy-API").mkdir()
    (tmp_path / "dev-agent").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "arquivo_solto.txt").write_text("x", encoding="utf-8")

    result = list_projects(tmp_path)

    assert result == ["PsiEasy-API", "dev-agent"]


def test_should_return_empty_list_when_workspace_does_not_exist(tmp_path):
    assert list_projects(tmp_path / "nao_existe") == []


def test_should_prefix_task_with_project_context_when_project_is_chosen():
    result = build_task_with_project_context("crie um endpoint novo", "PsiEasy-API")

    assert result.startswith("Projeto-alvo desta tarefa: `PsiEasy-API/`")
    assert result.endswith("crie um endpoint novo")


def test_should_return_task_unchanged_when_no_project_is_chosen():
    assert build_task_with_project_context("crie um endpoint novo", None) == "crie um endpoint novo"
    assert build_task_with_project_context("crie um endpoint novo", "") == "crie um endpoint novo"


def test_should_list_available_projects_via_endpoint():
    client = TestClient(app)

    response = client.get("/projects")

    assert response.status_code == 200
    assert isinstance(response.json()["projects"], list)


def test_should_skip_malformed_line_when_reading_new_usage(tmp_path):
    log_path = tmp_path / "usage_log.jsonl"
    valid = {"role": "arquiteto", "total_tokens": 10}
    log_path.write_text(json.dumps(valid) + "\n" + "linha quebrada\n", encoding="utf-8")

    entries, offset = read_new_usage_lines(0, log_path)

    assert entries == [valid]
    assert offset == 2
