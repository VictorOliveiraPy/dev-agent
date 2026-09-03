"""Modelos Pydantic compartilhados entre módulos do time — um lugar único
para os "contratos de dados" que atravessam mais de um arquivo, em vez de
dicts soltos com o mesmo formato reimplementado em cada ponta.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Decision(BaseModel):
    """Decisão do Supervisor sobre o próximo passo do time (ver agentes/supervisor.py)."""

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


class UsageEntry(BaseModel):
    """Uma chamada registrada ao modelo: quem, quantos tokens, quando.

    É o schema de cada linha de `usage_log.jsonl` — escrito por
    `agentes/usage.py` e lido por `dashboard.py`. Ter os dois lados
    validando contra o MESMO modelo evita o log e o dashboard divergirem
    silenciosamente sobre o formato dos dados.
    """

    timestamp: datetime
    role: str = Field(description="Papel do time responsável pela chamada, ex: 'dev_backend'.")
    model: str = Field(description="ID do modelo Claude usado, ex: 'claude-opus-5'.")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
