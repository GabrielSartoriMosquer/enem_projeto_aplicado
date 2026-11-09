.PHONY: install test api web demo docker etl-2025 etl-all gold

install:
	python -m pip install -e '.[dev]'
	cd frontend && npm install

test:
	pytest --cov=backend/app --cov-report=term-missing

api:
	uvicorn app.main:app --app-dir backend --reload --port 8000

web:
	cd frontend && npm run dev

docker:
	docker compose up --build

etl-2025:
	python -m app.etl.cli all --years 2025

etl-all:
	python -m app.etl.cli all --years 2018-2025

# Roda o ETL da raiz do repositório (download -> bronze -> silver -> gold). Etapas já feitas
# são puladas. A API passa a usar ../data/gold/enem_notas.parquet
gold:
	cd .. && uv run enem-pja3
