.PHONY: up down migrate seed test lint benchmark run

up:
	docker compose up --build

down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python scripts/seed_data.py --scale 0.02

seed-full:
	python scripts/seed_data.py --scale 1.0

test:
	pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80

lint:
	ruff check app tests scripts
	mypy app

benchmark:
	python scripts/benchmark_queries.py

run:
	uvicorn app.main:app --reload --port 8000
