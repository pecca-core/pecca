# Connector: notifiers

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_notifier.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_notifier.ipynb)

Shows the exact JSON each notifier (webhook, Slack, Teams) would send, then wires Slack into a project and shows the `trained` and `shadow` events firing (`events:` filters the rest).

```bash
pip install pecca respx
jupyter lab examples/notebooks/connector_notifier.ipynb
```
Runtime: ~15 s. Needs Docker: **no (HTTP mocked)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
