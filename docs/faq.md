# FAQ

**Does Pecca call an LLM?** No. Pecca core contains no LLM provider SDK or endpoint. It learns from answers your own function already returned.

**Do I need a GPU?** No for inference (CPU, milliseconds). Optional for fine-tuning `xlmr_finetune`.

**Which model will it pick?** The data decides: every eligible candidate is trained on the same cross-validated splits and the best measured metric wins.

**Is this distillation?** Related. Pecca targets small *non-LLM* models (linear, tree, encoder) for closed-set decisions, with calibrated fallback to the original LLM and governance around promotion.

**Is my data sent anywhere?** No. There is no telemetry. Data only goes to the connectors you configure.

**What if the model is wrong?** Below the calibrated threshold the LLM answers. Keep shadow running, watch `agreement` and `drift`, and `pecca promote --mode shadow` to demote at any time.

**Can it replace extraction calls?** Not in v0.1 (profiled only). See the roadmap in the README.
