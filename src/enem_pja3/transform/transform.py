from pathlib import Path

import duckdb

from enem_pja3.config import ANOS, ANOS_FORMATO_ANTIGO, DATA_DIR, MEMORIA_DUCKDB

# Contrato de dados da silver (formato antigo: 2018–2023)
SELECT_MICRODADOS = """
SELECT
    -- Perfil
    CAST(TP_FAIXA_ETARIA AS UTINYINT)        AS TP_FAIXA_ETARIA,
    TP_SEXO,
    CAST(TP_COR_RACA AS UTINYINT)            AS TP_COR_RACA,
    CAST(TP_ST_CONCLUSAO AS UTINYINT)        AS TP_ST_CONCLUSAO,
    CAST(TP_ESCOLA AS UTINYINT)              AS TP_ESCOLA,
    IN_TREINEIRO = '1'                       AS IN_TREINEIRO,

    -- Escola
    CAST(TP_DEPENDENCIA_ADM_ESC AS UTINYINT) AS TP_DEPENDENCIA_ADM_ESC,
    CAST(TP_LOCALIZACAO_ESC AS UTINYINT)     AS TP_LOCALIZACAO_ESC,

    -- Local da prova
    SG_UF_PROVA,

    -- Presença (0 = faltou, 1 = presente, 2 = eliminado)
    CAST(TP_PRESENCA_CN AS UTINYINT)         AS TP_PRESENCA_CN,
    CAST(TP_PRESENCA_CH AS UTINYINT)         AS TP_PRESENCA_CH,
    CAST(TP_PRESENCA_LC AS UTINYINT)         AS TP_PRESENCA_LC,
    CAST(TP_PRESENCA_MT AS UTINYINT)         AS TP_PRESENCA_MT,

    -- Notas
    CAST(NU_NOTA_CN AS DECIMAL(5,1))         AS NU_NOTA_CN,
    CAST(NU_NOTA_CH AS DECIMAL(5,1))         AS NU_NOTA_CH,
    CAST(NU_NOTA_LC AS DECIMAL(5,1))         AS NU_NOTA_LC,
    CAST(NU_NOTA_MT AS DECIMAL(5,1))         AS NU_NOTA_MT,
    CAST(TP_LINGUA AS UTINYINT)              AS TP_LINGUA,  -- 0 = inglês, 1 = espanhol

    -- Redação
    CAST(NU_NOTA_REDACAO AS SMALLINT)        AS NU_NOTA_REDACAO,
    CAST(TP_STATUS_REDACAO AS UTINYINT)      AS TP_STATUS_REDACAO,

    -- Questionário (todas as colunas Q001, Q002, ... de uma vez)
    COLUMNS('^Q\\d{3}$')
"""

# Formato novo (2024 em diante): o INEP separou o perfil e as notas em dois arquivos,
# e não tem nenhuma coluna que ligue um ao outro. Por isso viram duas tabelas na silver.
SELECT_PARTICIPANTES = """
SELECT
    -- Perfil (não tem mais TP_ESCOLA)
    CAST(TP_FAIXA_ETARIA AS UTINYINT)        AS TP_FAIXA_ETARIA,
    TP_SEXO,
    CAST(TP_COR_RACA AS UTINYINT)            AS TP_COR_RACA,
    CAST(TP_ST_CONCLUSAO AS UTINYINT)        AS TP_ST_CONCLUSAO,
    IN_TREINEIRO = '1'                       AS IN_TREINEIRO,

    -- Local da prova
    SG_UF_PROVA,

    -- Questionário
    COLUMNS('^Q\\d{3}$')
"""

SELECT_RESULTADOS = """
SELECT
    -- Escola
    CAST(TP_DEPENDENCIA_ADM_ESC AS UTINYINT) AS TP_DEPENDENCIA_ADM_ESC,
    CAST(TP_LOCALIZACAO_ESC AS UTINYINT)     AS TP_LOCALIZACAO_ESC,

    -- Local da prova
    SG_UF_PROVA,

    -- Presença
    CAST(TP_PRESENCA_CN AS UTINYINT)         AS TP_PRESENCA_CN,
    CAST(TP_PRESENCA_CH AS UTINYINT)         AS TP_PRESENCA_CH,
    CAST(TP_PRESENCA_LC AS UTINYINT)         AS TP_PRESENCA_LC,
    CAST(TP_PRESENCA_MT AS UTINYINT)         AS TP_PRESENCA_MT,

    -- Notas
    CAST(NU_NOTA_CN AS DECIMAL(5,1))         AS NU_NOTA_CN,
    CAST(NU_NOTA_CH AS DECIMAL(5,1))         AS NU_NOTA_CH,
    CAST(NU_NOTA_LC AS DECIMAL(5,1))         AS NU_NOTA_LC,
    CAST(NU_NOTA_MT AS DECIMAL(5,1))         AS NU_NOTA_MT,
    CAST(TP_LINGUA AS UTINYINT)              AS TP_LINGUA,

    -- Redação
    CAST(NU_NOTA_REDACAO AS SMALLINT)        AS NU_NOTA_REDACAO,
    CAST(TP_STATUS_REDACAO AS UTINYINT)      AS TP_STATUS_REDACAO
"""


def conectar() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql(f"SET memory_limit = '{MEMORIA_DUCKDB}'")
    con.sql(f"SET temp_directory = '{DATA_DIR / 'duckdb_tmp'}'")  # o que não couber na memória vai pro disco
    con.sql("SET preserve_insertion_order = false")  # economiza memória, a ordem das linhas não importa
    con.sql("SET enable_progress_bar = false")
    return con


def ler_csv(csv: Path, all_varchar: bool = True) -> str:
    # parallel=false: lendo em paralelo com encoding latin-1, o DuckDB às vezes juntava pedaços de
    # duas linhas e dava erro de número de colunas (cada vez numa linha diferente). Em série não acontece.
    return f"read_csv('{csv}', delim=';', encoding='latin-1', all_varchar={all_varchar}, parallel=false)"


def csv_para_parquet(select: str, csv: Path, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    conectar().sql(f"""
        COPY (
            {select}
            FROM {ler_csv(csv)}
        ) TO '{destino}' (FORMAT parquet, COMPRESSION zstd)
    """)
    return destino


def transformar(ano: int) -> None:
    """Lê os CSVs brutos de um ano e grava os Parquets da silver."""
    pasta_csv = DATA_DIR / "bronze" / "csv" / f"ano={ano}"
    silver = DATA_DIR / "silver"

    if ano in ANOS_FORMATO_ANTIGO:
        csv_para_parquet(SELECT_MICRODADOS, pasta_csv / f"MICRODADOS_ENEM_{ano}.csv",
                         silver / "enem" / f"ano={ano}" / "dados.parquet")
    else:
        csv_para_parquet(SELECT_PARTICIPANTES, pasta_csv / f"PARTICIPANTES_{ano}.csv",
                         silver / "participantes" / f"ano={ano}" / "dados.parquet")
        csv_para_parquet(SELECT_RESULTADOS, pasta_csv / f"RESULTADOS_{ano}.csv",
                         silver / "resultados" / f"ano={ano}" / "dados.parquet")


if __name__ == "__main__":
    for ano in ANOS:
        transformar(ano)
