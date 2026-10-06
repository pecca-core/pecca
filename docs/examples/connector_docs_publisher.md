# Connector: docs publishers

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_docs_publisher.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_docs_publisher.ipynb)

Publishes an audit pack to a Markdown folder and to Confluence (mocked): create the first time, update with version + 1 afterwards.

```bash
pip install pecca respx pyyaml
jupyter lab examples/notebooks/connector_docs_publisher.ipynb
```
Runtime: ~15 s. Needs Docker: **no (HTTP mocked)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
