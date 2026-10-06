"""Join late-arriving human labels onto a canonical frame."""

from __future__ import annotations

import pandas as pd

from pecca.core.errors import SchemaError


def join_labels(
    df: pd.DataFrame, labels: pd.DataFrame, join_on: str, column: str, id_col: str | None = None
) -> pd.DataFrame:
    """Fill null ``human_label`` from ``labels[column]`` matching ``labels[join_on]``.

    The canonical frame is matched through ``request_id`` (or ``id_col``).
    """
    key = id_col or "request_id"
    if key not in df.columns or df[key].isna().all():
        raise SchemaError("cannot join labels: canonical data has no request_id")
    if join_on not in labels.columns or column not in labels.columns:
        raise SchemaError(
            f"label table needs columns {join_on!r} and {column!r}",
            f"found: {list(labels.columns)}",
        )
    lookup = labels.drop_duplicates(join_on).set_index(join_on)[column]
    out = df.copy()
    mapped = out[key].map(lookup)
    out["human_label"] = out["human_label"].where(out["human_label"].notna(), mapped)
    return out
