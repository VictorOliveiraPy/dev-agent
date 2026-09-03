"""Passo 2 do time: o Dev Backend ganha ferramentas e passa a agir de
verdade — escreve arquivos dentro do workspace/ do projeto, em vez de só
descrever o que faria (como no Passo 1, em main.py).
"""

from agentes.equipe import criar_agente_com_ferramentas
from agentes.tools import list_dir, read_file, run_command, write_file

TOOLS_DEV_BACKEND = [write_file, read_file, list_dir, run_command]


def demo(pedido: str) -> str:
    """Executa o Dev Backend (com tools) sobre um pedido em linguagem natural."""
    agente = criar_agente_com_ferramentas("dev_backend", TOOLS_DEV_BACKEND)
    resultado = agente.invoke({"pedido": pedido})
    saida = resultado["output"]

    # A última mensagem do modelo pode vir como lista de content blocks
    # (thinking + texto) em vez de string pronta — normalizamos aqui.
    if isinstance(saida, list):
        saida = "".join(b.get("text", "") for b in saida if b.get("type") == "text")
    return saida


if __name__ == "__main__":
    saida = demo(
        "Crie o backend FastAPI de uma feature de login (email + senha): "
        "endpoints POST /auth/register, POST /auth/login (retornando um "
        "token fake por enquanto) e GET /auth/me. Guarde usuários em "
        "memória, com senha hasheada usando APENAS a biblioteca padrão do "
        "Python (hashlib) — sem dependências novas. Não rode comandos de "
        "instalação, apenas escreva os arquivos."
    )
    print("\n=== RESPOSTA FINAL DO DEV_BACKEND ===")
    print(saida)
