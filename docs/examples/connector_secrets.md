# Connector: secrets

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/connector_secrets.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/connector_secrets.ipynb)

Resolves `${SLACK_WEBHOOK}` from environment variables, a Vault dev server and AWS Secrets Manager (mocked), and shows the value never reaches `.pecca/config.resolved.yaml`.

```bash
pip install pecca hvac boto3 moto pyyaml requests
jupyter lab examples/notebooks/connector_secrets.ipynb
```
Runtime: ~10 s. Needs Docker: **yes (HashiCorp Vault dev container; skipped without Docker)**. With `PECCA_SKIP_DOCKER=1` (as in CI) the Docker cells are skipped and the notebook still runs end to end. Outputs are committed, so GitHub renders the results without running anything.
