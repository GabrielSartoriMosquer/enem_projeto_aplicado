from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import requests

URL_TEMPLATE = "https://download.inep.gov.br/microdados/microdados_enem_{year}.zip"


def download_year(year: int, output_dir: Path, force: bool = False) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"microdados_enem_{year}.zip"
    if target.exists() and not force:
        return target

    url = URL_TEMPLATE.format(year=year)
    temp = target.with_suffix(".zip.part")
    with requests.get(url, stream=True, timeout=(15, 180)) as response:
        response.raise_for_status()
        with temp.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    shutil.move(temp, target)
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
