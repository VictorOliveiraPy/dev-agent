"""Retoma a implementação do frontend do fe-catolica depois de uma queda
de rede no meio do build original (`build_fe_catolica.py`).

Não usa `run_frontend_task` (que sempre roda a etapa de DesignPlan do
zero) — o design já foi decidido e está em `frontend/tailwind.config.ts`;
redecidir agora arriscaria uma paleta diferente da já escrita. Em vez
disso, aciona `create_agent_with_tools` direto, instruindo o dev_frontend
a LER o que já existe (config do frontend + rotas do backend) e continuar
dali, sem tools de planejamento.
"""

import os

os.environ["DEV_AGENT_WORKSPACE"] = "/home/oliveira/Documentos/code/fe-catolica"

import logging  # noqa: E402

from agents.knowledge import search_standards  # noqa: E402
from agents.team import create_agent_with_tools, extract_agent_output_text  # noqa: E402
from agents.tools import list_dir, read_file, run_command, write_file  # noqa: E402

FRONTEND_TOOLS = [write_file, read_file, list_dir, run_command, search_standards]

TASK = (
    "O design system deste projeto JÁ FOI DECIDIDO — leia "
    "'frontend/tailwind.config.ts' e NÃO redecida cores/fontes, siga "
    "exatamente o que já está lá. A configuração do projeto Next.js "
    "(package.json, tsconfig.json, next.config.js, postcss.config.js, "
    "tailwind.config.ts) já existe — não recrie esses arquivos, só use.\n\n"
    "O backend já está COMPLETO em 'backend/' — use list_dir e read_file "
    "para examinar 'backend/app/routers.py' e 'backend/app/models.py' "
    "antes de escrever qualquer chamada de API, pra bater exatamente com "
    "os endpoints e formatos reais.\n\n"
    "Continue implementando o frontend a partir do que já existe: crie a "
    "estrutura 'app/' (App Router) com layout raiz, navegação clara entre "
    "as 8 categorias (Santos, Papas, Milagres Eucarísticos, Catecismo, "
    "Crisma, História da Igreja, Doutores da Igreja, Concílios), páginas "
    "de listagem e detalhe para cada categoria consumindo a API real do "
    "backend, e uma busca que funcione através de TODAS as categorias — "
    "esse é o requisito mais importante do projeto.\n\n"
    "Se estiver perto do limite de uma resposta, pare num ponto consistente "
    "(um arquivo completo) e continue na próxima chamada de tool — não "
    "deixe um arquivo pela metade."
)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    agent = create_agent_with_tools("dev_frontend", FRONTEND_TOOLS)
    result = agent.invoke({"task": TASK})
    output_text = extract_agent_output_text(result)

    print("\n=== RESPOSTA FINAL DO DEV_FRONTEND ===")
    print(output_text)
