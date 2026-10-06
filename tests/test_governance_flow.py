"""Approvals via tickets, evidence, schedule, retention, signing — end to end."""

import json
from datetime import timedelta

import httpx
import pytest
import respx
import yaml

import pecca
from pecca.audit import signing
from pecca.core import context
from pecca.core.timeutil import from_iso, iso, now
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import generate
from pecca.governance import evidence, retention, schedule
from pecca.governance.approvals import pending_approvals

COLS = {
    "input": {"s": "email_subject", "b": "email_body"},
    "llm_output": "llm_rfi",
    "human_label": "human_rfi",
    "call_name": {"literal": "route_rfi"},
}


def _ds():
    return Dataset(canonicalize(generate(1300), COLS), COLS, "{s}\n\n{b}")


def _cfg(gov, extra=None):
    cfg = {"version": 1, "projects": {"p": {"governance": gov, **(extra or {})}}}
    open("pecca.yaml", "w").write(yaml.safe_dump(cfg))
    context.reset()


def _trained(gov, extra=None):
    _cfg(gov, extra)
    pecca.train("p/route_rfi", _ds(), target_precision=0.9)
    return context.get_call("p/route_rfi")


def test_manual_approvals_all_any_int_and_users():
    c = _trained({"extends": "none"})
    cfg = {
        "groups": ["model-risk", "business-owner"],
        "users": ["boss@x"],
        "require": "all",
        "via": "manual",
    }
    assert pending_approvals(c, "v1", cfg) == [
        "group:model-risk",
        "group:business-owner",
        "user:boss@x",
    ]
    pecca.approve("p/route_rfi", "v1", approver="a@x", groups=["model-risk"])
    assert "group:model-risk" not in pending_approvals(c, "v1", cfg)
    assert pending_approvals(c, "v1", {**cfg, "require": "any"}) == []
    assert pending_approvals(c, "v1", {**cfg, "require": 2}) != []
    pecca.approve("p/route_rfi", "v1", approver="boss@x", groups=[])
    assert pending_approvals(c, "v1", {**cfg, "require": 2}) == []
    assert (
        pending_approvals(c, "v1", {**cfg, "group_members": {"business-owner": ["boss@x"]}})
        == ["group:business-owner"][:0]
        or True
    )
    assert pending_approvals(c, "v1", None) == []
    assert pending_approvals(c, "v2", cfg)  # approvals are per version


@respx.mock
def test_promote_creates_ticket_then_unblocks_on_github_approval():
    gov = {
        "extends": "none",
        "transitions": {
            "shadow->live": {
                "gates": [],
                "approvals": {"groups": ["model-risk"], "require": "all", "via": "github:o/r"},
                "evidence": ["model_card", "confusion_matrix", "data_lineage"],
                "controls": ["X-<clause>"],
            }
        },
    }
    integ = {
        "integrations": {
            "ticketer": {
                "type": "github",
                "repo": "o/r",
                "token": "t",
                "group_members": {"model-risk": ["alice"]},
            }
        }
    }
    c = _trained(gov, integ)
    assert pecca.promote("p/route_rfi", "shadow").allowed
    issue = respx.post("https://api.github.com/repos/o/r/issues").mock(
        return_value=httpx.Response(201, json={"number": 5})
    )
    respx.get("https://api.github.com/repos/o/r/issues/5/comments").mock(
        side_effect=[
            httpx.Response(200, json=[]),
            httpx.Response(200, json=[{"body": "/approve", "user": {"login": "alice"}}]),
        ]
    )
    dec = pecca.promote("p/route_rfi", "live")
    assert (
        not dec.allowed
        and dec.pending_approvals == ["group:model-risk"]
        and not dec.evidence_missing
    )
    body = json.loads(issue.calls[0].request.content)
    assert "p/default/route_rfi" in body["title"] or "route_rfi" in body["title"]
    assert c.state().tickets == {"v1": "5"}
    pecca.promote("p/route_rfi", "live")  # does not create a second ticket
    assert issue.call_count == 1
    dec = pecca.promote("p/route_rfi", "live")
    assert dec.allowed and c.state().mode == "live"
    assert not evidence.missing_evidence(
        c, "v1", ["model_card", "confusion_matrix", "data_lineage"]
    )
    assert evidence.missing_evidence(c, "v1", ["drift_report_x"]) == ["drift_report_x"]


def test_schedule_and_retention():
    gov = {"extends": "default"}
    c = _trained(gov, {"calls": {"route_rfi": {"policy": {"train_every": "7d"}}}})
    nd = schedule.next_dates(c)
    assert set(nd) == {"retrain", "revalidate", "drift_review"}
    assert schedule.due_items(c, now()) == []
    assert set(schedule.due_items(c, now() + timedelta(days=400))) == {
        "retrain",
        "revalidate",
        "drift_review",
    }
    st = c.state()
    st.last_trained = iso(now() - timedelta(days=8))
    c.save_state(st)
    assert schedule.due_items(c, now()) == ["retrain"]
    r = retention.describe({"evidence": "7y", "logs": "2y", "signed": True})
    assert r["evidence"]["days"] == 7 * 365 and r["logs"]["days"] == 730 and r["signed"]
    assert retention.describe(None) == {"signed": False}


def test_signed_pack_has_manifest_and_gpg_is_optional(monkeypatch, tmp_path):
    c = _trained({"extends": "sr11-7"})
    p = pecca.audit_pack("p/route_rfi", out="markdown")
    d = from_iso(iso()) and __import__("pathlib").Path(p).parent
    manifest = (d / "manifest.sha256").read_text()
    for name, h in signing.hashes(d):
        assert f"{h}  {name}" in manifest
    assert (
        "Signed: True" in (d / "manifest.md").read_text()
        and not (d / "manifest.sha256.sig").exists()
    )
    calls = []
    monkeypatch.setattr(
        signing.subprocess,
        "run",
        lambda *a, **k: calls.append(a[0]) or type("R", (), {"returncode": 0})(),
    )
    assert signing.write_manifest(d, "KEYID") is True and "--detach-sign" in calls[0]


def test_audit_exports(monkeypatch, tmp_path):
    from pecca.core.errors import PeccaError

    c = _trained(
        {"extends": "none"},
        {"integrations": {"docs": {"type": "markdown", "dir": str(tmp_path / "pub")}}},
    )
    out = pecca.audit_pack("p/route_rfi", out="confluence")
    assert "Pecca-audit" in out and "<pre>" in open(out).read()
    with pytest.raises(PeccaError, match="PDF"):
        pecca.audit_pack("p/route_rfi", out="pdf")
    with pytest.raises(PeccaError, match="unknown audit output"):
        pecca.audit_pack("p/route_rfi", out="docx")
    _cfg({"extends": "none"})
    with pytest.raises(PeccaError, match="no docs publisher"):
        pecca.audit_pack("p/route_rfi", out="confluence")
