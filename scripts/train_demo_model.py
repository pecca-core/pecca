"""Train the demo router with the public Pecca API and package it for Hugging Face.

    uv run python scripts/train_demo_model.py            # tfidf_linear + e5_logreg (expected winner: e5_logreg)
    uv run python scripts/train_demo_model.py --full     # also fine-tunes xlmr_finetune (slow on CPU)

Downloads intfloat/multilingual-e5-base (~1 GB) on first run. Runs in a throwaway PECCA_HOME.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CARD = """---
license: apache-2.0
library_name: pecca
pipeline_tag: text-classification
base_model: intfloat/multilingual-e5-base
datasets:
- pecca-core/demo-support-emails
tags: [pecca, onnx, routing]
---
# pecca-core/demo-router-e5-logreg

## What it does
Routes a synthetic customer-support email of the fictional "Northbridge Bank" to one of 60 RFI topics.
It is the demo model of [Pecca](https://github.com/pecca-core/pecca), which replaces repetitive LLM calls with
small, auditable models. **Not for production.**

## How it was trained
Pecca ran a tournament on the same cross-validated splits and measured macro-F1:

{leaderboard}

{note}

Training data: [pecca-core/demo-support-emails](https://huggingface.co/datasets/pecca-core/demo-support-emails)
({rows:,} rows; labels = human tag where present, else the simulated LLM's answer).

## Metrics
| | macro-F1 |
| --- | --- |
| this model (5-fold CV on training labels) | {metric:.3f} ± {std:.3f} |
| simulated "LLM" vs human labels (hold-out) | {llm} |

(The "LLM" is a noisy label generator with ~15% errors, not a real model. Synthetic data is far easier than real email.)

## Threshold & expected fallback
Calibration: {cal} on {basis}. Threshold **{thr:.2f}** (smallest confidence with precision >= {tp} on hold-out rows).
Expected fallback to the LLM: **{fb:.0%}** of calls.

## How to load with Pecca
```python
import pecca
from huggingface_hub import snapshot_download
model = pecca.load(snapshot_download("pecca-core/demo-router-e5-logreg"))
print(model.predict(["Card lost\\n\\nI lost my debit card ending ****1234, please block it."]))
```
The multilingual-e5-base encoder is downloaded from its own repository on first use.

## Limitations
Synthetic, code-mixed data (non-English emails keep the topic phrase in English). Latency/metrics are not representative
of real workloads. No real customer data was used.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="include xlmr_finetune")
    ap.add_argument("--data", default=str(ROOT / "data/pecca-demo-support-emails/train.parquet"))
    ap.add_argument("--out", default=str(ROOT / "models/pecca-demo-router"))
    a = ap.parse_args()
    os.environ.pop("PECCA_TEST_SMALL", None)  # real e5, not the hashing stand-in
    home = tempfile.mkdtemp(prefix="pecca-demo-")
    os.environ["PECCA_HOME"] = home
    os.chdir(home)

    import pecca
    from pecca.candidates import select_candidates

    ds = pecca.connect(
        "parquet",
        path=a.data,
        columns={
            "input": {"subject": "email_subject", "body": "email_body"},
            "llm_output": "llm_rfi",
            "human_label": "human_rfi",
            "call_name": {"literal": "route_rfi"},
        },
        input_template="{subject}\n\n{body}",
    )
    prof = pecca.profile(ds).profiles["route_rfi"]
    names = [c for c in select_candidates(prof) if a.full or c != "xlmr_finetune"]
    print("candidates:", names)
    tour = pecca.train("route_rfi", ds, candidates=names, target_precision=0.95, progress=print)
    print(
        f"tournament winner {tour.winner} {tour.metric_name}={tour.metric:.3f} llm={tour.llm_metric}"
    )
    scores = {e["candidate"]: e["metric"] for e in tour.leaderboard if e["status"] == "ok"}
    tour_board = tour.leaderboard
    if tour.winner == "e5_logreg":
        res, note = tour, "`e5_logreg` won the tournament."
    else:
        # The published demo model is e5_logreg regardless; the data decided the tournament, so say so.
        res = pecca.train(
            "route_rfi", ds, candidates=["e5_logreg"], target_precision=0.95, progress=print
        )
        margin = scores[tour.winner] - scores["e5_logreg"]
        note = (
            f"On this synthetic data `{tour.winner}` won the tournament by {margin:.3f} macro-F1. "
            "This published model is `e5_logreg` anyway: multilingual-e5 embeddings are more robust "
            "on real multilingual data, where templated phrasing is not repeated as it is here."
        )
    print(
        f"published {res.version}: {res.winner} {res.metric_name}={res.metric:.3f} threshold={res.threshold:.2f}"
    )

    from pecca.core import context

    call = context.get_call("route_rfi")
    mv = call.version(res.version)
    src = Path(call.model_dir(res.version))
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out, ignore=shutil.ignore_patterns("metadata.json"))
    if (src / "model.onnx").exists():
        (out / "onnx").mkdir(exist_ok=True)
        shutil.copy(src / "model.onnx", out / "onnx" / "model.onnx")
    (out / "metadata.json").write_text(json.dumps(mv.to_dict(), indent=2, default=str))

    # parity check: the packaged directory predicts the same as the trained model
    sample = ds.texts()[:100]
    native = pecca.predict("route_rfi", sample)
    packaged = pecca.load(str(out)).predict(sample)
    agree = sum(n.label == p.label for n, p in zip(native, packaged, strict=True))
    assert agree == 100, f"packaged model disagrees with trained model on {100 - agree} rows"
    print(f"format={mv.format}; packaged model matches on 100/100 rows")

    board = (
        "| candidate | macro-F1 | std | fit s | latency ms |\n| --- | --- | --- | --- | --- |\n"
        + "\n".join(
            f"| {e['candidate']}{' ★' if e.get('winner') else ''} | {e['metric']:.3f} | {e['metric_std']:.3f} | "
            f"{e['fit_time_s']:.1f} | {e['predict_latency_ms']:.1f} |"
            for e in tour_board
            if e["status"] == "ok"
        )
    )
    (out / "model_card.md").write_text(
        CARD.format(
            leaderboard=board,
            note=note,
            rows=mv.lineage["rows"],
            metric=mv.metric,
            std=mv.metric_std,
            llm="n/a" if mv.llm_metric is None else f"{mv.llm_metric:.3f}",
            cal=mv.calibration_kind,
            basis=mv.calibration_basis,
            thr=mv.threshold or 0.0,
            tp=mv.target_precision,
            fb=mv.expected_fallback_rate or 0.0,
        )
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
