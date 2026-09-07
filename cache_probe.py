"""Sonda de diagnóstico: o prompt caching está funcionando de verdade no
caminho do AgentExecutor (`create_agent_with_tools`)?

Contexto real (ver PROGRESS.md, sessão 2026-09-06): análise de
usage_log.jsonl mostrou cache_read/cache_creation em ZERO, em toda chamada,
pros papéis dev_backend e dev_frontend (ambos via `create_agent_with_tools`)
— enquanto o pesquisador (que NÃO usa AgentExecutor) tem cache saudável.
Verificado sem gastar API que a marcação `cache_control` sai correta na
requisição — o que sobra pra confirmar só dá pra ver com uma chamada real.

O QUE ESTE SCRIPT FAZ: manda a MESMA tarefa (bem pequena, uma escrita de
arquivo só) duas vezes seguidas pro dev_backend, e imprime os 4 contadores
de uso de cada chamada real feita nas duas rodadas. Se o cache estiver
saudável, alguma chamada da SEGUNDA rodada deve mostrar cache_read > 0
(reaproveitando o system prompt da primeira rodada, idêntico).

CUSTO REAL: isso gasta API de verdade (poucas chamadas pequenas — a tarefa
foi desenhada pra ser a mais barata possível, mas não é grátis). Só rode
com saldo na conta. Escreve em workspace/ (sandbox descartável padrão,
nunca no projeto real) — seguro rodar quantas vezes quiser.
"""

import json
import sys
from pathlib import Path

from agents.team import create_agent_with_tools
from agents.tools import write_file
from agents.usage import USAGE_LOG_PATH

# Tarefa mínima de propósito: uma escrita de arquivo só, sem exploração,
# pra manter o número de chamadas ao modelo (e o custo) o mais baixo e
# previsível possível.
_TASK = (
    "Use a tool write_file para criar cache_probe_output.txt com o "
    "conteúdo exato 'sonda de cache'. Não leia nenhum arquivo, não rode "
    "nenhum comando, não faça mais nada além dessa escrita."
)


def _tail_new_entries(path: Path, lines_before: int) -> list[dict]:
    """Lê só as linhas de usage_log.jsonl escritas DEPOIS de `lines_before`."""
    all_lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in all_lines[lines_before:] if line.strip()]


def run_probe() -> bool:
    """Roda a tarefa duas vezes e imprime os contadores de uso de cada
    chamada real feita. Devolve True se ALGUMA chamada da 2a rodada teve
    cache_read > 0 (cache saudável) — False caso contrário.
    """
    lines_before = 0
    if USAGE_LOG_PATH.exists():
        lines_before = len(USAGE_LOG_PATH.read_text(encoding="utf-8").splitlines())

    print("=== 1a chamada ===")
    agent = create_agent_with_tools("dev_backend", [write_file])
    agent.invoke({"task": _TASK})
    entries_1 = _tail_new_entries(USAGE_LOG_PATH, lines_before)
    for e in entries_1:
        print(_format_entry(e))

    print("\n=== 2a chamada (mesma tarefa, deveria reaproveitar o cache) ===")
    agent = create_agent_with_tools("dev_backend", [write_file])
    agent.invoke({"task": _TASK})
    entries_2 = _tail_new_entries(USAGE_LOG_PATH, lines_before + len(entries_1))
    for e in entries_2:
        print(_format_entry(e))

    cache_healthy = any((e.get("cache_read_tokens") or 0) > 0 for e in entries_2)
    print(f"\nVeredito: cache {'SAUDÁVEL' if cache_healthy else 'QUEBRADO'} "
          f"no caminho do AgentExecutor.")
    return cache_healthy


def _format_entry(entry: dict) -> str:
    return (
        f"  input={entry['input_tokens']:>6}  output={entry['output_tokens']:>5}  "
        f"cache_read={entry.get('cache_read_tokens', 0):>5}  "
        f"cache_creation={entry.get('cache_creation_tokens', 0):>5}"
    )


if __name__ == "__main__":
    healthy = run_probe()
    sys.exit(0 if healthy else 1)
