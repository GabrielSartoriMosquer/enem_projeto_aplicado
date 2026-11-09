from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Panorama ENEM API"
    app_version: str = "1.0.0"
    environment: str = "development"
    data_mode: str = Field(default="auto", validation_alias="PANORAMA_DATA_MODE")
    parquet_glob: str = str(PROJECT_ROOT / "backend/data/parquet/ano=*/enem.parquet")
    # Camada gold gerada pelo ETL deste repositório (data/gold/ na raiz, ao lado de panorama/)
    gold_path: str = str(PROJECT_ROOT.parent / "data/gold/enem_notas.parquet")
    demo_csv: str = str(PROJECT_ROOT / "backend/data/demo/enem_demo.csv")
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
