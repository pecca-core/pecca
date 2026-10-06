# OpenAI Agents SDK notebook

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecca-core/pecca/blob/main/examples/notebooks/agent_openai_agents.ipynb)
· [View on GitHub](https://github.com/pecca-core/pecca/blob/main/examples/notebooks/agent_openai_agents.ipynb)

A two-tool support agent (`classify_email` backed by an LLM, `lookup_policy`) runs 20 synthetic emails with a *scripted* model (no API key, offline), counting classification LLM calls. Then Pecca's `route_rfi` is added as the **first** tool and the same emails run again: classification LLM calls drop from 20 to 0, the agent still answers every email, and a per-email table shows Pecca's confidence and `fallback` flag.

Run it locally (the notebook installs its own dependencies):
```bash
pip install pecca openai-agents
jupyter lab examples/notebooks/agent_openai_agents.ipynb
```
The committed notebook has its outputs, so GitHub renders the results without running anything. Runtime: about 30 seconds. Needs Docker: no.
