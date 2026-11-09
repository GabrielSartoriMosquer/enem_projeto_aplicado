from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Area = Literal["CN", "CH", "LC", "MT", "REDACAO"]
SocioDimension = Literal["renda", "escolaridade_mae", "escolaridade_pai"]


class ScoreInput(BaseModel):
    year: int = Field(ge=2018, le=2025)
    scores: dict[Area, float]

    @field_validator("scores")
    @classmethod
    def validate_scores(cls, value: dict[Area, float]) -> dict[Area, float]:
        if not value:
            raise ValueError("Informe pelo menos uma nota.")
        for score in value.values():
            if not 0 <= score <= 1000:
                raise ValueError("As notas devem estar entre 0 e 1000.")
        return value


class EssayInput(BaseModel):
    year: int = Field(ge=2018, le=2025)
    score: float = Field(ge=0, le=1000)


class PercentileResult(BaseModel):
    area: Area
    label: str
    score: float
    percentile: float
    z_score: float | None
    mean: float
    std: float | None
    n: int


class AnalysisResponse(BaseModel):
    year: int
    data_source: str
    results: list[PercentileResult]
    disclaimer: str
