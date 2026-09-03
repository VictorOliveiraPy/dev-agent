"""Modelos Pydantic compartilhados entre módulos do time — um lugar único
para os "contratos de dados" que atravessam mais de um arquivo, em vez de
dicts soltos com o mesmo formato reimplementado em cada ponta.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Decision(BaseModel):
    """Decisão do Supervisor sobre o próximo passo do time (ver agents/supervisor.py)."""

    next_role: Literal["arquiteto", "dev_backend", "dev_frontend", "concluido"] = Field(
        description="Qual papel deve agir agora, ou 'concluido' se a tarefa já foi atendida."
    )
    instruction: str = Field(
        description=(
            "Instrução específica e objetiva para esse papel executar agora "
            "(ignorado se next_role == 'concluido')."
        )
    )
    reasoning: str = Field(description="Por que essa é a próxima ação certa, em 1 frase.")


class PlannedFile(BaseModel):
    """Um arquivo que o plano de arquitetura prevê que será criado."""

    path: str = Field(description="Caminho relativo do arquivo, ex: backend/app/main.py")
    description: str = Field(description="O que esse arquivo deve conter, em 1 frase.")


class ArchitecturePlan(BaseModel):
    """Plano estruturado que o papel 'arquiteto' produz antes de qualquer
    código ser escrito.

    Substitui a resposta em texto livre desse papel — dá ao Supervisor e
    aos outros especialistas um contrato de dados confiável (nomes de
    campo fixos, lista de arquivos navegável) em vez de prosa que
    precisaria ser reinterpretada a cada rodada.
    """

    project_name: str = Field(description="Nome curto do projeto, em kebab-case.")
    stack: str = Field(description="Stack técnica resumida, ex: 'FastAPI + React'.")
    summary: str = Field(description="Resumo da decisão de arquitetura, em poucas frases.")
    files: list[PlannedFile] = Field(description="Arquivos a criar, na ordem de criação.")


class ColorToken(BaseModel):
    """Uma cor nomeada do sistema de design (design token), não um valor solto."""

    name: str = Field(description="Nome do token, ex: 'accent', 'surface', 'text-muted'.")
    hex: str = Field(description="Valor hexadecimal, ex: '#2A6F4D'.", pattern=r"^#[0-9A-Fa-f]{6}$")


class DesignPlan(BaseModel):
    """Plano de design estruturado que o papel 'dev_frontend' produz ANTES
    de escrever qualquer componente — ver standards/design.md, seção
    "Decida a paleta e a tipografia ANTES do código".

    Formaliza a recomendação da skill `artifact-design`: sem isso, cada
    componente decide cor/fonte na hora, de forma inconsistente entre telas.
    """

    colors: list[ColorToken] = Field(
        description="De 4 a 6 cores nomeadas do sistema — nunca a paleta default sem revisão.",
        min_length=4,
        max_length=6,
    )
    display_font: str = Field(description="Fonte de destaque (títulos), ex: 'Fraunces'.")
    body_font: str = Field(description="Fonte de corpo de texto, ex: 'Source Sans 3'.")
    layout_concept: str = Field(
        description="Conceito de layout em 1-2 frases, específico da tarefa."
    )
    avoided_cliches: list[str] = Field(
        default_factory=list,
        description=(
            "Quais clichês de 'design gerado por IA' (ver standards/design.md) "
            "foram considerados e evitados nesta decisão."
        ),
    )

    def to_brief(self) -> str:
        """Renderiza o plano como um brief de instrução pro agente que vai implementar.

        Usado por `agents.team.run_frontend_task` pra passar o design JÁ
        DECIDIDO como parte da tarefa da etapa de implementação — o agente
        com tools não decide cor/fonte de novo, só segue o que já foi
        decidido nesta etapa de planejamento.
        """
        colors = ", ".join(f"{c.name}={c.hex}" for c in self.colors)
        return (
            "Plano de design já decidido — siga-o à risca, não decida "
            "cores/fontes de novo:\n"
            f"- Cores: {colors}\n"
            f"- Fonte de destaque: {self.display_font}\n"
            f"- Fonte de corpo: {self.body_font}\n"
            f"- Layout: {self.layout_concept}"
        )


class UsageEntry(BaseModel):
    """Uma chamada registrada ao modelo: quem, quantos tokens, quando.

    É o schema de cada linha de `usage_log.jsonl` — escrito por
    `agents/usage.py` e lido por `dashboard.py`. Ter os dois lados
    validando contra o MESMO modelo evita o log e o dashboard divergirem
    silenciosamente sobre o formato dos dados.
    """

    timestamp: datetime
    role: str = Field(description="Papel do time responsável pela chamada, ex: 'dev_backend'.")
    model: str = Field(description="ID do modelo Claude usado, ex: 'claude-opus-5'.")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(
        default=0, ge=0, description="Tokens servidos do cache (~0.1x custo) — ver prompt caching."
    )
    cache_creation_tokens: int = Field(
        default=0, ge=0, description="Tokens escritos no cache nesta chamada (~1.25x custo)."
    )
