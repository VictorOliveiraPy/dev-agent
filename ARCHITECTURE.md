# Arquitetura do dev-agent

> Documento vivo — atualizado a cada decisão estrutural nova. Objetivo:
> qualquer pessoa (ou sessão futura) entender não só *o que* o projeto faz,
> mas *por que* foi construído assim, sem precisar reconstruir o raciocínio
> do zero. Ver [PROGRESS.md](PROGRESS.md) para o estado tarefa-a-tarefa;
> este arquivo é sobre decisões estruturais, não status.

---

## Visão geral

O `dev-agent` é um time de agentes de IA (LangChain + Claude) que projeta
e implementa projetos de software (Python + Next.js) de ponta a ponta.
Cada papel do time é um agente especializado; um Supervisor decide qual
papel age em cada rodada, sem intervenção manual.

Duas orquestrações independentes convivem no mesmo repo: o **loop do
Supervisor** (arquiteto → dev_backend → dev_frontend, o diagrama abaixo)
constrói código; o **pesquisador** (`agents/researcher.py`) é um pipeline
à parte, sem Supervisor, que propõe e valida conteúdo (não código) via
busca web real — ver "Pesquisador" nas decisões abaixo.

## Diagrama do time

```mermaid
graph TD
    UI[web_ui.py / team_supervisor.py<br/>tarefa do usuário] -->|task| S
    S[Supervisor<br/>roteador com saída estruturada] -.stream ao vivo.-> UI
    S -->|decide o próximo papel| A[arquiteto<br/>Haiku 4.5, sem tools, saída estruturada]
    S --> B[dev_backend<br/>Opus 5, com tools]
    S --> F[dev_frontend<br/>Opus 5, design + tools, 2 etapas]

    A -->|ArchitecturePlan| S
    B -->|escreve código| WS[(workspace/)]
    F -->|DesignPlan + código| WS

    B -.consulta sob demanda.-> KB[search_standards<br/>BM25 sobre standards/*.md]
    F -.consulta sob demanda.-> KB

    STD[standards/*.md] -->|empilhado na persona| A
    STD -->|empilhado na persona| B
    STD -->|empilhado na persona| F
    STD -.indexado.-> KB

    B -->|usage_metadata| U[usage_log.jsonl]
    F -->|usage_metadata| U
    A -->|usage_metadata| U
    U --> D[dashboard.py<br/>Streamlit]
```

## Componentes

| Arquivo | Responsabilidade |
|---|---|
| `agents/llm.py` | Fábrica única do `ChatAnthropic` — modelo, `max_tokens`, header de workspace |
| `agents/team.py` | Personas (`ROLES`), composição de persona + padrões (`_build_persona`), fábricas de agente (`create_agent`, `create_agent_with_tools`), orquestração de duas etapas do frontend (`run_frontend_task`) |
| `agents/supervisor.py` | Roteador (`Decision`, saída estruturada) + loop que aciona cada papel e monta o histórico |
| `agents/schemas.py` | Todo modelo Pydantic compartilhado: `Decision`, `ArchitecturePlan`, `DesignPlan`, `UsageEntry` |
| `agents/tools.py` | Tools sandboxed em `workspace/` — o produto que o time constrói |
| `agents/project_tools.py` | Tools sandboxed na raiz do projeto real, com bloqueio de segredos/git/venv — auto-manutenção do time |
| `agents/knowledge.py` | Índice BM25 sobre `standards/*.md` + tool `search_standards` |
| `agents/usage.py` | Callback que grava cada chamada real ao modelo em `usage_log.jsonl` |
| `agents/researcher.py` | Papel `pesquisador` — propõe conteúdo via busca web real (`TavilySearch`) e valida cada item contra o schema real do backend antes de virar arquivo. Pipeline à parte, não passa pelo Supervisor |
| `standards/*.md` | Convenções de código/design que cada papel segue — arquivos editáveis sem tocar em Python |
| `dashboard.py` | Streamlit lendo `usage_log.jsonl` (custo/uso) |
| `web_ui.py` | Streamlit pra rodar o Supervisor e acompanhar a "conversa" do time ao vivo, com tarefa via formulário |
| `main.py`, `dev_backend_agent.py`, `dev_frontend_agent.py`, `team_supervisor.py`, `refactor_team.py` | Scripts de entrada do framework, cada um exercitando uma camada (Passos 1-4 + auditoria) |
| `projects/*.py` | Scripts que já dispararam o time em cima de um projeto real específico (fe-catolica, repasse-api, ...) — histórico de uso, não framework; ver "Organização do repositório" |

---

## Decisões e motivos

### Fundação

**LangChain + Claude (`ChatAnthropic`), não a API bruta da Anthropic direto.**
LangChain dá abstrações prontas (prompt templates, tool calling, saída
estruturada, callbacks) que teríamos que reimplementar na mão — o custo é
uma camada de indireção a mais, aceitável pelo ganho de velocidade.

**`max_tokens` sempre explícito em `build_chat_model`.** Bug real
encontrado cedo: sem isso, uma resposta com "thinking" + várias tool
calls na mesma chamada é cortada no meio do JSON de uma tool call, e a
tool recebe argumento incompleto.

**Papéis como dict de string (persona) + arquivos `.md`, não classes
Python por papel.** Um papel novo é uma entrada de dict + um `.md`
opcional — não precisa de uma classe/arquivo Python novo. O "quem esse
agente é" (persona) fica separado do "que convenções ele segue"
(`standards/*.md`), a mesma ideia de um `CLAUDE.md`.

### Organização do repositório

**`projects/*.py` separado do framework, não misturado na raiz.** O
dev-agent não é só um projeto de estudo — já disparou o time de verdade
em cima de projetos reais (fe-catolica, repasse-api, repassei), cada um
com seu próprio script de entrada (`DEV_AGENT_WORKSPACE` + tarefa). Esses
scripts não são o framework reutilizável, são o HISTÓRICO de uso dele —
misturados na raiz junto de `agents/`/`dashboard.py`/`web_ui.py`, ficava
difícil separar "o produto" de "os registros de quem já usou o produto".
Movidos para `projects/`, rodados como módulo (`python -m
projects.build_fe_catolica`, nunca pelo caminho do arquivo direto — o
import de `agents` só resolve com a raiz do repo no `sys.path`, que é o
que `-m` garante a partir do diretório atual).

### Segurança

**Duas sandboxes de tool separadas, nunca uma tool com acesso irrestrito
ao disco.** `agents/tools.py` só enxerga a sandbox de produto (por padrão
`workspace/`, o descartável); `agents/project_tools.py` só enxerga a raiz
do dev-agent, com bloqueio explícito de `.env`/`.git`/`.venv`/`workspace`
— usado só pra auto-manutenção pontual (`refactor_team.py`), nunca pelo
time em operação normal.

**Sandbox de produto configurável via `DEV_AGENT_WORKSPACE`, lida uma
única vez na importação.** O primeiro projeto real do time (`fe-catolica`)
precisava sair de um lugar keepable, com git próprio — não da sandbox
descartável de teste. Em vez de criar um terceiro conjunto de tools,
`agents/tools.py::_resolve_workspace()` lê essa env var (senão cai no
`workspace/` padrão); um script de entrada dedicado
(`build_fe_catolica.py`) define a env var ANTES de importar qualquer
coisa de `agents`. Ler uma única vez, na importação, é proposital: a
sandbox nunca muda no meio de uma execução, mesmo que algo mexa na env
var depois.

**Checkpoint git antes de qualquer sessão que dê a um agente acesso de
escrita ao código real.** Um agente reescrevendo o próprio código-fonte
que o executa é uma classe de risco diferente de escrever num sandbox
descartável — `git diff`/`git checkout -- .` como rede de segurança.

### Padrões e qualidade

**Padrões extraídos de repositórios reais em produção, não de opinião
genérica de internet.** `standards/backend.md` foi destilado de dois
backends FastAPI reais (um processa pagamento via Pix); `standards/frontend.md`,
de dois frontends Next.js reais. Regra prática: auditar a stack de
verdade (`package.json`, config real) ANTES de escrever o `.md` — já
aconteceu de montar um padrão rico demais em cima da stack errada
(auditoria de frontend revelou Next.js onde a gente tinha Vite; a stack
do time foi trocada pra bater com a realidade).

**`standards/backend.md` migrado de camadas técnicas (routers/services/
models) para Clean Architecture por domínio (domain/application/
infrastructure/interface), em 2026-09-19.** Decisão explícita do usuário:
todo backend futuro do time (não só um projeto específico) segue a regra
de dependência de Uncle Bob (camadas internas nunca importam framework).
Cláusula de DRY incluída de propósito na mesma mudança: um projeto com
muitos domínios estruturalmente idênticos (o caso real que motivou a
pergunta — o Acervo Católico tem 49 categorias de conteúdo quase
idênticas, sem banco de dados pro conteúdo principal) não deve ganhar um
use case por domínio só pra seguir a letra do padrão — um use case
genérico e parametrizado é a escolha certa quando nenhum domínio tem
regra de negócio distinta; Clean Architecture "de verdade" (um caso por
domínio) fica reservada pros domínios com regra própria (pagamento, lance,
autenticação — ou, no Acervo Católico, velas/liturgia/chat).

**Saída estruturada (Pydantic) sempre que o resultado alimenta outra
etapa do sistema, não só um humano lendo texto.** `Decision` (o
Supervisor decide o próximo papel), `ArchitecturePlan` (o arquiteto
decide antes de codar), `DesignPlan` (o frontend decide design antes de
codar). Texto livre truncado em 500 caracteres era frágil — um campo
Pydantic é um contrato, não uma esperança de que o modelo formatou certo.

**Design decidido ANTES do código, formalizado como uma etapa separada
(`run_frontend_task`), não só uma instrução na persona.** Recomendação da
skill `artifact-design`: sem isso, cada componente decide cor/fonte na
hora, de forma inconsistente. A etapa de planejamento roda sem tools
(não pode "trapacear" escrevendo código antes de decidir); a etapa de
implementação recebe o plano já pronto via `DesignPlan.to_brief()`.

**Identificadores de código em inglês, docstrings/comentários/logs em
português.** Regra em `standards/general.md`, aplicada em toda
refatoração — inclusive nos nomes de diretório (`agents/`, `standards/`;
`workspace/` já era inglês, não mudou).

### Dados e observabilidade

**Callback de uso próprio, não `get_openai_callback`.** Esse helper do
`langchain_community` só entende o formato de resposta da OpenAI — nem
funcionaria com `ChatAnthropic`, e `langchain_community` nem é
dependência do projeto. Usamos o `usage_metadata` nativo do
`langchain_anthropic`, com um `BaseCallbackHandler` próprio
(`agents/usage.py`) que também não depende de nenhuma classe de Memory
deprecada.

**`cache_read_tokens`/`cache_creation_tokens` no log, não só o total.**
Lacuna encontrada na primeira execução real (`fe-catolica`): tínhamos
implementado prompt caching mas o próprio log não capturava
`usage_metadata["input_token_details"]` (onde o LangChain expõe
`cache_read`/`cache_creation`), então não dava pra confirmar se o cache
estava funcionando — só o total de tokens. Corrigido depois dessa
primeira run (os 71 registros dela ficaram sem esse dado, default 0 por
retrocompatibilidade — `UsageEntry` não quebra lendo log antigo); toda
execução daqui pra frente já mostra a taxa de acerto do cache no
dashboard.

**`UsageEntry` (Pydantic) valida o log tanto na escrita quanto na
leitura.** Uma linha malformada em `usage_log.jsonl` (log antigo, edição
manual) é ignorada com aviso — não derruba o dashboard inteiro parseando
um dict solto.

**Dashboard lê o arquivo, não mantém estado próprio.** `usage_log.jsonl`
é a fonte de verdade; `dashboard.py` só lê e agrega. Atualizar a página
é manual por enquanto (ver PROGRESS.md — não há necessidade real de
tempo real ainda).

### Custo

**Prompt caching (`cache_control: ephemeral`) na mensagem de sistema de
`create_agent`/`create_agent_with_tools`.** Achado da skill `claude-api
cost-optimize`: a persona (papel + `standards/*.md`) é ~2.1-2.9k tokens
estimados por papel (`dev_backend`/`dev_frontend`), idêntica em toda
chamada, e reenviada INTEIRA a cada iteração do loop de tool calling — o
maior alvo de custo do projeto, e o único free win real que dava pra
aplicar sem crédito de API (o wiring se testa; o ganho de custo em si só
se mede com uso real). Efeito colateral bom: como a persona virou uma
`SystemMessage` construída direto (não mais a tupla `("system", persona)`
do `ChatPromptTemplate`, que a tratava como template f-string), o hack de
escapar chaves literais (`_build_persona` fazia `.replace("{", "{{")`)
deixou de ser necessário e foi removido.

**`max_tokens=16000` no agente com tools** (subiu de 8192, o default de
`build_chat_model`). Não é uma economia — é uma correção de higiene de
output: um loop agentic escrevendo vários arquivos tem mais chance de
estourar um teto baixo no meio de uma tool call (o mesmo tipo de corte
que já causou um bug real, documentado acima) do que uma chamada de
texto/planejamento única. Uma tarefa que falha por truncamento e precisa
ser refeita custa mais que a folga extra no teto.

**Modelo mais barato (Claude Haiku 4.5) só no `arquiteto`, nunca em
`dev_backend`/`dev_frontend`.** Diferente da ideia descartada abaixo
(dois modelos pros papéis que ESCREVEM código), o arquiteto só produz
texto/`ArchitecturePlan` — sem tool calling, sem arquivo real gravado. O
pior caso de um modelo mais fraco aí é um plano pior, não um `tool_use`
malformado travando o `AgentExecutor`. Ver `_ROLE_MODELS` em
`agents/team.py`.

**Propostas testadas e descartadas: Ollama local e OpenRouter como
provedor alternativo.** Testado de verdade (não só lido): `llama3.1:8b` e
`qwen2.5-coder:7b` via Ollama local (Docker). Achado real — o segundo,
apesar do nome sugerir foco em tool use, respondeu a uma tool call
simples com o JSON como TEXTO solto em vez de usar o canal estruturado de
tool calling que o LangChain sabe interpretar; o primeiro deu respostas
inconsistentes entre execuções (uma certa, uma contraditória) pro mesmo
prompt. Nenhum dos dois é confiável o bastante pros papéis que escrevem
arquivo de verdade — e OpenRouter (nunca chegou a ser testado de verdade)
foi removido junto por não ter uso real que justificasse a complexidade
extra (`langchain-openai`, endpoint OpenAI-compatible, mais um provedor
pra manter). Código revertido — `agents/llm.py` voltou a só Anthropic; a
lição (modelo pequeno = tool calling não confiável) fica registrada aqui,
não em código morto.

**Atualização (2026-09-21): DeepSeek re-testado e desta vez adotado —
`LLM_PROVIDER=deepseek` em `agents/llm.py`.** Não é a mesma ideia
ressuscitada sem critério: a lição acima (modelo pequeno = tool calling
não confiável) continua valendo pra Ollama, mas DeepSeek é um modelo bem
maior e passou nos três testes reais que decidiriam a troca, contra a API
de verdade (não simulado): (1) tool call única e estruturada
(`submit_entries` do pesquisador, com fatos prontos no prompt); (2) o loop
completo do `AgentExecutor` com múltiplas tool calls reais em sequência
(`write_file` -> `read_file` -> `list_dir`, através do wiring real de
`agents/team.py::create_agent_with_tools`, incluindo o bloco
`cache_control` Anthropic-specific do system prompt — não quebrou); (3)
`.with_structured_output()` contra `ArchitecturePlan` e `DesignPlan`. Os
três produziram saída estruturada correta na primeira tentativa. Ver
PROGRESS.md (sessão 2026-09-21) pro detalhe de cada teste.

Design da troca: `agents/llm.py::build_chat_model` lê `LLM_PROVIDER` do
ambiente (default `"anthropic"` — quem não configura nada não muda nada) e
devolve `ChatAnthropic` ou `ChatDeepSeek`, mesma interface `BaseChatModel`
pros dois. `_ROLE_MODELS` em `agents/team.py` (o Haiku do arquiteto) é
específico da Anthropic e é ignorado sob `LLM_PROVIDER=deepseek` — não
existe um "Haiku do DeepSeek" equivalente hoje.

**`agents/researcher.py` seguia `LLM_PROVIDER` normal até 2026-09 —
migrado depois de um bug real em produção.** Antes, o papel sempre passava
`provider="anthropic"` explicitamente pro `build_chat_model`, porque
dependia da tool `web_search` nativa *server-side* da Anthropic (ver seção
"Pesquisador" abaixo) — sem equivalente no DeepSeek. Quando o usuário
rodou o time inteiro sob `LLM_PROVIDER=deepseek` sem uma
`ANTHROPIC_API_KEY` configurada (não precisava dela pra mais nada), o
Pesquisador quebrou com erro de autenticação — o hardcoding forçava
Anthropic mesmo com o resto do time em outro provedor. A correção trocou
`web_search` por `TavilySearch` (client-side, precisa de
`TAVILY_API_KEY`) e reescreveu o loop de `research_batch` pra executar a
busca de verdade e devolver o resultado como `ToolMessage` — ainda não é
um `AgentExecutor` genérico (só duas tools: busca e `submit_entries`), mas
agora funciona com qualquer provedor de tool-calling padrão.

**Propostas descartadas por enquanto (exigem eval que não temos):**
effort mais baixo no roteador do Supervisor (é uma decisão pequena e
repetida — bom candidato, mas sem forma de medir se a qualidade do
roteamento cai) e um SEGUNDO modelo mais barato pras tarefas rotineiras
de `dev_backend`/`dev_frontend` (diferente do Haiku no arquiteto acima —
aqui o risco é justamente o tool calling, e é isso que o teste de
Ollama/OpenRouter deixou concreto, não só hipotético). Aplicar qualquer
um dos dois sem conseguir comparar antes/depois seria trocar qualidade
por custo às cegas — a skill de cost-optimize é explícita sobre isso:
tradeoffs só se aplicam com uma forma de medir a queda de qualidade, e
hoje não temos nenhuma.

### RAG e recuperação de conhecimento

**BM25 (busca por palavra-chave), não embeddings semânticos, pra
`search_standards`.** Alternativa descartada: `HuggingFaceEmbeddings`
(sentence-transformers) + vectorstore — exigiria baixar um modelo de
~100-800MB (com PyTorch) e não traria ganho real pro nosso caso: o
corpus é pequeno (poucos arquivos `.md`) e o vocabulário é técnico e
específico ("IDOR", "JWT", "rounded-lg") — exatamente o cenário onde
busca por palavra-chave funciona bem e busca semântica não compensa o
custo. `rank_bm25` é puro Python, sem dependência pesada, sem chamada de
API nenhuma (nem de embeddings). Se o corpus crescer muito ou ficar mais
narrativo/prosa (menos técnico), essa decisão deve ser revisitada.

**Tokenizador por regex, não `.split()` ingênuo.** Bug real: pontuação de
markdown gruda na palavra (`**idor` em vez de `idor`) e a busca erra o
alvo. Corrigido extraindo sequências de letras/dígitos, tratando o resto
como separador.

**`search_standards` é ADITIVO por enquanto — a persona continua
empilhando o `.md` inteiro.** A migração completa (persona enxuta + tool
como única fonte de detalhe) foi adiada de propósito: sem crédito de API
pra testar se o modelo usa a tool o suficiente sem a rede de segurança do
contexto já vindo pronto, trocar agora é arriscado sem conseguir validar.

### Pesquisador (conteúdo, não código)

**Busca via `TavilySearch`, client-side (precisa de `TAVILY_API_KEY`).**
Substituiu a antiga `web_search` nativa *server-side* da Anthropic (ver
nota em "Multi-provedor" acima) — o loop de `research_batch` agora executa
a busca de verdade e devolve o resultado como `ToolMessage`, igual
qualquer outra tool deste projeto. Isso tirou o hardcoding em
`provider="anthropic"`: o Pesquisador segue `LLM_PROVIDER` normal, como o
resto do time.

**Nunca confiar no que o modelo AFIRMA ter encontrado — validar contra o
schema real e verificar cada URL de imagem de verdade.** O mesmo gap
estrutural documentado em "O time não conseguia se auto-validar" abaixo
se aplica a conteúdo: o modelo pode dizer que achou uma fonte sem ter
achado, ou montar uma URL de imagem "parecida" com uma real. `validate_batch`
importa o schema Pydantic REAL do backend (não duplicado aqui) e faz uma
requisição HTTP de verdade em cada imagem proposta — descartando só a
imagem (não a entrada inteira) se ela não resolver.

**Sem override de modelo próprio — usa o padrão do provedor ativo**
(`agents/llm.py::_DEFAULT_MODELS`), igual todo papel sem entrada em
`_ROLE_MODELS`. Pesquisa grounded em busca depende mais de seguir regra à
risca (nunca inventar, sempre citar) do que de um modelo mais caro, e o
custo real observado desse papel já é alto por causa da própria busca
(tokens acumulados por resultado), não por precisar do modelo mais caro.

### Interface web e streaming do Supervisor

**`agents/supervisor.py::run` é um gerador, não uma função que devolve a
lista completa no final.** Motivo: `web_ui.py` (Streamlit) precisa
mostrar a decisão de CADA rodada assim que ela acontece — "acompanhar a
conversa do time", não só ver o resultado depois de tudo pronto. Virar
gerador não quebrou o consumidor antigo (`team_supervisor.py`, CLI): um
`for entry in run(task):` funciona igual com generator ou lista, e ganhou
de graça o mesmo streaming no terminal.

**A justificativa da decisão do Supervisor (`Decision.reasoning`) é
emitida pra quem consome o gerador, mas NUNCA entra no histórico
reenviado ao roteador.** Já existia no schema, mas não aparecia em lugar
nenhum antes do `web_ui.py` precisar dela pra exibir "por que o
supervisor escolheu esse papel". Incluí-la no histórico que volta pro
próprio roteador poluiria o contexto com a justificativa anterior do
modelo sobre si mesmo — testado explicitamente (`test_should_not_feed_
supervisor_reasoning_back_into_router_history`).

### Testes e CI

**Nenhum teste chama a API real da Anthropic.** Toda a suíte (63 testes)
usa fakes/stubs/monkeypatch — um chat model falso (`BaseChatModel`
determinístico) pra provar wiring de callback, ou substituição direta de
`create_agent`/`create_agent_with_tools`/`_router` por stubs quando o que
se testa é orquestração, não a chamada em si. Consequência direta: o CI
roda sem nenhum secret configurado no repo.

**Convenção de nome de teste**: `test_should_{o_que}_when_{causa}` —
descreve comportamento, não implementação. Herdado dos padrões reais de
backend auditados, aplicado ao próprio projeto.

---

## Limitações conhecidas / trade-offs em aberto

### O time não conseguia se auto-validar (encontrado no build do fe-catolica)

Depois do primeiro build real, uma revisão manual (Claude Code, sem API)
achou um bug de tipo genuíno (`apiGet<T>` com `ZodType<T>` quebrando a
inferência com schemas `.default()`) e uma dependência com 3 CVEs
críticas (`next@14.2.5`) — nenhum dos dois pego pelo `dev_frontend`
sozinho.

**Causa raiz**: a tarefa proibia "comandos de instalação", regra
copiada sem revisão dos scripts de TESTE rápido (onde faz sentido manter
o loop curto) pros scripts de build REAL. Sem `npm install`, o
`dev_frontend` nunca teve `node_modules` pra rodar `tsc`/`eslint`/
`vitest`/`build` sobre o próprio trabalho — o equivalente a proibir o
`dev_backend` de rodar `pytest`. Isso não é o modelo sendo fraco: é a
tarefa não dar a ferramenta pra ele se checar.

**Corrigido:**
- `run_command` tinha timeout de 60s (curto demais pra instalar
  dependência de verdade — um `npm install` real levou ~2min), subiu
  pra 180s.
- **Auto-validação virou regra permanente da persona, não instrução de
  uma tarefa**: `standards/general.md` ganhou uma seção obrigatória
  (instalar → typecheck/lint/teste/build → `pip-audit`/`npm audit` → só
  então "concluído"), com os comandos exatos em `backend.md`/
  `frontend.md`. Colocar isso no `.md` de padrões — não no texto da
  tarefa — significa que vale pra QUALQUER build futuro automaticamente,
  sem precisar lembrar de repetir a instrução. A proibição antiga de
  instalar foi removida dos scripts do fe-catolica (ficaria contraditória
  com o padrão novo).

**Ainda falta** (ver PROGRESS.md pro detalhe): um papel de revisão/QA no
Supervisor. Os repos reais auditados têm isso explícito
(`quality-reviewer`/`qa-engineer`, até "zero achados"); mesmo com
auto-validação, um agente revisando o PRÓPRIO trabalho pega menos erro
que um segundo papel dedicado a isso — é a parte estrutural do problema
que a mudança acima não resolve sozinha.

### Prompt caching parece quebrado no caminho do AgentExecutor (achado em 2026-09-06, não resolvido)

Análise real de `usage_log.jsonl` (317 chamadas, 3 dias) mostrou
`cache_read`/`cache_creation` em ZERO, em toda chamada, pra
`dev_backend`/`dev_frontend` (ambos via `create_agent_with_tools` →
`AgentExecutor`) — enquanto `pesquisador` (que não usa `AgentExecutor`)
tem cache saudável. A marcação `cache_control` sai correta na
requisição (confirmado sem gastar API, via modelo falso + inspeção do
código-fonte do `langchain_anthropic`), então o suspeito é algo
específico do caminho do `AgentExecutor` — não confirmado por completo
por falta de crédito de API pra rodar um teste real. `cache_probe.py`
(raiz do repo) está pronto pra confirmar assim que houver saldo: manda a
mesma tarefa mínima duas vezes seguidas e mostra os 4 contadores de uso
lado a lado. Isso importa porque caching é o maior lever de custo do
projeto (ver seção "Custo" acima) e está efetivamente desligado nos dois
papéis que mais gastam.

### Outras

- `search_standards` e a persona "cheia" convivem sem necessidade real
  hoje — redundância aceita até haver disposição pra validar uma migração.
- BM25 não generaliza bem pra pergunta em linguagem muito diferente do
  vocabulário do documento (paráfrase forte) — funciona porque nossos
  `.md` usam termos técnicos exatos que o usuário também tende a usar.
- O histórico do Supervisor (`history: list[str]`) cresce sem limite
  dentro de `MAX_ROUNDS` — não dá pra recuperar de uma queda de rede no
  meio (ver o incidente real do fe-catolica, PROGRESS.md); um resume
  automático precisaria persistir esse histórico em disco a cada rodada.
