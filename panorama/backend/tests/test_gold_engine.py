"""Integração com a camada gold do ETL (src/enem_pja3, na raiz do repositório).

Os testes criam um ``enem_notas.parquet`` pequeno com o mesmo esquema e tipos da gold real
(USMALLINT, DECIMAL(5,1), TIPO_ESCOLA em texto, IN_NOTA_ZERO etc.).
"""

from __future__ import annotations

import duckdb
import pytest
from app.api.routes import engine_dep
from app.core.config import Settings
from app.main import app
from app.services.data_engine import GoldEngine, PandasEngine, build_engine, get_engine
from fastapi.testclient import TestClient

DEMO_CSV = Settings().demo_csv

# NU_ANO, UF, TIPO_ESCOLA, ESC_PAI, ESC_MAE, RENDA, CN, CH, LC, MT, REDACAO
ROWS = [
    (2018, "SP", "publica", "B", "C", "A", 500.0, 520.0, 540.0, 560.0, 600),
    (2018, "SP", "privada", "F", "G", "Q", 700.0, 720.0, 740.0, 800.0, 900),
    (2018, "RJ", None, "A", "A", "B", 400.0, 420.0, 440.0, 460.0, 500),
    (2018, "RJ", "exterior", "H", "H", "C", 650.0, 650.0, 650.0, 650.0, 700),
    # nota 0 em CH: precisa ficar fora de todas as estatísticas
    (2018, "SP", "publica", "A", "A", "A", 450.0, 0.0, 480.0, 490.0, 520),
    # ausente: notas vazias, conta como participante mas não entra nas médias
    (2018, "MG", "publica", "C", "C", "D", None, None, None, None, None),
    # 2025: perfil não ligado à nota
    (2025, "SP", None, None, None, None, 510.0, 530.0, 550.0, 600.0, 640),
    (2025, "BA", None, None, None, None, 470.0, 480.0, 500.0, 520.0, 560),
]


def write_gold(path, with_zero_flag: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE g (
            NU_ANO USMALLINT, SG_UF_PROVA VARCHAR, TIPO_ESCOLA VARCHAR,
            ESCOLARIDADE_PAI VARCHAR, ESCOLARIDADE_MAE VARCHAR, RENDA_FAMILIAR VARCHAR,
            NU_NOTA_CN DECIMAL(5,1), NU_NOTA_CH DECIMAL(5,1), NU_NOTA_LC DECIMAL(5,1),
            NU_NOTA_MT DECIMAL(5,1), NU_NOTA_REDACAO SMALLINT
        )"""
    )
    con.executemany("INSERT INTO g VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    # Mesma regra do ETL (enem_pja3/load/load.py). Sem a flag = gold gerada antes de 03/11/2026.
    flag = "COALESCE(0 IN (NU_NOTA_CN, NU_NOTA_CH, NU_NOTA_LC, NU_NOTA_MT), false)"
    columns = f"*, {flag} AS IN_NOTA_ZERO" if with_zero_flag else "*"
    con.execute(f"COPY (SELECT {columns} FROM g) TO '{path.as_posix()}' (FORMAT parquet)")
    con.close()
    return path


@pytest.fixture
def gold_path(tmp_path):
    return write_gold(tmp_path / "gold" / "enem_notas.parquet")


@pytest.fixture
def engine(gold_path):
    return GoldEngine(str(gold_path))


def test_years_and_school_coverage(engine):
    assert engine.years() == [2018, 2025]
    assert engine.source_name == "official"
    assert engine.dataset_version == "enem-pja3-gold"
    assert engine.options(2018)["school_types"] == [
        {"code": 1, "label": "Não respondeu"},
        {"code": 2, "label": "Pública"},
        {"code": 3, "label": "Privada"},
    ]
    # 2025 não liga escola à nota: não inventa "não respondeu"
    assert engine.options(2025)["school_types"] == []


def test_summary_excludes_zero_scores(engine):
    summary = engine.summary(2018)
    # 6 linhas em 2018, menos a de nota zero
    assert summary["participants"] == 5
    assert summary["means"]["CH"] == pytest.approx((520 + 720 + 420 + 650) / 4, abs=0.01)
    assert summary["means"]["MT"] == pytest.approx((560 + 800 + 460 + 650) / 4, abs=0.01)
    assert summary["data_source"] == "official"


def test_unknown_year_raises_key_error(engine):
    with pytest.raises(KeyError):
        engine.summary(2020)


def test_percentile_and_essay(engine):
    (mt,) = engine.percentiles(2018, {"MT": 650})
    assert mt["n"] == 4
    assert mt["percentile"] == 75.0
    assert mt["mean"] == pytest.approx(617.5)
    essay = engine.essay(2025, 600)
    assert essay["n"] == 2
    assert essay["percentile"] == 50.0
    assert essay["mean"] == 600.0


def test_socioeconomic_uses_harmonized_columns(engine):
    renda = {group["code"]: group for group in engine.socioeconomic(2018, "MT", "renda")}
    assert set(renda) == {"A", "B", "C", "Q"}
    assert renda["A"]["n"] == 1  # a linha de nota zero (também renda A) ficou fora
    assert renda["Q"]["mean"] == 800.0
    assert renda["Q"]["category"].startswith("Q")

    mae = {
        group["code"]: group["mean"]
        for group in engine.socioeconomic(2018, "MT", "escolaridade_mae")
    }
    assert mae == {"A": 460.0, "C": 560.0, "G": 800.0, "H": 650.0}
    pai = {group["code"] for group in engine.socioeconomic(2018, "MT", "escolaridade_pai")}
    assert pai == {"A", "B", "F", "H"}

    assert engine.socioeconomic(2025, "MT", "renda") == []


def test_region_school_maps_school_type(engine):
    data = engine.region_school(2018, "MT")
    schools = {item["code"]: item for item in data["school_types"]}
    assert set(schools) == {1, 2, 3}  # 'exterior' fica de fora
    assert schools[1]["mean"] == 460.0
    assert schools[2]["mean"] == 560.0
    assert schools[3]["mean"] == 800.0
    states = {item["uf"]: item for item in data["states"]}
    assert len(states) == 27
    assert states["SP"]["n"] == 2
    assert states["RJ"]["n"] == 2
    assert states["MG"]["mean"] is None  # só tinha ausente
    assert data["states_with_data"] == 2

    publica = engine.region_school(2018, "MT", 2)
    assert publica["national_mean"] == 560.0
    assert publica["states_with_data"] == 1

    sem_ligacao = engine.region_school(2025, "MT", 2)
    assert sem_ligacao["states_with_data"] == 0
    assert sem_ligacao["national_mean"] is None


def test_missing_file_and_missing_columns(tmp_path):
    with pytest.raises(FileNotFoundError):
        GoldEngine(str(tmp_path / "nao_existe.parquet"))
    old_gold = write_gold(tmp_path / "old" / "enem_notas.parquet", with_zero_flag=False)
    with pytest.raises(ValueError, match="IN_NOTA_ZERO"):
        GoldEngine(str(old_gold))


def test_auto_mode_prefers_gold(gold_path, tmp_path):
    settings = Settings(
        data_mode="auto",
        gold_path=str(gold_path),
        parquet_glob=str(tmp_path / "parquet" / "ano=*" / "enem.parquet"),
        demo_csv=DEMO_CSV,
    )
    assert isinstance(build_engine(settings), GoldEngine)


def test_auto_mode_falls_back_to_demo_when_gold_is_invalid(tmp_path):
    old_gold = write_gold(tmp_path / "old" / "enem_notas.parquet", with_zero_flag=False)
    settings = Settings(
        data_mode="auto",
        gold_path=str(old_gold),
        parquet_glob=str(tmp_path / "parquet" / "ano=*" / "enem.parquet"),
        demo_csv=DEMO_CSV,
    )
    assert isinstance(build_engine(settings), PandasEngine)


def test_official_mode_uses_gold_and_rejects_invalid_gold(gold_path, tmp_path):
    parquet_glob = str(tmp_path / "parquet" / "ano=*" / "enem.parquet")
    official = Settings(data_mode="official", gold_path=str(gold_path), parquet_glob=parquet_glob)
    assert isinstance(build_engine(official), GoldEngine)

    old_gold = write_gold(tmp_path / "old" / "enem_notas.parquet", with_zero_flag=False)
    invalid = Settings(data_mode="official", gold_path=str(old_gold), parquet_glob=parquet_glob)
    with pytest.raises(RuntimeError):
        build_engine(invalid)


def test_demo_mode_ignores_gold(gold_path):
    settings = Settings(data_mode="demo", gold_path=str(gold_path), demo_csv=DEMO_CSV)
    assert isinstance(get_engine(settings), PandasEngine)


def test_api_end_to_end_with_gold(engine):
    app.dependency_overrides[engine_dep] = lambda: engine
    try:
        client = TestClient(app)
        health = client.get("/api/v1/health").json()
        assert health["data_source"] == "official"
        assert health["dataset_version"] == "enem-pja3-gold"
        assert health["years"] == [2018, 2025]

        response = client.post(
            "/api/v1/analysis/percentile", json={"year": 2018, "scores": {"MT": 650}}
        )
        assert response.status_code == 200
        assert response.json()["results"][0]["percentile"] == 75.0

        socio = client.get(
            "/api/v1/analysis/socioeconomic",
            params={"year": 2025, "area": "MT", "dimension": "renda"},
        )
        assert socio.status_code == 200
        assert socio.json()["groups"] == []

        region = client.get(
            "/api/v1/analysis/region-school",
            params={"year": 2018, "area": "LC", "school_type": 3},
        )
        assert region.status_code == 200
        assert region.json()["national_mean"] == 740.0

        assert client.get("/api/v1/analysis/summary", params={"year": 2020}).status_code == 404
    finally:
        app.dependency_overrides.pop(engine_dep, None)
