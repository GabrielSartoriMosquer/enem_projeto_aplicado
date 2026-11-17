"""Camada gold vinda do data lake no Azure (ADLS Gen2).

O ETL (src/enem_pja3/lake.py, na raiz do repositório) envia a gold para o container ``gold`` do
lake. Aqui a API baixa ``enem_notas.parquet`` de lá para um cache local ao subir e consulta essa
cópia com o DuckDB: ler o Parquet direto do lake a cada consulta deixaria tudo dependente da rede.

O download só acontece quando o arquivo do lake muda (comparamos o MD5 que o ETL grava no upload).
Sem AZURE_STORAGE_ACCOUNT nem AZURE_STORAGE_CONNECTION_STRING o lake não é usado.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)
# O SDK do Azure registra cada requisição HTTP em INFO; só interessam avisos e erros.
logging.getLogger("azure").setLevel(logging.WARNING)


def lake_enabled(settings: Settings) -> bool:
    return bool(settings.lake_account or settings.lake_connection_string)


def _file_client(settings: Settings):
    # Import tardio: quem não usa o lake não precisa do SDK do Azure.
    from azure.storage.filedatalake import DataLakeServiceClient

    if settings.lake_connection_string:
        service = DataLakeServiceClient.from_connection_string(settings.lake_connection_string)
    else:
        from azure.identity import DefaultAzureCredential

        service = DataLakeServiceClient(
            f"https://{settings.lake_account}.dfs.core.windows.net",
            credential=DefaultAzureCredential(),
        )
    return service.get_file_client(settings.lake_gold_container, settings.lake_gold_file)


def _md5(path: Path) -> bytes:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "md5").digest()


def sync_gold(settings: Settings) -> Path:
    """Garante no cache local a mesma gold que está no lake e devolve o caminho dela."""
    target = Path(settings.lake_cache_path)
    remote = _file_client(settings)
    remote_md5 = remote.get_file_properties().content_settings.content_md5
    location = f"{settings.lake_gold_container}/{settings.lake_gold_file}"

    if target.is_file() and remote_md5 and bytes(remote_md5) == _md5(target):
        logger.info("Gold do lake já está no cache: %s", target)
        return target

    logger.info("Baixando a gold do lake (%s) para %s", location, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    with open(partial, "wb") as handle:
        remote.download_file(max_concurrency=4).readinto(handle)
    partial.replace(target)
    return target
