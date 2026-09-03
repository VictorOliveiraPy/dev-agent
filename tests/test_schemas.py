"""Testes para os modelos Pydantic compartilhados (agents/schemas.py).

Validação pura — nenhum destes testes chama a API da Anthropic.
"""

import pytest
from pydantic import ValidationError

from agents.schemas import ArchitecturePlan, Decision, PlannedFile, UsageEntry


def test_should_accept_valid_decision_payload():
    """Um payload com todos os campos certos vira um Decision válido."""
    decision = Decision(
        next_role="dev_backend", instruction="crie o endpoint X", reasoning="motivo"
    )

    assert decision.next_role == "dev_backend"


def test_should_reject_decision_when_next_role_is_not_in_allowed_set():
    """next_role só aceita os 4 valores conhecidos do time."""
    with pytest.raises(ValidationError):
        Decision(next_role="estagiario", instruction="", reasoning="")


def test_should_build_architecture_plan_with_nested_files():
    """ArchitecturePlan aceita uma lista de PlannedFile aninhada."""
    plan = ArchitecturePlan(
        project_name="todo-api",
        stack="FastAPI + React",
        summary="API simples de tarefas",
        files=[PlannedFile(path="backend/main.py", description="rotas da API")],
    )

    assert len(plan.files) == 1
    assert plan.files[0].path == "backend/main.py"


def test_should_reject_usage_entry_when_tokens_are_negative():
    """input_tokens/output_tokens/total_tokens nunca podem ser negativos."""
    with pytest.raises(ValidationError):
        UsageEntry(
            timestamp="2026-09-03T10:00:00+00:00",
            role="dev_backend",
            model="claude-opus-5",
            input_tokens=-1,
            output_tokens=0,
            total_tokens=0,
        )
