.PHONY: install lint format format-check typecheck test coverage check up down

install:
	uv sync --locked

lint:
	uv run --locked ruff check .

format:
	uv run --locked ruff format .

format-check:
	uv run --locked ruff format --check .

typecheck:
	uv run --locked mypy .

test:
	uv run --locked pytest

coverage:
	uv run --locked pytest --cov

check: lint format-check typecheck test

up:
	docker compose up -d

down:
	docker compose down
