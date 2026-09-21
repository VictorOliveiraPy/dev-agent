"""Fixtures compartilhadas por toda a suíte.

`LLM_PROVIDER` é lido do ambiente em runtime, sem cache (ver
`agents.llm.current_provider`) — então o valor real do `.env` de quem está
rodando (ex.: `LLM_PROVIDER=deepseek`, configurado pra testar o time de
verdade contra outro provedor) vazaria pros testes e mudaria comportamento
esperado (ex.: `_ROLE_MODELS` do arquiteto em `agents/team.py`) dependendo
de quem roda a suíte. Bug real: apareceu depois de configurar
`LLM_PROVIDER=deepseek` no `.env` local pra testar `office/server.py`.

`autouse=True` limpa isso pra TODO teste, sem precisar lembrar de repetir
a mesma linha em cada arquivo novo nem antecipar quais vão precisar.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_llm_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
