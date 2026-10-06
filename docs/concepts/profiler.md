# Profiler

`pecca profile` applies deterministic rules to each call's logged outputs. No LLM is involved.

1. Compute `n_rows`, `n_unique_outputs`, `unique_ratio`.
2. If ≥ 95% of outputs are JSON objects with the same keys: **extraction** (profiled only; not replaceable in v0.1).
3. Else if ≥ 98% parse as numbers: **regression**.
4. Else if `n_unique <= max(50, 5% of rows)` and `unique_ratio <= 0.05`: **classification**.
5. Else: **free_text**, not replaceable ("outputs are not a closed set").
6. Input type: `text`, `multi_text` or `tabular`.
7. `replaceable` also needs at least `min_rows` rows (default 500).
8. Languages (≥ 5% share, on a sample of 500 inputs), `min_class_count` and `n_classes_below_20` are recorded.

With 60 classes you need at least 1,200 rows to be a "closed set" (5% rule).
