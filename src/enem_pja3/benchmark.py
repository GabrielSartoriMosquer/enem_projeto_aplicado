"""
Testa algumas formas de salvar o CSV de 2023 em Parquet e compara o tamanho de cada uma.
Também mede quanto tempo leva uma consulta parecida com a do app lendo do CSV e do Parquet.

Rodar depois do pipeline: python -m enem_pja3.benchmark
"""
import time

from enem_pja3.config import DATA_DIR
from enem_pja3.transform.transform import SELECT_MICRODADOS, conectar, ler_csv
from enem_pja3.volumetria import PASTA_DOCS, tamanho_mb

ANO = 2023
CSV = DATA_DIR / "bronze" / "csv" / f"ano={ANO}" / f"MICRODADOS_ENEM_{ANO}.csv"
PASTA_TESTE = DATA_DIR / "benchmark"

# Quartis da nota de matemática em SC e quantos % tiraram menos de 700
CONSULTA = """
SELECT
    quantile_cont(CAST(NU_NOTA_MT AS DOUBLE), [0.25, 0.5, 0.75]) AS quartis,
    avg(CASE WHEN CAST(NU_NOTA_MT AS DOUBLE) < 700 THEN 1 ELSE 0 END) AS abaixo_de_700
FROM {fonte}
WHERE SG_UF_PROVA = 'SC' AND TP_PRESENCA_MT = 1 {filtro}
"""


def main():
    con = conectar()
    PASTA_TESTE.mkdir(parents=True, exist_ok=True)

    testes = [
        ("Parquet, todas as colunas como texto, Snappy", f"SELECT * FROM {ler_csv(CSV)}", "snappy"),
        ("Parquet, todas as colunas com tipo detectado, Snappy", f"SELECT * FROM {ler_csv(CSV, all_varchar=False)}", "snappy"),
        ("Parquet, todas as colunas com tipo detectado, ZSTD", f"SELECT * FROM {ler_csv(CSV, all_varchar=False)}", "zstd"),
        ("Parquet da silver (só colunas usadas, tipos menores, ZSTD)", f"{SELECT_MICRODADOS} FROM {ler_csv(CSV)}", "zstd"),
    ]

    texto = f"# Benchmark de armazenamento (ENEM {ANO})\n\n"
    texto += "| Formato | Tamanho (MB) | % do CSV |\n|---|---:|---:|\n"
    texto += f"| CSV original | {tamanho_mb(CSV):.1f} | 100% |\n"
    for i, (nome, select, compressao) in enumerate(testes):
        arquivo = PASTA_TESTE / f"teste_{i}.parquet"
        con.sql(f"COPY ({select}) TO '{arquivo}' (FORMAT parquet, COMPRESSION {compressao})")
        texto += f"| {nome} | {tamanho_mb(arquivo):.1f} | {100 * tamanho_mb(arquivo) / tamanho_mb(CSV):.1f}% |\n"
        arquivo.unlink()

    fontes = [
        ("CSV original", ler_csv(CSV), ""),
        ("Parquet da silver", f"'{DATA_DIR}/silver/enem/ano={ANO}/dados.parquet'", ""),
        ("Parquet da gold (8 anos)", f"'{DATA_DIR}/gold/enem_notas.parquet'", f"AND NU_ANO = {ANO}"),
    ]
    texto += f"\n## Tempo da consulta (quartis de matemática em SC, {ANO})\n\n| Lendo de | Tempo (s) |\n|---|---:|\n"
    for nome, fonte, filtro in fontes:
        inicio = time.time()
        con.sql(CONSULTA.format(fonte=fonte, filtro=filtro)).fetchall()
        texto += f"| {nome} | {time.time() - inicio:.3f} |\n"

    PASTA_DOCS.mkdir(exist_ok=True)
    (PASTA_DOCS / "benchmark.md").write_text(texto)
    print(texto)


if __name__ == "__main__":
    main()
