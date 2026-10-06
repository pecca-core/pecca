from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pecca.connectors.base import Scheduler, register
from pecca.connectors.scheduler.cron import cron_expr
from pecca.core.errors import PeccaError


@register("scheduler", "databricks_workflows")
class DatabricksWorkflowsScheduler(Scheduler):
    """Generates Databricks job JSON (and creates the job with ``deploy: true`` via databricks-sdk)."""

    def __init__(
        self,
        out_dir: str = "databricks_jobs",
        deploy: bool = False,
        cluster_id: str | None = None,
        timezone: str = "UTC",
        **_: Any,
    ) -> None:
        self.dir, self.deploy, self.cluster_id, self.tz = (
            Path(out_dir),
            deploy,
            cluster_id,
            timezone,
        )

    def job_settings(self, name: str, every: str, command: list[str]) -> dict[str, Any]:
        cron = cron_expr(every).split()
        quartz = f"0 {cron[0]} {cron[1]} {'?' if cron[4] == '*' else cron[2]} {cron[3]} {'*' if cron[4] == '*' else cron[4]}"
        task: dict[str, Any] = {
            "task_key": name,
            "spark_python_task": {
                "python_file": "pecca_job.py",
                "parameters": command[1:] if command[:1] == ["pecca"] else command,
            },
        }
        if self.cluster_id:
            task["existing_cluster_id"] = self.cluster_id
        return {
            "name": f"pecca-{name}",
            "tasks": [task],
            "schedule": {
                "quartz_cron_expression": quartz.replace("0 0 6", "0 0 6"),
                "timezone_id": self.tz,
            },
        }

    def register_job(self, name: str, every: str, command: list[str]) -> None:
        settings = self.job_settings(name, every, command)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{name}.json").write_text(json.dumps(settings, indent=2))
        if self.deploy:
            try:
                from databricks.sdk import WorkspaceClient
                from databricks.sdk.service.jobs import JobSettings
            except ImportError as e:
                raise PeccaError(
                    "databricks-sdk is not installed", "pip install 'pecca[databricks]'"
                ) from e
            WorkspaceClient().jobs.create(**JobSettings.from_dict(settings).as_shallow_dict())

    def list_jobs(self) -> list[dict[str, Any]]:
        return [json.loads(p.read_text()) for p in sorted(self.dir.glob("*.json"))]
