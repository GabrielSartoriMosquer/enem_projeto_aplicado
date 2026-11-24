"""Modelo de probabilidade condicional entre nota e renda da família.

Responde a duas perguntas diferentes para uma nota x e uma faixa de renda r:

1. P(X >= x | r): entre quem tem a renda r, quantos tiram pelo menos x?
2. P(r | X >= x): entre quem tira pelo menos x, quantos têm a renda r?

A primeira sai da contagem. A segunda sai do Teorema de Bayes:

    P(X >= x)     = soma, em todas as faixas, de P(r) * P(X >= x | r)   (probabilidade total)
    P(r | X >= x) = P(r) * P(X >= x | r) / P(X >= x)                    (Bayes)

É um retrato da edição escolhida: descreve grupos, não prevê nota e não indica causa.
Este arquivo só faz conta; quem lê os dados é o data_engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Nota e renda só estão na mesma linha nestas edições (a partir de 2024 o INEP separa os arquivos).
FIRST_LINKED_YEAR = 2018
LAST_LINKED_YEAR = 2023

# Grupo menor que isso não é exibido: a proporção oscila demais e expõe poucas pessoas.
MIN_GROUP_SIZE = 100


@dataclass(frozen=True)
class IncomeBand:
    code: str
    label: str
    q006: str  # códigos A a Q da pergunta de renda que entram na faixa


# As 17 respostas do questionário viram 5 faixas: todas com muita gente e a conta cabe no papel.
INCOME_BANDS = (
    IncomeBand("ate_1", "Até 1 salário mínimo", "AB"),
    IncomeBand("1_a_2", "De 1 a 2 salários mínimos", "CD"),
    IncomeBand("2_a_4", "De 2 a 4 salários mínimos", "EFG"),
    IncomeBand("4_a_10", "De 4 a 10 salários mínimos", "HIJKLM"),
    IncomeBand("mais_10", "Mais de 10 salários mínimos", "NOPQ"),
)

# Cenário de comparação do plano da UC: escola privada (código 3) e renda alta.
REFERENCE_BAND = "mais_10"
REFERENCE_SCHOOL = 3
REFERENCE_LABEL = "Escola privada e renda acima de 10 salários mínimos"


@dataclass(frozen=True)
class GroupCount:
    n: int  # pessoas com nota válida no grupo
    n_ge: int  # com nota maior ou igual a x
    n_le: int  # com nota menor ou igual a x (percentil, como no resto do site)


def band_of(q006: str) -> str:
    for band in INCOME_BANDS:
        if q006 in band.q006:
            return band.code
    raise ValueError(f"Faixa de renda desconhecida: {q006}")


def check_linked_year(year: int) -> None:
    if not FIRST_LINKED_YEAR <= year <= LAST_LINKED_YEAR:
        raise ValueError(
            f"Nota e renda só podem ser cruzadas nas edições de {FIRST_LINKED_YEAR} a "
            f"{LAST_LINKED_YEAR}. Depois disso o INEP publica as duas em arquivos sem ligação."
        )


def group_percentile(count: GroupCount) -> float | None:
    return 100 * count.n_le / count.n if count.n >= MIN_GROUP_SIZE else None


def income_probability(counts: dict[str, GroupCount]) -> dict[str, Any]:
    """Aplica probabilidade total e Bayes às contagens de cada faixa de renda."""
    groups = {band.code: counts.get(band.code, GroupCount(0, 0, 0)) for band in INCOME_BANDS}
    total = sum(group.n for group in groups.values())
    if total == 0:
        raise ValueError("Não há participantes com nota e renda nesta edição.")

    bands = []
    for band in INCOME_BANDS:
        group = groups[band.code]
        prior = group.n / total  # P(r)
        likelihood = se = joint = None
        if group.n >= MIN_GROUP_SIZE:
            likelihood = group.n_ge / group.n  # P(X >= x | r)
            se = math.sqrt(likelihood * (1 - likelihood) / group.n)
            joint = prior * likelihood  # P(r) * P(X >= x | r)
        bands.append(
            {
                "code": band.code,
                "label": band.label,
                "n": group.n,
                "prior": prior,
                "likelihood": likelihood,
                "likelihood_se": se,
                "joint": joint,
                "posterior": None,
                "representation": None,
                "percentile": group_percentile(group),
            }
        )

    # Probabilidade total: só existe se todas as parcelas existem.
    joints = [band["joint"] for band in bands]
    total_probability = None if None in joints else sum(joints)

    # Bayes: com pouca gente acima da nota, as fatias por renda oscilam demais (e com zero
    # pessoas haveria divisão por zero).
    above = sum(group.n_ge for group in groups.values())
    bayes_available = total_probability is not None and above >= MIN_GROUP_SIZE
    if bayes_available:
        for band in bands:
            band["posterior"] = band["joint"] / total_probability
            band["representation"] = band["posterior"] / band["prior"]

    return {
        "n": total,
        "n_above": above,
        "percentile": 100 * sum(group.n_le for group in groups.values()) / total,
        "total_probability": total_probability,
        "bayes_available": bayes_available,
        "bands": bands,
    }
