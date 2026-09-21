# Atribuição

Os sprites `char_0.png` a `char_5.png` nesta pasta vêm de
[pixel-agents-hq/pixel-agents](https://github.com/pixel-agents-hq/pixel-agents)
(licença MIT — ver
[LICENSE](https://github.com/pixel-agents-hq/pixel-agents/blob/main/LICENSE)),
baixados diretamente do repositório deles. O README de lá credita o pack
de personagens a
["JIK-A-4, Metro City"](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack).

Usados aqui só pelo visual — não fazem parte do código deles, e o
`office/` deste projeto não integra com o pixel-agents (que observa
sessões do Claude Code no terminal; `agents/supervisor.py` é um loop
próprio, não uma sessão do Claude Code). O layout de cada folha
(112x96px: 3 linhas — baixo/cima/direita — x 7 colunas de 16x32px: 0-2
caminhada, 3-4 digitando, 5-6 lendo) foi confirmado lendo
`webview-ui/src/office/sprites/spriteData.ts` e
`webview-ui/src/office/engine/characters.ts` do repositório original, não
adivinhado por inspeção visual isolada.
