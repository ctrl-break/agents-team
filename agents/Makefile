# ── SpecPipeline — Common Commands ──────────────────────────────────────
# Usage:
#   make install     — install dependencies
#   make test        — run all tests
#   make lint        — run linter (ruff)
#   make typecheck   — run type checker (mypy)
#   make check       — run lint + typecheck
#   make format      — auto-format code
#   make clean       — remove build artifacts

.PHONY: install test lint typecheck check format clean dev

VENV := .venv
PYTHON := $(VENV)/bin/python
ifeq ($(OS),Windows_NT)
	PYTHON := $(VENV)/Scripts/python.exe
endif

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check src/ tests/

typecheck:
	$(PYTHON) -m mypy src/ --ignore-missing-imports

check: lint typecheck

format:
	$(PYTHON) -m ruff format src/ tests/

clean:
	@rm -rf .pytest_cache
	@rm -rf src/**/__pycache__
	@rm -rf tests/__pycache__
	@rm -rf .mypy_cache
	@rm -rf *.egg-info
	@rm -f test_output.txt