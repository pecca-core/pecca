"""Generate the example notebooks (outputs are produced by executing them: see `make notebooks`).

uv run python scripts/make_notebooks.py          # writes examples/quickstart.ipynb + examples/notebooks/agent_*.ipynb
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
REPO = "pecca-core/pecca"


def badge(path: str) -> str:
    return (
        "[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
        f"(https://colab.research.google.com/github/{REPO}/blob/main/{path})"
    )


def build(path: str, cells: list[tuple[str, str]]) -> None:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.cells = [
        nbf.v4.new_markdown_cell(src.strip()) if kind == "md" else nbf.v4.new_code_cell(src.strip())
        for kind, src in cells
    ]
    out = ROOT / path
    out.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, out)


# ------------------------------------------------------------------------------------------------
QUICKSTART = [
    (
        "md",
        f"""
# Pecca quickstart

{badge("examples/quickstart.ipynb")}

Replace a repetitive LLM call with a small, auditable model: **connect → profile → train → shadow → status → audit pack**.
Everything runs offline-friendly on a synthetic dataset (a fictional "Northbridge Bank"); the "LLM" is a stand-in function.
""",
    ),
    ("code", "%pip install -q pecca huggingface_hub"),
    (
        "code",
        """
import os, tempfile

work = tempfile.mkdtemp()
os.chdir(work)
os.environ["PECCA_HOME"] = os.path.join(work, ".pecca")
os.environ["TQDM_DISABLE"] = "1"   # no progress bars in the notebook output
os.environ.setdefault("PECCA_TEST_SMALL", "0")  # real multilingual-e5 embeddings (set to 1 for a tiny offline stand-in)

import pandas as pd
import pecca
print("pecca", pecca.__version__)
""",
    ),
    (
        "md",
        "## 1. Get the demo data\nThe dataset lives on the Hugging Face Hub; if you are offline we generate the same data locally.",
    ),
    (
        "code",
        """
try:
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("pecca-core/demo-support-emails", "train.parquet", repo_type="dataset")
    source = "Hugging Face Hub"
except Exception:  # offline / no hub access
    from pecca.data.synthetic import generate
    path = os.path.join(work, "train.parquet")
    generate(6000).to_parquet(path)
    source = "generated locally"
print("data:", source)
""",
    ),
    (
        "md",
        "## 2. Connect\nMap your columns to Pecca's canonical schema: `input`, `llm_output`, `human_label`, `call_name`.",
    ),
    (
        "code",
        """
ds = pecca.connect(
    "parquet",
    path=path,
    columns={
        "input": {"subject": "email_subject", "body": "email_body"},
        "llm_output": "llm_rfi",          # what the LLM answered
        "human_label": "human_rfi",       # agent corrections (present for ~55% of rows)
        "call_name": {"literal": "route_rfi"},
    },
    input_template="{subject}\\n\\n{body}",
)
print(ds)
ds.sample(3)[["input", "llm_output", "human_label"]]
""",
    ),
    ("md", "## 3. Profile\nDeterministic rules decide whether the call can be replaced."),
    (
        "code",
        """
profile = pecca.profile(ds).profiles["route_rfi"]
{k: profile.to_dict()[k] for k in ("task_type", "input_type", "n_rows", "n_unique_outputs", "replaceable", "languages", "min_class_count")}
""",
    ),
    (
        "md",
        "## 4. Train\nA tournament over the small candidates on identical cross-validated splits (the slow fine-tuned `xlmr_finetune` is left out for a laptop/Colab CPU).",
    ),
    (
        "code",
        """
result = pecca.train("route_rfi", ds, candidates=["tfidf_linear", "e5_logreg"])
print(f"winner {result.winner}: {result.metric_name} {result.metric:.3f} (LLM vs human labels: {result.llm_metric:.3f})")
print(f"threshold {result.threshold:.2f}, expected fallback to the LLM {result.expected_fallback_rate:.0%}, {result.latency_ms:.1f} ms/prediction")
pd.DataFrame(result.leaderboard)[["candidate", "metric", "metric_std", "fit_time_s", "predict_latency_ms", "winner"]]
""",
    ),
    (
        "md",
        '## 5. Wrap your LLM function and shadow it\n`my_llm` here replays what the "LLM" said; in your code it is whatever you already call.',
    ),
    (
        "code",
        """
from pecca.runtime.logging_sink import flush_all

emails = ds.to_pandas().tail(60)
said = {f"{i['subject']}\\n\\n{i['body']}": out for i, out in zip(emails["input"], emails["llm_output"])}   # the LLM's historical answers

def to_input(text):
    subject, body = text.split("\\n\\n", 1)
    return {"subject": subject, "body": body}

@pecca.replace("route_rfi", mode="shadow", input_adapter=to_input)
def route_rfi(text: str) -> str:
    return said[text]                     # stand-in for my_llm.classify(text), unchanged

print(pecca.promote("route_rfi", "shadow"))   # governance-gated mode change (default project: metric gates only)
for text in said:
    route_rfi(text)                        # still returns the LLM's answer; Pecca logs the model's next to it
flush_all()
report = pecca.evaluate("route_rfi", "1d")
print(f"{report.n_rows} calls in shadow: agreement with the LLM {report.agreement_rate:.0%}, would fall back {report.fallback_rate:.0%}")
""",
    ),
    ("md", "## 6. Status"),
    ("code", "!pecca status default/default/route_rfi"),
    (
        "md",
        "## 7. Audit pack preview\nEvery model version gets lineage, benchmarks, a confusion matrix, threshold rationale, calibration and an sha256 manifest.",
    ),
    (
        "code",
        """
from pathlib import Path
from IPython.display import Markdown, display

pack = Path(pecca.audit_pack("route_rfi", out="markdown")).parent
print(sorted(p.name for p in pack.iterdir()))
for section in ("summary", "benchmark_leaderboard", "threshold_rationale"):
    display(Markdown((pack / f"{section}.md").read_text()))
""",
    ),
    (
        "md",
        """
## Next
* Let it run in shadow, then `pecca promote default/default/route_rfi --mode live` once the gates pass.
* Docs: https://pecca-core.github.io/pecca/ · Source: https://github.com/pecca-core/pecca
""",
    ),
]

# ------------------------------------------------------------------------------------------------
SHARED = '''
import ast, hashlib, json, os, re, tempfile

import pandas as pd
import pecca
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import CATALOG, RFIS, generate

work = tempfile.mkdtemp()
os.chdir(work)
os.environ["PECCA_HOME"] = os.path.join(work, ".pecca")

# --- A deterministic stand-in "LLM" for classification: keyword match, ~15% of answers wrong ------
_STOP = {"i", "my", "the", "a", "to", "me", "is", "and", "of", "on", "for", "in", "it", "do", "how", "can",
         "you", "please", "this", "that", "amt", "date", "last", "prod", "need", "want"}
_tok = lambda t: [w for w in re.findall(r"[a-z]+", t.lower()) if w not in _STOP]
_grams = lambda t: set(t) | {f"{a} {b}" for a, b in zip(t, t[1:])}
_TOPICS = {rfi: [_grams(_tok(p.replace("{", " ").replace("}", " "))) for p in ps]
           for rs in CATALOG.values() for rfi, ps in rs.items()}
LLM = {"calls": 0}                      # every real classification LLM call is counted here

def llm_classify(text):
    LLM["calls"] += 1
    g = _grams(_tok(text))
    best = max(_TOPICS, key=lambda r: (max(len(g & x) / len(x) for x in _TOPICS[r]), r))
    h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    return RFIS[h % len(RFIS)][1] if h % 100 < 15 else best

# --- The support agent's two ordinary tools -----------------------------------------------------
def classify_email(text: str) -> str:
    """Classify a customer email into one of 60 RFI topics (LLM-backed)."""
    return llm_classify(text)

def lookup_policy(topic: str) -> str:
    """Return the reply template for an RFI topic."""
    return f"Reply template for {topic.replace('_', ' ')}"

# --- The scripted "agent model" (no API key, fully offline) -------------------------------------
# It plans like a sensible model would: use route_rfi first if it exists; fall back to classify_email
# when Pecca says fallback=True (or when route_rfi is not available); then look up the policy.
TURNS = {"n": 0}                         # how many times the agent model was asked for its next step

def _parse(r):
    if isinstance(r, (dict, list)):
        return r
    for f in (json.loads, ast.literal_eval):
        try:
            return f(r)
        except Exception:
            pass
    return r

def plan(email, history, tools):
    """history: [(tool_name, result), ...]. Returns ('tool', name, args) or ('final', text)."""
    TURNS["n"] += 1
    done = {n: _parse(r) for n, r in history}
    if "route_rfi" in tools and "route_rfi" not in done:
        return ("tool", "route_rfi", {"text": email})
    if "route_rfi" in done and not done["route_rfi"]["fallback"]:
        topic = done["route_rfi"]["label"]
    elif "classify_email" in done:
        topic = done["classify_email"]
    else:
        return ("tool", "classify_email", {"text": email})
    if "lookup_policy" not in done:
        return ("tool", "lookup_policy", {"topic": topic})
    return ("final", f"[{topic}] {done['lookup_policy']}")

# --- Train Pecca on the logged LLM answers (+ human corrections) --------------------------------
df = generate(3000)
df["text"] = df.email_subject + "\\n\\n" + df.email_body
cols = {"input": "text", "llm_output": "llm_rfi", "human_label": "human_rfi", "call_name": {"literal": "route_rfi"}}
result = pecca.train("route_rfi", Dataset(canonicalize(df, cols), cols), candidates=["tfidf_linear"])
print(f"trained {result.winner}: macro_f1 {result.metric:.2f}, threshold {result.threshold:.2f}, "
      f"expected fallback {result.expected_fallback_rate:.0%}")

# 20 new emails to run through the agent
emails = generate(20, seed=7)
texts = (emails.email_subject + "\\n\\n" + emails.email_body).tolist()
'''

REPORT = """
def report(run, tools_with_pecca, tools_without, label):
    LLM["calls"] = TURNS["n"] = 0
    base_out = run(tools_without)
    before = (LLM["calls"], TURNS["n"])
    LLM["calls"] = TURNS["n"] = 0
    pecca_out = run(tools_with_pecca)
    after = (LLM["calls"], TURNS["n"])
    print(f"{label}: 20 emails")
    print(f"  baseline (classify_email + lookup_policy):  classification LLM calls = {before[0]:>2}, agent model turns = {before[1]}")
    print(f"  with route_rfi first:                        classification LLM calls = {after[0]:>2}, agent model turns = {after[1]}")
    assert base_out == pecca_out or sum(a != b for a, b in zip(base_out, pecca_out)) <= 4   # same answers, apart from LLM noise
    return pecca_out
"""

TABLE = """
preds = pecca.predict("route_rfi", texts)
pd.DataFrame({
    "email": [t.split("\\n\\n")[0][:46] for t in texts],
    "pecca label": [p.label for p in preds],
    "confidence": [round(p.confidence, 2) for p in preds],
    "fallback to LLM": [p.fallback for p in preds],
    "agent answer": [o[:48] for o in outs],
})
"""


def agent_nb(
    name: str, title: str, pkgs: str, framework_cells: list[tuple[str, str]], note: str = ""
) -> None:
    path = f"examples/notebooks/agent_{name}.ipynb"
    cells = [
        (
            "md",
            f"""
# {title}: Pecca as the agent's first tool

{badge(path)}

A minimal support agent has two tools: `classify_email` (an LLM-backed classifier) and `lookup_policy`. We run 20 emails,
then add Pecca's `route_rfi` as the **first** tool and run them again. The agent model is a scripted stand-in (no API keys, runs offline);
it calls `route_rfi` first and only uses the LLM classifier when Pecca says `fallback=True`.
{note}
""",
        ),
        ("code", f"%pip install -q pecca {pkgs}"),
        (
            "md",
            "## Setup: stand-in LLM, tools, scripted model, and a trained Pecca model\n*(boilerplate shared by all five agent notebooks)*",
        ),
        ("code", SHARED),
        ("code", REPORT),
        *framework_cells,
        (
            "md",
            "## Per-email view: what Pecca decided\nHigh confidence → Pecca answers (no LLM call); `fallback=True` → the agent falls back to the LLM classifier.",
        ),
        ("code", TABLE),
        (
            "md",
            f"""
## Takeaway
Adding `pecca.integrations.{name}.tool("route_rfi")` as the first tool moved the cheap, deterministic routing step off the LLM:
classification LLM calls dropped while the agent still answers every email. The agent's own model turns are unchanged: Pecca replaces the *LLM-backed tool*, not the agent loop.
""",
        ),
    ]
    build(path, cells)


LANGGRAPH = [
    ("md", "## The framework-specific part: a scripted chat model for LangGraph"),
    (
        "code",
        """
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pecca.integrations import langgraph as pecca_lg


class ScriptedModel(BaseChatModel):
    tool_names: list = []

    @property
    def _llm_type(self):
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tool_names": [getattr(t, "name", str(t)) for t in tools]})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        email = next(m.content for m in messages if isinstance(m, HumanMessage))
        history, called = [], {}
        for m in messages:
            if isinstance(m, AIMessage):
                called.update({c["id"]: c["name"] for c in m.tool_calls})
            if isinstance(m, ToolMessage):
                history.append((called[m.tool_call_id], m.content))
        step = plan(email, history, set(self.tool_names))
        msg = (AIMessage(content=step[1]) if step[0] == "final"
               else AIMessage(content="", tool_calls=[{"name": step[1], "args": step[2], "id": f"c{len(history)}"}]))
        return ChatResult(generations=[ChatGeneration(message=msg)])


def run(tools):
    agent = create_react_agent(ScriptedModel(), tools)
    return [agent.invoke({"messages": [("user", t)]})["messages"][-1].content for t in texts]

base_tools = [tool(classify_email), tool(lookup_policy)]
""",
    ),
    ("md", "## (a)+(b) Baseline, then (c)+(d) with Pecca as the first tool"),
    (
        "code",
        'outs = report(run, [pecca_lg.tool("route_rfi")] + base_tools, base_tools, "LangGraph")',
    ),
]

STRANDS = [
    ("md", "## The framework-specific part: a scripted model for Strands Agents"),
    (
        "code",
        """
from strands import Agent, tool
from strands.models import Model
from pecca.integrations import strands as pecca_strands


class ScriptedModel(Model):
    def update_config(self, **config): pass
    def get_config(self): return {}
    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        tools = {s["name"] for s in (tool_specs or [])}
        email, history, called = None, [], {}
        for m in messages:
            for b in m["content"]:
                if "text" in b and m["role"] == "user" and email is None:
                    email = b["text"]
                if "toolUse" in b:
                    called[b["toolUse"]["toolUseId"]] = b["toolUse"]["name"]
                if "toolResult" in b:
                    r = b["toolResult"]
                    history.append((called[r["toolUseId"]], "".join(c.get("text") or json.dumps(c.get("json")) for c in r["content"])))
        step = plan(email, history, tools)
        yield {"messageStart": {"role": "assistant"}}
        if step[0] == "final":
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": step[1]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        else:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"t{len(history)}", "name": step[1]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step[2])}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        yield {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}, "metrics": {"latencyMs": 0}}}


async def run_async(tools):
    outs = []
    for t in texts:
        agent = Agent(model=ScriptedModel(), tools=tools, callback_handler=None)
        outs.append(str((await agent.invoke_async(t))).strip())
    return outs

base_tools = [tool(classify_email), tool(lookup_policy)]
""",
    ),
    ("md", "## (a)+(b) Baseline, then (c)+(d) with Pecca as the first tool"),
    (
        "code",
        """
import asyncio

# Notebooks already run an event loop, so drive the async agent with a small synchronous wrapper.
import concurrent.futures
def run(tools):
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        return pool.submit(lambda: asyncio.run(run_async(tools))).result()

outs = report(run, [pecca_strands.tool("route_rfi")] + base_tools, base_tools, "Strands Agents")
""",
    ),
]

ADK = [
    ("md", "## The framework-specific part: a scripted `BaseLlm` for Google ADK"),
    (
        "code",
        """
import asyncio, concurrent.futures, logging

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm, LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types
from pecca.integrations import google_adk as pecca_adk

logging.getLogger("google_adk").setLevel(logging.ERROR)


class ScriptedLlm(BaseLlm):
    model: str = "scripted"

    async def generate_content_async(self, llm_request, stream=False):
        tools = set((llm_request.tools_dict or {}).keys())
        email, history = None, []
        for c in llm_request.contents:
            for p in c.parts or []:
                if p.text and c.role == "user" and email is None:
                    email = p.text
                if p.function_response:
                    r = p.function_response.response
                    history.append((p.function_response.name, r["result"] if isinstance(r, dict) and set(r) == {"result"} else r))
        step = plan(email, history, tools)
        part = (types.Part(text=step[1]) if step[0] == "final"
                else types.Part(function_call=types.FunctionCall(name=step[1], args=step[2])))
        usage = types.GenerateContentResponseUsageMetadata(prompt_token_count=0, candidates_token_count=0, total_token_count=0)
        yield LlmResponse(content=types.Content(role="model", parts=[part]), usage_metadata=usage)


async def run_async(tools):
    service = InMemorySessionService()
    agent = LlmAgent(name="support", model=ScriptedLlm(), tools=tools, instruction="You are a support agent.")
    runner = Runner(agent=agent, app_name="support", session_service=service)
    outs = []
    for i, t in enumerate(texts):
        await service.create_session(app_name="support", user_id="u", session_id=f"s{i}")
        final = ""
        async for ev in runner.run_async(user_id="u", session_id=f"s{i}", new_message=types.Content(role="user", parts=[types.Part(text=t)])):
            if ev.is_final_response() and ev.content and ev.content.parts:
                final = ev.content.parts[0].text
        outs.append(final)
    return outs

base_tools = [FunctionTool(classify_email), FunctionTool(lookup_policy)]
""",
    ),
    ("md", "## (a)+(b) Baseline, then (c)+(d) with Pecca as the first tool"),
    (
        "code",
        """
def run(tools):
    with concurrent.futures.ThreadPoolExecutor(1) as pool:   # the notebook already has a running event loop
        return pool.submit(lambda: asyncio.run(run_async(tools))).result()

outs = report(run, [pecca_adk.tool("route_rfi")] + base_tools, base_tools, "Google ADK")
""",
    ),
]

OPENAI = [
    ("md", "## The framework-specific part: a scripted `Model` for the OpenAI Agents SDK"),
    (
        "code",
        """
from agents import Agent, ModelResponse, Runner, Usage, function_tool, set_tracing_disabled
from agents.models.interface import Model
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from pecca.integrations import openai_agents as pecca_oa

set_tracing_disabled(True)


class ScriptedModel(Model):
    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing,
                           *, previous_response_id=None, conversation_id=None, prompt=None):
        names = {t.name for t in tools}
        items = [{"role": "user", "content": input}] if isinstance(input, str) else list(input)
        email, history, called = None, [], {}
        for it in items:
            d = it if isinstance(it, dict) else it.model_dump()
            if d.get("role") == "user" and email is None:
                c = d["content"]
                email = c if isinstance(c, str) else "".join(p.get("text", "") for p in c)
            if d.get("type") == "function_call":
                called[d["call_id"]] = d["name"]
            if d.get("type") == "function_call_output":
                history.append((called[d["call_id"]], d["output"]))
        step = plan(email, history, names)
        if step[0] == "final":
            out = ResponseOutputMessage(id="m", role="assistant", status="completed", type="message",
                                        content=[ResponseOutputText(type="output_text", text=step[1], annotations=[])])
        else:
            out = ResponseFunctionToolCall(id=f"fc{len(history)}", call_id=f"c{len(history)}", name=step[1],
                                           arguments=json.dumps(step[2]), type="function_call")
        return ModelResponse(output=[out], usage=Usage(), response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


async def run_async(tools):
    agent = Agent(name="support", instructions="You are a support agent.", model=ScriptedModel(), tools=tools)
    return [(await Runner.run(agent, t)).final_output for t in texts]

base_tools = [function_tool(classify_email), function_tool(lookup_policy)]
""",
    ),
    ("md", "## (a)+(b) Baseline, then (c)+(d) with Pecca as the first tool"),
    (
        "code",
        """
import asyncio, concurrent.futures

def run(tools):
    with concurrent.futures.ThreadPoolExecutor(1) as pool:   # the notebook already has a running event loop
        return pool.submit(lambda: asyncio.run(run_async(tools))).result()

outs = report(run, [pecca_oa.tool("route_rfi")] + base_tools, base_tools, "OpenAI Agents SDK")
""",
    ),
]

CLAUDE = [
    (
        "md",
        """
## The framework-specific part: Claude Agent SDK
The SDK drives the real Claude Code CLI, which talks to the Messages API. To stay offline we point `ANTHROPIC_BASE_URL` at a tiny local
server that replays the same scripted plan; tools still run through the SDK's in-process MCP server exactly as they would in production.
""",
    ),
    (
        "code",
        """
import asyncio, concurrent.futures, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import claude_agent_sdk as sdk
from pecca.integrations import claude_agent as pecca_claude

PREFIX = "mcp__support__"


class FakeMessagesAPI(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        m = re.search(r"EMAIL<<(.*?)>>", json.dumps(body["messages"][0]["content"]), re.S)
        if not self.path.startswith("/v1/messages") or not m:      # CLI housekeeping requests
            out = ("text", "ok")
        else:
            email = json.loads('"' + m.group(1) + '"')
            tools = {t["name"].removeprefix(PREFIX) for t in body.get("tools", []) if t["name"].startswith(PREFIX)}
            history, called = [], {}
            for msg in body["messages"]:
                if isinstance(msg["content"], list):
                    for b in msg["content"]:
                        if b.get("type") == "tool_use":
                            called[b["id"]] = b["name"].removeprefix(PREFIX)
                        if b.get("type") == "tool_result":
                            c = b["content"]
                            history.append((called[b["tool_use_id"]], "".join(x.get("text", "") for x in c) if isinstance(c, list) else c))
            step = plan(email, history, tools)
            out = ("text", step[1]) if step[0] == "final" else ("tool", step[1], step[2], f"toolu_{len(history)}")
        sse = lambda t, d: f"event: {t}\\ndata: {json.dumps(d)}\\n\\n".encode()
        message = {"id": "msg_1", "type": "message", "role": "assistant", "model": body.get("model", "scripted"), "content": [],
                   "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        w = self.wfile.write
        w(sse("message_start", {"type": "message_start", "message": message}))
        if out[0] == "text":
            w(sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}))
            w(sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": out[1]}}))
            stop = "end_turn"
        else:
            w(sse("content_block_start", {"type": "content_block_start", "index": 0,
                                          "content_block": {"type": "tool_use", "id": out[3], "name": PREFIX + out[1], "input": {}}}))
            w(sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                          "delta": {"type": "input_json_delta", "partial_json": json.dumps(out[2])}}))
            stop = "tool_use"
        w(sse("content_block_stop", {"type": "content_block_stop", "index": 0}))
        w(sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 1}}))
        w(sse("message_stop", {"type": "message_stop"}))


server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMessagesAPI)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE_URL = f"http://127.0.0.1:{server.server_port}"
CONFIG_DIR = tempfile.mkdtemp()     # isolate from any local Claude Code settings/hooks


@sdk.tool("classify_email", classify_email.__doc__, {"text": str})
async def classify_tool(args):
    return {"content": [{"type": "text", "text": classify_email(args["text"])}]}


@sdk.tool("lookup_policy", lookup_policy.__doc__, {"topic": str})
async def lookup_tool(args):
    return {"content": [{"type": "text", "text": lookup_policy(args["topic"])}]}


async def run_async(tools):
    server_cfg = sdk.create_sdk_mcp_server("support", tools=tools)
    options = sdk.ClaudeAgentOptions(
        mcp_servers={"support": server_cfg}, allowed_tools=[PREFIX + t.name for t in tools], tools=[], max_turns=10,
        env={"ANTHROPIC_BASE_URL": BASE_URL, "ANTHROPIC_API_KEY": "sk-ant-offline", "CLAUDE_CONFIG_DIR": CONFIG_DIR,
             "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    outs = []
    for t in texts:
        final = ""
        async for message in sdk.query(prompt=f"EMAIL<<{json.dumps(t)[1:-1]}>>", options=options):
            if isinstance(message, sdk.ResultMessage):
                final = message.result
        outs.append(final)
    return outs

base_tools = [classify_tool, lookup_tool]
""",
    ),
    (
        "md",
        "## (a)+(b) Baseline, then (c)+(d) with Pecca as the first tool\nThe Pecca shim returns an SDK tool; the SDK serves it from the same in-process MCP server.",
    ),
    (
        "code",
        """
def run(tools):
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        return pool.submit(lambda: asyncio.run(run_async(tools))).result()

outs = report(run, [pecca_claude.tool("route_rfi")] + base_tools, base_tools, "Claude Agent SDK")
server.shutdown()
""",
    ),
]


def main() -> None:
    build("examples/quickstart.ipynb", QUICKSTART)
    agent_nb("langgraph", "LangGraph", "langgraph langchain-core", LANGGRAPH)
    agent_nb("strands", "Strands Agents", "strands-agents", STRANDS)
    agent_nb("google_adk", "Google ADK", "google-adk", ADK)
    agent_nb("openai_agents", "OpenAI Agents SDK", "openai-agents", OPENAI)
    agent_nb(
        "claude_agent_sdk",
        "Claude Agent SDK",
        "claude-agent-sdk",
        CLAUDE,
        note="\n*Needs the Claude Code CLI bundled with `claude-agent-sdk`; no Anthropic account or API key is used here.*",
    )
    print("wrote 6 notebooks")


if __name__ == "__main__":
    main()
