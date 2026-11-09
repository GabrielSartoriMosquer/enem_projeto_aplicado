from __future__ import annotations

import json
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

from app.etl.schema import COMMON_COLUMNS, NUMERIC_COLUMNS, REQUIRED_COLUMNS

VALID_UFS = {
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
VALID_SCHOOL_TYPES = {1, 2, 3}
VALID_SOCIO_CODES = set("ABCDEFGHIJKLMNO PQRSTU")
VALID_SOCIO_CODES.discard(" ")
VALID_QUESTION_CODES = {f"Q{i:03d}" for i in range(1, 26)}
NOTE_COLUMNS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]


def find_csv_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv") and "microdados" in name.lower()
        ]
        if not candidates:
            raise FileNotFoundError(f"CSV de microdados não encontrado dentro de {zip_path.name}")
        candidates.sort(
            key=lambda name: (
                "resultados" not in name.lower(),
                "participantes" not in name.lower(),
                "dados" not in name.lower(),
                len(name),
            )
        )
        return candidates[0]


def _row_rejections(frame: pd.DataFrame, year: int) -> tuple[pd.DataFrame, Counter[str]]:
    rejection_counter: Counter[str] = Counter()
    valid = frame.copy()

    if year < 2018 or year > 2025:
        rejection_counter["ano_invalido"] += len(valid)
        valid = valid.iloc[0:0].copy()
        return valid, rejection_counter

    if "SG_UF_PROVA" in valid.columns:
        uf_values = valid["SG_UF_PROVA"].astype("string").str.strip().str.upper()
        invalid_mask = ~uf_values.isin(VALID_UFS)
        if invalid_mask.any():
            rejection_counter["uf_invalida"] += int(invalid_mask.sum())
            valid = valid.loc[~invalid_mask].copy()

    if "TP_ESCOLA" in valid.columns:
        tp_values = pd.to_numeric(valid["TP_ESCOLA"], errors="coerce")
        if tp_values.notna().any():
            invalid_mask = ~tp_values.isin(list(VALID_SCHOOL_TYPES)) & tp_values.notna()
            if invalid_mask.any():
                rejection_counter["tipo_escola_invalido"] += int(invalid_mask.sum())
                valid = valid.loc[~invalid_mask].copy()

    for column in NUMERIC_COLUMNS:
        if column in valid.columns:
            valid[column] = pd.to_numeric(valid[column], errors="coerce")

    for column in NOTE_COLUMNS:
        if column in valid.columns:
            invalid_mask = valid[column].isna() | (valid[column] < 0) | (valid[column] > 1000)
            if invalid_mask.any():
                rejection_counter[f"nota_fora_do_intervalo:{column}"] += int(invalid_mask.sum())
                valid = valid.loc[~invalid_mask].copy()

    for q in [f"Q{i:03d}" for i in range(1, 26)]:
        if q in valid.columns:
            values = valid[q].astype("string").str.strip().str.upper()
            invalid_mask = ~values.isin(list(VALID_SOCIO_CODES)) & ~values.isna()
            if invalid_mask.any():
                rejection_counter[f"codigo_socioeconomico_invalido:{q}"] += int(invalid_mask.sum())
                valid = valid.loc[~invalid_mask].copy()

    if not valid.empty:
        valid["NU_ANO"] = year
        valid["SG_UF_PROVA"] = valid["SG_UF_PROVA"].astype("string").str.strip().str.upper()
        for q in [f"Q{i:03d}" for i in range(1, 26)]:
            if q in valid.columns:
                valid[q] = valid[q].astype("string").str.strip().str.upper()

    return valid, rejection_counter


def normalize_chunk(chunk: pd.DataFrame, year: int) -> tuple[pd.DataFrame, Counter[str]]:
    missing = [column for column in REQUIRED_COLUMNS if column not in chunk.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes em {year}: {', '.join(missing)}")

    frame = chunk.reindex(columns=COMMON_COLUMNS).copy()
    frame["NU_ANO"] = year
    valid_frame, rejections = _row_rejections(frame, year)

    note_cols = [column for column in NOTE_COLUMNS if column in valid_frame.columns]
    if note_cols:
        valid_frame = valid_frame[valid_frame[note_cols].notna().any(axis=1)].copy()
    else:
        valid_frame = valid_frame.iloc[0:0].copy()

    if valid_frame.empty:
        rejections["sem_notas_validas"] += 1
    return valid_frame, rejections


def transform_year(
    zip_path: Path,
    year: int,
    parquet_root: Path,
    chunk_size: int = 250_000,
) -> dict:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Instale pyarrow para executar o ETL em Parquet.") from exc

    started = perf_counter()
    member = find_csv_member(zip_path)
    year_dir = parquet_root / f"ano={year}"
    year_dir.mkdir(parents=True, exist_ok=True)
    target = year_dir / "enem.parquet"

    writer = None
    rows_read = 0
    rows_valid = 0
    rows_rejected = 0
    quality_counter: Counter[str] = Counter()
    file_timestamp = datetime.now(UTC).isoformat()
    try:
        with zipfile.ZipFile(zip_path) as archive, archive.open(member) as raw:
            reader = pd.read_csv(
                raw,
                sep=";",
                encoding="latin-1",
                low_memory=False,
                chunksize=chunk_size,
            )
            for chunk in reader:
                rows_read += len(chunk)
                normalized, rejects = normalize_chunk(chunk, year)
                rows_valid += len(normalized)
                rows_rejected += len(chunk) - len(normalized)
                quality_counter.update(rejects)
                if normalized.empty:
                    continue
                table = pa.Table.from_pandas(normalized, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(target, table.schema, compression="zstd")
                writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()

    elapsed = perf_counter() - started
    quality = {
        "year": year,
        "schema_version": "2025-01",
        "processed_at": file_timestamp,
        "source_zip": str(zip_path),
        "csv_member": member,
        "records_read": rows_read,
        "records_valid": rows_valid,
        "records_rejected": rows_rejected,
        "rejections": dict(sorted(quality_counter.items())),
        "is_valid": rows_valid > 0,
    }
    report = {
        "year": year,
        "source_zip": str(zip_path),
        "csv_member": member,
        "output": str(target),
        "rows_read": rows_read,
        "rows_written": rows_valid,
        "rows_rejected": rows_rejected,
        "quality": quality,
        "elapsed_seconds": round(elapsed, 2),
    }
    (year_dir / "etl_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (year_dir / "quality_report.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report
