# Padrões de backend (destilados de projetos reais em produção)

Baseado em auditoria de dois backends FastAPI reais do autor —
`melhorperfil-api` (processa pagamento via Pix) e `santo-guardiao-api` —
não é opinião genérica de internet. Persona: engenheiro sênior + auditor
de segurança. Trate qualquer bug de validação/autorização/dinheiro como
incidente de segurança, não como bug comum.

## Arquitetura em camadas — sempre as mesmas responsabilidades

- `app/core/` — config (`config.py`), banco (`database.py`), segurança/JWT
  (`security.py`), exceções (`exceptions.py` + `exception_handlers.py`),
  logging (`logging.py`), rate limit, middlewares.
- `app/models/` — um arquivo por domínio (SQLAlchemy).
- `app/schemas/` — Pydantic, espelha os models (request/response).
- `app/routers/` — rotas FINAS: parse de entrada, chamada ao service,
  serialização de saída. Nenhuma regra de negócio, nenhum SQL direto.
- `app/services/` — toda regra de negócio mora aqui. É o que se testa
  unitariamente com banco fake, sem subir a API inteira.
- `app/routers/deps.py` — dependências reutilizáveis de auth/autorização
  via `Depends` (ex: `get_current_user`, `get_current_admin_user`).

Nunca: lógica de negócio na rota, SQL espalhado, `except Exception`
genérico sem contexto, hardcode de valor de negócio (isso é `Settings`).

## Configuração — `pydantic-settings`, nunca `os.getenv` espalhado pelo código

Um único `Settings(BaseSettings)` em `app/core/config.py`, com `lru_cache`
no getter (singleton, lido uma vez):

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

- `@model_validator(mode="after")` para invariantes de segurança que só
  valem em produção — o **boot falha** (`raise ValueError`) se `DEBUG=True`
  em produção, `SECRET_KEY` for um placeholder ou tiver menos de 32
  caracteres, ou `CORS_ORIGINS` tiver wildcard em produção. Falhar no boot
  é sempre preferível a subir inseguro.
- `@field_validator("*", mode="before")` normaliza valores vindos do
  `.env` (string vazia -> `None`, `"true"/"1"/"yes"` -> `bool`) — evita bug
  de comparar string `"False"` com `bool` e ela dar `True` por engano.
- Feature opcional (Redis, Sentry) desliga sozinha se a dependência não
  estiver configurada, em vez de quebrar o boot inteiro por causa dela.

## Erros — exceção de domínio tipada, nunca `HTTPException` espalhada pelo service

Hierarquia própria em `app/core/exceptions.py`; cada uma já carrega
`status_code` + `code` (string estável — contrato com o frontend) +
`details`:

```python
class AppException(Exception):
    def __init__(self, message: str, status_code: int, code: str,
                 details: dict | None = None) -> None:
        ...

class NotFoundException(AppException):
    def __init__(self, message="Resource not found", details=None) -> None:
        super().__init__(message, status_code=404, code="NOT_FOUND", details=details)
```

Um `exception_handlers.py` central converte isso em resposta HTTP — o
`service` levanta `NotFoundException`, nunca monta `HTTPException` no meio
da regra de negócio. Mensagem é UX (pode mudar à vontade); `code` é
contrato (o frontend decide comportamento por ele — não muda sem
avisar quem consome).

## Segurança — inegociável

- **IDOR é o erro nº 1 a evitar.** Toda query que busca um recurso do
  usuário filtra pelo dono NA MESMA query — nunca busca por id e checa
  dono depois:
  ```python
  # inseguro — qualquer usuário autenticado acessa o item de qualquer outro
  item = session.get(Item, item_id)

  # correto — o filtro de posse faz parte da query, não é um "if" depois
  item = session.query(Item).filter(
      Item.id == item_id, Item.user_id == current_user.id,
  ).first()
  ```
- **JWT**: validar `exp`, `iat`, `sub` sempre; rejeitar token com
  `alg=none`; refresh token com rotação — se um token já rotacionado
  reaparecer, isso é sinal de roubo: invalida a família inteira de sessões
  daquele usuário, não só aquele token.
- **Comparação de segredo é sempre em tempo constante**:
  `secrets.compare_digest(a, b)`, nunca `a == b` (evita timing attack) —
  vale pra qualquer header/token de borda comparado no servidor.
- **Fail-closed sempre**: qualquer validação de segurança com resultado
  ambíguo (erro ao verificar assinatura, timeout numa checagem externa)
  REJEITA a request. Nunca deixa passar por omissão/exceção não tratada.
- **CORS**: nunca `allow_origins=["*"]` combinado com
  `allow_credentials=True`; em produção, lista explícita de origens, sem
  wildcard.
- **Idempotência em webhook**: o mesmo evento não pode ser processado duas
  vezes nem gerar duplicidade — registrar o id do evento já processado e
  checar antes de agir, não confiar que o provedor só manda uma vez.
- **Dinheiro é inteiro (centavos), nunca float.** Concorrência em
  atualização de saldo/lance/estoque: update atômico condicional no banco
  (`UPDATE ... WHERE valor_atual < :novo_valor`) ou
  `SELECT ... FOR UPDATE` — nunca ler, calcular em Python e escrever de
  volta em passos separados sem lock (race condition clássica).

## Logging — estruturado, nunca f-string, nunca dado sensível

```python
logger.info("Usuário autenticado", extra={"user_id": user.id})  # certo
logger.info(f"Usuário {user.id} autenticado")                    # errado
```

O `extra={...}` mantém o dado pesquisável/filtrável em produção; f-string
vira texto solto, perde estrutura. Nunca logar: senha, token/JWT completo,
CPF, header `Authorization`, payload cru de webhook com dado de pagamento.

## Testes — TDD, nome descreve comportamento, não implementação

Convenção obrigatória de nome:

```
test_should_{o_que}_when_{causa}
```

```python
def test_should_reject_token_when_required_jwt_claims_are_missing(): ...
def test_should_charge_only_difference_when_owner_reinforces_bid(): ...
def test_should_return_403_when_user_accesses_resource_from_another_user(): ...
```

- Escreva o teste ANTES do código (red -> green -> refactor). Código de
  produção sem teste que o precedeu não é aceito — o teste guia a
  implementação, não é conferido depois.
- Corpo do teste em Given/When/Then (comentário), com docstring de uma
  linha objetiva (não repete o nome da função por extenso).
- Separe unitário (`tests/services/`, `tests/core/` — regra de negócio
  isolada, banco fake, sem I/O real) de integração (`tests/routers/`,
  `TestClient` real, banco de teste, fluxo ponta a ponta).
- Cobertura mínima: `fail_under = 70` em `[tool.coverage.report]`.

## Ferramentas — config de referência (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "S", "SIM"]
ignore = ["E501", "B008", "S101", "S105", "S106"]

[tool.mypy]
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.coverage.report]
fail_under = 70
```

Comandos: `ruff check app tests` · `mypy app` · `pytest -q --cov` ·
`uvicorn app.main:app --reload`
