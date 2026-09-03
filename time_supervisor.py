"""Passo 4: o Supervisor decide sozinho qual especialista aciona e quando,
em vez de eu escolher manualmente (como nos Passos 2 e 3).
"""

from agentes.supervisor import executar

if __name__ == "__main__":
    historico = executar(
        "Crie uma feature simples de 'lista de favoritos': endpoint no "
        "backend para adicionar, listar e remover um item por id (guardado "
        "em memória) e uma tela no frontend em React que lista os favoritos "
        "e permite adicionar/remover. Não rode comandos de instalação, "
        "apenas escreva os arquivos."
    )

    print("\n\n=== HISTÓRICO COMPLETO ===")
    for entrada in historico:
        print(f"\n{entrada}")
