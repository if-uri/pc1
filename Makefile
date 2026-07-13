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

# --- digital twin (net-user-pl + mobile-user-pl + pc-user-pl submodules) ---

twin-init: ## Fetch submodules + build the CA and the Jan Kowalski desktop image
	git submodule update --init --recursive
	bash net-user-pl/ca/gen.sh
	-docker network create netpl
	docker build -t pc1-desktop:local desktop
	DOCKER_BUILDKIT=0 docker build -t pc-user-pl-desktop:local pc-user-pl/desktop

twin-up: ## Start the whole isolated digital world (net + phone + Jan's PC)
	-docker network create netpl
	docker compose -f compose.twin.yml up -d

twin-test: ## Run the flagship bank SMS-code login journey through the twin
	URIRUN_TWIN_E2E=1 $(VENV)/bin/python -m pytest tests/test_twin_bank_sms.py -v

twin-events: ## Print the URI event trace of the last twin episode
	@curl -s http://127.0.0.1:28800/events | python3 -m json.tool

twin-down: ## Stop and wipe the twin
	docker compose -f compose.twin.yml down -v

scenario-init: ## Build CA/base images for the multi-node customer/buyer scenario
	git submodule update --init --recursive
	bash net-user-pl/ca/gen.sh
	-docker network create netpl
	docker build -t pc1-desktop:local desktop
	DOCKER_BUILDKIT=0 docker build -t pc-user-pl-desktop:local pc-user-pl/desktop

scenario-up: ## Start net-user-pl, business portal, human connector, pc1 and pc2
	-docker network create netpl
	docker compose -f compose.scenario.yml up -d --build

scenario-test: ## Run the multi-node pc1/pc2 scenario suite and write reports
	PYTHONPATH=$(CURDIR) $(VENV)/bin/python -m pytest tests/test_multinode_scenarios.py -v
	PYTHONPATH=$(CURDIR) $(VENV)/bin/python -m scenarios.multinode.runner --out reports/scenario

scenario-events: ## Print the last multi-node URI event trace
	@python3 -m json.tool reports/scenario/events.json

scenario-report: ## Print the Markdown report path
	@echo "report: reports/scenario/summary.md"
	@echo "junit:  reports/scenario/junit.xml"

scenario-down: ## Stop and wipe the multi-node scenario environment
	docker compose -f compose.scenario.yml down -v --remove-orphans

scenario-ci: ## Build, test, report and always clean the multi-node scenario
	$(MAKE) scenario-init
	$(MAKE) scenario-up
	@status=0; $(MAKE) scenario-test || status=$$?; $(MAKE) scenario-report || true; $(MAKE) scenario-down || true; exit $$status

.PHONY: help venv up down test watch twin-init twin-up twin-test twin-events twin-down scenario-init scenario-up scenario-test scenario-events scenario-report scenario-down scenario-ci
