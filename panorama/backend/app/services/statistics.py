from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ScoreStatistics:
    n: int
    mean: float
    std: float | None
    percentile: float
    z_score: float | None


def safe_population_std(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None
    std_raw = float(numeric.std(ddof=0))
    if not math.isfinite(std_raw) or std_raw <= 0:
        return None
    return std_raw


def compute_score_statistics(series: pd.Series, score: float) -> ScoreStatistics:
    """Compute exact empirical percentile and z-score for one score.

    Percentile is the share of valid observations <= the informed score.
    The calculation is always expected to be scoped to one ENEM edition.
    The z-score is descriptive only and is not interpreted as a normal-theory test.
    """
    values = pd.to_numeric(series, errors="coerce").dropna()
    n = int(values.shape[0])
    if n == 0:
        raise ValueError("Não há observações válidas para o recorte solicitado.")

    score_value = float(score)
    if not math.isfinite(score_value):
        raise ValueError("A nota informada deve ser numérica e finita.")

    mean = float(values.mean())
    std = safe_population_std(values)
    percentile = round(float((values <= score_value).sum()) / n * 100.0, 2)
    z_score = round((score_value - mean) / std, 3) if std is not None else None

    return ScoreStatistics(
        n=n,
        mean=round(mean, 2),
        std=round(std, 2) if std is not None else None,
        percentile=percentile,
        z_score=z_score,
    )
