"""Data lake no Azure (ADLS Gen2) com as camadas bronze, silver e gold.

Cada camada é um container do lake e o caminho dentro dele é o mesmo da pasta local:
data/silver/enem/ano=2018/dados.parquet fica em silver/enem/ano=2018/dados.parquet.

O processamento continua no disco local (o unzip precisa do zip inteiro e o DuckDB grava em disco
o que não cabe na memória). O lake guarda o resultado de cada camada e é de onde o pipeline puxa
o que não tem local. Para saber se um arquivo mudou comparamos o MD5, que gravamos no upload.

Sem AZURE_STORAGE_ACCOUNT nem AZURE_STORAGE_CONNECTION_STRING as funções não fazem nada.
"""
import hashlib
from functools import cache
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import ContentSettings, DataLakeFileClient, DataLakeServiceClient

from enem_pja3.config import DATA_DIR, LAKE_CONEXAO, LAKE_CONTA

TAMANHO_PEDACO = 8 * 1024 * 1024


def ativo() -> bool:
    return bool(LAKE_CONTA or LAKE_CONEXAO)


@cache
def _servico() -> DataLakeServiceClient:
    if LAKE_CONEXAO:
        return DataLakeServiceClient.from_connection_string(LAKE_CONEXAO)
    return DataLakeServiceClient(f"https://{LAKE_CONTA}.dfs.core.windows.net", credential=DefaultAzureCredential())


def _camada_e_caminho(caminho: Path) -> tuple[str, str]:
    """data/silver/enem/ano=2018 -> ('silver', 'enem/ano=2018')"""
    camada, *resto = caminho.relative_to(DATA_DIR).parts
    return camada, "/".join(resto)


def _arquivo(caminho: Path) -> DataLakeFileClient:
    return _servico().get_file_client(*_camada_e_caminho(caminho))


def _md5(caminho: Path) -> bytes:
    with open(caminho, "rb") as f:
        return hashlib.file_digest(f, "md5").digest()


def _md5_no_lake(arquivo: DataLakeFileClient) -> bytearray | None:
    """MD5 do arquivo no lake, ou None se ele não existe lá"""
    try:
        return arquivo.get_file_properties().content_settings.content_md5
    except ResourceNotFoundError:
        return None


def enviar(caminho: Path) -> None:
    """Envia o arquivo para o lake, a não ser que lá já esteja o mesmo conteúdo"""
    if not ativo():
        return
    arquivo = _arquivo(caminho)
    md5 = _md5(caminho)
    if _md5_no_lake(arquivo) == md5:
        return
    print(f"[lake] enviando {caminho}")
    # O padrão do SDK é mandar pedaços de 100 MB em várias conexões ao mesmo tempo. Numa internet
    # de casa (testamos com ~6 Mbit/s de upload) as conexões disputam a banda e alguma passa dos
    # 20 s sem conseguir escrever, que é o tempo limite. Um pedaço pequeno por vez não dá esse erro.
    with open(caminho, "rb") as f:
        arquivo.upload_data(f, overwrite=True, max_concurrency=1, chunk_size=TAMANHO_PEDACO,
                            content_settings=ContentSettings(content_md5=bytearray(md5)))


def baixar(caminho: Path) -> bool:
    """Traz o arquivo do lake se ele não existe local ou está diferente. False se não está no lake"""
    if not ativo():
        return False
    arquivo = _arquivo(caminho)
    if not arquivo.exists():
        return False
    if caminho.exists() and _md5_no_lake(arquivo) == _md5(caminho):
        return True

    print(f"[lake] baixando {caminho}")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Baixa com outro nome e só renomeia no final, igual ao download do INEP
    temporario = caminho.with_name(caminho.name + ".part")
    with open(temporario, "wb") as f:
        arquivo.download_file(max_concurrency=4).readinto(f)
    temporario.replace(caminho)
    return True


def sincronizar(pasta: Path) -> None:
    """Deixa a pasta local e a do lake com os mesmos arquivos.

    Arquivo que só está no lake é baixado e arquivo que só está local é enviado. Se está nos dois
    com conteúdo diferente, vale o do lake: o que foi processado nesta execução já foi enviado
    antes, então a diferença é uma cópia local antiga.
    """
    if not ativo():
        return
    camada, prefixo = _camada_e_caminho(pasta)
    try:
        caminhos = _servico().get_file_system_client(camada).get_paths(path=prefixo or None, recursive=True)
        no_lake = {p.name for p in caminhos if not p.is_directory}
    except ResourceNotFoundError:
        no_lake = set()  # a pasta ainda não existe no lake

    for nome in sorted(no_lake):
        baixar(DATA_DIR / camada / nome)
    for local in sorted(pasta.rglob("*")):
        if local.is_file() and _camada_e_caminho(local)[1] not in no_lake:
            enviar(local)
