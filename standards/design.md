# Design & UX Standards

> Adaptado da própria guidance de design da Anthropic (skill `artifact-design`)
> pra parar de produzir interface com "cara de feito por IA" — genérica, sem
> hierarquia, sem identidade, difícil de escanear. Isso se soma às convenções
> de engenharia de [frontend.md](frontend.md), não as substitui.

---

## 🧠 7 conceitos de UX por trás destas regras

Teoria de usabilidade estabelecida, não opinião — cada regra abaixo (cara de
IA, paleta, hierarquia, copy...) é uma aplicação prática de um destes 7
conceitos. Quando uma decisão de UI não tiver regra explícita cobrindo, volte
pra estes princípios em vez de adivinhar.

### 1. Os dois golfos (Norman)

Toda interação tem dois pontos onde o usuário se perde: o **golfo de
execução** ("o que eu clico pra fazer isso?") e o **golfo de avaliação** ("deu
certo? o que mudou?"). Uma tela só está completa quando fecha os dois — não
adianta a ação estar clara se o resultado dela fica invisível.

- Golfo de execução: o controle certo parece controle (botão parece
  clicável, campo parece editável) e o rótulo diz a ação, não o mecanismo
  interno (ver "Copy é material de design" abaixo).
- Golfo de avaliação: toda ação dá feedback imediato e legível — um toast,
  uma mudança de estado visível, um item que aparece na lista. Nunca deixar
  o usuário adivinhar se o clique "pegou".

### 2. Dez heurísticas (Nielsen)

As que mais pesam em ferramenta/dashboard (não é a lista completa — é a que
importa no dia a dia):

- **Visibilidade do estado do sistema**: loading, sucesso, erro e vazio são
  estados distintos e visíveis, nunca a mesma tela "em branco" pros três.
- **Controle e liberdade do usuário**: toda ação destrutiva ou de múltiplos
  passos tem como desfazer ou cancelar — nunca uma via de mão única.
- **Consistência e padrões**: o mesmo componente se comporta igual em toda a
  interface; uma exceção sem motivo é bug, não variedade.
- **Prevenção de erro > boa mensagem de erro**: um campo que já valida antes
  do submit vale mais que a melhor mensagem de erro depois.
- **Reconhecer, não lembrar**: opções visíveis (menu, breadcrumb) em vez de
  exigir que o usuário memorize um caminho ou comando.

### 3. Atributos pré-atentivos (Ware)

Cor, tamanho, orientação, forma e movimento são percebidos em <200ms, antes
de qualquer leitura consciente — é isso que faz um elemento "saltar aos
olhos" sem o usuário precisar procurar. Use pra hierarquia real (o que
precisa ser visto primeiro), não decoração:

- Reserve um atributo pré-atentivo (cor de destaque, por exemplo) pro que é
  realmente prioritário — se tudo pisca ou tudo é vermelho, nada se destaca
  (mesma ideia de "nem tudo é card" em Layout e espaçamento, abaixo).
- Combine no máximo 2 atributos pra uma mesma hierarquia (cor + tamanho, por
  ex.) — empilhar todos ao mesmo tempo cria ruído, não clareza.

### 4. Acessibilidade como restrição, não feature extra

Acessibilidade decidida DEPOIS do visual pronto sempre fica pior e mais cara
de corrigir — trate como restrição de design desde a primeira decisão de
paleta/layout, igual a "decida a paleta antes do código" abaixo:

- Contraste mínimo AA (4.5:1 texto normal, 3:1 texto grande) — verificar na
  hora de escolher a paleta, não depois.
- Navegável 100% por teclado, com ordem de foco lógica e foco sempre visível.
- Estado nunca comunicado só por cor (ver "cor semântica" abaixo) — sempre
  com um segundo sinal (ícone, texto, padrão).

### 5. Divulgação progressiva e custo de interação (Fitts, Krug)

Lei de Fitts: quanto maior e mais perto do cursor/dedo um alvo, mais rápido e
com menos erro ele é atingido — a ação primária de uma tela é o alvo maior e
mais ao alcance, nunca do mesmo tamanho que uma ação secundária rara. "Não me
faça pensar" (Krug): cada decisão que o usuário precisa tomar pra entender a
tela é custo de interação — divulgação progressiva reduz esse custo
mostrando só o essencial primeiro:

- Configuração avançada/rara fica atrás de um passo extra ("Mais opções"),
  nunca lotando a tela principal por igual à ação comum.
- Ação primária de uma tela é visualmente maior/mais isolada que as demais —
  nunca um grupo de botões do mesmo peso competindo por atenção.

### 6. Lei de Jakob e orçamento de atenção

O usuário passa a maior parte do tempo em OUTROS produtos — ele chega
esperando que o seu funcione como os que ele já conhece (posição de menu,
ícone de carrinho, gesto de swipe). Reinventar o óbvio gasta orçamento de
atenção que o usuário tem finito — e esse orçamento deveria ir pro que
realmente diferencia o produto, não pra ele reaprender navegação básica.

- Convenção conhecida (ícone, posição, atalho) vence originalidade, exceto
  onde a originalidade É o produto.
- Gaste a "cota de novidade" da interface no que importa (o dado, a
  decisão), não em componentes de UI reinventados sem motivo.

### 7. Inclusão por padrão

Desenhar pro "caso médio" e tratar o resto como exceção depois é como
acessibilidade mal-feita nasce — pense nos extremos desde a primeira versão,
não como polimento final:

- Idioma/localização, tela pequena, conexão lenta, dispositivo antigo,
  capacidade motora ou visual diferente — fazem parte do desenho, não são
  "casos extras" a tratar depois se sobrar tempo.
- Se a interface só funciona no caminho feliz (usuário rápido, tela grande,
  conexão boa, sem deficiência), ela não está pronta — está incompleta.

---

## 🚫 Evite a "cara de IA"

Design gerado por IA se agrupa em uns poucos clichês bem reconhecíveis.
Não usar nenhum deles como default — só se o projeto pedir de propósito:

- Creme quente (`#F4F1EA`) + serifada + terracota.
- Quase-preto com um único acento neon (verde-ácido, vermelhão).
- Rules finas estilo jornal com colunas densas.
- Hero com gradiente roxo-pra-azul em fundo branco.
- Inter ou Space Grotesk como fonte "segura" default.
- Emoji como marcador de seção.
- Tudo centralizado.
- `rounded-lg` em absolutamente tudo.
- Barra de acento lateral em card arredondado.

Se o usuário pedir um desses de propósito, usa — a preferência dele sempre
ganha. O problema é usar por padrão, sem decisão nenhuma por trás.

## 🎨 Decida a paleta e a tipografia ANTES do código

Antes de escrever o primeiro componente, decida (poucas frases, não precisa
de doc formal):

- **Cor**: 4 a 6 cores nomeadas — não deixar a paleta default do Tailwind
  sem revisão.
- **Tipografia**: pelo menos 2 fontes com papéis diferentes (display/título
  e corpo de texto) — nunca a fonte padrão do starter do framework, sem
  decisão.
- **Layout**: o conceito em 1-2 frases (ex: "sidebar fixa + conteúdo em
  cards de largura igual", não "um layout comum de dashboard").

Neutros (cinza) são ESCOLHIDOS, não herdados — um cinza com leve viés de
matiz pra cor de destaque do projeto lê como intencional; cinza puro lê
como não pensado. Centralize essas decisões em tokens (cores, escala de
espaçamento, escala tipográfica) reaproveitados em todo componente — nunca
valor solto espalhado pelo código.

## ✍️ Tipografia

- Empareje uma fonte de destaque (títulos) com uma de corpo — nunca a dupla
  que o framework já vem configurado.
- Defina uma escala tipográfica e siga ela em toda a interface.
- Texto corrido: em torno de 65 caracteres de largura confortável.
- Títulos e corpo de texto precisam de respiro (`line-height`,
  `margin`/`gap`) — não espremer.

## 🗂️ Layout e espaçamento

- Espaçamento entre elementos-irmãos via `flex`/`grid` + `gap` — não margem
  espalhada que colapsa ou dobra silenciosamente.
- **Elementos repetidos são UM objeto consistente**: cards de uma lista,
  linhas de uma tabela — mesma borda, mesmo padding, mesma altura de
  baseline entre eles. Um card diferente dos irmãos na mesma lista é bug
  visual, não variação.
- **Nem tudo é card.** Borda, preenchimento, raio e sombra dizem "isto é um
  objeto separado, importante" — gaste isso por papel (destacar o que
  precisa), não carimbe o mesmo raio/sombra em todo bloco por igual (achata
  a hierarquia em vez de criar uma).

## 🧭 Usabilidade — "fácil do usuário encontrar tudo"

- Um dashboard/ferramenta é **escaneado**, não lido de cima a baixo: o
  resumo vem antes do detalhe.
- Estado se comunica visualmente, não só em número — um badge/chip/cor de
  severidade, não só um texto solto.
- O que é interativo PRECISA parecer interativo (botão parece clicável,
  estado desabilitado parece desabilitado).
- Cor semântica (sucesso/aviso/erro) é separada da cor de destaque da marca
  — não reaproveitar o accent da marca também como cor de status.

## ✏️ Copy é material de design, não enfeite

- Nomeie as coisas como o USUÁRIO pensa nelas, não como o sistema é
  construído por dentro (a pessoa gerencia "notificações", não "webhook
  config").
- Botão/ação em voz ativa, dizendo exatamente o que vai acontecer
  ("Publicar", seguido de confirmação "Publicado").
- Mensagem de erro explica o que deu errado E como resolver — nunca vaga,
  nunca em tom de desculpa genérica.

## 🌗 Os dois temas (se o projeto tiver dark mode)

- Desenhe os dois de propósito — não é só inverter a cor. Todo elemento
  pega a cor do MESMO conjunto de tokens que a superfície ao redor dele,
  nunca um valor fixo específico de um componente só.

## 🖼️ Mostre um estado real

- A tela, ao carregar pela primeira vez, mostra dado de exemplo realista
  (ou o dado de verdade do usuário) — nunca uma casca vazia sem nenhuma
  prova visual do que a tela faz.
