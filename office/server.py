"""Escritório: interface web pra ativar o Supervisor e acompanhar o time
em tempo real — cada papel (arquiteto, dev_backend, dev_frontend,
supervisor) é desenhado como um personagem pixel-art sentado numa mesa,
que "acorda" quando é a vez dele agir.

Por que FastAPI + WebSocket, e não Streamlit (como `web_ui.py`): Streamlit
recarrega o script inteiro a cada evento, o que não dá pra animar sprites
num canvas em tempo real nem manter uma conexão persistente barata. Aqui o
back-end só faz duas coisas — rodar `agents.supervisor.run(task)` numa
thread separada (é uma chamada síncrona e bloqueante, faz chamadas reais
de API) e empurrar cada evento pro cliente assim que acontece — e o
front-end (`office/static/`) é HTML/CSS/JS puro, sem build step.

Rodar: .venv/bin/uvicorn office.server:app --reload
Depois abra http://localhost:8000 — **cada tarefa rodada faz chamadas
reais à API (custo de verdade)**, igual a `web_ui.py`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.callbacks import BaseCallbackHandler

from agents.llm import current_provider
from agents.researcher import _DEFAULT_MODEL as RESEARCHER_MODEL
from agents.researcher import research_batch, validate_batch
from agents.supervisor import run
from agents.tools import _IGNORED_DIR_NAMES, WORKSPACE
from agents.usage import USAGE_LOG_PATH

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Papéis que o Supervisor pode acionar (ver agents/schemas.py::Decision) —
# mesmo conjunto que web_ui.py usa pros avatares do chat. "pesquisador"
# fica de fora de propósito: o Supervisor nunca o aciona (Decision.next_role
# não o inclui), então ele nunca aparece nesta tela.
ROLES = ("supervisor", "arquiteto", "dev_backend", "dev_frontend")

# Cada entrada de agents.supervisor.run() começa com "[papel] ..." — ver
# docstring de `run`. Captura o papel e o resto do texto separadamente
# (web_ui.py só precisa do papel; aqui o texto também vai pro cliente).
_ENTRY_PATTERN = re.compile(r"^\[(\w+)\]\s*(.*)$", re.DOTALL)


def parse_entry(entry: str) -> dict[str, str]:
    """Quebra uma entrada de `agents.supervisor.run()` em papel/tipo/texto.

    `kind` classifica a entrada pro front-end saber como reagir:
    - "decision": o supervisor escolheu o próximo papel (texto começa com
      "próximo:") — é o sinal pra "acordar" o personagem daquele papel.
    - "info": mensagem terminal do supervisor (concluído / limite de
      rodadas) — não aciona nenhum personagem.
    - "result": resumo de um especialista que acabou de agir — é o sinal
      pra "adormecer" o personagem de volta ao idle.

    Uma entrada sem o prefixo "[papel] " (não deveria acontecer) cai como
    supervisor/info, mesma escolha conservadora de `web_ui._parse_speaker`.
    """
    match = _ENTRY_PATTERN.match(entry)
    if not match:
        return {"role": "supervisor", "kind": "info", "text": entry}

    role, text = match.group(1), match.group(2)
    if role != "supervisor":
        kind = "result"
    elif text.startswith("próximo:"):
        kind = "decision"
    else:
        kind = "info"
    return {"role": role, "kind": kind, "text": text}


def count_usage_lines(log_path: Path = USAGE_LOG_PATH) -> int:
    """Quantas linhas `usage_log.jsonl` já tem — usado como ponto de
    partida antes de rodar uma tarefa, pra só reportar uso NOVO daquela
    rodada (mesma ideia de `web_ui._total_tokens`, mas incremental em vez
    de "antes e depois")."""
    if not log_path.exists():
        return 0
    return len(log_path.read_text(encoding="utf-8").splitlines())


def read_new_usage_lines(
    after_line: int, log_path: Path = USAGE_LOG_PATH
) -> tuple[list[dict[str, Any]], int]:
    """Lê as linhas de `usage_log.jsonl` gravadas desde `after_line`.

    Uma linha malformada é ignorada (mesmo tratamento de
    `dashboard.load_usage`) — não derruba a transmissão em tempo real por
    causa de uma linha ruim.

    Returns:
        `(entradas_novas, total_de_linhas_agora)` — o segundo valor vira o
        próximo `after_line` de quem chama, pra não reler o que já leu.
    """
    if not log_path.exists():
        return [], after_line

    lines = log_path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines[after_line:]:
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Linha inválida em usage_log.jsonl durante streaming, ignorada")
    return entries, len(lines)


def list_projects(workspace: Path = WORKSPACE) -> list[str]:
    """Subpastas de 1º nível do workspace — vira as opções do seletor de
    projeto na tela. Reusa a mesma lista de pastas ruidosas de
    `agents.tools.list_dir` (node_modules, .venv, .git, ...) — não faz
    sentido oferecer `.git` como "projeto" pra escolher.
    """
    if not workspace.exists():
        return []
    return sorted(
        p.name for p in workspace.iterdir()
        if p.is_dir() and p.name not in _IGNORED_DIR_NAMES and not p.name.startswith(".")
    )


def build_task_with_project_context(task: str, project: str | None) -> str:
    """Prefixa a tarefa com qual projeto é o alvo, quando o usuário escolhe
    um no seletor — poupa o agente de descobrir isso sozinho explorando o
    workspace inteiro a cada rodada (achado real: sem isso, a primeira
    ação de todo `dev_backend` era um `list_dir`/`run_command` de
    reconhecimento, gastando uma rodada inteira só pra achar o projeto).

    É um HINT forte no prompt, não uma restrição técnica nova — o sandbox
    (`agents/tools.py::WORKSPACE`) continua sendo o workspace inteiro; o
    agente ainda PODE tocar outro projeto se a tarefa genuinamente pedir
    (ex.: "compare com o schema do PsiEasy-API").
    """
    if not project:
        return task
    return (
        f"Projeto-alvo desta tarefa: `{project}/` (caminho relativo ao "
        f"workspace). Comece explorando `{project}/` — para `run_command`, "
        f"inicie com `cd {project} && ...` numa única chamada (o diretório "
        "não persiste entre chamadas). Só saia desse projeto se a tarefa "
        "pedir explicitamente comparar ou integrar com outro.\n\n"
        f"{task}"
    )


# Pasta do backend do Acervo Católico dentro do workspace ativo — mesmo
# projeto que `projects/research_concilios.py` apontava por um caminho fixo
# (hoje obsoleto: o projeto foi movido). Resolvido contra WORKSPACE, que já
# cobre todos os projetos reais (ver DEV_AGENT_WORKSPACE em agents/tools.py),
# em vez de repetir esse mesmo erro de caminho fixo aqui.
_ACERVO_BACKEND_DIRNAME = "Acervo-Cat-lico-API"


def _acervo_data_dir() -> Path:
    return WORKSPACE / _ACERVO_BACKEND_DIRNAME / "app" / "data"


def _load_acervo_models() -> tuple[Any, dict[Any, type]]:
    """Importa `Category`/`ENTRY_MODEL_BY_CATEGORY` do backend do acervo —
    a mesma fonte única de verdade que `agents/researcher.py` já usa pra
    validar (nunca duplicada aqui). Import tardio (não no topo do módulo):
    o backend só existe se `WORKSPACE` apontar pra ele, e isso só é sabido
    em runtime (ver `agents/tools.py::_resolve_workspace`).

    Raises:
        FileNotFoundError: backend não está no workspace ativo.
    """
    backend_path = WORKSPACE / _ACERVO_BACKEND_DIRNAME
    if not backend_path.exists():
        raise FileNotFoundError(
            f"Backend do acervo não encontrado em {backend_path} — "
            "confira se DEV_AGENT_WORKSPACE cobre esse projeto."
        )
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from app.models import ENTRY_MODEL_BY_CATEGORY, Category  # type: ignore[import-not-found]

    return Category, ENTRY_MODEL_BY_CATEGORY


def _load_existing_slugs(categoria: str) -> set[str]:
    path = _acervo_data_dir() / f"{categoria}.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["slug"] for item in data.get("itens", [])}


def _write_entries(categoria: str, entries: list[Any]) -> None:
    """Grava (append) as entradas validadas no arquivo de dados real —
    mesmo padrão de `projects/research_concilios.py::_write_entries`."""
    if not entries:
        return
    path = _acervo_data_dir() / f"{categoria}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["itens"].extend(entry.model_dump(mode="json") for entry in entries)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Mesmo prefixo/convenção de agents/usage.py::_extract_role — os papéis com
# tools são tagueados com "role:<papel>" (ver agents/team.py::
# create_agent_with_tools), e essa tag se propaga pras callbacks de CADA
# tool call individual dentro do AgentExecutor, não só na chamada ao modelo.
_ROLE_TAG_PREFIX = "role:"


def _extract_role_from_tags(tags: list[str] | None) -> str:
    for tag in tags or []:
        if tag.startswith(_ROLE_TAG_PREFIX):
            return tag[len(_ROLE_TAG_PREFIX):]
    return "desconhecido"


class _ActivityCallbackHandler(BaseCallbackHandler):
    """Ponte pra transmitir cada tool call individual em tempo real.

    Sem isso, o cliente só vê o resumo final de um papel (um evento por
    especialista, ver `parse_entry`) — mesmo que ele faça dezenas de
    chamadas reais de tool por baixo. Numa auditoria longa (`run_command`
    repetido: pytest, ruff, mypy, leitura de vários arquivos), isso fazia a
    tela ficar muda por minutos, parecendo travada (achado real, testando
    o escritório contra um projeto de verdade fora do sandbox).

    Cada instância é de UMA execução (`_stream_run` cria uma nova por
    tarefa rodada) — não é compartilhada feito `agents.usage.usage_handler`,
    porque só faz sentido durante a conexão WebSocket que a criou.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        self._loop = loop
        self._queue = queue

    def _emit(self, role: str, text: str) -> None:
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait, ("activity", {"role": role, "text": text})
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        role = _extract_role_from_tags(tags)
        name = (serialized or {}).get("name", "tool")
        self._emit(role, f"→ {name}({input_str[:200]})")

    def on_tool_end(self, output: Any, *, tags: list[str] | None = None, **kwargs: Any) -> None:
        role = _extract_role_from_tags(tags)
        self._emit(role, f"  {str(output)[:300]}")

    def on_tool_error(
        self, error: BaseException, *, tags: list[str] | None = None, **kwargs: Any
    ) -> None:
        role = _extract_role_from_tags(tags)
        self._emit(role, f"⚠ erro na tool: {error}")


app = FastAPI(title="dev-agent — Escritório")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/config")
async def config() -> dict[str, str]:
    """Provedor e pasta que `dev_backend`/`dev_frontend` podem tocar nesta
    sessão — exibido no front-end pra nunca ficar implícito.

    `WORKSPACE` é lido uma única vez, na importação de `agents/tools.py`
    (ver o docstring de lá) — pra apontar o escritório pra um projeto real
    em vez do `workspace/` descartável, defina `DEV_AGENT_WORKSPACE` ANTES
    de subir o servidor: `DEV_AGENT_WORKSPACE=/caminho/do/projeto
    uvicorn office.server:app`. Não dá pra trocar no meio de uma execução
    (proposital: a sandbox nunca muda durante uma tarefa rodando).
    """
    return {"provider": current_provider(), "workspace": str(WORKSPACE)}


@app.get("/projects")
async def projects() -> dict[str, list[str]]:
    """Pastas de projeto disponíveis no workspace ativo — alimenta o
    seletor de projeto da tela (ver `build_task_with_project_context`)."""
    return {"projects": list_projects()}


@app.get("/research/categories")
async def research_categories() -> dict[str, list[str]]:
    """Categorias do acervo disponíveis pro pesquisador — alimenta o
    seletor de categoria do painel de pesquisa. Lista vazia (não erro) se o
    backend do acervo não estiver no workspace ativo — o front-end trata
    isso escondendo o painel, não travando a página inteira."""
    try:
        category_enum, _ = _load_acervo_models()
    except FileNotFoundError:
        return {"categories": []}
    return {"categories": sorted(c.value for c in category_enum)}


async def _stream_run(websocket: WebSocket, task: str) -> None:
    """Roda `agents.supervisor.run(task)` numa thread (é síncrono e faz
    chamadas de API reais, bloqueantes) e envia cada evento pro cliente
    assim que acontece, via uma fila ponte entre a thread e o event loop.

    Três tipos de evento saem dessa fila: "entry" (uma entrada de
    `run()` — decisão do supervisor ou resumo final de um especialista),
    "activity" (uma tool call individual dentro de um `AgentExecutor`, via
    `_ActivityCallbackHandler` — é o que dá visibilidade DURANTE um papel
    longo, não só no fim) e "error"/"done" (fim da execução). Depois de
    cada uma, também checa se `usage_log.jsonl` ganhou linhas novas e as
    envia como eventos de uso.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    usage_offset = count_usage_lines()
    run_total_tokens = 0
    activity_callback = _ActivityCallbackHandler(loop, queue)

    def worker() -> None:
        try:
            for entry in run(task, extra_callbacks=[activity_callback]):
                loop.call_soon_threadsafe(queue.put_nowait, ("entry", entry))
        except Exception as exc:  # erro real de API/rede — reportado, não engolido
            logger.exception("Falha ao rodar o time no escritório")
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    threading.Thread(target=worker, daemon=True).start()

    while True:
        kind, payload = await queue.get()

        if kind == "error":
            await websocket.send_json({"type": "error", "message": payload})
            break
        if kind == "done":
            break
        if kind == "activity":
            await websocket.send_json({"type": "activity", **payload})
            continue

        await websocket.send_json({"type": "event", **parse_entry(payload)})

        new_usage, usage_offset = read_new_usage_lines(usage_offset)
        for usage_entry in new_usage:
            run_total_tokens += usage_entry.get("total_tokens", 0)
            await websocket.send_json({
                "type": "usage",
                "role": usage_entry.get("role", "desconhecido"),
                "total_tokens": usage_entry.get("total_tokens", 0),
                "run_total_tokens": run_total_tokens,
            })

    await websocket.send_json({"type": "done", "run_total_tokens": run_total_tokens})


async def _stream_research(websocket: WebSocket, categoria: str, task: str) -> None:
    """Roda `research_batch` + `validate_batch` (síncronos, bloqueantes,
    `research_batch` faz busca web real) numa thread, igual `_stream_run` —
    mas é um fluxo diferente do time: uma categoria + um schema Pydantic
    real do backend, sem `AgentExecutor`, sem Decision do Supervisor (o
    pesquisador nunca é acionado por ali, ver docstring de `ROLES`).

    Grava as entradas validadas direto no arquivo de dados real do acervo
    (`_write_entries`) — mesmo comportamento de
    `projects/research_concilios.py`, mesma rede de segurança (revisar o
    diff antes de commitar), não uma trava de confirmação extra aqui.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    usage_offset = count_usage_lines()
    run_total_tokens = 0

    def worker() -> None:
        try:
            category_enum, entry_model_by_category = _load_acervo_models()
            item_model = entry_model_by_category[category_enum(categoria)]

            loop.call_soon_threadsafe(
                queue.put_nowait, ("status", "Pesquisando (busca web real)…")
            )
            raw_items = research_batch(task, item_model, model=RESEARCHER_MODEL)

            status_text = (
                f"{len(raw_items)} item(ns) proposto(s) — validando contra o schema real…"
            )
            loop.call_soon_threadsafe(queue.put_nowait, ("status", status_text))
            existing_slugs = _load_existing_slugs(categoria)
            valid, warnings = validate_batch(
                raw_items, item_model, existing_slugs, model=RESEARCHER_MODEL
            )
            for warning in warnings:
                loop.call_soon_threadsafe(queue.put_nowait, ("warning", warning))

            _write_entries(categoria, valid)
            result_payload = {
                "categoria": categoria,
                "proposed": len(raw_items),
                "valid": len(valid),
            }
            loop.call_soon_threadsafe(queue.put_nowait, ("result", result_payload))
        except Exception as exc:  # erro real (API, rede, KeyError de categoria) — reportado
            logger.exception("Falha ao rodar o pesquisador no escritório")
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    threading.Thread(target=worker, daemon=True).start()

    while True:
        kind, payload = await queue.get()

        if kind == "error":
            await websocket.send_json({"type": "error", "message": payload})
            break
        if kind == "done":
            break
        if kind == "status":
            await websocket.send_json({"type": "research_status", "text": payload})
        elif kind == "warning":
            await websocket.send_json({"type": "research_warning", "text": payload})
        elif kind == "result":
            await websocket.send_json({"type": "research_result", **payload})

        # research_batch/validate_batch já registram uso em usage_log.jsonl
        # (role "pesquisador", ver agents/researcher.py) — mesmo streaming
        # incremental de `_stream_run`, pro painel de tokens atualizar ao
        # vivo aqui também.
        new_usage, usage_offset = read_new_usage_lines(usage_offset)
        for usage_entry in new_usage:
            run_total_tokens += usage_entry.get("total_tokens", 0)
            await websocket.send_json({
                "type": "usage",
                "role": usage_entry.get("role", "desconhecido"),
                "total_tokens": usage_entry.get("total_tokens", 0),
                "run_total_tokens": run_total_tokens,
            })

    await websocket.send_json({"type": "done", "run_total_tokens": run_total_tokens})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    running = False
    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            if action not in ("run", "research"):
                continue
            if running:
                await websocket.send_json({
                    "type": "error", "message": "Já tem uma tarefa rodando."
                })
                continue

            running = True
            await websocket.send_json({"type": "status", "running": True})
            try:
                if action == "run":
                    task = (message.get("task") or "").strip()
                    if not task:
                        await websocket.send_json({"type": "error", "message": "Tarefa vazia."})
                        continue
                    task = build_task_with_project_context(task, message.get("project"))
                    await _stream_run(websocket, task)
                else:
                    categoria = (message.get("categoria") or "").strip()
                    task = (message.get("task") or "").strip()
                    if not categoria or not task:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Escolha uma categoria e descreva o que pesquisar.",
                        })
                        continue
                    await _stream_research(websocket, categoria, task)
            finally:
                running = False
                await websocket.send_json({"type": "status", "running": False})
    except WebSocketDisconnect:
        logger.info("Cliente do escritório desconectou.")
