# Examples

Every notebook runs offline (mock LLM, scripted agent models, mocked HTTP), has committed outputs, and an *Open in Colab* badge. CI executes them with `PECCA_TEST_SMALL=1`.

| Notebook | What it shows | Runtime | Needs Docker? |
| --- | --- | --- | --- |
| [Quickstart](quickstart.md) | connect → profile → train → shadow → status → audit pack | ~3 min | no |
| [LangGraph](agent_langgraph.md) | Pecca as the agent's first tool | ~15 s | no |
| [Strands Agents](agent_strands.md) | same, with Strands | ~15 s | no |
| [Google ADK](agent_google_adk.md) | same, with ADK | ~15 s | no |
| [OpenAI Agents SDK](agent_openai_agents.md) | same, with the Agents SDK | ~15 s | no |
| [Claude Agent SDK](agent_claude_agent_sdk.md) | same, through the SDK's MCP server | ~30 s | no |

## Monitoring
Pecca exports OpenTelemetry spans; no vendor-specific code. Config-only guides:
[Datadog](monitoring_datadog.md) · [New Relic](monitoring_new_relic.md) · [Honeycomb](monitoring_honeycomb.md) · [Langfuse](monitoring_langfuse.md) · [Dynatrace](monitoring_dynatrace.md).
See also [OpenTelemetry](../integrations/opentelemetry.md).
