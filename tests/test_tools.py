"""Testes para o sandbox de caminho seguro de agents/tools.py.

Só cobre lógica pura e determinística — nenhum destes testes chama a API
da Anthropic nem invoca as tools via LangChain.
"""

import pytest
from langchain_core.tools import ToolException

from agents import tools


def test_should_resolve_path_when_it_stays_inside_workspace():
    """Um caminho relativo normal resolve dentro da WORKSPACE."""
    result = tools._safe_path("subdir/file.txt")

    assert result.is_relative_to(tools.WORKSPACE)


def test_should_reject_path_when_it_tries_to_escape_workspace():
    """Path traversal ('../../etc/passwd') precisa ser bloqueado.

    ToolException, não ValueError — é o tipo que o `handle_tool_error =
    True` de cada tool (setado no fim deste módulo, não no
    AgentExecutor — ver docstring de _safe_path) reconhece e converte em
    observação pro modelo, em vez de derrubar o loop inteiro."""
    with pytest.raises(ToolException):
        tools._safe_path("../../etc/passwd")


def test_should_enable_handle_tool_error_on_every_sandboxed_tool():
    """Trava de regressão: sem isso setado em CADA tool (não no
    AgentExecutor — não existe esse parâmetro na versão instalada do
    LangChain, ver agents/team.py::create_agent_with_tools), uma
    ToolException propaga e derruba o AgentExecutor inteiro em vez de
    virar uma observação recuperável pro modelo. Bug real, já aconteceu."""
    for sandboxed_tool in (tools.write_file, tools.read_file, tools.list_dir, tools.run_command):
        assert sandboxed_tool.handle_tool_error is True


def test_should_return_error_as_observation_when_tool_run_hits_sandbox_violation():
    """Fim a fim, pelo mesmo caminho que o AgentExecutor usa (`.run()`, não
    chamar a função Python direto): uma tool call com caminho fora da
    sandbox devolve uma STRING de erro (observação), não levanta exceção.
    """
    result = tools.read_file.run({"path": "../../etc/passwd"})

    assert "sandbox" in result.lower()


def test_should_replace_invalid_bytes_instead_of_raising_when_file_is_not_utf8(
    tmp_path, monkeypatch
):
    """Bug real de produção: run_command no Windows produz saída em cp1252,
    não UTF-8 — um arquivo escrito a partir dela derrubava read_file com
    UnicodeDecodeError, que (diferente de ToolException) não é pego por
    handle_tool_error e propagava cru, derrubando o AgentExecutor inteiro."""
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path)
    bad_file = tmp_path / "saida_cp1252.txt"
    bad_file.write_bytes("olá mundo".encode("cp1252"))  # 'á' não é UTF-8 válido sozinho

    result = tools.read_file.run({"path": "saida_cp1252.txt"})

    assert "mundo" in result
    assert "�" in result  # byte inválido virou replacement char, não exceção


def test_should_prune_noise_directories_when_listing(tmp_path, monkeypatch):
    """Bug real, achado antes de liberar DEV_AGENT_WORKSPACE pra cobrir
    vários projetos reais: sem podar node_modules/.venv/.git, um list_dir
    na raiz percorre dependência instalada de TODOS os projetos — 45 mil
    entradas medidas de verdade só até profundidade 6 em 5 repos."""
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path)
    (tmp_path / "node_modules" / "pacote").mkdir(parents=True)
    (tmp_path / "node_modules" / "pacote" / "index.js").write_text("x", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".git" / "objects").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x", encoding="utf-8")

    result = tools.list_dir.run({"path": "."})

    assert "src/main.py" in result
    assert "node_modules" not in result
    assert ".venv" not in result
    assert ".git" not in result


def test_should_truncate_listing_when_over_the_item_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path)
    monkeypatch.setattr(tools, "_MAX_LIST_ITEMS", 10)
    for i in range(30):
        (tmp_path / f"arquivo_{i}.txt").write_text("x", encoding="utf-8")

    result = tools.list_dir.run({"path": "."})

    assert len(result.splitlines()) == 11  # 10 itens + a linha de aviso
    assert "corte" in result.lower()


def test_should_resolve_custom_workspace_when_env_var_is_set(tmp_path, monkeypatch):
    """DEV_AGENT_WORKSPACE aponta a sandbox pra um projeto real, fora do
    workspace/ de testes do dev-agent.
    """
    custom_dir = tmp_path / "projeto-real"
    monkeypatch.setenv("DEV_AGENT_WORKSPACE", str(custom_dir))

    assert tools._resolve_workspace() == custom_dir.resolve()


def test_should_resolve_default_workspace_when_env_var_is_unset(monkeypatch):
    """Sem DEV_AGENT_WORKSPACE, a sandbox continua sendo o workspace/ padrão."""
    monkeypatch.delenv("DEV_AGENT_WORKSPACE", raising=False)

    assert tools._resolve_workspace().name == "workspace"
