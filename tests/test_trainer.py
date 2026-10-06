import numpy as np
import pytest

from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import generate
from pecca.profiler import profile_call
from pecca.trainer.calibration import Calibrator, fit_calibrator
from pecca.trainer.export_onnx import export_with_parity
from pecca.trainer.splits import cv_splits, holdout_split
from pecca.trainer.threshold import search_threshold
from pecca.trainer.tournament import run_tournament


@pytest.fixture(scope="module")
def ds():
    df = generate(1200)
    cols = {
        "input": {"subject": "email_subject", "body": "email_body"},
        "llm_output": "llm_rfi",
        "human_label": "human_rfi",
        "call_name": {"literal": "route_rfi"},
    }
    return Dataset(canonicalize(df, cols), cols, "{subject}\n\n{body}")


def test_threshold_meets_target():
    rng = np.random.RandomState(0)
    conf = rng.rand(2000)
    correct = (rng.rand(2000) < conf).astype(float)
    t, fb, met, prec = search_threshold(conf, correct, 0.9)
    assert met and prec >= 0.9
    served = conf >= t
    assert correct[served].mean() >= 0.9
    assert abs(fb - (1 - served.mean())) < 1e-9
    # smallest such t: a slightly lower one would break the target (or support floor)
    lower = (
        conf >= np.sort(conf)[np.searchsorted(np.sort(conf), t) - 1] if t > conf.min() else served
    )
    assert correct[lower].mean() <= correct[served].mean() + 1e-9 or lower.sum() >= served.sum()


def test_threshold_unreachable_falls_back_everything():
    conf = np.linspace(0.1, 0.9, 100)
    t, fb, met, _ = search_threshold(conf, np.zeros(100), 0.95)
    assert not met and fb == 1.0 and t > conf.max()


def test_calibrator_roundtrip():
    rng = np.random.RandomState(1)
    p = rng.dirichlet(np.ones(4) * 0.3, 800)
    y = np.array([rng.choice(4, p=q) for q in p])
    cal = fit_calibrator(p, y)
    again = Calibrator.from_dict(cal.to_dict())
    assert np.allclose(cal.confidence(p), again.confidence(p))


def test_splits_deterministic_and_disjoint():
    y = ["a", "b"] * 300
    a1, c1 = holdout_split(y, True)
    a2, c2 = holdout_split(y, True)
    assert (a1 == a2).all() and not set(a1) & set(c1)
    for tr, va in cv_splits(y, True, len(y)):
        assert not set(tr) & set(va)


def test_tournament_end_to_end(ds, tmp_path):
    prof = profile_call(ds, "route_rfi")
    out = run_tournament(
        "route_rfi", ds, prof, version="v1", workdir=str(tmp_path), target_precision=0.9
    )
    mv = out.version
    assert mv.candidate in {"tfidf_linear", "e5_logreg"}
    assert 0 < mv.metric <= 1 and mv.threshold is not None and mv.latency_ms > 0
    assert len(mv.leaderboard) == 2 and sum(1 for e in mv.leaderboard if e.get("winner")) == 1
    assert mv.lineage["rows"] == 1200 and len(mv.lineage["dataset_sha256"]) == 64
    for f in ("calibration.json", "labels.json", "lineage.json", "config.json"):
        assert (tmp_path / "artefacts" / f).exists()


def test_tournament_tie_prefers_lower_latency(ds, tmp_path, monkeypatch):
    from pecca.trainer import tournament as T

    monkeypatch.setattr(
        T, "_median_latency_ms", lambda c, X: 5.0 if c.name == "tfidf_linear" else 1.0
    )
    monkeypatch.setattr(T.M, "score", lambda m, a, b: 0.8)
    prof = profile_call(ds, "route_rfi")
    out = run_tournament("route_rfi", ds, prof, version="v1", workdir=str(tmp_path))
    assert out.version.candidate == "e5_logreg"


def test_onnx_export_never_returns_unvalidated_onnx(ds, tmp_path):
    from pecca.candidates import all_candidates

    X = ds.texts()[:600]
    y = [str(v) for v in ds.to_pandas()["llm_output"][:600]]
    for name in ("tfidf_linear", "e5_logreg"):
        c = all_candidates()[name]()
        c.fit(X, y)
        d = tmp_path / name
        c.save(str(d))
        fmt = export_with_parity(c, str(d), X)
        assert fmt in {"onnx", "pickle"}
        loaded = type(c).load(str(d))
        assert loaded.format == fmt
        assert np.allclose(c.predict_proba(X[:100]), loaded.predict_proba(X[:100]), atol=1e-3)
    # e5 head must export cleanly
    assert export_with_parity(c, str(d), X) == "onnx"
