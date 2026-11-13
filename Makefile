.PHONY: setup run test lint

setup:
	pip install -r requirements.txt -r requirements-dev.txt

run:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .
	ruff format --check .
