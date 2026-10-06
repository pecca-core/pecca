"""Pecca CLI (typer)."""

from __future__ import annotations

import typer

from pecca.cli.commands import ops, pipeline, setup

app = typer.Typer(
    help="Pecca: replace repetitive LLM calls with small, auditable models.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("init")(setup.init)
app.command("apply")(setup.apply)
app.command("connect")(setup.connect)
app.command("doctor")(setup.doctor)
app.command("version")(setup.version)
app.command("profile")(pipeline.profile)
app.command("train")(pipeline.train)
app.command("status")(pipeline.status)
app.command("eval")(pipeline.eval_)
app.command("promote")(pipeline.promote)
app.command("approve")(pipeline.approve)
app.command("diff")(pipeline.diff)
app.command("audit")(pipeline.audit)
app.command("logs")(pipeline.logs)

datasets = typer.Typer(help="Demo datasets", no_args_is_help=True)
datasets.command("demo")(setup.datasets_demo)
app.add_typer(datasets, name="datasets")

plugins = typer.Typer(help="Registered candidates and connectors", no_args_is_help=True)
plugins.command("list")(ops.plugins_list)
app.add_typer(plugins, name="plugins")

scheduler = typer.Typer(help="Scheduler", no_args_is_help=True)
scheduler.command("run")(ops.scheduler_run)
app.add_typer(scheduler, name="scheduler")

mcp = typer.Typer(help="MCP server", no_args_is_help=True)
mcp.command("serve")(ops.mcp_serve)
app.add_typer(mcp, name="mcp")

if __name__ == "__main__":
    app()
