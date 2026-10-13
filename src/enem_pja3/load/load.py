from enem_pja3.config import DATA_DIR
from enem_pja3.transform.transform import conectar

SILVER = DATA_DIR / "silver"
GOLD = DATA_DIR / "gold"

# Os dois arquivos da gold ficam ordenados por ano e UF. Como o app quase sempre filtra por
# ano e estado, o DuckDB consegue pular os pedaços do arquivo que não interessam.


def carregar_notas():
    """Junta as notas dos 8 anos em um Parquet só (base para percentil e Z-Score)"""
    destino = GOLD / "enem_notas.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    conectar().sql(f"""
        COPY (
            SELECT
                CAST(ano AS USMALLINT) AS NU_ANO,
                SG_UF_PROVA,
                TP_DEPENDENCIA_ADM_ESC, TP_LOCALIZACAO_ESC,
                TP_PRESENCA_CN, TP_PRESENCA_CH, TP_PRESENCA_LC, TP_PRESENCA_MT,
                NU_NOTA_CN, NU_NOTA_CH, NU_NOTA_LC, NU_NOTA_MT, TP_LINGUA,
                NU_NOTA_REDACAO, TP_STATUS_REDACAO
            FROM read_parquet(['{SILVER}/enem/*/dados.parquet', '{SILVER}/resultados/*/dados.parquet'],
                              hive_partitioning = true, union_by_name = true)
            ORDER BY NU_ANO, SG_UF_PROVA
        ) TO '{destino}' (FORMAT parquet, COMPRESSION zstd)
    """)


def carregar_perfil():
    """Junta o perfil e o questionário dos 8 anos em um Parquet só"""
    destino = GOLD / "enem_perfil.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    conectar().sql(f"""
        COPY (
            SELECT
                CAST(ano AS USMALLINT) AS NU_ANO,
                SG_UF_PROVA,
                TP_FAIXA_ETARIA, TP_SEXO, TP_COR_RACA, TP_ST_CONCLUSAO, IN_TREINEIRO,
                COLUMNS('^Q\\d{{3}}$')
            FROM read_parquet(['{SILVER}/enem/*/dados.parquet', '{SILVER}/participantes/*/dados.parquet'],
                              hive_partitioning = true, union_by_name = true)
            ORDER BY NU_ANO, SG_UF_PROVA
        ) TO '{destino}' (FORMAT parquet, COMPRESSION zstd)
    """)


if __name__ == "__main__":
    carregar_notas()
    carregar_perfil()
