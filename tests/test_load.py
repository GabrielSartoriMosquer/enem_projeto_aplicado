import duckdb

from conftest import COLUNAS_ANTIGO, COLUNAS_PARTICIPANTES, COLUNAS_RESULTADOS, escrever_csv
from enem_pja3.load.load import carregar_notas, carregar_perfil
from enem_pja3.load.resumo import carregar_resumo_perfil
from enem_pja3.transform.transform import transformar


def linha_antiga(ano, uf, tp_escola, renda):
    return ["1", str(ano), "3", "F", "1", "1", str(tp_escola), "0", "", "", "", uf,
            "1", "1", "1", "1", "500.0", "500.0", "500.0", "600.0", "0", "800", "1", "E", "F", renda]


def preparar_silver(dados):
    # 2018: 4 = privada e 3 = exterior | 2019: 3 = privada
    escrever_csv(dados / "bronze/csv/ano=2018/MICRODADOS_ENEM_2018.csv", COLUNAS_ANTIGO, [
        linha_antiga(2018, "SC", 4, "Q"),
        linha_antiga(2018, "SP", 3, "B"),
        linha_antiga(2018, "RJ", 1, "A"),
    ])
    escrever_csv(dados / "bronze/csv/ano=2019/MICRODADOS_ENEM_2019.csv", COLUNAS_ANTIGO, [
        linha_antiga(2019, "SC", 3, "D"),
    ])
    # 2024: Q006 = "Você possui renda?" e Q007 = renda da família | Q023 = tipo de escola
    escrever_csv(dados / "bronze/csv/ano=2024/PARTICIPANTES_2024.csv", COLUNAS_PARTICIPANTES, [
        ["1", "2024", "3", "F", "1", "1", "0", "RS", "E", "F", "B", "C", "B"],
    ])
    escrever_csv(dados / "bronze/csv/ano=2024/RESULTADOS_2024.csv", COLUNAS_RESULTADOS, [
        ["1", "2024", "2", "1", "RS", "1", "1", "1", "1", "500.0", "510.0", "520.0", "530.0", "0", "900", "1"],
    ])
    for ano in (2018, 2019, 2024):
        transformar(ano)


def consultar(arquivo, sql):
    return duckdb.sql(sql.replace("ARQUIVO", f"'{arquivo}'")).fetchall()


def test_tipo_de_escola_harmonizado(dados):
    preparar_silver(dados)
    carregar_perfil()
    perfil = dados / "gold/enem_perfil.parquet"

    resultado = consultar(perfil, "SELECT NU_ANO, SG_UF_PROVA, TIPO_ESCOLA FROM ARQUIVO ORDER BY 1, 2")
    assert resultado == [
        (2018, "RJ", None),        # 1 = não respondeu
        (2018, "SC", "privada"),   # 4 em 2018
        (2018, "SP", "exterior"),  # 3 em 2018
        (2019, "SC", "privada"),   # 3 em 2019
        (2024, "RS", "mista"),     # Q023 = B
    ]


def test_renda_usa_q007_a_partir_de_2024(dados):
    preparar_silver(dados)
    carregar_perfil()
    perfil = dados / "gold/enem_perfil.parquet"

    resultado = dict(consultar(perfil, "SELECT NU_ANO, RENDA_FAMILIAR FROM ARQUIVO WHERE SG_UF_PROVA IN ('SC', 'RS')"))
    assert resultado[2019] == "D"   # Q006
    assert resultado[2024] == "C"   # Q007, e não a Q006 ("Você possui renda?")


def test_notas_juntam_os_anos_e_ficam_ordenadas(dados):
    preparar_silver(dados)
    carregar_notas()
    notas = dados / "gold/enem_notas.parquet"

    anos = [linha[0] for linha in consultar(notas, "SELECT NU_ANO FROM ARQUIVO")]
    assert anos == sorted(anos)
    assert len(anos) == 5

    # Em 2024 nota e perfil estão em arquivos sem ligação, então o perfil fica vazio na tabela de notas
    linha_2024 = consultar(notas, "SELECT TIPO_ESCOLA, RENDA_FAMILIAR, NU_NOTA_MT FROM ARQUIVO WHERE NU_ANO = 2024")
    assert linha_2024 == [(None, None, 530)]


def test_marca_nota_zero(dados):
    nota_zero = linha_antiga(2018, "SC", 2, "A")
    nota_zero[19] = "0.0"  # NU_NOTA_MT
    faltou = linha_antiga(2018, "SP", 2, "A")
    faltou[12:20] = ["0", "0", "0", "0", "", "", "", ""]  # presenças e notas
    escrever_csv(dados / "bronze/csv/ano=2018/MICRODADOS_ENEM_2018.csv", COLUNAS_ANTIGO, [
        nota_zero,
        faltou,
        linha_antiga(2018, "RJ", 2, "A"),
    ])
    transformar(2018)
    carregar_notas()
    notas = dados / "gold/enem_notas.parquet"

    resultado = consultar(notas, "SELECT SG_UF_PROVA, IN_NOTA_ZERO FROM ARQUIVO ORDER BY 1")
    assert resultado == [
        ("RJ", False),
        ("SC", True),
        ("SP", False),  # faltou: nota nula não é nota zero
    ]


def test_resumo_harmoniza_perguntas_e_soma_o_total(dados):
    # Internet: Q025 até 2023 e Q020 de 2024 em diante | computador: Q024 e Q021
    antigo = COLUNAS_ANTIGO + ["Q024", "Q025"]
    novo = COLUNAS_PARTICIPANTES + ["Q020", "Q021"]
    escrever_csv(dados / "bronze/csv/ano=2018/MICRODADOS_ENEM_2018.csv", antigo, [
        linha_antiga(2018, "SC", 2, "B") + ["A", "B"],   # sem computador, com internet
        linha_antiga(2018, "SC", 2, "Q") + ["C", "B"],   # 2 computadores, com internet
        linha_antiga(2018, "SP", 2, "A") + ["A", "A"],   # sem computador, sem internet
    ])
    escrever_csv(dados / "bronze/csv/ano=2024/PARTICIPANTES_2024.csv", novo, [
        # Q006 = possui renda própria (B = sim); Q007 = renda da família
        ["1", "2024", "3", "F", "1", "1", "0", "RS", "E", "F", "B", "B", "B", "A", "B"],
        ["2", "2024", "3", "M", "3", "1", "0", "RS", "E", "F", "A", "C", "A", "B", "A"],
    ])
    escrever_csv(dados / "bronze/csv/ano=2024/RESULTADOS_2024.csv", COLUNAS_RESULTADOS, [])
    for ano in (2018, 2024):
        transformar(ano)
    carregar_perfil()
    resumo = carregar_resumo_perfil()

    def contagem(indicador, ano):
        return dict(consultar(resumo, f"""
            SELECT CATEGORIA, sum(N)::INT FROM ARQUIVO
            WHERE INDICADOR = '{indicador}' AND NU_ANO = {ano} AND RECORTE IS NULL GROUP BY 1
        """))

    assert contagem("internet", 2018) == {"sim": 2, "nao": 1}
    assert contagem("internet", 2024) == {"nao": 1, "sim": 1}   # Q020, não a Q025
    assert contagem("computador", 2018) == {"nenhum": 2, "dois_mais": 1}
    assert contagem("computador", 2024) == {"um": 1, "nenhum": 1}
    assert contagem("renda_propria", 2024) == {"sim": 1, "nao": 1}
    assert contagem("renda_propria", 2018) == {}               # pergunta só existe a partir de 2024
    assert contagem("renda_familiar", 2018) == {"ate_1": 1, "mais_20": 1, "nenhuma": 1}

    # Por UF a soma de cada indicador é o total de inscritos que responderam
    por_uf = dict(consultar(resumo, """
        SELECT SG_UF_PROVA, sum(N)::INT FROM ARQUIVO
        WHERE INDICADOR = 'sexo' AND NU_ANO = 2018 AND RECORTE IS NULL GROUP BY 1
    """))
    assert por_uf == {"SC": 2, "SP": 1}

    # O cruzamento nacional soma o mesmo total e não tem UF
    cruzamento = consultar(resumo, """
        SELECT RECORTE_CATEGORIA, CATEGORIA, N::INT, SG_UF_PROVA FROM ARQUIVO
        WHERE INDICADOR = 'computador' AND NU_ANO = 2018 AND RECORTE = 'renda' ORDER BY 1, 2
    """)
    assert cruzamento == [("ate_1", "nenhum", 2, None), ("mais_10", "dois_mais", 1, None)]
