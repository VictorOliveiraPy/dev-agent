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
