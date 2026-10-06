# Monitoring with MLflow

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/monitoring_mlflow.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/monitoring_mlflow.ipynb)

Uses MLflow as the registry and shows what lands there: one run per version (params, metrics, artefacts, pyfunc model), a state run, and decision logs.

```bash
pip install pecca mlflow requests
jupyter lab examples/notebooks/monitoring_mlflow.ipynb
```
Runtime: ~40 s. Needs Docker: **no (local MLflow server)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
