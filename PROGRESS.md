# Progresso — sessões de 2026-09-02 e 2026-09-03

## Onde paramos

O time de tecnologia (LangChain + Claude) está montado e validado
ponta a ponta: **Fundação → especialista com tools → segundo especialista
→ Supervisor → padrões de código próprios → refatoração pro estilo real
→ rastreamento de custos + dashboard → padronização com Pydantic**. O
repo já está no GitHub
(`VictorOliveiraPy/dev-agent`), e a conta da Anthropic ficou sem crédito
no meio do dia 02 — por isso o dia 03 foi todo em coisas que não custam
API (correção de imprecisões técnicas, rastreamento de uso, dashboard).

## O que já funciona (testado de verdade, rodando)

- **`agentes/llm.py`** — fábrica única do `ChatAnthropic` (`claude-opus-5`,
  `max_tokens` explícito — evita respostas cortadas no meio de tool calls).
- **`agentes/team.py`** — personas do time (`ROLES`) + composição automática
  com `padroes/*.md` (`_build_persona`). Testado que monta certo, inclusive
  o escape de chaves literais (bug real que já apareceu e foi corrigido).
- **`agentes/tools.py`** — `write_file`/`read_file`/`list_dir`/`run_command`
  sandboxed em `workspace/` (path traversal bloqueado, testado).
- **`agentes/project_tools.py`** — mesma ideia, mas sandboxed na raiz do
  projeto real, com bloqueio explícito de `.env`/`.git`/`.venv`/`workspace`
  (pra auto-manutenção do próprio time). Testado.
- **`agentes/supervisor.py`** — roteador com saída estruturada (`Decision`)
  que decide qual papel age a cada rodada. Rodou ponta a ponta uma vez
  (antes da rigorização dos padrões) e escolheu certinho:
  `arquiteto → dev_backend → dev_frontend → concluido`.
- **Passos 2 e 3** (`dev_backend_agent.py`, `dev_frontend_agent.py`) já
  produziram, em teste, um backend de login completo (FastAPI, hash com
  `hashlib`, testes próprios, pytest passando) e um frontend React
  (Vite, `AuthContext`, telas de login/registro) que leu o backend real
  antes de codar e detectou sozinho uma lacuna de CORS.
- **`padroes/general.md` + `padroes/backend.md`** — destilados de dois
  repos reais em produção (`melhorperfil-api`, `santo-guardiao-api`):
  arquitetura em camadas, config com `pydantic-settings`, exceções
  tipadas, checklist de segurança (IDOR, JWT, fail-closed), logging
  estruturado, convenção de teste `test_should_{o_que}_when_{causa}`.
  Traduzidos pro inglês hoje, com tabelas/exemplos ✅/❌.
- **Refatoração do próprio código do time** pro padrão rigoroso — feita
  manualmente (a tentativa via agente esbarrou em falta de crédito de API,
  ver "Gotchas" abaixo): identificadores em inglês, docstrings/comentários
  em português, logging estruturado no supervisor, `pyproject.toml`
  (ruff + pytest), 12 testes novos (`tests/`) cobrindo lógica pura
  (montagem de persona, sandbox de caminho). `ruff check .` limpo,
  `pytest -q` passando.
- **`agentes/usage.py`** — `UsageCallbackHandler` grava cada chamada real
  ao modelo em `usage_log.jsonl` (papel, tokens de entrada/saída, modelo,
  timestamp), lendo o `usage_metadata` nativo do `langchain_anthropic`
  (NÃO o `get_openai_callback`, que é específico da OpenAI e nem está
  instalado no projeto — ver "Gotchas"). Já conectado em
  `agentes/team.py` (`create_agent`/`create_agent_with_tools` via
  `.with_config(callbacks=..., tags=["role:<papel>"])`) — todo agente já
  registra uso automaticamente, sem precisar mudar nenhum script de
  entrada. Testado de ponta a ponta com um chat model falso (sem custo de
  API) provando que o callback dispara de verdade.
- **`dashboard.py`** — app Streamlit que lê `usage_log.jsonl` e mostra
  total de chamadas, tokens por agente, tokens ao longo do tempo e as
  últimas chamadas. Testado: sobe (`streamlit run`, HTTP 200 confirmado)
  e a função de leitura (`load_usage`) tem testes próprios. Rodar com
  `.venv/bin/streamlit run dashboard.py`.
- **`agentes/schemas.py`** — lugar único pros modelos Pydantic
  compartilhados: `Decision` (movido de dentro de `supervisor.py`),
  `UsageEntry` (agora é o schema de verdade do `usage_log.jsonl`, validado
  tanto na escrita quanto na leitura pelo dashboard) e `ArchitecturePlan` +
  `PlannedFile` (novo). O papel `arquiteto`, quando acionado pelo
  Supervisor, agora devolve um `ArchitecturePlan` estruturado
  (`create_agent(role, output_schema=...)`, parâmetro novo) em vez de
  prosa livre truncada — o resumo que vai pro histórico do Supervisor é
  montado a partir dos campos do modelo. Testado (validação dos 4
  modelos + wiring de ponta a ponta do `usage_log.jsonl`); a saída
  estruturada do arquiteto em si só é exercitada de verdade com crédito.

## Pendências / próximos passos possíveis

1. **Rodar `team_supervisor.py` de novo** — a última execução ponta a
   ponta foi ANTES da rigorização de `padroes/backend.md` E antes da
   saída estruturada do arquiteto. Vale ver: (a) se o código gerado
   reflete IDOR-safe queries, exceções tipadas etc.; (b) se o
   `ArchitecturePlan` vem preenchido direito; (c) vai ser a primeira
   execução real aparecendo no dashboard.
2. **Rodar `refactor_team.py`** (virou uma auditoria só-leitura) pra ver
   o próprio `dev_backend` conferir se a refatoração manual de hoje ficou
   aderente aos padrões, do ponto de vista dele.
3. **Decidir um projeto real** pra equipe construir — até agora só pedidos
   de teste genéricos (login, lista de favoritos). Ficou em aberto
   propositalmente ("vou decidir na hora").
4. **`padroes/frontend.md` ainda é só baseline**, não foi auditado contra
   um frontend real em produção (dá pra fazer o mesmo processo que foi
   feito com o backend, usando `melhorperfil-web` como fonte).
5. **Memória entre execuções** e **RAG sob demanda** (papéis lendo docs
   via tool em vez de tudo empilhado na persona) — ficaram cogitados no
   roteiro original e nunca foram construídos. `trim_messages` (LangChain,
   ainda válido/atual) é o candidato certo pro dia que isso for construído
   — as classes antigas de `langchain.memory` (`ConversationBufferWindowMemory`
   e primas) estão deprecadas desde 0.3.1, removal na 1.0.0.
6. **Renomear os diretórios** `agentes/`, `padroes/`, `workspace/` pro
   inglês — decisão adiada de propósito (mudança mais estrutural/arriscada
   que renomear só identificadores de código).
7. **CI** — agora que `ruff`/`pytest` estão configurados, dá pra subir um
   GitHub Actions rodando os dois a cada push.
8. **Dashboard só mostra o que já aconteceu.** Se um dia fizer sentido
   acompanhar em tempo real durante uma execução longa (ex: o Supervisor
   rodando várias rodadas), dá pra explorar `st.rerun`/auto-refresh — hoje
   é preciso atualizar a página manualmente.

## Gotchas importantes (não repetir)

- **`ChatAnthropic` sem `max_tokens` explícito corta respostas com
  thinking + várias tool calls no meio do JSON.** Sempre passe
  `max_tokens` (ver `agentes/llm.py`).
- **`ChatPromptTemplate` trata a string do "system" como f-string** —
  chaves literais de exemplo de código (ex: `extra={"user_id": user.id}`)
  quebram a montagem do prompt se não forem escapadas (`_build_persona` já
  faz isso).
- **A conta da Anthropic ficou sem crédito de API** no meio da sessão —
  se `team_supervisor.py`/`refactor_team.py` falharem com
  `credit balance is too low`, é isso: recarregar em
  console.anthropic.com → Plans & Billing.
- **`run_command`/`run_project_command` rodam com o PATH do shell, não
  necessariamente o `.venv` do projeto** — sempre invocar como
  `.venv/bin/python -m <ferramenta>`, nunca confiar em `ruff`/`pytest`
  soltos.
- **`get_openai_callback` (langchain_community) não serve pra rastrear
  uso do Claude** — é específico do formato de resposta da OpenAI, e o
  `langchain_community` nem é dependência do projeto. O jeito certo é o
  `usage_metadata` nativo do `langchain_anthropic` (ver `agentes/usage.py`).
- **`ConversationBufferWindowMemory`, `ConversationSummaryMemory` e
  `ConversationSummaryBufferMemory` (`langchain.memory`) estão
  deprecadas** desde a 0.3.1 (removal na 1.0.0) — não usar em código
  novo. O guia de migração do LangChain aponta pro padrão LCEL nativo
  (`trim_messages` + histórico gerenciado à mão).
