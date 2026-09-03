# Padrões gerais do time

Regras que valem para QUALQUER papel do time, em qualquer linguagem.
Edite este arquivo livremente — os agentes releem o conteúdo a cada execução,
nenhum código Python precisa mudar.

- Nomes de domínio (variáveis, funções, classes de negócio) em português;
  termos técnicos genéricos (`request`, `response`, `config`) podem ficar
  em inglês quando for mais idiomático na linguagem.
- Toda função pública tem docstring explicando o quê e, quando não for
  óbvio, por quê — não apenas repetir a assinatura em prosa.
- Prefira poucos arquivos bem organizados a muitos arquivos pequenos; só
  separe em módulos quando isso reduzir complexidade de verdade.
- Trate erros explicitamente; nunca engula uma exceção em silêncio.
