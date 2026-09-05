# dev-agent

[![CI](https://github.com/VictorOliveiraPy/dev-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/VictorOliveiraPy/dev-agent/actions/workflows/ci.yml)

Time de agentes de IA construído com LangChain + Claude, capaz de projetar e
implementar projetos (Python + React) de ponta a ponta — arquitetura,
backend, frontend — sozinho ou orquestrado por um Supervisor.

## Papéis do time

- **arquiteto** — decide stack e contrato entre backend/frontend (sem tools).
- **dev_backend** — implementa a API (FastAPI), com ferramentas reais de
  escrita de arquivo (`agents/tools.py`, sandboxed em `workspace/`).
- **dev_frontend** — implementa a UI (React), lendo o contrato real do
  backend antes de codar.
- **supervisor** (`agents/supervisor.py`) — decide sozinho qual
  especialista aciona e quando, via saída estruturada.

## Padrões de código

Cada papel carrega automaticamente os padrões de `standards/*.md` na própria
persona (`agents/team.py::_build_persona`) — edite esses arquivos
livremente, nenhum código Python precisa mudar. Ver `standards/general.md`
(regras gerais), `standards/design.md` (UX/identidade visual — evita a
"cara de feito por IA", destilado da skill `artifact-design`) e
`standards/backend.md` (destilado de dois backends FastAPI
reais em produção).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # preencha ANTHROPIC_API_KEY
```

### Provedor de modelo: Claude (API) ou Ollama (local)

Por padrão o time inteiro usa a API da Anthropic (`ANTHROPIC_API_KEY` no
`.env`). Para rodar em cima de um Ollama local em vez disso — sem custo por
token, útil para testar sem gastar API —, suba o container e troque
`LLM_PROVIDER` no `.env`:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull llama3.1   # baixa o modelo, uma vez
```

```bash
# .env
LLM_PROVIDER=ollama
```

Ver `agents/llm.py::build_chat_model` para os detalhes (inclui como forçar
um provedor específico independente do `.env`). O papel `pesquisador`
sempre usa Anthropic, mesmo com `LLM_PROVIDER=ollama` — ele depende da tool
server-side `web_search`, exclusiva da API da Anthropic.

## Rodar

```bash
.venv/bin/python main.py                # Passo 1: personas sem tools
.venv/bin/python dev_backend_agent.py   # Passo 2: dev_backend com tools
.venv/bin/python dev_frontend_agent.py  # Passo 3: dev_frontend com tools
.venv/bin/python team_supervisor.py     # Passo 4: supervisor orquestrando o time
.venv/bin/python refactor_team.py       # auditoria (só leitura) do próprio código do time
```

## Custos — dashboard de uso de tokens

Toda chamada real ao modelo feita via `agents/team.py` (`create_agent` /
`create_agent_with_tools`) é registrada automaticamente em
`usage_log.jsonl` (gitignored), com o papel responsável, tokens de entrada/
saída e timestamp — ver `agents/usage.py`.

```bash
.venv/bin/streamlit run dashboard.py
```

Mostra total de chamadas, tokens por agente e ao longo do tempo, e as
últimas chamadas. Antes da primeira execução real, a página só mostra um
aviso de "nenhum uso registrado ainda" — é esperado.

## Qualidade

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
```

Ver [PROGRESS.md](PROGRESS.md) para o estado atual do projeto e os próximos
passos, e [ARCHITECTURE.md](ARCHITECTURE.md) para as decisões estruturais
e o motivo de cada uma.
