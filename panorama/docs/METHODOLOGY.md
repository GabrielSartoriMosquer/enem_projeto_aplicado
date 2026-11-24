# Metodologia e transparência

O Panorama ENEM é uma aplicação estatístico-descritiva. Ele **não prevê aprovação**, **não estima nota futura** e **não atribui causalidade** a diferenças observadas entre grupos.

## Contrato de dados

Campos ligados à nota em todas as edições, de 2018 a 2025:

- `NU_ANO`
- `SG_UF_PROVA`
- `NU_NOTA_CN`, `NU_NOTA_CH`, `NU_NOTA_LC`, `NU_NOTA_MT`
- `NU_NOTA_REDACAO`

Ligados à nota só de 2018 a 2023, porque a partir de 2024 o INEP publica perfil e nota em arquivos
sem ligação:

- tipo de escola informado no questionário (`TP_ESCOLA`)
- escolaridade dos pais e renda da família (`Q001`, `Q002` e `Q006`)

## Regras

- Toda estatística é calculada dentro da mesma edição.
- O percentil é empírico e usa observações válidas da área.
- Médias de grupos são descritivas; diferenças podem refletir múltiplos fatores não controlados.
- O sistema não armazena identificação de participante nem histórico individual de consulta.
- O modo demo contém dados sintéticos apenas para demonstrar o funcionamento. Resultados acadêmicos devem ser produzidos com os microdados oficiais processados pelo ETL.

## Questionário socioeconômico

A interface preserva os códigos do INEP (por exemplo, Q006 A–Q). Os valores monetários exatos de cada faixa devem ser interpretados com o dicionário da respectiva edição, pois a redação e os limites podem mudar entre anos.

## Modelo de probabilidade condicional (nota e renda)

Código em `backend/app/services/income_model.py`; rota `POST /analysis/income-probability`.

Para uma nota `x` e uma faixa de renda `r`:

- `P(r)`: participantes da faixa / participantes com nota e renda;
- `P(X >= x | r)`: participantes da faixa com nota maior ou igual a `x` / participantes da faixa;
- `P(X >= x)`: soma de `P(r) * P(X >= x | r)` em todas as faixas (probabilidade total);
- `P(r | X >= x)`: `P(r) * P(X >= x | r) / P(X >= x)` (Teorema de Bayes).

Regras:

- só edições de 2018 a 2023;
- entra quem tem nota válida na área e respondeu a renda; nota zero em prova objetiva fica fora,
  como no resto do site;
- as 17 respostas da renda viram cinco faixas: A–B, C–D, E–G, H–M e N–Q;
- grupo com menos de 100 pessoas não é exibido; com menos de 100 pessoas acima da nota, a divisão
  por renda também não;
- erro padrão de `P(X >= x | r)`: `sqrt(p * (1 - p) / n)`;
- o cenário "escola privada e renda acima de 10 salários" só inclui quem informou o tipo de escola.

Bayes usa as mesmas contagens da divisão direta, então a igualdade entre os dois confere a conta, e
não prova que o resultado vale para outra edição. Quem faltou não tem nota e não entra.
