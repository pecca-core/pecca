"""plugins, scheduler, mcp."""

from __future__ import annotations

import time

import typer
from rich.table import Table

import pecca.candidates  # noqa: F401  (registers built-ins)
from pecca import connectors
from pecca.candidates import all_candidates
from pecca.cli.common import console, handle
from pecca.core import context
from pecca.core.timeutil import iso, now


@handle
def plugins_list() -> None:
    """List registered candidates and connectors with their source module."""
    t = Table(title="candidates", show_header=True, header_style="bold")
    for col in ("name", "task types", "module"):
        t.add_column(col)
    for name, cls in sorted(all_candidates().items()):
        t.add_row(name, ",".join(cls.task_types), cls.__module__)
    console.print(t)
    c = Table(title="connectors", show_header=True, header_style="bold")
    for col in ("interface", "type", "module"):
        c.add_column(col)
    for row in connectors.available():
        c.add_row(row["interface"], row["type"], row["module"])
    console.print(c)


def tick() -> list[str]:
    """Evaluate due policies for every call in the workspace. Returns a log of what ran."""
    import pecca
    from pecca.governance import schedule

    done: list[str] = []
    ws = context.get_workspace()
    for pname in ws.projects:
        for cname in ws.registry.list_calls(f"pecca/{ws.name}/{pname}"):
            call = context.get_call(f"{ws.name}/{pname}/{cname}", ws)
            for item in schedule.due_items(call, now()):
                st = call.state()
                if item == "retrain":
                    pecca.retrain(str(call.path))
                    done.append(f"{call.path}: retrained")
                    continue
                if item == "revalidate":
                    pecca.audit_pack(str(call.path))
                    st.last_revalidated = iso()
                    call.notify("revalidate", {"message": "revalidation pack generated"})
                else:
                    rep = pecca.evaluate(str(call.path), "30d")
                    st.last_drift_review = iso()
                    call.notify("drift", {"message": f"drift {rep.drift_score}"})
                call.save_state(st)
                done.append(f"{call.path}: {item}")
    return done


@handle
def scheduler_run(once: bool = typer.Option(False, "--once", help="Run a single tick and exit"),
                  interval: int = typer.Option(60, "--interval", help="Seconds between ticks")) -> None:
    """Evaluate due train_every / revalidate / drift_review items, execute them and notify."""
    while True:
        done = tick()
        console.print("\n".join(done) if done else "nothing due", markup=False, highlight=False)
        if once:
            return
        time.sleep(interval)


@handle
def mcp_serve(transport: str = typer.Option("stdio", "--transport"), port: int = typer.Option(8765, "--port"),
              workspace: str = typer.Option(None, "--workspace"),
              allow_promote: bool = typer.Option(False, "--allow-promote", help="Expose pecca_promote")) -> None:
    """Run the Pecca MCP server."""
    from pecca.mcp.server import build_server

    server = build_server(workspace=workspace, allow_promote=allow_promote)
    if transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host="127.0.0.1", port=port)
