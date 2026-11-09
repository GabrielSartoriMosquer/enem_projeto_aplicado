# Matriz de atendimento do plano

| Requisito do plano | Implementação |
|---|---|
| Edições 2018–2025 | ETL parametrizado e partição por `NU_ANO` |
| Aproximadamente 35 milhões de registros | Processamento em chunks, sem exigir carga integral em RAM |
| Parquet particionado | `backend/app/etl/transform.py` |
| Percentil e medidas de dispersão | `services/statistics.py` e engine DuckDB |
| Quatro módulos de análise | Endpoints REST + quatro telas React |
| API | FastAPI com Swagger/OpenAPI |
| Interface responsiva | React/Vite, CSS responsivo e navegação por teclado |
| Dados anônimos | Sem autenticação e sem histórico de consultas |
| Docker | `docker-compose.yml` |
| Cobertura mínima de 60% | suíte atual: 72% no ambiente de validação |
| Nuvem | base Terraform para S3; compute fica condicionado aos testes de volumetria |

## Itens que precisam de validação com a base oficial

As metas de **pipeline completo em até 2 horas** e **consulta p95 em até 3 segundos** dependem do volume real, hardware e infraestrutura de nuvem. O código inclui arquitetura e filtros necessários para perseguir essas metas, mas elas só podem ser consideradas comprovadas após benchmark com os microdados oficiais.
