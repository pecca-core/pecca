# Custom candidates

```python
import numpy as np
import pecca
from pecca.candidates import Candidate


@pecca.register("my_knn", task_types=["classification"], min_rows=1000, estimated_latency_ms=3)
class MyKnn(Candidate):
    def fit(self, X, y): ...
    def predict_proba(self, X) -> np.ndarray: ...  # (n, n_classes)
    def predict(self, X) -> np.ndarray: ...
    @property
    def classes_(self): ...
    def save(self, path): ...
    @classmethod
    def load(cls, path): ...
    def to_onnx(self, path) -> bool:
        return False  # optional
```
`X` is a list of rendered strings (text calls) or dicts of numbers (tabular). A registered candidate whose `task_types` match and `min_rows` is satisfied joins every tournament for that task, and wins only by measured metric. `SklearnCandidate` is a helper base for scikit-learn estimators (implement `_build()`).
