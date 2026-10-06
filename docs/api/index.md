# API reference

```python
import pecca

(
    pecca.connect,
    pecca.profile,
    pecca.train,
    pecca.predict,
    pecca.replace,
    pecca.evaluate,
)
(
    pecca.retrain,
    pecca.audit_pack,
    pecca.register,
    pecca.promote,
    pecca.approve,
    pecca.load,
    pecca.as_tool,
)
```

::: pecca.api
    options:
      members: [connect, profile, train, retrain, predict, evaluate, promote, approve, audit_pack, load, as_tool]
      show_root_heading: false

::: pecca.core.models
    options:
      members: [CallProfile, ModelVersion, Prediction, TrainResult, EvalReport, Decision, CallState]

::: pecca.candidates.base.Candidate
