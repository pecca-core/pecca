# Connector: ticketers and the approval loop

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_ticketer.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_ticketer.ipynb)

The full loop (train → shadow → `live` blocked → ticket opened → approval → `live`) with manual, GitHub Issues (`/approve` comment) and Jira (status transition) approvals.

```bash
pip install pecca respx pyyaml
jupyter lab examples/notebooks/connector_ticketer.ipynb
```
Runtime: ~25 s. Needs Docker: **no (HTTP mocked)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
