# Connector: registry

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_registry.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_registry.ipynb)

Trains and promotes the same call against the `local` and `mlflow` registries and shows that versions, state and predictions are identical.

```bash
pip install pecca mlflow requests
jupyter lab examples/notebooks/connector_registry.ipynb
```
Runtime: ~35 s. Needs Docker: **no (starts a local MLflow server process)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
