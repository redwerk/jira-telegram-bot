ENV_ROOT=venv/
PYBINARYDIR=$(ENV_ROOT)bin/
PYTHON=$(PYBINARYDIR)python

help:
	@echo 'run-tests         - Run pytest'
	@echo 'run-bot           - Run JiraTelegramBot'
	@echo 'run-oauth-service - Run auth service to authorize via OAuth in Jira'
	@echo 'run-code-chaker   - Run flake8 checks'

run-tests:
	$(PYBINARYDIR)pytest -v

run-bot:
	$(PYTHON) run.py

run-oauth-service:
	$(PYTHON) auth_run.py

run-code-chaker:
	$(PYBINARYDIR)flake8 --exclude=$(ENV_ROOT)
