"""Generate an audit pack for one model version."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pecca import evaluation
from pecca.audit import renderer, signing
from pecca.audit.sections import EXTRA_SECTIONS, SECTIONS
from pecca.core.call import Call
from pecca.core.errors import PeccaError
from pecca.core.timeutil import iso
from pecca.governance.evidence import audit_dir
from pecca.templates_util import render


def build_context(call: Call, version: str) -> dict[str, Any]:
    mv = call.version(version)
    st = call.state()
    gov = call.project.governance
    trans = (gov.get("transitions") or {}).get("shadow->live") or {}
    controls = [c for t in (gov.get("transitions") or {}).values() for c in t.get("controls", [])]
    rep = evaluation.evaluate_call(call, "30d")
    return {
        "call": {"path": str(call.path), "name": call.name, "mode": st.mode, "version": version},
        "model": mv.to_dict(),
        "shadow": rep.to_dict(),
        "policy": {**trans, "call": call.project.policy(call.name)},
        "governance": gov,
        "workspace": call.path.workspace,
        "project": call.path.project,
        "now": iso(),
        "audit": {
            "approvals": [a for a in st.approvals if a.get("version") == version],
            "ticket": st.tickets.get(version),
            "controls": controls,
            "history": st.history,
            "shadow_days": evaluation.shadow_days(call),
            "retention": gov.get("retention"),
            "hashes": [],
            "signed": False,
        },
    }


def generate(call: Call, version: str | None = None) -> Path:
    """Write all sections + manifest to ``audit/<version>/`` and return that directory."""
    version = version or call.version().version
    ctx = build_context(call, version)
    out = audit_dir(call, version)
    for f in out.glob("*"):
        if f.is_file():
            f.unlink()
    evidence = {
        e
        for t in (ctx["governance"].get("transitions") or {}).values()
        for e in t.get("evidence", [])
    }
    names = [*SECTIONS, *[s for s in EXTRA_SECTIONS if s in evidence]]
    for name in names:
        builder = SECTIONS.get(name)
        extras = builder(ctx, out) if builder else {}
        (out / f"{name}.md").write_text(renderer.render_section(name, ctx, extras))
    (out / "audit.md").write_text(combined_markdown(out))  # included in the manifest below
    ret = ctx["governance"].get("retention") or {}
    pre = signing.hashes(out)
    ctx["audit"]["hashes"] = pre
    ctx["audit"]["signed"] = bool(ret.get("signed"))
    (out / "manifest.md").write_text(renderer.render_section("manifest", ctx, {}))
    signing.write_manifest(out, ret.get("gpg_key") if ret.get("signed") else None)
    return out


def combined_markdown(directory: Path) -> str:
    order = [*SECTIONS, "human_oversight_log", "manifest"]
    parts = [(directory / f"{n}.md").read_text() for n in order if (directory / f"{n}.md").exists()]
    return "\n\n---\n\n".join(parts)


def export(call: Call, version: str | None, out: str, path: str | None) -> str:
    """Return the produced path (markdown/pdf), page URL (confluence) or JSON text."""
    version = version or call.version().version
    d = generate(call, version)
    md = combined_markdown(d)
    if out == "markdown":
        dest = Path(path) if path else d
        dest.mkdir(parents=True, exist_ok=True)
        if dest != d:
            for f in d.iterdir():
                (dest / f.name).write_bytes(f.read_bytes())
        return str(dest / "audit.md")
    if out == "json":
        ctx = build_context(call, version)
        ctx["audit"].pop("hashes", None)
        return json.dumps(ctx, indent=2, default=str)
    if out == "pdf":
        dest = Path(path) if path else d
        dest.mkdir(parents=True, exist_ok=True)
        return renderer.to_pdf(md, str(dest / "audit.pdf"))
    if out == "confluence":
        pub = call.project.docs_publisher()
        if pub is None:
            raise PeccaError("no docs publisher configured", "add integrations.docs to pecca.yaml")
        ctx = build_context(call, version)
        title = f"Pecca audit — {call.path} {version}"
        html = render("confluence_page.html.j2", **ctx, markdown=md)
        return pub.publish(title, html, {"call": str(call.path), "version": version})
    raise PeccaError(f"unknown audit output {out!r}", "use markdown, pdf, confluence or json")
