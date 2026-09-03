# General Team Standards

> Rules that apply to **any role**, in any language. Edit this file freely —
> agents re-read it on every run, no Python code needs to change.

---

## 🌐 Language

**Code in English, docstrings/comments in Portuguese.**

| What | Language |
|---|---|
| Variables, functions, classes, parameters | English |
| Module and `.py` file names | English |
| Docstrings and comments | Portuguese |
| Log messages, error text shown to a human | Portuguese |

```python
def create_agent(role: str) -> Runnable:      # ✅ English identifier
    """Monta a chain LCEL do papel dado."""    # ✅ Portuguese docstring
    ...
```

## 📝 Documentation

- Every public function has a docstring explaining **what** it does and,
  when it isn't obvious, **why** — not just a paraphrase of the signature.
- A comment earns its place by explaining a decision a reader couldn't
  infer from the code itself; it doesn't restate what the code says.

## 🏗️ Structure

- Prefer a few well-organized files over many small ones. Only split into
  modules when it genuinely reduces complexity — splitting for its own
  sake adds indirection without paying for itself.

## 🚨 Error handling

- Handle errors explicitly. Never swallow an exception silently — a bare
  `except: pass` hides bugs instead of fixing them.

## ✅ Mandatory self-validation before declaring a task done

A task is not finished when the file is written — it's finished when it
runs. Before reporting a task as complete:

1. **Install dependencies** if the project needs them (`pip install -r
   requirements.txt`, `npm install`) — this is expected for real project
   work, not just allowed. A task that skips this can't check its own
   work at all.
2. **Run the project's own verification commands** — typecheck, lint,
   tests, build (see the role-specific standard, e.g.
   [backend.md](backend.md) / [frontend.md](frontend.md), for the exact
   commands). Use `run_command` for this.
3. **Fix what's broken** before moving on — a failing check found by you
   is much cheaper than one found later by someone else.
4. **Check for known-vulnerable dependencies** (`pip-audit`, `npm audit`)
   when you install or change a dependency, and prefer a patched version
   in the same major line when one exists.

Skipping this isn't "moving faster" — a task that was never run is not
verified, it's a guess. (This was a real gap: an earlier version of this
project's task instructions banned install commands to keep quick test
runs fast, and that ban was copied uncritically into real project
builds — see the dev-agent's own ARCHITECTURE.md for the story.)
