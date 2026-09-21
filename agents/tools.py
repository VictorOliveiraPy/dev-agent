"""Ferramentas (tools) que os agentes do time podem usar para agir de
verdade no sistema de arquivos — escrever código, ler o que já existe,
rodar comandos.

O modelo NUNCA executa estas funções diretamente: ele só decide "quero
chamar write_file com esses argumentos" (tool_use). Quem executa é o
AgentExecutor, chamando a função Python de fato.

SEGURANÇA: todas as tools são restritas a uma pasta sandbox — nunca ao
sistema de arquivos inteiro. Por padrão essa sandbox é `workspace/` (a
pasta de teste descartável do próprio dev-agent), mas um script de
entrada — ou o `.env` (`DEV_AGENT_WORKSPACE`, lido por `office/server.py`
e qualquer outro entrypoint) — pode apontar pra um projeto real de
verdade, ou pra uma pasta que contém VÁRIOS projetos (ex.: a raiz onde
todos os repos do usuário vivem), dando ao time acesso de leitura/escrita
a qualquer um deles quando a tarefa pedir. A raiz é lida uma única vez, na
importação, de propósito: a sandbox nunca muda no meio de uma execução —
pra apontar pra outro lugar, reinicie o processo.

⚠️ Quanto maior a sandbox, maior o raio de ação de um erro do modelo — se
`DEV_AGENT_WORKSPACE` cobre vários projetos reais (não mais um
`workspace/` descartável), `write_file`/`run_command` conseguem alterar
qualquer um deles de verdade, e `read_file` consegue ler qualquer arquivo
ali dentro, incluindo `.env` de outro projeto se a tarefa levar o agente
até lá. Isso é uma escolha deliberada (autorizada pelo usuário), não uma
falha de sandbox — mas vale saber o que está habilitado.
"""

import os
import subprocess
from pathlib import Path

from langchain_core.tools import ToolException, tool


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
    """Resolve um caminho relativo à sandbox e bloqueia path traversal.

    Levanta `ToolException` (não `ValueError`) de propósito: é uma
    exceção que `AgentExecutor(handle_tool_error=True)` (ver
    `agents/team.py::create_agent_with_tools`) reconhece e converte numa
    OBSERVAÇÃO devolvida ao modelo — "esse caminho não é permitido, tente
    outra coisa" — em vez de derrubar o loop inteiro. Um `ValueError`
    comum não recebe esse tratamento (só `ToolException`/`ValidationError`
    passam pelo `handle_tool_error`; qualquer outra exceção sempre
    propaga) — bug real: apareceu testando `office/server.py` contra um
    projeto real fora do workspace, onde essa tool call falhando derrubava
    a rodada inteira mesmo com orçamento de iterações sobrando.
    """
    target = (WORKSPACE / relative_path).resolve()
    if not target.is_relative_to(WORKSPACE):
        raise ToolException(f"Caminho fora da sandbox permitida: {relative_path}")
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
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Não é ToolException — UnicodeDecodeError é um ValueError comum,
        # então handle_tool_error (ver fim do módulo) NÃO o intercepta:
        # sem este try/except ele propaga cru e derruba o AgentExecutor
        # inteiro, mesmo tools.handle_tool_error=True (bug real, achado em
        # produção: `run_command` no Windows produz saída em cp1252, não
        # UTF-8, e um arquivo gerado a partir dela quebrava aqui). Troca
        # os bytes inválidos por "�" em vez de travar — o modelo recebe um
        # conteúdo talvez imperfeito, mas nunca uma exceção crua.
        return target.read_text(encoding="utf-8", errors="replace")


# Pastas nunca listadas (nem percorridas — podadas ANTES de descer, não
# filtradas depois): dependência instalada, VCS, cache de ferramenta. Sem
# isso, um `list_dir` na raiz de um workspace que cobre vários projetos
# reais (ver DEV_AGENT_WORKSPACE) percorre node_modules/.venv/.git de
# TODOS eles — só até profundidade 6, em 5 projetos reais, isso já é 45 mil
# entradas (medido de verdade, não estimado). Bug real, achado antes de
# liberar o sandbox pra cobrir múltiplos projetos.
_IGNORED_DIR_NAMES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".next", ".turbo", "dist", "build",
    "coverage", ".pnpm-store",
}

# Teto de itens por chamada — mesmo com as pastas ruidosas podadas, um
# projeto real sozinho pode ter milhares de arquivos de código; melhor
# cortar com aviso do que devolver um muro de texto sem fim.
_MAX_LIST_ITEMS = 500


@tool
def list_dir(path: str = ".") -> str:
    """Lista arquivos e pastas dentro de um diretório do workspace.

    Pula `node_modules/`, `.venv/`, `.git/` e outras pastas de dependência/
    cache automaticamente (nunca desce nelas) — se precisar delas mesmo
    assim, use `run_command` com um comando específico. Corta em 500 itens
    por chamada; refine `path` pra uma subpasta se vier truncado.

    Args:
        path: caminho relativo ao workspace (default: raiz do workspace).
    """
    target = _safe_path(path)
    if not target.exists():
        return f"ERRO: diretório não existe: {path}"

    items: list[str] = []
    for root, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIR_NAMES]
        root_path = Path(root)
        items.extend(
            (root_path / name).relative_to(WORKSPACE).as_posix()
            for name in (*dirnames, *filenames)
        )
        if len(items) > _MAX_LIST_ITEMS:
            break

    if not items:
        return "(vazio)"

    items.sort()
    truncated = len(items) > _MAX_LIST_ITEMS
    listing = "\n".join(items[:_MAX_LIST_ITEMS])
    if truncated:
        listing += (
            f"\n… corte em {_MAX_LIST_ITEMS} itens — refine `path` pra uma subpasta"
        )
    return listing


@tool
def run_command(command: str) -> str:
    """Executa um comando de shell dentro do workspace (ex: 'npm install',
    'npm run build', 'python -m pytest').

    IMPORTANTE — Windows, não bash: isto roda via `subprocess.run(...,
    shell=True)`, que no Windows chama `cmd.exe /c <command>`, não bash/sh.
    Sintaxe Unix (`||`, `2>/dev/null`, `find -name`, `cat`, `ls -la`) falha
    silenciosamente ou faz algo diferente do esperado em vez de dar erro
    claro — bug real já visto (um `find app -type f -name "*.py"` com
    `2>nul || true` devolveu "sem saída" sem processar nada). Prefira: `dir`
    /`Get-ChildItem`, `type`/`Get-Content`, `findstr`, `where`, ou rode
    PowerShell explicitamente com `powershell -Command "..."` quando
    precisar de algo que `cmd.exe` não tem (glob recursivo, pipes mais
    ricos). Cada chamada é um processo novo: nenhum `cd` anterior persiste
    entre uma tool call e a próxima — use caminhos relativos ao workspace
    ou `cd pasta && comando` numa única chamada.

    Tem timeout de 180s (dá pra instalar dependência de verdade — um
    `npm install` real chegou a levar ~2min num teste; 60s cortava isso
    no meio) e roda sempre com cwd fixo na sandbox — não é possível "cd"
    para fora dela.

    Args:
        command: comando de shell completo a executar (sintaxe cmd.exe/
            PowerShell do Windows — ver nota acima, não bash).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = result.stdout + result.stderr
        if not output:
            return f"(sem saída, código de retorno {result.returncode})"
        return output[-4000:]
    except subprocess.TimeoutExpired:
        return "ERRO: comando excedeu 180s e foi interrompido."


# `handle_tool_error = True` faz uma `ToolException` levantada dentro da
# tool (ex.: _safe_path barrando um caminho fora da sandbox) virar uma
# OBSERVAÇÃO de erro devolvida ao modelo, em vez de propagar e derrubar o
# `AgentExecutor` inteiro (ver LangChain `BaseTool.run`). Setado aqui, na
# origem — não em `agents/team.py::create_agent_with_tools` — pra valer
# pra qualquer agente que use estas tools, sem depender de quem monta o
# executor lembrar de repetir. Bug real: um `ValueError` (agora
# `ToolException`) numa `read_file` fora da sandbox derrubava a rodada
# inteira, mesmo com orçamento de iterações sobrando (achado testando
# office/server.py contra um projeto real).
for _tool in (write_file, read_file, list_dir, run_command):
    _tool.handle_tool_error = True
