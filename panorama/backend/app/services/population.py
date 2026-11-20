"""Área "Quem faz o ENEM": perfil dos inscritos a partir de gold/enem_perfil_resumo.parquet.

O resumo (gerado pelo ETL em src/enem_pja3/load/resumo.py) tem só contagens: quantos inscritos de
cada ano e UF deram cada resposta, mais cruzamentos nacionais por renda, cor/raça, sexo e escola.
São poucos milhares de linhas, então ficam em memória e cada consulta é só soma e divisão.

Com o data lake configurado, o arquivo vem do container gold, como as notas. Sem o arquivo (modo
demonstração, por exemplo), a área fica indisponível e as rotas respondem 503.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import Settings
from app.core.constants import UF_NAMES
from app.core.population_catalog import INDICATORS, RECORTES, THEMES

logger = logging.getLogger(__name__)

UNAVAILABLE = "O perfil dos inscritos não está disponível no momento."


def pct(part: float, total: float) -> float | None:
    return round(100 * part / total, 1) if total else None


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%".replace(".", ",")


class PopulationEngine:
    def __init__(self, path: str | Path, origin: str = "local"):
        import duckdb

        self.path = Path(path)
        self.origin = origin
        rows = duckdb.sql(
            f"SELECT NU_ANO, SG_UF_PROVA, INDICADOR, CATEGORIA, RECORTE, RECORTE_CATEGORIA, N "
            f"FROM read_parquet('{self.path.as_posix()}')"
        ).fetchall()
        # by_uf: (ano, indicador) -> uf -> categoria -> n
        # cross: (ano, indicador, recorte) -> grupo -> categoria -> n
        self.by_uf: dict[tuple, dict] = defaultdict(lambda: defaultdict(dict))
        self.cross: dict[tuple, dict] = defaultdict(lambda: defaultdict(dict))
        for year, uf, indicator, category, recorte, group, n in rows:
            if recorte is None:
                self.by_uf[(int(year), indicator)][uf][category] = int(n)
            else:
                self.cross[(int(year), indicator, recorte)][group][category] = int(n)
        self._years = sorted({year for year, _ in self.by_uf})

    # Utilidades -------------------------------------------------------------------------------

    def years(self) -> list[int]:
        return self._years

    def _check(self, year: int | None, indicator: str) -> dict:
        if indicator not in INDICATORS:
            raise KeyError(f"Indicador desconhecido: {indicator}.")
        if year is not None and year not in self._years:
            raise KeyError(f"Edição {year} não disponível.")
        return INDICATORS[indicator]

    def indicator_years(self, indicator: str) -> list[int]:
        return [year for year in self._years if self.by_uf.get((year, indicator))]

    @staticmethod
    def _notes(meta: dict, year: int | None) -> list[str]:
        return [
            note["text"]
            for note in meta.get("notes", [])
            if year is None or (note.get("from", 0) <= year <= note.get("to", 9999))
        ]

    @staticmethod
    def _distribution(meta: dict, counts: dict[str, int]) -> dict[str, Any]:
        total = sum(counts.values())
        highlight = sum(counts.get(code, 0) for code in meta["highlight"])
        return {
            "total": total,
            "highlight_pct": pct(highlight, total),
            "categories": [
                {
                    "code": code,
                    "label": label,
                    "n": counts.get(code, 0),
                    "pct": pct(counts.get(code, 0), total),
                }
                for code, label in meta["categories"]
            ],
        }

    def _national(self, year: int, indicator: str) -> dict[str, int]:
        totals: dict[str, int] = defaultdict(int)
        for counts in self.by_uf.get((year, indicator), {}).values():
            for category, n in counts.items():
                totals[category] += n
        return totals

    def _meta(self, indicator: str, meta: dict) -> dict[str, Any]:
        return {
            "id": indicator,
            "label": meta["label"],
            "theme": meta["theme"],
            "question": meta["question"],
            "highlight": meta["highlight"],
            "highlight_label": meta["highlight_label"],
            "map": meta.get("map", True),
            "years": self.indicator_years(indicator),
        }

    # Consultas --------------------------------------------------------------------------------

    def catalog(self) -> dict[str, Any]:
        return {
            "years": self._years,
            "themes": THEMES,
            "indicators": [self._meta(key, meta) for key, meta in INDICATORS.items()],
            "recortes": [{"id": key, "label": value["label"]} for key, value in RECORTES.items()],
        }

    def indicator(self, year: int, indicator: str) -> dict[str, Any]:
        meta = self._check(year, indicator)
        states_counts = self.by_uf.get((year, indicator), {})
        national = self._distribution(meta, self._national(year, indicator))
        states = [
            {"uf": uf, "name": UF_NAMES.get(uf, uf), **self._distribution(meta, counts)}
            for uf, counts in sorted(states_counts.items())
        ]
        return {
            "year": year,
            "indicator": self._meta(indicator, meta),
            "available": bool(states_counts),
            "national": national,
            "states": states,
            "notes": self._notes(meta, year),
        }

    def trend(self, indicator: str) -> dict[str, Any]:
        meta = self._check(None, indicator)
        points = []
        for year in self._years:
            counts = self._national(year, indicator)
            points.append(
                {"year": year, **self._distribution(meta, counts)}
                if counts
                else {"year": year, "total": 0, "highlight_pct": None, "categories": []}
            )
        notes = [note for note in meta.get("notes", []) if "from" in note]
        return {
            "indicator": self._meta(indicator, meta),
            "points": points,
            "breaks": [{"year": note["from"], "text": note["text"]} for note in notes],
        }

    def crosstab(self, year: int, indicator: str, recorte: str) -> dict[str, Any]:
        meta = self._check(year, indicator)
        if recorte not in RECORTES:
            raise KeyError(f"Recorte desconhecido: {recorte}.")
        groups = self.cross.get((year, indicator, recorte), {})
        return {
            "year": year,
            "indicator": self._meta(indicator, meta),
            "recorte": {"id": recorte, "label": RECORTES[recorte]["label"]},
            "groups": [
                {"code": code, "label": label, **self._distribution(meta, groups[code])}
                for code, label in RECORTES[recorte]["categories"]
                if groups.get(code)
            ],
        }

    def highlights(self, year: int) -> dict[str, Any]:
        """Fatos de destaque da edição, com o número e a frase prontos para exibir"""
        if year not in self._years:
            raise KeyError(f"Edição {year} não disponível.")
        facts = []

        def share(indicator: str) -> float | None:
            if not self.by_uf.get((year, indicator)):
                return None
            return self._distribution(INDICATORS[indicator], self._national(year, indicator))[
                "highlight_pct"
            ]

        def by_group(indicator: str, recorte: str) -> dict[str, float | None]:
            groups = self.cross.get((year, indicator, recorte), {})
            return {
                code: self._distribution(INDICATORS[indicator], counts)["highlight_pct"]
                for code, counts in groups.items()
            }

        computer = share("computador")
        if computer is not None:
            income = by_group("computador", "renda")
            text = "dos inscritos não têm computador em casa."
            detail = None
            if income.get("ate_1") is not None and income.get("mais_10") is not None:
                detail = (
                    "Entre quem tem renda familiar de até 1 salário mínimo, "
                    f"são {fmt_pct(income['ate_1'])}; "
                    f"acima de 10 salários, {fmt_pct(income['mais_10'])}."
                )
            facts.append(
                {
                    "id": "computador",
                    "indicator": "computador",
                    "value": computer,
                    "text": text,
                    "detail": detail,
                }
            )

        internet = share("internet")
        if internet is not None:
            states = self.indicator(year, "internet")["states"]
            ranked = sorted(
                (s for s in states if s["highlight_pct"] is not None),
                key=lambda s: s["highlight_pct"],
            )
            detail = None
            if ranked:
                detail = (
                    f"Vai de {fmt_pct(ranked[0]['highlight_pct'])} em {ranked[0]['name']} "
                    f"a {fmt_pct(ranked[-1]['highlight_pct'])} em {ranked[-1]['name']}."
                )
            facts.append(
                {
                    "id": "internet",
                    "indicator": "internet",
                    "value": internet,
                    "text": "não têm internet em casa.",
                    "detail": detail,
                }
            )

        income = share("renda_familiar")
        if income is not None:
            facts.append(
                {
                    "id": "renda",
                    "indicator": "renda_familiar",
                    "value": income,
                    "text": "vivem com renda familiar de até 1 salário mínimo.",
                    "detail": "Somando a renda de todos que moram na casa.",
                }
            )

        mothers = share("escolaridade_mae")
        if mothers is not None:
            facts.append(
                {
                    "id": "maes",
                    "indicator": "escolaridade_mae",
                    "value": mothers,
                    "text": "têm mães que não completaram o ensino fundamental.",
                    "detail": None,
                }
            )

        women = share("sexo")
        if women is not None:
            facts.append(
                {
                    "id": "mulheres",
                    "indicator": "sexo",
                    "value": women,
                    "text": "dos inscritos são mulheres.",
                    "detail": None,
                }
            )

        black = share("cor_raca")
        if black is not None:
            facts.append(
                {
                    "id": "cor_raca",
                    "indicator": "cor_raca",
                    "value": black,
                    "text": "se declaram pretos ou pardos.",
                    "detail": None,
                }
            )

        total = sum(sum(counts.values()) for counts in self.by_uf.get((year, "sexo"), {}).values())
        return {"year": year, "participants": total, "facts": facts}


_engine_cache: dict[tuple, PopulationEngine | None] = {}
_engine_lock = Lock()


def _resolve_path(settings: Settings) -> tuple[Path, str]:
    """Com o lake configurado, usa a cópia sincronizada do Azure; senão, o arquivo local"""
    from app.services import lake

    local = Path(settings.population_path)
    if settings.normalized_data_mode == "demo" or not lake.lake_enabled(settings):
        return local, "local"
    try:
        path = lake.sync_file(
            settings, settings.lake_population_file, Path(settings.lake_population_cache_path)
        )
        return path, "azure"
    except Exception as exc:
        logger.error(
            "Falha ao obter o resumo do perfil no data lake; usando o arquivo local. %s", exc
        )
        return local, "local"


def get_population(settings: Settings) -> PopulationEngine | None:
    key = (
        settings.normalized_data_mode,
        settings.population_path,
        settings.lake_population_cache_path,
    )
    with _engine_lock:
        if key not in _engine_cache:
            engine = None
            if settings.normalized_data_mode != "demo":
                path, origin = _resolve_path(settings)
                if path.is_file():
                    try:
                        engine = PopulationEngine(path, origin)
                        logger.info("Perfil dos inscritos carregado de %s (%s)", path, origin)
                    except Exception as exc:
                        logger.error("Resumo do perfil inválido em %s: %s", path, exc)
            _engine_cache[key] = engine
        return _engine_cache[key]


def reset_population() -> None:
    with _engine_lock:
        _engine_cache.clear()
