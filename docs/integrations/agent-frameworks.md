# Agent frameworks

Expose a Pecca call as a tool. Each shim imports its framework lazily and raises `PeccaError("install <package>")` if missing. They all wrap `pecca.as_tool(call)`: a plain typed function `f(text) -> {label, confidence, fallback, version}` with a docstring.

```python
from pecca.integrations import langgraph, strands, google_adk, openai_agents, claude_agent

t = langgraph.tool("route_rfi")  # langchain_core.tools.tool
t = strands.tool("route_rfi")  # strands.tool
t = google_adk.tool("route_rfi")  # google.adk.tools.FunctionTool
t = openai_agents.tool("route_rfi")  # agents.function_tool
t = claude_agent.tool("route_rfi")  # claude_agent_sdk.tool (SdkMcpTool)
```
Claude Agent SDK: pass the tool to `claude_agent_sdk.create_sdk_mcp_server("pecca", tools=[t])`.
Put the Pecca tool first so cheap, deterministic routing happens before any LLM-backed tool; `fallback=True` tells the agent to use the LLM instead.
