# LureRadar developer tasks. `make check` is the gate for every commit.
.DEFAULT_GOAL := help
UV ?= uv
RUN := $(UV) run
CORE := '*/lureradar/detectors/*,*/lureradar/scoring/*,*/lureradar/export/*,*/lureradar/util/*,*/lureradar/textlure/*'

.PHONY: help install lint fmt typecheck test coverage packs secrets fixtures links hostnames schemas \
        check bench demo scan-fixtures site og wheel smoke-wheel clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv from uv.lock
	$(UV) sync --locked

lint: ## Ruff lint + format check
	$(RUN) ruff check .
	$(RUN) ruff format --check .

fmt: ## Auto-format and fix lint
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

typecheck: ## mypy --strict on src/
	$(RUN) mypy

test: ## Run the test suite with coverage
	$(RUN) pytest -q --cov --cov-report=term:skip-covered --cov-report=xml

coverage: ## Enforce >= 85% coverage on the core packages
	$(RUN) coverage report --include=$(CORE) --fail-under=85 --skip-covered

packs: ## Validate every campaign pack
	$(RUN) lureradar pack validate

secrets: ## Scan tracked files for secrets
	$(RUN) python scripts/check_secrets.py

fixtures: ## Fail if a fixture contains a non-reserved domain
	$(RUN) python scripts/check_fixture_domains.py

links: ## Check relative links in Markdown docs
	$(RUN) python scripts/check_links.py

hostnames: ## Ensure the site hostname is only configured in the allowed files
	$(RUN) python scripts/check_hostnames.py

schemas: ## Regenerate JSON Schemas from the pydantic models
	$(RUN) python scripts/gen_schemas.py

check: lint typecheck test coverage packs secrets fixtures links hostnames ## Everything CI runs

bench: ## Run the benchmark and write docs/BENCHMARKS.md
	$(RUN) python -m bench

demo: ## Re-record assets/demo.gif
	./scripts/record_demo.sh

scan-fixtures: ## Run the full pipeline offline against recorded fixtures
	$(RUN) lureradar scan --fixtures --out build/site/feeds --state build/state.db

site: ## Build the static site into web/dist (demo data unless FEEDS=dir)
	$(RUN) python scripts/build_site_data.py $(if $(FEEDS),--feeds $(FEEDS),)
	cd web && npm ci && npm test && npm run build

og: ## Regenerate brand images (social preview, favicons, OG cards)
	$(RUN) python scripts/gen_og.py

wheel: ## Build sdist + wheel into dist/
	$(UV) build

smoke-wheel: wheel ## Install the wheel in a clean venv and run an offline check
	./scripts/smoke_wheel.sh

clean: ## Remove build artefacts
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache coverage.xml .coverage htmlcov
