from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from pecca import __version__
from pecca.connectors.base import ServingTarget, register
from pecca.connectors.registry.local import LocalRegistry

APP = """from fastapi import FastAPI
from pydantic import BaseModel

from pecca.candidates import get_candidate
import json, pathlib

app = FastAPI(title="pecca-{call}")
MODEL_DIR = pathlib.Path(__file__).parent / "model"
cfg = json.loads((MODEL_DIR / "config.json").read_text())
labels = json.loads((MODEL_DIR / "labels.json").read_text())
cand = get_candidate(cfg["candidate"]).load(str(MODEL_DIR))


class Req(BaseModel):
    inputs: list[str]


@app.post("/predict")
def predict(req: Req):
    proba = cand.predict_proba(req.inputs)
    classes = cand.classes_
    return [{{"label": labels["forms"].get(classes[int(p.argmax())], classes[int(p.argmax())]),
              "confidence": float(p.max())}} for p in proba]
"""
DOCKERFILE = """FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""


@register("serving", "docker_export")
class DockerExportServing(ServingTarget):
    """Writes ``<out_dir>/<call>-<version>/`` with Dockerfile, FastAPI ``/predict`` app and the model."""

    def __init__(
        self,
        out_dir: str = "docker_export",
        home: str | None = None,
        pecca_version: str | None = None,
        **_: Any,
    ) -> None:
        self.out = Path(out_dir)
        self.registry = LocalRegistry(home or os.environ.get("PECCA_HOME") or ".pecca")
        self.pecca_version = pecca_version or __version__
        self._last: dict[str, str] = {}

    def deploy(self, path_key: str, version: str) -> str:
        call = path_key.rsplit("/", 1)[-1]
        d = self.out / f"{call}-{version}"
        if (d / "model").exists():
            shutil.rmtree(d / "model")
        shutil.copytree(self.registry.load_model(path_key, version), d / "model")
        (d / "app.py").write_text(APP.format(call=call))
        (d / "Dockerfile").write_text(DOCKERFILE)
        (d / "requirements.txt").write_text(f"pecca=={self.pecca_version}\nfastapi\nuvicorn\n")
        self._last[path_key] = str(d)
        return str(d)

    def endpoint(self, path_key: str) -> str | None:
        return None
