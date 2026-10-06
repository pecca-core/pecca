# Monitoring with Grafana Tempo

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/monitoring_grafana_tempo.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/monitoring_grafana_tempo.ipynb)

Sends spans to Tempo, queries them with TraceQL (disagreements, fallbacks, low confidence) and checks the provisioned **Pecca: LLM replacement** Grafana dashboard.

```bash
pip install pecca requests
jupyter lab examples/notebooks/monitoring_grafana_tempo.ipynb
```
Runtime: ~90 s. Needs Docker: **yes (`examples/monitoring/tempo`)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
