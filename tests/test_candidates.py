import warnings

import numpy as np
import pytest

from pecca.candidates import all_candidates, register, select_candidates, Candidate
from pecca.candidates.registry import _REGISTRY
from pecca.core.models import CallProfile


def prof(task="classification", inp="text", n=1000):
    return CallProfile(call="c", n_rows=n, n_unique_outputs=3, unique_ratio=0.0, task_type=task,
                       input_type=inp, replaceable=True)


def test_selection_rules():
    assert select_candidates(prof(n=1000), has_gpu=True) == ["tfidf_linear", "e5_logreg"]
    assert select_candidates(prof(n=2000), has_gpu=True) == ["tfidf_linear", "e5_logreg", "xlmr_finetune"]
    assert select_candidates(prof("regression")) == ["tfidf_ridge", "e5_ridge"]
    assert select_candidates(prof(inp="tabular")) == ["logreg", "lightgbm"]
    assert select_candidates(prof("regression", "tabular")) == ["ridge", "lightgbm_reg"]
    assert select_candidates(prof("classification", "multi_text", 3000), has_gpu=True)[-1] == "xlmr_finetune"


def test_latency_budget_removes_transformers():
    assert select_candidates(prof(n=3000), latency_budget_ms=5, has_gpu=True) == ["tfidf_linear"]


def test_xlmr_skipped_without_gpu_on_large_data():
    with pytest.warns(UserWarning):
        names = select_candidates(prof(n=30000), has_gpu=False)
    assert "xlmr_finetune" not in names


def test_plugin_registration():
    @register("plug", task_types=["classification"], min_rows=500)
    class Plug(Candidate):
        def fit(self, X, y): ...
        def predict_proba(self, X): ...
        def predict(self, X): ...
        classes_ = []
        def save(self, path): ...
        @classmethod
        def load(cls, path): ...

    try:
        assert "plug" in select_candidates(prof(n=1000), has_gpu=True)
        assert "plug" not in select_candidates(prof(n=100), has_gpu=True)
        assert "plug" not in select_candidates(prof("regression"), has_gpu=True)
    finally:
        _REGISTRY.pop("plug")


def test_all_builtins_registered():
    assert {"tfidf_linear", "tfidf_ridge", "e5_logreg", "e5_ridge", "xlmr_finetune",
            "logreg", "lightgbm", "ridge", "lightgbm_reg"} <= set(all_candidates())


@pytest.mark.parametrize("name", ["e5_logreg"])  # tfidf: see test_trainer (parity-gated fallback)
def test_fit_save_load_onnx_parity(name, tmp_path):
    rng = np.random.RandomState(0)
    words = {"a": ["card", "lost", "stolen"], "b": ["loan", "rate", "interest"], "c": ["login", "app", "password"]}
    X, y = [], []
    for _ in range(300):
        k = rng.choice(list(words))
        X.append(" ".join(rng.choice(words[k], 6)) + f" ref{rng.randint(9)}")
        y.append(k)
    cand = all_candidates()[name]()
    cand.fit(X, y)
    native = cand.predict_proba(X[:50])
    cand.save(str(tmp_path))
    assert cand.to_onnx(str(tmp_path / "model.onnx"))
    loaded = type(cand).load(str(tmp_path))
    assert loaded.format == "onnx"
    assert np.allclose(native, loaded.predict_proba(X[:50]), atol=1e-3)
    assert list(loaded.predict(X[:5])) == list(cand.predict(X[:5]))


def test_tabular_candidates():
    rng = np.random.RandomState(0)
    X = [{"f1": float(a), "f2": float(b)} for a, b in rng.randn(200, 2)]
    y = ["p" if x["f1"] + x["f2"] > 0 else "n" for x in X]
    for name in ["logreg", "lightgbm"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c = all_candidates()[name]()
            c.fit(X, y)
            assert (c.predict(X) == np.array(y)).mean() > 0.9
    r = all_candidates()["ridge"]()
    r.fit(X, [x["f1"] * 2 for x in X])
    assert abs(r.predict(X[:3])[0] - X[0]["f1"] * 2) < 0.2
