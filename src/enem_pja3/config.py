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
