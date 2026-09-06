"""Dispara o time completo (Supervisor) pra construir o BACKEND da Fase 1
do RepasseApp — PRD em `~/Documentos/code/medico/Project RepasseApp.docx`.

Segue o padrão de `build_fe_catolica.py`: aponta as tools pra um projeto
real via DEV_AGENT_WORKSPACE, definida ANTES de importar `agents` (ver
agents/tools.py::_resolve_workspace).

Diferente do fe-catolica (workspace único com backend/ e frontend/ juntos,
depois separado manualmente em dois repos), aqui backend e frontend já
nascem em repositórios git próprios (`repasse-api` e `repasse-web`), no
mesmo padrão dos outros projetos do time (alumia-api/alumia-web,
santo-guardiao-api/santo-guardiao-web). Esta execução cobre SÓ o backend;
`build_repasse_web.py` cobre o frontend depois, consumindo o contrato real
que esta rodada produzir.

Escopo: só a Fase 1 do roadmap do PRD (Autenticação, CRUD de plantões e
Dashboard financeiro do mês vigente — Core Free), não o PRD inteiro. Fases
2-4 (amizades, match PRO, relatórios PRO) ficam para execuções seguintes —
o Supervisor tem teto de 10 rodadas por execução, e tentar o PRD inteiro de
uma vez arrisca estourar esse teto no meio de uma feature.
"""

import os

os.environ["DEV_AGENT_WORKSPACE"] = "/home/oliveira/Documentos/code/repasse-api"

import logging  # noqa: E402 (import depois do env var de propósito)

from agents.supervisor import run  # noqa: E402

TASK = (
    "Construa o BACKEND (FastAPI + PostgreSQL via SQLAlchemy) da Fase 1 do "
    "RepasseApp, um app de gestão financeira de plantões médicos. Este é "
    "um repositório SÓ de backend — não escreva nenhum código de frontend/UI.\n\n"
    "Escopo da Fase 1 (não implemente mais que isso agora):\n"
    "1. Autenticação: cadastro e login por email/senha, com JWT "
    "(access + refresh token).\n"
    "2. Entidade USERS: id (UUID), name, email (único), phone, crm, "
    "specialty, subscription_tier (enum: free/pro), created_at.\n"
    "3. CRUD de plantões (entidade SHIFTS), sempre filtrado pelo dono "
    "(user_id) autenticado — nunca por id sozinho: hospital_name, "
    "requester_name, start_time, end_time, duration_hours (calculado a "
    "partir de start_time/end_time), value (decimal, nunca float), "
    "payment_due_date, payment_status (enum: pending/received), "
    "shift_status (enum: confirmed/looking_for_cover/transferred), "
    "created_at.\n"
    "4. Endpoint de dashboard do mês vigente: soma do valor a receber "
    "(payment_status=pending), soma do valor já recebido "
    "(payment_status=received), total de plantões e total de horas do mês "
    "corrente, mais a lista cronológica dos próximos plantões.\n"
    "5. Regra de negócio: usuários do plano 'free' só podem consultar o "
    "mês vigente — qualquer filtro por mês anterior deve devolver 403 com "
    "um código de erro estável (ex.: 'PRO_REQUIRED'), nunca os dados; "
    "usuários 'pro' não têm essa restrição.\n\n"
    "Siga a arquitetura em camadas de standards/backend.md (app/core, "
    "app/models, app/schemas, app/routers, app/services), com exceções "
    "tipadas, JWT completo (exp/iat/sub validados, rotação de refresh "
    "token) e testes (TDD, nomenclatura test_should_..._when_...). Ao "
    "final, deixe rodando e documentado como subir localmente (README com "
    "setup + variáveis de ambiente esperadas), e valide de verdade "
    "instalando dependências e rodando lint/typecheck/testes antes de "
    "declarar concluído."
)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    history = run(TASK)

    print("\n\n=== HISTÓRICO COMPLETO ===")
    for entry in history:
        print(f"\n{entry}")
