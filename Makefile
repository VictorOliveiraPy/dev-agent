# Comandos do dia a dia - ver README.md pro contexto completo de cada um.
# `make` (sem alvo) ou `make help` lista tudo isto na tela.

PYTHON := .venv/Scripts/python.exe

.PHONY: help venv install lint test \
        main dev-backend dev-frontend team-supervisor refactor-team cache-probe \
        office web-ui dashboard quality-dashboard clean

help:
	@echo "Setup"
	@echo "  make venv               cria .venv/"
	@echo "  make install            instala requirements.txt + requirements-dev.txt"
	@echo ""
	@echo "Qualidade"
	@echo "  make lint               ruff check ."
	@echo "  make test               pytest -q"
	@echo ""
	@echo "Rodar o time (cada um gasta API real)"
	@echo "  make main               main.py - personas sem tools"
	@echo "  make dev-backend        dev_backend_agent.py - dev_backend com tools"
	@echo "  make dev-frontend       dev_frontend_agent.py - dev_frontend com tools"
	@echo "  make team-supervisor    team_supervisor.py - supervisor orquestrando o time"
	@echo "  make refactor-team      refactor_team.py - auditoria só-leitura do próprio código"
	@echo "  make cache-probe        cache_probe.py - diagnóstico de prompt caching (API real, pouco)"
	@echo ""
	@echo "Interfaces web"
	@echo "  make office             escritório em tempo real (FastAPI+WebSocket) - http://localhost:8000"
	@echo "  make web-ui             rodar o time e ver a conversa ao vivo (Streamlit)"
	@echo "  make dashboard          custo/uso de tokens (Streamlit)"
	@echo "  make quality-dashboard  acertividade do pesquisador (Streamlit)"
	@echo ""
	@echo "Scripts de projeto real (não listados aqui, cada um é específico):"
	@echo "  python -m projects.<nome>   ex.: python -m projects.build_fe_catolica"
	@echo ""
	@echo "make clean              limpa workspace/, logs de uso e caches locais"

venv:
	python -m venv .venv

install:
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest -q

main:
	$(PYTHON) main.py

dev-backend:
	$(PYTHON) dev_backend_agent.py

dev-frontend:
	$(PYTHON) dev_frontend_agent.py

team-supervisor:
	$(PYTHON) team_supervisor.py

refactor-team:
	$(PYTHON) refactor_team.py

cache-probe:
	$(PYTHON) cache_probe.py

office:
	$(PYTHON) -m uvicorn office.server:app --reload

web-ui:
	$(PYTHON) -m streamlit run web_ui.py

dashboard:
	$(PYTHON) -m streamlit run dashboard.py

quality-dashboard:
	$(PYTHON) -m streamlit run quality_dashboard.py

clean:
	rm -rf workspace/* usage_log.jsonl quality_log.jsonl .pytest_cache .ruff_cache
