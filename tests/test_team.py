"""Testes para a montagem de persona do time (agentes/team.py).

Só cobre lógica pura e determinística — nenhum destes testes chama a API
da Anthropic.
"""

import pytest

from agentes import team


@pytest.fixture
def standards_dir(tmp_path, monkeypatch):
    """Aponta agentes.team._STANDARDS_DIR para uma pasta de padrões isolada."""
    monkeypatch.setattr(team, "_STANDARDS_DIR", tmp_path)
    return tmp_path


def test_should_include_only_general_standards_when_role_has_no_specific_file(standards_dir):
    """Um papel sem entrada em _ROLE_STANDARDS só recebe general.md na persona."""
    (standards_dir / "general.md").write_text("Regra geral X", encoding="utf-8")

    persona = team._build_persona("arquiteto")

    assert "Regra geral X" in persona
    assert "Padrões específicos" not in persona


def test_should_include_role_specific_standards_when_file_exists(standards_dir):
    """dev_backend recebe general.md + backend.md na mesma persona."""
    (standards_dir / "general.md").write_text("Regra geral X", encoding="utf-8")
    (standards_dir / "backend.md").write_text("Regra de backend Y", encoding="utf-8")

    persona = team._build_persona("dev_backend")

    assert "Regra geral X" in persona
    assert "Regra de backend Y" in persona


def test_should_escape_curly_braces_when_standards_contain_code_examples(standards_dir):
    """Chaves literais de exemplo de código precisam ficar escapadas — sem
    isso o ChatPromptTemplate quebra (bug real que já aconteceu no projeto).
    """
    (standards_dir / "general.md").write_text('extra={"user_id": user.id}', encoding="utf-8")

    persona = team._build_persona("arquiteto")

    assert "{{" in persona
    assert "}}" in persona


def test_should_return_empty_string_when_standard_file_is_missing(standards_dir):
    """Um arquivo de padrão que não existe não derruba a montagem da persona."""
    assert team._read_standard("nao_existe.md") == ""
