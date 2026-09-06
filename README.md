# dev-agent

[![CI](https://github.com/VictorOliveiraPy/dev-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/VictorOliveiraPy/dev-agent/actions/workflows/ci.yml)

Time de agentes de IA construído com LangChain + Claude, capaz de projetar e
implementar projetos (Python + React) de ponta a ponta — arquitetura,
backend, frontend — sozinho ou orquestrado por um Supervisor.

## Papéis do time

- **arquiteto** — decide stack e contrato entre backend/frontend (sem
  tools). Usa Claude Haiku 4.5 (mais barato) — ver "Custo" abaixo.
- **dev_backend** — implementa a API (FastAPI), com ferramentas reais de
  escrita de arquivo (`agents/tools.py`, sandboxed em `workspace/`).
- **dev_frontend** — implementa a UI (React), lendo o contrato real do
  backend antes de codar.
- **pesquisador** (`agents/researcher.py`) — propõe conteúdo novo via
  `web_search` nativo da Anthropic, valida cada item contra o schema real
  do backend antes de virar arquivo (nunca confia no que o modelo afirma
  ter encontrado).
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

### Custo: modelo mais barato para o papel de rascunho/opinião

O `arquiteto` (só opina em texto, sem tools) usa **Claude Haiku 4.5** por
padrão — o modelo mais barato da Anthropic ($1/$5 por milhão de tokens de
entrada/saída, contra $5/$25 do Opus 5). `dev_backend`/`dev_frontend`
continuam em Opus 5: escrevem arquivo de verdade via tool calling, e um
modelo mais fraco aí arrisca código pior ou tool call malformada — custa
mais em retrabalho do que economiza em tokens. Ver `_ROLE_MODELS` em
`agents/team.py`, e ARCHITECTURE.md pra outras arquiteturas de custo já
tentadas e descartadas (Ollama local, OpenRouter) — nenhuma delas se
provou confiável o bastante pros papéis que escrevem código de verdade.

## Rodar

```bash
.venv/bin/python main.py                # Passo 1: personas sem tools
.venv/bin/python dev_backend_agent.py   # Passo 2: dev_backend com tools
.venv/bin/python dev_frontend_agent.py  # Passo 3: dev_frontend com tools
.venv/bin/python team_supervisor.py     # Passo 4: supervisor orquestrando o time
.venv/bin/python refactor_team.py       # auditoria (só leitura) do próprio código do time
```

`projects/` guarda os scripts que já dispararam o time em cima de um
projeto real específico (fe-catolica, repasse-api, ...) — cada um aponta
`DEV_AGENT_WORKSPACE` pro repositório de destino antes de importar
`agents` (ver o docstring de qualquer um deles). Não são parte do
framework reutilizável; são o HISTÓRICO de uso dele. Rode sempre como
módulo, da raiz do repo (não pelo caminho do arquivo direto — `agents`
não resolveria):

```bash
.venv/bin/python -m projects.build_fe_catolica
```

## Interface web — rodar o time e acompanhar a conversa ao vivo

```bash
.venv/bin/streamlit run web_ui.py
```

Um formulário (com exemplos prontos na barra lateral) pra digitar a tarefa
e um botão "▶️ Rodar" — a partir daí a "conversa" do time aparece ao vivo,
uma bolha de chat por evento: a decisão do supervisor (qual papel aciona e
por quê) seguida do resultado de cada especialista, na ordem em que
acontecem (`agents/supervisor.py::run` é um gerador — ver docstring). Ao
final, mostra quantos tokens aquela rodada específica gastou (comparando
`usage_log.jsonl` antes/depois). **Cada rodada faz chamadas reais à API —
custo de verdade**, não uma simulação.

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
