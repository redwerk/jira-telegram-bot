PYBINARYDIR=venv/bin/
PYTHON=$(PYBINARYDIR)python

help:
	@echo 'run-tests         - Run pytest'
	@echo 'run-bot           - Run JiraTelegramBot'
	@echo 'run-web-service   - Run web server'
	@echo 'run-code-chaker   - Run flake8 checks'

run-tests:
	$(PYBINARYDIR)pytest -v

run-bot:
	$(PYTHON) run.py bot

run-web-service:
	$(PYTHON) run.py web

run-code-chaker:
	$(PYBINARYDIR)flake8
