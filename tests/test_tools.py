"""Testes para o sandbox de caminho seguro de agents/tools.py.

Só cobre lógica pura e determinística — nenhum destes testes chama a API
da Anthropic nem invoca as tools via LangChain.
"""

import pytest

from agents import tools


def test_should_resolve_path_when_it_stays_inside_workspace():
    """Um caminho relativo normal resolve dentro da WORKSPACE."""
    result = tools._safe_path("subdir/file.txt")

    assert result.is_relative_to(tools.WORKSPACE)


def test_should_reject_path_when_it_tries_to_escape_workspace():
    """Path traversal ('../../etc/passwd') precisa ser bloqueado."""
    with pytest.raises(ValueError):
        tools._safe_path("../../etc/passwd")


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
