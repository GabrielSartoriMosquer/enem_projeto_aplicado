import os
from pathlib import Path

LINK_DOWNLOAD = "https://download.inep.gov.br/microdados/microdados_enem_{ano}.zip"
ANOS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025] # Trabalharemos com 8 anos

# Até 2023 o INEP publicava um CSV só. De 2024 em diante são dois: PARTICIPANTES e RESULTADOS
ANOS_FORMATO_ANTIGO = [2018, 2019, 2020, 2021, 2022, 2023]

# No container é /data (docker-compose), rodando local é ./data
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

# Limite de memória do DuckDB. Sem ele o load usou mais de 20 GB e o processo foi morto
MEMORIA_DUCKDB = "4GB"

# Data lake no Azure (ADLS Gen2). Sem nenhuma das duas variáveis o pipeline usa só a pasta local.
# Com AZURE_STORAGE_ACCOUNT o login é o do `az login` (ou a identidade gerenciada, rodando no Azure).
# A connection string serve para o container local, que não tem o az CLI.
LAKE_CONTA = os.environ.get("AZURE_STORAGE_ACCOUNT") or None
LAKE_CONEXAO = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or None
