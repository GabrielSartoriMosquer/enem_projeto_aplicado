import os
from pathlib import Path

import duckdb

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

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


def transformar_microdados(ano: int) -> Path:
    """Lê o CSV bruto de um ano (formato antigo) e grava o Parquet da silver."""
    csv = DATA_DIR / "bronze" / "csv" / f"ano={ano}" / f"MICRODADOS_ENEM_{ano}.csv"
    destino = DATA_DIR / "silver" / "enem" / f"ano={ano}" / "dados.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)

    duckdb.sql(f"""
        COPY (
            {SELECT_MICRODADOS}
            FROM read_csv('{csv}', delim=';', encoding='latin-1', all_varchar=true)
        ) TO '{destino}' (FORMAT parquet, COMPRESSION zstd)
    """)
    return destino


if __name__ == "__main__":
    print(transformar_microdados(2023))
