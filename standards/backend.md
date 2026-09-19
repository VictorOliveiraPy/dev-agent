# Backend Standards

> Clean Architecture (Uncle Bob) adapted from two real FastAPI backends in
> production — `melhorperfil-api` (processes real payments via Pix) and
> `santo-guardiao-api` — not generic internet opinion. Mindset: senior
> engineer + security auditor. Treat any validation/authorization/money bug
> as a security incident, not a regular bug.

---

## 🏗️ Layered architecture — Clean Architecture, organized by domain

Four layers, same responsibilities every time. **The dependency rule is not
optional**: dependencies only point inward. `interface` depends on
`application`, `application` depends on `domain`. `domain` and
`application` never import FastAPI, SQLAlchemy, httpx, or anything else
framework-specific — they're plain Python. `infrastructure` is the only
layer allowed to import a framework/driver, and it depends on `domain`
(it implements `domain`'s interfaces), never the other way around.

```text
app/
  domain/                        # Enterprise business rules — no I/O, no framework
    <domain>/
      entities.py                 # Entities/value objects (dataclass or plain class — not an ORM model, not a Pydantic API schema)
      repository.py               # Abstract repository interface (typing.Protocol or ABC) — the CONTRACT only
      exceptions.py               # Domain-specific exceptions, if the domain needs its own (else use core/exceptions.py)

  application/                    # Use cases — application-specific business rules
    <domain>/
      <verb>_<noun>_use_case.py   # e.g. place_bid_use_case.py — orchestrates entities + the repository interface

  infrastructure/                 # Frameworks & drivers — concrete implementations of domain interfaces
    database.py                   # engine/session setup
    <domain>/
      models.py                    # SQLAlchemy ORM models (mirror entities.py, don't reuse the class)
      sqlalchemy_repository.py     # implements domain/<domain>/repository.py

  interface/                      # Interface adapters — the thinnest layer, talks to the outside world
    <domain>/
      router.py                    # parses request → calls one use case → serializes response. No business logic, no direct SQL, no direct repository access
      schemas.py                   # Pydantic request/response DTOs (mirror entities.py, don't reuse the class)

  core/                           # Cross-cutting, needed by every layer: config.py, security.py (JWT), exceptions.py (base hierarchy), logging.py, rate limiting, middlewares
```

> **Never:** business logic in a route, a route calling a repository
> directly (it must go through a use case), SQL scattered around, a domain
> entity that's also the SQLAlchemy model or the Pydantic schema (three
> different classes, three different jobs — a domain change shouldn't force
> an API contract change or vice versa), a bare `except Exception` with no
> context, hardcoded business values (that's what `Settings` is for).

### DRY over ceremony — don't multiply near-duplicate domains

Clean Architecture's goal is isolating business rules from frameworks — it
is **not** "one use case class per CRUD operation no matter what." When a
project has many structurally identical domains (e.g., dozens of read-only
content categories with the same shape, or a handful of near-identical CRUD
resources with no distinct business rules), a use case per domain produces
boilerplate that violates DRY far more than it protects the architecture.

- **One real use case per domain** when the domain has actual business
  rules: validation, side effects, orchestration across repositories, a
  state machine, money changing hands. This is where the separation earns
  its cost — a bid domain, a payment domain, an auth domain.
- **One generic, parametrized use case/repository** when many domains
  share the exact same shape and have no distinct rules — the domain
  identifier becomes data, not a class name. `GetEntryUseCase(category:
  str, slug: str)` over `GetSantoUseCase` + `GetPapaUseCase` + 47 more.
  Route the generic use case's domain parameter through a small registry
  or enum, not a `match`/`if` chain that special-cases each one.
- When in doubt, ask: "if a new rule appeared for just one of these
  domains, would I actually want it isolated from the others?" If yes,
  it's a real domain — split it. If every domain would need the exact same
  change at the exact same time, it's one generic case wearing 49 hats —
  keep it generic.

## ⚙️ Configuration — `pydantic-settings`, never scattered `os.getenv`

A single `Settings(BaseSettings)` in `app/core/config.py`, `lru_cache`d
getter (singleton, read once):

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

- `@model_validator(mode="after")` for security invariants that only apply
  in production — **boot fails** (`raise ValueError`) if `DEBUG=True` in
  prod, `SECRET_KEY` is a placeholder or under 32 characters, or
  `CORS_ORIGINS` has a wildcard in production. Failing at boot is always
  better than running insecure.
- `@field_validator("*", mode="before")` normalizes values coming from
  `.env` (empty string → `None`, `"true"/"1"/"yes"` → `bool`) — avoids the
  classic bug of comparing the string `"False"` to a `bool` and getting
  `True` by accident.
- An optional feature (Redis, Sentry) turns itself off when its dependency
  isn't configured, instead of crashing the whole boot over it.

## 🧨 Errors — typed domain exceptions, never `HTTPException` in a use case

The hierarchy lives in `app/core/exceptions.py` (or `domain/<domain>/
exceptions.py` for a domain-specific one, subclassing the base); each one
already carries `status_code` + `code` (a stable string — the contract with
the frontend) + `details`:

```python
class AppException(Exception):
    def __init__(self, message: str, status_code: int, code: str,
                 details: dict | None = None) -> None:
        ...

class NotFoundException(AppException):
    def __init__(self, message="Resource not found", details=None) -> None:
        super().__init__(message, status_code=404, code="NOT_FOUND", details=details)
```

A central `exception_handlers.py` (interface layer) converts this into an
HTTP response — the **use case** raises `NotFoundException`, never an
`HTTPException` (that's an HTTP concept, and `application`/`domain` don't
know what HTTP is). The message is UX (free to change); `code` is a
contract (the frontend branches on it — don't change it without notice).

## 🔒 Security — non-negotiable

- **IDOR is enemy #1.** Every repository method that fetches a user's
  resource filters by owner **in the same query** — never fetch by id and
  check ownership afterward, and never in the use case after the
  repository already returned someone else's row:

  ```python
  # insecure — any authenticated user can reach anyone else's item
  item = session.get(Item, item_id)

  # correct — the ownership filter is part of the query, not an "if" after
  item = session.query(Item).filter(
      Item.id == item_id, Item.user_id == current_user.id,
  ).first()
  ```

- **JWT**: always validate `exp`, `iat`, `sub`; reject tokens with
  `alg=none`; rotate refresh tokens — if an already-rotated token reappears,
  that's a theft signal: invalidate the user's **entire session family**,
  not just that token.
- **Secret comparison is always constant-time**: `secrets.compare_digest(a, b)`,
  never `a == b` (avoids timing attacks) — applies to any edge header/token
  compared server-side.
- **Fail closed, always.** Any security check with an ambiguous result
  (signature verification error, timeout on an external check) **rejects**
  the request. Never let it through by omission or an unhandled exception.
- **CORS**: never `allow_origins=["*"]` combined with `allow_credentials=True`;
  in production, an explicit origin list, no wildcard.
- **Webhook idempotency**: the same event must not be processed twice or
  create a duplicate — record the processed event id and check it before
  acting, don't trust the provider to only send it once.
- **Money is an integer (cents), never a float.** Concurrency on
  balance/bid/stock updates: an atomic conditional update in the database
  (`UPDATE ... WHERE current_value < :new_value`) or `SELECT ... FOR UPDATE`
  — never read, compute in Python, and write back in separate steps without
  a lock (a classic race condition). This belongs in the
  `infrastructure` repository implementation, behind the domain interface
  — the use case orchestrates, it doesn't issue raw SQL.

## 📋 Logging — structured, never an f-string, never sensitive data

```python
logger.info("Usuário autenticado", extra={"user_id": user.id})  # ✅ correct
logger.info(f"Usuário {user.id} autenticado")                    # ❌ wrong
```

`extra={...}` keeps the field searchable/filterable in production; an
f-string turns into loose text and loses structure. Never log: passwords,
full tokens/JWTs, national ID numbers, the `Authorization` header, raw
webhook payloads with payment data.

> Log message text stays in Portuguese (see [general.md](general.md)) — it's
> human-facing text, not a code identifier.

## ✅ Testing — TDD, name describes behavior, not implementation

Mandatory naming convention:

```
test_should_{what}_when_{cause}
```

```python
def test_should_reject_token_when_required_jwt_claims_are_missing(): ...
def test_should_charge_only_difference_when_owner_reinforces_bid(): ...
def test_should_return_403_when_user_accesses_resource_from_another_user(): ...
```

- Write the test **before** the code (red → green → refactor). Production
  code without a test that preceded it is not accepted — the test drives
  the implementation, it isn't checked off afterward.
- Test body in Given/When/Then (comment), with a one-line, to-the-point
  docstring (not a restatement of the function name in prose).
- Test each layer at the level it belongs to, with the layers below it
  faked — that's what the dependency rule buys you:
  - `tests/domain/` — entities and any domain logic, zero I/O.
  - `tests/application/` — one use case at a time, with a **fake**
    implementation of its repository interface (an in-memory dict is
    usually enough) — this is where most business-rule tests live, and
    they run without a database.
  - `tests/infrastructure/` — the real repository against a real (test)
    database — confirms the SQL/ORM mapping actually works, not the
    business rule (already covered above).
  - `tests/interface/` — real `TestClient`, end-to-end through the router,
    confirms wiring (status codes, serialization) — not business-rule
    edge cases (already covered in `application`).
- Minimum coverage: `fail_under = 70` in `[tool.coverage.report]`.

## 🛠️ Tooling — reference config (`pyproject.toml`)

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

**Commands:** `ruff check app tests` · `mypy app` · `pytest -q --cov` ·
`uvicorn app.main:app --reload`

## ✅ Before declaring the backend done

Per [general.md](general.md), self-validation is mandatory, not optional.
For a backend task specifically, run — via `run_command` — in this order,
and fix anything that fails before moving on:

1. `pip install -r requirements.txt` (once, if not already installed).
2. **Dependency-rule check** — grep for a framework import
   (`fastapi`, `sqlalchemy`, `httpx`) inside `app/domain/` and
   `app/application/`. Any match is a violation: move the import to
   `infrastructure` or `interface`, or the layer boundary isn't real.
3. `ruff check app tests` — lint.
4. `mypy app` — type check.
5. `pytest -q` — the test suite. A red test is a blocked task, not a
   footnote in the final report.
6. If you added or changed a dependency: `pip install pip-audit && pip-audit`
   (or `pip list --outdated` if that fails to install). A high/critical
   finding on a production dependency gets bumped to a patched version in
   the same major line before you finish — don't ship a dependency you
   know is vulnerable because "it still runs".
