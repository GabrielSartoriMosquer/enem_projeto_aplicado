import os
from pathlib import Path

os.environ["PANORAMA_DATA_MODE"] = "demo"
os.environ["PANORAMA_DEMO_CSV"] = str(
    Path(__file__).resolve().parents[1] / "data" / "demo" / "enem_demo.csv"
)
# Isola os testes de um .env local que aponte para a gold ou para Parquets reais.
os.environ["PANORAMA_GOLD_PATH"] = str(Path(__file__).resolve().parent / "_sem_gold.parquet")
os.environ["PANORAMA_PARQUET_GLOB"] = str(
    Path(__file__).resolve().parent / "_sem_parquet" / "ano=*" / "enem.parquet"
)
