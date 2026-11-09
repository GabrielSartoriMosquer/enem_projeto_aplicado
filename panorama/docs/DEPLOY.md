# Implantação

## Local com Docker

```bash
docker compose up --build
```

- Frontend: `http://localhost:8080`
- API: `http://localhost:8000/docs`

## Dados oficiais

```bash
python -m app.etl.cli all --years 2025
# ou
python -m app.etl.cli all --years 2018-2025
```

Após gerar `backend/data/parquet/ano=YYYY/enem.parquet`, reinicie a API. Em `PANORAMA_DATA_MODE=auto`, ela detecta Parquet e deixa o modo demonstração automaticamente.

## Produção em nuvem

Recomendação de referência:

- objetos Parquet: Amazon S3;
- containers: ECS Fargate ou serviço equivalente;
- frontend: Nginx/CloudFront;
- observabilidade: CloudWatch;
- CI: GitHub Actions.

O diretório `infra/terraform` contém uma base segura para o bucket de dados. A camada de compute pode ser ajustada após testes de volumetria, como previsto no plano do projeto.
