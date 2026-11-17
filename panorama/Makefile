.PHONY: install test api web demo docker etl-2025 etl-all gold

# Usa o ambiente virtual da pasta panorama/.venv (criado pelo `make install`), mesmo que outro
# ambiente esteja ativo no terminal (ex.: o .venv da raiz, que não tem uvicorn).
VENV := .venv
BIN := $(VENV)/bin

$(BIN)/python:
	python3 -m venv $(VENV)

# Com o uv instalado usa `uv pip` (um .venv criado pelo uv não tem pip); senão, o pip do venv.
install: $(BIN)/python
	if command -v uv >/dev/null 2>&1; then uv pip install --python $(BIN)/python -e '.[dev]'; \
	else $(BIN)/python -m pip install -e '.[dev]'; fi
	cd frontend && npm install

test:
	$(BIN)/pytest --cov=backend/app --cov-report=term-missing

api:
	@test -x $(BIN)/uvicorn || { echo "Dependências da API não instaladas. Rode: make install"; exit 1; }
	$(BIN)/uvicorn app.main:app --app-dir backend --reload --port 8000

web:
	cd frontend && npm run dev

docker:
	docker compose up --build

etl-2025:
	$(BIN)/python -m app.etl.cli all --years 2025

etl-all:
	$(BIN)/python -m app.etl.cli all --years 2018-2025

# Roda o ETL da raiz do repositório (download -> bronze -> silver -> gold). Etapas já feitas
# são puladas. A API passa a usar ../data/gold/enem_notas.parquet
gold:
	cd .. && uv run enem-pja3
