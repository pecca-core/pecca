# Autoresponse routing (example)

A bank's email-reply system classifies every incoming customer email into one of ~60 RFI topics with an LLM call
before deciding whether to auto-reply. The calls return a fixed label, run on every email, and months of logged
answers plus human agent tags already exist. Pecca replaces them. All data is synthetic ("Northbridge Bank") and the
LLM is a deterministic mock, so everything runs offline.

| file | what it shows |
| --- | --- |
| `before.py` | the pipeline today: one LLM call per email |
| `after.py` | one decorator, shadow mode, LLM unchanged |
| `greenfield.py` | no logs yet: record → train → shadow |
| `pecca.yaml` | project config with a CSV datasource and governance |

```bash
pecca datasets demo            # writes ./data/demo (from the repo root)
cd examples/autoresponse_routing
python before.py               # 200 emails -> 200 LLM calls
python greenfield.py           # records 1,500 calls, trains, promotes to shadow
python after.py                # shadow: model runs next to the LLM, agreement is logged
pecca status default/default/route_rfi
```

Or, with historical data and the config in this folder: `pecca apply && pecca profile && pecca train autoresponse/route_rfi`.
