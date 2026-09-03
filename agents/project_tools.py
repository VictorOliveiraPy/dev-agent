"""Ferramentas de escrita no código REAL do time (não no `workspace/`).

As tools de `agents/tools.py` são sandboxed em `workspace/` de propósito —
nenhum papel do time toca no próprio código-fonte por padrão. Este módulo
existe só para a tarefa pontual de auto-refatoração: dar ao `dev_backend`
acesso de escrita à raiz do projeto, com uma lista de bloqueio explícita
para o que ele NUNCA deve tocar (segredos, git, ambiente virtual, e a
sandbox descartável dos outros testes).

Use com cautela — diferente de `tools.py`, um erro aqui afeta o projeto de
verdade. Por isso existe o checkpoint git antes de qualquer execução.
"""

import subprocess
from pathlib import Path

from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

_BLOCKED = {".env", ".env.example", ".git", ".venv", "workspace", "__pycache__"}


def _safe_path(relative_path: str) -> Path:
    """Resolve um caminho relativo à raiz do projeto e bloqueia:

    - path traversal (escapar da raiz do projeto);
    - qualquer caminho cujo primeiro segmento esteja em `_BLOCKED`.
    """
    target = (PROJECT_ROOT / relative_path).resolve()
    if not target.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"Caminho fora da raiz do projeto: {relative_path}")

    first_segment = Path(relative_path).parts[0] if relative_path not in ("", ".") else ""
    if first_segment in _BLOCKED:
        raise ValueError(f"Caminho bloqueado (fora do escopo da refatoração): {relative_path}")

    return target


@tool
def write_project_file(path: str, content: str) -> str:
    """Sobrescreve um arquivo do código-fonte real do time (fora da sandbox).

    Args:
        path: caminho relativo à raiz do projeto, ex: 'agents/llm.py'.
        content: conteúdo completo a ser escrito no arquivo.
    """
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Arquivo escrito: {path} ({len(content)} chars)"


@tool
def read_project_file(path: str) -> str:
    """Lê um arquivo do código-fonte real do time.

    Args:
        path: caminho relativo à raiz do projeto.
    """
    target = _safe_path(path)
    if not target.exists():
        return f"ERRO: arquivo não existe: {path}"
    return target.read_text(encoding="utf-8")


@tool
def list_project_dir(path: str = ".") -> str:
    """Lista arquivos do projeto real (exclui .git/.venv/workspace/__pycache__).

    Args:
        path: caminho relativo à raiz do projeto (default: raiz).
    """
    target = _safe_path(path)
    if not target.exists():
        return f"ERRO: diretório não existe: {path}"
    items = sorted(
        p.relative_to(PROJECT_ROOT).as_posix()
        for p in target.rglob("*")
        if not any(part in _BLOCKED for part in p.relative_to(PROJECT_ROOT).parts)
    )
    return "\n".join(items) if items else "(vazio)"


@tool
def run_project_command(command: str) -> str:
    """Roda um comando de verificação (ex: ruff, pytest) na raiz do projeto.

    Use o Python do próprio .venv explicitamente (ex:
    '.venv/bin/python -m ruff check .') — não confie em 'ruff'/'pytest'
    soltos, o PATH do shell pode resolver para outro ambiente.

    Args:
        command: comando de shell completo a executar.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
        )
        output = result.stdout + result.stderr
        if not output:
            return f"(sem saída, código de retorno {result.returncode})"
        return output[-4000:]
    except subprocess.TimeoutExpired:
        return "ERRO: comando excedeu 90s e foi interrompido."
