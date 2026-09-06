"""Passo 4: o Supervisor decide sozinho qual especialista aciona e quando,
em vez de eu escolher manualmente (como nos Passos 2 e 3).
"""

import logging

from agents.supervisor import run

if __name__ == "__main__":
    # Habilita o logging estruturado do supervisor (ver agents/supervisor.py)
    # neste terminal — sem isso as decisões de roteamento ficam invisíveis.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    # run() é um gerador — cada entrada aparece aqui assim que o supervisor
    # ou o especialista a produz, não só depois que todas as rodadas
    # terminam (ver docstring de agents.supervisor.run).
    print("\n=== TIME EM EXECUÇÃO (acompanhe abaixo) ===")
    for entry in run(
        "Crie uma feature simples de 'lista de favoritos': endpoint no "
        "backend para adicionar, listar e remover um item por id (guardado "
        "em memória) e uma tela no frontend em React que lista os favoritos "
        "e permite adicionar/remover. Não rode comandos de instalação, "
        "apenas escreva os arquivos."
    ):
        print(f"\n{entry}")
