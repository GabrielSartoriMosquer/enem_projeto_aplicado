from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.constants import AREA_LABELS
from app.core.models import AnalysisResponse, EssayInput, ScoreInput
from app.services.data_engine import DISCLAIMER, DataEngine, get_engine
from app.services.population import UNAVAILABLE as POPULATION_UNAVAILABLE
from app.services.population import PopulationEngine, get_population
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


def engine_dep(settings: Settings = Depends(get_settings)) -> DataEngine:
    return get_engine(settings)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="Erro interno ao consultar os dados.")


@router.get("/health")
def health(engine: DataEngine = Depends(engine_dep)):
    try:
        payload = engine.healthcheck()
        return {
            "status": "ok",
            "data_source": engine.source_name,
            # azure = gold baixada do data lake; local = arquivo no disco; demo = dados sintéticos
            "data_origin": getattr(engine, "data_origin", "local"),
            "dataset_version": getattr(engine, "dataset_version", "unknown"),
            "years": engine.years(),
            "available": payload.get("available", True),
            "duckdb": payload.get("duckdb", True),
        }
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/meta/years")
def years(engine: DataEngine = Depends(engine_dep)):
    return {
        "years": engine.years(),
        "data_source": engine.source_name,
        "data_origin": getattr(engine, "data_origin", "local"),
    }


@router.get("/meta/options")
def options(year: int = Query(..., ge=2018, le=2025), engine: DataEngine = Depends(engine_dep)):
    try:
        return engine.options(year)
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/analysis/summary")
def summary(year: int = Query(..., ge=2018, le=2025), engine: DataEngine = Depends(engine_dep)):
    try:
        return engine.summary(year)
    except Exception as exc:
        raise translate_error(exc) from exc


@router.post("/analysis/percentile", response_model=AnalysisResponse)
def percentile(payload: ScoreInput, engine: DataEngine = Depends(engine_dep)):
    try:
        engine.validate_scores(payload.year, payload.scores)
        results = engine.percentiles(payload.year, payload.scores)
        return {
            "year": payload.year,
            "data_source": engine.source_name,
            "results": results,
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/analysis/socioeconomic")
def socioeconomic(
    year: int = Query(..., ge=2018, le=2025),
    area: str = Query("MT"),
    dimension: str = Query("renda"),
    engine: DataEngine = Depends(engine_dep),
):
    if area not in AREA_LABELS:
        raise HTTPException(status_code=422, detail="Área inválida.")
    if dimension not in {"renda", "escolaridade_mae", "escolaridade_pai"}:
        raise HTTPException(status_code=422, detail="Dimensão socioeconômica inválida.")
    try:
        return {
            "year": year,
            "area": area,
            "area_label": AREA_LABELS[area],
            "dimension": dimension,
            "groups": engine.socioeconomic(year, area, dimension),
            "data_source": engine.source_name,
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/analysis/region-school")
def region_school(
    year: int = Query(..., ge=2018, le=2025),
    area: str = Query("MT"),
    school_type: int | None = Query(None, ge=1, le=3),
    engine: DataEngine = Depends(engine_dep),
):
    if area not in AREA_LABELS:
        raise HTTPException(status_code=422, detail="Área inválida.")
    try:
        data = engine.region_school(year, area, school_type)
        return {
            "year": year,
            "area": area,
            "area_label": AREA_LABELS[area],
            **data,
            "data_source": engine.source_name,
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:
        raise translate_error(exc) from exc


@router.post("/analysis/essay")
def essay(payload: EssayInput, engine: DataEngine = Depends(engine_dep)):
    try:
        return engine.essay(payload.year, payload.score)
    except Exception as exc:
        raise translate_error(exc) from exc


# Área "Quem faz o ENEM" (perfil dos inscritos) ---------------------------------------------


def population_dep(settings: Settings = Depends(get_settings)) -> PopulationEngine:
    engine = get_population(settings)
    if engine is None:
        raise HTTPException(status_code=503, detail=POPULATION_UNAVAILABLE)
    return engine


@router.get("/population/catalog")
def population_catalog(engine: PopulationEngine = Depends(population_dep)):
    return engine.catalog()


@router.get("/population/indicator")
def population_indicator(
    year: int = Query(..., ge=2018, le=2025),
    id: str = Query(..., max_length=40),
    engine: PopulationEngine = Depends(population_dep),
):
    try:
        return engine.indicator(year, id)
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/population/trend")
def population_trend(
    id: str = Query(..., max_length=40), engine: PopulationEngine = Depends(population_dep)
):
    try:
        return engine.trend(id)
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/population/crosstab")
def population_crosstab(
    year: int = Query(..., ge=2018, le=2025),
    id: str = Query(..., max_length=40),
    recorte: str = Query(..., max_length=20),
    engine: PopulationEngine = Depends(population_dep),
):
    try:
        return engine.crosstab(year, id, recorte)
    except Exception as exc:
        raise translate_error(exc) from exc


@router.get("/population/highlights")
def population_highlights(
    year: int = Query(..., ge=2018, le=2025),
    engine: PopulationEngine = Depends(population_dep),
):
    try:
        return engine.highlights(year)
    except Exception as exc:
        raise translate_error(exc) from exc
