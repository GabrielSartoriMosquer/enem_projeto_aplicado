from pathlib import Path

from app.core.constants import UF_CODES
from app.services.data_engine import PandasEngine

DATA = Path(__file__).resolve().parents[1] / "data" / "demo" / "enem_demo.csv"


def test_engine_years_and_options():
    engine = PandasEngine(str(DATA))
    assert engine.years() == list(range(2018, 2026))
    options = engine.options(2025)
    assert any(area["code"] == "MT" for area in options["areas"])


def test_engine_group_analytics():
    engine = PandasEngine(str(DATA))
    socio = engine.socioeconomic(2025, "MT", "renda")
    assert socio[0]["n"] > 0
    region = engine.region_school(2025, "LC")
    assert region["states"]


def test_canonical_ufs_are_exactly_the_27_brazilian_codes():
    assert len(UF_CODES) == 27
    assert len(set(UF_CODES)) == 27
    assert set(UF_CODES) == {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }


def test_region_school_keeps_missing_uf_without_fabricating_a_mean():
    engine = PandasEngine(str(DATA))
    engine.df = engine.df[engine.df["SG_UF_PROVA"] != "AC"]

    states = {state["uf"]: state for state in engine.region_school(2025, "MT")["states"]}

    assert len(states) == 27
    assert states["AC"]["n"] == 0
    assert states["AC"]["mean"] is None
    assert states["SP"]["n"] > 0
    assert states["SP"]["mean"] is not None
