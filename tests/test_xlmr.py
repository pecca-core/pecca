"""Exercise the fine-tuning candidate offline with a tiny randomly initialised BERT."""

import numpy as np
import pytest

transformers = pytest.importorskip("transformers")
torch = pytest.importorskip("torch")


@pytest.fixture()
def tiny_base(tmp_path):
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

    words = [
        "card",
        "loan",
        "login",
        "stolen",
        "rate",
        "password",
        "lost",
        "interest",
        "app",
        "blocked",
    ]
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", *words]
    (tmp_path / "vocab.txt").write_text("\n".join(vocab))
    tok = BertTokenizerFast(str(tmp_path / "vocab.txt"))
    d = tmp_path / "tiny"
    tok.save_pretrained(d)
    BertForSequenceClassification(
        BertConfig(
            vocab_size=len(vocab),
            hidden_size=16,
            num_hidden_layers=1,
            num_attention_heads=2,
            intermediate_size=32,
            max_position_embeddings=64,
            num_labels=3,
        )
    ).save_pretrained(d)
    return str(d)


def test_xlmr_fit_predict_save_load(tiny_base, tmp_path, monkeypatch):
    from pecca.candidates import get_candidate
    from pecca.candidates.transformers_ft import XlmrFinetune

    monkeypatch.setattr(XlmrFinetune, "epochs", 6)
    monkeypatch.setattr(XlmrFinetune, "lr", 5e-3)
    monkeypatch.setattr(XlmrFinetune, "max_len", 16)
    monkeypatch.setenv("PECCA_XLMR_BASE", tiny_base)
    # Accuracy bar is not stable on MPS. This test checks fit/save/load, which CPU already covers.
    monkeypatch.setattr("pecca.candidates.transformers_ft._device", lambda: "cpu")
    rng = np.random.RandomState(0)
    vocab = {
        "a": ["card", "stolen", "lost"],
        "b": ["loan", "rate", "interest"],
        "c": ["login", "password", "app"],
    }
    X, y = [], []
    for _ in range(150):
        k = rng.choice(list(vocab))
        X.append(" ".join(rng.choice(vocab[k], 4)))
        y.append(k)
    cand = get_candidate("xlmr_finetune")()
    cand.fit(X, y)
    proba = cand.predict_proba(X[:30])
    assert proba.shape == (30, 3) and np.allclose(proba.sum(axis=1), 1)
    assert (cand.predict(X) == np.array(y)).mean() > 0.6
    cand.save(str(tmp_path / "m"))
    assert not cand.to_onnx(str(tmp_path / "m" / "model.onnx"))
    loaded = XlmrFinetune.load(str(tmp_path / "m"))
    assert np.allclose(
        loaded.predict_proba(X[:10]), cand.predict_proba(X[:10]), atol=1e-4
    ) and loaded.classes_ == ["a", "b", "c"]
