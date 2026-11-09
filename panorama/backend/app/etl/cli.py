from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.etl.download import download_year, sha256
from app.etl.transform import transform_year


def parse_years(value: str) -> list[int]:
    years = []
    for part in value.split(","):
        part = part.strip()
        if "-" in part:
            start, end = map(int, part.split("-", 1))
            years.extend(range(start, end + 1))
        elif part:
            years.append(int(part))
    years = sorted(set(years))
    if not years or any(year < 2018 or year > 2025 for year in years):
        raise argparse.ArgumentTypeError("Use edições entre 2018 e 2025.")
    return years


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline ETL do Panorama ENEM")
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="Baixa os ZIPs oficiais do INEP")
    download.add_argument("--years", type=parse_years, default=list(range(2018, 2026)))
    download.add_argument("--raw-dir", type=Path, default=Path("backend/data/raw"))
    download.add_argument("--force", action="store_true")

    build = sub.add_parser("build", help="Converte os microdados para Parquet padronizado")
    build.add_argument("--years", type=parse_years, default=list(range(2018, 2026)))
    build.add_argument("--raw-dir", type=Path, default=Path("backend/data/raw"))
    build.add_argument("--parquet-dir", type=Path, default=Path("backend/data/parquet"))
    build.add_argument("--chunk-size", type=int, default=250_000)

    all_cmd = sub.add_parser("all", help="Baixa e transforma")
    all_cmd.add_argument("--years", type=parse_years, default=list(range(2018, 2026)))
    all_cmd.add_argument("--raw-dir", type=Path, default=Path("backend/data/raw"))
    all_cmd.add_argument("--parquet-dir", type=Path, default=Path("backend/data/parquet"))
    all_cmd.add_argument("--chunk-size", type=int, default=250_000)

    args = parser.parse_args()

    if args.command == "download":
        for year in args.years:
            path = download_year(year, args.raw_dir, args.force)
            print(
                json.dumps(
                    {"year": year, "path": str(path), "sha256": sha256(path)}, ensure_ascii=False
                )
            )
        return

    if args.command in {"build", "all"}:
        for year in args.years:
            zip_path = args.raw_dir / f"microdados_enem_{year}.zip"
            if args.command == "all":
                zip_path = download_year(year, args.raw_dir)
            if not zip_path.exists():
                raise SystemExit(
                    f"Arquivo ausente: {zip_path}. Execute o comando download primeiro."
                )
            report = transform_year(zip_path, year, args.parquet_dir, args.chunk_size)
            print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
