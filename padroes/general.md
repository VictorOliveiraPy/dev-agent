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
