# Progresso — sessões de 2026-09-02, 2026-09-03 e 2026-09-06

## Onde paramos

O time de tecnologia (LangChain + Claude) está montado e validado
ponta a ponta: **Fundação → especialista com tools → segundo especialista
→ Supervisor → padrões de código próprios → refatoração pro estilo real
→ rastreamento de custos + dashboard → padronização com Pydantic →
diretórios em inglês + CI + padrão de frontend real → padrão de design/UX
→ DesignPlan estruturado → RAG sob demanda (`search_standards`) →
prompt caching (`cost-optimize`) → sandbox configurável pra projeto
real**. O repo já está no GitHub (`VictorOliveiraPy/dev-agent`), e a
conta da Anthropic ficou sem crédito no meio do dia 02 — por isso o dia
03 foi todo em coisas que não custam API. Ver também ARCHITECTURE.md,
que documenta as decisões e o porquê de cada uma.

## ⚠️ Achado importante: o time não conseguia se auto-validar

Depois do build real do fe-catolica, revisei o frontend manualmente (via
Claude Code, sem gastar API — só `node`/`npm` locais) e achei: **um bug
de tipo real** (`apiGet<T>` com `ZodType<T>` quebrando a inferência com
schemas `.default()` — erro `tsc` genuíno) e **uma dependência com 3 CVEs
críticas** (`next@14.2.5`). Nenhum dos dois foi pego pelo time sozinho.

**Causa raiz, não é o modelo ser fraco**: a tarefa (`build_fe_catolica.py`
e `resume_fe_catolica_frontend.py`) instruía explicitamente "não rode
comandos de instalação" — regra copiada sem questionar dos scripts de
teste RÁPIDOS (`main.py`, `dev_backend_agent.py`), onde fazia sentido
manter os loops curtos. Só que sem `npm install`, o `dev_frontend` NUNCA
teve `node_modules` — logo nunca pôde rodar `tsc`/`eslint`/`vitest`/
`build` para conferir o próprio trabalho. É o equivalente a proibir o
`dev_backend` de rodar `pytest`.

### O que precisa mudar (concreto)

1. ✅ **Feito**: `run_command` tinha timeout de 60s — curto demais pra
   instalar dependência de verdade (`npm install` real levou ~2min).
   Subiu pra 180s (`agents/tools.py`).
2. ✅ **Feito**: auto-validação virou seção obrigatória em
   `standards/general.md` (instalar → typecheck/lint/teste/build →
   `pip-audit`/`npm audit` → só então "concluído"), com os comandos
   exatos em `standards/backend.md` e `standards/frontend.md`. Como fica
   na persona automaticamente (não no texto de UMA tarefa), vale pra
   qualquer build futuro sem precisar repetir a instrução. Removida a
   proibição de instalar de `build_fe_catolica.py`/
   `resume_fe_catolica_frontend.py` (ficaria contraditória com o padrão
   novo). Testado que as duas personas carregam a regra certa, sem API.
3. **Pendente**: item 3 acima (`pip-audit`/`npm audit`) já ficou coberto
   pelo item 2 — mantido só como registro histórico do problema original.
4. **Pendente, maior**: considerar um papel de revisão/QA no loop do
   Supervisor. Os repos reais que auditamos (`melhorperfil-api/web`,
   `santo-guardiao-api/web`) têm `quality-reviewer`/`qa-engineer`
   explícitos, rodando até "zero achados" — nosso Supervisor vai
   `arquiteto → dev_backend → dev_frontend → concluido` sem NINGUÉM
   conferir o resultado final de ponta a ponta. Isso é o motivo
   estrutural de fundo: mesmo com auto-validação (item 2), um agente
   revisando o PRÓPRIO trabalho tem menos poder de pegar erro do que um
   segundo papel dedicado a isso.

Ver ARCHITECTURE.md, seção "Limitações conhecidas", pro registro
completo desta decisão.

**🎉 PRIMEIRO PROJETO REAL RODOU — `fe-catolica`, em 2026-09-03.** O
usuário recarregou a conta e mandou rodar. Resultado: backend FastAPI
completo (8 categorias, 25 testes passando) + frontend Next.js quase
completo (parou por atingir `max_iterations=40`, não por erro). Ver seção
dedicada "Projeto real: fe-catolica" abaixo pro relato completo, incluindo
uma queda de rede real no meio do processo e como foi contornada sem
repetir trabalho já pago.

## O que já funciona (testado de verdade, rodando)

- **`agents/llm.py`** — fábrica única do `ChatAnthropic` (`claude-opus-5`,
  `max_tokens` explícito — evita respostas cortadas no meio de tool calls).
- **`agents/team.py`** — personas do time (`ROLES`) + composição automática
  com `standards/*.md` (`_build_persona`). A persona vira uma
  `SystemMessage` com `cache_control` (`_system_message`) — ver o item de
  prompt caching mais abaixo; isso também eliminou o hack antigo de
  escapar chaves literais, que não é mais necessário.
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
- **`DesignPlan` estruturado + orquestração em duas etapas** — formaliza a
  recomendação da skill (decidir design ANTES do código). Novo em
  `agents/schemas.py`: `ColorToken` (hex validado por regex) e
  `DesignPlan` (4-6 cores, 2 fontes, conceito de layout, clichês evitados;
  método `to_brief()` renderiza o plano como instrução pro agente de
  implementação). Nova função `agents/team.py::run_frontend_task(task,
  tools)`: chama o `dev_frontend` sem tools pra decidir o `DesignPlan`,
  depois com tools pra implementar já seguindo o plano — devolve
  `(plan, texto)`. Conectado em `dev_frontend_agent.py` e em
  `agents/supervisor.py::_run_frontend` (o resumo no histórico do
  Supervisor agora inclui o plano decidido, então uma segunda tela na
  mesma tarefa reaproveita a paleta em vez de decidir de novo). De
  quebra, extraí `extract_agent_output_text` (antes duplicado 3x — em
  `dev_backend_agent.py`, `dev_frontend_agent.py`, `supervisor.py`) pra
  uma função só em `team.py`. Testado de ponta a ponta com stubs (sem
  chamar `.with_structured_output()` de verdade, que exige API real) — 6
  testes novos, 28 no total.
- **`search_standards` — RAG sob demanda sobre `standards/*.md`, via BM25**
  (`agents/knowledge.py`). Decisão consciente: BM25 (busca por
  palavra-chave, `rank_bm25`, puro Python) em vez de embeddings
  semânticos (sentence-transformers + PyTorch, 100-800MB de download) —
  nosso corpus é pequeno e o vocabulário é técnico/específico ("IDOR",
  "JWT", "rounded-lg"), onde BM25 funciona bem sem gastar API nem baixar
  modelo pesado. Detalhe real encontrado testando contra os `.md` de
  verdade: um tokenizador ingênuo (`.split()`) gruda pontuação de
  markdown na palavra (`**idor` em vez de `idor`) e a busca erra o alvo —
  corrigido com um tokenizador por regex. Também descobrimos uma
  degenerescência matemática do BM25: com um corpus de só 2 documentos,
  um termo presente em exatamente 1 deles (50%) zera o IDF pela fórmula
  clássica — documentado no teste, não é bug. Conectada como tool de
  `dev_backend`/`dev_frontend`/Supervisor, somando às tools de arquivo.
  5 testes novos, 33 no total. Ver ARCHITECTURE.md para a decisão completa.
- **Prompt caching (`cache_control: ephemeral`)** na mensagem de sistema
  de `create_agent`/`create_agent_with_tools`, via a skill `claude-api
  cost-optimize`. Persona ~2.1-2.9k tokens estimados por papel,
  reenviada inteira em cada iteração do loop — maior alvo de custo do
  projeto. Efeito colateral: virou uma `SystemMessage` direta em vez da
  tupla `("system", persona)` do `ChatPromptTemplate`, então o escape de
  chaves literais deixou de ser necessário e foi removido (bug antigo,
  não volta). De brinde, `max_tokens` do agente com tools subiu de 8192
  pra 16000 (higiene de output, evita truncar loop agentic). Testado o
  wiring (a mensagem chega ao modelo com `cache_control`, sem chaves
  escapadas) — o GANHO de custo em si só se mede com uso real
  (`usage.cache_read_input_tokens > 0`), pendente de crédito. 2 testes
  novos, 35 no total. Effort menor no roteador e modelo mais barato foram propostos mas NÃO
  aplicados — exigem um eval que não temos (ver ARCHITECTURE.md).
- **Sandbox de produto configurável (`DEV_AGENT_WORKSPACE`)** —
  `agents/tools.py::_resolve_workspace()` lê essa env var (senão cai no
  `workspace/` padrão), lida uma única vez na importação. Permite um
  script de entrada apontar o time pra um projeto real, com git próprio,
  em vez da sandbox descartável. Testado (escrita real confirmada em
  `/home/oliveira/Documentos/code/fe-catolica`, depois limpa). 2 testes
  novos, 37 no total.

## 🚀 Projeto real: fe-catolica

Primeiro projeto de verdade do time (não mais teste genérico). Decidido
com o usuário em 2026-09-03:

- **O quê**: plataforma sobre a Igreja Católica — Santos (e histórias),
  Papas, Milagres Eucarísticos registrados, Catecismo, Crisma, História
  da Igreja, Doutores da Igreja, Concílios.
- **Escopo v1** (escolha explícita do usuário): estrutura completa
  primeiro — todas as categorias navegáveis e buscáveis, com 2-3
  exemplos reais por categoria — não um catálogo extenso ainda.
  Aprofundar categoria por categoria vem depois.
- **Cuidado de conteúdo**: a tarefa (`build_fe_catolica.py::TASK`) pede
  fatos amplamente conhecidos e não controversos como exemplo, proíbe
  inventar detalhe incerto (data, local), e pede que fique explícito nos
  dados que são exemplos iniciais a expandir — mitigação deliberada
  contra alucinação em conteúdo religioso/histórico real.
- **Onde**: `/home/oliveira/Documentos/code/fe-catolica`, repositório git
  próprio (separado do dev-agent).

### O que rolou na execução real (2026-09-03)

1. `build_fe_catolica.py` rodou o Supervisor: `arquiteto` → `dev_backend`
   → `dev_frontend`. Arquiteto e backend terminaram normalmente. No meio
   da implementação do frontend (depois de escrever os arquivos de
   config), a chamada quebrou com
   `httpx.RemoteProtocolError: peer closed connection without sending
   complete message body` — falha de REDE (conexão caiu no meio de um
   stream), não bug nosso. `agents.supervisor.run()` não tem
   checkpoint/resume: o `history` em memória se perde se o processo
   morre, mas os ARQUIVOS já escritos no disco continuam lá.
2. Em vez de re-rodar tudo (o que re-pagaria arquiteto + backend do
   zero), criei `resume_fe_catolica_frontend.py`: aciona
   `create_agent_with_tools("dev_frontend", ...)` DIRETO — não
   `run_frontend_task` — com uma instrução pra ler o `tailwind.config.ts`
   já escrito (não redecidir design) e o backend já pronto, e continuar
   a implementação dali. Terminou com `Agent stopped due to max
   iterations` (40) — não erro, só o teto batido depois de gerar bastante
   coisa (todas as páginas, componentes, lib e testes existem).
3. Resultado final: **backend completo, 25 testes passando**
   (`pytest -q -o addopts=""`, rodando com o Python global do sandbox —
   `pyproject.toml` pede `--cov` mas `pytest-cov` não está instalado
   globalmente aqui, só no `requirements.txt` do próprio fe-catolica).
   **Frontend com toda a estrutura** (home, nav entre as 8 categorias,
   listagem, detalhe, busca cross-categoria, error/not-found, testes
   `vitest` pra lógica pura) — não validado rodando (`node`/`npm` não
   existem neste ambiente), então falta confirmar
   `npm install && npm run build && npm test` numa máquina com Node.
4. **Design decidido pelo `dev_frontend`**: paleta pergaminho/bordô/
   púrpura/dourado, serifada + sans, cantos praticamente retos de
   propósito ("o projeto é impresso, não app de celular") — nenhum
   clichê de `standards/design.md` apareceu.
5. **Mitigação de conteúdo funcionou**: cada JSON de dados veio com
   `_meta.status: "exemplos-iniciais"`, aviso explícito de que precisa
   revisão contra fonte primária, datas incertas marcadas com "c." em vez
   de inventadas, e fontes gerais citadas (Martirológio Romano,
   vatican.va).
6. **Achado**: nosso log de uso não capturava `cache_read`/
   `cache_creation` (só o total) — corrigido depois desta run (ver
   ARCHITECTURE.md); os 71 registros desta primeira execução real ficaram
   sem esse detalhe, então não dá pra confirmar se o prompt caching
   funcionou NESTA run especificamente. **3.04M tokens de entrada, 130K
   de saída, 71+2 chamadas** ao todo (arquiteto: 2 chamadas; dev_backend:
   ~1 rodada completa; dev_frontend: 2 execuções — a que caiu + a de
   retomada).
7. Commitado localmente no `fe-catolica` (`git commit`, sem push — não há
   remote configurado ainda).

### Pendente de revisão humana antes de considerar "pronto"

- Rodar `npm install && npm run build && npm test` no frontend numa
  máquina com Node.
- Ler o conteúdo religioso/histórico gerado com atenção — a mitigação
  ajudou, mas exemplo gerado por LLM sempre merece checagem antes de
  virar parte pública de uma plataforma.
- Decidir se o `fe-catolica` ganha um remote no GitHub.

## 🔎 Novo papel: Pesquisador de conteúdo (RAG) — 2026-09-03

Depois de expandir o acervo do fe-catolica manualmente (via Claude Code,
sem gastar API — `WebFetch`/`WebSearch` + `curl` pra conferir imagem) por
várias categorias, o usuário pediu pra automatizar isso dentro do
dev-agent: um agente que pesquisa a web de verdade (RAG) e propõe novas
entradas, em vez de escrever fato de memória.

### Desenho: por que NÃO é `AgentExecutor` (diferente dos outros papéis)

`web_search` é uma tool **server-side** da própria Anthropic — o modelo a
executa e recebe o resultado dentro da MESMA chamada, sem round-trip pelo
cliente (ver `langchain_anthropic.chat_models`, linha ~1217, que já
documenta `bind_tools([{"type": "web_search_20250305", "name":
"web_search"}])`). A única tool "de verdade" (que precisa de execução no
cliente) é `submit_entries`, a saída final estruturada. Por isso
`agents/researcher.py` não usa o loop genérico de tool-calling do
LangChain — é um loop manual pequeno: chama o modelo, olha se ele já
chamou `submit_entries`, se não chamou insiste (até `max_attempts`).

### O gap de autovalidação, aplicado a CONTEÚDO (não só código)

O achado da sessão anterior ("o time não conseguia se autovalidar") vale
igual aqui, só que pra fatos em vez de código. `validate_batch` nunca
confia no que o modelo afirma:

1. **Slug duplicado** é descartado antes de tudo.
2. **`id` é sempre recalculado como `'{categoria}:{slug}'`** — nunca
   aceito do jeito que o modelo propôs.
3. **Toda URL de imagem leva uma requisição HTTP de verdade**
   (`_verify_image_url`, via `httpx`) — se não resolver como `image/*`
   200, a imagem (não a entrada) é descartada.
4. **O item final valida contra o modelo Pydantic REAL do backend**,
   importado do repositório `acervo-catolico-api` (não duplicado) — o
   mesmo `model_json_schema()` vira o schema da tool `submit_entries` E
   o validador, então o modelo nunca recebe um contrato diferente do que
   será cobrado dele.

Nada disso substitui checar o TEXTO (datas, nomes, teologia) — isso
ainda depende de revisão humana antes de publicar (ver "Pendente de
revisão" abaixo). `validate_batch` pega estrutura e imagem, não fato.

### Primeiro lote real: concílios ecumênicos (categoria fechada, 21 no total)

Escolhido de propósito como piloto: dá pra chegar a 100% da categoria
(diferente de santos/papas, sem teto natural), e serve pra medir custo
real antes de decidir se vale escalar.

**Três bugs reais encontrados na primeira execução de verdade** (nenhum
pego pelos testes com fake model — só apareceram gastando API de
verdade):

1. **Pedir 18 concílios numa chamada só estourou `max_tokens`** (a
   tentativa gastou ~220k tokens só de contexto acumulado de busca — e
   FALHOU, sem gravar nada) e o código original lia
   `call["args"]["itens"]` sem checar se a tool call tinha vindo
   completa, resultando num `KeyError` cru sem contexto nenhum. Corrigido
   em duas frentes: (a) `research_batch` agora checa
   `response_metadata["stop_reason"] == "max_tokens"` e falha com
   mensagem clara ANTES de tentar ler `tool_calls`; (b)
   `research_concilios.py` passou a pedir em sub-lotes de 4 (`_CHUNK_SIZE`),
   não os 18 de uma vez — 5 chamadas menores em vez de uma gigante, cada
   uma resiliente (um sub-lote falhar não derruba os outros).
2. **O modelo devolveu `"id": "efeso"` em vez de `"id": "concilios:efeso"`**
   — quebra a convenção usada em TODA entrada existente do acervo.
   Corrigido removendo a decisão do modelo: `validate_batch` agora
   recalcula `id` sempre, ignorando o que veio na resposta (ver ponto 2
   da lista de autovalidação acima).
3. **Tags vieram em `kebab-case-sem-acento`** (`seculo-v`, `leao-magno`)
   — o resto do acervo usa palavras naturais com acento (`século V`,
   `Leão Magno`); isso quebraria a busca por tema no site. Sem checagem
   automática pra isso (é estilo, não schema) — corrigido manualmente
   nas 4 entradas já gravadas, e a persona do pesquisador ganhou uma
   regra explícita com os exemplos reais do erro (regra 7). Também
   apareceu um vazamento de inglês no meio de uma frase em português
   ("é **rightly** chamada Mãe de Deus") — mesma categoria de problema
   (estilo, não estrutura), mesma resposta: regra explícita na persona
   (regra 8) + correção manual do que já tinha sido escrito.

**Custo real observado**: o sub-lote de 4 concílios que teve sucesso
gastou **264.787 tokens** (255.577 de entrada, 9.210 de saída — a
maioria é resultado de busca acumulado no contexto, não geração). A
tentativa anterior de 18-de-uma-vez gastou ~220k tokens e não gravou
nada (falhou). **O crédito da API acabou nesse ponto** — restam 14 dos
18 concílios, mais os lotes de papas/santos/milagres que o usuário
pediu, tudo pendente de mais crédito.

Isso é bem mais caro, por entrada, do que fazer a mesma pesquisa
manualmente via Claude Code (`WebFetch`/`WebSearch`) — o resultado de
busca da Anthropic fica inteiro no contexto a cada turno subsequente,
sem o mesmo controle de "resumir antes de usar" que dá pra fazer
manualmente. **Considerar**: usar o tier gratuito do Google Gemini
(tem tool de busca nativa, `google_search`) como backend alternativo
pra este papel especificamente — exigiria `langchain-google-genai` como
dependência nova e adaptar o formato da tool de busca (a da Anthropic e
a do Gemini não são o mesmo shape). Ainda não feito; avaliar quando/se o
custo da Anthropic pra este papel voltar a incomodar.

### Estado atual

- ✅ `agents/researcher.py` (`research_batch`, `validate_batch`,
  `_verify_image_url`) — 11 testes, zero chamada real de API neles
  (fake model + `_verify_image_url` monkeypatchada).
- ✅ `research_concilios.py` — primeiro script piloto, com `--dry-run`
  pra conferir o prompt/lotes sem gastar nada.
- ✅ 4/18 concílios que faltavam já estão em
  `acervo-catolico-api/app/data/concilios.json`, revisados e com os 3
  bugs acima corrigidos manualmente (nenhum commit/push feito ainda —
  aguardando decisão sobre completar o lote primeiro).
- ⏳ Faltam 14 concílios, e os lotes de papas (263!), santos (~15-20) e
  milagres eucarísticos que o usuário também pediu — todos bloqueados
  por crédito de API até novo aviso.
- ⏳ Nenhuma das 4 entradas gravadas tem imagem (o modelo preferiu `null`
  a arriscar — ver regra 3 da persona) — ficaria bom completar isso,
  manualmente (como as outras categorias) ou num lote de pesquisa
  dedicado só a imagem, depois que houver crédito de novo.

## Pendências / próximos passos possíveis

1. ✅ **Validar o frontend do fe-catolica rodando de verdade** — feito
   nesta sessão via Claude Code (node/npm reais, zero custo de API):
   achou e corrigiu um bug de tipo real e uma dependência com CVEs
   críticas. Ver seção "Achado importante" acima — isso virou 4 itens de
   melhoria pro dev-agent, não só uma checagem pontual.
2. **Revisar o conteúdo gerado com olho crítico antes de considerar
   "pronto"** — mesmo com a mitigação na tarefa, fatos religiosos/
   históricos gerados por LLM merecem checagem humana antes de virar
   parte pública da plataforma.
3. **Aprofundar categoria por categoria no fe-catolica** — v1 entregou
   estrutura completa com 2-3 exemplos por categoria (escolha explícita
   do usuário); o próximo passo natural do PRODUTO (não do dev-agent) é
   popular cada categoria de verdade.
4. **Rodar `refactor_team.py`** (virou uma auditoria só-leitura) pra ver
   o próprio `dev_backend` conferir se o código do TIME (dev-agent, não o
   fe-catolica) está aderente aos padrões — inclui checar os paths novos
   (`agents/`, `standards/`) e o `.github/workflows/ci.yml`.
5. **Memória entre execuções** — ainda não construída. `trim_messages`
   (LangChain, ainda válido/atual) é o candidato certo — as classes
   antigas de `langchain.memory` (`ConversationBufferWindowMemory` e
   primas) estão deprecadas desde 0.3.1, removal na 1.0.0.
6. **`agents.supervisor.run()` não tem checkpoint/resume.** A queda de
   rede no fe-catolica só foi contornável porque os arquivos já escritos
   sobrevivem no disco — o `history` em memória, não. Se isso voltar a
   acontecer, vale considerar salvar o `history` em disco a cada rodada
   (não só no fim), pra um resume automático não precisar de um script
   manual como `resume_fe_catolica_frontend.py`.
7. **RAG sob demanda — parcialmente feito, mas já validado em uso real.**
   `search_standards` foi chamada 3x sozinha durante o build do
   fe-catolica (sem eu ter pedido) — o time usa a tool quando faz
   sentido. Ainda é ADITIVO (a persona segue empilhando o `.md` inteiro
   também); ir além (persona enxuta + tool como única fonte) continua
   adiado por ora.
8. ✅ **Dashboard só mostra o que já aconteceu** — resolvido em
   2026-09-06 com `web_ui.py`: `agents/supervisor.py::run` virou gerador
   e a Streamlit UI mostra cada rodada ao vivo, sem precisar de
   auto-refresh no `dashboard.py` original (que continua só pra
   custo/histórico agregado). Ver seção "Interface web" abaixo.
9. **Confirmar o primeiro run do CI no GitHub** (Actions tab) — ver nota
   acima, não verificado nesta sessão.

## Gotchas importantes (não repetir)

- **`ChatAnthropic` sem `max_tokens` explícito corta respostas com
  thinking + várias tool calls no meio do JSON.** Sempre passe
  `max_tokens` (ver `agents/llm.py`).
- **`ChatPromptTemplate` trata a tupla `("system", texto)` como f-string**
  — chaves literais de exemplo de código (ex: `extra={"user_id": user.id}`)
  quebravam a montagem do prompt. Resolvido de vez (não é mais um "cuidado
  ao editar", virou impossível de acontecer): a persona agora vira uma
  `SystemMessage` construída direto (`agents/team.py::_system_message`),
  que não passa pelo motor de template — nenhum escape é necessário.
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
- **A tool `web_search` nativa da Anthropic é MUITO mais cara, em
  tokens, do que parece.** Cada resultado de busca fica inteiro no
  contexto do turno e de todos os turnos seguintes — 4 itens pesquisados
  gastaram 264.787 tokens numa chamada só (ver seção "Pesquisador de
  conteúdo" acima). Nunca peça um lote grande (18 itens) numa chamada só
  por causa disso: além do custo, o output também estoura `max_tokens`
  fácil e a resposta vem cortada no meio da tool call. Prefira lotes de
  3-6 itens por chamada.
- **`response.tool_calls` pode vir com uma tool chamada mas sem os
  argumentos esperados** se a geração foi cortada por `max_tokens` no
  meio do JSON — sempre cheque `response.response_metadata["stop_reason"]`
  ANTES de indexar `call["args"][...]`, ou um corte vira `KeyError` sem
  contexto nenhum em vez de um erro claro (ver `agents/researcher.py::
  research_batch`).
- **Nunca deixe o modelo decidir o valor de um campo 100% derivável**
  (ex.: `id`, que é sempre `'{categoria}:{slug}'`) **quando dá pra
  calcular em código.** O pesquisador devolveu `id: "efeso"` em vez de
  `id: "concilios:efeso"` na primeira tentativa real — bug de
  inconsistência que só existe porque o modelo tinha esse campo pra
  preencher. `validate_batch` agora recalcula `id` sempre, ignorando o
  que vem na resposta.

## Sessão de 2026-09-06 — modelo mais barato, interface web, organização

**Contexto**: a conta da Anthropic ficou sem crédito de novo no meio da
sessão (mesmo gotcha de 02/09, recorrente) — não impediu o trabalho
porque quase tudo abaixo é wiring/decisão, testável sem crédito real
(exceto o experimento com Ollama, que roda local).

**Experimento real: Ollama local (Docker) como provedor mais barato —
testado e revertido.** Subiu `ollama/ollama` via `docker compose`, baixou
`llama3.1:8b` e `qwen2.5-coder:7b`, e testou os dois com
`build_chat_model` de verdade: resposta factual + uma tool call simples
(`write_file`). Achado real, não hipotético — `qwen2.5-coder:7b` (apesar
do nome) devolveu o JSON da tool como TEXTO solto em vez de usar o canal
estruturado de tool calling; `llama3.1:8b` foi inconsistente entre
execuções no mesmo prompt. Decisão: reverter o código (`agents/llm.py`
voltou a só `ChatAnthropic`) — a lição fica em ARCHITECTURE.md, não como
provedor morto no repo. OpenRouter (adicionado junto, nunca testado de
verdade) foi removido pelo mesmo motivo de simplicidade.

**Modelo mais barato aplicado de verdade, mas só onde o risco é baixo.**
`arquiteto` (só texto/`ArchitecturePlan`, sem tools) passou a usar Claude
Haiku 4.5 — mais barato ($1/$5 por milhão de tokens vs. $5/$25 do Opus
5). `dev_backend`/`dev_frontend` continuam em Opus 5 de propósito: é
exatamente o cenário (tool calling) onde o teste do Ollama mostrou risco
concreto — ver ARCHITECTURE.md, seção "Custo".

**`web_ui.py`: interface Streamlit pra rodar o time e ver a conversa ao
vivo**, resolvendo a pendência #8 acima. Exigiu transformar
`agents/supervisor.py::run` de função (devolvia a lista completa no
final) em GERADOR (entrega cada evento assim que acontece) — e expor
`Decision.reasoning` (já existia no schema, nunca tinha virado visível em
lugar nenhum) como um evento próprio, sem poluir o histórico que volta
pro roteador. `team_supervisor.py` (CLI) ganhou o mesmo streaming de
graça, sem precisar mudar como ele chama `run()`.

**Organização: `projects/*.py` separado do framework.** Os scripts que
disparam o time em cima de um projeto real específico (fe-catolica,
repasse-api, repassei, concílios) foram movidos pra `projects/` — não são
o framework, são o histórico de uso dele. Rodar como módulo agora
(`python -m projects.build_fe_catolica`), não pelo caminho do arquivo —
Python só coloca a raiz do repo no `sys.path` (onde `agents/` resolve)
quando o script roda com `-m` a partir da raiz.

**Testes**: suíte cresceu de 33 pra 63 (novos: `test_llm.py`,
`test_supervisor.py`, `test_web_ui.py`; `test_team.py` ganhou um caso
pro `_ROLE_MODELS`) — nenhum chama API real, mesma convenção de sempre.
