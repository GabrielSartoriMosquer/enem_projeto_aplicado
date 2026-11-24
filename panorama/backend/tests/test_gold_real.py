"""Confere a API sobre a gold real do ETL, quando ela existe nesta máquina.

Caminho: variável ENEM_GOLD_PATH ou data/gold/enem_notas.parquet na raiz do repositório (gerada
pelo ETL). Sem o arquivo (CI, por exemplo), os testes são pulados.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.core.config import PROJECT_ROOT
from app.core.constants import Q001_Q002_LABELS, Q006_LABELS
from app.services.data_engine import GoldEngine
from app.services.income_model import income_probability

GOLD = Path(
    os.environ.get(
        "ENEM_GOLD_PATH",
        PROJECT_ROOT.parent / "data" / "gold" / "enem_notas.parquet",
    )
)

pytestmark = pytest.mark.skipif(not GOLD.is_file(), reason=f"gold real não encontrada: {GOLD}")


@pytest.fixture(scope="module")
def engine():
    return GoldEngine(str(GOLD))


def test_all_editions(engine):
    assert engine.years() == list(range(2018, 2026))


@pytest.mark.parametrize("year", range(2018, 2026))
def test_every_edition_answers_all_modules(engine, year):
    summary = engine.summary(year)
    assert summary["participants"] > 3_000_000
    assert all(300 < mean < 700 for mean in summary["means"].values())

    results = engine.percentiles(year, {"CN": 500, "CH": 500, "LC": 500, "MT": 500, "REDACAO": 600})
    assert all(0 < item["percentile"] < 100 and item["n"] > 2_000_000 for item in results)

    region = engine.region_school(year, "MT")
    assert region["states_with_data"] == 27

    renda = engine.socioeconomic(year, "MT", "renda")
    mae = engine.socioeconomic(year, "MT", "escolaridade_mae")
    if year <= 2023:
        assert {group["code"] for group in renda} <= set(Q006_LABELS)
        assert len(renda) == 17
        assert {group["code"] for group in mae} == set(Q001_Q002_LABELS)
        assert {item["code"] for item in region["school_types"]} == {1, 2, 3}
    else:
        # 2024 e 2025: o INEP separou perfil e nota em arquivos sem ligação
        assert renda == [] and mae == []
        assert region["school_types"] == []


def test_zero_scores_are_excluded(engine):
    # Quem tirou 0 em alguma objetiva sai da base, então nenhuma objetiva tem nota 0
    for area in ("CN", "CH", "LC", "MT"):
        (result,) = engine.percentiles(2023, {area: 0})
        assert result["percentile"] == 0.0


@pytest.mark.parametrize("year", range(2018, 2024))
def test_income_model_matches_direct_count(engine, year):
    """Bayes tem que dar o mesmo que contar direto, e o percentil o mesmo do resto do site."""
    counts, reference = engine.income_counts(year, "MT", 700)
    result = income_probability(counts)
    assert result["bayes_available"]
    assert sum(band["posterior"] for band in result["bands"]) == pytest.approx(1)
    for band in result["bands"]:
        direct = counts[band["code"]].n_ge / result["n_above"]
        assert band["posterior"] == pytest.approx(direct)
    # a chance de chegar à nota cresce de uma faixa de renda para a seguinte
    rates = [band["likelihood"] for band in result["bands"]]
    assert rates == sorted(rates)
    assert reference.n > 10_000
    (site,) = engine.percentiles(year, {"MT": 700})
    assert result["percentile"] == pytest.approx(site["percentile"], abs=0.5)
