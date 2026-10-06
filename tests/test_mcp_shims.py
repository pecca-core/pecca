import asyncio
import json
import sys
import types

import pytest

import pecca
from pecca.core.errors import PeccaError
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import generate
from pecca.mcp.server import build_server

COLS = {
    "input": {"s": "email_subject", "b": "email_body"},
    "llm_output": "llm_rfi",
    "human_label": "human_rfi",
    "call_name": {"literal": "route_rfi"},
}


@pytest.fixture()
def trained():
    pecca.train("route_rfi", Dataset(canonicalize(generate(1300), COLS), COLS, "{s}\n\n{b}"))


def _names(server):
    from mcp.client import Client

    async def go():
        async with Client(server) as c:
            return sorted(t.name for t in (await c.list_tools()).tools)

    return asyncio.run(go())


def test_mcp_lists_tools_and_gates_promote():
    base = [
        "pecca_audit",
        "pecca_diff",
        "pecca_evaluate",
        "pecca_predict",
        "pecca_profile",
        "pecca_status",
    ]
    assert _names(build_server()) == base
    assert _names(build_server(allow_promote=True)) == sorted([*base, "pecca_promote"])


def test_mcp_tools_work(trained):
    from mcp.client import Client

    async def go():
        async with Client(build_server(allow_promote=True)) as c:
            st = await c.call_tool("pecca_status", {"path": "route_rfi"})
            pr = await c.call_tool(
                "pecca_predict",
                {"path": "route_rfi", "inputs": [{"s": "lost card", "b": "my card was stolen"}]},
            )
            pm = await c.call_tool("pecca_promote", {"path": "route_rfi", "mode": "shadow"})
            return st, pr, pm

    st, pr, pm = asyncio.run(go())
    assert json.loads(st.content[0].text)["version"] == "v1"
    first = json.loads(pr.content[0].text)
    assert "label" in (first[0] if isinstance(first, list) else first)
    assert "allowed" in pm.content[0].text


def _fake(monkeypatch, module, **attrs):
    mod = types.ModuleType(module)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, module, mod)
    parts = module.split(".")
    for i in range(1, len(parts)):  # make parent packages importable
        monkeypatch.setitem(
            sys.modules,
            ".".join(parts[:i]),
            sys.modules.get(".".join(parts[:i])) or types.ModuleType(".".join(parts[:i])),
        )
    return mod


def test_as_tool_plain(trained):
    t = pecca.as_tool("route_rfi")
    assert t.__name__ == "route_rfi" and "Pecca" in t.__doc__
    assert set(t("lost card\n\nmy card was stolen")) == {
        "label",
        "confidence",
        "fallback",
        "version",
    }


def test_shims_with_mocked_frameworks(monkeypatch, trained):
    from pecca.integrations import claude_agent, google_adk, langgraph, openai_agents, strands

    seen = {}
    _fake(
        monkeypatch,
        "langchain_core.tools",
        tool=lambda name, description=None: lambda f: seen.setdefault("lc", (name, description, f)),
    )
    assert langgraph.tool("route_rfi")[0] == "route_rfi"
    _fake(monkeypatch, "strands", tool=lambda f, name=None, description=None: ("strands", name, f))
    assert strands.tool("route_rfi")[:2] == ("strands", "route_rfi")
    _fake(monkeypatch, "google.adk.tools", FunctionTool=lambda func: ("adk", func.__name__))
    assert google_adk.tool("route_rfi") == ("adk", "route_rfi")
    _fake(
        monkeypatch,
        "agents",
        function_tool=lambda f, name_override=None, description_override=None: (
            "oa",
            name_override,
        ),
    )
    assert openai_agents.tool("route_rfi") == ("oa", "route_rfi")
    _fake(
        monkeypatch,
        "claude_agent_sdk",
        tool=lambda name, desc, schema: lambda h: ("claude", name, h),
    )
    kind, name, handler = claude_agent.tool("route_rfi")
    assert (kind, name) == ("claude", "route_rfi")
    out = asyncio.run(handler({"text": "lost card\n\nmy card was stolen"}))
    assert json.loads(out["content"][0]["text"])["version"] == "v1"


@pytest.mark.parametrize(
    "mod,pkg",
    [
        ("langgraph", "langchain-core"),
        ("strands", "strands-agents"),
        ("google_adk", "google-adk"),
        ("openai_agents", "openai-agents"),
        ("claude_agent", "claude-agent-sdk"),
    ],
)
def test_shims_raise_clear_error_when_framework_missing(mod, pkg, monkeypatch):
    import importlib

    for name in (
        "langchain_core",
        "langchain_core.tools",
        "strands",
        "google.adk.tools",
        "agents",
        "claude_agent_sdk",
    ):
        monkeypatch.setitem(sys.modules, name, None)  # None => ImportError on import
    shim = importlib.import_module(f"pecca.integrations.{mod}")
    with pytest.raises(PeccaError, match=f"install {pkg}"):
        shim.tool("route_rfi")
