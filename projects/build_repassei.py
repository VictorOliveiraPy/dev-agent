"""Dispara o time completo (Supervisor) para construir a Fase 1 do
"Repassei" — PWA de gestão financeira de plantões para profissionais de
saúde plantonistas.

Mesmo padrão do build_fe_catolica.py: workspace temporário (backend/ +
frontend/) via DEV_AGENT_WORKSPACE, definida ANTES de importar `agents`
(agents.tools lê a sandbox uma única vez, na importação). Depois de
validado, o conteúdo é dividido manualmente em repasse-api/repasse-web
(repos irmãos já criados, vazios) — mesmo fluxo usado no fe-catolica →
acervo-catolico-api/web.

Escopo deliberadamente estreito (Fase 1 do roadmap do PRD + PWA
instalável, nada de pagamento/matching/relatórios): lote grande demais
já se mostrou caro e arriscado (ver PROGRESS.md, lote de concílios).
"""

import os

os.environ["DEV_AGENT_WORKSPACE"] = "/home/oliveira/Documentos/code/repassei-build"

import logging  # noqa: E402 (import depois do env var de propósito)

from agents.supervisor import run  # noqa: E402

TASK = (
    "Construa a Fase 1 do app 'Repassei': uma PWA (Progressive Web App) de "
    "gestão financeira de plantões para profissionais de saúde plantonistas "
    "(médicos, residentes, enfermeiros). Stack: backend FastAPI (SQLAlchemy "
    "+ Alembic, Postgres) com autenticação JWT, seguindo a arquitetura em "
    "camadas e os padrões de segurança do time; frontend Next.js/"
    "TypeScript, instalável como PWA de verdade — manifest.json completo "
    "(nome 'Repassei', ícones, theme_color, display: standalone), service "
    "worker registrado, e um componente visível que escuta o evento "
    "beforeinstallprompt para oferecer 'Instalar aplicativo' (não basta o "
    "ícone padrão do navegador).\n\n"
    "Escopo desta fase — implemente exatamente isto, nada além:\n"
    "1. Autenticação: cadastro e login por e-mail/senha, JWT (access + "
    "refresh token), validando exp/iat/sub e com rotação de refresh "
    "token.\n"
    "2. Entidade User: nome, e-mail (único), telefone, CRM, especialidade, "
    "subscription_tier (enum free/pro, default free), created_at. O campo "
    "existe no modelo desde já, mas NENHUMA tela ou regra de cobrança "
    "precisa existir ainda — é só o dado, pronto pra fase futura.\n"
    "3. Entidade Shift (plantão), pertencente a um User: hospital_name, "
    "requester_name, start_time, end_time, duration_hours (calculada a "
    "partir de start/end), value (em CENTAVOS, nunca float), "
    "payment_due_date, payment_status (enum pending/received), "
    "created_at. CRUD completo (criar, listar, editar, marcar como "
    "recebido, excluir) — toda consulta já filtra por user_id na própria "
    "query (nunca buscar por id e checar dono depois).\n"
    "4. Dashboard: card do próximo plantão em destaque; 4 KPIs do MÊS "
    "VIGENTE (a receber em R$, recebido em R$, total de plantões, total "
    "de horas); lista cronológica dos próximos plantões com tag de "
    "status.\n\n"
    "Fora de escopo nesta fase — NÃO implemente: rede de amigos, "
    "disponibilidade compartilhada, matching automático de trocas, "
    "cobrança/assinatura PRO de verdade, relatórios/exportação, "
    "notificação push."
)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    history = run(TASK)

    print("\n\n=== HISTÓRICO COMPLETO ===")
    for entry in history:
        print(f"\n{entry}")
