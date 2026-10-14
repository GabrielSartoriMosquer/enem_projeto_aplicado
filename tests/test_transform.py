from decimal import Decimal

import duckdb

from conftest import COLUNAS_ANTIGO, COLUNAS_PARTICIPANTES, COLUNAS_RESULTADOS, escrever_csv
from enem_pja3.transform.transform import ler_csv, transformar

# Uma pessoa presente (com acento no município, para testar o latin-1) e uma que faltou (notas vazias)
LINHAS_2018 = [
    ["1", "2018", "3", "F", "1", "1", "4", "0", "Florianópolis", "2", "1", "SC",
     "1", "1", "1", "1", "512.3", "600.0", "550.5", "700.1", "0", "880", "1", "E", "F", "Q"],
    ["2", "2018", "5", "M", "3", "2", "2", "1", "", "", "", "SP",
     "0", "0", "0", "0", "", "", "", "", "1", "", "", "A", "B", "A"],
]


def ler(parquet):
    return duckdb.sql(f"SELECT * FROM '{parquet}' ORDER BY SG_UF_PROVA")


def test_formato_antigo_tipos_e_valores(dados):
    escrever_csv(dados / "bronze/csv/ano=2018/MICRODADOS_ENEM_2018.csv", COLUNAS_ANTIGO, LINHAS_2018)
    transformar(2018)

    tabela = ler(dados / "silver/enem/ano=2018/dados.parquet")
    tipos = dict(zip(tabela.columns, [str(t) for t in tabela.types]))
    assert tipos["NU_NOTA_MT"] == "DECIMAL(5,1)"
    assert tipos["TP_ESCOLA"] == "UTINYINT"
    assert tipos["IN_TREINEIRO"] == "BOOLEAN"
    assert tipos["NU_NOTA_REDACAO"] == "SMALLINT"

    sc, sp = tabela.fetchall()
    linha_sc = dict(zip(tabela.columns, sc))
    linha_sp = dict(zip(tabela.columns, sp))
    assert linha_sc["NU_NOTA_MT"] == Decimal("700.1")
    assert linha_sc["IN_TREINEIRO"] is False
    assert linha_sp["IN_TREINEIRO"] is True
    # Campo vazio no CSV vira NULL (quem faltou não tem nota)
    assert linha_sp["NU_NOTA_MT"] is None
    assert linha_sp["TP_DEPENDENCIA_ADM_ESC"] is None


def test_contrato_nao_leva_inscricao_nem_colunas_extras(dados):
    escrever_csv(dados / "bronze/csv/ano=2018/MICRODADOS_ENEM_2018.csv", COLUNAS_ANTIGO, LINHAS_2018)
    transformar(2018)

    colunas = ler(dados / "silver/enem/ano=2018/dados.parquet").columns
    assert "NU_INSCRICAO" not in colunas
    assert "NO_MUNICIPIO_ESC" not in colunas
    # O questionário vem inteiro
    assert {"Q001", "Q002", "Q006"} <= set(colunas)


def test_formato_novo_gera_duas_tabelas(dados):
    escrever_csv(dados / "bronze/csv/ano=2024/PARTICIPANTES_2024.csv", COLUNAS_PARTICIPANTES,
                 [["1", "2024", "3", "F", "1", "1", "0", "RS", "E", "F", "B", "C", "B"]])
    escrever_csv(dados / "bronze/csv/ano=2024/RESULTADOS_2024.csv", COLUNAS_RESULTADOS,
                 [["1", "2024", "2", "1", "RS", "1", "1", "1", "1", "500.0", "510.0", "520.0", "530.0", "0", "900", "1"]])
    transformar(2024)

    participantes = ler(dados / "silver/participantes/ano=2024/dados.parquet")
    resultados = ler(dados / "silver/resultados/ano=2024/dados.parquet")
    assert "NU_NOTA_MT" not in participantes.columns
    assert "Q007" in participantes.columns
    assert "TP_SEXO" not in resultados.columns
    assert resultados.fetchone()[resultados.columns.index("NU_NOTA_MT")] == Decimal("530.0")


def test_leitura_do_csv_em_serie(tmp_path):
    # Em paralelo o DuckDB misturava linhas do CSV em latin-1 (ver README)
    assert "parallel=false" in ler_csv(tmp_path / "x.csv")
