from enem_pja3.config import DATA_DIR
from enem_pja3.transform.transform import conectar

SILVER = DATA_DIR / "silver"
GOLD = DATA_DIR / "gold"

# Os dois arquivos da gold ficam ordenados por ano e UF. Como o app quase sempre filtra por
# ano e estado, o DuckDB consegue pular os pedaços do arquivo que não interessam.

# Tipo de escola, escolaridade dos pais e renda mudaram de código entre os anos (conferido nos
# dicionários do INEP). Aqui elas ganham o mesmo nome e os mesmos valores nos 8 anos.
PERFIL_ANTIGO = """
    -- Tipo de escola (TP_ESCOLA)
    -- 2018: 2 = pública, 3 = exterior, 4 = privada | 2019 e 2020: 3 = privada, 4 = exterior
    -- 2021 a 2023: 2 = pública, 3 = privada | 1 = não respondeu (fica NULL)
    CASE
        WHEN TP_ESCOLA = 2 THEN 'publica'
        WHEN (ano = 2018 AND TP_ESCOLA = 4) OR (ano >= 2019 AND TP_ESCOLA = 3) THEN 'privada'
        WHEN (ano = 2018 AND TP_ESCOLA = 3) OR (ano IN (2019, 2020) AND TP_ESCOLA = 4) THEN 'exterior'
    END AS TIPO_ESCOLA,
    Q001 AS ESCOLARIDADE_PAI,   -- A a H, igual em todos os anos
    Q002 AS ESCOLARIDADE_MAE,
    Q006 AS RENDA_FAMILIAR,     -- A a Q, faixas em salários mínimos do ano
"""

PERFIL_NOVO = """
    -- Tipo de escola virou a pergunta Q023 do questionário
    CASE Q023
        WHEN 'A' THEN 'publica'
        WHEN 'B' THEN 'mista'
        WHEN 'C' THEN 'mista'
        WHEN 'D' THEN 'privada'
        WHEN 'E' THEN 'privada'
        WHEN 'F' THEN 'nao_frequentou'
    END AS TIPO_ESCOLA,
    Q001 AS ESCOLARIDADE_PAI,
    Q002 AS ESCOLARIDADE_MAE,
    Q007 AS RENDA_FAMILIAR,     -- a partir de 2024 a Q006 virou "Você possui renda?"
"""

NOTAS = """
    TP_PRESENCA_CN, TP_PRESENCA_CH, TP_PRESENCA_LC, TP_PRESENCA_MT,
    NU_NOTA_CN, NU_NOTA_CH, NU_NOTA_LC, NU_NOTA_MT, TP_LINGUA,
    NU_NOTA_REDACAO, TP_STATUS_REDACAO
"""


def ler_silver(tabela: str, colunas: str) -> str | None:
    """SELECT de uma tabela da silver, ou None se nenhum ano dela foi processado"""
    arquivos = [str(p) for p in sorted(SILVER.glob(f"{tabela}/*/dados.parquet"))]
    if not arquivos:
        return None
    return f"""
        SELECT CAST(ano AS USMALLINT) AS NU_ANO, SG_UF_PROVA, {colunas}
        FROM read_parquet({arquivos}, hive_partitioning = true, union_by_name = true)
    """


def gravar(destino, *selects):
    """Junta os SELECTs pelo nome das colunas, ordena por ano e UF e grava o Parquet"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    juntos = "\nUNION ALL BY NAME\n".join(s for s in selects if s)
    conectar().sql(f"""
        COPY (
            SELECT * FROM ({juntos})
            ORDER BY NU_ANO, SG_UF_PROVA
        ) TO '{destino}' (FORMAT parquet, COMPRESSION zstd)
    """)
    return destino


def carregar_notas():
    """Junta as notas dos 8 anos em um Parquet só (base para percentil e Z-Score).

    De 2018 a 2023 cada linha também traz tipo de escola, escolaridade dos pais e renda, porque
    perfil e nota estão no mesmo arquivo. Em 2024 e 2025 essas colunas ficam vazias: o INEP
    separou perfil e nota em arquivos sem ligação.
    """
    escola = "TP_DEPENDENCIA_ADM_ESC, TP_LOCALIZACAO_ESC,"
    return gravar(
        GOLD / "enem_notas.parquet",
        ler_silver("enem", escola + PERFIL_ANTIGO + NOTAS),
        ler_silver("resultados", escola + NOTAS),
    )


def carregar_perfil():
    """Junta o perfil e o questionário dos 8 anos em um Parquet só"""
    perfil = "TP_FAIXA_ETARIA, TP_SEXO, TP_COR_RACA, TP_ST_CONCLUSAO, IN_TREINEIRO,"
    questionario = "COLUMNS('^Q\\d{3}$')"
    return gravar(
        GOLD / "enem_perfil.parquet",
        ler_silver("enem", perfil + PERFIL_ANTIGO + questionario),
        ler_silver("participantes", perfil + PERFIL_NOVO + questionario),
    )


if __name__ == "__main__":
    carregar_notas()
    carregar_perfil()
