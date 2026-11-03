"""Verificações de qualidade na gold de verdade (data/gold), não nos CSVs de teste.

Só rodam se o pipeline já gerou a gold. Servem para pegar mudanças no formato do INEP ou erros
no pipeline que os testes com dados pequenos não mostram.
"""
import duckdb
import pytest

from enem_pja3.config import DATA_DIR

NOTAS = DATA_DIR / "gold" / "enem_notas.parquet"
PERFIL = DATA_DIR / "gold" / "enem_perfil.parquet"

pytestmark = pytest.mark.skipif(not (NOTAS.exists() and PERFIL.exists()), reason="gold ainda não foi gerada")


def contar(sql):
    return duckdb.sql(sql.replace("NOTAS", f"'{NOTAS}'").replace("PERFIL", f"'{PERFIL}'")).fetchone()[0]


@pytest.mark.parametrize("area", ["CN", "CH", "LC", "MT"])
def test_presenca_e_nota_batem(area):
    # 1 = presente: tem nota | 0 = faltou e 2 = eliminado: não tem nota
    assert contar(f"SELECT count(*) FROM NOTAS WHERE TP_PRESENCA_{area} = 1 AND NU_NOTA_{area} IS NULL") == 0
    assert contar(f"SELECT count(*) FROM NOTAS WHERE TP_PRESENCA_{area} <> 1 AND NU_NOTA_{area} IS NOT NULL") == 0


def test_notas_dentro_da_escala():
    assert contar("""
        SELECT count(*) FROM NOTAS
        WHERE NOT (NU_NOTA_CN BETWEEN 0 AND 1000 AND NU_NOTA_CH BETWEEN 0 AND 1000
                   AND NU_NOTA_LC BETWEEN 0 AND 1000 AND NU_NOTA_MT BETWEEN 0 AND 1000)
    """) == 0


def test_redacao_vai_de_20_em_20():
    assert contar("SELECT count(*) FROM NOTAS WHERE NU_NOTA_REDACAO NOT BETWEEN 0 AND 1000") == 0
    assert contar("SELECT count(*) FROM NOTAS WHERE NU_NOTA_REDACAO % 20 <> 0") == 0


def test_redacao_zero_tem_motivo():
    # TP_STATUS_REDACAO = 1 é redação sem problema, então a nota não pode ser 0
    assert contar("SELECT count(*) FROM NOTAS WHERE NU_NOTA_REDACAO = 0 AND TP_STATUS_REDACAO = 1") == 0


def test_nota_zero_marcada():
    assert contar("""
        SELECT count(*) FROM NOTAS
        WHERE IN_NOTA_ZERO <> COALESCE(0 IN (NU_NOTA_CN, NU_NOTA_CH, NU_NOTA_LC, NU_NOTA_MT), false)
    """) == 0


@pytest.mark.parametrize("arquivo", ["NOTAS", "PERFIL"])
def test_todas_as_ufs_em_todos_os_anos(arquivo):
    assert contar(f"SELECT count(*) FROM {arquivo} WHERE SG_UF_PROVA IS NULL") == 0
    assert contar(f"""
        SELECT count(*) FROM (SELECT NU_ANO FROM {arquivo} GROUP BY 1 HAVING count(DISTINCT SG_UF_PROVA) <> 27)
    """) == 0


def test_notas_e_perfil_com_as_mesmas_linhas_por_ano():
    # Uma linha por inscrito nas duas tabelas
    assert contar("""
        SELECT count(*) FROM
            (SELECT NU_ANO, count(*) AS n FROM NOTAS GROUP BY 1) n
            FULL JOIN (SELECT NU_ANO, count(*) AS n FROM PERFIL GROUP BY 1) p USING (NU_ANO)
        WHERE n.n IS DISTINCT FROM p.n
    """) == 0
