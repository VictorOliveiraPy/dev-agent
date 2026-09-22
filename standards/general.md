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

## ✍️ Prose that doesn't read as AI-generated

Applies to anything meant for a human to read as writing — commit
messages, PR/README text, error messages, docstring prose (not the
line-by-line code itself). Based on the `humanizer` skill (Wikipedia's
"Signs of AI writing") — this is the distilled version; run `/humanizer`
on a specific paragraph if it still feels off after applying these.

- State the point directly. Don't stage it ("It's not just X, it's Y",
  "Honestly? It depends...") — just say X or Y.
- No forced triads ("fast, reliable, and scalable") when the fact needs
  one or two words, not three.
- No inflated significance ("marks a pivotal moment", "the future looks
  bright") — state the fact and stop.
- No stock AI vocabulary: *delve, testament, landscape, showcasing,
  leverage, robust, seamless*. Use the plain word.
- No decorative bold/headings, emoji-as-bullet, or a heading immediately
  repeated as the first sentence under it.
- No chatbot residue ("Great question!", "Hope this helps!", "Let's dive
  in") — this is written output, not a chat reply.
- Never invent a detail (name, number, date, claim) to fill a gap — say
  what's actually known, or ask.

## 📝 Documentation

- Every public function has a docstring explaining **what** it does and,
  when it isn't obvious, **why** — not just a paraphrase of the signature.
- A comment earns its place by explaining a decision a reader couldn't
  infer from the code itself; it doesn't restate what the code says.

## 🏗️ Structure — depth over sprawl

Prefer a few well-organized files over many small ones. Before extracting a
helper, adding a layer of indirection, or introducing an interface "for
testability," apply two checks (distilled from a "module depth" school of
thought — Ousterhout's *A Philosophy of Software Design*):

- **The deletion test.** Imagine deleting the module/function. If the
  complexity it held vanishes, it was a pass-through — inline it back. If
  the complexity reappears at every caller, it was earning its keep.
- **One adapter is a hypothetical seam; two is a real one.** Don't
  introduce an interface/port because "we might swap this later" —
  introduce it when a second real implementation (a fake used in tests
  counts) already needs it. The repository interfaces in
  [backend.md](backend.md)'s layered architecture are the exception: the
  layering itself requires them, independent of this rule.

A **deep** module hides real behavior behind a small, clear interface. A
**shallow** one has an interface almost as complex as what's inside —
it adds a name to learn without paying for itself. One deep module beats
three shallow ones that each require reading the others to understand it.
Applies to backend layers and frontend components alike: a component split
into five files that always change together isn't more testable, it's just
more to navigate.

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
