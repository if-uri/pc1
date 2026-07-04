VENV := .venv

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n",$$1,$$2}'

venv: ## Create the host-side venv with the urirun CLI (mesh) + pytest
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -U pip
	$(VENV)/bin/pip install -q --no-deps desktop/vendor/urirun-0*.whl
	$(VENV)/bin/pip install -q desktop/vendor/urirun_contract-*.whl \
	  desktop/vendor/urirun_connector_router-*.whl desktop/vendor/urirun_flow-*.whl \
	  jsonschema pydantic pytest
	$(VENV)/bin/python -c "import urirun.node.mesh; print('mesh OK')"

up: ## Build + start the workplace (desktop, mail, wordpress, intranet)
	docker compose up -d --build

down: ## Stop and wipe the workplace
	docker compose down -v

test: ## Run the daily-work E2E journeys (composes up itself)
	$(VENV)/bin/python -m pytest tests -v

watch: ## Print the live-view URL
	@echo "noVNC: http://127.0.0.1:26080/vnc.html  |  Mailpit: http://127.0.0.1:28025  |  WP: http://127.0.0.1:28080"

.PHONY: help venv up down test watch
