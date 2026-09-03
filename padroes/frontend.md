# Frontend Standards

> Baseline conventions for the React side of generated projects. Lighter than
> [backend.md](backend.md) for now — it hasn't been audited against a real
> production frontend codebase yet. Edit freely as real preferences emerge.

---

## ⚛️ Stack

- Default framework: **React** with **Vite**.

## 🗂️ State management

- Global state (auth, shared data) via the **Context API** — no external
  state-management library unless the project genuinely calls for one.

## 🌐 API calls

- Centralize API calls under `src/api/` — never a loose `fetch` inside a
  component. Keeps request shape, error handling, and base URL in one place
  instead of scattered across the UI.
