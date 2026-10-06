"""Generate reference pages: config reference from the JSON Schemas and the CLI reference from typer.

uv run python scripts/gen_docs.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from pecca.config import loader

ROOT = Path(__file__).resolve().parents[1]


def _rows(
    schema: dict[str, Any], defs: dict[str, Any], prefix: str = ""
) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if "$ref" in schema:
        schema = defs[schema["$ref"].split("/")[-1]]
    for name, sub in (schema.get("properties") or {}).items():
        if "$ref" in sub:
            sub = defs[sub["$ref"].split("/")[-1]]
        t = sub.get("type") or ("enum" if "enum" in sub else "")
        desc = sub.get("description", "")
        if "enum" in sub:
            desc = (desc + " One of: " + ", ".join(map(str, sub["enum"]))).strip()
        if "pattern" in sub:
            desc = (desc + f" Pattern `{sub['pattern']}`.").strip()
        rows.append((f"{prefix}{name}", str(t), desc))
        rows += _rows(sub, defs, f"{prefix}{name}.")
    if isinstance(schema.get("additionalProperties"), dict):
        rows += _rows(schema["additionalProperties"], defs, f"{prefix}<name>.")
    return rows


def config_page() -> str:
    schema = loader.config_schema()
    defs = schema.get("$defs", {})
    out = [
        "# pecca.yaml reference",
        "",
        "*Generated from the JSON Schema by `scripts/gen_docs.py`.*",
        "",
        "`pecca apply` validates the file, resolves `extends`, checks that every `${VAR}` resolves, stores the result in "
        "`.pecca/config.resolved.yaml` (placeholders kept) and prints a diff against what was stored before.",
        "",
        "```yaml",
        Path(ROOT / "examples/autoresponse_routing/pecca.yaml").read_text().rstrip(),
        "```",
        "",
        "| key | type | notes |",
        "| --- | --- | --- |",
    ]
    for key, typ, desc in _rows(schema, defs):
        out.append(f"| `{key}` | {typ} | {desc} |")
    out += [
        "",
        "Connector blocks (`datasource`, `labels`, `integrations.*`) take `type:` plus the options listed on the [connector pages](../connectors/overview.md).",
        "Durations use `<n>d`, `<n>w`, `<n>m` or `<n>y`. Gate expressions are described in [Governance](../governance/overview.md).",
    ]
    return "\n".join(out) + "\n"


def main() -> None:
    (ROOT / "docs/config/pecca-yaml.md").write_text(config_page())
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "typer",
            "pecca.cli.main",
            "utils",
            "docs",
            "--name",
            "pecca",
            "--output",
            str(ROOT / "docs/cli.md"),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if res.returncode != 0:
        raise SystemExit(f"typer docs failed: {res.stderr or res.stdout}")
    print("wrote docs/config/pecca-yaml.md and docs/cli.md")


if __name__ == "__main__":
    main()
