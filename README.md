# Panorama ENEM - Pipeline de ETL

Pipeline que baixa os microdados do ENEM de 2018 a 2025 do site do INEP, extrai os CSVs,
converte para Parquet e junta tudo em arquivos menores que o app usa para calcular percentil e Z-Score.

## Arquitetura

Usamos a ideia de camadas bronze, silver e gold:

```mermaid
flowchart LR
    INEP[(Site do INEP)] -->|download| ZIP

    subgraph Bronze
        ZIP[zips/microdados_enem_AAAA.zip]
        CSV[csv/ano=AAAA/*.csv]
        ZIP -->|extract| CSV
    end

    subgraph Silver
        ENEM[enem/ano=2018..2023]
        PART[participantes/ano=2024..2025]
        RES[resultados/ano=2024..2025]
    end

    CSV -->|transform com DuckDB| ENEM
    CSV --> PART
    CSV --> RES

    subgraph Gold
        NOTAS[enem_notas.parquet]
        PERFIL[enem_perfil.parquet]
    end

    ENEM -->|load| NOTAS
    RES --> NOTAS
    ENEM --> PERFIL
    PART --> PERFIL
```

- **Bronze** (`data/bronze/`): o zip como veio do INEP e os CSVs da pasta `DADOS/` do zip.
- **Silver** (`data/silver/`): um Parquet por ano, só com as colunas que vamos usar, com tipos
  menores (ex.: `UTINYINT` para códigos, `DECIMAL(5,1)` para notas) e compressão ZSTD.
- **Gold** (`data/gold/`): os 8 anos juntos em dois arquivos, ordenados por ano e UF.

Os tamanhos de cada camada estão em [docs/volumetria.md](docs/volumetria.md) e a comparação
entre formatos em [docs/benchmark.md](docs/benchmark.md).

## Como rodar

Com Docker (os dados ficam na pasta `./data`):

```bash
docker compose build
docker compose run --rm etl
```

Sem Docker, com o [uv](https://docs.astral.sh/uv/) (precisa ter o `unzip` instalado):

```bash
uv sync
uv run enem-pja3              # todos os anos
uv run enem-pja3 2023 2024    # só alguns anos
uv run python -m enem_pja3.benchmark
```

Se o pipeline parar no meio, é só rodar de novo: zips e CSVs que já existem são pulados.

## Arquivos

- `src/enem_pja3/config.py`: anos, link do INEP e pasta dos dados
- `src/enem_pja3/extract/download_zips.py`: download dos zips
- `src/enem_pja3/extract/extract_zips.py`: extração dos CSVs
- `src/enem_pja3/transform/transform.py`: CSV para Parquet (silver)
- `src/enem_pja3/load/load.py`: junta os anos na gold
- `src/enem_pja3/volumetria.py`: mede o tamanho de cada camada
- `src/enem_pja3/pipeline.py`: roda tudo em sequência

## Problemas que encontramos nos dados

- **Formato mudou em 2024.** Até 2023 era um CSV só por ano. Em 2024 e 2025 são dois:
  `PARTICIPANTES` (perfil e questionário) e `RESULTADOS` (escola e notas), e não tem coluna
  que ligue um ao outro. Então só dá para cruzar nota com perfil socioeconômico de 2018 a 2023.
- **Questionário muda de um ano para outro.** 2018 tem 27 perguntas, 2019 a 2023 têm 25 e
  2024/2025 têm 23. A mesma coluna (ex.: `Q006`) pode ser outra pergunta em outro ano, então
  é preciso olhar o dicionário de cada ano antes de comparar.
- **Certificado do site do INEP.** O servidor não manda o certificado intermediário e o
  `requests` dá erro de SSL. Em vez de desligar a verificação, salvamos esse certificado em
  `src/enem_pja3/certs/`.
- **Zip de 2025.** O `RESULTADOS_2025.csv` está compactado em Deflate64, que o Python não abre.
  Para esse arquivo usamos o `unzip` do sistema.
- **Memória.** Sem limite, o DuckDB passou de 20 GB de RAM ao montar a gold e o processo foi
  morto pelo sistema. Colocamos limite de 4 GB; o que passar disso ele grava em disco.
- **Leitura do CSV em paralelo.** Com encoding latin-1, a leitura em paralelo do DuckDB às vezes
  misturava duas linhas e dava erro. Lendo em série o problema não acontece.
