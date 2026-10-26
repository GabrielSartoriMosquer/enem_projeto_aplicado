# Volumetria do pipeline

Tamanhos em MB.

| Ano | Linhas | Zip do INEP | CSV (bronze) | Parquet (silver) |
|---|---:|---:|---:|---:|
| 2023 | 3933955 | 524.1 | 1695.1 | 56.0 |
| 2024 | 4332944 | 501.7 | 2046.4 | 62.4 |
| **Total** | **8266899** | **1025.8** | **3741.5** | **118.4** |

## Arquivos finais (gold)

| Arquivo | Linhas | Tamanho (MB) |
|---|---:|---:|
| enem_notas.parquet | 8266899 | 63.5 |
| enem_perfil.parquet | 8266899 | 61.6 |

Gold total: 125.1 MB, contra 3741.5 MB de CSV (redução de 96.7%).
