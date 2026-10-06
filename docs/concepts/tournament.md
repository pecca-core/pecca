# Tournament

The user says *what* to replace; Pecca owns *how*. Eligible candidates are chosen by rules, trained on **the same** splits, and the winner is picked by measured metric.

| Task | < 2,000 rows | ≥ 2,000 rows |
| --- | --- | --- |
| text classification | `tfidf_linear`, `e5_logreg` | + `xlmr_finetune` |
| text regression | `tfidf_ridge`, `e5_ridge` | same |
| tabular classification / regression | `logreg`, `lightgbm` / `ridge`, `lightgbm_reg` | same |

`latency_budget_ms < 10` removes transformer candidates. Without a GPU/MPS, `xlmr_finetune` is skipped above 5,000 rows (a warning says how to include it: `--candidates`). Custom candidates join via [`@pecca.register`](../extending/custom-candidates.md).

Procedure: hold out 15% for calibration, run stratified 5-fold CV (3-fold under 2,000 rows) with `random_state=42`, record mean/std of the primary metric (`macro_f1`, or `rmse` for regression), fit time and median single-row CPU latency (200 predictions). Highest metric wins; ties go to lower latency. The winner is refit, calibrated, thresholded and exported (ONNX when its output matches the native model within 1e-3, otherwise the native artefact).

`llm_metric` compares the LLM's output to `human_label` on the same hold-out rows. Without human labels it is `None` and the model is only shown to *match* the LLM, not exceed it.

!!! note
    `PECCA_TEST_SMALL=1` swaps the e5 encoder for a tiny local hashing embedder and drops `xlmr_finetune`. Use it in CI and tests; it never downloads a model.
