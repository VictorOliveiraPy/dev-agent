"""Ferramentas (tools) que os agentes do time podem usar para agir de
verdade no sistema de arquivos — escrever código, ler o que já existe,
rodar comandos.

O modelo NUNCA executa estas funções diretamente: ele só decide "quero
chamar write_file com esses argumentos" (tool_use). Quem executa é o
AgentExecutor, chamando a função Python de fato.

SEGURANÇA: todas as tools são restritas a uma pasta sandbox — nunca ao
sistema de arquivos inteiro. Por padrão essa sandbox é `workspace/` (a
pasta de teste descartável do próprio dev-agent), mas um script de
entrada pode apontar pra um projeto real de verdade definindo a variável
de ambiente `DEV_AGENT_WORKSPACE` ANTES de importar este módulo (ver
`build_fe_catolica.py` para um exemplo) — a raiz é lida uma única vez, na
importação, de propósito: a sandbox nunca muda no meio de uma execução.
"""

import os
import subprocess
from pathlib import Path

from langchain_core.tools import tool


def _resolve_workspace() -> Path:
    """Decide a raiz da sandbox: `DEV_AGENT_WORKSPACE` (projeto real) ou o
    `workspace/` padrão do dev-agent (usado nos testes e exemplos).
    """
    custom = os.environ.get("DEV_AGENT_WORKSPACE")
    if custom:
        return Path(custom).resolve()
    return (Path(__file__).parent.parent / "workspace").resolve()


WORKSPACE = _resolve_workspace()
WORKSPACE.mkdir(parents=True, exist_ok=True)


def _safe_path(relative_path: str) -> Path:
    """Resolve um caminho relativo à sandbox e bloqueia path traversal."""
    target = (WORKSPACE / relative_path).resolve()
    if not target.is_relative_to(WORKSPACE):
        raise ValueError(f"Caminho fora da sandbox permitida: {relative_path}")
    return target


@tool
def write_file(path: str, content: str) -> str:
    """Cria ou sobrescreve um arquivo dentro do workspace do projeto.

    Args:
        path: caminho relativo ao workspace, ex: 'backend/main.py'.
        content: conteúdo completo a ser escrito no arquivo.
    """
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Arquivo escrito: {path} ({len(content)} chars)"


@tool
def read_file(path: str) -> str:
    """Lê e devolve o conteúdo de um arquivo do workspace do projeto.

    Args:
        path: caminho relativo ao workspace.
    """
    target = _safe_path(path)
    if not target.exists():
        return f"ERRO: arquivo não existe: {path}"
    return target.read_text(encoding="utf-8")


@tool
def list_dir(path: str = ".") -> str:
    """Lista arquivos e pastas dentro de um diretório do workspace.

    Args:
        path: caminho relativo ao workspace (default: raiz do workspace).
    """
    target = _safe_path(path)
    if not target.exists():
        return f"ERRO: diretório não existe: {path}"
    items = sorted(p.relative_to(WORKSPACE).as_posix() for p in target.rglob("*"))
    return "\n".join(items) if items else "(vazio)"


@tool
def run_command(command: str) -> str:
    """Executa um comando de shell dentro do workspace (ex: 'python -m py_compile arquivo.py').

    Tem timeout de 60s e roda sempre com cwd fixo na sandbox — não é
    possível "cd" para fora dela.

    Args:
        command: comando de shell completo a executar.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        if not output:
            return f"(sem saída, código de retorno {result.returncode})"
        return output[-4000:]
    except subprocess.TimeoutExpired:
        return "ERRO: comando excedeu 60s e foi interrompido."
