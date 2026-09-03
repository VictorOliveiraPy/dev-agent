# Padrões de frontend

- Framework padrão: React (Vite).
- Estado de autenticação/dados globais via Context API — sem libs de state
  management externas, a menos que o projeto realmente peça.
- Chamadas à API centralizadas em `src/api/`, nunca `fetch` solto dentro
  de um componente.
