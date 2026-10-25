PYTHON ?= python3

.PHONY: setup test replay serve

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

test:
	.venv/bin/pytest -q

replay:
	.venv/bin/python -m services.agents.orchestrator --replay route_block

serve:
	.venv/bin/uvicorn services.api.handlers:app --host 127.0.0.1 --port 8080
