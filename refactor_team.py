"""Dá ao dev_backend acesso de ESCRITA ao código REAL do time (fora da
sandbox workspace/), para tarefas de auto-manutenção — refatoração,
auditoria de aderência aos padrões, etc.

Pré-requisito de segurança: rode isto só com o working tree do git limpo —
se o resultado não for bom, `git diff` mostra exatamente o que mudou e
`git checkout -- .` reverte tudo.

Nota histórica: a primeira tarefa deste script (renomear identificadores
para inglês + logging estruturado + testes, seguindo standards/backend.md)
foi interrompida por falta de crédito de API e acabou sendo feita
manualmente. O script continua útil para a próxima rodada de manutenção.
"""

from agents.project_tools import (
    list_project_dir,
    read_project_file,
    run_project_command,
    write_project_file,
)
from agents.team import create_agent_with_tools, extract_agent_output_text

PROJECT_TOOLS = [write_project_file, read_project_file, list_project_dir, run_project_command]


def demo(task: str) -> str:
    """Executa o Dev Backend (com acesso ao código real) sobre uma tarefa."""
    agent = create_agent_with_tools("dev_backend", PROJECT_TOOLS)
    result = agent.invoke({"task": task})
    return extract_agent_output_text(result)


if __name__ == "__main__":
    output_text = demo(
        "Use list_project_dir para mapear o projeto e read_project_file "
        "para ler cada arquivo .py em agents/ e na raiz. Audite a "
        "aderência a standards/general.md e standards/backend.md (ignorando o "
        "que é específico de API REST: IDOR, JWT, CORS, webhook, dinheiro "
        "em centavos). Rode '.venv/bin/python -m ruff check .' e "
        "'.venv/bin/python -m pytest -q' via run_project_command. "
        "NÃO altere nenhum arquivo — apenas reporte, em português, o que "
        "encontrar: violações de padrão, resultado do ruff, resultado dos "
        "testes."
    )
    print("\n=== RESPOSTA FINAL DO DEV_BACKEND ===")
    print(output_text)
