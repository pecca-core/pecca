"""Approval checking against manual records and the Ticketer connector."""

from __future__ import annotations

from typing import Any


def _approvers(call: Any, version: str, via: str) -> list[dict[str, Any]]:
    st = call.state()
    people = [
        {"principal": a["approver"], "groups": a.get("groups", [])}
        for a in st.approvals
        if a.get("version") == version
    ]
    if via != "manual":
        ticket = st.tickets.get(version)
        ticketer = call.project.ticketer()
        if ticket and ticketer is not None:
            for a in ticketer.get_approvers(ticket):
                grp = a.get("group")
                people.append(
                    {
                        "principal": a.get("principal"),
                        "groups": list(a.get("groups") or ([grp] if grp else [])),
                    }
                )
    return people


def pending_approvals(call: Any, version: str, cfg: dict[str, Any] | None) -> list[str]:
    if not cfg:
        return []
    groups, users = list(cfg.get("groups") or []), list(cfg.get("users") or [])
    members: dict[str, list[str]] = cfg.get("group_members") or {}
    people = _approvers(call, version, str(cfg.get("via", "manual")))
    principals = [f"group:{g}" for g in groups] + [f"user:{u}" for u in users]
    if not principals:
        principals = ["any-approver"]

    def satisfied(p: str) -> bool:
        if p == "any-approver":
            return bool(people)
        kind, name = p.split(":", 1)
        for a in people:
            who = str(a["principal"])
            if kind == "user" and who == name:
                return True
            if kind == "group" and (name in a["groups"] or who in members.get(name, [])):
                return True
        return False

    req = cfg.get("require", "all")
    need = len(principals) if req == "all" else 1 if req == "any" else int(req)
    ok = [p for p in principals if satisfied(p)]
    if len(ok) >= need:
        return []
    return [p for p in principals if p not in ok]
