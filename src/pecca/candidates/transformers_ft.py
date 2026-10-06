"""Fine-tuned encoder transformer candidate (xlm-roberta-base by default)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from pecca.candidates.base import Candidate
from pecca.candidates.registry import register

BASE_MODEL = "xlm-roberta-base"  # alternative: microsoft/mdeberta-v3-base


def _device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@register("xlmr_finetune", task_types=["classification"], min_rows=2000, requires_gpu=True,
          estimated_latency_ms=80.0, input_types=("text", "multi_text"), _builtin=True)
class XlmrFinetune(Candidate):
    max_len = 256
    epochs = 3
    lr = 2e-5
    batch_size = 16

    def __init__(self, base_model: str | None = None) -> None:
        self.base_model = base_model or os.environ.get("PECCA_XLMR_BASE", BASE_MODEL)
        self._tok: Any = None
        self._model: Any = None
        self._classes: list[str] = []
        self.format = "hf"

    @property
    def classes_(self) -> list[str]:
        return self._classes

    def fit(self, X: list[Any], y: list[Any]) -> None:
        import torch
        from sklearn.metrics import f1_score
        from sklearn.model_selection import train_test_split
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.manual_seed(42)
        self._classes = sorted({str(v) for v in y})
        idx = {c: i for i, c in enumerate(self._classes)}
        labels = np.array([idx[str(v)] for v in y])
        texts = [str(x) for x in X]
        try:
            tr, va = train_test_split(range(len(texts)), test_size=0.1, random_state=42, stratify=labels)
        except ValueError:
            tr, va = train_test_split(range(len(texts)), test_size=0.1, random_state=42)
        dev = _device()
        self._tok = AutoTokenizer.from_pretrained(self.base_model)
        model = AutoModelForSequenceClassification.from_pretrained(
            self.base_model, num_labels=len(self._classes)
        ).to(dev)
        opt = torch.optim.AdamW(model.parameters(), lr=self.lr)
        best, best_state = -1.0, None
        for _ in range(self.epochs):
            model.train()
            order = np.random.RandomState(42).permutation(tr)
            for s in range(0, len(order), self.batch_size):
                b = order[s : s + self.batch_size]
                enc = self._tok([texts[i] for i in b], truncation=True, max_length=self.max_len,
                                padding=True, return_tensors="pt").to(dev)
                out = model(**enc, labels=torch.tensor(labels[b]).to(dev))
                out.loss.backward()
                opt.step()
                opt.zero_grad()
            self._model = model
            pred = self._predict_idx([texts[i] for i in va], dev)
            f1 = f1_score(labels[list(va)], pred, average="macro")
            if f1 > best:  # early stopping: keep the best epoch
                best = f1
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if best_state is not None:
            model.load_state_dict(best_state)
        self._model = model.to("cpu").eval()

    def _logits(self, texts: list[str], dev: str) -> np.ndarray:
        import torch

        self._model.eval()
        outs = []
        with torch.no_grad():
            for s in range(0, len(texts), 32):
                enc = self._tok(texts[s : s + 32], truncation=True, max_length=self.max_len,
                                padding=True, return_tensors="pt").to(dev)
                outs.append(self._model.to(dev)(**enc).logits.cpu().numpy())
        return np.vstack(outs) if outs else np.zeros((0, len(self._classes)))

    def _predict_idx(self, texts: list[str], dev: str) -> np.ndarray:
        return self._logits(texts, dev).argmax(axis=1)

    def predict_proba(self, X: list[Any]) -> np.ndarray:
        z = self._logits([str(x) for x in X], "cpu")
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return np.asarray(e / e.sum(axis=1, keepdims=True), dtype=np.float64)

    def predict(self, X: list[Any]) -> np.ndarray:
        return np.asarray(self._classes, dtype=object)[self.predict_proba(X).argmax(axis=1)]

    def save(self, path: str) -> None:
        d = Path(path)
        (d / "hf").mkdir(parents=True, exist_ok=True)
        self._model.save_pretrained(d / "hf")
        self._tok.save_pretrained(d / "hf")
        (d / "candidate.json").write_text(
            json.dumps({"candidate": self.name, "classes": self._classes, "base_model": self.base_model})
        )

    @classmethod
    def load(cls, path: str) -> XlmrFinetune:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        d = Path(path)
        meta = json.loads((d / "candidate.json").read_text())
        obj = cls(meta.get("base_model"))
        obj._classes = meta["classes"]
        obj._tok = AutoTokenizer.from_pretrained(d / "hf")
        obj._model = AutoModelForSequenceClassification.from_pretrained(d / "hf").eval()
        return obj
