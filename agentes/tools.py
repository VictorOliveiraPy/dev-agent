"""Ferramentas (tools) que os agentes do time podem usar para agir de
verdade no sistema de arquivos — escrever código, ler o que já existe,
rodar comandos.

O modelo NUNCA executa estas funções diretamente: ele só decide "quero
chamar write_file com esses argumentos" (tool_use). Quem executa é o
AgentExecutor, chamando a função Python de fato.

SEGURANÇA: todas as tools são restritas a uma pasta sandbox (`workspace/`)
na raiz do projeto — nunca ao sistema de arquivos inteiro.
"""

import subprocess
from pathlib import Path

from langchain_core.tools import tool

WORKSPACE = (Path(__file__).parent.parent / "workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)


def _caminho_seguro(caminho_relativo: str) -> Path:
    """Resolve um caminho relativo à sandbox e bloqueia path traversal."""
    destino = (WORKSPACE / caminho_relativo).resolve()
    if not destino.is_relative_to(WORKSPACE):
        raise ValueError(f"Caminho fora da sandbox permitida: {caminho_relativo}")
    return destino


@tool
def write_file(caminho: str, conteudo: str) -> str:
    """Cria ou sobrescreve um arquivo dentro do workspace do projeto.

    Args:
        caminho: caminho relativo ao workspace, ex: 'backend/main.py'.
        conteudo: conteúdo completo a ser escrito no arquivo.
    """
    destino = _caminho_seguro(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")
    return f"Arquivo escrito: {caminho} ({len(conteudo)} chars)"


@tool
def read_file(caminho: str) -> str:
    """Lê e devolve o conteúdo de um arquivo do workspace do projeto.

    Args:
        caminho: caminho relativo ao workspace.
    """
    destino = _caminho_seguro(caminho)
    if not destino.exists():
        return f"ERRO: arquivo não existe: {caminho}"
    return destino.read_text(encoding="utf-8")


@tool
def list_dir(caminho: str = ".") -> str:
    """Lista arquivos e pastas dentro de um diretório do workspace.

    Args:
        caminho: caminho relativo ao workspace (default: raiz do workspace).
    """
    destino = _caminho_seguro(caminho)
    if not destino.exists():
        return f"ERRO: diretório não existe: {caminho}"
    itens = sorted(p.relative_to(WORKSPACE).as_posix() for p in destino.rglob("*"))
    return "\n".join(itens) if itens else "(vazio)"


@tool
def run_command(comando: str) -> str:
    """Executa um comando de shell dentro do workspace (ex: 'python -m py_compile arquivo.py').

    Tem timeout de 60s e roda sempre com cwd fixo na sandbox — não é
    possível "cd" para fora dela.

    Args:
        comando: comando de shell completo a executar.
    """
    try:
        resultado = subprocess.run(
            comando,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=60,
        )
        saida = resultado.stdout + resultado.stderr
        if not saida:
            return f"(sem saída, código de retorno {resultado.returncode})"
        return saida[-4000:]
    except subprocess.TimeoutExpired:
        return "ERRO: comando excedeu 60s e foi interrompido."
