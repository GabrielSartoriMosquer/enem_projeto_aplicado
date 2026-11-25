"""Rede escolar e estrutura das notas entre áreas (análise individual de Gabriel).

Compara escolas públicas e privadas no ENEM de 2018 a 2025 usando a gold de notas
(data/gold/enem_notas.parquet). As notas vêm da TRI e a escala muda a cada ano, então toda medida
é calculada dentro de uma mesma edição. Entre edições só entram medidas relativas (probabilidade
de superioridade, d de Cohen, percentil, razão de representação, perfil relativo e rankings).

As notas nunca são carregadas em Python: tudo que cresce com o número de participantes roda no
DuckDB, sempre por uma conexão de conectar(), que limita a memória em MEMORIA_DUCKDB (4 GB).
"""
import math
from fractions import Fraction
from statistics import NormalDist

from enem_pja3.config import ANOS, ANOS_FORMATO_ANTIGO
from enem_pja3.transform.transform import conectar

__all__ = [
    "AREAS", "AREAS_OBJETIVAS", "ANOS_FORMATO_NOVO", "COLUNAS_AREA", "COLUNAS_OBRIGATORIAS",
    "FILTRO_EDICAO", "GRUPOS_REDE", "LIMITE_ALERTA_COBERTURA_PP", "METODO_IC_AUC",
    "METODO_IC_COHEN_D", "METODO_IC_PERFIL", "METODO_IC_RAZAO", "PARES",
    "POSICOES_FEDERAL", "REDE_SQL", "REDES", "REDES_PUBLICAS", "SEM_REDE", "SEMENTE_PADRAO",
    "TAMANHO_MINIMO_GRUPO",
    "amostra_valida_sql", "anos_disponiveis", "cobertura", "cohen_d", "colunas_ausentes",
    "comparar_grupos", "conectar", "contar_inclusao", "criterios_inclusao", "estatisticas",
    "estatisticas_por_rede", "grupos_por_rede", "histograma", "ic_cohen_d",
    "ic_prob_superioridade", "ic_razao", "kendall_w", "mediana_percentil_por_rede",
    "nao_calculado", "percentil_lookup", "perfil_relativo", "perfil_relativo_medio",
    "posicao_federal", "processar", "processar_edicao",
    "prob_superioridade", "ranking_areas", "razao_representacao", "representacao_topo10",
    "somar_histogramas", "spearman", "taxa_preenchimento", "topo10", "valor_auc",
]

# As cinco provas. A redação não tem presença própria: conta a presença do dia de LC
AREAS = ("CN", "CH", "LC", "MT", "REDACAO")
AREAS_OBJETIVAS = ("CN", "CH", "LC", "MT")

# Colunas da gold que a análise lê. Se faltar alguma, o script para com mensagem (Requisito 17.2)
COLUNAS_OBRIGATORIAS = (
    "NU_ANO",
    "SG_UF_PROVA",
    "TP_DEPENDENCIA_ADM_ESC",
    "TP_PRESENCA_CN", "TP_PRESENCA_CH", "TP_PRESENCA_LC", "TP_PRESENCA_MT",
    "NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT",
    "NU_NOTA_REDACAO",
    "TP_STATUS_REDACAO",
    "IN_NOTA_ZERO",
)

# TP_DEPENDENCIA_ADM_ESC. Nulo ou outro valor = sem rede informada (fica fora das comparações)
REDES = {1: "federal", 2: "estadual", 3: "municipal", 4: "privada"}

# Redes que formam a rede pública (Requisito 2.2)
REDES_PUBLICAS = ("federal", "estadual", "municipal")

# Pares comparados (primeiro grupo × segundo). "publica" = federal + estadual + municipal
PARES = [
    ("privada", "publica"),
    ("privada", "federal"),
    ("privada", "estadual"),
    ("privada", "municipal"),
    ("federal", "estadual"),
]

# Grupo com menos participantes que isso não tem medida calculada (Requisito 5.6). Configurável
# pelo parâmetro min_grupo das funções e por --min-grupo no script
TAMANHO_MINIMO_GRUPO = 100

# Nome do método de cada intervalo de confiança, gravado junto do IC no resultados.json (Req 9.5)
METODO_IC_AUC = "hanley-mcneil"
METODO_IC_COHEN_D = "normal-aproximada (variancia de Hedges e Olkin)"
METODO_IC_RAZAO = "delta-log"


# ---------------------------------------------------------------------------------------------
# Histogramas
#
# Um histograma é um dict {nota_x10: contagem}: a nota multiplicada por 10 vira inteiro (as
# objetivas têm uma casa decimal e a redação é inteira), e a contagem é o número de participantes
# do grupo com aquela nota. Ele sai de um GROUP BY no DuckDB e tem no máximo ~10 mil chaves, então
# todo o cálculo abaixo é barato e não depende do número de participantes.
# ---------------------------------------------------------------------------------------------

def nao_calculado(motivo, n=None, **extra):
    """Registro de uma medida que não pôde ser calculada, com o motivo e o tamanho do grupo."""
    registro = {"calculado": False, "motivo": motivo}
    if n is not None:
        registro["n"] = n
    registro.update(extra)
    return registro


def somar_histogramas(*histogramas):
    """Soma histogramas valor a valor (por exemplo, a rede pública = federal + estadual + municipal)."""
    total = {}
    for hist in histogramas:
        for valor, contagem in hist.items():
            total[valor] = total.get(valor, 0) + contagem
    return total


def _tamanho(hist):
    return sum(hist.values())


def _estatisticas_de_somas(n, soma, soma_quadrados):
    """n, média e variância amostral a partir de n, Σv e Σv² (todos inteiros).

    É a mesma conta para os histogramas (estatisticas) e para as somas que vêm do DuckDB
    (estatisticas_por_rede), então os dois caminhos dão exatamente o mesmo resultado.
    """
    if n == 0:
        raise ValueError("histograma vazio: não há participantes no grupo")
    variancia = (n * soma_quadrados - soma * soma) / (n * (n - 1)) if n > 1 else 0.0
    return {"n": n, "media": soma / n, "variancia": variancia}


def estatisticas(hist):
    """n, média e variância amostral (divisor n − 1) de um histograma.

    As somas são feitas em inteiros, então a variância não sofre cancelamento numérico mesmo com
    milhões de participantes. Com n = 1 a variância é 0. As unidades são as das chaves do
    histograma (nota × 10); o d de Cohen não muda com a escala, então isso não altera o resultado.
    """
    n = _tamanho(hist)
    soma = sum(valor * contagem for valor, contagem in hist.items())
    soma_quadrados = sum(valor * valor * contagem for valor, contagem in hist.items())
    return _estatisticas_de_somas(n, soma, soma_quadrados)


# ---------------------------------------------------------------------------------------------
# Probabilidade de superioridade (Requisito 5) e IC de Hanley–McNeil (Requisito 9.1)
# ---------------------------------------------------------------------------------------------

def prob_superioridade(hist_a, hist_b):
    """P(nota de A > nota de B) + 0,5 · P(nota de A = nota de B), a partir dos histogramas.

    É o U de Mann–Whitney com meio-posto para empates dividido por nA · nB (a AUC). Percorre os
    valores distintos em ordem crescente acumulando quantos participantes de B ficaram abaixo:
        2U = Σ_v contagemA(v) · (2 · menores_B(v) + iguais_B(v))
    A conta é feita em inteiros (2U) e só a divisão final é em ponto flutuante, o que garante que
    AUC(A, B) + AUC(B, A) = 1 sem erro acumulado. Só a ordem das notas importa, então o valor não
    muda com transformações estritamente crescentes das notas.
    """
    n_a, n_b = _tamanho(hist_a), _tamanho(hist_b)
    if n_a == 0 or n_b == 0:
        raise ValueError("probabilidade de superioridade com grupo vazio")
    dois_u = 0
    menores_b = 0
    for valor in sorted(set(hist_a) | set(hist_b)):
        iguais_b = hist_b.get(valor, 0)
        dois_u += hist_a.get(valor, 0) * (2 * menores_b + iguais_b)
        menores_b += iguais_b
    return dois_u / (2 * n_a * n_b)


def _z(confianca):
    """Quantil da normal padrão para um IC bilateral (1,96 para 95%)."""
    return NormalDist().inv_cdf(0.5 + confianca / 2)


def ic_prob_superioridade(hist_a, hist_b, auc=None, confianca=0.95):
    """IC da probabilidade de superioridade pelo erro-padrão de Hanley e McNeil (1982).

    EP² = [θ(1 − θ) + (nA − 1)(Q1 − θ²) + (nB − 1)(Q2 − θ²)] / (nA · nB),
    com Q1 = θ / (2 − θ) e Q2 = 2θ² / (1 + θ). Os dois termos (Q − θ²) nunca são negativos para θ
    em [0, 1]. O intervalo é θ ± z · EP, cortado em [0, 1]; como θ está em [0, 1], sempre vale
    inferior ≤ θ ≤ superior. Devolve a tupla (inferior, superior).
    """
    n_a, n_b = _tamanho(hist_a), _tamanho(hist_b)
    theta = prob_superioridade(hist_a, hist_b) if auc is None else auc
    q1 = theta / (2 - theta)
    q2 = 2 * theta * theta / (1 + theta)
    variancia = (
        theta * (1 - theta) + (n_a - 1) * (q1 - theta * theta) + (n_b - 1) * (q2 - theta * theta)
    ) / (n_a * n_b)
    margem = _z(confianca) * math.sqrt(max(variancia, 0.0))
    return (max(0.0, theta - margem), min(1.0, theta + margem))


# ---------------------------------------------------------------------------------------------
# d de Cohen (Requisito 6) e IC pela variância aproximada (Requisito 9.2)
# ---------------------------------------------------------------------------------------------

def _desvio_combinado(stats_a, stats_b):
    """Desvio-padrão combinado: raiz de ((nA−1)varA + (nB−1)varB) / (nA + nB − 2)."""
    graus = stats_a["n"] + stats_b["n"] - 2
    if graus <= 0:
        return 0.0
    soma = (stats_a["n"] - 1) * stats_a["variancia"] + (stats_b["n"] - 1) * stats_b["variancia"]
    return math.sqrt(max(soma / graus, 0.0))


def cohen_d(stats_a, stats_b):
    """(média de A − média de B) / desvio-padrão combinado, ou None se o desvio combinado for 0.

    stats_a e stats_b são dicts com n, media e variancia (amostral). Trocar A e B só troca o sinal
    do numerador, e uma transformação afim com coeficiente positivo multiplica numerador e desvio
    pelo mesmo fator, então o d não muda.
    """
    desvio = _desvio_combinado(stats_a, stats_b)
    if desvio == 0:
        return None
    return (stats_a["media"] - stats_b["media"]) / desvio


def ic_cohen_d(stats_a, stats_b, d=None, confianca=0.95):
    """IC do d de Cohen pela variância aproximada usual (Hedges e Olkin, 1985).

    Var(d) = (nA + nB) / (nA · nB) + d² / (2 · (nA + nB)); o intervalo é d ± z · raiz(Var(d)).
    Devolve a tupla (inferior, superior), ou None quando o d não pode ser calculado.
    """
    if d is None:
        d = cohen_d(stats_a, stats_b)
        if d is None:
            return None
    n_a, n_b = stats_a["n"], stats_b["n"]
    variancia = (n_a + n_b) / (n_a * n_b) + d * d / (2 * (n_a + n_b))
    margem = _z(confianca) * math.sqrt(variancia)
    return (d - margem, d + margem)


# ---------------------------------------------------------------------------------------------
# Comparação de dois grupos com as regras de tamanho mínimo (Requisitos 5.6 e 6.4)
# ---------------------------------------------------------------------------------------------

def comparar_grupos(hist_a, hist_b, min_grupo=TAMANHO_MINIMO_GRUPO, stats_a=None, stats_b=None,
                    confianca=0.95):
    """Probabilidade de superioridade e d de Cohen de A em relação a B, prontos para o JSON.

    Se algum grupo tiver menos de min_grupo participantes (ou estiver vazio), devolve o registro de
    medida não calculada com o motivo e o tamanho do menor grupo. stats_a e stats_b podem vir de
    uma agregação do DuckDB (com as notas em pontos); se faltarem, saem dos histogramas. Se o
    desvio combinado for zero, só o d fica como não calculado, com o motivo.
    """
    n_a, n_b = _tamanho(hist_a), _tamanho(hist_b)
    menor = min(n_a, n_b)
    if menor == 0 or menor < min_grupo:
        return nao_calculado(
            f"grupo com {menor} participantes, abaixo do mínimo de {min_grupo}",
            n=menor, n_a=n_a, n_b=n_b,
        )

    auc = prob_superioridade(hist_a, hist_b)
    inferior, superior = ic_prob_superioridade(hist_a, hist_b, auc=auc, confianca=confianca)
    resultado = {
        "calculado": True,
        "n_a": n_a,
        "n_b": n_b,
        "prob_superioridade": {"valor": auc, "ic": [inferior, superior], "metodo": METODO_IC_AUC},
    }

    stats_a = estatisticas(hist_a) if stats_a is None else stats_a
    stats_b = estatisticas(hist_b) if stats_b is None else stats_b
    d = cohen_d(stats_a, stats_b)
    if d is None:
        resultado["cohen_d"] = nao_calculado("desvio-padrão combinado igual a zero", n=n_a + n_b)
    else:
        inferior, superior = ic_cohen_d(stats_a, stats_b, d=d, confianca=confianca)
        resultado["cohen_d"] = {"valor": d, "ic": [inferior, superior], "metodo": METODO_IC_COHEN_D}
    return resultado


# ---------------------------------------------------------------------------------------------
# Grupos por rede
#
# Os histogramas de uma edição e área chegam como {rede: {nota_x10: contagem}}, com as chaves
# "federal", "estadual", "municipal", "privada" e "sem_rede". Rede ausente no dict = sem
# participantes. A rede pública não vem pronta: é a soma de federal, estadual e municipal.
# ---------------------------------------------------------------------------------------------

def grupos_por_rede(histogramas):
    """Histogramas das quatro redes e da rede pública, sem os participantes sem rede informada."""
    grupos = {rede: dict(histogramas.get(rede, {})) for rede in REDES.values()}
    grupos["publica"] = somar_histogramas(*(grupos[rede] for rede in REDES_PUBLICAS))
    return grupos


def _amostra_valida(histogramas):
    """Histograma de toda a Amostra_Valida: as quatro redes mais os sem rede informada."""
    return somar_histogramas(*histogramas.values())


# ---------------------------------------------------------------------------------------------
# Percentil na edição (Requisito 7)
# ---------------------------------------------------------------------------------------------

def percentil_lookup(hist_total):
    """Tabela {nota_x10: percentil} com percentil(v) = 100 · (menores(v) + 0,5 · iguais(v)) / n.

    hist_total é o histograma de toda a Amostra_Valida da área (com e sem rede informada). O
    percentil fica sempre em [0, 100], cresce com a nota, e a média sobre todos os participantes é
    exatamente 50 (meio-posto para empates). A conta é feita em inteiros, como
    100 · (2 · menores + iguais) / (2n), e só a divisão final é em ponto flutuante.
    """
    n = _tamanho(hist_total)
    if n == 0:
        raise ValueError("histograma vazio: não há participantes na amostra")
    tabela = {}
    menores = 0
    for valor in sorted(hist_total):
        iguais = hist_total[valor]
        tabela[valor] = 100 * (2 * menores + iguais) / (2 * n)
        menores += iguais
    return tabela


def _valor_na_posicao(hist, posicao):
    """Nota de quem ocupa a posição dada (a partir de 0) quando o grupo é ordenado pela nota."""
    acumulado = 0
    for valor in sorted(hist):
        acumulado += hist[valor]
        if acumulado > posicao:
            return valor
    raise IndexError("posição fora do grupo")


def mediana_percentil_por_rede(histogramas, lookup=None, min_grupo=1):
    """Mediana do percentil na edição de cada rede e da rede pública (Requisito 7.5).

    O percentil de cada participante é o da Amostra_Valida inteira (lookup, que por padrão sai da
    soma de todos os histogramas, inclusive "sem_rede"). Com n par, a mediana é a média dos
    percentis dos dois participantes do meio. Rede com menos de min_grupo participantes (ou sem
    nenhum) fica como não calculada. Devolve {rede: mediana ou registro de não calculado}.
    """
    if lookup is None:
        lookup = percentil_lookup(_amostra_valida(histogramas))
    resultado = {}
    for rede, hist in grupos_por_rede(histogramas).items():
        n = _tamanho(hist)
        if n == 0 or n < min_grupo:
            resultado[rede] = nao_calculado(
                f"rede com {n} participantes, abaixo do mínimo de {max(min_grupo, 1)}", n=n
            )
            continue
        meio_baixo = lookup[_valor_na_posicao(hist, (n - 1) // 2)]
        meio_alto = lookup[_valor_na_posicao(hist, n // 2)]
        resultado[rede] = (meio_baixo + meio_alto) / 2
    return resultado


# ---------------------------------------------------------------------------------------------
# Topo_10 e razão de representação (Requisito 8) com IC pelo método delta no log (Requisito 9.3)
# ---------------------------------------------------------------------------------------------

def topo10(hist_total):
    """Nota de corte do Topo_10 e a proporção real da Amostra_Valida que ficou no topo.

    O corte é o percentil 90 discreto: a menor nota v com mais de 90% da amostra em notas ≤ v
    (em inteiros: 10 · acumulado(v) > 9 · n). Entram no Topo_10 todos com nota ≥ corte, então os
    empates na nota de corte entram juntos e a proporção real pode passar de 10% (nunca fica
    abaixo). Devolve {"corte": nota em pontos, "corte_x10", "n_topo", "n", "prop_real"}.
    """
    n = _tamanho(hist_total)
    if n == 0:
        raise ValueError("histograma vazio: não há participantes na amostra")
    acumulado = 0
    for valor in sorted(hist_total):
        acumulado += hist_total[valor]
        if 10 * acumulado > 9 * n:
            n_topo = n - (acumulado - hist_total[valor])
            return {
                "corte": valor / 10,
                "corte_x10": valor,
                "n_topo": n_topo,
                "n": n,
                "prop_real": n_topo / n,
            }
    raise AssertionError("inalcançável: o acumulado final é n e 10n > 9n")


def ic_razao(n_topo_rede, n_topo, n_rede, n_total, confianca=0.95):
    """IC da razão de representação pelo método delta no log da razão.

    Razão R = (n_topo_rede / n_topo) / (n_rede / n_total). Tratando as duas participações como
    proporções binomiais, Var(log p) ≈ (1 − p) / contagem, e
        Var(log R) ≈ (1 − p_topo) / n_topo_rede + (1 − p_todos) / n_rede.
    O Topo_10 é parte da amostra, então as duas proporções têm covariância positiva e ignorá-la
    deixa o IC um pouco mais largo (conservador). O intervalo é R · exp(±z · EP), o que mantém
    inferior ≤ R ≤ superior e o limite inferior positivo.

    Casos de borda: com n_topo_rede = 0 a razão é 0 e o log não existe; o limite inferior fica 0 e
    o superior sai da mesma fórmula com 0,5 participante no topo (correção de continuidade).
    Participação igual a 1 só zera o termo correspondente da variância. Exige n_rede > 0 e
    n_topo > 0. Devolve a tupla (inferior, superior).
    """
    if n_rede <= 0 or n_topo <= 0:
        raise ValueError("razão de representação sem participantes na rede ou no topo")
    z = _z(confianca)
    p_todos = n_rede / n_total
    razao = (n_topo_rede * n_total) / (n_topo * n_rede)
    if n_topo_rede == 0:
        # Correção de continuidade só para obter um limite superior finito
        p_topo = 0.5 / n_topo
        variancia = (1 - p_topo) / 0.5 + (1 - p_todos) / n_rede
        superior = (0.5 * n_total) / (n_topo * n_rede) * math.exp(z * math.sqrt(variancia))
        return (0.0, superior)
    p_topo = n_topo_rede / n_topo
    variancia = (1 - p_topo) / n_topo_rede + (1 - p_todos) / n_rede
    margem = z * math.sqrt(max(variancia, 0.0))
    # min/max só protegem contra arredondamento; em aritmética exata já vale a ordenação
    return (min(razao * math.exp(-margem), razao), max(razao * math.exp(margem), razao))


def _contar_a_partir(hist, corte_x10):
    """Quantos participantes do histograma têm nota ≥ corte."""
    return sum(contagem for valor, contagem in hist.items() if valor >= corte_x10)


def razao_representacao(histogramas, corte_x10, min_grupo=1, confianca=0.95):
    """Razão de representação no Topo_10 de cada rede e da rede pública (Requisito 8.1).

    Usa só participantes com rede informada: participação da rede no Topo_10 (nota ≥ corte) ÷
    participação da rede na Amostra_Valida. Em contagens, R = (t_rede · N) / (T · n_rede), com
    T e N somados sobre as quatro redes; por isso Σ (n_rede / N) · R = Σ t_rede / T = 1 sobre as
    quatro redes. Cada razão é calculada com uma única divisão de inteiros, sem erro acumulado.

    Rede com menos de min_grupo participantes (por padrão, só a rede vazia) fica como não
    calculada (Requisito 8.5). Se ninguém com rede informada estiver no topo, todas ficam como
    não calculadas. Devolve {rede: {"razao", "ic", "metodo", "n", "n_topo",
    "participacao_todos", "participacao_topo", "calculado"} ou registro de não calculado}.
    """
    grupos = grupos_por_rede(histogramas)
    n_rede = {rede: _tamanho(hist) for rede, hist in grupos.items()}
    t_rede = {rede: _contar_a_partir(hist, corte_x10) for rede, hist in grupos.items()}
    n_total = sum(n_rede[rede] for rede in REDES.values())
    n_topo = sum(t_rede[rede] for rede in REDES.values())

    resultado = {}
    for rede in grupos:
        n, t = n_rede[rede], t_rede[rede]
        if n == 0 or n < min_grupo:
            resultado[rede] = nao_calculado(
                f"rede com {n} participantes com rede informada, abaixo do mínimo de "
                f"{max(min_grupo, 1)}",
                n=n,
            )
            continue
        if n_topo == 0:
            resultado[rede] = nao_calculado(
                "nenhum participante com rede informada no Topo_10", n=n
            )
            continue
        inferior, superior = ic_razao(t, n_topo, n, n_total, confianca=confianca)
        resultado[rede] = {
            "calculado": True,
            "razao": (t * n_total) / (n_topo * n),
            "ic": [inferior, superior],
            "metodo": METODO_IC_RAZAO,
            "n": n,
            "n_topo": t,
            "participacao_todos": n / n_total,
            "participacao_topo": t / n_topo,
        }
    return resultado


def representacao_topo10(histogramas, min_grupo=1, confianca=0.95):
    """Corte do Topo_10, proporção real e razão por rede, no formato do resultados.json.

    O corte sai da Amostra_Valida inteira (inclusive os sem rede informada); a razão usa só quem
    tem rede informada. Devolve {"corte", "prop_real", "n_topo", "n", "por_rede": {...}}.
    """
    topo = topo10(_amostra_valida(histogramas))
    return {
        "corte": topo["corte"],
        "prop_real": topo["prop_real"],
        "n_topo": topo["n_topo"],
        "n": topo["n"],
        "por_rede": razao_representacao(
            histogramas, topo["corte_x10"], min_grupo=min_grupo, confianca=confianca
        ),
    }


# ---------------------------------------------------------------------------------------------
# Ranking das áreas (Requisito 10.1) e estabilidade entre edições (Requisitos 10.2 e 10.3)
#
# Os rankings são pequenos (no máximo 5 áreas × 8 edições), então tudo aqui é Python puro. As
# contas são feitas em inteiros e só a divisão final é em ponto flutuante: com rankings idênticos
# o W de Kendall dá exatamente 1.
# ---------------------------------------------------------------------------------------------

def valor_auc(registro):
    """AUC de um registro de comparação, ou None se a medida não foi calculada.

    Aceita um número (a própria AUC), None, ou o dict de comparar_grupos (lê
    prob_superioridade.valor quando calculado é verdadeiro).
    """
    if registro is None:
        return None
    if isinstance(registro, dict):
        if not registro.get("calculado", False):
            return None
        return registro["prob_superioridade"]["valor"]
    return float(registro)


def ranking_areas(aucs):
    """Áreas em ordem decrescente da AUC da rede privada sobre a rede pública.

    aucs é um dict {area: AUC}, em que cada valor pode ser um número, None ou o registro de
    comparar_grupos. Também aceita o dict de comparações de uma edição inteira: se tiver a chave
    "privada_vs_publica", usa o que está nela. Áreas com a AUC não calculada (None ou
    calculado = False) ficam fora do ranking, então ele pode ter menos de cinco áreas. Empates na
    AUC seguem a ordem de AREAS (CN, CH, LC, MT, REDACAO), para o resultado ser determinístico.
    Devolve a lista de áreas, da maior AUC para a menor.
    """
    if "privada_vs_publica" in aucs:
        aucs = aucs["privada_vs_publica"]
    desconhecidas = set(aucs) - set(AREAS)
    if desconhecidas:
        raise ValueError(f"áreas desconhecidas no ranking: {sorted(desconhecidas)}")
    valores = {}
    for area in AREAS:
        if area in aucs:
            valor = valor_auc(aucs[area])
            if valor is not None:
                valores[area] = valor
    return sorted(valores, key=lambda area: (-valores[area], AREAS.index(area)))


def _itens_comuns(rankings):
    """Itens presentes em todos os rankings, na ordem do primeiro ranking."""
    comuns = set(rankings[0]).intersection(*rankings[1:])
    return [item for item in rankings[0] if item in comuns]


def _posicoes(ranking, itens):
    """Posição (1 = primeiro) de cada item do ranking, contando só os itens dados."""
    escolhidos = set(itens)
    filtrado = [item for item in ranking if item in escolhidos]
    return {item: posicao for posicao, item in enumerate(filtrado, start=1)}


def _validar_ranking(ranking):
    if len(set(ranking)) != len(ranking):
        raise ValueError(f"ranking com item repetido: {list(ranking)}")


def kendall_w(rankings):
    """Coeficiente de concordância W de Kendall entre rankings (sem empates).

    rankings é uma lista de rankings, cada um uma sequência de itens do primeiro ao último (como
    sai de ranking_areas). Com m rankings e n itens, R_i é a soma das posições do item i e
        W = 12 · S / (m² · (n³ − n)),  S = Σ_i (R_i − m(n + 1)/2)².
    Em inteiros: 4S = Σ_i (2R_i − m(n + 1))² e W = 3 · 4S / (m² · (n³ − n)).

    Se os rankings não tiverem os mesmos itens (por exemplo, uma área sem AUC numa edição), o W
    usa só os itens presentes em todos, com as posições renumeradas entre eles. Devolve None
    quando não há ranking ou quando sobram menos de 2 itens em comum (o W não é definido). Com um
    único ranking, a fórmula dá 1. O resultado é cortado em [0, 1] por segurança.
    """
    rankings = [list(ranking) for ranking in rankings]
    if not rankings:
        return None
    for ranking in rankings:
        _validar_ranking(ranking)
    itens = _itens_comuns(rankings)
    n, m = len(itens), len(rankings)
    if n < 2:
        return None
    somas = {item: 0 for item in itens}
    for ranking in rankings:
        for item, posicao in _posicoes(ranking, itens).items():
            somas[item] += posicao
    quatro_s = sum((2 * soma - m * (n + 1)) ** 2 for soma in somas.values())
    w = 3 * quatro_s / (m * m * (n ** 3 - n))
    return min(1.0, max(0.0, w))


def spearman(rank_a, rank_b):
    """Correlação de Spearman entre dois rankings sem empates.

    rho = 1 − 6 · Σ d² / (n · (n² − 1)), com d a diferença de posição de cada item. Como em
    kendall_w, só entram os itens presentes nos dois rankings, com as posições renumeradas.
    Devolve None quando há menos de 2 itens em comum. O resultado fica em [−1, 1].
    """
    rank_a, rank_b = list(rank_a), list(rank_b)
    _validar_ranking(rank_a)
    _validar_ranking(rank_b)
    itens = _itens_comuns([rank_a, rank_b])
    n = len(itens)
    if n < 2:
        return None
    pos_a, pos_b = _posicoes(rank_a, itens), _posicoes(rank_b, itens)
    soma_d2 = sum((pos_a[item] - pos_b[item]) ** 2 for item in itens)
    rho = 1 - 6 * soma_d2 / (n * (n * n - 1))
    return min(1.0, max(-1.0, rho))


# ---------------------------------------------------------------------------------------------
# Perfil relativo de um participante (Requisito 11.2 e 11.3)
# ---------------------------------------------------------------------------------------------

def perfil_relativo(percentis):
    """Percentil de cada área menos a média dos cinco percentis do participante.

    percentis é um dict {area: percentil} com as cinco áreas de AREAS ou uma sequência de cinco
    percentis na ordem de AREAS. Devolve o mesmo formato da entrada (dict na ordem de AREAS ou
    lista). A média usa math.fsum, então a soma dos componentes é 0 e um perfil uniforme dá cinco
    zeros, a menos de arredondamento da ordem de 1e-13. A agregação por rede (média e IC de cada
    componente) roda no DuckDB, no passo 4.2, com a mesma fórmula.
    """
    if isinstance(percentis, dict):
        if set(percentis) != set(AREAS):
            raise ValueError(f"o perfil relativo precisa das cinco áreas {AREAS}")
        valores = [percentis[area] for area in AREAS]
    else:
        valores = list(percentis)
        if len(valores) != len(AREAS):
            raise ValueError(f"o perfil relativo precisa de {len(AREAS)} percentis")
    media = math.fsum(valores) / len(valores)
    componentes = [valor - media for valor in valores]
    if isinstance(percentis, dict):
        return dict(zip(AREAS, componentes))
    return componentes


# ---------------------------------------------------------------------------------------------
# Posição da rede federal (Requisito 12)
# ---------------------------------------------------------------------------------------------

POSICOES_FEDERAL = ("mais_proxima_da_privada", "mais_proxima_da_estadual", "equidistante")


def posicao_federal(auc_federal_privada, auc_federal_estadual, tolerancia=1e-12):
    """Classifica a federal como mais próxima da privada, da estadual ou equidistante.

    Recebe AUC(federal, privada) e AUC(federal, estadual), como número, None ou registro de
    comparar_grupos. Atenção: PARES guarda o par ("privada", "federal"), então quem chama deve
    passar AUC(federal, privada) = 1 − AUC(privada, federal). O par ("federal", "estadual") já
    está na ordem certa. As distâncias são |AUC − 0,5| (Requisitos 12.1 e 12.2); a menor decide a
    classificação, e diferença até `tolerancia` conta como empate ("equidistante"), para absorver
    o arredondamento do 1 − AUC.

    Devolve {"calculado": True, "classificacao", "distancia_privada", "distancia_estadual"}, ou o
    registro de não calculado quando alguma das duas AUC não foi calculada.
    """
    auc_privada = valor_auc(auc_federal_privada)
    auc_estadual = valor_auc(auc_federal_estadual)
    faltando = [
        nome for nome, valor in (("federal × privada", auc_privada),
                                 ("federal × estadual", auc_estadual))
        if valor is None
    ]
    if faltando:
        return nao_calculado(f"AUC não calculada para {' e '.join(faltando)}")
    distancia_privada = abs(auc_privada - 0.5)
    distancia_estadual = abs(auc_estadual - 0.5)
    if abs(distancia_privada - distancia_estadual) <= tolerancia:
        classificacao = "equidistante"
    elif distancia_privada < distancia_estadual:
        classificacao = "mais_proxima_da_privada"
    else:
        classificacao = "mais_proxima_da_estadual"
    return {
        "calculado": True,
        "classificacao": classificacao,
        "distancia_privada": distancia_privada,
        "distancia_estadual": distancia_estadual,
    }


# ---------------------------------------------------------------------------------------------
# Consultas à gold (DuckDB): inclusão, rede escolar, histogramas e cobertura (Requisitos 1 a 3)
#
# Todas as consultas recebem a conexão de conectar() (limite de memória MEMORIA_DUCKDB, Requisito
# 17.5) e devolvem só agregados: contagens por critério, por rede ou por (rede, nota). Nenhuma
# linha da gold vem para o Python. O caminho da gold e o ano entram como parâmetros da consulta
# ($gold e $ano); nomes de colunas e de áreas saem só das constantes deste módulo.
# ---------------------------------------------------------------------------------------------

# Grupo dos participantes sem rede informada (TP_DEPENDENCIA_ADM_ESC nulo ou fora de 1 a 4)
SEM_REDE = "sem_rede"

# Chaves dos histogramas e das contagens por rede, sempre nesta ordem
GRUPOS_REDE = tuple(REDES.values()) + (SEM_REDE,)

# Coluna da nota e coluna de presença de cada área. A redação usa a presença do dia de LC
COLUNAS_AREA = {
    "CN": ("NU_NOTA_CN", "TP_PRESENCA_CN"),
    "CH": ("NU_NOTA_CH", "TP_PRESENCA_CH"),
    "LC": ("NU_NOTA_LC", "TP_PRESENCA_LC"),
    "MT": ("NU_NOTA_MT", "TP_PRESENCA_MT"),
    "REDACAO": ("NU_NOTA_REDACAO", "TP_PRESENCA_LC"),
}

# Filtro da edição (Requisito 1.4): toda consulta usa só as linhas do ano pedido
FILTRO_EDICAO = "NU_ANO = $ano"

# Classificação da rede escolar (Requisitos 2.1 e 2.3): nulo ou outro código vira "sem_rede"
REDE_SQL = (
    "CASE TP_DEPENDENCIA_ADM_ESC "
    + " ".join(f"WHEN {codigo} THEN '{rede}'" for codigo, rede in REDES.items())
    + f" ELSE '{SEM_REDE}' END"
)


def _colunas_area(area):
    """(coluna da nota, coluna de presença) da área; área fora de AREAS é erro."""
    if area not in COLUNAS_AREA:
        raise ValueError(f"área desconhecida: {area!r}; use uma de {AREAS}")
    return COLUNAS_AREA[area]


def _nota_x10_sql(area):
    """Nota da área × 10 como inteiro, a mesma chave dos histogramas.

    As objetivas são DECIMAL(5,1) e a redação é SMALLINT, então nota × 10 já é inteira; o round
    só deixa explícito que não há truncamento se a coluna vier em ponto flutuante.
    """
    nota, _ = _colunas_area(area)
    return f"CAST(round({nota} * 10) AS BIGINT)"


def criterios_inclusao(area):
    """Critérios de inclusão da área (Requisitos 1.1 e 1.2), na ordem em que são aplicados.

    Devolve uma lista de (nome, predicado SQL). Cada predicado é verdadeiro para quem fica na
    amostra e nunca é nulo (por isso o IS TRUE / IS FALSE), o que permite contar as exclusões com
    NOT. Os nomes são as chaves de "excluidos" em contar_inclusao:
      - presenca: presença igual a 1 na área (na redação, TP_PRESENCA_LC igual a 1);
      - status_redacao (só na redação): TP_STATUS_REDACAO igual a 1;
      - nota_nula: nota da área não nula;
      - nota_zero: IN_NOTA_ZERO falso (verdadeiro ou nulo exclui; a gold nunca grava nulo).
    """
    nota, presenca = _colunas_area(area)
    criterios = [("presenca", f"({presenca} = 1) IS TRUE")]
    if area == "REDACAO":
        criterios.append(("status_redacao", "(TP_STATUS_REDACAO = 1) IS TRUE"))
    criterios.append(("nota_nula", f"{nota} IS NOT NULL"))
    criterios.append(("nota_zero", "IN_NOTA_ZERO IS FALSE"))
    return criterios


def amostra_valida_sql(area):
    """Predicado SQL da Amostra_Valida da área: filtro da edição e critérios de inclusão.

    O ano não vai no texto: o predicado usa o parâmetro $ano, que a consulta recebe junto com
    $gold (ver _consultar). Assim o valor nunca é interpolado no SQL.
    """
    return " AND ".join([FILTRO_EDICAO] + [predicado for _, predicado in criterios_inclusao(area)])


def _consultar(con, sql, gold, ano=None):
    """Executa a consulta com $gold (e $ano, se dado) como parâmetros e devolve todas as linhas."""
    parametros = {"gold": str(gold)}
    if ano is not None:
        parametros["ano"] = int(ano)
    return con.execute(sql, parametros).fetchall()


def colunas_ausentes(con, gold):
    """Colunas de COLUNAS_OBRIGATORIAS que não existem na gold, na ordem da constante.

    Lê só o esquema do Parquet (LIMIT 0). Lista vazia = a gold tem tudo que a análise usa.
    """
    cursor = con.execute("SELECT * FROM read_parquet($gold) LIMIT 0", {"gold": str(gold)})
    presentes = {descricao[0] for descricao in cursor.description}
    return [coluna for coluna in COLUNAS_OBRIGATORIAS if coluna not in presentes]


def anos_disponiveis(con, gold):
    """Edições (NU_ANO) com pelo menos uma linha na gold, em ordem crescente."""
    linhas = _consultar(
        con,
        "SELECT DISTINCT NU_ANO FROM read_parquet($gold) WHERE NU_ANO IS NOT NULL ORDER BY NU_ANO",
        gold,
    )
    return [int(ano) for (ano,) in linhas]


def contar_inclusao(con, gold, ano, area):
    """Total da edição, excluídos por critério e tamanho da Amostra_Valida (Requisito 1.3).

    As exclusões são contadas em cascata, na ordem de criterios_inclusao: cada participante é
    contado só no primeiro critério que não atende. Por isso
        total = soma de excluidos + amostra_valida.
    Devolve {"total": int, "excluidos": {critério: int}, "amostra_valida": int}. Edição sem
    linhas dá tudo zero.
    """
    criterios = criterios_inclusao(area)
    colunas, anteriores = [], []
    for nome, predicado in criterios:
        condicao = " AND ".join(anteriores + [f"NOT ({predicado})"])
        colunas.append(f"count(*) FILTER (WHERE {condicao}) AS {nome}")
        anteriores.append(f"({predicado})")
    colunas.append(f"count(*) FILTER (WHERE {' AND '.join(anteriores)}) AS amostra_valida")
    sql = f"""
        SELECT count(*) AS total, {', '.join(colunas)}
        FROM read_parquet($gold)
        WHERE {FILTRO_EDICAO}
    """
    total, *excluidos, amostra = _consultar(con, sql, gold, ano)[0]
    return {
        "total": int(total),
        "excluidos": {nome: int(n) for (nome, _), n in zip(criterios, excluidos)},
        "amostra_valida": int(amostra),
    }


def histograma(con, gold, ano, area):
    """Histogramas da Amostra_Valida por rede: {rede: {nota_x10: contagem}}.

    Sai de um COUNT(*) por (rede, nota × 10) no DuckDB. Sempre traz as cinco chaves de
    GRUPOS_REDE ("federal", "estadual", "municipal", "privada", "sem_rede"); grupo sem
    participantes fica com {}. As notas de cada rede ficam em ordem crescente. A rede pública não
    vem pronta: é a soma de federal, estadual e municipal (grupos_por_rede).
    """
    sql = f"""
        SELECT {REDE_SQL} AS rede, {_nota_x10_sql(area)} AS nota_x10, count(*) AS contagem
        FROM read_parquet($gold)
        WHERE {amostra_valida_sql(area)}
        GROUP BY ALL
        ORDER BY rede, nota_x10
    """
    resultado = {grupo: {} for grupo in GRUPOS_REDE}
    for rede, nota_x10, contagem in _consultar(con, sql, gold, ano):
        resultado[rede][int(nota_x10)] = int(contagem)
    return resultado


def estatisticas_por_rede(con, gold, ano, area):
    """n, média e variância amostral da nota × 10 de cada rede e da rede pública.

    O DuckDB devolve, por rede, n, Σv e Σv² em inteiros (v = nota × 10); a média e a variância
    saem de _estatisticas_de_somas, a mesma conta de estatisticas(hist). Então o resultado é
    exatamente o de estatisticas(histograma(...)[rede]) (mesmas unidades, divisor n − 1, variância
    0 com n = 1) e não depende da ordem das linhas. A rede pública soma as somas de federal,
    estadual e municipal. Grupo sem participantes fica fora do dict.

    Devolve {grupo: {"n", "media", "variancia"}} com grupos entre GRUPOS_REDE e "publica", no
    formato que comparar_grupos aceita em stats_a e stats_b.
    """
    nota_x10 = _nota_x10_sql(area)
    sql = f"""
        SELECT {REDE_SQL} AS rede, count(*) AS n, sum({nota_x10}) AS soma,
               sum({nota_x10} * {nota_x10}) AS soma_quadrados
        FROM read_parquet($gold)
        WHERE {amostra_valida_sql(area)}
        GROUP BY ALL
        ORDER BY rede
    """
    somas = {rede: (int(n), int(soma), int(soma_q))
             for rede, n, soma, soma_q in _consultar(con, sql, gold, ano)}
    publica = [somas[rede] for rede in REDES_PUBLICAS if rede in somas]
    if publica:
        somas["publica"] = tuple(sum(parte) for parte in zip(*publica))
    ordem = GRUPOS_REDE + ("publica",)
    return {grupo: _estatisticas_de_somas(*somas[grupo]) for grupo in ordem if grupo in somas}


def cobertura(con, gold, ano, area):
    """Taxa_de_Preenchimento e distribuição da Amostra_Valida por rede (Requisitos 3.1 e 3.2).

    Devolve {"n": tamanho da Amostra_Valida, "n_rede_informada": int,
    "taxa_preenchimento": n_rede_informada / n, "por_rede": {grupo: {"n", "proporcao"}}}, com as
    cinco chaves de GRUPOS_REDE em por_rede (proporção sobre toda a Amostra_Valida, inclusive os
    sem rede). Com a Amostra_Valida vazia, a taxa e as proporções ficam None (não há denominador).
    """
    sql = f"""
        SELECT {REDE_SQL} AS rede, count(*) AS n
        FROM read_parquet($gold)
        WHERE {amostra_valida_sql(area)}
        GROUP BY ALL
        ORDER BY rede
    """
    contagens = {grupo: 0 for grupo in GRUPOS_REDE}
    for rede, n in _consultar(con, sql, gold, ano):
        contagens[rede] = int(n)
    return _cobertura_de_contagens(contagens)


def _cobertura_de_contagens(contagens):
    """Registro de cobertura a partir de {grupo: n} com as cinco chaves de GRUPOS_REDE.

    Mesma conta para a consulta de cobertura() e para os totais dos histogramas (processar_edicao),
    então os dois caminhos dão exatamente o mesmo registro.
    """
    n_total = sum(contagens.values())
    n_informada = n_total - contagens[SEM_REDE]
    return {
        "n": n_total,
        "n_rede_informada": n_informada,
        "taxa_preenchimento": n_informada / n_total if n_total else None,
        "por_rede": {
            grupo: {"n": n, "proporcao": n / n_total if n_total else None}
            for grupo, n in contagens.items()
        },
    }


def taxa_preenchimento(con, gold, ano, area):
    """Proporção da Amostra_Valida da área com rede informada, ou None se a amostra é vazia."""
    return cobertura(con, gold, ano, area)["taxa_preenchimento"]


# ---------------------------------------------------------------------------------------------
# Perfil relativo médio por rede (Requisito 11) com IC de cada componente (Requisito 9.4)
#
# O percentil de um participante numa área é o da Amostra_Valida daquela área (Requisito 11.6),
# 100 · (2 · menores + iguais) / (2 · n_area), exatamente o de percentil_lookup. No DuckDB, cada
# área ganha uma tabela de lookup nota_x10 → posto r = 2 · menores + iguais (inteiro), e cada
# participante da Amostra_Completa (válido nas cinco áreas) recebe os cinco postos por junção.
#
# O perfil é linear nos postos: componente_a = Σ_b (δ_ab − 1/5) · (50 / n_b) · r_b. Então basta o
# DuckDB devolver, por rede, n, Σ r_b e Σ r_b · r_c: somas de inteiros, exatas e independentes da
# ordem das linhas. A média e a variância de cada componente saem dessas somas em frações exatas
# (Fraction) e só o resultado final vira float. Nenhuma linha da gold vem para o Python.
# ---------------------------------------------------------------------------------------------

METODO_IC_PERFIL = "normal (media ± z·dp/raiz(n))"

# Grupos do perfil relativo médio, nesta ordem: as quatro redes e a rede pública
_GRUPOS_PERFIL = tuple(REDES.values()) + ("publica",)


def _pares_de_areas():
    """Pares (b, c) de áreas com b antes ou igual a c, para as somas Σ r_b · r_c."""
    return [(b, c) for i, b in enumerate(AREAS) for c in AREAS[i:]]


def _somas_perfil_sql():
    """Consulta das somas de postos por rede sobre a Amostra_Completa da edição ($gold, $ano)."""
    lookups = ",\n".join(
        f"""
        lookup_{area} AS (
            SELECT nota_x10,
                   CAST(2 * (sum(contagem) OVER (ORDER BY nota_x10) - contagem) + contagem
                        AS BIGINT) AS r
            FROM (
                SELECT {_nota_x10_sql(area)} AS nota_x10, count(*) AS contagem
                FROM read_parquet($gold)
                WHERE {amostra_valida_sql(area)}
                GROUP BY ALL
            )
        )"""
        for area in AREAS
    )
    notas = ", ".join(f"{_nota_x10_sql(area)} AS v_{area}" for area in AREAS)
    completa = " AND ".join(f"({amostra_valida_sql(area)})" for area in AREAS)
    postos = ", ".join(f"l_{area}.r AS r_{area}" for area in AREAS)
    juncoes = "\n".join(
        f"JOIN lookup_{area} AS l_{area} ON c.v_{area} = l_{area}.nota_x10" for area in AREAS
    )
    somas = ", ".join(f"sum(r_{area}) AS s_{area}" for area in AREAS)
    produtos = ", ".join(f"sum(r_{b} * r_{c}) AS q_{b}_{c}" for b, c in _pares_de_areas())
    return f"""
        WITH {lookups},
        completa AS (
            SELECT {REDE_SQL} AS rede, {notas}
            FROM read_parquet($gold)
            WHERE {completa}
        ),
        postos AS (
            SELECT c.rede, {postos}
            FROM completa AS c
            {juncoes}
        )
        SELECT rede, count(*) AS n, {somas}, {produtos}
        FROM postos
        GROUP BY rede
        ORDER BY rede
    """


def _tamanhos_amostra_valida(con, gold, ano):
    """Tamanho da Amostra_Valida de cada área na edição: {area: n}."""
    colunas = ", ".join(
        f"count(*) FILTER (WHERE {amostra_valida_sql(area)}) AS n_{area}" for area in AREAS
    )
    sql = f"SELECT {colunas} FROM read_parquet($gold) WHERE {FILTRO_EDICAO}"
    linha = _consultar(con, sql, gold, ano)[0]
    return {area: int(n) for area, n in zip(AREAS, linha)}


def _componentes_perfil(n, somas, produtos, n_area, z):
    """Média, IC e médias exatas de cada componente a partir das somas de postos de um grupo.

    somas = {b: Σ r_b} e produtos = {(b, c): Σ r_b · r_c} (com as duas ordens do par). Com
    k_ab = (δ_ab − 1/5) · 50 / n_b, o componente a de um participante é Σ_b k_ab · r_b, então
        média_a = Σ_b k_ab · S_b / n   e   Σ componente_a² = Σ_b Σ_c k_ab · k_ac · Q_bc.
    A variância amostral (divisor n − 1, 0 com n = 1) é exata e nunca negativa; o IC é
    média ± z · dp / raiz(n), então sempre inferior ≤ média ≤ superior.
    """
    peso = Fraction(1, len(AREAS))
    componentes, exatas = {}, {}
    for a in AREAS:
        k = {b: (Fraction(int(a == b)) - peso) * Fraction(50, n_area[b]) for b in AREAS}
        media = sum(k[b] * somas[b] for b in AREAS) / n
        soma_quadrados = sum(k[b] * k[c] * produtos[(b, c)] for b in AREAS for c in AREAS)
        variancia = (soma_quadrados - n * media * media) / (n - 1) if n > 1 else Fraction(0)
        valor = float(media)
        margem = z * math.sqrt(float(variancia) / n)
        componentes[a] = {"valor": valor, "ic": [valor - margem, valor + margem],
                          "metodo": METODO_IC_PERFIL}
        exatas[a] = media
    return componentes, exatas


def perfil_relativo_medio(con, gold, ano, min_grupo=TAMANHO_MINIMO_GRUPO, confianca=0.95):
    """Perfil relativo médio de cada rede e da rede pública na edição (Requisitos 11.1 a 11.6).

    Usa a Amostra_Completa da edição (participantes válidos nas cinco áreas, pelos critérios de
    criterios_inclusao); o percentil de cada área é o da Amostra_Valida da área inteira, com e sem
    rede informada. Os sem rede informada entram no cálculo dos percentis, mas não têm perfil
    médio próprio. A rede pública soma federal, estadual e municipal.

    Devolve {grupo: registro} para os grupos "federal", "estadual", "municipal", "privada" e
    "publica", nesta ordem. Registro calculado:
        {"calculado": True, "n": participantes do grupo na Amostra_Completa,
         "CN": {"valor", "ic": [inferior, superior], "metodo"}, ... (as cinco áreas de AREAS),
         "area_maior": área com o maior componente médio, "area_menor": com o menor}
    Os componentes estão em pontos de percentil e somam 0. Empates em area_maior ou area_menor
    ficam com a primeira área na ordem de AREAS. Grupo com menos de min_grupo participantes (ou
    vazio) vira o registro de nao_calculado com o motivo e n.
    """
    n_area = _tamanhos_amostra_valida(con, gold, ano)
    pares = _pares_de_areas()
    somas_por_rede = {}
    for linha in _consultar(con, _somas_perfil_sql(), gold, ano):
        rede, n, *resto = linha
        somas = [int(valor) for valor in resto[:len(AREAS)]]
        produtos = [int(valor) for valor in resto[len(AREAS):]]
        somas_por_rede[rede] = (int(n), somas, produtos)

    vazio = (0, [0] * len(AREAS), [0] * len(pares))
    agregados = {rede: somas_por_rede.get(rede, vazio) for rede in REDES.values()}
    publicas = [agregados[rede] for rede in REDES_PUBLICAS]
    agregados["publica"] = (
        sum(parte[0] for parte in publicas),
        [sum(valores) for valores in zip(*(parte[1] for parte in publicas))],
        [sum(valores) for valores in zip(*(parte[2] for parte in publicas))],
    )

    z = _z(confianca)
    resultado = {}
    for grupo in _GRUPOS_PERFIL:
        n, lista_somas, lista_produtos = agregados[grupo]
        if n == 0 or n < min_grupo:
            resultado[grupo] = nao_calculado(
                f"rede com {n} participantes na Amostra_Completa, abaixo do mínimo de "
                f"{max(min_grupo, 1)}",
                n=n,
            )
            continue
        somas = dict(zip(AREAS, lista_somas))
        produtos = {}
        for (b, c), valor in zip(pares, lista_produtos):
            produtos[(b, c)] = produtos[(c, b)] = valor
        componentes, exatas = _componentes_perfil(n, somas, produtos, n_area, z)
        resultado[grupo] = {
            "calculado": True,
            "n": n,
            **componentes,
            "area_maior": max(AREAS, key=lambda area: exatas[area]),
            "area_menor": min(AREAS, key=lambda area: exatas[area]),
        }
    return resultado


# ---------------------------------------------------------------------------------------------
# Montagem dos resultados: uma edição (processar_edicao) e todas as pedidas (processar)
#
# Por edição e área, a gold é lida duas vezes: contar_inclusao (exclusões por critério) e
# histograma (contagens por rede e nota). Cobertura, estatísticas, comparações, percentis e
# Topo_10 saem do histograma em Python, com as mesmas contas exatas de cobertura() e
# estatisticas_por_rede(). O perfil relativo médio faz a própria consulta, uma vez por edição.
# As chaves das edições são texto ("2018"), como ficam no resultados.json depois da ida e volta.
# ---------------------------------------------------------------------------------------------

# Edições do formato novo (perfil e nota em arquivos separados): 2024 e 2025
ANOS_FORMATO_NOVO = tuple(ano for ano in ANOS if ano not in ANOS_FORMATO_ANTIGO)

# Diferença de cobertura entre os formatos, em pontos percentuais, acima da qual há alerta (Req 3.4)
LIMITE_ALERTA_COBERTURA_PP = 5.0

# Semente registrada nos parâmetros (Requisito 9.6). Os ICs atuais são analíticos e não a usam
SEMENTE_PADRAO = 42


def _chave_par(par):
    """Chave do par em "comparacoes": ("privada", "publica") → "privada_vs_publica"."""
    return f"{par[0]}_vs_{par[1]}"


def _motivo_sem_comparacao(registro_cobertura):
    """Motivo para não comparar redes na área (amostra vazia ou taxa zero), ou None (Req 17.4)."""
    taxa = registro_cobertura["taxa_preenchimento"]
    if taxa is None:
        return "amostra válida vazia na edição e área"
    if taxa == 0:
        return "taxa de preenchimento igual a zero: nenhum participante com rede informada"
    return None


def _medias_em_pontos(grupos, stats, min_grupo):
    """Média da nota em pontos (média de nota × 10 dividida por 10) de cada rede e da pública.

    Valor na escala da TRI da edição: só entra na tabela por edição do relatório (Req 4.3).
    """
    medias = {}
    for grupo, hist in grupos.items():
        n = _tamanho(hist)
        if n == 0 or n < min_grupo:
            medias[grupo] = nao_calculado(
                f"rede com {n} participantes, abaixo do mínimo de {max(min_grupo, 1)}", n=n
            )
        else:
            medias[grupo] = stats[grupo]["media"] / 10
    return medias


def processar_edicao(con, gold, ano, min_grupo=TAMANHO_MINIMO_GRUPO):
    """Todas as medidas de uma edição, no formato de resultados["edicoes"]["AAAA"].

    Para cada área: inclusão (Req 1.3), cobertura (Req 3.1 e 3.2), os cinco pares de PARES com a
    rede pública = federal + estadual + municipal (Req 2.4), percentil mediano por rede (Req 7.5),
    Topo_10 e razão de representação (Req 8), médias em pontos e posição da federal (Req 12).
    Depois, o ranking das áreas (Req 10.1) e o perfil relativo médio (Req 11).

    Área com a amostra válida vazia tem todas as medidas como não calculadas. Área com taxa de
    preenchimento zero tem as comparações entre redes como não calculadas, com o motivo (Req
    17.4); percentis, razões e médias por rede também ficam sem valor, porque as redes estão
    vazias. Os dois casos geram um alerta da edição. Devolve só tipos de JSON (dicts com chaves
    texto, listas, números finitos, texto, bool e None).
    """
    comparacoes = {_chave_par(par): {} for par in PARES}
    edicao = {
        "inclusao": {},
        "cobertura": {},
        "comparacoes": comparacoes,
        "percentil_mediano": {},
        "representacao_topo10": {},
        "medias": {},
        "ranking_areas": [],
        "posicao_federal": {},
        "perfil_relativo": {},
        "alertas": [],
    }
    for area in AREAS:
        edicao["inclusao"][area] = contar_inclusao(con, gold, ano, area)
        histogramas = histograma(con, gold, ano, area)
        registro_cobertura = _cobertura_de_contagens(
            {grupo: _tamanho(histogramas[grupo]) for grupo in GRUPOS_REDE}
        )
        edicao["cobertura"][area] = registro_cobertura
        grupos = grupos_por_rede(histogramas)
        motivo = _motivo_sem_comparacao(registro_cobertura)
        if motivo is not None:
            edicao["alertas"].append(f"{area}: {motivo}; comparações entre redes não calculadas")

        if registro_cobertura["n"] == 0:
            # Sem amostra não há percentil nem Topo_10 (as funções exigem amostra não vazia)
            for chave in comparacoes:
                comparacoes[chave][area] = nao_calculado(motivo, n=0)
            edicao["percentil_mediano"][area] = {grupo: nao_calculado(motivo, n=0)
                                                 for grupo in grupos}
            edicao["representacao_topo10"][area] = nao_calculado(motivo, n=0)
            edicao["medias"][area] = {grupo: nao_calculado(motivo, n=0) for grupo in grupos}
        else:
            stats = {grupo: estatisticas(hist) for grupo, hist in grupos.items() if hist}
            for par in PARES:
                if motivo is not None:
                    registro = nao_calculado(motivo, n=registro_cobertura["n_rede_informada"])
                else:
                    a, b = par
                    registro = comparar_grupos(grupos[a], grupos[b], min_grupo,
                                               stats.get(a), stats.get(b))
                comparacoes[_chave_par(par)][area] = registro
            lookup = percentil_lookup(_amostra_valida(histogramas))
            edicao["percentil_mediano"][area] = mediana_percentil_por_rede(
                histogramas, lookup=lookup, min_grupo=min_grupo
            )
            edicao["representacao_topo10"][area] = representacao_topo10(
                histogramas, min_grupo=min_grupo
            )
            edicao["medias"][area] = _medias_em_pontos(grupos, stats, min_grupo)

        # PARES guarda (privada, federal): a federal sobre a privada é 1 − AUC(privada, federal)
        auc_privada_federal = valor_auc(comparacoes["privada_vs_federal"][area])
        edicao["posicao_federal"][area] = posicao_federal(
            None if auc_privada_federal is None else 1 - auc_privada_federal,
            comparacoes["federal_vs_estadual"][area],
        )

    edicao["ranking_areas"] = ranking_areas(comparacoes)
    edicao["perfil_relativo"] = perfil_relativo_medio(con, gold, ano, min_grupo)
    return edicao


def _estabilidade(edicoes):
    """W de Kendall entre os rankings das edições e Spearman de cada par (Req 10.2 e 10.3).

    Entram as edições com pelo menos duas áreas no ranking, em ordem crescente. Medida que não
    pode ser calculada (menos de duas edições ou de duas áreas em comum) vira não calculada.
    Devolve {"kendall_w", "edicoes": [anos usados], "spearman": {"AAAA-BBBB": rho}}.
    """
    rankings = {ano: edicao["ranking_areas"] for ano, edicao in edicoes.items()}
    validas = [ano for ano in sorted(rankings, key=int) if len(rankings[ano]) >= 2]
    if len(validas) < 2:
        kendall = nao_calculado("menos de duas edições com ranking de pelo menos duas áreas")
    else:
        w = kendall_w([rankings[ano] for ano in validas])
        kendall = w if w is not None else nao_calculado(
            "menos de duas áreas presentes nos rankings de todas as edições"
        )
    rhos = {}
    for i, ano_a in enumerate(validas):
        for ano_b in validas[i + 1:]:
            rho = spearman(rankings[ano_a], rankings[ano_b])
            rhos[f"{ano_a}-{ano_b}"] = rho if rho is not None else nao_calculado(
                "menos de duas áreas em comum nos dois rankings"
            )
    return {"kendall_w": kendall, "edicoes": [int(ano) for ano in validas], "spearman": rhos}


def _cobertura_formato(edicoes):
    """Taxa de preenchimento média de 2018–2023 menos a de 2024–2025, em p.p. (Req 3.3 e 3.4).

    Usa as edições processadas com amostra válida na área. Sem edição de algum dos dois formatos,
    a diferença fica None, sem alerta, com o motivo. O alerta vale para |diferença| > 5 p.p.
    """
    resultado = {}
    for area in AREAS:
        taxas = {"antigo": [], "novo": []}
        for ano, edicao in sorted(edicoes.items(), key=lambda item: int(item[0])):
            taxa = edicao["cobertura"][area]["taxa_preenchimento"]
            if taxa is None:
                continue
            if int(ano) in ANOS_FORMATO_ANTIGO:
                taxas["antigo"].append(taxa)
            elif int(ano) in ANOS_FORMATO_NOVO:
                taxas["novo"].append(taxa)
        medias = {formato: math.fsum(valores) / len(valores) if valores else None
                  for formato, valores in taxas.items()}
        registro = {
            "dif_pp": None,
            "alerta": False,
            "media_formato_antigo": medias["antigo"],
            "media_formato_novo": medias["novo"],
        }
        if medias["antigo"] is None or medias["novo"] is None:
            registro["motivo"] = ("sem edição processada com amostra válida nos dois formatos "
                                  "(2018–2023 e 2024–2025)")
        else:
            registro["dif_pp"] = 100 * (medias["antigo"] - medias["novo"])
            registro["alerta"] = abs(registro["dif_pp"]) > LIMITE_ALERTA_COBERTURA_PP
        resultado[area] = registro
    return resultado


def processar(con, gold, anos=None, min_grupo=TAMANHO_MINIMO_GRUPO, semente=SEMENTE_PADRAO):
    """Objeto completo de resultados das edições pedidas, sem gravar nada.

    anos None = todas as edições de 2018 a 2025. Só as edições pedidas são processadas (Req
    18.3); pedida e sem linhas na gold vai para metadados.edicoes_ausentes e fica fora de
    "edicoes" (Req 17.3). As séries entre edições ("estabilidade" e "cobertura_formato") só usam
    medidas relativas (Req 4.2). A data da execução e o MD5 da gold entram no script
    (adicionar_metadados), então o objeto depende só da gold e dos parâmetros (Req 18.1).
    """
    pedidos = sorted({int(ano) for ano in (ANOS if anos is None else anos)})
    disponiveis = set(anos_disponiveis(con, gold))
    processadas = [ano for ano in pedidos if ano in disponiveis]
    edicoes = {str(ano): processar_edicao(con, gold, ano, min_grupo) for ano in processadas}
    return {
        "metadados": {
            "parametros": {"anos": pedidos, "min_grupo": min_grupo, "semente": semente},
            "edicoes_processadas": processadas,
            "edicoes_ausentes": [ano for ano in pedidos if ano not in disponiveis],
        },
        "edicoes": edicoes,
        "estabilidade": _estabilidade(edicoes),
        "cobertura_formato": _cobertura_formato(edicoes),
    }
