.PHONY: install lint format test

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

lint:
	ruff check src tests
	ruff format --check src tests
	mypy src tests

format:
	ruff check --fix src tests
	ruff format src tests

test:
	pytest
