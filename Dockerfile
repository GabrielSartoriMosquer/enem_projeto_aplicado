FROM python:3.14-slim

# Copia o binário do uv de uma imagem oficial
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

# unzip: o RESULTADOS_2025.csv usa Deflate64, que o zipfile do Python não abre
RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 etl && mkdir -p /data && chown etl:etl /data
USER etl

# Roda o pipeline completo (download, extract, transform, load e volumetria)
CMD ["enem-pja3"]
