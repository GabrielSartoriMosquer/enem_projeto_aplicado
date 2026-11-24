"""Modelo de probabilidade condicional (Bayes) entre nota e renda."""

from __future__ import annotations

import math

import duckdb
import pytest
from app.api.routes import engine_dep
from app.main import app
from app.services.data_engine import GoldEngine
from app.services.income_model import (
    INCOME_BANDS,
    MIN_GROUP_SIZE,
    GroupCount,
    band_of,
    income_probability,
)
from fastapi.testclient import TestClient

# Turma fictícia fácil de conferir no papel: 1000 pessoas, 200 por faixa.
# Com nota >= x: 10, 20, 40, 60 e 70 pessoas (total 200).
COUNTS = {
    band.code: GroupCount(n=200, n_ge=n_ge, n_le=200 - n_ge)
    for band, n_ge in zip(INCOME_BANDS, (10, 20, 40, 60, 70), strict=True)
}


def by_code(result):
    return {band["code"]: band for band in result["bands"]}


def test_bands_cover_the_17_codes_once():
    codes = [code for band in INCOME_BANDS for code in band.q006]
    assert sorted(codes) == list("ABCDEFGHIJKLMNOPQ")
    assert band_of("A") == band_of("B") == "ate_1"
    assert band_of("M") == "4_a_10"
    assert band_of("N") == "mais_10"
    with pytest.raises(ValueError):
        band_of("Z")


def test_hand_calculated_example():
    result = income_probability(COUNTS)
    low, high = by_code(result)["ate_1"], by_code(result)["mais_10"]
    assert low["prior"] == pytest.approx(0.2)  # P(r) = 200/1000
    assert low["likelihood"] == pytest.approx(0.05)  # P(X>=x | r) = 10/200
    assert low["joint"] == pytest.approx(0.01)  # 0,2 * 0,05
    assert result["total_probability"] == pytest.approx(0.2)  # soma dos produtos
    assert low["posterior"] == pytest.approx(0.05)  # 0,01 / 0,2
    assert high["posterior"] == pytest.approx(0.35)
    assert high["representation"] == pytest.approx(1.75)  # 0,35 / 0,2
    assert low["percentile"] == pytest.approx(95.0)


def test_probabilities_sum_to_one_and_match_direct_count():
    result = income_probability(COUNTS)
    bands = result["bands"]
    assert sum(band["prior"] for band in bands) == pytest.approx(1)
    assert sum(band["posterior"] for band in bands) == pytest.approx(1)
    n_ge = sum(count.n_ge for count in COUNTS.values())
    for band in bands:
        assert band["posterior"] == pytest.approx(COUNTS[band["code"]].n_ge / n_ge)


def test_standard_error():
    low = by_code(income_probability(COUNTS))["ate_1"]
    assert low["likelihood_se"] == pytest.approx(math.sqrt(0.05 * 0.95 / 200))


def test_small_group_hides_its_rate_and_the_posterior():
    counts = {**COUNTS, "mais_10": GroupCount(n=MIN_GROUP_SIZE - 1, n_ge=50, n_le=49)}
    result = income_probability(counts)
    high = by_code(result)["mais_10"]
    assert high["likelihood"] is None and high["percentile"] is None
    # sem uma das parcelas não há como somar a probabilidade total
    assert result["bayes_available"] is False
    assert all(band["posterior"] is None for band in result["bands"])
    assert by_code(result)["ate_1"]["likelihood"] == pytest.approx(0.05)


def test_nobody_reaches_the_score():
    counts = {code: GroupCount(n=200, n_ge=0, n_le=200) for code in COUNTS}
    result = income_probability(counts)
    assert result["total_probability"] == 0
    assert result["bayes_available"] is False
    assert all(band["posterior"] is None for band in result["bands"])


def test_no_data_raises():
    with pytest.raises(ValueError):
        income_probability({})


# API ----------------------------------------------------------------------------------------

BODY = {"year": 2023, "area": "MT", "score": 600, "income": "ate_1"}
URL = "/api/v1/analysis/income-probability"


@pytest.fixture
def gold_engine(tmp_path):
    """Gold com 1200 pessoas em 2023 e uma linha em 2025, no esquema do ETL."""
    path = tmp_path / "enem_notas.parquet"
    rows = []
    for band, share in zip(INCOME_BANDS, (0.05, 0.10, 0.20, 0.30, 0.50), strict=True):
        code = band.q006[-1]
        for i in range(200):
            score = 700.0 if i < 200 * share else 400.0
            rows.append((2023, "SC", "privada", "E", "E", code, 500, 500, 500, score, 600))
    # renda vazia e nota zero em Humanas: não podem entrar
    rows += [(2023, "SC", "publica", "E", "E", None, 500, 500, 500, 700.0, 600)] * 100
    rows += [(2023, "SC", "publica", "E", "E", "A", 500, 0, 500, 700.0, 600)] * 100
    rows.append((2025, "SC", None, None, None, None, 500, 500, 500, 700.0, 600))
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE g (NU_ANO USMALLINT, SG_UF_PROVA VARCHAR, TIPO_ESCOLA VARCHAR,
        ESCOLARIDADE_PAI VARCHAR, ESCOLARIDADE_MAE VARCHAR, RENDA_FAMILIAR VARCHAR,
        NU_NOTA_CN DECIMAL(5,1), NU_NOTA_CH DECIMAL(5,1), NU_NOTA_LC DECIMAL(5,1),
        NU_NOTA_MT DECIMAL(5,1), NU_NOTA_REDACAO SMALLINT)"""
    )
    con.executemany("INSERT INTO g VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.execute(
        f"""COPY (SELECT *, COALESCE(0 IN (NU_NOTA_CN, NU_NOTA_CH, NU_NOTA_LC, NU_NOTA_MT), false)
        AS IN_NOTA_ZERO FROM g) TO '{path.as_posix()}' (FORMAT parquet)"""
    )
    con.close()
    return GoldEngine(str(path))


@pytest.fixture
def client(gold_engine):
    app.dependency_overrides[engine_dep] = lambda: gold_engine
    yield TestClient(app)
    app.dependency_overrides.pop(engine_dep, None)


def test_api_answers_both_questions(client):
    data = client.post(URL, json=BODY).json()
    assert data["n"] == 1000  # sem renda vazia e sem nota zero
    bands = {band["code"]: band for band in data["bands"]}
    assert bands["ate_1"]["likelihood"] == pytest.approx(0.05)
    assert data["total_probability"] == pytest.approx(0.23)
    assert bands["ate_1"]["posterior"] == pytest.approx(0.05 * 0.2 / 0.23)
    assert data["income"] == "ate_1"
    # cenário de referência: escola privada e renda acima de 10 salários
    assert data["reference"]["n"] == 200
    assert data["reference"]["percentile"] == pytest.approx(50.0)
    assert "causais" in data["disclaimer"]


def test_score_equal_to_the_limit_counts_as_reached(client):
    data = client.post(URL, json={**BODY, "score": 700}).json()
    assert data["total_probability"] == pytest.approx(0.23)
    assert data["percentile"] == 100.0


@pytest.mark.parametrize(
    "change",
    [
        {"income": "rico"},
        {"area": "XX"},
        {"score": 1500},
        {"score": 950},  # dentro de 0-1000, mas acima do máximo da edição
        {"score": "abc"},
        {"score": "nan"},
        {"year": 2017},
        {"year": 2025},  # perfil não ligado à nota
    ],
)
def test_api_rejects_invalid_input(client, change):
    assert client.post(URL, json={**BODY, **change}).status_code == 422


def test_unlinked_year_explains_why(client):
    response = client.post(URL, json={**BODY, "year": 2025})
    assert "2018 a 2023" in response.json()["detail"]


def test_edition_not_loaded(client):
    assert client.post(URL, json={**BODY, "year": 2020}).status_code == 404


def test_demo_engine_answers():
    app.dependency_overrides.pop(engine_dep, None)
    response = TestClient(app).post(URL, json={**BODY, "score": 550})
    assert response.status_code == 200
    data = response.json()
    assert data["data_source"] == "demo"
    assert sum(band["n"] for band in data["bands"]) == data["n"]
