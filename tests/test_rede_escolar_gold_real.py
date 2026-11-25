"""Execução completa da análise da rede escolar sobre a gold de verdade (data/gold).

Só roda se o pipeline já gerou a gold, no mesmo padrão de tests/test_qualidade_gold.py. Os outros
testes da análise ficam em tests/test_rede_escolar.py e usam uma gold sintética.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from enem_pja3.config import DATA_DIR

NOTAS = DATA_DIR / "gold" / "enem_notas.parquet"
SCRIPT = Path(__file__).resolve().parents[1] / "analises" / "rede_escolar" / "analise.py"

pytestmark = pytest.mark.skipif(not NOTAS.exists(), reason="gold ainda não foi gerada")


def carregar_script():
    # analises/ não é pacote, então o script é importado pelo caminho do arquivo
    spec = importlib.util.spec_from_file_location("analise_rede_escolar", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_analise_completa_na_gold_real(tmp_path):
    saida = tmp_path / "saida"

    assert carregar_script().main(["--gold", str(NOTAS), "--saida", str(saida)]) == 0

    resultados = json.loads((saida / "resultados.json").read_text(encoding="utf-8"))
    assert resultados["metadados"]["edicoes_processadas"]
    assert (saida / "RELATORIO.md").is_file()
    assert len(list((saida / "figuras").glob("*.png"))) == 4
