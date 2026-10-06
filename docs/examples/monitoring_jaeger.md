# Monitoring with Jaeger

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/monitoring_jaeger.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/monitoring_jaeger.ipynb)

Runs shadow calls with OTLP export to a local Jaeger and reads the `pecca.call` spans back through Jaeger's API.

```bash
pip install pecca requests
jupyter lab examples/notebooks/monitoring_jaeger.ipynb
```
Runtime: ~20 s. Needs Docker: **yes (`examples/monitoring/jaeger`)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
