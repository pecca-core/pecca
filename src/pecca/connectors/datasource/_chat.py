"""Extract (input, output) from OpenAI-style request/response payloads."""

from __future__ import annotations

import json
from typing import Any


def loads(v: Any) -> Any:
    if isinstance(v, (dict, list)) or v is None:
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


def _content(c: Any) -> str:
    if isinstance(c, list):  # content parts
        return "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
    return "" if c is None else str(c)


def extract_input(req: Any) -> str | None:
    req = loads(req)
    if isinstance(req, dict):
        msgs = req.get("messages")
        if isinstance(msgs, list):
            users = [m for m in msgs if isinstance(m, dict) and m.get("role") == "user"]
            if users or msgs:
                return _content((users or msgs)[-1].get("content"))
        for k in ("prompt", "input", "inputs"):
            if k in req:
                v = req[k]
                return _content(v[0] if isinstance(v, list) and v else v)
    if isinstance(req, list) and req and isinstance(req[-1], dict):
        return _content(req[-1].get("content"))
    return None if req is None else str(req)


def extract_output(resp: Any) -> str | None:
    resp = loads(resp)
    if isinstance(resp, dict):
        ch = resp.get("choices")
        if isinstance(ch, list) and ch:
            c = ch[0]
            if isinstance(c.get("message"), dict):
                return _content(c["message"].get("content"))
            if "text" in c:
                return _content(c["text"])
        if "predictions" in resp and resp["predictions"]:
            p = resp["predictions"][0]
            return _content(p if not isinstance(p, dict) else p.get("text", json.dumps(p)))
        if "output" in resp:
            return _content(resp["output"])
    return None if resp is None else str(resp)
