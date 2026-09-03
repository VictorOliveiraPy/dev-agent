"""Passo 3 do time: o Dev Frontend, com as mesmas ferramentas do Dev
Backend (Passo 2).

Diferença proposital neste teste: o pedido instrui o agente a LER o código
do backend (já escrito por dev_backend_agent.py) antes de implementar a UI
— ou seja, ele usa `read_file`/`list_dir` não só para criar, mas para se
informar sobre um contrato que ele mesmo não definiu. Isso antecipa o
Passo 4 (Supervisor): times reais coordenam trabalho consultando o que os
outros membros já fizeram, não trabalhando às cegas.
"""

from agentes.equipe import criar_agente_com_ferramentas
from agentes.tools import list_dir, read_file, run_command, write_file

TOOLS_DEV_FRONTEND = [write_file, read_file, list_dir, run_command]


def demo(pedido: str) -> str:
    """Executa o Dev Frontend (com tools) sobre um pedido em linguagem natural."""
    agente = criar_agente_com_ferramentas("dev_frontend", TOOLS_DEV_FRONTEND)
    resultado = agente.invoke({"pedido": pedido})
    saida = resultado["output"]

    if isinstance(saida, list):
        saida = "".join(b.get("text", "") for b in saida if b.get("type") == "text")
    return saida


if __name__ == "__main__":
    saida = demo(
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
    print(saida)
