"""Render sections to Markdown and convert to other formats."""

from __future__ import annotations

from typing import Any

from pecca.core.errors import PeccaError
from pecca.templates_util import render


def render_section(name: str, ctx: dict[str, Any], extras: dict[str, Any]) -> str:
    audit = {**ctx["audit"], **extras}
    return render(f"audit_pack/{name}.md.j2", **{**ctx, "audit": audit})


def to_pdf(markdown_text: str, path: str) -> str:
    try:
        import markdown as md
        from weasyprint import HTML
    except ImportError as e:
        raise PeccaError("PDF output needs extra dependencies", "pip install 'pecca[pdf]'") from e
    except OSError as e:  # weasyprint is installed but pango/glib are not
        raise PeccaError(
            f"PDF output needs system libraries ({e})",
            "install pango (macOS: brew install pango; Debian/Ubuntu: apt install libpango-1.0-0)",
        ) from e
    html = md.markdown(markdown_text, extensions=["tables", "fenced_code"])
    HTML(string=f"<html><body>{html}</body></html>").write_pdf(path)
    return path
