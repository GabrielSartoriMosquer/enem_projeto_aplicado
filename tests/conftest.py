import pytest

from enem_pja3.extract import extract_zips
from enem_pja3.load import load
from enem_pja3.transform import transform

# Colunas que o transform usa (formato antigo, até 2023). Os CSVs de teste são bem menores que os
# do INEP, mas têm o mesmo jeito: latin-1, separados por ';' e com campos vazios.
COLUNAS_ANTIGO = [
    "NU_INSCRICAO", "NU_ANO", "TP_FAIXA_ETARIA", "TP_SEXO", "TP_COR_RACA", "TP_ST_CONCLUSAO",
    "TP_ESCOLA", "IN_TREINEIRO", "NO_MUNICIPIO_ESC", "TP_DEPENDENCIA_ADM_ESC", "TP_LOCALIZACAO_ESC",
    "SG_UF_PROVA", "TP_PRESENCA_CN", "TP_PRESENCA_CH", "TP_PRESENCA_LC", "TP_PRESENCA_MT",
    "NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "TP_LINGUA",
    "NU_NOTA_REDACAO", "TP_STATUS_REDACAO", "Q001", "Q002", "Q006",
]

COLUNAS_PARTICIPANTES = [
    "NU_INSCRICAO", "NU_ANO", "TP_FAIXA_ETARIA", "TP_SEXO", "TP_COR_RACA", "TP_ST_CONCLUSAO",
    "IN_TREINEIRO", "SG_UF_PROVA", "Q001", "Q002", "Q006", "Q007", "Q023",
]

COLUNAS_RESULTADOS = [
    "NU_SEQUENCIAL", "NU_ANO", "TP_DEPENDENCIA_ADM_ESC", "TP_LOCALIZACAO_ESC", "SG_UF_PROVA",
    "TP_PRESENCA_CN", "TP_PRESENCA_CH", "TP_PRESENCA_LC", "TP_PRESENCA_MT",
    "NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "TP_LINGUA",
    "NU_NOTA_REDACAO", "TP_STATUS_REDACAO",
]


@pytest.fixture
def dados(tmp_path, monkeypatch):
    """Faz o pipeline usar uma pasta temporária no lugar de data/"""
    monkeypatch.setattr(transform, "DATA_DIR", tmp_path)
    monkeypatch.setattr(extract_zips, "DATA_DIR", tmp_path)
    monkeypatch.setattr(load, "SILVER", tmp_path / "silver")
    monkeypatch.setattr(load, "GOLD", tmp_path / "gold")
    return tmp_path


def escrever_csv(caminho, colunas, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = ";".join(colunas) + "\n" + "\n".join(";".join(linha) for linha in linhas) + "\n"
    caminho.write_bytes(texto.encode("latin-1"))
