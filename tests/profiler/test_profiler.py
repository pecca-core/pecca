import json
import random

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from pecca.data.dataset import Dataset, canonicalize
from pecca.profiler import profile_call
from pecca.profiler.rules import infer_task_type


def _ds(inputs, outputs, human=None, call="c"):
    raw = pd.DataFrame({"i": inputs, "o": outputs, "h": human or [None] * len(outputs)})
    df = canonicalize(
        raw, {"input": "i", "llm_output": "o", "human_label": "h", "call_name": {"literal": call}}
    )
    return Dataset(df)


def test_classification():
    rng = random.Random(0)
    outs = [rng.choice(["Billing", "Cards", "Loans"]) for _ in range(600)]
    p = profile_call(_ds([f"text {i}" for i in range(600)], outs), "c")
    assert p.task_type == "classification" and p.replaceable
    assert p.labels == ["billing", "cards", "loans"] and p.input_type == "text"


def test_regression():
    p = profile_call(_ds([f"t{i}" for i in range(600)], [str(i / 7) for i in range(600)]), "c")
    assert p.task_type == "regression" and p.replaceable


def test_extraction_not_replaceable():
    outs = [json.dumps({"a": i, "b": "x"}) for i in range(600)]
    p = profile_call(_ds(["t"] * 600, outs), "c")
    assert p.task_type == "extraction" and not p.replaceable
    assert "not supported" in p.reason


def test_free_text():
    p = profile_call(
        _ds([f"t{i}" for i in range(600)], [f"reply number {i} " * 3 for i in range(600)]), "c"
    )
    assert p.task_type == "free_text" and not p.replaceable and "closed set" in p.reason


def test_insufficient_rows():
    p = profile_call(_ds([f"t{i}" for i in range(100)], ["a", "b"] * 50), "c")
    assert p.task_type == "classification" and not p.replaceable
    assert "n<500" in p.reason


def test_tabular_and_multi_text():
    raw = pd.DataFrame({"x": range(600), "y": range(600), "o": ["a", "b"] * 300, "s": ["hi"] * 600})
    df = canonicalize(
        raw, {"input": {"x": "x", "y": "y"}, "llm_output": "o", "call_name": {"literal": "c"}}
    )
    assert profile_call(Dataset(df), "c").input_type == "tabular"
    df = canonicalize(
        raw, {"input": {"s": "s", "t": "s"}, "llm_output": "o", "call_name": {"literal": "c"}}
    )
    assert profile_call(Dataset(df), "c").input_type == "multi_text"


def test_human_labels_and_imbalance():
    outs = ["a"] * 590 + ["b"] * 10
    human = ["a"] * 100 + [None] * 500
    p = profile_call(_ds([f"t{i}" for i in range(600)], outs, human), "c")
    assert p.n_human_labels == 100 and p.min_class_count == 10 and p.n_classes_below_20 == 1


@given(st.lists(st.text(max_size=8), min_size=1, max_size=40))
def test_infer_never_crashes(outs):
    task, _, _ = infer_task_type(outs, len(outs))
    assert task in {"classification", "regression", "extraction", "free_text"}
