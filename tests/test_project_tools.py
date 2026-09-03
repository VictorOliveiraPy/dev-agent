"""Testes para o sandbox de caminho seguro de agents/project_tools.py.

Só cobre lógica pura e determinística — nenhum destes testes chama a API
da Anthropic nem escreve de verdade no projeto.
"""

import pytest

from agents import project_tools


def test_should_resolve_path_when_it_stays_inside_project_root():
    """Um arquivo comum do projeto resolve normalmente."""
    result = project_tools._safe_path("agents/team.py")

    assert result.is_relative_to(project_tools.PROJECT_ROOT)


def test_should_reject_path_when_it_tries_to_escape_project_root():
    """Path traversal para fora da raiz do projeto precisa ser bloqueado."""
    with pytest.raises(ValueError):
        project_tools._safe_path("../outside.txt")


@pytest.mark.parametrize(
    "blocked_path", [".env", ".git/config", ".venv/bin/python", "workspace/x.txt"]
)
def test_should_reject_path_when_first_segment_is_blocked(blocked_path):
    """.env, .git, .venv e workspace/ nunca podem ser tocados por esta tool."""
    with pytest.raises(ValueError):
        project_tools._safe_path(blocked_path)
