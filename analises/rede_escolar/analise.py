"""Análise da rede escolar: pública × privada e estrutura das notas entre as cinco áreas.

Uso: uv run python analises/rede_escolar/analise.py

Este script só orquestra (argumentos, saídas e erros). Os cálculos ficam em
src/enem_pja3/analises/rede_escolar.py.

Parâmetros: --gold, --saida, --anos (ex.: --anos 2023 2024), --min-grupo e --semente.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb

from enem_pja3.analises import rede_escolar
from enem_pja3.config import ANOS, DATA_DIR

# Caminhos padrão. A gold é relativa à pasta onde o comando roda (como no pipeline); a saída fica
# ao lado deste script, então funciona de qualquer pasta
GOLD_PADRAO = DATA_DIR / "gold" / "enem_notas.parquet"
SAIDA_PADRAO = Path(__file__).parent / "saida"
SEMENTE_PADRAO = 42

NOME_JSON = "resultados.json"


class ErroEntrada(Exception):
    """Problema nos dados de entrada (gold ausente ou incompleta). O main mostra a mensagem e sai com 1."""


# ---------------------------------------------------------------------------------------------
# Argumentos, verificação da entrada e resultados.json (tarefa 5.1)
# ---------------------------------------------------------------------------------------------

def _inteiro_positivo(texto):
    valor = int(texto)
    if valor < 1:
        raise argparse.ArgumentTypeError(f"precisa ser pelo menos 1, veio {valor}")
    return valor


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Rede escolar (pública × privada) e estrutura das notas entre as áreas do ENEM.",
    )
    parser.add_argument("--gold", type=Path, default=GOLD_PADRAO,
                        help=f"Parquet da gold de notas (padrão: {GOLD_PADRAO})")
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO,
                        help="pasta onde ficam resultados.json, RELATORIO.md e figuras/ "
                             "(padrão: analises/rede_escolar/saida)")
    parser.add_argument("--anos", type=int, nargs="+", choices=ANOS, metavar="ANO",
                        help=f"edições a processar (padrão: todas, {ANOS[0]} a {ANOS[-1]})")
    parser.add_argument("--min-grupo", type=_inteiro_positivo,
                        default=rede_escolar.TAMANHO_MINIMO_GRUPO,
                        help="tamanho mínimo de um grupo para calcular a medida "
                             f"(padrão: {rede_escolar.TAMANHO_MINIMO_GRUPO})")
    parser.add_argument("--semente", type=int, default=SEMENTE_PADRAO,
                        help=f"semente registrada nos resultados (padrão: {SEMENTE_PADRAO})")
    args = parser.parse_args(argv)
    # Sem --anos processa todas; com --anos, só as pedidas (Requisito 18.3), sem repetição
    args.anos = sorted(set(args.anos)) if args.anos else list(ANOS)
    return args


def verificar_entrada(con, gold):
    """Confere se a gold existe e tem as colunas obrigatórias (Requisitos 17.1 e 17.2).

    Levanta ErroEntrada com a mensagem para o usuário; não devolve nada quando está tudo certo.
    """
    gold = Path(gold)
    if not gold.is_file():
        raise ErroEntrada(
            f"Gold não encontrada: {gold}\n"
            "Para gerar a gold, rode o pipeline na raiz do repositório:\n"
            "    uv run enem-pja3\n"
            "ou use o data lake no Azure (depois do az login):\n"
            "    AZURE_STORAGE_ACCOUNT=stpanoramaenem uv run enem-pja3\n"
            "Se a gold estiver em outro lugar, informe o caminho com --gold."
        )
    try:
        ausentes = rede_escolar.colunas_ausentes(con, gold)
    except duckdb.Error as erro:
        raise ErroEntrada(f"Não foi possível ler a gold {gold} como Parquet: {erro}") from erro
    if ausentes:
        lista = "\n".join(f"    {coluna}" for coluna in ausentes)
        raise ErroEntrada(
            f"A gold {gold} não tem {len(ausentes)} coluna(s) obrigatória(s):\n{lista}\n"
            "Gere a gold de novo com uv run enem-pja3."
        )


def md5_arquivo(caminho):
    """MD5 do arquivo em hexadecimal, lido em blocos (a gold real tem alguns GB)."""
    with open(caminho, "rb") as arquivo:
        return hashlib.file_digest(arquivo, "md5").hexdigest()


def adicionar_metadados(resultados, gold, args):
    """Devolve os resultados com o bloco "metadados" completo e em primeiro lugar (Requisito 14.2).

    processar já preenche parametros, edicoes_processadas e edicoes_ausentes; aqui entram a data
    da execução (ISO-8601), o MD5 da gold e o caminho da gold nos parâmetros. Se processar não
    trouxer as edições, elas saem de "edicoes" e da lista pedida em --anos.
    """
    anteriores = dict(resultados.get("metadados", {}))
    parametros = {
        "gold": str(gold),
        "anos": list(args.anos),
        "min_grupo": args.min_grupo,
        "semente": args.semente,
    }
    # Parâmetros extras que processar registrar entram depois, sem sobrescrever os da execução
    parametros |= {chave: valor for chave, valor in anteriores.pop("parametros", {}).items()
                   if chave not in parametros}
    processadas = anteriores.pop(
        "edicoes_processadas", sorted(int(ano) for ano in resultados.get("edicoes", {}))
    )
    ausentes = anteriores.pop(
        "edicoes_ausentes", [ano for ano in args.anos if ano not in processadas]
    )
    anteriores.pop("data_execucao", None)
    anteriores.pop("md5_gold", None)
    metadados = {
        "data_execucao": datetime.now().astimezone().isoformat(timespec="seconds"),
        "md5_gold": md5_arquivo(gold),
        "parametros": parametros,
        "edicoes_processadas": processadas,
        "edicoes_ausentes": ausentes,
        **anteriores,
    }
    resto = {chave: valor for chave, valor in resultados.items() if chave != "metadados"}
    return {"metadados": metadados, **resto}


def gravar_json(resultados, saida):
    """Grava saida/resultados.json (UTF-8, indentado) e devolve o caminho.

    allow_nan=False: NaN ou infinito não é JSON válido, então um valor assim é erro de cálculo e
    para a gravação em vez de sair um arquivo que outros programas não leem. Ler o arquivo de
    volta com json.loads devolve um objeto igual ao gravado (Propriedade 16).
    """
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / NOME_JSON
    texto = json.dumps(resultados, ensure_ascii=False, allow_nan=False, indent=2)
    destino.write_text(texto + "\n", encoding="utf-8")
    return destino


# --- Figuras (tarefa 5.2) ---
#
# As figuras leem só o objeto de resultados, o mesmo gravado no resultados.json. Todo acesso à
# estrutura do objeto passa pelos acessores _figura_* abaixo, para que uma mudança de formato
# fique num lugar só. Medida não calculada ou ausente vira um ponto em branco, nunca um erro.
# Figura com eixo de tempo só mostra Medida_Relativa (Requisito 4.4). O matplotlib é importado
# dentro de gerar_figuras, para que importar este script continue barato.

# Pasta das figuras dentro da saída e nome de cada arquivo (nomes estáveis, citados no relatório)
PASTA_FIGURAS = "figuras"
FIGURAS = {
    "auc": "auc_privada_publica.png",
    "razao": "razao_representacao.png",
    "perfil": "perfil_relativo.png",
    "taxa": "taxa_preenchimento.png",
}

_NOMES_AREAS = {
    "CN": "Ciências da Natureza",
    "CH": "Ciências Humanas",
    "LC": "Linguagens e Códigos",
    "MT": "Matemática",
    "REDACAO": "Redação",
}
_SIGLAS_AREAS = {"CN": "CN", "CH": "CH", "LC": "LC", "MT": "MT", "REDACAO": "Redação"}
_NOMES_REDES = {
    "federal": "Federal",
    "estadual": "Estadual",
    "municipal": "Municipal",
    "privada": "Privada",
    "publica": "Pública (fed. + est. + mun.)",
}
_ULTIMA_EDICAO_FORMATO_ANTIGO = 2023
_DPI_FIGURAS = 150


def _numero(valor):
    """O valor como float, ou None se não for um número finito (None, NaN, texto, bool)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor = float(valor)
    return valor if float("-inf") < valor < float("inf") else None


def _caminho(dados, *chaves):
    """dados[c1][c2]..., ou None se algum nível faltar ou não for dict."""
    atual = dados
    for chave in chaves:
        if not isinstance(atual, dict) or chave not in atual:
            return None
        atual = atual[chave]
    return atual


def _valor_e_ic(registro, *chaves_valor):
    """(valor, ic_inferior, ic_superior) de um registro de medida, ou None se não há valor.

    registro pode ser um número ou um dict com o valor numa das chaves_valor e "ic": [inf, sup].
    Registro com "calculado": false (formato de nao_calculado) devolve None. IC ausente ou
    inválido vira (valor, None, None).
    """
    if registro is None:
        return None
    if not isinstance(registro, dict):
        valor = _numero(registro)
        return None if valor is None else (valor, None, None)
    if registro.get("calculado", True) is False:
        return None
    valor = next(
        (v for v in (_numero(registro.get(chave)) for chave in chaves_valor) if v is not None),
        None,
    )
    if valor is None:
        return None
    ic = registro.get("ic")
    inferior = superior = None
    if isinstance(ic, (list, tuple)) and len(ic) == 2:
        inferior, superior = _numero(ic[0]), _numero(ic[1])
    return valor, inferior, superior


def _edicoes_para_figura(resultados):
    """[(ano, dados da edição)] em ordem crescente de resultados["edicoes"].

    Aceita chaves int (saída de processar) ou str ("2018", depois do JSON).
    """
    edicoes = _caminho(resultados, "edicoes") or {}
    pares = []
    for chave, dados in edicoes.items():
        try:
            ano = int(chave)
        except (TypeError, ValueError):
            continue
        if isinstance(dados, dict):
            pares.append((ano, dados))
    return sorted(pares, key=lambda par: par[0])


def _figura_auc(dados_edicao, area, par=("privada", "publica")):
    """AUC e IC de par[0] sobre par[1]: comparacoes["<a>_vs_<b>"][area]["prob_superioridade"].

    O registro da área é o dict de comparar_grupos; com "calculado": false devolve None.
    """
    registro = _caminho(dados_edicao, "comparacoes", f"{par[0]}_vs_{par[1]}", area)
    if not isinstance(registro, dict) or registro.get("calculado", True) is False:
        return None
    return _valor_e_ic(registro.get("prob_superioridade"), "valor")


def _figura_razao(dados_edicao, area, rede):
    """Razão e IC: representacao_topo10[area]["por_rede"][rede] (formato de razao_representacao)."""
    registro = _caminho(dados_edicao, "representacao_topo10", area, "por_rede", rede)
    return _valor_e_ic(registro, "razao")


def _figura_perfil(dados_edicao, rede, area):
    """Componente médio do perfil relativo: perfil_relativo[rede][area].

    Aceita o componente como número ou como dict com "valor" ou "media" e "ic", direto na rede
    ou dentro de "componentes". Rede com "calculado": false devolve None.
    """
    entrada = _caminho(dados_edicao, "perfil_relativo", rede)
    if not isinstance(entrada, dict) or entrada.get("calculado", True) is False:
        return None
    componente = entrada.get(area)
    if componente is None:
        componente = _caminho(entrada, "componentes", area)
    return _valor_e_ic(componente, "valor", "media")


def _figura_taxa(dados_edicao, area):
    """Taxa de preenchimento (0 a 1): cobertura[area]["taxa_preenchimento"], ou None."""
    return _numero(_caminho(dados_edicao, "cobertura", area, "taxa_preenchimento"))


def _desenhar_serie(ax, xs, pontos, rotulo, **estilo):
    """Linha com marcadores e barras de IC; pontos[i] é (valor, inf, sup) ou None.

    Ponto None vira um buraco na linha. Devolve True se a série tinha algum valor.
    """
    if all(ponto is None for ponto in pontos):
        return False
    ys = [ponto[0] if ponto else float("nan") for ponto in pontos]
    (linha,) = ax.plot(xs, ys, marker="o", label=rotulo, **estilo)
    com_ic = [
        (x, ponto) for x, ponto in zip(xs, pontos)
        if ponto and ponto[1] is not None and ponto[2] is not None
    ]
    if com_ic:
        ax.errorbar(
            [x for x, _ in com_ic],
            [ponto[0] for _, ponto in com_ic],
            yerr=[
                [max(ponto[0] - ponto[1], 0.0) for _, ponto in com_ic],
                [max(ponto[2] - ponto[0], 0.0) for _, ponto in com_ic],
            ],
            fmt="none", ecolor=linha.get_color(), capsize=3, alpha=0.7,
        )
    return True


def _eixo_edicoes(ax, anos):
    ax.set_xticks(anos)
    ax.set_xticklabels([str(ano) for ano in anos])
    ax.set_xlabel("Edição do ENEM")
    ax.grid(True, alpha=0.3)


def _aviso_sem_dados(ax):
    ax.text(0.5, 0.5, "sem valores calculados", ha="center", va="center",
            transform=ax.transAxes, color="gray")


def _legenda_no_ultimo_painel(eixos, titulo, nota):
    """Usa o último painel da grade (vazio) para a legenda comum e uma nota de leitura."""
    painel = eixos[-1]
    painel.axis("off")
    alcas, rotulos = [], []
    for ax in eixos[:-1]:
        for alca, rotulo in zip(*ax.get_legend_handles_labels()):
            if rotulo not in rotulos:
                alcas.append(alca)
                rotulos.append(rotulo)
    if alcas:
        painel.legend(alcas, rotulos, loc="center", title=titulo)
    painel.text(0.5, 0.02, nota, ha="center", va="bottom", transform=painel.transAxes,
                fontsize="small")


def _desenhar_auc(fig, edicoes):
    """AUC privada × pública por edição, uma linha por área, com IC de 95%."""
    anos = [ano for ano, _ in edicoes]
    ax = fig.subplots()
    desenhou = False
    for area, nome in _NOMES_AREAS.items():
        pontos = [_figura_auc(dados, area) for _, dados in edicoes]
        desenhou = _desenhar_serie(ax, anos, pontos, nome) or desenhou
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="0,5 = sem diferença")
    ax.set_ylabel("Probabilidade de superioridade\nP(nota da privada > nota da pública)")
    ax.set_title("Rede privada × rede pública, por área e edição\n"
                 "(medida relativa à própria edição; barras: IC de 95%)")
    _eixo_edicoes(ax, anos)
    if not desenhou:
        _aviso_sem_dados(ax)
    ax.legend(loc="best", fontsize="small")


def _desenhar_razao(fig, edicoes):
    """Razão de representação no Topo_10 por edição: um painel por área, uma linha por rede."""
    anos = [ano for ano, _ in edicoes]
    eixos = fig.subplots(2, 3, sharey=True).flatten()
    for ax, (area, nome) in zip(eixos, _NOMES_AREAS.items()):
        desenhou = False
        for rede, rotulo in _NOMES_REDES.items():
            pontos = [_figura_razao(dados, area, rede) for _, dados in edicoes]
            estilo = {"linestyle": "--"} if rede == "publica" else {}
            desenhou = _desenhar_serie(ax, anos, pontos, rotulo, **estilo) or desenhou
        ax.axhline(1.0, color="gray", linestyle=":", linewidth=1)
        ax.set_title(nome)
        _eixo_edicoes(ax, anos)
        if not desenhou:
            _aviso_sem_dados(ax)
    eixos[0].set_ylabel("Razão de representação no topo 10%")
    eixos[3].set_ylabel("Razão de representação no topo 10%")
    _legenda_no_ultimo_painel(eixos, "Rede",
                              "1 = mesma participação no topo e no total\nbarras: IC de 95%")
    fig.suptitle("Participação da rede no topo 10% ÷ participação na amostra, por área e edição")


def _desenhar_perfil(fig, edicoes):
    """Perfil relativo médio: um painel por rede, as áreas no eixo x, uma linha por edição."""
    from matplotlib import colormaps

    areas = list(_NOMES_AREAS)
    xs = list(range(len(areas)))
    cores = colormaps["viridis"]
    eixos = fig.subplots(2, 3, sharey=True).flatten()
    for ax, (rede, nome) in zip(eixos, _NOMES_REDES.items()):
        desenhou = False
        for indice, (ano, dados) in enumerate(edicoes):
            pontos = [_figura_perfil(dados, rede, area) for area in areas]
            cor = cores(indice / max(len(edicoes) - 1, 1))
            desenhou = _desenhar_serie(ax, xs, pontos, str(ano), color=cor) or desenhou
        ax.axhline(0.0, color="gray", linestyle="--", linewidth=1)
        ax.set_xticks(xs)
        ax.set_xticklabels([_SIGLAS_AREAS[area] for area in areas])
        ax.set_title(nome)
        ax.grid(True, alpha=0.3)
        if not desenhou:
            _aviso_sem_dados(ax)
    eixos[0].set_ylabel("Percentil na área − média\ndos 5 percentis (pontos)")
    eixos[3].set_ylabel("Percentil na área − média\ndos 5 percentis (pontos)")
    _legenda_no_ultimo_painel(eixos, "Edição",
                              "acima de 0: área relativamente mais forte da rede\n"
                              "barras: IC de 95%")
    fig.suptitle("Perfil relativo médio entre as áreas, por rede (participantes com as 5 notas)")


def _desenhar_taxa(fig, edicoes):
    """Taxa de preenchimento da rede escolar por edição, uma linha por área, em %."""
    anos = [ano for ano, _ in edicoes]
    ax = fig.subplots()
    desenhou = False
    for area, nome in _NOMES_AREAS.items():
        pontos = []
        for _, dados in edicoes:
            taxa = _figura_taxa(dados, area)
            pontos.append(None if taxa is None else (100 * taxa, None, None))
        desenhou = _desenhar_serie(ax, anos, pontos, nome) or desenhou
    if any(ano <= _ULTIMA_EDICAO_FORMATO_ANTIGO for ano in anos) and any(
        ano > _ULTIMA_EDICAO_FORMATO_ANTIGO for ano in anos
    ):
        ax.axvline(_ULTIMA_EDICAO_FORMATO_ANTIGO + 0.5, color="gray", linestyle=":",
                   label="início do formato novo (2024)")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Participantes com rede escolar informada (%)")
    ax.set_title("Taxa de preenchimento de TP_DEPENDENCIA_ADM_ESC na amostra válida")
    _eixo_edicoes(ax, anos)
    if not desenhou:
        _aviso_sem_dados(ax)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="best", fontsize="small")


_DESENHOS_FIGURAS = {
    "auc": (_desenhar_auc, (9, 5.5)),
    "razao": (_desenhar_razao, (15, 8)),
    "perfil": (_desenhar_perfil, (15, 8)),
    "taxa": (_desenhar_taxa, (9, 5.5)),
}


def gerar_figuras(resultados, saida) -> list[Path]:
    """Grava as quatro figuras em saida/figuras/ e devolve os caminhos, na ordem de FIGURAS.

    Requisito 14.4: AUC privada × pública por edição e área, razão de representação por edição e
    área, perfil relativo médio por rede e taxa de preenchimento por edição. Funciona com uma
    edição só e com medidas não calculadas (ficam em branco).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pasta = Path(saida) / PASTA_FIGURAS
    pasta.mkdir(parents=True, exist_ok=True)
    edicoes = _edicoes_para_figura(resultados)
    caminhos = []
    for chave, nome in FIGURAS.items():
        desenhar, tamanho = _DESENHOS_FIGURAS[chave]
        destino = pasta / nome
        fig = plt.figure(figsize=tamanho, layout="constrained")
        try:
            desenhar(fig, edicoes)
            fig.savefig(destino, dpi=_DPI_FIGURAS, bbox_inches="tight")
        finally:
            plt.close(fig)
        caminhos.append(destino)
    return caminhos


# --- Relatório (tarefa 5.3) ---
#
# gerar_relatorio escreve o RELATORIO.md a partir do mesmo objeto gravado no resultados.json e da
# lista de figuras de gerar_figuras. Todo número passa por _rel_num (formatador único), então o
# relatório mostra os valores do JSON arredondados (Requisito 14.6). As suposições sobre o formato
# do objeto ficam nos acessores _rel_* abaixo. Medida não calculada aparece como "—", com o motivo
# listado embaixo da tabela.

NOME_RELATORIO = "RELATORIO.md"

_REL_TRACO = "—"
_REL_AREAS = {"CN": "CN", "CH": "CH", "LC": "LC", "MT": "MT", "REDACAO": "Redação"}
_REL_REDES = {
    "federal": "Federal",
    "estadual": "Estadual",
    "municipal": "Municipal",
    "privada": "Privada",
    "publica": "Pública",
}
_REL_POSICOES = {
    "mais_proxima_da_privada": "mais próxima da privada",
    "mais_proxima_da_estadual": "mais próxima da estadual",
    "equidistante": "equidistante",
}
# Chaves de "excluidos" de contar_inclusao, na ordem em que os critérios são aplicados
_REL_CRITERIOS = {
    "presenca": "Presença",
    "status_redacao": "Status da redação",
    "nota_nula": "Nota nula",
    "nota_zero": "IN_NOTA_ZERO",
}
# Palavras do nome do arquivo que ligam cada figura à seção onde ela aparece
_REL_FIGURAS_SECAO = {
    "cobertura": ("preenchimento",),
    "comparacoes": ("auc", "superioridade"),
    "topo10": ("razao", "representacao", "topo"),
    "perfil": ("perfil",),
}


def _rel_num(valor, casas=3):
    """Formatador único dos números do relatório: o valor do JSON com `casas` casas decimais.

    Contagens (int) saem inteiras. None, bool, texto, NaN e infinito saem como "—". Zero
    arredondado sai sem sinal (nada de "-0.000").
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return _REL_TRACO
    if isinstance(valor, int):
        return str(valor)
    if not float("-inf") < valor < float("inf"):
        return _REL_TRACO
    texto = f"{valor:.{casas}f}"
    return f"{0.0:.{casas}f}" if float(texto) == 0 else texto


def _rel_pct(proporcao, casas=1):
    """Proporção do JSON (0 a 1) em porcentagem, pelo mesmo formatador."""
    if isinstance(proporcao, bool) or not isinstance(proporcao, (int, float)):
        return _REL_TRACO
    texto = _rel_num(100.0 * proporcao, casas)
    return texto if texto == _REL_TRACO else f"{texto}%"


def _rel_lista(valores):
    valores = list(valores or [])
    return ", ".join(str(valor) for valor in valores) if valores else "nenhuma"


def _rel_tabela(cabecalho, linhas):
    """Tabela Markdown; "|" dentro de uma célula é escapado."""
    def linha(celulas):
        return "| " + " | ".join(str(celula).replace("|", "\\|") for celula in celulas) + " |"
    return "\n".join([linha(cabecalho), linha(["---"] * len(cabecalho))]
                     + [linha(celulas) for celulas in linhas])


def _rel_notas(notas):
    """Lista dos motivos das células "—" de uma tabela (vazio se não há nenhum)."""
    if not notas:
        return ""
    return "Não calculado:\n\n" + "\n".join(f"- {nota}" for nota in notas)


def _rel_bloco(*partes):
    """Junta trechos de Markdown com uma linha em branco entre eles, ignorando os vazios."""
    return "\n\n".join(parte.strip("\n") for parte in partes if parte)


# Acessores: únicos pontos que conhecem o formato do objeto de resultados

def _rel_edicoes(resultados):
    """[(ano em texto, dados da edição)] em ordem crescente.

    Aceita chaves int (saída de processar) ou str (depois do JSON).
    """
    edicoes = resultados.get("edicoes") or {}
    pares = [(str(ano), dados) for ano, dados in edicoes.items() if isinstance(dados, dict)]
    return sorted(pares, key=lambda par: int(par[0]))


def _rel_nao_calculado(registro):
    """Verdadeiro para medida ausente (None) ou no formato de nao_calculado ("calculado": false)."""
    return registro is None or (isinstance(registro, dict) and registro.get("calculado") is False)


def _rel_motivo(registro, notas, contexto):
    """Anota na lista da tabela o motivo de uma medida não calculada, se o registro tiver um."""
    if notas is not None and isinstance(registro, dict) and registro.get("motivo"):
        notas.append(f"{contexto}: {registro['motivo']}")


def _rel_valor_ic(medida):
    """(valor, ic) de uma medida: número, ou dict com "valor", "razao" ou "media" e "ic"."""
    if _rel_nao_calculado(medida):
        return None
    if not isinstance(medida, dict):
        return (medida, None)
    for chave in ("valor", "razao", "media"):
        if chave in medida:
            return (medida[chave], medida.get("ic"))
    return None


def _rel_celula(medida, notas=None, contexto="", casas=3):
    """Célula "valor [inferior, superior]", ou "—" com o motivo anotado em `notas`."""
    par = _rel_valor_ic(medida)
    if par is None or _rel_num(par[0], casas) == _REL_TRACO:
        _rel_motivo(medida, notas, contexto)
        return _REL_TRACO
    valor, ic = par
    texto = _rel_num(valor, casas)
    if isinstance(ic, (list, tuple)) and len(ic) == 2:
        texto += f" [{_rel_num(ic[0], casas)}, {_rel_num(ic[1], casas)}]"
    return texto


def _rel_metodos(medidas):
    """Métodos de IC (chave "metodo") das medidas calculadas, sem repetição."""
    metodos = []
    for medida in medidas:
        if isinstance(medida, dict) and not _rel_nao_calculado(medida):
            metodo = medida.get("metodo")
            if metodo and metodo not in metodos:
                metodos.append(metodo)
    return ", ".join(metodos)


def _rel_comparacao(edicao, par, area, medida):
    """prob_superioridade ou cohen_d de comparacoes["<a>_vs_<b>"][area] (dict de comparar_grupos).

    Se a comparação inteira não foi calculada, devolve o próprio registro, para o motivo aparecer.
    """
    registro = ((edicao.get("comparacoes") or {}).get(f"{par[0]}_vs_{par[1]}") or {}).get(area)
    if _rel_nao_calculado(registro) or not isinstance(registro, dict):
        return registro
    return registro.get(medida)


def _rel_taxa(edicao, area):
    """cobertura[area]["taxa_preenchimento"] (proporção de 0 a 1), ou None."""
    registro = (edicao.get("cobertura") or {}).get(area)
    return registro.get("taxa_preenchimento") if isinstance(registro, dict) else None


def _rel_topo10(edicao, area):
    """representacao_topo10[area]: {"corte", "prop_real", "por_rede"} ou registro não calculado."""
    return (edicao.get("representacao_topo10") or {}).get(area)


def _rel_classificacao_federal(registro):
    """Classificação da federal: texto (formato do design) ou o dict de posicao_federal."""
    if isinstance(registro, str):
        return registro
    if _rel_nao_calculado(registro) or not isinstance(registro, dict):
        return None
    return registro.get("classificacao")


def _rel_perfil_componente(perfil_rede, area):
    """Componente médio do perfil de uma rede: número ou dict com "media"/"valor" e "ic".

    Aceita a área direto no dict da rede (formato do design) ou dentro de "componentes", e o IC
    dentro do componente ou num dict "ic" por área.
    """
    componente = perfil_rede.get(area)
    if componente is None:
        componente = (perfil_rede.get("componentes") or {}).get(area)
    ic = perfil_rede.get("ic")
    if not isinstance(componente, dict) and isinstance(ic, dict) and area in ic:
        return {"valor": componente, "ic": ic[area]}
    return componente


def _rel_rotulo_area(area):
    return _REL_AREAS.get(area, area) if area else _REL_TRACO


# Figuras

def _rel_caminho_figura(figura, saida):
    """Caminho da figura relativo ao diretório do relatório, com "/" (Requisito 14.5)."""
    import os

    figura, saida = Path(figura), Path(saida)
    try:
        return figura.resolve().relative_to(saida.resolve()).as_posix()
    except ValueError:
        pass
    if not figura.is_absolute():
        return figura.as_posix()  # já relativo à saída, como "figuras/x.png"
    return Path(os.path.relpath(figura, saida.resolve())).as_posix()


def _rel_tomar_figuras(pendentes, secao):
    """Tira de `pendentes` as figuras da seção (pelo nome do arquivo) e devolve o Markdown delas."""
    palavras = _REL_FIGURAS_SECAO[secao]
    escolhidas = [figura for figura in pendentes
                  if any(palavra in Path(figura).name.lower() for palavra in palavras)]
    for figura in escolhidas:
        pendentes.remove(figura)
    return "\n\n".join(f"![{Path(figura).stem.replace('_', ' ')}]({figura})"
                       for figura in escolhidas)


# Seções

def _rel_secao_cabecalho(resultados):
    meta = resultados.get("metadados") or {}
    parametros = meta.get("parametros") or {}
    return "\n".join([
        "# Rede escolar e estrutura das notas entre áreas (ENEM 2018–2025)",
        "",
        "Análise individual de Gabriel Sartori Mosquer para o relatório técnico do Projeto "
        "Aplicado III (Panorama ENEM). Compara participantes de escolas públicas e privadas e "
        "descreve como a diferença se distribui entre CN, CH, LC, MT e Redação.",
        "",
        "Relatório gerado por `analises/rede_escolar/analise.py` a partir do `resultados.json` "
        "deste diretório. Os números das tabelas são os do JSON, arredondados e com ponto decimal. "
        "\"—\" indica medida não calculada; o motivo aparece embaixo da tabela.",
        "",
        f"- Data da execução: {meta.get('data_execucao') or _REL_TRACO}",
        f"- MD5 da gold: `{meta.get('md5_gold') or _REL_TRACO}`",
        f"- Gold: `{parametros.get('gold') or _REL_TRACO}`",
        f"- Tamanho mínimo do grupo: {_rel_num(parametros.get('min_grupo'))}",
        f"- Semente: {_rel_num(parametros.get('semente'))}",
        f"- Edições pedidas: {_rel_lista(parametros.get('anos'))}",
        f"- Edições processadas: {_rel_lista(meta.get('edicoes_processadas'))}",
        f"- Edições ausentes na gold: {_rel_lista(meta.get('edicoes_ausentes'))}",
    ])


def _rel_texto_alerta(alerta):
    if isinstance(alerta, dict):
        if alerta.get("mensagem"):
            return str(alerta["mensagem"])
        return "; ".join(f"{chave}: {valor}" for chave, valor in alerta.items())
    return str(alerta)


def _rel_secao_alertas(resultados):
    """Edições ausentes (Requisito 17.3), alertas de cobertura (3.4) e alertas por edição."""
    meta = resultados.get("metadados") or {}
    itens = []
    ausentes = meta.get("edicoes_ausentes") or []
    if ausentes:
        itens.append(f"Edições de 2018 a 2025 sem linhas na gold, fora da análise: "
                     f"{_rel_lista(ausentes)}.")
    formato = resultados.get("cobertura_formato") or {}
    for area in _REL_AREAS:
        registro = formato.get(area)
        if isinstance(registro, dict) and registro.get("alerta"):
            itens.append(
                f"Alerta de cobertura em {_rel_rotulo_area(area)}: a taxa de preenchimento média "
                f"de 2018–2023 difere da de 2024–2025 em {_rel_num(registro.get('dif_pp'), 1)} "
                "p.p. (limite de 5 p.p.)."
            )
    itens += [_rel_texto_alerta(alerta) for alerta in resultados.get("alertas") or []]
    for ano, edicao in _rel_edicoes(resultados):
        itens += [f"{ano}: {_rel_texto_alerta(alerta)}" for alerta in edicao.get("alertas") or []]
    unicos = list(dict.fromkeys(itens))
    corpo = "\n".join(f"- {item}" for item in unicos) if unicos else "Nenhum alerta."
    return _rel_bloco("## Alertas", corpo)


def _rel_tabela_taxa(resultados):
    linhas = [[ano] + [_rel_pct(_rel_taxa(edicao, area)) for area in _REL_AREAS]
              for ano, edicao in _rel_edicoes(resultados)]
    return _rel_tabela(["Edição", *_REL_AREAS.values()], linhas)


def _rel_secao_cobertura(resultados, figuras):
    """Taxa de preenchimento por edição e área, antes das diferenças entre redes (Req. 3.5)."""
    formato = resultados.get("cobertura_formato") or {}
    linhas_formato = [
        [_rel_rotulo_area(area), _rel_num(formato[area].get("dif_pp"), 1),
         "sim" if formato[area].get("alerta") else "não"]
        for area in _REL_AREAS if isinstance(formato.get(area), dict)
    ]
    partes = [
        "## Cobertura da rede escolar",
        "Taxa de preenchimento: proporção da amostra válida com `TP_DEPENDENCIA_ADM_ESC` entre 1 "
        "e 4. Quem não tem a rede informada fica fora das comparações entre redes.",
        _rel_tabela_taxa(resultados),
    ]
    if linhas_formato:
        partes += [
            "Diferença entre a taxa média do formato antigo (2018–2023) e a do formato novo "
            "(2024–2025), em pontos percentuais. Acima de 5 p.p. gera alerta.",
            _rel_tabela(["Área", "Diferença (p.p.)", "Alerta"], linhas_formato),
        ]
    partes.append(figuras)
    return _rel_bloco(*partes)


def _rel_secao_inclusao(resultados):
    """Total da edição, excluídos por critério e amostra válida (Requisito 1.3)."""
    linhas = []
    for ano, edicao in _rel_edicoes(resultados):
        inclusao = edicao.get("inclusao") or {}
        for area in _REL_AREAS:
            registro = inclusao.get(area)
            if not isinstance(registro, dict):
                continue
            excluidos = registro.get("excluidos") or {}
            linhas.append(
                [ano, _rel_rotulo_area(area), _rel_num(registro.get("total"))]
                + [_rel_num(excluidos.get(criterio)) for criterio in _REL_CRITERIOS]
                + [_rel_num(registro.get("amostra_valida"))]
            )
    cabecalho = (["Edição", "Área", "Total da edição"]
                 + [f"Excluídos: {rotulo}" for rotulo in _REL_CRITERIOS.values()]
                 + ["Amostra válida"])
    return _rel_bloco(
        "## Critérios de inclusão",
        "Exclusões contadas em cascata: cada participante entra só no primeiro critério que não "
        "atende. \"—\" = critério que não se aplica à área.",
        _rel_tabela(cabecalho, linhas),
    )


def _rel_grade(edicoes, obter, casas=3):
    """Tabela edição × área de uma medida com IC, seguida do método do IC e dos motivos de "—"."""
    notas, medidas, linhas = [], [], []
    for ano, edicao in edicoes:
        linha = [ano]
        for area, rotulo in _REL_AREAS.items():
            medida = obter(edicao, area)
            medidas.append(medida)
            linha.append(_rel_celula(medida, notas, f"{ano} {rotulo}", casas))
        linhas.append(linha)
    metodos = _rel_metodos(medidas)
    return _rel_bloco(
        _rel_tabela(["Edição", *_REL_AREAS.values()], linhas),
        f"Método do IC de 95%: {metodos}." if metodos else "",
        _rel_notas(notas),
    )


def _rel_secao_comparacoes(resultados, figuras):
    edicoes = _rel_edicoes(resultados)
    partes = [
        "## Diferenças entre redes (medidas relativas)",
        "Probabilidade de superioridade (AUC): chance de um participante do primeiro grupo ter "
        "nota maior que um participante do segundo, contando empate como meio; 0.5 = sem "
        "diferença. d de Cohen: diferença das médias em desvios-padrão combinados da própria "
        "edição. As duas medidas são calculadas dentro de cada edição e podem ser comparadas entre "
        "edições. Entre colchetes, o IC de 95%.",
        figuras,
    ]
    for par in rede_escolar.PARES:
        primeiro, segundo = _REL_REDES[par[0]], _REL_REDES[par[1]]
        partes += [
            f"### {primeiro} × {segundo}",
            f"Probabilidade de superioridade da rede {primeiro.lower()} sobre a rede "
            f"{segundo.lower()}:",
            _rel_grade(edicoes, lambda edicao, area, par=par:
                       _rel_comparacao(edicao, par, area, "prob_superioridade")),
            f"d de Cohen da rede {primeiro.lower()} em relação à rede {segundo.lower()}:",
            _rel_grade(edicoes, lambda edicao, area, par=par:
                       _rel_comparacao(edicao, par, area, "cohen_d")),
        ]
    return _rel_bloco(*partes)


def _rel_secao_percentil(resultados):
    notas, linhas = [], []
    for ano, edicao in _rel_edicoes(resultados):
        percentis = edicao.get("percentil_mediano") or {}
        for area, rotulo in _REL_AREAS.items():
            por_rede = percentis.get(area) or {}
            linhas.append([ano, rotulo] + [
                _rel_celula(por_rede.get(rede), notas, f"{ano} {rotulo} {nome}", 1)
                for rede, nome in _REL_REDES.items()
            ])
    return _rel_bloco(
        "## Percentil mediano por rede",
        "Mediana do percentil na edição dos participantes de cada rede. O percentil é calculado "
        "sobre toda a amostra válida da área (com e sem rede informada); 50 = posição do "
        "participante típico da edição.",
        _rel_tabela(["Edição", "Área", *_REL_REDES.values()], linhas),
        _rel_notas(notas),
    )


def _rel_secao_topo10(resultados, figuras):
    notas, medidas, linhas = [], [], []
    for ano, edicao in _rel_edicoes(resultados):
        for area, rotulo in _REL_AREAS.items():
            registro = _rel_topo10(edicao, area)
            contexto = f"{ano} {rotulo}"
            if _rel_nao_calculado(registro) or not isinstance(registro, dict):
                _rel_motivo(registro, notas, contexto)
                linhas.append([ano, rotulo] + [_REL_TRACO] * (1 + len(_REL_REDES)))
                continue
            por_rede = registro.get("por_rede") or {}
            linha = [ano, rotulo, _rel_pct(registro.get("prop_real"))]
            for rede, nome in _REL_REDES.items():
                medida = por_rede.get(rede)
                medidas.append(medida)
                linha.append(_rel_celula(medida, notas, f"{contexto} {nome}", 2))
            linhas.append(linha)
    metodos = _rel_metodos(medidas)
    return _rel_bloco(
        "## Representação no topo 10%",
        "Razão de representação: participação da rede no Topo_10 dividida pela participação dela "
        "na amostra válida, as duas só entre quem tem rede informada. 1 = representação "
        "proporcional; acima de 1 = rede sobrerrepresentada no topo. A proporção real é a fração "
        "da amostra válida no Topo_10, que passa de 10% quando há empates na nota de corte. A nota "
        "de corte, em pontos, está na seção de valores em pontos.",
        _rel_tabela(["Edição", "Área", "Proporção real no Topo_10", *_REL_REDES.values()], linhas),
        f"Método do IC de 95%: {metodos}." if metodos else "",
        _rel_notas(notas),
        figuras,
    )


def _rel_secao_ranking(resultados):
    """Posição de cada área por edição (Requisito 10.6), W de Kendall e Spearman."""
    linhas = []
    for ano, edicao in _rel_edicoes(resultados):
        ranking = list(edicao.get("ranking_areas") or [])
        linhas.append([ano] + [str(ranking.index(area) + 1) if area in ranking else _REL_TRACO
                               for area in _REL_AREAS])
    estabilidade = resultados.get("estabilidade") or {}
    notas = []
    kendall = _rel_celula(estabilidade.get("kendall_w"), notas, "W de Kendall")
    spearman = estabilidade.get("spearman") or {}
    linhas_spearman = [[par, _rel_celula(valor, notas, f"Spearman {par}")]
                       for par, valor in sorted(spearman.items())]
    return _rel_bloco(
        "## Ranking das áreas",
        "Posição de cada área no ranking da edição, pela probabilidade de superioridade da rede "
        "privada sobre a pública (1 = maior diferença). \"—\" = área sem AUC calculada na edição, "
        "fora do ranking.",
        _rel_tabela(["Edição", *_REL_AREAS.values()], linhas),
        f"W de Kendall entre os rankings das edições processadas: {kendall}.",
        _rel_tabela(["Par de edições", "Spearman"], linhas_spearman) if linhas_spearman else "",
        _rel_notas(notas),
    )


def _rel_secao_posicao_federal(resultados):
    """Classificação da federal por edição e área (Requisito 12.4)."""
    notas, linhas = [], []
    for ano, edicao in _rel_edicoes(resultados):
        posicoes = edicao.get("posicao_federal") or {}
        linha = [ano]
        for area, rotulo in _REL_AREAS.items():
            registro = posicoes.get(area)
            classificacao = _rel_classificacao_federal(registro)
            if classificacao is None:
                _rel_motivo(registro, notas, f"{ano} {rotulo}")
                linha.append(_REL_TRACO)
            else:
                linha.append(_REL_POSICOES.get(classificacao, classificacao))
        linhas.append(linha)
    return _rel_bloco(
        "## Posição da rede federal",
        "Compara |AUC(federal, privada) − 0.5| com |AUC(federal, estadual) − 0.5|: a menor "
        "distância indica de qual rede a federal está mais próxima na edição e área.",
        _rel_tabela(["Edição", *_REL_AREAS.values()], linhas),
        _rel_notas(notas),
    )


def _rel_secao_perfil(resultados, figuras):
    notas, medidas, linhas = [], [], []
    for ano, edicao in _rel_edicoes(resultados):
        perfil = edicao.get("perfil_relativo")
        if _rel_nao_calculado(perfil) or not isinstance(perfil, dict):
            _rel_motivo(perfil, notas, ano)
            continue
        for rede, nome in _REL_REDES.items():
            if rede not in perfil:
                continue
            perfil_rede = perfil[rede]
            contexto = f"{ano} {nome}"
            if _rel_nao_calculado(perfil_rede) or not isinstance(perfil_rede, dict):
                _rel_motivo(perfil_rede, notas, contexto)
                linhas.append([ano, nome] + [_REL_TRACO] * (len(_REL_AREAS) + 2))
                continue
            medidas.append(perfil_rede)
            linha = [ano, nome]
            for area, rotulo in _REL_AREAS.items():
                medida = _rel_perfil_componente(perfil_rede, area)
                medidas.append(medida)
                linha.append(_rel_celula(medida, notas, f"{contexto} {rotulo}", 1))
            linha += [_rel_rotulo_area(perfil_rede.get("area_maior")),
                      _rel_rotulo_area(perfil_rede.get("area_menor"))]
            linhas.append(linha)
    metodos = _rel_metodos(medidas)
    return _rel_bloco(
        "## Perfil relativo médio por rede",
        "Participantes com nota válida nas cinco áreas (amostra completa). Componente = percentil "
        "na área menos a média dos cinco percentis do participante, em pontos de percentil. "
        "Positivo = área relativamente mais forte da rede. Entre colchetes, o IC de 95%.",
        _rel_tabela(["Edição", "Rede", *_REL_AREAS.values(), "Área maior", "Área menor"], linhas),
        f"Método do IC de 95%: {metodos}." if metodos else "",
        _rel_notas(notas),
        figuras,
    )


def _rel_secao_pontos(resultados):
    """Valores em pontos, uma tabela por edição, com aviso de não comparabilidade (Req. 4.3).

    Mostra a nota de corte do Topo_10 e, se a edição trouxer "medias" ({area: {rede: média em
    pontos}}), a média de cada rede.
    """
    partes = [
        "## Valores em pontos de nota, por edição",
        "**Aviso:** estes valores estão na escala da TRI de cada edição e não são comparáveis "
        "entre edições. Para comparar anos, use as medidas relativas das seções anteriores.",
    ]
    for ano, edicao in _rel_edicoes(resultados):
        medias = edicao.get("medias") or {}
        cabecalho = ["Área", "Nota de corte do Topo_10"]
        if medias:
            cabecalho += [f"Média {nome.lower()}" for nome in _REL_REDES.values()]
        linhas = []
        for area, rotulo in _REL_AREAS.items():
            registro = _rel_topo10(edicao, area)
            corte = registro.get("corte") if isinstance(registro, dict) else None
            linha = [rotulo, _rel_num(corte, 1)]
            if medias:
                por_rede = medias.get(area) or {}
                linha += [_rel_celula(por_rede.get(rede), casas=1) for rede in _REL_REDES]
            linhas.append(linha)
        partes += [f"### {ano}",
                   f"Escala da TRI de {ano}; não comparar com outras edições.",
                   _rel_tabela(cabecalho, linhas)]
    return _rel_bloco(*partes)


def _rel_secao_outras_figuras(pendentes):
    if not pendentes:
        return ""
    return _rel_bloco("## Outras figuras", *(
        f"![{Path(figura).stem.replace('_', ' ')}]({figura})" for figura in pendentes
    ))


def _rel_tabela_exclusoes(resultados):
    """Participantes excluídos (soma dos critérios) por edição e área."""
    linhas = []
    for ano, edicao in _rel_edicoes(resultados):
        inclusao = edicao.get("inclusao") or {}
        linha = [ano]
        for area in _REL_AREAS:
            registro = inclusao.get(area)
            excluidos = registro.get("excluidos") if isinstance(registro, dict) else None
            linha.append(_rel_num(sum(excluidos.values())) if isinstance(excluidos, dict)
                         else _REL_TRACO)
        linhas.append(linha)
    return _rel_tabela(["Edição", *_REL_AREAS.values()], linhas)


def _rel_secao_limitacoes(resultados):
    """Seção de limitações (Requisitos 15.1 a 15.5)."""
    return _rel_bloco(
        "## Limitações",
        "- **Associação, não causa.** As medidas descrevem a associação entre a rede escolar e a "
        "nota dentro de cada edição. Elas não medem o efeito causal de estudar em uma rede.\n"
        "- **Seleção das famílias e das escolas.** A rede escolar é escolhida pelas famílias e "
        "reflete diferenças de renda e de escolaridade dos pais. Parte das escolas, como as "
        "federais, também seleciona os alunos no ingresso. A diferença entre redes mistura essa "
        "composição e essa seleção com o que a escola faz.\n"
        "- **Cobertura da rede informada.** `TP_DEPENDENCIA_ADM_ESC` cobre principalmente os "
        "concluintes do ensino médio. Quem não tem a rede informada fica fora das comparações "
        "entre redes, mas entra no percentil na edição e no corte do Topo_10. Taxa de "
        "preenchimento por edição e área:",
        _rel_tabela_taxa(resultados),
        "- **Escala da TRI.** As notas vêm da TRI e a escala muda a cada edição. Valores em "
        "pontos de nota não são comparáveis entre edições; as séries entre anos usam só medidas "
        "relativas.\n"
        "- **Exclusões.** A análise descreve só participantes presentes e com nota válida. A "
        "exclusão por ausência, por nota nula, por `IN_NOTA_ZERO` e, na Redação, por status "
        "diferente de 1 altera a população analisada. Participantes excluídos por edição e área "
        "(detalhe por critério na seção de critérios de inclusão):",
        _rel_tabela_exclusoes(resultados),
    )


_REL_CAPITULO = """\
## Rascunho do capítulo: seções 1.1 a 1.3

### 1.1 Regras da análise

**Objetivo e relação com as outras análises do grupo.** A análise compara o desempenho de \
participantes de escolas públicas e privadas no ENEM de 2018 a 2025 e descreve como a diferença \
se distribui entre as cinco áreas (CN, CH, LC, MT e Redação). O eixo é a rede escolar. A análise \
de Vítor (`analises/preco_do_ponto/`) estuda renda per capita × nota de 2018 a 2023, com regressão \
no log2 da renda, U de Mann-Whitney normalizado e d de Cohen entre extremos de renda, padronização \
indireta por UF e decomposição de Shapley do R². A de Pedro (`income_model.py`, rota \
`POST /api/v1/analysis/income-probability`) modela a probabilidade condicional de nota por faixa de \
renda pelo teorema de Bayes, de 2018 a 2023. Esta análise não usa a renda, cobre as oito edições e \
separa a rede pública em federal, estadual e municipal.

**Critérios de inclusão.** Para cada edição e área, a amostra válida tem:

- nas provas objetivas (CN, CH, LC, MT): presença igual a 1 na prova, nota não nula e \
`IN_NOTA_ZERO` falso;
- na Redação: `TP_PRESENCA_LC` igual a 1 (a redação é feita no dia de LC), `TP_STATUS_REDACAO` \
igual a 1, `NU_NOTA_REDACAO` não nula e `IN_NOTA_ZERO` falso.

As exclusões são contadas em cascata, na ordem presença, status da redação, nota nula e \
`IN_NOTA_ZERO`: cada participante entra só no primeiro critério que não atende, e o total da \
edição é a soma dos excluídos com a amostra válida. A amostra válida inclui quem não tem rede \
informada. A amostra completa de uma edição reúne quem está na amostra válida das cinco áreas e é \
usada no perfil relativo. Todas as consultas usam só as linhas com `NU_ANO` igual à edição.

**Classificação da rede escolar.** `TP_DEPENDENCIA_ADM_ESC` define a rede: 1 federal, 2 estadual, \
3 municipal e 4 privada. A rede pública reúne federal, estadual e municipal. Valor nulo ou fora de \
1 a 4 conta como sem rede informada: o participante fica fora das comparações entre redes e reduz \
a taxa de preenchimento. Os pares comparados são privada × pública, privada × federal, privada × \
estadual, privada × municipal e federal × estadual.

**Regra entre edições.** As notas do ENEM vêm da TRI e a escala muda a cada edição. Toda medida é \
calculada com participantes de uma única edição. As séries entre edições e as figuras com eixo de \
tempo usam só medidas relativas: probabilidade de superioridade, d de Cohen, percentil na edição, \
razão de representação, perfil relativo, posição no ranking de áreas e taxa de preenchimento. \
Valores em pontos de nota aparecem só em tabelas separadas por edição, com o aviso de que não são \
comparáveis.

**Medidas e intervalos de confiança.** As notas são discretas (objetivas com uma casa decimal, \
redação inteira). O DuckDB conta os participantes por rede e por valor de nota, e todas as medidas \
saem dessas contagens, sem carregar as notas em Python. Os intervalos são de 95% e analíticos, sem \
reamostragem; o método de cada um fica registrado no `resultados.json`.

- *Probabilidade de superioridade (AUC).* P(nota de A > nota de B) + 0,5 · P(nota de A = nota de \
B), igual ao U de Mann-Whitney dividido por nA · nB; 0,5 indica ausência de diferença. IC de \
Hanley e McNeil (1982): EP² = [θ(1 − θ) + (nA − 1)(Q1 − θ²) + (nB − 1)(Q2 − θ²)] / (nA · nB), com \
Q1 = θ / (2 − θ) e Q2 = 2θ² / (1 + θ); o intervalo θ ± 1,96 · EP é cortado em [0, 1].
- *d de Cohen.* (média de A − média de B) dividido pelo desvio-padrão combinado, \
√(((nA − 1)·varA + (nB − 1)·varB) / (nA + nB − 2)). Com desvio combinado zero, o d não é \
calculado. IC pela variância aproximada de Hedges e Olkin (1985): Var(d) = (nA + nB) / (nA · nB) \
+ d² / (2(nA + nB)), intervalo d ± 1,96 · √Var(d).
- *Percentil na edição.* 100 · (participantes com nota menor + 0,5 · participantes com nota igual) \
/ tamanho da amostra válida da área. Para cada rede e para a rede pública, o relatório mostra a \
mediana desse percentil (com n par, a média dos dois participantes centrais). Sem IC.
- *Topo_10 e razão de representação.* A nota de corte é o percentil 90 discreto da amostra válida \
(a menor nota com mais de 90% da amostra em notas menores ou iguais). Entram no Topo_10 todos com \
nota maior ou igual ao corte; empates no corte podem levar a proporção real acima de 10%, e essa \
proporção fica registrada. A razão de uma rede é a participação dela no Topo_10 dividida pela \
participação dela na amostra válida, as duas só entre quem tem rede informada; 1 indica \
representação proporcional. IC pelo método delta no log: Var(log R) ≈ (1 − p_topo) / t + \
(1 − p_todos) / n, com t e n os participantes da rede no topo e na amostra; intervalo \
R · exp(±1,96 · EP). A covariância entre as duas proporções é ignorada, o que deixa o intervalo um \
pouco mais largo. Sem participante da rede no topo, o limite inferior é 0 e o superior usa 0,5 \
participante (correção de continuidade).
- *Ranking de áreas e estabilidade.* Em cada edição, as áreas são ordenadas pela AUC da privada \
sobre a pública, da maior para a menor (empates seguem a ordem CN, CH, LC, MT, Redação). A \
concordância entre as edições é medida pelo W de Kendall, W = 12S / (m²(n³ − n)), e cada par de \
edições pela correlação de Spearman, ρ = 1 − 6Σd² / (n(n² − 1)). Área sem AUC numa edição fica \
fora do ranking dessa edição, e o W e o Spearman usam só as áreas presentes em todos os rankings \
comparados.
- *Perfil relativo.* Para cada participante da amostra completa, o percentil em cada área \
(calculado na amostra válida da área) menos a média dos cinco percentis dele; os cinco \
componentes somam zero. O relatório mostra a média de cada componente por rede e para a rede \
pública, com IC de 95%, e a área com maior e com menor componente.
- *Posição da rede federal.* Distância à privada = |AUC(federal, privada) − 0,5|; distância à \
estadual = |AUC(federal, estadual) − 0,5|. A menor distância define a classificação (\"mais \
próxima da privada\" ou \"mais próxima da estadual\"); distâncias iguais dão \"equidistante\".
- *Taxa de preenchimento.* Proporção da amostra válida com rede informada, por edição e área. A \
análise compara a média de 2018–2023 (formato antigo) com a de 2024–2025 (formato novo) e registra \
um alerta quando a diferença passa de 5 pontos percentuais.
- *Tamanho mínimo do grupo.* Grupo com menos participantes que o mínimo (padrão 100) tem a medida \
registrada como não calculada, com o motivo e o tamanho do grupo.

### 1.2 Entradas, execução e saídas

**Entrada.** `data/gold/enem_notas.parquet`, gerada por `src/enem_pja3/load/load.py`, com uma \
linha por participante. Colunas lidas: `NU_ANO`, `SG_UF_PROVA`, `TP_DEPENDENCIA_ADM_ESC`, \
`TP_PRESENCA_CN`, `TP_PRESENCA_CH`, `TP_PRESENCA_LC`, `TP_PRESENCA_MT`, `NU_NOTA_CN`, \
`NU_NOTA_CH`, `NU_NOTA_LC`, `NU_NOTA_MT`, `NU_NOTA_REDACAO`, `TP_STATUS_REDACAO` e `IN_NOTA_ZERO`. \
`SG_UF_PROVA` faz parte do contrato verificado na entrada, mas não entra nas medidas.

**Comando.**

```bash
uv sync
uv run python analises/rede_escolar/analise.py
```

**Parâmetros.**

| Parâmetro | Padrão | Uso |
| --- | --- | --- |
| `--gold` | `data/gold/enem_notas.parquet` | caminho da gold |
| `--saida` | `analises/rede_escolar/saida/` | diretório das saídas |
| `--anos` | todas as edições de 2018 a 2025 | edições a processar (ex.: `--anos 2023 2024`) |
| `--min-grupo` | 100 | tamanho mínimo do grupo |
| `--semente` | 42 | semente registrada no `resultados.json`; os ICs atuais não usam reamostragem |

**Saídas** (no diretório de `--saida`):

- `resultados.json`: metadados (data da execução, MD5 da gold, parâmetros, edições processadas e \
ausentes); por edição, inclusão, cobertura, comparações entre redes, percentis medianos, Topo_10, \
ranking de áreas, perfil relativo, posição da federal e alertas; a estabilidade dos rankings e a \
comparação de cobertura entre os formatos.
- `RELATORIO.md`: este relatório, com tabelas, figuras, limitações e este rascunho.
- `figuras/*.png`: probabilidade de superioridade por edição e área, razão de representação por \
edição e área, perfil relativo médio por rede e taxa de preenchimento por edição.

**Organização e memória.** O script `analises/rede_escolar/analise.py` só orquestra: lê os \
argumentos, verifica a entrada, chama o cálculo e grava as saídas. Os cálculos ficam em \
`src/enem_pja3/analises/rede_escolar.py`. As consultas usam a conexão de `conectar()`, com o limite \
de memória `MEMORIA_DUCKDB` (4 GB) de `src/enem_pja3/config.py`, e só trazem agregados para o \
Python.

### 1.3 Validação e resiliência

**Testes.** A suíte roda com `uv run pytest` sem a gold real: os testes gravam uma gold sintética \
pequena, com o mesmo contrato de colunas, num diretório temporário. Os testes da análise ficam em \
`tests/test_rede_escolar.py`:

- testes de exemplo com valores calculados à mão para probabilidade de superioridade, d de Cohen, \
percentil na edição, razão de representação e perfil relativo;
- casos de borda: empates no corte do Topo_10, grupo abaixo do mínimo, desvio combinado zero e as \
três classificações da federal;
- testes sobre a gold sintética: inclusão por área, rede nula ou fora de 1 a 4, cobertura por \
rede, alerta de cobertura, edição ausente, taxa de preenchimento zero, filtro de edições e \
idempotência;
- testes de erro do script e de execução completa sobre a gold sintética.

Um teste de execução completa sobre `data/gold/enem_notas.parquet` roda quando a gold real existe \
e é marcado como ignorado quando ela não existe.

**Propriedades verificadas** (biblioteca `hypothesis`, 100 exemplos gerados por propriedade, \
tolerância de 1e-9 nas igualdades):

| Propriedade | O que verifica | Requisito |
| --- | --- | --- |
| 1 | AUC(A, B) = 1 − AUC(B, A) | 5.3 |
| 2 | a AUC não muda com transformações estritamente crescentes das notas | 5.4 |
| 3 | a AUC é igual à comparação direta de todos os pares (grupos de até 200) e fica em [0, 1] \
| 5.2, 5.5 |
| 4 | d(A, B) = −d(B, A) | 6.2 |
| 5 | o d não muda com transformações afins de coeficiente positivo | 6.3 |
| 6 | o percentil fica em [0, 100] | 7.2 |
| 7 | nota maior ou igual tem percentil maior ou igual | 7.3 |
| 8 | a média dos percentis é 50 | 7.4 |
| 9 | a soma, nas quatro redes, de participação na amostra × razão de representação é 1 | 8.3 |
| 10 | participação igual no topo e na amostra dá razão de representação 1 | 8.4 |
| 11 | limite inferior ≤ estimativa ≤ limite superior em todos os ICs | 9.4 |
| 12 | rankings idênticos dão W de Kendall igual a 1 | 10.4 |
| 13 | o W de Kendall fica em [0, 1] | 10.5 |
| 14 | os cinco componentes do perfil relativo somam 0 | 11.2 |
| 15 | percentis iguais nas cinco áreas dão perfil relativo nulo | 11.3 |
| 16 | gravar e ler de volta o `resultados.json` dá um objeto equivalente | 14.3 |
| 17 | permutar as linhas da gold não muda os resultados (fora a data da execução) | 18.2 |

**Comportamento em cada situação de erro.**

| Situação | Comportamento |
| --- | --- |
| Gold ausente | encerra com código diferente de zero; a mensagem mostra o caminho procurado e como \
obter a gold: `uv run enem-pja3` (pipeline) ou `AZURE_STORAGE_ACCOUNT=stpanoramaenem uv run \
enem-pja3` (data lake) |
| Coluna obrigatória ausente | encerra com código diferente de zero e lista cada coluna que falta |
| Edição de 2018 a 2025 sem linhas | processa as edições disponíveis e registra a ausente no \
`resultados.json` e neste relatório |
| Taxa de preenchimento zero numa área | comparações entre redes da edição e área registradas como \
não calculadas, com o motivo |
| Grupo abaixo do tamanho mínimo | medida registrada como não calculada, com o motivo e o tamanho \
do grupo |
| Desvio-padrão combinado zero | d de Cohen registrado como não calculado, com o motivo |
| Rede sem participantes com rede informada | razão de representação registrada como não calculada |
| Volume de dados | consultas com o limite de memória `MEMORIA_DUCKDB` (4 GB); o DuckDB usa disco \
para o que não couber |
"""


def gerar_relatorio(resultados, figuras, saida) -> Path:
    """Grava saida/RELATORIO.md e devolve o caminho (Requisitos 3.4, 3.5, 4.3, 10.6, 12.4, 14.5,
    14.6, 15, 16 e 17.3).

    Lê só `resultados` (o objeto gravado no resultados.json) e `figuras` (os caminhos devolvidos
    por gerar_figuras). Cada figura entra na seção do assunto dela, pelo caminho relativo à saída;
    figura que não casa com nenhuma seção vai para "Outras figuras", então todas são citadas.
    """
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    pendentes = [_rel_caminho_figura(figura, saida) for figura in figuras or []]
    # A ordem importa: a cobertura vem antes das diferenças entre redes (Requisito 3.5), e cada
    # _rel_tomar_figuras tira suas figuras de `pendentes` antes de "Outras figuras"
    secoes = [
        _rel_secao_cabecalho(resultados),
        _rel_secao_alertas(resultados),
        _rel_secao_cobertura(resultados, _rel_tomar_figuras(pendentes, "cobertura")),
        _rel_secao_inclusao(resultados),
        _rel_secao_comparacoes(resultados, _rel_tomar_figuras(pendentes, "comparacoes")),
        _rel_secao_percentil(resultados),
        _rel_secao_topo10(resultados, _rel_tomar_figuras(pendentes, "topo10")),
        _rel_secao_ranking(resultados),
        _rel_secao_posicao_federal(resultados),
        _rel_secao_perfil(resultados, _rel_tomar_figuras(pendentes, "perfil")),
        _rel_secao_pontos(resultados),
        _rel_secao_outras_figuras(pendentes),
        _rel_secao_limitacoes(resultados),
        _REL_CAPITULO,
    ]
    destino = saida / NOME_RELATORIO
    destino.write_text(_rel_bloco(*secoes) + "\n", encoding="utf-8")
    return destino


def main(argv=None) -> int:
    args = parse_args(argv)
    con = rede_escolar.conectar()  # limite de memória MEMORIA_DUCKDB (Requisito 17.5)
    try:
        try:
            verificar_entrada(con, args.gold)
        except ErroEntrada as erro:
            print(f"Erro: {erro}", file=sys.stderr)
            return 1
        print(f"Gold: {args.gold}")
        print(f"Edições pedidas: {', '.join(map(str, args.anos))} (min_grupo={args.min_grupo})")
        resultados = rede_escolar.processar(con, args.gold, args.anos, args.min_grupo, args.semente)
    finally:
        con.close()

    resultados = adicionar_metadados(resultados, args.gold, args)
    caminho_json = gravar_json(resultados, args.saida)
    figuras = gerar_figuras(resultados, args.saida)
    caminho_relatorio = gerar_relatorio(resultados, figuras, args.saida)

    ausentes = resultados["metadados"]["edicoes_ausentes"]
    if ausentes:
        print(f"Edições sem linhas na gold: {', '.join(map(str, ausentes))}")
    print(f"Resultados: {caminho_json}")
    print(f"Relatório: {caminho_relatorio}")
    for figura in figuras:
        print(f"Figura: {figura}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
