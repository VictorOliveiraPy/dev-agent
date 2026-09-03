# Backend Standards

> Distilled from two real FastAPI backends in production — `melhorperfil-api`
> (processes real payments via Pix) and `santo-guardiao-api` — not generic
> internet opinion. Mindset: senior engineer + security auditor. Treat any
> validation/authorization/money bug as a security incident, not a regular bug.

---

## 🏗️ Layered architecture

Same responsibilities, every time:

| Layer | Responsibility |
|---|---|
| `app/core/` | config (`config.py`), database (`database.py`), auth/JWT (`security.py`), exceptions (`exceptions.py` + `exception_handlers.py`), logging (`logging.py`), rate limiting, middlewares |
| `app/models/` | one file per domain (SQLAlchemy) |
| `app/schemas/` | Pydantic, mirrors the models (request/response) |
| `app/routers/` | **thin** routes: parse input, call the service, serialize output. No business logic, no direct SQL |
| `app/services/` | all business logic lives here — this is what gets unit-tested with a fake DB |
| `app/routers/deps.py` | reusable auth/authorization dependencies via `Depends` (e.g. `get_current_user`) |

> **Never:** business logic in a route, SQL scattered around, a bare
> `except Exception` with no context, hardcoded business values (that's what
> `Settings` is for).

## ⚙️ Configuration — `pydantic-settings`, never scattered `os.getenv`

A single `Settings(BaseSettings)` in `app/core/config.py`, `lru_cache`d getter
(singleton, read once):

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

## 🧨 Errors — typed domain exceptions, never `HTTPException` scattered in services

A dedicated hierarchy in `app/core/exceptions.py`; each one already carries
`status_code` + `code` (a stable string — the contract with the frontend) +
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

A central `exception_handlers.py` converts this into an HTTP response — the
`service` raises `NotFoundException`, never builds an `HTTPException` in the
middle of business logic. The message is UX (free to change); `code` is a
contract (the frontend branches on it — don't change it without notice).

## 🔒 Security — non-negotiable

- **IDOR is enemy #1.** Every query that fetches a user's resource filters
  by owner **in the same query** — never fetch by id and check ownership
  afterward:

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
  a lock (a classic race condition).

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
- Separate unit tests (`tests/services/`, `tests/core/` — isolated business
  logic, fake DB, no real I/O) from integration tests (`tests/routers/`,
  real `TestClient`, test database, end-to-end flow).
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
