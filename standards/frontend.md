# Frontend Standards

> Distilled from two real Next.js frontends in production —
> `melhorperfil-web` and `santo-guardiao-web` (the latter is the canonical
> source both repos reuse patterns from) — not generic internet opinion.
> Mirrors the rigor of [backend.md](backend.md).

---

## ⚛️ Stack

- **Next.js (App Router) + React + TypeScript.** Not a Vite SPA — SSR/SSG
  is the reason to use Next.js in the first place; don't implement
  public/indexable pages as client-only fetch.
- Server Components by default. Add `"use client"` only where real
  interactivity is needed (a form, a counter, anything with state or
  event handlers) — and put it on line 1, before imports.

## 🏗️ Architecture

- **Generic HTTP client separate from domain services.** One client
  (`src/lib/api.ts`) handles the transport (base URL, auth headers, CSRF);
  each domain gets its own thin service on top of it
  (`src/lib/services/userService.ts`, `authService.ts`, ...). Components
  call services, never the raw client directly.
- **Same-origin proxy for first-party cookies.** A server-side proxy
  (`/api/:path*`) forwards to the real API — this is also where an edge
  secret header (if the backend requires one) gets attached, **never** in
  a client-side `fetch`.

## 📛 Naming and file shape

| What | Convention |
|---|---|
| Component (symbol + file) | `PascalCase`, e.g. `UserCard.tsx` |
| Custom hook | `useCamelCase`, e.g. `useDebounce` |
| Event handler | `handleClick`, `handleSubmit` (inside the component) |
| Boolean prop/state | `isLoading`, `hasError`, `canSubmit` |
| File with JSX | `.tsx` |
| Pure logic, hook without JSX, utility | `.ts` |
| Test file | `.test.tsx` / `.test.ts`, mirrors the source file |

```tsx
type Props = {
  user: User;
  onSelect: (id: string) => void;
};

export function UserCard({ user, onSelect }: Props) {
  return (
    <button type="button" onClick={() => onSelect(user.id)}>
      {user.name}
    </button>
  );
}
```

- Always destructure props in the parameter list.
- Prefer `type Props = {}` for closed component prop shapes.
- Self-close tags with no children (`<UserCard user={u} />`); use `<>...</>`
  over a wrapper `<div>` when no DOM element is needed.
- Class components are **forbidden** in new code.

## 🪝 Hooks discipline

- Group all hook calls at the top of the component, before any
  conditional logic.
- Complete every dependency in `useEffect`/`useMemo`/`useCallback` — a
  missing dependency is a bug, not a lint nag to silence.

```tsx
// ❌ missing dependency
useEffect(() => {
  fetchData(userId);
}, []);

// ✅ correct
useEffect(() => {
  fetchData(userId);
}, [userId]);
```

## 🗂️ State management

- Local first (`useState`); lift state only when it's actually shared.
- Context API for cross-cutting concerns (theme, auth).
- An external store (Zustand, Jotai) only when state needs to persist
  across route changes — not by default.
- Never duplicate state that can be derived from existing state/props.

## 🔷 TypeScript

- **Explicit types on public APIs**: exported functions, shared
  utilities, component props. Let TypeScript infer obvious local
  variables.
- `interface` for object shapes that may be extended; `type` for unions,
  intersections, tuples, mapped/utility types.
- **Avoid `any`.** Use `unknown` for external/untrusted input and narrow
  it safely; use generics when a type depends on the caller.

  ```typescript
  // ❌ any removes type safety
  function getErrorMessage(error: any) {
    return error.message;
  }

  // ✅ unknown forces safe narrowing
  function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return "Erro inesperado";
  }
  ```

- **Immutability**: update via spread, never mutate an argument.
- **Errors**: `async`/`await` with `try`/`catch`, narrow `unknown` before
  using it.
- **Input validation**: Zod for schema-based validation of anything
  crossing a boundary (form input, API response shape).
- No `console.log` in production code — use a real logging path.

## ✅ Testing

- **Don't test visual/3D/styled components directly** — expensive and
  fragile. Extract all real logic (bid preview calculation, client-side
  URL normalization, currency formatting) into `src/lib/`, tested in
  isolation.
- **Name** describes behavior, not implementation:
  `it("should show only the difference when owner reinforces bid")`.
- **Body** in Given/When/Then (comment), one-line description in the
  `it(...)` itself — no separate docstring, that's not the TS convention.

  ```ts
  it("should show only the difference when owner reinforces bid", () => {
    // Given
    const listing = listingFactory({ currentBidCents: 1200 });

    // When
    const preview = previewBid(listing, { amountCents: 1500, isOwner: true });

    // Then
    expect(preview.chargeCents).toBe(300);
  });
  ```

- Vitest, environment `node` (not `jsdom`) for `src/lib/**` — reinforces
  that only pure logic is under test there. Coverage thresholds: 70%
  lines/functions, 60% branches.

## 🔒 Security

- **Never trust a client-side calculation for anything that costs money
  or grants access** — it's a preview only; the server recalculates and
  is the one that decides.
- **Never render free-text user input unsanitized** (display name, bio,
  any field a user fills in) — XSS surface.
- **No secret in the client.** An edge/gateway secret lives in a
  server-only env var (no `NEXT_PUBLIC_` prefix) and is attached only by
  the server-side proxy — never in a client component's `fetch`.

## 🛠️ Tooling — commands

```bash
npm run lint
npm test -- --run
npm run build
npm run dev
```
