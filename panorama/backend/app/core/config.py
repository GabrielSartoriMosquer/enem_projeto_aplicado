from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Pasta backend/. No Vercel só ela é publicada (é a raiz do serviço), então os caminhos dos
# arquivos que vão junto com a API partem daqui, não de PROJECT_ROOT.
BACKEND_DIR = Path(__file__).resolve().parents[2]
# No Vercel o disco é só leitura, a não ser o /tmp.
if os.environ.get("VERCEL"):
    LAKE_CACHE_DIR = Path(tempfile.gettempdir()) / "panorama-lake"
else:
    LAKE_CACHE_DIR = BACKEND_DIR / "data/lake"


class Settings(BaseSettings):
    app_name: str = "Panorama ENEM API"
    app_version: str = "1.0.0"
    environment: str = "development"
    data_mode: str = Field(default="auto", validation_alias="PANORAMA_DATA_MODE")
    parquet_glob: str = str(PROJECT_ROOT / "backend/data/parquet/ano=*/enem.parquet")
    # Camada gold gerada pelo ETL deste repositório (data/gold/ na raiz, ao lado de panorama/)
    gold_path: str = str(PROJECT_ROOT.parent / "data/gold/enem_notas.parquet")
    demo_csv: str = str(BACKEND_DIR / "data/demo/enem_demo.csv")
    # Data lake no Azure (mesmas variáveis do ETL). Com uma delas definida, a API usa a gold do
    # lake: com a conta, o login é o do `az login`; a connection string serve para o Docker.
    lake_account: str | None = Field(default=None, validation_alias="AZURE_STORAGE_ACCOUNT")
    lake_connection_string: str | None = Field(
        default=None, validation_alias="AZURE_STORAGE_CONNECTION_STRING"
    )
    lake_gold_container: str = "gold"
    lake_gold_file: str = "enem_notas.parquet"
    # Onde a cópia baixada do lake fica guardada (fora do git, ver .gitignore; /tmp no Vercel).
    lake_cache_path: str = str(LAKE_CACHE_DIR / "gold/enem_notas.parquet")
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    api_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_prefix="PANORAMA_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def normalized_data_mode(self) -> str:
        mode = (self.data_mode or "auto").strip().lower()
        if mode not in {"demo", "official", "auto"}:
            raise ValueError("data_mode deve ser demo, official ou auto.")
        return mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
