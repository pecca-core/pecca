# Connector: data sources

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_datasource.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_datasource.ipynb)

Reads the same 2,000 rows from CSV, Parquet, a throwaway `postgres:16-alpine` container and OTLP trace exports, showing how `since`/`limit` are pushed down into SQL.

```bash
pip install pecca psycopg[binary]
jupyter lab examples/notebooks/connector_datasource.ipynb
```
Runtime: ~10 s. Needs Docker: **yes (Postgres container; SQLite fallback otherwise)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
