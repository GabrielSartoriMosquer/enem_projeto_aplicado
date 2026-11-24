"""Resumo do perfil dos inscritos: contagens por ano, UF, indicador e categoria.

O enem_perfil.parquet tem uma linha por inscrito (36 milhões nos 8 anos) e quase 300 MB. Para a
área "Quem faz o ENEM" do app não precisamos das linhas, só de quantas pessoas caem em cada
resposta. Este arquivo guarda essas contagens já harmonizadas entre os anos e fica com poucos MB,
então a API consegue carregar tudo na memória.

Formato longo, uma linha por contagem:
    NU_ANO, SG_UF_PROVA, INDICADOR, CATEGORIA, RECORTE, RECORTE_CATEGORIA, N
- RECORTE nulo: quantos inscritos da UF deram aquela resposta.
- RECORTE preenchido (renda, cor_raca, sexo, tipo_escola): cruzamento nacional (UF nula), por
  exemplo quantos inscritos sem computador há em cada faixa de renda.
Quem não respondeu a pergunta (ou a pergunta não existia no ano) fica fora da contagem, então o
total de cada indicador é o de quem respondeu.

O questionário mudou de numeração em 2024 (conferido nos dicionários do INEP de 2018 a 2025):
até 2023 a internet era a Q025, de 2024 em diante é a Q020, e assim por diante. Cada indicador
abaixo diz de qual pergunta vem em cada época.
"""
from enem_pja3.load import load
from enem_pja3.transform.transform import conectar

# Todas as perguntas que algum indicador usa. Se faltar alguma no arquivo (o questionário de um ano
# não tem a pergunta, ou é um arquivo de teste), ela entra como vazia.
PERGUNTAS = [f"Q{i:03d}" for i in range(1, 28)]


def epoca(antiga: str, nova: str) -> str:
    """Pergunta de 2018–2023 ou de 2024 em diante"""
    return f"(CASE WHEN NU_ANO <= 2023 THEN {antiga} ELSE {nova} END)"


def sim_nao(coluna: str) -> str:
    # Nas perguntas de bens, A = "Não" e qualquer outra letra = tem (um, dois, ...)
    return f"(CASE WHEN {coluna} IS NULL THEN NULL WHEN {coluna} = 'A' THEN 'nao' ELSE 'sim' END)"


def quantidade(coluna: str, ate: int) -> str:
    """A = nenhum, B = um, C = dois... agrupando a partir de `ate` em "<ate>_mais" """
    nomes = ["nenhum", "um", "dois", "tres"]
    casos = " ".join(f"WHEN '{'ABCD'[i]}' THEN '{nomes[i]}'" for i in range(ate))
    # `WHEN NULL` nunca casa no CASE simples: sem o teste explícito, quem não respondeu cairia no ELSE
    return f"(CASE WHEN {coluna} IS NULL THEN NULL ELSE CASE {coluna} {casos} ELSE '{nomes[ate]}_mais' END END)"


REGIOES = {
    "norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "centro_oeste": ["DF", "GO", "MT", "MS"],
    "sudeste": ["ES", "MG", "RJ", "SP"],
    "sul": ["PR", "RS", "SC"],
}
REGIAO = "(CASE " + " ".join(
    f"WHEN SG_UF_PROVA IN ({', '.join(repr(uf) for uf in ufs)}) THEN '{nome}'" for nome, ufs in REGIOES.items()
) + " END)"

# Renda familiar em salários mínimos do ano (as letras são as mesmas faixas em todos os anos:
# B = até 1 SM, C = até 1,5, D = até 2, E = até 2,5, F = até 3, G = até 4, H = até 5,
# I a M = até 6, 7, 8, 9 e 10, N = até 12, O = até 15, P = até 20, Q = mais de 20)
RENDA = """(CASE
    WHEN RENDA_FAMILIAR = 'A' THEN 'nenhuma'
    WHEN RENDA_FAMILIAR = 'B' THEN 'ate_1'
    WHEN RENDA_FAMILIAR IN ('C', 'D') THEN '1_2'
    WHEN RENDA_FAMILIAR IN ('E', 'F') THEN '2_3'
    WHEN RENDA_FAMILIAR IN ('G', 'H') THEN '3_5'
    WHEN RENDA_FAMILIAR IN ('I', 'J', 'K', 'L', 'M') THEN '5_10'
    WHEN RENDA_FAMILIAR IN ('N', 'O', 'P') THEN '10_20'
    WHEN RENDA_FAMILIAR = 'Q' THEN 'mais_20'
END)"""

ESCOLARIDADE = """(CASE {col}
    WHEN 'A' THEN 'nunca_estudou' WHEN 'B' THEN 'fund1_incompleto' WHEN 'C' THEN 'fund1'
    WHEN 'D' THEN 'fundamental' WHEN 'E' THEN 'medio' WHEN 'F' THEN 'superior'
    WHEN 'G' THEN 'pos' WHEN 'H' THEN 'nao_sabe'
END)"""

OCUPACAO = """(CASE {col}
    WHEN 'A' THEN 'grupo1' WHEN 'B' THEN 'grupo2' WHEN 'C' THEN 'grupo3'
    WHEN 'D' THEN 'grupo4' WHEN 'E' THEN 'grupo5' WHEN 'F' THEN 'nao_sabe'
END)"""

# id do indicador -> expressão SQL que dá a categoria de cada inscrito (NULL = não respondeu)
INDICADORES = {
    # Quem são
    "sexo": "(CASE TP_SEXO WHEN 'F' THEN 'feminino' WHEN 'M' THEN 'masculino' END)",
    # 0 = não declarado e 6 = não dispõe da informação
    "cor_raca": """(CASE TP_COR_RACA WHEN 1 THEN 'branca' WHEN 2 THEN 'preta' WHEN 3 THEN 'parda'
        WHEN 4 THEN 'amarela' WHEN 5 THEN 'indigena' WHEN 0 THEN 'nao_declarado' WHEN 6 THEN 'nao_declarado' END)""",
    # 1 = menor de 17, 2 = 17 anos, 3 = 18, ..., 10 = 25, 11 = 26 a 30, 12 = 31 a 35, 13 = 36 a 40, 14+ = 41 ou mais
    "faixa_etaria": """(CASE WHEN TP_FAIXA_ETARIA <= 2 THEN 'ate_17' WHEN TP_FAIXA_ETARIA = 3 THEN '18'
        WHEN TP_FAIXA_ETARIA <= 5 THEN '19_20' WHEN TP_FAIXA_ETARIA <= 10 THEN '21_25'
        WHEN TP_FAIXA_ETARIA = 11 THEN '26_30' WHEN TP_FAIXA_ETARIA <= 13 THEN '31_40'
        WHEN TP_FAIXA_ETARIA >= 14 THEN '41_mais' END)""",
    "situacao_em": """(CASE TP_ST_CONCLUSAO WHEN 1 THEN 'concluido' WHEN 2 THEN 'concluindo'
        WHEN 3 THEN 'depois' WHEN 4 THEN 'nao_cursando' END)""",
    "treineiro": "(CASE WHEN IN_TREINEIRO THEN 'sim' WHEN NOT IN_TREINEIRO THEN 'nao' END)",
    "regiao": REGIAO,
    # Renda e família
    "renda_familiar": RENDA,
    "escolaridade_mae": ESCOLARIDADE.format(col="ESCOLARIDADE_MAE"),
    "escolaridade_pai": ESCOLARIDADE.format(col="ESCOLARIDADE_PAI"),
    "ocupacao_mae": OCUPACAO.format(col="Q004"),
    "ocupacao_pai": OCUPACAO.format(col="Q003"),
    "pessoas_casa": """(CASE WHEN TRY_CAST(Q005 AS INTEGER) >= 6 THEN '6_mais'
        ELSE CAST(TRY_CAST(Q005 AS INTEGER) AS VARCHAR) END)""",
    # Só existe de 2024 em diante (Q006 = "Você possui renda?")
    "renda_propria": f"(CASE WHEN NU_ANO >= 2024 THEN {sim_nao('Q006')} END)",
    # Conectividade (2024+: a pergunta passou a ser "internet por rede wi-fi")
    "internet": sim_nao(epoca("Q025", "Q020")),
    "computador": quantidade(epoca("Q024", "Q021"), 2),
    "celular": quantidade("Q022", 3),
    "tv_assinatura": sim_nao(epoca("Q021", "Q019")),
    # Moradia e bens
    "carro": quantidade(epoca("Q010", "Q011"), 2),
    "moto": sim_nao(epoca("Q011", "Q012")),
    "banheiros": quantidade(epoca("Q008", "Q009"), 3),
    "quartos": quantidade(epoca("Q009", "Q010"), 3),
    "empregada": """(CASE {col} WHEN 'A' THEN 'nao' WHEN 'B' THEN '1_2_dias'
        WHEN 'C' THEN '3_4_dias' WHEN 'D' THEN '5_dias' END)""".format(col=epoca("Q007", "Q008")),
    "maquina_lavar": sim_nao(epoca("Q014", "Q015")),
    "micro_ondas": sim_nao("Q016"),
    "geladeira": sim_nao(epoca("Q012", "Q013")),
    # Escola (até 2023 só uma parte dos inscritos informava o tipo de escola)
    "tipo_escola": "TIPO_ESCOLA",
}

# Recortes dos cruzamentos nacionais (colunas calculadas uma vez por inscrito)
RECORTES = {
    "renda": """(CASE
        WHEN RENDA_FAMILIAR IN ('A', 'B') THEN 'ate_1'
        WHEN RENDA_FAMILIAR IN ('C', 'D', 'E', 'F') THEN '1_3'
        WHEN RENDA_FAMILIAR IN ('G', 'H') THEN '3_5'
        WHEN RENDA_FAMILIAR IN ('I', 'J', 'K', 'L', 'M') THEN '5_10'
        WHEN RENDA_FAMILIAR IN ('N', 'O', 'P', 'Q') THEN 'mais_10'
    END)""",
    "cor_raca": INDICADORES["cor_raca"],
    "sexo": INDICADORES["sexo"],
    "tipo_escola": "(CASE WHEN TIPO_ESCOLA IN ('publica', 'privada') THEN TIPO_ESCOLA END)",
}


def consulta_indicador(indicador: str, expressao: str, origem: str) -> str:
    """Contagem por UF e os cruzamentos nacionais de um indicador, numa passada pelo arquivo"""
    recortes = ", ".join(f"{sql} AS r_{nome}" for nome, sql in RECORTES.items())
    conjuntos = ", ".join(["(NU_ANO, SG_UF_PROVA, categoria)"] + [f"(NU_ANO, categoria, r_{nome})" for nome in RECORTES])
    qual_recorte = " ".join(f"WHEN GROUPING(r_{nome}) = 0 THEN '{nome}'" for nome in RECORTES)
    valor_recorte = ", ".join(f"r_{nome}" for nome in RECORTES)
    return f"""
        SELECT NU_ANO, SG_UF_PROVA, '{indicador}' AS INDICADOR, categoria AS CATEGORIA,
               CASE {qual_recorte} END AS RECORTE,
               COALESCE({valor_recorte}) AS RECORTE_CATEGORIA,
               count(*) AS N
        FROM (SELECT NU_ANO, SG_UF_PROVA, {expressao} AS categoria, {recortes} FROM {origem})
        WHERE categoria IS NOT NULL
        GROUP BY GROUPING SETS ({conjuntos})
    """


def carregar_resumo_perfil():
    """Gera gold/enem_perfil_resumo.parquet a partir de gold/enem_perfil.parquet"""
    perfil, resumo = load.GOLD / "enem_perfil.parquet", load.GOLD / "enem_perfil_resumo.parquet"
    con = conectar()
    colunas = {linha[0] for linha in con.sql(f"DESCRIBE SELECT * FROM '{perfil}'").fetchall()}
    faltando = "".join(f", NULL::VARCHAR AS {q}" for q in PERGUNTAS if q not in colunas)
    origem = f"(SELECT *{faltando} FROM read_parquet('{perfil}'))"
    partes = "\nUNION ALL\n".join(consulta_indicador(nome, sql, origem) for nome, sql in INDICADORES.items())
    con.sql(f"""
        COPY (
            SELECT CAST(NU_ANO AS USMALLINT) AS NU_ANO, SG_UF_PROVA, INDICADOR, CATEGORIA, RECORTE,
                   RECORTE_CATEGORIA, CAST(N AS UINTEGER) AS N
            FROM ({partes})
            -- No cruzamento, quem não respondeu a pergunta do recorte (ex.: renda) fica de fora
            WHERE RECORTE IS NULL OR RECORTE_CATEGORIA IS NOT NULL
            ORDER BY NU_ANO, INDICADOR, RECORTE NULLS FIRST, SG_UF_PROVA, CATEGORIA
        ) TO '{resumo}' (FORMAT parquet, COMPRESSION zstd)
    """)
    return resumo


if __name__ == "__main__":
    print(carregar_resumo_perfil())
