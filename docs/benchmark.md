# Benchmark de armazenamento (ENEM 2023)

| Formato | Tamanho (MB) | % do CSV |
|---|---:|---:|
| CSV original | 1694.8 | 100% |
| Parquet, todas as colunas como texto, Snappy | 427.7 | 25.2% |
| Parquet, todas as colunas com tipo detectado, Snappy | 422.4 | 24.9% |
| Parquet, todas as colunas com tipo detectado, ZSTD | 293.1 | 17.3% |
| Parquet da silver (só colunas usadas, tipos menores, ZSTD) | 56.0 | 3.3% |

## Tempo da consulta (quartis de matemática em SC, 2023)

| Lendo de | Tempo (s) |
|---|---:|
| CSV original | 6.976 |
| Parquet da silver | 0.017 |
| Parquet da gold (8 anos) | 0.027 |
