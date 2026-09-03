"""Passo 1 do time de tecnologia: o mesmo pedido visto por papéis
diferentes, cada um respondendo sob sua especialidade.

Ainda não há orquestração (ninguém decide "quem fala primeiro" ou passa
trabalho adiante) nem tools (ninguém escreve arquivo de verdade) — isso são
os próximos passos. Aqui validamos só a fundação: fábrica de modelo +
personas.
"""

from agentes.equipe import PAPEIS, criar_agente


def demo(pedido: str) -> None:
    """Envia o mesmo pedido para cada papel do time e imprime as respostas."""
    for papel in PAPEIS:
        agente = criar_agente(papel)
        resposta = agente.invoke({"pedido": pedido})
        print(f"\n=== {papel.upper()} ===")
        print(resposta)


if __name__ == "__main__":
    demo(
        "Precisamos de uma feature de login de usuário (email + senha) no "
        "nosso projeto FastAPI + React. O que você faria?"
    )
