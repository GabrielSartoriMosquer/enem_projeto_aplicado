import requests # Para baixar os arquivos .zip dos microdados
import truststore # Para contornar a quebra de código por credencial
from tqdm import tqdm # Barra de progesso dos downloads
from requests.adapters import HTTPAdapter 
from urllib3.util.retry import Retry # Para re-tentar o GET caso sejam disparados códigos de erro específicos
from config.yaml import RAIZ_PROJETO, ANOS, LINK_DOWNLOAD

truststore.inject_into_ssl()

retry = Retry(
    total=5,                          # até 5 tentativas
    backoff_factor=2,                 # 2s, 4s, 8s, 16s... entre tentativas
    status_forcelist=[500, 502, 503, 504],  # também re-tenta esses status HTTP
)
sessao = requests.Session()
sessao.mount("https://", HTTPAdapter(max_retries=retry))

PASTA_DESTINO = RAIZ_PROJETO / 'data' / 'bronze' / 'zips'
PASTA_DESTINO.mkdir(parents=True, exist_ok=True)


response = sessao.get(LINK_DOWNLOAD.replace('ANO', str(ano)), stream=True, timeout=30)    
total = int(response.headers.get('content-length', 0))
caminho = PASTA_DESTINO / f"md_{ano}.zip"
with open(caminho, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True, desc=f"md_{ano}") as barra:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
        barra.update(len(chunk))