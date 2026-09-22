"""Testes para o escritório (office/server.py).

A maior parte cobre só a lógica pura (parse_entry, count_usage_lines,
read_new_usage_lines) — sem subir o servidor. O endpoint /config usa
`TestClient` (não abre socket de verdade) só pra confirmar o wiring HTTP;
nada aqui chama a API real nem abre WebSocket de ponta a ponta (isso foi
validado manualmente, ver PROGRESS.md).
"""

import json
import sys

import pytest
from fastapi.testclient import TestClient

from office import server
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


# ---------------------------------------------------------------------
# Pesquisador: painel próprio (categoria + schema real do backend), ver
# _stream_research. Testes de lógica pura só — não chamam research_batch
# nem a API real (isso foi validado manualmente, ver PROGRESS.md).
# ---------------------------------------------------------------------

_FAKE_BACKEND_MODELS_PY = '''
from enum import Enum

class Category(str, Enum):
    CONCILIOS = "concilios"
    SANTOS = "santos"

class Concilio:
    pass

class Santo:
    pass

ENTRY_MODEL_BY_CATEGORY = {Category.CONCILIOS: Concilio, Category.SANTOS: Santo}
'''


def _install_fake_backend(tmp_path, monkeypatch):
    """Cria um backend falso mínimo (só o que _load_acervo_models precisa)
    dentro de tmp_path, e aponta WORKSPACE/sys.modules pra ele — evita
    depender do repositório real do Acervo Católico estar clonado do lado
    pra testar o import dinâmico."""
    backend_dir = tmp_path / server._ACERVO_BACKEND_DIRNAME
    app_dir = backend_dir / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "models.py").write_text(_FAKE_BACKEND_MODELS_PY, encoding="utf-8")
    monkeypatch.setattr(server, "WORKSPACE", tmp_path)
    # Um `app` de verdade (Acervo-Cat-lico-API) pode já estar importado por
    # outro teste desta mesma sessão do pytest — limpa pra forçar reimport
    # do módulo falso, não o cache do de verdade.
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    return backend_dir


def test_should_raise_when_acervo_backend_is_not_in_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "WORKSPACE", tmp_path / "vazio")

    with pytest.raises(FileNotFoundError, match="Backend do acervo"):
        server._load_acervo_models()


def test_should_import_category_and_model_map_when_backend_exists(tmp_path, monkeypatch):
    _install_fake_backend(tmp_path, monkeypatch)

    category_enum, entry_model_by_category = server._load_acervo_models()

    assert category_enum("concilios").value == "concilios"
    assert set(entry_model_by_category.keys()) == {category_enum.CONCILIOS, category_enum.SANTOS}


def test_should_load_existing_slugs_from_the_real_data_file(tmp_path, monkeypatch):
    _install_fake_backend(tmp_path, monkeypatch)
    data_dir = server._acervo_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "concilios.json").write_text(
        json.dumps({"itens": [{"slug": "niceia-i"}, {"slug": "trento"}]}), encoding="utf-8"
    )

    assert server._load_existing_slugs("concilios") == {"niceia-i", "trento"}


def test_should_return_empty_slugs_when_data_file_does_not_exist_yet(tmp_path, monkeypatch):
    _install_fake_backend(tmp_path, monkeypatch)

    assert server._load_existing_slugs("concilios") == set()


def test_should_append_validated_entries_to_the_real_data_file(tmp_path, monkeypatch):
    _install_fake_backend(tmp_path, monkeypatch)
    data_dir = server._acervo_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    data_path = data_dir / "concilios.json"
    data_path.write_text(json.dumps({"itens": [{"slug": "niceia-i"}]}), encoding="utf-8")

    class _FakeEntry:
        def model_dump(self, mode="json"):
            return {"slug": "efeso"}

    server._write_entries("concilios", [_FakeEntry()])

    saved = json.loads(data_path.read_text(encoding="utf-8"))
    assert [item["slug"] for item in saved["itens"]] == ["niceia-i", "efeso"]


def test_should_not_touch_file_when_there_is_nothing_to_write(tmp_path, monkeypatch):
    """_write_entries([]) não deve exigir que o arquivo exista — nenhum
    item validado é um resultado normal (lote todo rejeitado), não erro."""
    _install_fake_backend(tmp_path, monkeypatch)

    server._write_entries("concilios", [])  # não deve levantar


def test_should_expose_real_categories_via_endpoint_when_backend_exists(tmp_path, monkeypatch):
    _install_fake_backend(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get("/research/categories")

    assert response.status_code == 200
    assert response.json() == {"categories": ["concilios", "santos"]}


def test_should_return_empty_categories_when_backend_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "WORKSPACE", tmp_path / "vazio")
    client = TestClient(app)

    response = client.get("/research/categories")

    assert response.status_code == 200
    assert response.json() == {"categories": []}
