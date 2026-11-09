# Metodologia e transparência

O Panorama ENEM é uma aplicação estatístico-descritiva. Ele **não prevê aprovação**, **não estima nota futura** e **não atribui causalidade** a diferenças observadas entre grupos.

## Contrato de dados

Campos comuns usados entre 2018 e 2025:

- `NU_ANO`
- `SG_UF_PROVA`
- `TP_ESCOLA`
- `NU_NOTA_CN`, `NU_NOTA_CH`, `NU_NOTA_LC`, `NU_NOTA_MT`
- `NU_NOTA_REDACAO`
- `Q001` a `Q025`

## Regras

- Toda estatística é calculada dentro da mesma edição.
- O percentil é empírico e usa observações válidas da área.
- Médias de grupos são descritivas; diferenças podem refletir múltiplos fatores não controlados.
- O sistema não armazena identificação de participante nem histórico individual de consulta.
- O modo demo contém dados sintéticos apenas para demonstrar o funcionamento. Resultados acadêmicos devem ser produzidos com os microdados oficiais processados pelo ETL.

## Questionário socioeconômico

A interface preserva os códigos do INEP (por exemplo, Q006 A–Q). Os valores monetários exatos de cada faixa devem ser interpretados com o dicionário da respectiva edição, pois a redação e os limites podem mudar entre anos.
