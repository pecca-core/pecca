# Threshold and fallback

Confidence is calibrated on the hold-out split with **temperature scaling** (isotonic is used instead only when there are ≤ 10 classes and ≥ 500 calibration rows *and* it lowers the calibration error).
When enough human-labelled hold-out rows exist (≥ 200) calibration and the threshold use those, because noise in LLM labels would otherwise cap the measurable precision.

The **threshold** is the smallest confidence `t` such that precision on hold-out rows with `confidence >= t` is at least `target_precision` (default 0.95). `expected_fallback_rate` is the share of hold-out rows below `t`. If no threshold reaches the target, everything falls back to the LLM and the audit pack says so.

In `live` mode: `confidence >= t` → the model answers; otherwise your original function is called. Regression calls have no confidence and are always served by the model.
Tune with `target_precision` in `calls.<name>.policy`.
