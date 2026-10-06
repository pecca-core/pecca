# Quickstart notebook

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/quickstart.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/quickstart.ipynb)

connect → profile → train → shadow → status → audit pack on the synthetic demo dataset (downloaded from Hugging Face, or generated locally if offline). Uses the real multilingual-e5 embeddings unless `PECCA_TEST_SMALL=1`.

Run it locally (the notebook installs its own dependencies):
```bash
pip install pecca huggingface_hub
jupyter lab examples/quickstart.ipynb
```
The committed notebook has its outputs, so GitHub renders the results without running anything. Runtime: about 3 minutes. Needs Docker: no.
