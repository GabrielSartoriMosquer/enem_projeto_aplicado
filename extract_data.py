import requests 

ANOS = [n for n in range(2018, 2026)]
LINK_DOWNLOAD = 'https://download.inep.gov.br/microdados/microdados_enem_ANO.zip'
for ano in ANOS:
    requests.get(LINK_DOWNLOAD.replace('ANO', str(ano)), stream=True, )