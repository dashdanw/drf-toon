.PHONY: install lint format format-check typecheck test check all

install:
	uv sync --dev

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint format-check typecheck test

all: install check

