"""Passo 2 do time: o Dev Backend ganha ferramentas e passa a agir de
verdade — escreve arquivos dentro do workspace/ do projeto, em vez de só
descrever o que faria (como no Passo 1, em main.py).
"""

from agentes.team import create_agent_with_tools
from agentes.tools import list_dir, read_file, run_command, write_file

BACKEND_TOOLS = [write_file, read_file, list_dir, run_command]


def demo(task: str) -> str:
    """Executa o Dev Backend (com tools) sobre uma tarefa em linguagem natural."""
    agent = create_agent_with_tools("dev_backend", BACKEND_TOOLS)
    result = agent.invoke({"task": task})
    output_text = result["output"]

    # A última mensagem do modelo pode vir como lista de content blocks
    # (thinking + texto) em vez de string pronta — normalizamos aqui.
    if isinstance(output_text, list):
        output_text = "".join(b.get("text", "") for b in output_text if b.get("type") == "text")
    return output_text


if __name__ == "__main__":
    output_text = demo(
        "Crie o backend FastAPI de uma feature de login (email + senha): "
        "endpoints POST /auth/register, POST /auth/login (retornando um "
        "token fake por enquanto) e GET /auth/me. Guarde usuários em "
        "memória, com senha hasheada usando APENAS a biblioteca padrão do "
        "Python (hashlib) — sem dependências novas. Não rode comandos de "
        "instalação, apenas escreva os arquivos."
    )
    print("\n=== RESPOSTA FINAL DO DEV_BACKEND ===")
    print(output_text)
