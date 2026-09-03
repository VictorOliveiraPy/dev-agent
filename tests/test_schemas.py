"""Testes para os modelos Pydantic compartilhados (agents/schemas.py).

Validação pura — nenhum destes testes chama a API da Anthropic.
"""

import pytest
from pydantic import ValidationError

from agents.schemas import (
    ArchitecturePlan,
    ColorToken,
    Decision,
    DesignPlan,
    PlannedFile,
    UsageEntry,
)


def _four_colors() -> list[ColorToken]:
    return [
        ColorToken(name="accent", hex="#2A6F4D"),
        ColorToken(name="surface", hex="#F4F1EA"),
        ColorToken(name="text", hex="#1A1A1A"),
        ColorToken(name="muted", hex="#6B7280"),
    ]


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


def test_should_reject_color_token_when_hex_is_malformed():
    """Cor tem que ser um hex de 6 dígitos válido, não qualquer string."""
    with pytest.raises(ValidationError):
        ColorToken(name="accent", hex="verde")


def test_should_reject_design_plan_when_fewer_than_four_colors():
    """Menos de 4 cores não é um sistema de design de verdade, é um acidente."""
    with pytest.raises(ValidationError):
        DesignPlan(
            colors=_four_colors()[:2],
            display_font="Fraunces",
            body_font="Source Sans 3",
            layout_concept="Sidebar fixa.",
        )


def test_should_reject_design_plan_when_more_than_six_colors():
    """Mais de 6 cores também é rejeitado — o objetivo é forçar uma decisão
    enxuta, não uma paleta infinita.
    """
    seven_colors = _four_colors() + [
        ColorToken(name="extra1", hex="#111111"),
        ColorToken(name="extra2", hex="#222222"),
        ColorToken(name="extra3", hex="#333333"),
    ]
    with pytest.raises(ValidationError):
        DesignPlan(
            colors=seven_colors,
            display_font="Fraunces",
            body_font="Source Sans 3",
            layout_concept="Sidebar fixa.",
        )


def test_should_render_readable_brief_when_design_plan_is_formatted():
    """to_brief() é o que vira parte da tarefa do agente de implementação —
    precisa conter toda decisão tomada, pronta pra ler.
    """
    plan = DesignPlan(
        colors=_four_colors(),
        display_font="Fraunces",
        body_font="Source Sans 3",
        layout_concept="Sidebar fixa + conteúdo em cards.",
    )

    brief = plan.to_brief()

    assert "accent=#2A6F4D" in brief
    assert "Fraunces" in brief
    assert "Source Sans 3" in brief
    assert "Sidebar fixa" in brief


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
