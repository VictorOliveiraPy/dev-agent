"""Dispara o time completo (Supervisor) pra construir o PRIMEIRO projeto
real do dev-agent: a plataforma "fe-catolica".

Diferente de main.py/dev_backend_agent.py/etc. (que escrevem em
workspace/, sandbox descartável), este script aponta as tools pra um
projeto real e keepable — /home/oliveira/Documentos/code/fe-catolica,
repositório git próprio — via a env var DEV_AGENT_WORKSPACE. Essa env var
PRECISA ser definida antes de importar qualquer coisa de `agents`, porque
`agents.tools` lê a sandbox uma única vez, na importação (ver
agents/tools.py::_resolve_workspace).

Cuidado deliberado no texto da tarefa: como o conteúdo é sobre fatos
religiosos/históricos reais (santos, papas, milagres, concílios), a
instrução pede fatos AMPLAMENTE conhecidos e não controversos como
exemplo, não uma tentativa de cobrir tudo de uma vez — reduz o risco de
alucinação e deixa claro, no próprio pedido, que os exemplos são um ponto
de partida a expandir, não um catálogo definitivo.
"""

import os

os.environ["DEV_AGENT_WORKSPACE"] = "/home/oliveira/Documentos/code/fe-catolica"

import logging  # noqa: E402 (import depois do env var de propósito)

from agents.supervisor import run  # noqa: E402

TASK = (
    "Construa a ESTRUTURA de uma plataforma web sobre a Igreja Católica: "
    "backend FastAPI + frontend Next.js/TypeScript. A plataforma precisa "
    "cobrir estas categorias de conteúdo, todas navegáveis e buscáveis: "
    "Santos (e suas histórias), Papas, Milagres Eucarísticos registrados, "
    "Catecismo, Crisma, História da Igreja, Doutores da Igreja, Concílios. "
    "\n\n"
    "Este é o PRIMEIRO passo: o objetivo é a estrutura completa e bem "
    "organizada, NÃO um catálogo extenso. Para cada categoria, modele os "
    "dados no backend e crie de 2 a 3 exemplos REAIS, amplamente "
    "conhecidos e NÃO controversos (santos e papas de reconhecimento "
    "universal, milagres eucarísticos já oficialmente documentados pela "
    "Igreja) — não invente fato nenhum; se não tiver certeza absoluta de "
    "um detalhe (data, local), prefira omitir a arriscar errar. Deixe "
    "explícito nos dados/comentários que são exemplos iniciais a expandir "
    "depois, não um catálogo definitivo.\n\n"
    "O requisito mais importante do projeto é a NAVEGAÇÃO: o usuário "
    "precisa conseguir achar qualquer tema facilmente — menu/navegação "
    "clara entre TODAS as categorias e uma busca que funcione através "
    "delas. Siga os padrões de design do time (evite interface genérica, "
    "decida paleta e tipografia de propósito)."
)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    history = run(TASK)

    print("\n\n=== HISTÓRICO COMPLETO ===")
    for entry in history:
        print(f"\n{entry}")
