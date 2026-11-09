# Arquitetura — Panorama ENEM

```text
INEP (ZIP/CSV)
      |
      v
ETL Python em chunks
      |
      v
Parquet ZSTD particionado por ano  ---> armazenamento de objeto (produção)
      |
      v
DuckDB (consulta analítica com partition pruning)
      |
      v
FastAPI /api/v1
      |
      v
React + Vite + Nginx
```

## Decisões

- **Parquet + ZSTD** reduz I/O e mantém esquema colunar adequado a consultas analíticas.
- **Partição por edição** evita comparar nota bruta entre anos e permite pruning no DuckDB.
- **DuckDB** executa agregações diretamente nos Parquets sem manter um servidor de banco analítico dedicado.
- **FastAPI** separa regras estatísticas da interface e oferece documentação OpenAPI automática.
- **React/Vite** entrega interface responsiva e modular.
- **Modo demo** garante execução imediata do sistema sem os ~35 milhões de registros. Quando os Parquets oficiais existem, a API muda automaticamente para eles.

## Fluxo de consulta

1. O usuário seleciona uma edição.
2. A API restringe a consulta a `NU_ANO` daquela edição.
3. Nulos da métrica analisada são excluídos apenas daquela análise.
4. Percentil empírico = `100 * count(nota <= nota_usuario) / count(nota válida)`.
5. Z-score usa média e desvio-padrão populacional da mesma edição.
