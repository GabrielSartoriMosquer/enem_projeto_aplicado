"""Testes da análise da rede escolar (src/enem_pja3/analises/rede_escolar.py).

Rodam sem a gold de verdade: cada teste grava uma gold sintética pequena em tmp_path, com as
mesmas colunas e os mesmos tipos de data/gold/enem_notas.parquet (ver load.py e transform.py).
"""
import math
from statistics import NormalDist

import duckdb
import pytest

from enem_pja3.analises import rede_escolar

Z95 = NormalDist().inv_cdf(0.975)  # 1,959964...

# Contrato de colunas da gold de notas, na ordem e com os tipos gravados pelo load.
# TIPO_ESCOLA, escolaridade e renda só vêm preenchidas de 2018 a 2023 (formato antigo).
COLUNAS_GOLD = {
    "NU_ANO": "USMALLINT",
    "SG_UF_PROVA": "VARCHAR",
    "TP_DEPENDENCIA_ADM_ESC": "UTINYINT",
    "TP_LOCALIZACAO_ESC": "UTINYINT",
    "TIPO_ESCOLA": "VARCHAR",
    "ESCOLARIDADE_PAI": "VARCHAR",
    "ESCOLARIDADE_MAE": "VARCHAR",
    "RENDA_FAMILIAR": "VARCHAR",
    "TP_PRESENCA_CN": "UTINYINT",
    "TP_PRESENCA_CH": "UTINYINT",
    "TP_PRESENCA_LC": "UTINYINT",
    "TP_PRESENCA_MT": "UTINYINT",
    "NU_NOTA_CN": "DECIMAL(5,1)",
    "NU_NOTA_CH": "DECIMAL(5,1)",
    "NU_NOTA_LC": "DECIMAL(5,1)",
    "NU_NOTA_MT": "DECIMAL(5,1)",
    "TP_LINGUA": "UTINYINT",
    "NU_NOTA_REDACAO": "SMALLINT",
    "TP_STATUS_REDACAO": "UTINYINT",
    "IN_NOTA_ZERO": "BOOLEAN",
}


def participante(ano=2018, rede=2, cn=500.0, ch=500.0, lc=500.0, mt=500.0, redacao=600, **extra):
    """Uma linha da gold com o participante presente nas quatro provas e redação válida.

    rede é o TP_DEPENDENCIA_ADM_ESC (None = não informado). Qualquer coluna pode ser trocada
    por extra, por exemplo TP_PRESENCA_MT=0 ou IN_NOTA_ZERO=True.
    """
    linha = {
        "NU_ANO": ano, "SG_UF_PROVA": "SP", "TP_DEPENDENCIA_ADM_ESC": rede,
        "TP_PRESENCA_CN": 1, "TP_PRESENCA_CH": 1, "TP_PRESENCA_LC": 1, "TP_PRESENCA_MT": 1,
        "NU_NOTA_CN": cn, "NU_NOTA_CH": ch, "NU_NOTA_LC": lc, "NU_NOTA_MT": mt,
        "TP_LINGUA": 0, "NU_NOTA_REDACAO": redacao, "TP_STATUS_REDACAO": 1,
        "IN_NOTA_ZERO": 0 in (cn, ch, lc, mt),
    }
    linha.update(extra)
    return linha


def gravar_gold_sintetica(tmp_path, linhas, sem_colunas=()):
    """Grava uma gold sintética em tmp_path/gold/enem_notas.parquet e devolve o caminho.

    linhas é uma lista de dicts {coluna: valor}; coluna que não aparece fica NULL.
    sem_colunas tira colunas do arquivo (para testar gold com coluna faltando).
    """
    colunas = {nome: tipo for nome, tipo in COLUNAS_GOLD.items() if nome not in sem_colunas}
    destino = tmp_path / "gold" / "enem_notas.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql(f"CREATE TABLE gold ({', '.join(f'{nome} {tipo}' for nome, tipo in colunas.items())})")
    if linhas:
        marcadores = ", ".join("?" for _ in colunas)
        con.executemany(
            f"INSERT INTO gold VALUES ({marcadores})",
            [[linha.get(nome) for nome in colunas] for linha in linhas],
        )
    con.sql(f"COPY gold TO '{destino}' (FORMAT parquet)")
    con.close()
    return destino


def test_gold_sintetica_tem_o_contrato_da_gold(tmp_path):
    gold = gravar_gold_sintetica(tmp_path, [participante(), participante(ano=2024, rede=None)])
    esquema = dict(duckdb.sql(f"SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM '{gold}')").fetchall())
    assert esquema == COLUNAS_GOLD
    assert set(rede_escolar.COLUNAS_OBRIGATORIAS) <= set(esquema)
    assert duckdb.sql(f"SELECT count(*), count(TP_DEPENDENCIA_ADM_ESC) FROM '{gold}'").fetchone() == (2, 1)


def test_gold_sintetica_sem_coluna(tmp_path):
    gold = gravar_gold_sintetica(tmp_path, [participante()], sem_colunas=["IN_NOTA_ZERO"])
    colunas = [c[0] for c in duckdb.sql(f"DESCRIBE SELECT * FROM '{gold}'").fetchall()]
    assert "IN_NOTA_ZERO" not in colunas


def test_constantes_do_modulo():
    assert rede_escolar.AREAS == rede_escolar.AREAS_OBJETIVAS + ("REDACAO",)
    assert rede_escolar.REDES == {1: "federal", 2: "estadual", 3: "municipal", 4: "privada"}
    grupos = set(rede_escolar.REDES.values()) | {"publica"}
    assert all(a in grupos and b in grupos for a, b in rede_escolar.PARES)
    assert len(rede_escolar.PARES) == 5


# --- Probabilidade de superioridade, d de Cohen e intervalos (tarefa 2.1) --------------------

def test_prob_superioridade_e_cohen_d_conta_a_mao():
    # A = {1, 2, 3} e B = {2, 4}, em histogramas nota×10.
    # Pares A > B: só (3, 2); empate: (2, 2) vale 0,5. AUC = 1,5 / 6 = 0,25
    a, b = {10: 1, 20: 1, 30: 1}, {20: 1, 40: 1}
    assert rede_escolar.prob_superioridade(a, b) == 0.25
    assert rede_escolar.prob_superioridade(b, a) == 0.75
    # médias 2 e 3, variâncias 1 e 2; desvio combinado = raiz((2·1 + 1·2) / 3) = raiz(4/3)
    d = rede_escolar.cohen_d(rede_escolar.estatisticas(a), rede_escolar.estatisticas(b))
    assert abs(d - (-1 / (4 / 3) ** 0.5)) < 1e-12


def test_comparar_grupos_registra_ic_e_metodo():
    a = {v: 3 for v in range(4000, 6000, 10)}
    b = {v: 3 for v in range(3500, 5500, 10)}
    r = rede_escolar.comparar_grupos(a, b, min_grupo=100)
    assert r["calculado"] is True
    for medida, metodo in (("prob_superioridade", rede_escolar.METODO_IC_AUC),
                           ("cohen_d", rede_escolar.METODO_IC_COHEN_D)):
        inferior, superior = r[medida]["ic"]
        assert inferior <= r[medida]["valor"] <= superior
        assert r[medida]["metodo"] == metodo
    assert 0.5 < r["prob_superioridade"]["valor"] <= 1


def test_comparar_grupos_abaixo_do_minimo_e_desvio_zero():
    pequeno = rede_escolar.comparar_grupos({5000: 50}, {6000: 200}, min_grupo=100)
    assert pequeno["calculado"] is False and pequeno["n"] == 50 and "mínimo" in pequeno["motivo"]
    # todos com a mesma nota em cada grupo: AUC existe (0 ou 1), mas o d não
    constante = rede_escolar.comparar_grupos({5000: 150}, {6000: 150}, min_grupo=100)
    assert constante["prob_superioridade"]["valor"] == 0.0
    assert constante["cohen_d"]["calculado"] is False
    assert "zero" in constante["cohen_d"]["motivo"]


# --- Testes de exemplo com contas à mão (tarefa 2.4) -----------------------------------------

def test_ic_prob_superioridade_e_cohen_d_conta_a_mao():
    # Mesmos grupos do teste anterior: A = {1, 2, 3}, B = {2, 4}, θ = 0,25, nA = 3, nB = 2.
    a, b = {10: 1, 20: 1, 30: 1}, {20: 1, 40: 1}
    # Hanley–McNeil: Q1 = 0,25 / 1,75 = 1/7; Q2 = 2 · 0,0625 / 1,25 = 0,1; θ² = 0,0625
    # EP² = [0,1875 + 2 · (1/7 − 0,0625) + 1 · (0,1 − 0,0625)] / 6 = 0,385714 / 6 = 0,0642857
    # margem = 1,96 · 0,253546 = 0,49694 → IC = [max(0; −0,24694); 0,74694] = [0; 0,74694]
    inferior, superior = rede_escolar.ic_prob_superioridade(a, b)
    ep2 = (0.1875 + 2 * (1 / 7 - 0.0625) + (0.1 - 0.0625)) / 6
    assert inferior == 0.0
    assert superior == pytest.approx(0.25 + Z95 * math.sqrt(ep2), abs=1e-12)
    assert superior == pytest.approx(0.74694, abs=1e-5)
    # d = −1 / raiz(4/3) = −0,866025; Var(d) = 5/6 + 0,75 / 10 = 0,908333
    # margem = 1,96 · 0,953065 = 1,867974 → IC = [−2,73400; 1,00195]
    inferior, superior = rede_escolar.ic_cohen_d(rede_escolar.estatisticas(a), rede_escolar.estatisticas(b))
    assert inferior == pytest.approx(-2.73400, abs=1e-5)
    assert superior == pytest.approx(1.00195, abs=1e-5)


def test_comparar_grupos_no_limite_do_minimo():
    # n igual ao mínimo calcula; um a menos não calcula e registra o tamanho do menor grupo
    a, b = {5000: 50, 5100: 50}, {4900: 50, 5000: 50}
    assert rede_escolar.comparar_grupos(a, b, min_grupo=100)["calculado"] is True
    abaixo = rede_escolar.comparar_grupos(a, {4900: 99}, min_grupo=100)
    assert abaixo["calculado"] is False
    assert (abaixo["n"], abaixo["n_a"], abaixo["n_b"]) == (99, 100, 99)


def test_percentil_lookup_conta_a_mao():
    # Notas {1, 2, 2, 3}, n = 4:
    #   1 → 100 · (0 + 0,5 · 1) / 4 = 12,5
    #   2 → 100 · (1 + 0,5 · 2) / 4 = 50
    #   3 → 100 · (3 + 0,5 · 1) / 4 = 87,5
    lookup = rede_escolar.percentil_lookup({10: 1, 20: 2, 30: 1})
    assert lookup == {10: 12.5, 20: 50.0, 30: 87.5}
    # um único participante fica no percentil 50
    assert rede_escolar.percentil_lookup({5000: 1}) == {5000: 50.0}
    with pytest.raises(ValueError):
        rede_escolar.percentil_lookup({})


def test_mediana_percentil_por_rede_conta_a_mao():
    # Amostra_Valida (com os sem rede, que entram no percentil): notas {1, 2, 2, 3, 4, 4}, n = 6
    #   1 → 100 · 0,5 / 6 = 50/6;  2 → 100 · (1 + 1) / 6 = 200/6
    #   3 → 100 · (3 + 0,5) / 6 = 350/6;  4 → 100 · (4 + 1) / 6 = 500/6
    hist = {
        "federal": {30: 1},
        "estadual": {10: 1, 20: 1},
        "privada": {20: 1},
        "sem_rede": {40: 2},
    }
    medianas = rede_escolar.mediana_percentil_por_rede(hist)
    assert medianas["federal"] == pytest.approx(350 / 6)           # um só participante, nota 3
    assert medianas["estadual"] == pytest.approx((50 / 6 + 200 / 6) / 2)  # n par: média dos dois
    assert medianas["privada"] == pytest.approx(200 / 6)
    # pública = federal + estadual = {1, 2, 3}: o do meio tem nota 2
    assert medianas["publica"] == pytest.approx(200 / 6)
    # municipal sem participantes fica como não calculada
    assert medianas["municipal"]["calculado"] is False and medianas["municipal"]["n"] == 0
    # com min_grupo = 2, a federal e a privada (n = 1) também ficam sem cálculo
    filtradas = rede_escolar.mediana_percentil_por_rede(hist, min_grupo=2)
    assert filtradas["federal"]["calculado"] is False and filtradas["federal"]["n"] == 1
    assert filtradas["estadual"] == pytest.approx(125 / 6)


def test_topo10_sem_empate_no_corte():
    # Notas 1..10, uma de cada. Acumulado em 9 é 9 (10 · 9 = 90, não > 90); em 10 é 10 (100 > 90).
    # Corte = 10, Topo_10 = {10}: 1 de 10 = exatamente 10%
    topo = rede_escolar.topo10({v * 10: 1 for v in range(1, 11)})
    assert (topo["corte"], topo["corte_x10"], topo["n_topo"], topo["n"]) == (10.0, 100, 1, 10)
    assert topo["prop_real"] == 0.1


def test_topo10_com_empate_no_corte_passa_de_10_porcento():
    # Notas: cinco 1, três 2, dois 3 (n = 10). Acumulado: 5, 8, 10; só em 3 vale 10 · 10 > 90.
    # Corte = 3 e os dois empatados na nota 3 entram: prop_real = 2 / 10 = 20% > 10%
    topo = rede_escolar.topo10({10: 5, 20: 3, 30: 2})
    assert topo["corte"] == 3.0 and topo["n_topo"] == 2
    assert topo["prop_real"] == 0.2 and topo["prop_real"] > 0.1
    # Caso extremo: todos com a mesma nota ficam no topo (100%)
    assert rede_escolar.topo10({5000: 30})["prop_real"] == 1.0


# Histogramas da razão de representação, com corte em nota 10 (chave 100):
#   federal  : 2 no topo de 4      estadual: 1 no topo de 10
#   municipal: 0 no topo de 4      privada : 2 no topo de 2
#   sem_rede : 5 no topo (fora da razão, que só usa rede informada)
# Com rede informada: N = 4 + 10 + 4 + 2 = 20 e T = 2 + 1 + 0 + 2 = 5.
HIST_RAZAO = {
    "federal": {100: 2, 50: 2},
    "estadual": {100: 1, 50: 9},
    "municipal": {50: 4},
    "privada": {100: 2},
    "sem_rede": {100: 5},
}


def test_razao_representacao_conta_a_mao():
    r = rede_escolar.razao_representacao(HIST_RAZAO, corte_x10=100)
    # R = (t · N) / (T · n)
    assert r["federal"]["razao"] == 2.0           # (2 · 20) / (5 · 4) = 40/20
    assert r["estadual"]["razao"] == 0.4          # (1 · 20) / (5 · 10) = 20/50
    assert r["municipal"]["razao"] == 0.0         # ninguém no topo
    assert r["privada"]["razao"] == 4.0           # (2 · 20) / (5 · 2) = 40/10
    assert r["publica"]["razao"] == pytest.approx(2 / 3)  # (3 · 20) / (5 · 18) = 60/90
    assert r["federal"]["participacao_todos"] == 0.2 and r["federal"]["participacao_topo"] == 0.4
    # Consistência: 0,2 · 2 + 0,5 · 0,4 + 0,2 · 0 + 0,1 · 4 = 0,4 + 0,2 + 0 + 0,4 = 1
    soma = sum(r[rede]["participacao_todos"] * r[rede]["razao"] for rede in rede_escolar.REDES.values())
    assert soma == pytest.approx(1.0, abs=1e-12)
    for rede in ("federal", "estadual", "municipal", "privada", "publica"):
        assert r[rede]["calculado"] is True
        assert r[rede]["metodo"] == rede_escolar.METODO_IC_RAZAO
        inferior, superior = r[rede]["ic"]
        assert inferior <= r[rede]["razao"] <= superior


def test_ic_razao_conta_a_mao():
    # Federal: p_topo = 2/5 = 0,4 e p_todos = 4/20 = 0,2
    # Var(log R) = (1 − 0,4) / 2 + (1 − 0,2) / 4 = 0,3 + 0,2 = 0,5; EP = 0,707107
    # margem = 1,96 · 0,707107 = 1,385904 → IC = 2 · exp(∓1,385904) = [0,50020; 7,99688]
    inferior, superior = rede_escolar.ic_razao(2, 5, 4, 20)
    assert inferior == pytest.approx(2 * math.exp(-Z95 * math.sqrt(0.5)), rel=1e-12)
    assert superior == pytest.approx(2 * math.exp(Z95 * math.sqrt(0.5)), rel=1e-12)
    assert (round(inferior, 4), round(superior, 4)) == (0.5002, 7.9969)
    # Municipal com 0 no topo: limite inferior 0 e superior finito (correção de 0,5 participante)
    inferior, superior = rede_escolar.ic_razao(0, 5, 4, 20)
    assert inferior == 0.0 and 0 < superior < math.inf
    with pytest.raises(ValueError):
        rede_escolar.ic_razao(0, 5, 0, 20)


def test_razao_representacao_nao_calculada():
    # min_grupo = 3: a privada (n = 2) fica sem razão, com o tamanho registrado
    r = rede_escolar.razao_representacao(HIST_RAZAO, corte_x10=100, min_grupo=3)
    assert r["privada"]["calculado"] is False and r["privada"]["n"] == 2
    assert r["federal"]["calculado"] is True
    # rede sem participantes com rede informada (Requisito 8.5)
    sem_municipal = {k: v for k, v in HIST_RAZAO.items() if k != "municipal"}
    r = rede_escolar.razao_representacao(sem_municipal, corte_x10=100)
    assert r["municipal"]["calculado"] is False and r["municipal"]["n"] == 0
    # só quem não tem rede informada chegou ao topo: nenhuma razão é calculada
    r = rede_escolar.razao_representacao({"estadual": {50: 3}, "sem_rede": {200: 1}}, corte_x10=200)
    assert all(registro["calculado"] is False for registro in r.values())


def test_representacao_topo10_usa_amostra_inteira_no_corte():
    # Amostra inteira: 8 notas 5 (estadual 6, privada 2) e 2 notas 10 (sem rede 1, privada 1).
    # Acumulado em 5 é 8 (80 ≤ 90); em 10 é 10 (100 > 90) → corte 10, prop_real 2/10 = 0,2.
    # Com rede informada: N = 9, T = 1 (a privada) → R_privada = (1 · 9) / (1 · 3) = 3
    hist = {"estadual": {50: 6}, "privada": {50: 2, 100: 1}, "sem_rede": {100: 1}}
    r = rede_escolar.representacao_topo10(hist)
    assert (r["corte"], r["n_topo"], r["n"], r["prop_real"]) == (10.0, 2, 10, 0.2)
    assert r["por_rede"]["privada"]["razao"] == 3.0
    assert r["por_rede"]["estadual"]["razao"] == 0.0


def test_perfil_relativo_conta_a_mao():
    # Percentis 60, 40, 50, 80, 20: média = 250 / 5 = 50 → perfil 10, −10, 0, 30, −30
    percentis = {"CN": 60.0, "CH": 40.0, "LC": 50.0, "MT": 80.0, "REDACAO": 20.0}
    assert rede_escolar.perfil_relativo(percentis) == {
        "CN": 10.0, "CH": -10.0, "LC": 0.0, "MT": 30.0, "REDACAO": -30.0,
    }
    assert rede_escolar.perfil_relativo([60, 40, 50, 80, 20]) == [10, -10, 0, 30, -30]
    # perfil uniforme: todos os componentes zero
    assert rede_escolar.perfil_relativo([37.5] * 5) == [0.0] * 5
    with pytest.raises(ValueError):
        rede_escolar.perfil_relativo({"CN": 50.0, "CH": 50.0})
    with pytest.raises(ValueError):
        rede_escolar.perfil_relativo([50, 50, 50, 50])


def test_ranking_areas():
    aucs = {"CN": 0.6, "CH": 0.7, "LC": 0.65, "MT": 0.8, "REDACAO": 0.55}
    assert rede_escolar.ranking_areas(aucs) == ["MT", "CH", "LC", "CN", "REDACAO"]
    # empate na AUC segue a ordem de AREAS (CN antes de CH); não calculada fica fora do ranking
    aucs = {"CN": 0.6, "CH": 0.6, "LC": None, "MT": {"calculado": False, "motivo": "x"},
            "REDACAO": {"calculado": True, "prob_superioridade": {"valor": 0.9}}}
    assert rede_escolar.ranking_areas(aucs) == ["REDACAO", "CN", "CH"]
    # aceita o dict de comparações de uma edição inteira
    assert rede_escolar.ranking_areas({"privada_vs_publica": {"CN": 0.5, "MT": 0.7}}) == ["MT", "CN"]
    with pytest.raises(ValueError):
        rede_escolar.ranking_areas({"XX": 0.5})


def test_kendall_w_conta_a_mao():
    # Rankings idênticos: W = 1. Um único ranking também dá 1.
    assert rede_escolar.kendall_w([["a", "b", "c"]] * 4) == 1.0
    assert rede_escolar.kendall_w([["a", "b", "c"]]) == 1.0
    # Dois rankings invertidos (m = 2, n = 3): somas 4, 4, 4 = m(n+1)/2 → S = 0 → W = 0
    assert rede_escolar.kendall_w([["a", "b", "c"], ["c", "b", "a"]]) == 0.0
    # m = 3, n = 3: a = 1+1+2 = 4, b = 2+3+1 = 6, c = 3+2+3 = 8; média 6 → S = 4 + 0 + 4 = 8
    # W = 12 · 8 / (3² · (27 − 3)) = 96 / 216 = 4/9
    w = rede_escolar.kendall_w([["a", "b", "c"], ["a", "c", "b"], ["b", "a", "c"]])
    assert w == pytest.approx(4 / 9, abs=1e-12)
    # itens diferentes: só os comuns (a, c), renumerados → rankings iguais → W = 1
    assert rede_escolar.kendall_w([["a", "b", "c"], ["a", "c"]]) == 1.0
    assert rede_escolar.kendall_w([]) is None
    assert rede_escolar.kendall_w([["a"], ["a"]]) is None
    with pytest.raises(ValueError):
        rede_escolar.kendall_w([["a", "a"]])


def test_spearman_conta_a_mao():
    assert rede_escolar.spearman(list("abcde"), list("abcde")) == 1.0
    assert rede_escolar.spearman(list("abcde"), list("edcba")) == -1.0
    # Troca das duas primeiras posições (n = 4): Σd² = 1 + 1 = 2 → rho = 1 − 12 / 60 = 0,8
    assert rede_escolar.spearman(list("abcd"), list("bacd")) == pytest.approx(0.8, abs=1e-12)
    assert rede_escolar.spearman(["a"], ["a"]) is None


def test_posicao_federal_tres_classificacoes():
    # |0,52 − 0,5| = 0,02 < |0,70 − 0,5| = 0,20 → mais próxima da privada
    r = rede_escolar.posicao_federal(0.52, 0.70)
    assert r["classificacao"] == "mais_proxima_da_privada"
    assert r["distancia_privada"] == pytest.approx(0.02) and r["distancia_estadual"] == pytest.approx(0.20)
    # AUC(privada, federal) = 0,7 → AUC(federal, privada) = 0,3; |0,3 − 0,5| = 0,2 > |0,55 − 0,5| = 0,05
    r = rede_escolar.posicao_federal(1 - 0.7, 0.55)
    assert r["classificacao"] == "mais_proxima_da_estadual"
    # |0,4 − 0,5| = |0,6 − 0,5| = 0,1 → equidistante (arredondamento absorvido pela tolerância)
    assert rede_escolar.posicao_federal(0.4, 0.6)["classificacao"] == "equidistante"
    assert rede_escolar.posicao_federal(1 - 0.7, 0.7)["classificacao"] == "equidistante"


def test_posicao_federal_nao_calculada():
    nao = {"calculado": False, "motivo": "grupo pequeno", "n": 10}
    r = rede_escolar.posicao_federal(None, 0.6)
    assert r["calculado"] is False and "federal × privada" in r["motivo"]
    r = rede_escolar.posicao_federal(0.4, nao)
    assert r["calculado"] is False and "federal × estadual" in r["motivo"]
    # aceita o registro de comparar_grupos calculado
    calc = {"calculado": True, "prob_superioridade": {"valor": 0.52}}
    assert rede_escolar.posicao_federal(calc, 0.7)["classificacao"] == "mais_proxima_da_privada"


# --- Testes de propriedade (hypothesis) ------------------------------------------------------
from collections import Counter

from hypothesis import assume, given, settings
from hypothesis import strategies as st

TOLERANCIA = 1e-9


def notas(min_size=1, max_size=200):
    """Lista de notas discretas (inteiros de 0 a 1000), com repetições para gerar empates."""
    return st.lists(st.integers(min_value=0, max_value=1000), min_size=min_size, max_size=max_size)


def histogramas(min_size=1, max_size=200):
    """Histograma {nota_x10: contagem} montado a partir de uma lista de notas de 0 a 1000."""
    return notas(min_size, max_size).map(lambda valores: dict(Counter(v * 10 for v in valores)))


# Feature: rede-escolar-estrutura-areas, Property 1: Simetria da probabilidade de superioridade
@settings(max_examples=100)
@given(hist_a=histogramas(), hist_b=histogramas())
def test_propriedade_simetria_prob_superioridade(hist_a, hist_b):
    """**Validates: Requirements 5.3**"""
    ab = rede_escolar.prob_superioridade(hist_a, hist_b)
    ba = rede_escolar.prob_superioridade(hist_b, hist_a)
    assert abs(ab - (1 - ba)) <= TOLERANCIA


def transformar(hist, funcao):
    """Aplica funcao às notas do histograma; com funcao estritamente crescente, nada se funde."""
    return {funcao[v]: contagem for v, contagem in hist.items()}


# Feature: rede-escolar-estrutura-areas, Property 2: Invariância a transformações monotônicas
@settings(max_examples=100)
@given(hist_a=histogramas(), hist_b=histogramas(), data=st.data())
def test_propriedade_invariancia_monotonica_prob_superioridade(hist_a, hist_b, data):
    """**Validates: Requirements 5.4**"""
    # Função estritamente crescente arbitrária sobre os valores presentes: parte de um ponto
    # inicial e soma incrementos positivos ao longo dos valores distintos ordenados.
    valores = sorted(set(hist_a) | set(hist_b))
    inicio = data.draw(st.integers(min_value=-10_000, max_value=10_000), label="inicio")
    incrementos = data.draw(
        st.lists(st.integers(min_value=1, max_value=1_000), min_size=len(valores), max_size=len(valores)),
        label="incrementos",
    )
    funcao, atual = {}, inicio
    for valor, incremento in zip(valores, incrementos):
        atual += incremento
        funcao[valor] = atual

    original = rede_escolar.prob_superioridade(hist_a, hist_b)
    transformada = rede_escolar.prob_superioridade(transformar(hist_a, funcao), transformar(hist_b, funcao))
    assert abs(original - transformada) <= TOLERANCIA


def oraculo_prob_superioridade(notas_a, notas_b):
    """Definição direta: compara todos os pares (1 se a > b, 0,5 no empate) e divide por nA·nB."""
    soma = 0.0
    for a in notas_a:
        for b in notas_b:
            if a > b:
                soma += 1.0
            elif a == b:
                soma += 0.5
    return soma / (len(notas_a) * len(notas_b))


# Feature: rede-escolar-estrutura-areas, Property 3: Equivalência com o modelo de referência (oráculo)
@settings(max_examples=100)
@given(notas_a=notas(), notas_b=notas())
def test_propriedade_oraculo_prob_superioridade(notas_a, notas_b):
    """**Validates: Requirements 5.2, 5.5**"""
    hist_a = dict(Counter(v * 10 for v in notas_a))
    hist_b = dict(Counter(v * 10 for v in notas_b))
    valor = rede_escolar.prob_superioridade(hist_a, hist_b)
    assert abs(valor - oraculo_prob_superioridade(notas_a, notas_b)) <= TOLERANCIA
    assert 0.0 <= valor <= 1.0


# --- Propriedades do d de Cohen e dos intervalos (tarefas 2.8, 2.9, 2.15) ---

# Feature: rede-escolar-estrutura-areas, Property 4: Antissimetria do d de Cohen
@settings(max_examples=100)
@given(hist_a=histogramas(), hist_b=histogramas())
def test_propriedade_antissimetria_cohen_d(hist_a, hist_b):
    """**Validates: Requirements 6.2**"""
    stats_a = rede_escolar.estatisticas(hist_a)
    stats_b = rede_escolar.estatisticas(hist_b)
    ab = rede_escolar.cohen_d(stats_a, stats_b)
    # A propriedade só vale com desvio-padrão combinado maior que zero; com desvio zero
    # (nA + nB ≤ 2 ou nenhuma variação dentro dos grupos) o d não é calculado.
    assume(ab is not None)
    ba = rede_escolar.cohen_d(stats_b, stats_a)
    assert ba is not None
    assert abs(ab + ba) <= TOLERANCIA


# Feature: rede-escolar-estrutura-areas, Property 5: Invariância de escala do d de Cohen
@settings(max_examples=100)
@given(
    hist_a=histogramas(),
    hist_b=histogramas(),
    deslocamento=st.integers(min_value=-10_000, max_value=10_000),
    inclinacao=st.integers(min_value=1, max_value=100),
)
def test_propriedade_invariancia_escala_cohen_d(hist_a, hist_b, deslocamento, inclinacao):
    """**Validates: Requirements 6.3**"""
    # Transformação afim v → deslocamento + inclinacao · v (inclinacao > 0) nas chaves nota×10.
    # Coeficientes inteiros mantêm as somas de estatisticas() exatas, sem erro de arredondamento.
    def afim(hist):
        return {deslocamento + inclinacao * v: contagem for v, contagem in hist.items()}

    original = rede_escolar.cohen_d(rede_escolar.estatisticas(hist_a), rede_escolar.estatisticas(hist_b))
    assume(original is not None)
    transformado = rede_escolar.cohen_d(
        rede_escolar.estatisticas(afim(hist_a)), rede_escolar.estatisticas(afim(hist_b))
    )
    assert transformado is not None
    assert abs(original - transformado) <= TOLERANCIA


@st.composite
def tabelas_topo(draw, maximo=100_000):
    """Contagens (n_topo_rede, n_topo, n_rede, n_total) coerentes, a partir da tabela 2×2
    rede × Topo_10. Garante n_topo > 0 e n_rede > 0, como exige ic_razao."""
    topo_na_rede = draw(st.integers(min_value=0, max_value=maximo))
    minimo = 0 if topo_na_rede else 1
    topo_fora_da_rede = draw(st.integers(min_value=minimo, max_value=maximo))
    rede_fora_do_topo = draw(st.integers(min_value=minimo, max_value=maximo))
    resto = draw(st.integers(min_value=0, max_value=maximo))
    n_topo = topo_na_rede + topo_fora_da_rede
    n_rede = topo_na_rede + rede_fora_do_topo
    return topo_na_rede, n_topo, n_rede, n_topo + rede_fora_do_topo + resto


# Feature: rede-escolar-estrutura-areas, Property 11: Ordenação do intervalo de confiança
@settings(max_examples=100)
@given(hist_a=histogramas(), hist_b=histogramas(), tabela=tabelas_topo())
def test_propriedade_ordenacao_intervalos(hist_a, hist_b, tabela):
    """**Validates: Requirements 9.4**"""
    # Probabilidade de superioridade (Hanley–McNeil)
    auc = rede_escolar.prob_superioridade(hist_a, hist_b)
    inferior, superior = rede_escolar.ic_prob_superioridade(hist_a, hist_b)
    assert inferior <= auc <= superior

    # d de Cohen (variância aproximada), só quando o desvio combinado é maior que zero
    stats_a, stats_b = rede_escolar.estatisticas(hist_a), rede_escolar.estatisticas(hist_b)
    d = rede_escolar.cohen_d(stats_a, stats_b)
    if d is None:
        assert rede_escolar.ic_cohen_d(stats_a, stats_b) is None
    else:
        inferior, superior = rede_escolar.ic_cohen_d(stats_a, stats_b)
        assert inferior <= d <= superior

    # Razão de representação (método delta no log), com a razão calculada pela definição
    n_topo_rede, n_topo, n_rede, n_total = tabela
    razao = (n_topo_rede / n_topo) / (n_rede / n_total)
    inferior, superior = rede_escolar.ic_razao(n_topo_rede, n_topo, n_rede, n_total)
    assert inferior <= razao <= superior


# --- Propriedades do Kendall W e do perfil relativo (tarefas 2.16–2.19) ---


def itens_de_ranking():
    """Itens a ordenar: as cinco áreas ou de 2 a 10 itens genéricos (0, 1, ..., n − 1)."""
    return st.one_of(
        st.just(list(rede_escolar.AREAS)),
        st.integers(min_value=2, max_value=10).map(lambda n: list(range(n))),
    )


def rankings_completos(itens):
    """De 2 a 8 rankings, cada um uma permutação dos mesmos itens."""
    return st.lists(st.permutations(itens), min_size=2, max_size=8)


def rankings_parciais(itens):
    """De 2 a 8 rankings de subconjuntos dos itens, como uma área sem AUC numa edição."""
    ranking = st.lists(st.sampled_from(itens), unique=True, max_size=len(itens))
    return st.lists(ranking, min_size=2, max_size=8)


# Feature: rede-escolar-estrutura-areas, Property 12: Kendall W de rankings idênticos
@settings(max_examples=100)
@given(
    ranking=itens_de_ranking().flatmap(st.permutations),
    avaliadores=st.integers(min_value=2, max_value=8),
)
def test_propriedade_kendall_w_rankings_identicos(ranking, avaliadores):
    """**Validates: Requirements 10.4**"""
    w = rede_escolar.kendall_w([list(ranking) for _ in range(avaliadores)])
    assert w is not None
    assert abs(w - 1.0) <= TOLERANCIA


# Feature: rede-escolar-estrutura-areas, Property 13: Limite do Kendall W
@settings(max_examples=100)
@given(rankings=itens_de_ranking().flatmap(lambda itens: st.one_of(rankings_completos(itens), rankings_parciais(itens))))
def test_propriedade_limite_kendall_w(rankings):
    """**Validates: Requirements 10.5**"""
    w = rede_escolar.kendall_w(rankings)
    comuns = set(rankings[0]).intersection(*rankings[1:])
    if len(comuns) < 2:
        # Com menos de 2 itens em comum o W não é definido
        assert w is None
    else:
        assert 0.0 <= w <= 1.0


percentis_validos = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


# Feature: rede-escolar-estrutura-areas, Property 14: Soma zero do perfil relativo
@settings(max_examples=100)
@given(percentis=st.lists(percentis_validos, min_size=5, max_size=5))
def test_propriedade_soma_zero_perfil_relativo(percentis):
    """**Validates: Requirements 11.2**"""
    como_lista = rede_escolar.perfil_relativo(percentis)
    como_dict = rede_escolar.perfil_relativo(dict(zip(rede_escolar.AREAS, percentis)))
    assert abs(math.fsum(como_lista)) <= TOLERANCIA
    assert abs(math.fsum(como_dict.values())) <= TOLERANCIA


# Feature: rede-escolar-estrutura-areas, Property 15: Perfil uniforme é nulo
@settings(max_examples=100)
@given(percentil=percentis_validos)
def test_propriedade_perfil_uniforme_nulo(percentil):
    """**Validates: Requirements 11.3**"""
    como_lista = rede_escolar.perfil_relativo([percentil] * len(rede_escolar.AREAS))
    como_dict = rede_escolar.perfil_relativo({area: percentil for area in rede_escolar.AREAS})
    assert all(abs(c) <= TOLERANCIA for c in como_lista)
    assert all(abs(c) <= TOLERANCIA for c in como_dict.values())


# --- Propriedades do percentil e da razão de representação (tarefas 2.10–2.14) ---


def histogramas_grandes(max_valores=200, max_contagem=1_000_000):
    """Histograma {nota_x10: contagem} com contagens de até um milhão por nota, como numa edição
    real (milhões de participantes concentrados em poucos milhares de notas distintas)."""
    return st.dictionaries(
        st.integers(min_value=0, max_value=1000).map(lambda v: v * 10),
        st.integers(min_value=1, max_value=max_contagem),
        min_size=1,
        max_size=max_valores,
    )


def histogramas_por_rede(max_size=60, max_sem_rede=20):
    """{rede: histograma} com as quatro redes e os sem rede informada; qualquer uma pode vir vazia."""
    redes = {rede: histogramas(min_size=0, max_size=max_size) for rede in rede_escolar.REDES.values()}
    redes["sem_rede"] = histogramas(min_size=0, max_size=max_sem_rede)
    return st.fixed_dictionaries(redes)


# Feature: rede-escolar-estrutura-areas, Property 6: Limite do percentil
@settings(max_examples=100)
@given(hist=histogramas_grandes())
def test_propriedade_limite_percentil(hist):
    """**Validates: Requirements 7.2**"""
    lookup = rede_escolar.percentil_lookup(hist)
    # Toda nota presente na amostra tem percentil, e todos ficam em [0, 100]
    assert set(lookup) == set(hist)
    assert all(0.0 <= percentil <= 100.0 for percentil in lookup.values())


# Feature: rede-escolar-estrutura-areas, Property 7: Monotonicidade do percentil
@settings(max_examples=100)
@given(hist=histogramas_grandes())
def test_propriedade_monotonicidade_percentil(hist):
    """**Validates: Requirements 7.3**"""
    lookup = rede_escolar.percentil_lookup(hist)
    # O percentil de um participante só depende da nota (empatados têm o mesmo percentil). Basta
    # conferir notas distintas consecutivas: por transitividade vale para qualquer par.
    valores = sorted(hist)
    for menor, maior in zip(valores, valores[1:]):
        assert lookup[menor] <= lookup[maior]


# Feature: rede-escolar-estrutura-areas, Property 8: Centro do percentil
@settings(max_examples=100)
@given(hist=histogramas_grandes())
def test_propriedade_centro_percentil(hist):
    """**Validates: Requirements 7.4**"""
    lookup = rede_escolar.percentil_lookup(hist)
    # Média sobre os participantes: cada nota pesa pelo número de participantes com ela
    n = sum(hist.values())
    media = math.fsum(lookup[valor] * contagem for valor, contagem in hist.items()) / n
    assert abs(media - 50.0) <= TOLERANCIA


# Feature: rede-escolar-estrutura-areas, Property 9: Consistência da razão de representação
@settings(max_examples=100)
@given(hist=histogramas_por_rede())
def test_propriedade_consistencia_razao_representacao(hist):
    """**Validates: Requirements 8.3**"""
    assume(any(hist[rede] for rede in rede_escolar.REDES.values()))
    por_rede = rede_escolar.representacao_topo10(hist)["por_rede"]
    # Precondição: ao menos um participante com rede informada no Topo_10. Sem isso nenhuma
    # razão é calculada (os sem rede ocuparam todo o topo).
    assume(any(por_rede[rede]["calculado"] for rede in rede_escolar.REDES.values()))
    soma = 0.0
    for rede in rede_escolar.REDES.values():
        registro = por_rede[rede]
        if registro["calculado"]:
            soma += registro["participacao_todos"] * registro["razao"]
        else:
            # Com min_grupo = 1, só a rede vazia fica sem razão, e ela não pesa na soma
            assert registro["n"] == 0
    assert abs(soma - 1.0) <= TOLERANCIA


# Feature: rede-escolar-estrutura-areas, Property 10: Ponto fixo da razão de representação
@settings(max_examples=100)
@given(
    outras=histogramas_por_rede(),
    rede_alvo=st.sampled_from(tuple(rede_escolar.REDES.values())),
    repeticoes=st.integers(min_value=1, max_value=5),
    data=st.data(),
)
def test_propriedade_ponto_fixo_razao_representacao(outras, rede_alvo, repeticoes, data):
    """**Validates: Requirements 8.4**"""
    # As outras três redes (e os sem rede) são arbitrárias; o corte é uma nota de alguma delas,
    # então ao menos um participante com rede informada fica no topo.
    hist = {rede: h for rede, h in outras.items() if rede != rede_alvo}
    informadas = [h for rede, h in hist.items() if rede != "sem_rede"]
    notas_informadas = sorted({valor for h in informadas for valor in h})
    assume(notas_informadas)
    corte_x10 = data.draw(st.sampled_from(notas_informadas), label="corte_x10")
    n_outras = sum(sum(h.values()) for h in informadas)
    t_outras = sum(c for h in informadas for valor, c in h.items() if valor >= corte_x10)

    # A rede alvo recebe t no topo e n no total com t / n = t_outras / n_outras. Então
    # t / (t_outras + t) = n / (n_outras + n): a participação no topo é igual à participação na
    # amostra, que é a premissa da propriedade.
    mdc = math.gcd(t_outras, n_outras)
    t_alvo = repeticoes * t_outras // mdc
    n_alvo = repeticoes * n_outras // mdc
    nota_topo = data.draw(st.integers(min_value=corte_x10 // 10, max_value=1000), label="nota_topo") * 10
    alvo = {nota_topo: t_alvo}
    if n_alvo > t_alvo:
        # Só há participantes abaixo do corte se o corte for maior que a nota mínima (0)
        nota_abaixo = data.draw(st.integers(min_value=0, max_value=corte_x10 // 10 - 1), label="nota_abaixo") * 10
        alvo[nota_abaixo] = n_alvo - t_alvo
    hist[rede_alvo] = alvo

    registro = rede_escolar.razao_representacao(hist, corte_x10)[rede_alvo]
    assert registro["calculado"] is True
    assert abs(registro["participacao_topo"] - registro["participacao_todos"]) <= TOLERANCIA
    assert abs(registro["razao"] - 1.0) <= TOLERANCIA


# --- Consultas DuckDB (tarefa 4.1) -----------------------------------------------------------

def _linhas_consultas():
    """Edição 2018 com um caso de cada critério de inclusão e de cada rede, mais uma linha de 2019."""
    return [
        participante(rede=1, cn=600.0),
        participante(rede=2, cn=512.3),
        participante(rede=3, cn=450.5),
        participante(rede=4, cn=700.0),
        participante(rede=4, cn=650.0),
        participante(rede=None, cn=500.0),  # rede não informada
        participante(rede=9, cn=480.0),  # código fora de 1–4: também sem rede
        # Faltou CN e a redação tem status 4: sai de CN por presença e da redação por status
        participante(rede=2, TP_PRESENCA_CN=0, NU_NOTA_CN=None, TP_STATUS_REDACAO=4),
        participante(rede=2, cn=0.0),  # IN_NOTA_ZERO verdadeiro: sai de todas as áreas
        participante(rede=2, NU_NOTA_CN=None),  # presente em CN, mas sem nota
        participante(ano=2019, rede=4, cn=999.0),  # outra edição: nunca entra em 2018
    ]


def test_consultas_inclusao_histograma_e_cobertura(tmp_path):
    gold = gravar_gold_sintetica(tmp_path, _linhas_consultas())
    con = rede_escolar.conectar()

    assert rede_escolar.colunas_ausentes(con, gold) == []
    assert rede_escolar.anos_disponiveis(con, gold) == [2018, 2019]
    assert "$ano" in rede_escolar.amostra_valida_sql("CN") and "2018" not in rede_escolar.amostra_valida_sql("CN")
    with pytest.raises(ValueError):
        rede_escolar.amostra_valida_sql("XX")

    # Exclusões em cascata: total = soma dos excluídos + amostra válida
    assert rede_escolar.contar_inclusao(con, gold, 2018, "CN") == {
        "total": 10,
        "excluidos": {"presenca": 1, "nota_nula": 1, "nota_zero": 1},
        "amostra_valida": 7,
    }
    assert rede_escolar.contar_inclusao(con, gold, 2018, "REDACAO") == {
        "total": 10,
        "excluidos": {"presenca": 0, "status_redacao": 1, "nota_nula": 0, "nota_zero": 1},
        "amostra_valida": 8,
    }

    # Chave nota × 10 inteira (512,3 → 5123); nulo e código 9 vão para "sem_rede"
    hist = rede_escolar.histograma(con, gold, 2018, "CN")
    assert hist == {
        "federal": {6000: 1}, "estadual": {5123: 1}, "municipal": {4505: 1},
        "privada": {6500: 1, 7000: 1}, "sem_rede": {4800: 1, 5000: 1},
    }
    assert rede_escolar.histograma(con, gold, 2018, "REDACAO")["estadual"] == {6000: 2}

    # Estatísticas do DuckDB batem exatamente com as do histograma, inclusive a rede pública
    stats = rede_escolar.estatisticas_por_rede(con, gold, 2018, "CN")
    esperado = {grupo: rede_escolar.estatisticas(h) for grupo, h in hist.items()}
    esperado["publica"] = rede_escolar.estatisticas(rede_escolar.grupos_por_rede(hist)["publica"])
    assert stats == esperado

    cob = rede_escolar.cobertura(con, gold, 2018, "CN")
    assert cob["n"] == 7 and cob["n_rede_informada"] == 5
    assert cob["taxa_preenchimento"] == 5 / 7
    assert cob["por_rede"]["privada"] == {"n": 2, "proporcao": 2 / 7}
    assert cob["por_rede"]["sem_rede"] == {"n": 2, "proporcao": 2 / 7}
    assert rede_escolar.taxa_preenchimento(con, gold, 2018, "CN") == 5 / 7

    # Edição sem linhas: contagens zeradas, histogramas vazios e taxa sem denominador
    assert rede_escolar.contar_inclusao(con, gold, 2020, "MT")["total"] == 0
    assert all(h == {} for h in rede_escolar.histograma(con, gold, 2020, "MT").values())
    assert rede_escolar.estatisticas_por_rede(con, gold, 2020, "MT") == {}
    assert rede_escolar.taxa_preenchimento(con, gold, 2020, "MT") is None

    # A ordem das linhas na gold não muda nenhum agregado
    invertida = gravar_gold_sintetica(tmp_path / "invertida", list(reversed(_linhas_consultas())))
    for area in rede_escolar.AREAS:
        assert rede_escolar.contar_inclusao(con, invertida, 2018, area) == rede_escolar.contar_inclusao(con, gold, 2018, area)
        assert rede_escolar.histograma(con, invertida, 2018, area) == rede_escolar.histograma(con, gold, 2018, area)
        assert rede_escolar.estatisticas_por_rede(con, invertida, 2018, area) == rede_escolar.estatisticas_por_rede(con, gold, 2018, area)
        assert rede_escolar.cobertura(con, invertida, 2018, area) == rede_escolar.cobertura(con, gold, 2018, area)
    con.close()


def test_colunas_ausentes_lista_cada_coluna(tmp_path):
    gold = gravar_gold_sintetica(tmp_path, [participante()], sem_colunas=["IN_NOTA_ZERO", "TP_DEPENDENCIA_ADM_ESC"])
    con = rede_escolar.conectar()
    assert rede_escolar.colunas_ausentes(con, gold) == ["TP_DEPENDENCIA_ADM_ESC", "IN_NOTA_ZERO"]
    con.close()


# --- Perfil relativo médio (tarefa 4.2) ------------------------------------------------------

def test_perfil_relativo_medio_conta_a_mao(tmp_path):
    """Percentis da Amostra_Valida de cada área, perfil e média por rede conferidos à mão.

    Amostra_Valida (2018): CN = {700, 500, 500, 300}, CH = MT = {500, 700, 500, 500} com o 700 de
    um participante diferente em cada, LC = {500 × 4}, REDACAO = {600 × 3} (o sem rede não tem
    nota de redação). Percentis: CN 300 → 12,5, 500 → 50, 700 → 87,5; CH e MT 500 → 37,5,
    700 → 87,5; LC e REDACAO → 50. O sem rede entra nos percentis de CN, CH, LC e MT, mas não na
    Amostra_Completa. A linha de 2019 nunca entra.
      federal:  (87,5; 37,5; 50; 37,5; 50), média 52,5 → (35; −15; −2,5; −15; −2,5)
      estadual: (50; 87,5; 50; 37,5; 50),  média 55   → (−5; 32,5; −5; −17,5; −5)
      privada:  (50; 37,5; 50; 87,5; 50),  média 55   → (−5; −17,5; −5; 32,5; −5)
    Rede pública = federal + estadual (n = 2): média de cada componente e, com n = 2,
    dp / raiz(n) = |x1 − x2| / 2.
    """
    gold = gravar_gold_sintetica(tmp_path, [
        participante(rede=1, cn=700.0),
        participante(rede=2, ch=700.0),
        participante(rede=4, mt=700.0),
        participante(rede=None, cn=300.0, redacao=None),
        participante(ano=2019, rede=4, cn=900.0),
    ])
    con = rede_escolar.conectar()
    perfil = rede_escolar.perfil_relativo_medio(con, gold, 2018, min_grupo=1)

    assert list(perfil) == ["federal", "estadual", "municipal", "privada", "publica"]
    esperado = {
        "federal": [35.0, -15.0, -2.5, -15.0, -2.5],
        "estadual": [-5.0, 32.5, -5.0, -17.5, -5.0],
        "privada": [-5.0, -17.5, -5.0, 32.5, -5.0],
    }
    for rede, componentes in esperado.items():
        registro = perfil[rede]
        assert registro["calculado"] is True and registro["n"] == 1
        for area, valor in zip(rede_escolar.AREAS, componentes):
            assert registro[area]["valor"] == pytest.approx(valor, abs=1e-9)
            # n = 1: variância 0, o IC é o próprio ponto
            assert registro[area]["ic"] == pytest.approx([valor, valor], abs=1e-9)
            assert registro[area]["metodo"] == rede_escolar.METODO_IC_PERFIL
    assert (perfil["federal"]["area_maior"], perfil["federal"]["area_menor"]) == ("CN", "CH")
    assert (perfil["estadual"]["area_maior"], perfil["estadual"]["area_menor"]) == ("CH", "MT")
    assert (perfil["privada"]["area_maior"], perfil["privada"]["area_menor"]) == ("MT", "CH")

    publica = perfil["publica"]
    assert publica["calculado"] is True and publica["n"] == 2
    for area, media, meia_diferenca in [
        ("CN", 15.0, 20.0), ("CH", 8.75, 23.75), ("LC", -3.75, 1.25),
        ("MT", -16.25, 1.25), ("REDACAO", -3.75, 1.25),
    ]:
        assert publica[area]["valor"] == pytest.approx(media, abs=1e-9)
        assert publica[area]["ic"] == pytest.approx(
            [media - Z95 * meia_diferenca, media + Z95 * meia_diferenca], abs=1e-9
        )
    assert math.fsum(publica[area]["valor"] for area in rede_escolar.AREAS) == pytest.approx(0, abs=1e-9)
    assert (publica["area_maior"], publica["area_menor"]) == ("CN", "MT")

    # Rede sem participantes e grupo abaixo do mínimo ficam como não calculados, com n
    assert perfil["municipal"]["calculado"] is False and perfil["municipal"]["n"] == 0
    com_minimo = rede_escolar.perfil_relativo_medio(con, gold, 2018, min_grupo=2)
    assert com_minimo["federal"]["calculado"] is False and com_minimo["federal"]["n"] == 1
    assert com_minimo["publica"]["calculado"] is True
    # Edição sem linhas: nenhum grupo calculado
    assert all(not r["calculado"] for r in rede_escolar.perfil_relativo_medio(con, gold, 2020).values())
    con.close()


# --- Ida e volta do resultados.json (tarefa 5.4) ---
import functools
import importlib.util
import json
import tempfile
from pathlib import Path

SCRIPT_ANALISE = Path(__file__).resolve().parents[1] / "analises" / "rede_escolar" / "analise.py"


@functools.cache
def carregar_analise():
    """Importa analises/rede_escolar/analise.py pelo caminho (analises/ não é pacote)."""
    spec = importlib.util.spec_from_file_location("analise_rede_escolar", SCRIPT_ANALISE)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# Texto com acentos e unicode (st.text já exclui surrogates, que não são UTF-8 válido)
TEXTO = st.text(max_size=20)
REAL = st.floats(allow_nan=False, allow_infinity=False)

# JSON arbitrário: folhas str/int/float finito/bool/None, listas e dicts com chaves str
JSON_ARBITRARIO = st.recursive(
    st.none() | st.booleans() | st.integers() | REAL | TEXTO,
    lambda filhos: st.lists(filhos, max_size=5) | st.dictionaries(TEXTO, filhos, max_size=5),
    max_leaves=30,
)

NAO_CALCULADO = st.fixed_dictionaries(
    {"calculado": st.just(False), "motivo": TEXTO, "n": st.integers(min_value=0)}
)
MEDIDA_COM_IC = st.fixed_dictionaries({
    "valor": REAL,
    "ic": st.lists(REAL, min_size=2, max_size=2).map(sorted),
    "metodo": st.sampled_from(["hanley-mcneil", "hedges-olkin", "delta-log", "normal"]),
})
COMPARACAO = st.one_of(
    NAO_CALCULADO,
    st.fixed_dictionaries({
        "prob_superioridade": MEDIDA_COM_IC, "cohen_d": MEDIDA_COM_IC, "calculado": st.just(True),
    }),
)
POR_AREA = lambda valores: st.dictionaries(st.sampled_from(rede_escolar.AREAS), valores, max_size=5)  # noqa: E731
EDICAO = st.fixed_dictionaries({
    "comparacoes": st.dictionaries(
        st.sampled_from(["privada_vs_publica", "privada_vs_federal", "federal_vs_estadual"]),
        POR_AREA(COMPARACAO), max_size=3,
    ),
    "percentil_mediano": POR_AREA(st.dictionaries(st.sampled_from(list(rede_escolar.REDES.values())), REAL)),
    "ranking_areas": st.permutations(rede_escolar.AREAS),
    "posicao_federal": POR_AREA(st.sampled_from(
        ["mais_proxima_da_privada", "mais_proxima_da_estadual", "equidistante"]
    ) | NAO_CALCULADO),
    "alertas": st.lists(TEXTO, max_size=3),
})
ANOS_EDICAO = st.integers(min_value=2018, max_value=2025)
RESULTADOS_REALISTAS = st.fixed_dictionaries({
    "metadados": st.fixed_dictionaries({
        "data_execucao": st.just("2025-01-01T12:00:00-03:00"),
        "md5_gold": st.text(alphabet="0123456789abcdef", min_size=32, max_size=32),
        "parametros": st.fixed_dictionaries({
            "gold": TEXTO, "anos": st.lists(ANOS_EDICAO, unique=True),
            "min_grupo": st.integers(min_value=1), "semente": st.integers(),
        }),
        "edicoes_processadas": st.lists(ANOS_EDICAO, unique=True),
        "edicoes_ausentes": st.lists(ANOS_EDICAO, unique=True),
    }),
    "edicoes": st.dictionaries(ANOS_EDICAO.map(str), EDICAO, max_size=3),
    "estabilidade": st.fixed_dictionaries({
        "kendall_w": st.floats(min_value=0, max_value=1) | NAO_CALCULADO,
        "spearman": st.dictionaries(TEXTO, st.floats(min_value=-1, max_value=1)),
    }),
})


# Feature: rede-escolar-estrutura-areas, Property 16: Ida e volta do resultados.json
@settings(max_examples=100)
@given(resultados=st.one_of(JSON_ARBITRARIO.map(lambda v: {"dados": v}), RESULTADOS_REALISTAS))
def test_propriedade_ida_e_volta_resultados_json(resultados):
    """**Validates: Requirements 14.3**"""
    analise = carregar_analise()
    with tempfile.TemporaryDirectory() as pasta:
        destino = analise.gravar_json(resultados, Path(pasta) / "saida")
        assert destino == Path(pasta) / "saida" / analise.NOME_JSON
        lido = json.loads(destino.read_text(encoding="utf-8"))
    # == trata 0.0 e −0.0 como iguais; floats finitos voltam exatos (repr de ida e volta)
    assert lido == resultados
