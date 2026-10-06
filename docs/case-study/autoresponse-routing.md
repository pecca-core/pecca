# Case study: autoresponse routing

A bank's email-reply system classifies every incoming customer email into one of ~60 RFI topics with an LLM call, then decides whether to auto-reply. The calls return fixed labels, run on every email, and there are months of logged answers plus human agent tags. (All data here is synthetic.)

**Before** (`examples/autoresponse_routing/before.py`):
```python
def route_rfi(subject, body):
    return llm_route_rfi(subject, body)  # one LLM call per email
```

**After** (`after.py`): one decorator; the LLM stays in place while Pecca shadows it.
```python
@pecca.replace(
    "route_rfi",
    mode="shadow",
    input_adapter=lambda subject, body: {"subject": subject, "body": body},
)
def route_rfi(subject, body):
    return llm_route_rfi(subject, body)  # unchanged
```

**Greenfield** (`greenfield.py`): no history yet. Record 1,500 calls, then `pecca.train("route_rfi")`, then promote to shadow. See the example README for the commands; everything runs offline with a deterministic mock LLM.

On the bundled dataset the simulated LLM scores about 0.83 macro-F1 against human labels while a small model trained on its logs reaches 0.91 against the same noisy labels. These are synthetic numbers: real email is harder and your results will differ.
