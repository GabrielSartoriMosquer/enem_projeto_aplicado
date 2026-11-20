"""Catálogo da área "Quem faz o ENEM": temas, indicadores e rótulos das respostas.

Os códigos das categorias são os que o ETL grava em gold/enem_perfil_resumo.parquet
(src/enem_pja3/load/resumo.py). Cada indicador diz:
- `categories`: as respostas na ordem do questionário, com o rótulo exibido;
- `highlight`: as respostas somadas no número de destaque e no mapa (ex.: internet = "não tem");
- `highlight_label`: o que esse percentual mede, dito para quem lê;
- `question`: a pergunta do questionário, para o balão de informação;
- `notes`: avisos que valem para uma faixa de anos (`from` / `to`, inclusive);
- `map`: False quando um mapa por UF não diz nada (região, por exemplo).
"""

from __future__ import annotations

THEMES = [
    {"id": "quem", "label": "Quem são"},
    {"id": "renda", "label": "Renda e família"},
    {"id": "conectividade", "label": "Conectividade"},
    {"id": "moradia", "label": "Moradia e bens"},
    {"id": "escola", "label": "Escola"},
]

SIM_NAO = [("sim", "Sim"), ("nao", "Não")]
NENHUM_UM_DOIS = [("nenhum", "Nenhum"), ("um", "Um"), ("dois_mais", "Dois ou mais")]
ATE_TRES = [("nenhum", "Nenhum"), ("um", "Um"), ("dois", "Dois"), ("tres_mais", "Três ou mais")]

ESCOLARIDADE = [
    ("nunca_estudou", "Nunca estudou"),
    ("fund1_incompleto", "Não completou o 5º ano"),
    ("fund1", "Completou o 5º ano, mas não o 9º"),
    ("fundamental", "Completou o fundamental, mas não o médio"),
    ("medio", "Completou o médio, mas não a faculdade"),
    ("superior", "Completou a faculdade"),
    ("pos", "Fez pós-graduação"),
    ("nao_sabe", "Não sabe"),
]

# Grupos de ocupação do questionário do INEP (Q003 e Q004), com exemplos que o próprio
# questionário dá para cada grupo.
OCUPACAO = [
    ("grupo1", "Grupo 1: lavoura, criação e pesca"),
    ("grupo2", "Grupo 2: serviços domésticos e gerais"),
    ("grupo3", "Grupo 3: indústria, construção e comércio"),
    ("grupo4", "Grupo 4: professores, técnicos e pequenos comerciantes"),
    ("grupo5", "Grupo 5: nível superior, gestão e empresários"),
    ("nao_sabe", "Não sabe"),
]

WIFI_2024 = {
    "from": 2024,
    "text": "A partir de 2024 a pergunta passou a ser sobre internet por rede wi-fi.",
}
RESPONDENTES = "Percentual entre quem respondeu à pergunta."

INDICATORS = {
    # Quem são
    "sexo": {
        "theme": "quem",
        "label": "Sexo",
        "categories": [("feminino", "Mulheres"), ("masculino", "Homens")],
        "highlight": ["feminino"],
        "highlight_label": "mulheres",
        "question": "Sexo informado na inscrição.",
    },
    "cor_raca": {
        "theme": "quem",
        "label": "Cor ou raça",
        "categories": [
            ("branca", "Branca"),
            ("preta", "Preta"),
            ("parda", "Parda"),
            ("amarela", "Amarela"),
            ("indigena", "Indígena"),
            ("nao_declarado", "Não declarada"),
        ],
        "highlight": ["preta", "parda"],
        "highlight_label": "pretos e pardos",
        "question": "Cor ou raça autodeclarada na inscrição.",
    },
    "faixa_etaria": {
        "theme": "quem",
        "label": "Idade",
        "categories": [
            ("ate_17", "Até 17 anos"),
            ("18", "18 anos"),
            ("19_20", "19 e 20 anos"),
            ("21_25", "21 a 25 anos"),
            ("26_30", "26 a 30 anos"),
            ("31_40", "31 a 40 anos"),
            ("41_mais", "41 anos ou mais"),
        ],
        "highlight": ["21_25", "26_30", "31_40", "41_mais"],
        "highlight_label": "com 21 anos ou mais",
        "question": "Faixa etária informada pelo INEP.",
    },
    "situacao_em": {
        "theme": "quem",
        "label": "Ensino médio",
        "categories": [
            ("concluido", "Já concluiu"),
            ("concluindo", "Conclui no ano da prova"),
            ("depois", "Conclui depois do ano da prova"),
            ("nao_cursando", "Não concluiu e não está cursando"),
        ],
        "highlight": ["concluido"],
        "highlight_label": "que já tinham concluído o ensino médio",
        "question": "Situação de conclusão do ensino médio informada na inscrição.",
    },
    "treineiro": {
        "theme": "quem",
        "label": "Treineiros",
        "categories": [("sim", "Treineiro"), ("nao", "Não é treineiro")],
        "highlight": ["sim"],
        "highlight_label": "treineiros",
        "question": (
            "Treineiro é quem faz a prova só para treinar, antes de terminar o ensino médio."
        ),
    },
    "regiao": {
        "theme": "quem",
        "label": "Região",
        "categories": [
            ("norte", "Norte"),
            ("nordeste", "Nordeste"),
            ("centro_oeste", "Centro-Oeste"),
            ("sudeste", "Sudeste"),
            ("sul", "Sul"),
        ],
        "highlight": ["nordeste"],
        "highlight_label": "no Nordeste",
        "question": "Região do estado onde a pessoa fez a prova.",
        "map": False,
    },
    # Renda e família
    "renda_familiar": {
        "theme": "renda",
        "label": "Renda da família",
        "categories": [
            ("nenhuma", "Nenhuma renda"),
            ("ate_1", "Até 1 salário mínimo"),
            ("1_2", "De 1 a 2 salários"),
            ("2_3", "De 2 a 3 salários"),
            ("3_5", "De 3 a 5 salários"),
            ("5_10", "De 5 a 10 salários"),
            ("10_20", "De 10 a 20 salários"),
            ("mais_20", "Mais de 20 salários"),
        ],
        "highlight": ["nenhuma", "ate_1"],
        "highlight_label": "com renda familiar de até 1 salário mínimo",
        "question": (
            "Qual é a renda mensal de sua família? "
            "As faixas do INEP seguem o salário mínimo do ano da prova."
        ),
        "notes": [{"text": RESPONDENTES}],
    },
    "escolaridade_mae": {
        "theme": "renda",
        "label": "Escolaridade da mãe",
        "categories": ESCOLARIDADE,
        "highlight": ["nunca_estudou", "fund1_incompleto", "fund1"],
        "highlight_label": "cujas mães não completaram o ensino fundamental",
        "question": "Até que série sua mãe, ou a mulher responsável por você, estudou?",
    },
    "escolaridade_pai": {
        "theme": "renda",
        "label": "Escolaridade do pai",
        "categories": ESCOLARIDADE,
        "highlight": ["nunca_estudou", "fund1_incompleto", "fund1"],
        "highlight_label": "cujos pais não completaram o ensino fundamental",
        "question": "Até que série seu pai, ou o homem responsável por você, estudou?",
    },
    "ocupacao_mae": {
        "theme": "renda",
        "label": "Ocupação da mãe",
        "categories": OCUPACAO,
        "highlight": ["grupo5"],
        "highlight_label": "cujas mães trabalham em ocupações de nível superior ou gestão",
        "question": (
            "Grupo de ocupação da mãe, ou da mulher responsável, "
            "segundo os grupos do questionário do INEP."
        ),
    },
    "ocupacao_pai": {
        "theme": "renda",
        "label": "Ocupação do pai",
        "categories": OCUPACAO,
        "highlight": ["grupo5"],
        "highlight_label": "cujos pais trabalham em ocupações de nível superior ou gestão",
        "question": (
            "Grupo de ocupação do pai, ou do homem responsável, "
            "segundo os grupos do questionário do INEP."
        ),
    },
    "pessoas_casa": {
        "theme": "renda",
        "label": "Pessoas na casa",
        "categories": [
            ("1", "Mora sozinho(a)"),
            ("2", "2 pessoas"),
            ("3", "3 pessoas"),
            ("4", "4 pessoas"),
            ("5", "5 pessoas"),
            ("6_mais", "6 ou mais"),
        ],
        "highlight": ["5", "6_mais"],
        "highlight_label": "que moram em casas com 5 pessoas ou mais",
        "question": "Incluindo você, quantas pessoas moram atualmente em sua residência?",
    },
    "renda_propria": {
        "theme": "renda",
        "label": "Renda própria",
        "categories": SIM_NAO,
        "highlight": ["sim"],
        "highlight_label": "que têm renda própria",
        "question": "Você possui renda? Pergunta incluída no questionário em 2024.",
        "notes": [{"to": 2023, "text": "Esta pergunta só existe a partir de 2024."}],
    },
    # Conectividade
    "internet": {
        "theme": "conectividade",
        "label": "Internet em casa",
        "categories": SIM_NAO,
        "highlight": ["nao"],
        "highlight_label": "sem internet em casa",
        "question": "Na sua residência tem acesso à internet?",
        "notes": [WIFI_2024],
    },
    "computador": {
        "theme": "conectividade",
        "label": "Computador em casa",
        "categories": NENHUM_UM_DOIS,
        "highlight": ["nenhum"],
        "highlight_label": "sem computador em casa",
        "question": "Na sua residência tem computador (ou notebook, a partir de 2024)?",
    },
    "celular": {
        "theme": "conectividade",
        "label": "Celular em casa",
        "categories": ATE_TRES,
        "highlight": ["nenhum"],
        "highlight_label": "em casas sem nenhum celular",
        "question": "Na sua residência tem telefone celular?",
    },
    "tv_assinatura": {
        "theme": "conectividade",
        "label": "TV por assinatura",
        "categories": SIM_NAO,
        "highlight": ["sim"],
        "highlight_label": "com TV por assinatura",
        "question": "Na sua residência tem TV por assinatura?",
    },
    # Moradia e bens
    "carro": {
        "theme": "moradia",
        "label": "Carro",
        "categories": NENHUM_UM_DOIS,
        "highlight": ["nenhum"],
        "highlight_label": "em casas sem carro",
        "question": "Na sua residência tem carro?",
    },
    "moto": {
        "theme": "moradia",
        "label": "Moto",
        "categories": SIM_NAO,
        "highlight": ["sim"],
        "highlight_label": "em casas com moto",
        "question": "Na sua residência tem motocicleta?",
    },
    "banheiros": {
        "theme": "moradia",
        "label": "Banheiros",
        "categories": ATE_TRES,
        "highlight": ["nenhum"],
        "highlight_label": "em casas sem banheiro",
        "question": "Na sua residência tem banheiro?",
    },
    "quartos": {
        "theme": "moradia",
        "label": "Quartos",
        "categories": ATE_TRES,
        "highlight": ["nenhum", "um"],
        "highlight_label": "em casas com no máximo 1 quarto",
        "question": "Na sua residência tem quartos para dormir?",
    },
    "empregada": {
        "theme": "moradia",
        "label": "Empregada doméstica",
        "categories": [
            ("nao", "Não"),
            ("1_2_dias", "1 ou 2 dias por semana"),
            ("3_4_dias", "3 ou 4 dias por semana"),
            ("5_dias", "5 dias ou mais"),
        ],
        "highlight": ["1_2_dias", "3_4_dias", "5_dias"],
        "highlight_label": "com empregada doméstica em casa",
        "question": "Em sua residência trabalha empregado(a) doméstico(a)?",
    },
    "maquina_lavar": {
        "theme": "moradia",
        "label": "Máquina de lavar",
        "categories": SIM_NAO,
        "highlight": ["nao"],
        "highlight_label": "em casas sem máquina de lavar roupa",
        "question": "Na sua residência tem máquina de lavar roupa? (o tanquinho não conta)",
    },
    "micro_ondas": {
        "theme": "moradia",
        "label": "Micro-ondas",
        "categories": SIM_NAO,
        "highlight": ["nao"],
        "highlight_label": "em casas sem micro-ondas",
        "question": "Na sua residência tem forno micro-ondas?",
    },
    "geladeira": {
        "theme": "moradia",
        "label": "Geladeira",
        "categories": SIM_NAO,
        "highlight": ["nao"],
        "highlight_label": "em casas sem geladeira",
        "question": "Na sua residência tem geladeira?",
    },
    # Escola
    "tipo_escola": {
        "theme": "escola",
        "label": "Tipo de escola",
        "categories": [
            ("publica", "Só escola pública"),
            ("privada", "Só escola privada"),
            ("mista", "Parte pública, parte privada"),
            ("exterior", "No exterior"),
            ("nao_frequentou", "Não frequentou o ensino médio"),
        ],
        "highlight": ["publica"],
        "highlight_label": "que estudaram só em escola pública",
        "question": "Em que tipo de escola você frequentou o ensino médio?",
        "notes": [
            {
                "to": 2023,
                "text": (
                    "Até 2023 só parte dos inscritos informava o tipo de escola; "
                    "os percentuais são de quem informou."
                ),
            }
        ],
    },
}

# Recortes dos cruzamentos (gravados pelo ETL só no total do Brasil)
RECORTES = {
    "renda": {
        "label": "Renda da família",
        "categories": [
            ("ate_1", "Até 1 salário"),
            ("1_3", "1 a 3 salários"),
            ("3_5", "3 a 5 salários"),
            ("5_10", "5 a 10 salários"),
            ("mais_10", "Mais de 10 salários"),
        ],
    },
    "cor_raca": {"label": "Cor ou raça", "categories": INDICATORS["cor_raca"]["categories"]},
    "sexo": {"label": "Sexo", "categories": INDICATORS["sexo"]["categories"]},
    "tipo_escola": {
        "label": "Tipo de escola",
        "categories": [("publica", "Escola pública"), ("privada", "Escola privada")],
    },
}
