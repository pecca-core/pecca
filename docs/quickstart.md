# Quickstart

Everything below runs offline on the bundled synthetic dataset (a fictional "Northbridge Bank"). The outputs are real.

```bash
pip install pecca
pecca datasets demo
```
```text
6,000 rows → ./data/demo
```

## 1. Create a project
```bash
pecca init --profile none
```
```text
created pecca.yaml, templates/
```
`init` wires `data/demo/calls.csv` as the datasource when it exists. The `none` profile only has metric gates (see [Governance](governance/overview.md)).

## 2. Profile the calls
```bash
pecca profile
```
```text
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ call           ┃ task           ┃ classes   ┃ rows       ┃ languages ┃ replaceable                    ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ generate_reply │ free_text      │ —         │ 800 rows   │ en,tl,es  │ ✘ outputs are not a closed set │
│ route_domain   │ classification │ 12 labels │ 6,000 rows │ en,tl,es  │ ✔                              │
│ route_rfi      │ classification │ 60 labels │ 6,000 rows │ en,tl,es  │ ✔                              │
└────────────────┴────────────────┴───────────┴────────────┴───────────┴────────────────────────────────┘
```
`generate_reply` returns a different text every time, so Pecca refuses to replace it.

## 3. Train
```bash
pecca train default/default/route_rfi --candidates tfidf_linear,e5_logreg
```
```text
training default/default/route_rfi ...
  tfidf_linear: macro_f1 0.9148
  e5_logreg: macro_f1 0.9093
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┓
┃ candidate      ┃ macro_f1 ┃ std   ┃ fit s ┃ latency ms ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━┩
│ ★ tfidf_linear │ 0.915    │ 0.011 │ 0.9   │ 0.4        │
│ e5_logreg      │ 0.909    │ 0.011 │ 8.6   │ 0.2        │
└────────────────┴──────────┴───────┴───────┴────────────┘
winner tfidf_linear  macro_f1 0.91 vs llm 0.83
threshold 0.70  expected fallback 0%
saved v1 → .pecca/default/default/route_rfi/versions/v1
```
Without `--candidates`, Pecca also fine-tunes `xlmr_finetune` for calls with 2,000+ rows. On a machine with no GPU/MPS it is skipped automatically above 5,000 rows (with a warning); on a GPU or Apple Silicon it runs and is slow on a laptop, so this quickstart limits the tournament to the two fast candidates.
The *data* decides the winner: on this synthetic data TF-IDF edges out the e5 embedding model.

## 4. Shadow it
```bash
pecca promote default/default/route_rfi --mode shadow
```
```text
shadow since now
```
Decorate the function you already have (`toy.py`):
```python
@pecca.replace(
    "route_rfi",
    mode="shadow",
    input_adapter=lambda text: {"subject": text.split("\n\n")[0], "body": text.split("\n\n", 1)[1]},
)
def route_rfi(text: str) -> str:
    return my_llm.classify(text)
```
```text
ran 40 emails in shadow mode
```

## 5. Check status
```bash
pecca status default/default/route_rfi
```
```text
call       default/default/route_rfi
mode       shadow          since 2026-10-06
version    v1              trained 2026-10-06 on 6,000 rows
model      tfidf_linear    macro_f1 0.91  (llm 0.83)
threshold  0.70            expected fallback 0%
agreement  0.95 (14d)      fallback 0%   drift 0.60
policy     shadow_at cv_metric>=0.80  live_at agreement>=0.85 & shadow_days>=7
next       -
```

## 6. Go live
```bash
pecca promote default/default/route_rfi --mode live
```
```text
blocked: shadow->live
  gate failing: shadow_days >= 7 (actual 0.000104)
```
The gate `shadow_days >= 7` is doing its job: in production the model must run next to the LLM for a week first. For this local demo, relax the gate in `pecca.yaml` (under `projects.default.governance`), apply it, and promote again:
```yaml
    governance:
      extends: none
      transitions:
        shadow->live:
          gates: ["agreement >= 0.85", "shadow_days >= 0"]   # demo only; keep 7+ in real use
```
```bash
pecca apply
pecca promote default/default/route_rfi --mode live
```
```text
live since now
```
```text
call       default/default/route_rfi
mode       live            since 2026-10-06
...
policy     shadow_at cv_metric>=0.80  live_at agreement>=0.85 & shadow_days>=0
```
Changing a gate is a reviewable config change; `pecca apply` prints the diff. (`pecca promote --force` exists for emergencies, needs `PECCA_ALLOW_FORCE=1` and is written to the audit trail, but it is not how you go live.)

Next: [modes](concepts/modes.md), [the tournament](concepts/tournament.md), [governance](governance/overview.md).
