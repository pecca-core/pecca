"""MLflow pyfunc wrapper around a Pecca model directory."""

from __future__ import annotations

from typing import Any

import mlflow.pyfunc
import pandas as pd


class PeccaPyfunc(mlflow.pyfunc.PythonModel):  # type: ignore[misc]
    """Input: a DataFrame with a ``text`` column (or the first column). Output: label/confidence/fallback."""

    def load_context(self, context: Any) -> None:
        from pecca.runtime.predictor import Bundle

        self.bundle = Bundle(context.artifacts["pecca_model"])

    def predict(self, context: Any, model_input: pd.DataFrame, params: Any = None) -> pd.DataFrame:
        col = "text" if "text" in model_input else model_input.columns[0]
        preds = self.bundle.predict(model_input[col].tolist())
        return pd.DataFrame({"label": [p.label for p in preds], "confidence": [p.confidence for p in preds],
                             "fallback": [p.fallback for p in preds]})
