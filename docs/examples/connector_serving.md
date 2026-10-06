# Connector: serving targets

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_serving.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_serving.ipynb)

Benchmarks in-process serving (pickle vs ONNX head) and shows the `docker_export` folder: Dockerfile, FastAPI app, requirements and model.

```bash
pip install pecca 
jupyter lab examples/notebooks/connector_serving.ipynb
```
Runtime: ~15 s. Needs Docker: **no (the `docker build` is shown, not run)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
