# Design & UX Standards

> Adaptado da própria guidance de design da Anthropic (skill `artifact-design`)
> pra parar de produzir interface com "cara de feito por IA" — genérica, sem
> hierarquia, sem identidade, difícil de escanear. Isso se soma às convenções
> de engenharia de [frontend.md](frontend.md), não as substitui.

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
