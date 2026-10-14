from pathlib import Path

import certifi
import requests # Para baixar os arquivos .zip dos microdados
from tqdm import tqdm # Barra de progesso dos downloads
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry # Para re-tentar o GET caso sejam disparados códigos de erro específicos

from enem_pja3.config import ANOS, DATA_DIR, LINK_DOWNLOAD

PASTA_DESTINO = DATA_DIR / 'bronze' / 'zips'

# O site do INEP não envia o certificado intermediário, então o requests não consegue validar o HTTPS.
# Deixamos esse certificado (da RNP) salvo no projeto e juntamos com os certificados do certifi.
CERTIFICADO_INEP = Path(__file__).parent.parent / 'certs' / 'rnp_icpedu_gr46_ov_tls_ca_2025.pem'


def criar_sessao() -> requests.Session:
    retry = Retry(
        total=5,                          # até 5 tentativas
        backoff_factor=2,                 # 2s, 4s, 8s, 16s... entre tentativas
        status_forcelist=[500, 502, 503, 504],  # também re-tenta esses status HTTP
    )
    sessao = requests.Session()
    sessao.mount("https://", HTTPAdapter(max_retries=retry))

    certificados = DATA_DIR / 'certificados.pem'
    certificados.parent.mkdir(parents=True, exist_ok=True)
    certificados.write_text(Path(certifi.where()).read_text() + CERTIFICADO_INEP.read_text())
    sessao.verify = str(certificados)
    return sessao


def baixar_zip(ano: int, sessao: requests.Session) -> Path:
    """Baixa o zip dos microdados de um ano para bronze/zips/"""
    PASTA_DESTINO.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_DESTINO / f"microdados_enem_{ano}.zip"
    if caminho.exists():
        print(f"[pulado] {caminho} já existe")
        return caminho

    # Baixa com outro nome e só renomeia no final, assim um download pela metade não vira um .zip
    temporario = PASTA_DESTINO / f"microdados_enem_{ano}.zip.part"
    response = sessao.get(LINK_DOWNLOAD.format(ano=ano), stream=True, timeout=30)
    response.raise_for_status()
    total = int(response.headers.get('content-length', 0))
    with open(temporario, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True, desc=f"md_{ano}") as barra:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            barra.update(len(chunk))

    temporario.rename(caminho)
    return caminho


if __name__ == "__main__":
    sessao = criar_sessao()
    for ano in ANOS:
        baixar_zip(ano, sessao)
