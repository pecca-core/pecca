# Connector: schedulers

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_scheduler.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_scheduler.ipynb)

Registers cron jobs, makes a call due for retraining, runs `pecca scheduler run --once`, and generates an Airflow DAG and Databricks Workflows job JSON.

```bash
pip install pecca pyyaml
jupyter lab examples/notebooks/connector_scheduler.ipynb
```
Runtime: ~20 s. Needs Docker: **no**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
