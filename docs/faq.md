# FAQ

**Does Pecca call an LLM?** No. Pecca core contains no LLM provider SDK or endpoint. It learns from answers your own function already returned.

**Do I need a GPU?** No for inference (CPU, milliseconds). Optional for fine-tuning `xlmr_finetune`.

**Which model will it pick?** The data decides: every eligible candidate is trained on the same cross-validated splits and the best measured metric wins.

**Is this distillation?** Related. Pecca targets small *non-LLM* models (linear, tree, encoder) for closed-set decisions, with calibrated fallback to the original LLM and governance around promotion.

**Is my data sent anywhere?** No. There is no telemetry. Data only goes to the connectors you configure.

**What if the model is wrong?** Below the calibrated threshold the LLM answers. Keep shadow running, watch `agreement` and `drift`, and `pecca promote --mode shadow` to demote at any time.

**Can it replace extraction calls?** Not in v0.1 (profiled only). See the roadmap in the README.

**ONNX export status?** The winner is exported to ONNX only when its output matches the native model within 1e-3 on 100 rows; otherwise the native artefact is kept and `format` records it.

* `e5_logreg` / `e5_ridge`: only the **linear head** is exported to ONNX (exact parity). The multilingual-e5 encoder still runs through `sentence-transformers` (PyTorch) at inference time; an ONNX/int8 encoder export is not in v0.1.
* `tfidf_linear` / `tfidf_ridge`: skl2onnx's TF-IDF tokenizer does not reproduce scikit-learn's probabilities (differences up to ~0.2), so the parity check fails and these models are served from the pickled scikit-learn pipeline. Latency is still about a millisecond on CPU.
* `xlmr_finetune`: kept as a Hugging Face directory (PyTorch); no ONNX or int8 export in v0.1.
* LightGBM models are not exported to ONNX in v0.1 (pickle).
