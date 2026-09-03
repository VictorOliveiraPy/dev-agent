"""Passo 3 do time: o Dev Frontend, com as mesmas ferramentas do Dev
Backend (Passo 2).

Diferença proposital neste teste: a tarefa instrui o agente a LER o código
do backend (já escrito por dev_backend_agent.py) antes de implementar a UI
— ou seja, ele usa `read_file`/`list_dir` não só para criar, mas para se
informar sobre um contrato que ele mesmo não definiu. Isso antecipa o
Passo 4 (Supervisor): times reais coordenam trabalho consultando o que os
outros membros já fizeram, não trabalhando às cegas.
"""

from agentes.team import create_agent_with_tools
from agentes.tools import list_dir, read_file, run_command, write_file

FRONTEND_TOOLS = [write_file, read_file, list_dir, run_command]


def demo(task: str) -> str:
    """Executa o Dev Frontend (com tools) sobre uma tarefa em linguagem natural."""
    agent = create_agent_with_tools("dev_frontend", FRONTEND_TOOLS)
    result = agent.invoke({"task": task})
    output_text = result["output"]

    if isinstance(output_text, list):
        output_text = "".join(b.get("text", "") for b in output_text if b.get("type") == "text")
    return output_text


if __name__ == "__main__":
    output_text = demo(
        "Antes de escrever qualquer coisa, use list_dir e read_file para "
        "examinar 'backend/app/routers/auth.py' e 'backend/app/schemas.py' "
        "dentro do workspace — é o backend de login que já existe. Depois, "
        "crie o frontend em React (Vite) dessa feature: tela de login, "
        "tela de registro, e um contexto de autenticação (AuthContext) que "
        "guarda o token e expõe login/logout/usuário atual. As chamadas à "
        "API devem bater exatamente com os endpoints e formatos de "
        "request/response que você encontrar no backend real — não invente "
        "nada que não esteja lá. Não rode comandos de instalação, apenas "
        "escreva os arquivos."
    )
    print("\n=== RESPOSTA FINAL DO DEV_FRONTEND ===")
    print(output_text)
