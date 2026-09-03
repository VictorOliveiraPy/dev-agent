# Progresso — sessões de 2026-09-02 e 2026-09-03

## Onde paramos

O time de tecnologia (LangChain + Claude) está montado e validado
ponta a ponta: **Fundação → especialista com tools → segundo especialista
→ Supervisor → padrões de código próprios → refatoração pro estilo real
→ rastreamento de custos + dashboard → padronização com Pydantic →
diretórios em inglês + CI + padrão de frontend real → padrão de design/UX**.
O repo já está no GitHub (`VictorOliveiraPy/dev-agent`), e a conta da
Anthropic ficou sem crédito no meio do dia 02 — por isso o dia 03 foi todo
em coisas que não custam API (correção de imprecisões técnicas,
rastreamento de uso, dashboard, Pydantic, renomeação de diretórios, CI,
auditoria de frontend, padrão de design/UX).

## O que já funciona (testado de verdade, rodando)

- **`agents/llm.py`** — fábrica única do `ChatAnthropic` (`claude-opus-5`,
  `max_tokens` explícito — evita respostas cortadas no meio de tool calls).
- **`agents/team.py`** — personas do time (`ROLES`) + composição automática
  com `standards/*.md` (`_build_persona`). Testado que monta certo, inclusive
  o escape de chaves literais (bug real que já apareceu e foi corrigido).
- **`agents/tools.py`** — `write_file`/`read_file`/`list_dir`/`run_command`
  sandboxed em `workspace/` (path traversal bloqueado, testado).
- **`agents/project_tools.py`** — mesma ideia, mas sandboxed na raiz do
  projeto real, com bloqueio explícito de `.env`/`.git`/`.venv`/`workspace`
  (pra auto-manutenção do próprio time). Testado.
- **`agents/supervisor.py`** — roteador com saída estruturada (`Decision`)
  que decide qual papel age a cada rodada. Rodou ponta a ponta uma vez
  (antes da rigorização dos padrões) e escolheu certinho:
  `arquiteto → dev_backend → dev_frontend → concluido`.
- **Passos 2 e 3** (`dev_backend_agent.py`, `dev_frontend_agent.py`) já
  produziram, em teste, um backend de login completo (FastAPI, hash com
  `hashlib`, testes próprios, pytest passando) e um frontend React (Vite,
  `AuthContext`, telas de login/registro) que leu o backend real antes de
  codar e detectou sozinho uma lacuna de CORS. **Atenção:** essa execução
  foi ANTES da troca de stack pra Next.js (ver abaixo) — o resultado em
  `workspace/frontend` é Vite, desatualizado em relação ao padrão atual.
- **`standards/general.md` + `standards/backend.md`** — destilados de dois
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
- **`agents/usage.py`** — `UsageCallbackHandler` grava cada chamada real
  ao modelo em `usage_log.jsonl` (papel, tokens de entrada/saída, modelo,
  timestamp), lendo o `usage_metadata` nativo do `langchain_anthropic`
  (NÃO o `get_openai_callback`, que é específico da OpenAI e nem está
  instalado no projeto — ver "Gotchas"). Já conectado em
  `agents/team.py` (`create_agent`/`create_agent_with_tools` via
  `.with_config(callbacks=..., tags=["role:<papel>"])`) — todo agente já
  registra uso automaticamente, sem precisar mudar nenhum script de
  entrada. Testado de ponta a ponta com um chat model falso (sem custo de
  API) provando que o callback dispara de verdade.
- **`dashboard.py`** — app Streamlit que lê `usage_log.jsonl` e mostra
  total de chamadas, tokens por agente, tokens ao longo do tempo e as
  últimas chamadas. Testado: sobe (`streamlit run`, HTTP 200 confirmado)
  e a função de leitura (`load_usage`) tem testes próprios. Rodar com
  `.venv/bin/streamlit run dashboard.py`.
- **`agents/schemas.py`** — lugar único pros modelos Pydantic
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
- **Diretórios renomeados pro inglês**: `agentes/` → `agents/`,
  `padroes/` → `standards/`. `workspace/` não mudou (já era inglês). Só
  paths/imports foram alterados — o uso da palavra "agentes" como prosa
  em português (docstrings/comentários) foi preservado de propósito.
  Testado (22 testes, ruff limpo, smoke test estrutural).
- **CI** (`.github/workflows/ci.yml`) — GitHub Actions rodando
  `ruff check .` e `pytest -q` a cada push/PR pra `main`. Confirmei
  localmente que a suíte inteira passa sem `ANTHROPIC_API_KEY` nem
  `.env` no ambiente (todos os testes usam chat models falsos), então
  nenhum secret precisa ser configurado no repo. Badge de status no
  README.md. **Não confirmei o run real no GitHub** (repo é privado e
  não tenho `gh`/token configurado nesta sessão) — conferir na aba
  Actions.
- **`standards/frontend.md` auditado e reescrito** — igual foi feito com
  o backend, mas com uma decisão importante: os dois frontends reais
  disponíveis (`melhorperfil-web`, `santo-guardiao-web`) são **Next.js
  (App Router) + TypeScript**, não Vite. Optamos por TROCAR o padrão do
  time pra Next.js/TypeScript (em vez de manter Vite e só extrair
  princípios agnósticos) — decisão explícita do usuário. Persona do
  `dev_frontend` em `agents/team.py` e o pedido de exemplo em
  `dev_frontend_agent.py` já atualizados pra Next.js. **O que já rodou
  em `workspace/frontend` (Passo 3) ainda é Vite** — desatualizado, sem
  problema porque é só sandbox de teste.
- **`standards/design.md`** — resposta a uma preocupação real do usuário:
  IA costuma gerar frontend com "cara de IA" (genérico, sem hierarquia,
  sem identidade, difícil de escanear). Destilado da skill própria
  `artifact-design` (não é sobre Artifact aqui — só minerei os
  fundamentos de design que são universais: lista de clichês pra evitar,
  paleta/tipografia decididas ANTES do código, layout consistente,
  usabilidade — "resumo antes do detalhe", estado interativo parece
  interativo —, copy como material de design, os dois temas, estado
  inicial realista). Já conectado na persona do `dev_frontend`
  (`_ROLE_STANDARDS`), junto com `frontend.md`. Testado que carrega.

## Pendências / próximos passos possíveis

1. **Rodar `team_supervisor.py` de novo** — a última execução ponta a
   ponta foi ANTES de tudo que rigorizamos depois: `standards/backend.md`,
   saída estruturada do arquiteto, e a troca de frontend pra Next.js.
   Vale ver: (a) se o backend gerado reflete IDOR-safe queries, exceções
   tipadas etc.; (b) se o `ArchitecturePlan` vem preenchido direito;
   (c) se o frontend já sai em Next.js/TypeScript, seguindo `design.md`
   (paleta/tipografia decididas, sem clichê de IA); (d) vai ser a primeira
   execução real aparecendo no dashboard.
2. **Rodar `refactor_team.py`** (virou uma auditoria só-leitura) pra ver
   o próprio `dev_backend` conferir se o código do time está aderente aos
   padrões, do ponto de vista dele — inclui checar os paths novos
   (`agents/`, `standards/`) e o `.github/workflows/ci.yml`.
3. **Decidir um projeto real** pra equipe construir — até agora só pedidos
   de teste genéricos (login, lista de favoritos). Ficou em aberto
   propositalmente ("vou decidir na hora").
4. **`DesignPlan` estruturado, mirando o padrão do `ArchitecturePlan`.**
   A skill `artifact-design` recomenda esboçar um plano de design (paleta,
   tipografia, conceito de layout) ANTES de escrever código — hoje isso
   só existe como texto dentro de `design.md`, o modelo tem que "lembrar"
   sozinho. Dá pra formalizar como saída estruturada
   (`create_agent("dev_frontend", output_schema=DesignPlan)`, igual já
   fizemos pro arquiteto) — o Supervisor guardaria o plano decidido no
   histórico, e telas seguintes reaproveitariam a mesma paleta/tipografia
   em vez de cada rodada decidir de novo.
5. **Memória entre execuções** e **RAG sob demanda** (papéis lendo docs
   via tool em vez de tudo empilhado na persona) — ficaram cogitados no
   roteiro original e nunca foram construídos. `trim_messages` (LangChain,
   ainda válido/atual) é o candidato certo pro dia que isso for construído
   — as classes antigas de `langchain.memory` (`ConversationBufferWindowMemory`
   e primas) estão deprecadas desde 0.3.1, removal na 1.0.0.
6. **Dashboard só mostra o que já aconteceu.** Se um dia fizer sentido
   acompanhar em tempo real durante uma execução longa (ex: o Supervisor
   rodando várias rodadas), dá pra explorar `st.rerun`/auto-refresh — hoje
   é preciso atualizar a página manualmente.
7. **Confirmar o primeiro run do CI no GitHub** (Actions tab) — ver nota
   acima, não verificado nesta sessão.

## Gotchas importantes (não repetir)

- **`ChatAnthropic` sem `max_tokens` explícito corta respostas com
  thinking + várias tool calls no meio do JSON.** Sempre passe
  `max_tokens` (ver `agents/llm.py`).
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
  `usage_metadata` nativo do `langchain_anthropic` (ver `agents/usage.py`).
- **`ConversationBufferWindowMemory`, `ConversationSummaryMemory` e
  `ConversationSummaryBufferMemory` (`langchain.memory`) estão
  deprecadas** desde a 0.3.1 (removal na 1.0.0) — não usar em código
  novo. O guia de migração do LangChain aponta pro padrão LCEL nativo
  (`trim_messages` + histórico gerenciado à mão).
- **Audite a stack antes de escrever um `.md` de padrões, não depois.**
  A auditoria de frontend quase gerou um `standards/frontend.md` rico mas
  incompatível com os repos reais — eles são Next.js, o time já vinha
  usando Vite. Sempre checar `package.json`/config real do projeto fonte
  antes de destilar padrões, e decidir explicitamente se a stack do time
  muda ou se só os princípios agnósticos são aproveitados.
