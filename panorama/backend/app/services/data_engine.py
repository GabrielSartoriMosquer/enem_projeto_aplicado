from __future__ import annotations

import glob
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
from app.core.config import Settings
from app.core.constants import (
    AREA_COLUMNS,
    AREA_LABELS,
    Q001_Q002_LABELS,
    Q006_LABELS,
    SCHOOL_TYPE_LABELS,
    UF_CODES,
    UF_NAMES,
)
from app.services.statistics import compute_score_statistics

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Os resultados são estatístico-descritivos, calculados dentro da mesma edição do ENEM. "
    "Associações observadas não devem ser interpretadas como relações causais."
)


def discover_parquet_files(pattern: str) -> list[Path]:
    matches = [Path(path).resolve() for path in glob.glob(pattern, recursive=True)]
    if matches:
        return sorted({path for path in matches if path.is_file()})
    base_dir = Path(pattern).parent
    if base_dir.exists():
        files = sorted({path.resolve() for path in base_dir.rglob("*.parquet") if path.is_file()})
        if files:
            return files
    return []


class DataEngine(ABC):
    source_name: str
    dataset_version: str = "unknown"

    @abstractmethod
    def years(self) -> list[int]: ...

    @abstractmethod
    def summary(self, year: int) -> dict[str, Any]: ...

    @abstractmethod
    def percentiles(self, year: int, scores: dict[str, float]) -> list[dict[str, Any]]: ...

    @abstractmethod
    def socioeconomic(self, year: int, area: str, dimension: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def region_school(
        self, year: int, area: str, school_type: int | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    def essay(self, year: int, score: float) -> dict[str, Any]: ...

    @abstractmethod
    def options(self, year: int) -> dict[str, Any]: ...

    @abstractmethod
    def healthcheck(self) -> dict[str, Any]: ...


class PandasEngine(DataEngine):
    """Exact analytics engine for the bundled demonstration dataset."""

    source_name = "demo"
    dataset_version = "demo-synthetic"

    def __init__(self, csv_path: str):
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset demonstrativo não encontrado: {path}")
        self.df = pd.read_csv(path, low_memory=False)
        self.df["NU_ANO"] = self.df["NU_ANO"].astype(int)

    def _year(self, year: int) -> pd.DataFrame:
        frame = self.df[self.df["NU_ANO"] == year]
        if frame.empty:
            raise KeyError(f"Edição {year} não disponível.")
        return frame

    def years(self) -> list[int]:
        return sorted(self.df["NU_ANO"].dropna().astype(int).unique().tolist())

    def summary(self, year: int) -> dict[str, Any]:
        frame = self._year(year)
        means = {}
        for area, column in AREA_COLUMNS.items():
            means[area] = round(float(pd.to_numeric(frame[column], errors="coerce").mean()), 2)
        return {
            "year": year,
            "participants": int(frame.shape[0]),
            "means": means,
            "data_source": self.source_name,
            "disclaimer": DISCLAIMER,
        }

    def percentiles(self, year: int, scores: dict[str, float]) -> list[dict[str, Any]]:
        frame = self._year(year)
        results = []
        for area, score in scores.items():
            column = AREA_COLUMNS[area]
            stats = compute_score_statistics(frame[column], score)
            results.append(
                {
                    "area": area,
                    "label": AREA_LABELS[area],
                    "score": score,
                    "percentile": stats.percentile,
                    "z_score": stats.z_score,
                    "mean": stats.mean,
                    "std": stats.std,
                    "n": stats.n,
                }
            )
        return results

    def socioeconomic(self, year: int, area: str, dimension: str) -> list[dict[str, Any]]:
        frame = self._year(year)
        score_col = AREA_COLUMNS[area]
        dim_map = {
            "renda": ("Q006", Q006_LABELS),
            "escolaridade_mae": ("Q002", Q001_Q002_LABELS),
            "escolaridade_pai": ("Q001", Q001_Q002_LABELS),
        }
        column, labels = dim_map[dimension]
        grouped = (
            frame[[column, score_col]]
            .dropna()
            .groupby(column, observed=True)[score_col]
            .agg(["count", "mean", "median", "std"])
            .reset_index()
            .sort_values(column)
        )
        return [
            {
                "code": str(row[column]),
                "category": labels.get(str(row[column]), str(row[column])),
                "n": int(row["count"]),
                "mean": round(float(row["mean"]), 2),
                "median": round(float(row["median"]), 2),
                "std": round(float(row["std"]), 2) if pd.notna(row["std"]) else None,
            }
            for _, row in grouped.iterrows()
        ]

    def region_school(self, year: int, area: str, school_type: int | None = None) -> dict[str, Any]:
        frame = self._year(year)
        score_col = AREA_COLUMNS[area]
        if school_type is not None:
            frame = frame[frame["TP_ESCOLA"] == school_type]
        by_uf = (
            frame[["SG_UF_PROVA", score_col]]
            .dropna()
            .groupby("SG_UF_PROVA", observed=True)[score_col]
            .agg(["count", "mean"])
            .reset_index()
            .sort_values("mean", ascending=False)
        )
        by_school = (
            frame[["TP_ESCOLA", score_col]]
            .dropna()
            .groupby("TP_ESCOLA", observed=True)[score_col]
            .agg(["count", "mean"])
            .reset_index()
            .sort_values("mean", ascending=False)
        )
        state_stats = {
            str(row["SG_UF_PROVA"]): {
                "n": int(row["count"]),
                "mean": round(float(row["mean"]), 2),
            }
            for _, row in by_uf.iterrows()
        }
        ranked_ufs = [code for code in UF_CODES if code in state_stats]
        ranked_ufs.sort(key=lambda code: state_stats[code]["mean"], reverse=True)
        position = {code: index + 1 for index, code in enumerate(ranked_ufs)}
        national_values = pd.to_numeric(frame[score_col], errors="coerce").dropna()
        return {
            "states": [
                {
                    "uf": code,
                    "name": UF_NAMES[code],
                    "n": state_stats.get(code, {}).get("n", 0),
                    "mean": state_stats.get(code, {}).get("mean"),
                    "position": position.get(code),
                }
                for code in UF_CODES
            ],
            "school_types": [
                {
                    "code": int(row["TP_ESCOLA"]),
                    "category": SCHOOL_TYPE_LABELS.get(
                        int(row["TP_ESCOLA"]), str(row["TP_ESCOLA"])
                    ),
                    "n": int(row["count"]),
                    "mean": round(float(row["mean"]), 2),
                }
                for _, row in by_school.iterrows()
            ],
            "national_mean": round(float(national_values.mean()), 2)
            if not national_values.empty
            else None,
            "states_with_data": len(ranked_ufs),
        }

    def essay(self, year: int, score: float) -> dict[str, Any]:
        frame = self._year(year)
        stats = compute_score_statistics(frame[AREA_COLUMNS["REDACAO"]], score)
        return {
            "year": year,
            "score": score,
            "percentile": stats.percentile,
            "z_score": stats.z_score,
            "mean": stats.mean,
            "std": stats.std,
            "n": stats.n,
            "data_source": self.source_name,
            "disclaimer": DISCLAIMER,
        }

    def options(self, year: int) -> dict[str, Any]:
        frame = self._year(year)
        return {
            "year": year,
            "areas": [{"code": k, "label": v} for k, v in AREA_LABELS.items()],
            "ufs": list(UF_CODES),
            "school_types": [
                {"code": int(value), "label": SCHOOL_TYPE_LABELS.get(int(value), str(value))}
                for value in sorted(frame["TP_ESCOLA"].dropna().astype(int).unique().tolist())
            ],
        }

    def healthcheck(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "source": self.source_name,
            "dataset_version": self.dataset_version,
            "years": self.years(),
            "available": True,
        }


class DuckDBEngine(DataEngine):
    """DuckDB engine over year-partitioned Parquet files."""

    source_name = "official"
    dataset_version = "parquet-partitioned"

    def __init__(self, parquet_glob: str):
        import duckdb  # lazy import to keep demo mode lightweight

        self.duckdb = duckdb
        self.parquet_glob = parquet_glob.replace("\\", "/")
        self._validate()

    def _connect(self):
        con = self.duckdb.connect(database=":memory:")
        con.execute("PRAGMA threads=4")
        return con

    def _base(self) -> str:
        escaped = self.parquet_glob.replace("'", "''")
        return f"read_parquet('{escaped}', hive_partitioning=true, union_by_name=true)"

    def _validate(self) -> None:
        files = discover_parquet_files(self.parquet_glob)
        if not files:
            raise FileNotFoundError(
                f"Nenhum arquivo Parquet encontrado para o glob: {self.parquet_glob}"
            )
        with self._connect() as con:
            con.execute(f"SELECT 1 FROM {self._base()} LIMIT 1").fetchone()

    def years(self) -> list[int]:
        with self._connect() as con:
            rows = con.execute(
                f"SELECT DISTINCT NU_ANO FROM {self._base()} ORDER BY NU_ANO"
            ).fetchall()
        return [int(row[0]) for row in rows]

    def _ensure_year(self, year: int) -> None:
        if year not in self.years():
            raise KeyError(f"Edição {year} não disponível.")

    def summary(self, year: int) -> dict[str, Any]:
        self._ensure_year(year)
        expr = ", ".join(f"AVG({col}) AS {area}" for area, col in AREA_COLUMNS.items())
        sql = f"SELECT COUNT(*) AS n, {expr} FROM {self._base()} WHERE NU_ANO = ?"
        with self._connect() as con:
            row = con.execute(sql, [year]).fetchone()
        return {
            "year": year,
            "participants": int(row[0]),
            "means": {area: round(float(row[i + 1]), 2) for i, area in enumerate(AREA_COLUMNS)},
            "data_source": self.source_name,
            "disclaimer": DISCLAIMER,
        }

    def percentiles(self, year: int, scores: dict[str, float]) -> list[dict[str, Any]]:
        self._ensure_year(year)
        results = []
        with self._connect() as con:
            for area, score in scores.items():
                col = AREA_COLUMNS[area]
                sql = f"""
                    SELECT
                        COUNT({col}) AS n,
                        AVG({col}) AS mean,
                        STDDEV_POP({col}) AS std,
                        100.0 * SUM(CASE WHEN {col} <= ? THEN 1 ELSE 0 END) / COUNT({col}) AS pct
                    FROM {self._base()}
                    WHERE NU_ANO = ? AND {col} IS NOT NULL
                """
                n, mean, std, pct = con.execute(sql, [score, year]).fetchone()
                z = (score - mean) / std if std and std > 0 else None
                results.append(
                    {
                        "area": area,
                        "label": AREA_LABELS[area],
                        "score": score,
                        "percentile": round(float(pct), 2),
                        "z_score": round(float(z), 3) if z is not None else None,
                        "mean": round(float(mean), 2),
                        "std": round(float(std), 2) if std is not None else None,
                        "n": int(n),
                    }
                )
        return results

    def socioeconomic(self, year: int, area: str, dimension: str) -> list[dict[str, Any]]:
        self._ensure_year(year)
        score_col = AREA_COLUMNS[area]
        dim_map = {
            "renda": ("Q006", Q006_LABELS),
            "escolaridade_mae": ("Q002", Q001_Q002_LABELS),
            "escolaridade_pai": ("Q001", Q001_Q002_LABELS),
        }
        dim_col, labels = dim_map[dimension]
        sql = f"""
            SELECT {dim_col}, COUNT({score_col}), AVG({score_col}),
                   MEDIAN({score_col}), STDDEV_SAMP({score_col})
            FROM {self._base()}
            WHERE NU_ANO = ? AND {dim_col} IS NOT NULL AND {score_col} IS NOT NULL
            GROUP BY {dim_col}
            ORDER BY {dim_col}
        """
        with self._connect() as con:
            rows = con.execute(sql, [year]).fetchall()
        return [
            {
                "code": str(code),
                "category": labels.get(str(code), str(code)),
                "n": int(n),
                "mean": round(float(mean), 2),
                "median": round(float(median), 2),
                "std": round(float(std), 2) if std is not None else None,
            }
            for code, n, mean, median, std in rows
        ]

    def region_school(self, year: int, area: str, school_type: int | None = None) -> dict[str, Any]:
        self._ensure_year(year)
        score_col = AREA_COLUMNS[area]
        where = f"NU_ANO=? AND SG_UF_PROVA IS NOT NULL AND {score_col} IS NOT NULL"
        params: list[Any] = [year]
        if school_type is not None:
            where += " AND TP_ESCOLA=?"
            params.append(school_type)
        with self._connect() as con:
            uf_rows = con.execute(
                f"""SELECT SG_UF_PROVA, COUNT({score_col}), AVG({score_col})
                FROM {self._base()} WHERE {where}
                GROUP BY SG_UF_PROVA ORDER BY 3 DESC""",
                params,
            ).fetchall()
            school_rows = con.execute(
                f"""SELECT TP_ESCOLA, COUNT({score_col}), AVG({score_col})
                FROM {self._base()} WHERE NU_ANO=?
                AND TP_ESCOLA IS NOT NULL AND {score_col} IS NOT NULL
                GROUP BY TP_ESCOLA ORDER BY 3 DESC""",
                [year],
            ).fetchall()
            national_row = con.execute(
                f"SELECT COUNT({score_col}), AVG({score_col}) FROM {self._base()} WHERE {where}",
                params,
            ).fetchone()
        state_stats = {
            str(uf): {"n": int(n), "mean": round(float(mean), 2)} for uf, n, mean in uf_rows
        }
        ranked_ufs = [code for code in UF_CODES if code in state_stats]
        ranked_ufs.sort(key=lambda code: state_stats[code]["mean"], reverse=True)
        position = {code: index + 1 for index, code in enumerate(ranked_ufs)}
        return {
            "states": [
                {
                    "uf": code,
                    "name": UF_NAMES[code],
                    "n": state_stats.get(code, {}).get("n", 0),
                    "mean": state_stats.get(code, {}).get("mean"),
                    "position": position.get(code),
                }
                for code in UF_CODES
            ],
            "school_types": [
                {
                    "code": int(code),
                    "category": SCHOOL_TYPE_LABELS.get(int(code), str(code)),
                    "n": int(n),
                    "mean": round(float(mean), 2),
                }
                for code, n, mean in school_rows
            ],
            "national_mean": round(float(national_row[1]), 2)
            if national_row[1] is not None
            else None,
            "states_with_data": len(ranked_ufs),
        }

    def essay(self, year: int, score: float) -> dict[str, Any]:
        row = self.percentiles(year, {"REDACAO": score})[0]
        return {
            "year": year,
            **{k: v for k, v in row.items() if k not in {"area", "label"}},
            "data_source": self.source_name,
            "disclaimer": DISCLAIMER,
        }

    def options(self, year: int) -> dict[str, Any]:
        self._ensure_year(year)
        with self._connect() as con:
            schools = [
                r[0]
                for r in con.execute(
                    f"SELECT DISTINCT TP_ESCOLA FROM {self._base()} "
                    "WHERE NU_ANO=? AND TP_ESCOLA IS NOT NULL ORDER BY 1",
                    [year],
                ).fetchall()
            ]
        return {
            "year": year,
            "areas": [{"code": k, "label": v} for k, v in AREA_LABELS.items()],
            "ufs": list(UF_CODES),
            "school_types": [
                {"code": int(v), "label": SCHOOL_TYPE_LABELS.get(int(v), str(v))} for v in schools
            ],
        }

    def healthcheck(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "source": self.source_name,
            "dataset_version": self.dataset_version,
            "years": self.years(),
            "available": True,
        }


# Colunas que a camada gold do ETL (src/enem_pja3/load/load.py) precisa ter.
GOLD_REQUIRED_COLUMNS = (
    "NU_ANO",
    "SG_UF_PROVA",
    "TIPO_ESCOLA",
    "ESCOLARIDADE_PAI",
    "ESCOLARIDADE_MAE",
    "RENDA_FAMILIAR",
    *AREA_COLUMNS.values(),
    "IN_NOTA_ZERO",
)


class GoldEngine(DuckDBEngine):
    """DuckDB engine over the ETL gold layer (``data/gold/enem_notas.parquet``).

    A gold junta as 8 edições em um único Parquet com colunas harmonizadas entre os anos.
    Aqui elas são traduzidas para o mesmo contrato usado pelos outros engines:

    - ``TIPO_ESCOLA`` ('publica'/'privada') vira ``TP_ESCOLA`` 2/3. Nas edições em que o INEP
      liga escola e nota (2018 a 2023), vazio significa "não respondeu" (código 1). Em 2024 e
      2025 o perfil não está ligado à nota, então fica vazio. 'exterior' (só em 2018) fica de fora;
    - ``ESCOLARIDADE_PAI``, ``ESCOLARIDADE_MAE`` e ``RENDA_FAMILIAR`` viram Q001, Q002 e Q006
      (mesmos códigos A–H e A–Q em todos os anos);
    - linhas com ``IN_NOTA_ZERO`` (0 em alguma prova objetiva) são excluídas, como recomenda
      o ETL, porque distorcem média, percentil e z-score.
    """

    source_name = "official"
    dataset_version = "enem-pja3-gold"

    def __init__(self, gold_path: str):
        import duckdb  # lazy import to keep demo mode lightweight

        self.duckdb = duckdb
        self.gold_path = Path(gold_path).resolve().as_posix()
        self._years: list[int] = []
        self._school_years: list[int] = []
        self._validate()

    def _source(self) -> str:
        escaped = self.gold_path.replace("'", "''")
        return f"read_parquet('{escaped}')"

    def _base(self) -> str:
        school_years = ", ".join(str(year) for year in self._school_years) or "NULL"
        notas = ", ".join(
            f"CAST({column} AS DOUBLE) AS {column}" for column in AREA_COLUMNS.values()
        )
        return f"""(
            SELECT
                CAST(NU_ANO AS INTEGER) AS NU_ANO,
                SG_UF_PROVA,
                CASE
                    WHEN TIPO_ESCOLA = 'publica' THEN 2
                    WHEN TIPO_ESCOLA = 'privada' THEN 3
                    WHEN TIPO_ESCOLA IS NULL AND NU_ANO IN ({school_years}) THEN 1
                END AS TP_ESCOLA,
                ESCOLARIDADE_PAI AS Q001,
                ESCOLARIDADE_MAE AS Q002,
                RENDA_FAMILIAR AS Q006,
                {notas}
            FROM {self._source()}
            WHERE IN_NOTA_ZERO IS NOT TRUE
        ) AS gold"""

    def _validate(self) -> None:
        if not Path(self.gold_path).is_file():
            raise FileNotFoundError(f"Camada gold não encontrada: {self.gold_path}")
        with self._connect() as con:
            columns = {
                row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {self._source()}").fetchall()
            }
            missing = [column for column in GOLD_REQUIRED_COLUMNS if column not in columns]
            if missing:
                raise ValueError(
                    "Camada gold sem as colunas esperadas: "
                    + ", ".join(missing)
                    + ". Gere a gold novamente com o ETL atualizado."
                )
            rows = con.execute(
                f"""SELECT CAST(NU_ANO AS INTEGER), COUNT(TIPO_ESCOLA)
                FROM {self._source()} WHERE NU_ANO IS NOT NULL GROUP BY 1 ORDER BY 1"""
            ).fetchall()
        if not rows:
            raise ValueError(f"Camada gold vazia: {self.gold_path}")
        self._years = [int(year) for year, _ in rows]
        self._school_years = [int(year) for year, with_school in rows if with_school > 0]

    def years(self) -> list[int]:
        return list(self._years)


_engine_cache: dict[tuple[str, str, str, str], DataEngine] = {}
_engine_lock = Lock()


def build_engine(settings: Settings) -> DataEngine:
    mode = settings.normalized_data_mode
    parquet_candidates = discover_parquet_files(settings.parquet_glob)

    gold_available = Path(settings.gold_path).is_file()

    if mode == "official":
        if gold_available:
            try:
                engine = GoldEngine(settings.gold_path)
                logger.info("Fonte oficial (camada gold) selecionada: %s", settings.gold_path)
                return engine
            except Exception as exc:
                raise RuntimeError(
                    "Camada gold encontrada, mas inválida para consulta analítica."
                ) from exc
        if not parquet_candidates:
            raise FileNotFoundError(
                f"Dados oficiais não encontrados para o padrão: {settings.parquet_glob}."
            )
        try:
            engine = DuckDBEngine(settings.parquet_glob)
            logger.info("Fonte oficial selecionada para %s", settings.parquet_glob)
            return engine
        except Exception as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "Dados oficiais detectados, mas inválidos para consulta analítica."
            ) from exc

    if mode == "demo":
        engine = PandasEngine(settings.demo_csv)
        logger.info("Fonte demo selecionada explicitamente.")
        return engine

    if gold_available:
        try:
            engine = GoldEngine(settings.gold_path)
            logger.info("Modo auto selecionou a camada gold do ETL: %s", settings.gold_path)
            return engine
        except Exception as exc:
            logger.warning("Camada gold detectada, mas inválida; tentando outras fontes. %s", exc)

    if parquet_candidates:
        try:
            engine = DuckDBEngine(settings.parquet_glob)
            logger.info("Modo auto selecionou origem oficial para o dataset Parquet detectado.")
            return engine
        except Exception as exc:
            logger.warning("Parquet detectado, mas inválido; usando demo. Detalhe: %s", exc)

    engine = PandasEngine(settings.demo_csv)
    logger.info(
        "Modo auto usou fonte demo porque os dados oficiais não estavam válidos ou indisponíveis."
    )
    return engine


def get_engine(settings: Settings) -> DataEngine:
    global _engine_cache
    cache_key = (
        settings.normalized_data_mode,
        settings.gold_path,
        settings.parquet_glob,
        settings.demo_csv,
    )
    with _engine_lock:
        engine = _engine_cache.get(cache_key)
        if engine is None:
            engine = build_engine(settings)
            _engine_cache[cache_key] = engine
        return engine


def reset_engine() -> None:
    global _engine_cache
    with _engine_lock:
        _engine_cache.clear()
