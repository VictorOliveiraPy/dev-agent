"""Passo 1 do time de tecnologia: a mesma tarefa vista por papéis
diferentes, cada um respondendo sob sua especialidade.

Ainda não há orquestração (ninguém decide "quem fala primeiro" ou passa
trabalho adiante) nem tools (ninguém escreve arquivo de verdade) — isso são
os próximos passos. Aqui validamos só a fundação: fábrica de modelo +
personas.
"""

from agents.team import ROLES, create_agent


def demo(task: str) -> None:
    """Envia a mesma tarefa para cada papel do time e imprime as respostas."""
    for role in ROLES:
        agent = create_agent(role)
        response = agent.invoke({"task": task})
        print(f"\n=== {role.upper()} ===")
        print(response)


if __name__ == "__main__":
    demo(
        "Precisamos de uma feature de login de usuário (email + senha) no "
        "nosso projeto FastAPI + React. O que você faria?"
    )
