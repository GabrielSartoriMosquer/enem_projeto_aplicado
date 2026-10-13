from pathlib import Path

import duckdb

from enem_pja3.config import ANOS, ANOS_FORMATO_ANTIGO, DATA_DIR

PASTA_DOCS = Path(__file__).parent.parent.parent / "docs"


def tamanho_mb(caminho: Path) -> float:
    if caminho.is_file():
        return caminho.stat().st_size / 1024 / 1024
    return sum(f.stat().st_size for f in caminho.rglob("*") if f.is_file()) / 1024 / 1024


def contar_linhas(parquet: Path) -> int:
    return duckdb.sql(f"SELECT count(*) FROM '{parquet}'").fetchone()[0]


def gerar_volumetria() -> str:
    """Mede o tamanho de cada camada e salva a tabela em docs/volumetria.md"""
    texto = "# Volumetria do pipeline\n\nTamanhos em MB.\n\n"
    texto += "| Ano | Linhas | Zip do INEP | CSV (bronze) | Parquet (silver) |\n"
    texto += "|---|---:|---:|---:|---:|\n"

    total_linhas, total_zip, total_csv, total_silver = 0, 0, 0, 0
    for ano in ANOS:
        zip_mb = tamanho_mb(DATA_DIR / "bronze" / "zips" / f"microdados_enem_{ano}.zip")
        csv_mb = tamanho_mb(DATA_DIR / "bronze" / "csv" / f"ano={ano}")
        silver_mb = sum(tamanho_mb(p) for p in DATA_DIR.glob(f"silver/*/ano={ano}/dados.parquet"))

        # Número de inscritos: no formato novo contamos pelo arquivo de resultados
        tabela = "enem" if ano in ANOS_FORMATO_ANTIGO else "resultados"
        linhas = contar_linhas(DATA_DIR / "silver" / tabela / f"ano={ano}" / "dados.parquet")

        texto += f"| {ano} | {linhas} | {zip_mb:.1f} | {csv_mb:.1f} | {silver_mb:.1f} |\n"
        total_linhas += linhas
        total_zip += zip_mb
        total_csv += csv_mb
        total_silver += silver_mb

    texto += f"| **Total** | **{total_linhas}** | **{total_zip:.1f}** | **{total_csv:.1f}** | **{total_silver:.1f}** |\n"

    texto += "\n## Arquivos finais (gold)\n\n| Arquivo | Linhas | Tamanho (MB) |\n|---|---:|---:|\n"
    total_gold = 0
    for arquivo in sorted((DATA_DIR / "gold").glob("*.parquet")):
        texto += f"| {arquivo.name} | {contar_linhas(arquivo)} | {tamanho_mb(arquivo):.1f} |\n"
        total_gold += tamanho_mb(arquivo)

    reducao = 100 * (1 - total_gold / total_csv)
    texto += f"\nGold total: {total_gold:.1f} MB, contra {total_csv:.1f} MB de CSV (redução de {reducao:.1f}%).\n"

    PASTA_DOCS.mkdir(exist_ok=True)
    (PASTA_DOCS / "volumetria.md").write_text(texto)
    return texto


if __name__ == "__main__":
    print(gerar_volumetria())
