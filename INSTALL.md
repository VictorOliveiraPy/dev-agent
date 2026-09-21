# Guia de instalação — do zero, num PC novo

Pensado pra depois de formatar: o repositório inteiro está no GitHub
(`VictorOliveiraPy/dev-agent`, branch `main` atualizada), mas três coisas
NÃO estão versionadas (ver `.gitignore`) e não sobrevivem a uma
formatação sem backup manual.

## 0. Antes de formatar — backup do que não está no Git

- [ ] **`ANTHROPIC_API_KEY`** — só existe no seu `.env` local. Anote a
      chave em algum lugar seguro (gerenciador de senhas), ou saiba que
      vai precisar gerar uma nova em
      [console.anthropic.com](https://console.anthropic.com) → Plans & Billing.
- [ ] **`DEEPSEEK_API_KEY`** (opcional, só se usa `LLM_PROVIDER=deepseek`)
      — mesma lógica, chave só no `.env` local; gere uma nova em
      [platform.deepseek.com](https://platform.deepseek.com) se não tiver backup.
- [ ] **`usage_log.jsonl` / `quality_log.jsonl`** — históricos de custo e
      de acertividade que alimentam `dashboard.py`/`quality_dashboard.py`.
      Se quiser manter o histórico, copie esses arquivos pra fora do repo
      antes de formatar (ex: pra um pendrive/nuvem). Sem backup, os
      dashboards começam vazios de novo — não é um problema funcional, só
      perde o histórico.
- [ ] **Chaves SSH (`~/.ssh/`)** — o remoto do repo usa SSH
      (`git@github.com:VictorOliveiraPy/dev-agent.git`). Sem backup das
      chaves, você vai precisar gerar um par novo e cadastrar a pública
      em [github.com/settings/keys](https://github.com/settings/keys)
      depois de formatar (passo 2 abaixo cobre isso).
- [ ] **Confirme que tudo já está commitado e no GitHub** antes de
      formatar: `git status` (deve dar "nada a commitar") e `git log
      origin/main..main` (deve dar vazio — nada local sem push).

## 1. Pré-requisitos no PC novo

- **Git**
- **Python 3.13** (o projeto usa `python3.13`; confira com `python3 --version`)
- **(Opcional) Node.js + npm** — só necessário se você quiser VALIDAR de
  verdade um frontend Next.js que o `dev_frontend` escrever (rodar
  `tsc`/`eslint`/`vitest`/`build` sobre o resultado). Não é dependência
  do dev-agent em si.
- **Docker NÃO é mais necessário** — o suporte a Ollama local foi
  removido (ver ARCHITECTURE.md, "Propostas testadas e descartadas").

## 2. Configurar o Git/SSH (se não restaurou backup das chaves)

```bash
ssh-keygen -t ed25519 -C "seu-email@exemplo.com"
cat ~/.ssh/id_ed25519.pub   # cole isso em github.com/settings/keys
ssh -T git@github.com       # deve responder "Hi <usuário>! You've
                            # successfully authenticated..."
```

## 3. Clonar e configurar o projeto

```bash
git clone git@github.com:VictorOliveiraPy/dev-agent.git
cd dev-agent

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env
# edite .env e cole sua ANTHROPIC_API_KEY (e ANTHROPIC_WORKSPACE_ID,
# se você usa múltiplos workspaces na conta — opcional)
#
# Opcional: LLM_PROVIDER=deepseek + DEEPSEEK_API_KEY troca todo o time
# (exceto o pesquisador, que sempre usa Anthropic — ver ARCHITECTURE.md)
# pra rodar em cima do DeepSeek em vez de Claude. Sem essas duas
# variáveis, nada muda (default é "anthropic").
```

Se tinha backup de `usage_log.jsonl`, copie ele de volta pra raiz do
repo agora (fica de fora do Git de propósito, não precisa de `git add`).

## 4. Confirmar que funcionou (não gasta API — nenhum destes chama o modelo real)

```bash
.venv/bin/python -m ruff check .     # deve dar "All checks passed!"
.venv/bin/python -m pytest -q        # deve dar "87 passed" (ou mais)
```

Se os dois passarem, a fundação (dependências, venv, código) está OK —
o que falta testar é a chamada real à API.

## 5. Primeiro teste real (gasta API — pouco, uma chamada por papel)

```bash
.venv/bin/python main.py
```

Deve imprimir a resposta de `arquiteto`, `dev_backend` e `dev_frontend`
pra mesma tarefa de exemplo. Se der erro `credit balance is too low`,
recarregue em console.anthropic.com → Plans & Billing.

## 6. Interfaces web (opcional)

```bash
.venv/bin/streamlit run dashboard.py           # custo/uso de tokens (usage_log.jsonl)
.venv/bin/streamlit run quality_dashboard.py   # acertividade do pesquisador (quality_log.jsonl)
.venv/bin/streamlit run web_ui.py              # rodar o time e ver a conversa ao vivo
.venv/bin/uvicorn office.server:app --reload   # o time como personagens pixel-art, tempo real
```

## 7. Pendência em aberto que você vai herdar

Existe uma investigação real ainda não fechada: o prompt caching parece
quebrado no caminho do `AgentExecutor` (`dev_backend`/`dev_frontend`) —
ver ARCHITECTURE.md, seção "Limitações conhecidas", e `PROGRESS.md`
(sessão 2026-09-06). Quando tiver saldo de API disponível, rode:

```bash
.venv/bin/python cache_probe.py
```

Isso confirma (ou descarta) o achado com uma chamada real e barata —
antes de considerar qualquer troca de modelo/provedor por custo.

---

Ver [README.md](README.md) pro resto dos comandos do dia a dia,
[ARCHITECTURE.md](ARCHITECTURE.md) pras decisões estruturais e o motivo
de cada uma, e [PROGRESS.md](PROGRESS.md) pro histórico sessão a sessão.
