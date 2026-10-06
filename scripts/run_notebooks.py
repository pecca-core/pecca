"""Execute notebooks in place and keep their outputs committed-clean.

    uv run python scripts/run_notebooks.py [paths...]      # default: every notebook under examples/
    PECCA_NB_KERNEL=pecca-nb uv run python scripts/run_notebooks.py examples/quickstart.ipynb

* `%pip` cells have their output cleared (it is environment noise and leaks local paths).
* Fails if any cell errors, or if any output contains a local filesystem path.
* Cells that need Docker are guarded in the notebook with `PECCA_SKIP_DOCKER=1` (set it in CI).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
LEAKS = re.compile(r"/Users/|/private/|/var/folders|/home/runner|C:\\\\Users")


def run(path: Path) -> None:
    nb = nbformat.read(path, 4)
    kernel = os.environ.get("PECCA_NB_KERNEL", "python3")
    ep = ExecutePreprocessor(timeout=900, kernel_name=kernel, allow_errors=False)
    ep.preprocess(nb, {"metadata": {"path": str(path.parent)}})
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        if cell.source.lstrip().startswith("%pip"):
            cell.outputs = []
            continue
        for out in cell.get("outputs", []):
            text = out.get("text", "") or str(out.get("data", {}).get("text/plain", "")) + str(
                out.get("data", {}).get("text/html", "")
            )
            if LEAKS.search(text):
                raise SystemExit(f"{path}: output leaks a local path:\n{text[:300]}")
    nb.metadata.pop("widgets", None)
    nbformat.write(nb, path)
    print(f"ok  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name}")


def main() -> None:
    paths = [Path(p).resolve() for p in sys.argv[1:]] or sorted(ROOT.glob("examples/**/*.ipynb"))
    for p in paths:
        run(p)


if __name__ == "__main__":
    main()
