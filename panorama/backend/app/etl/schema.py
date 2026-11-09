from __future__ import annotations

COMMON_COLUMNS = [
    "NU_ANO",
    "SG_UF_PROVA",
    "TP_ESCOLA",
    "NU_NOTA_CN",
    "NU_NOTA_CH",
    "NU_NOTA_LC",
    "NU_NOTA_MT",
    "NU_NOTA_REDACAO",
    *[f"Q{i:03d}" for i in range(1, 26)],
]

REQUIRED_COLUMNS = ["NU_ANO", "SG_UF_PROVA"]

NUMERIC_COLUMNS = [
    "NU_ANO",
    "TP_ESCOLA",
    "NU_NOTA_CN",
    "NU_NOTA_CH",
    "NU_NOTA_LC",
    "NU_NOTA_MT",
    "NU_NOTA_REDACAO",
]
