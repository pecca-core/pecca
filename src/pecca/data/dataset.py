"""Canonical schema, column mapping, validation and the ``Dataset`` wrapper."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

import pandas as pd

from pecca.core.errors import SchemaError

REQUIRED = ("input", "llm_output", "human_label", "call_name")
OPTIONAL = (
    "timestamp",
    "llm_model",
    "language",
    "channel",
    "segment",
    "request_id",
    "latency_ms",
    "cost_usd",
)
CANONICAL_COLUMNS = (*REQUIRED, *OPTIONAL, "extra")

_STRIP = " \t\r\n\"'`.,;:!"


def normalise_output(value: Any) -> str:
    """Strip, lowercase and remove surrounding quotes/punctuation."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value).strip().strip(_STRIP).lower()


def render_input(value: Any, template: str | None = None) -> str:
    """Render a canonical ``input`` (str or dict of fields) to model text."""
    if isinstance(value, dict):
        if template:
            try:
                return template.format(**{k: ("" if v is None else v) for k, v in value.items()})
            except KeyError as e:
                raise SchemaError(
                    f"input_template references unknown field {e}",
                    f"available fields: {sorted(value)}",
                ) from e
        return "\n\n".join(str(v) for v in value.values())
    return "" if value is None else str(value)


def resolve_labels(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """``label = human_label if not null else llm_output`` and its source, both normalised."""
    labels: list[str] = []
    sources: list[str] = []
    for human, llm in zip(df["human_label"], df["llm_output"], strict=True):
        if human is not None and not (isinstance(human, float) and human != human) and human != "":
            labels.append(normalise_output(human))
            sources.append("human")
        else:
            labels.append(normalise_output(llm))
            sources.append("llm")
    return labels, sources


def dataset_hash(inputs: list[str]) -> str:
    h = hashlib.sha256()
    for s in sorted(inputs):
        h.update(s.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def canonicalize(
    raw: pd.DataFrame,
    columns: dict[str, Any],
    input_template: str | None = None,
) -> pd.DataFrame:
    """Map user columns to the canonical schema; raises ``SchemaError`` listing problems."""
    allowed = set(REQUIRED) | set(OPTIONAL)
    unknown = sorted(set(columns) - allowed)
    missing_keys = [k for k in ("input", "llm_output", "call_name") if k not in columns]
    if unknown or missing_keys:
        raise SchemaError(
            "bad column mapping"
            + (f": missing mapping for {missing_keys}" if missing_keys else "")
            + (f"; unknown canonical fields {unknown}" if unknown else ""),
            f"canonical fields: {sorted(allowed)}",
        )

    def src_cols(spec: Any) -> list[str]:
        if isinstance(spec, dict):
            if "literal" in spec:
                return []
            return [str(v) for v in spec.values()]
        return [str(spec)]

    needed: list[str] = []
    for spec in columns.values():
        if spec is not None:
            needed += src_cols(spec)
    absent = sorted({c for c in needed if c not in raw.columns})
    if absent:
        raise SchemaError(
            f"columns not found in data: {absent}", f"available columns: {list(raw.columns)}"
        )

    out = pd.DataFrame(index=raw.index)
    inp = columns["input"]
    if isinstance(inp, dict):
        names = list(inp)
        columns_data = [list(raw[inp[n]]) for n in names]
        records = [dict(zip(names, vals, strict=True)) for vals in zip(*columns_data, strict=True)]
        out["input"] = pd.Series(records, index=raw.index, dtype=object)
    else:
        out["input"] = raw[inp]
    out["llm_output"] = raw[columns["llm_output"]]
    hl = columns.get("human_label")
    out["human_label"] = raw[hl] if hl else None
    cn = columns["call_name"]
    out["call_name"] = cn["literal"] if isinstance(cn, dict) and "literal" in cn else raw[cn]
    for k in OPTIONAL:
        spec = columns.get(k)
        if spec is not None:
            out[k] = spec["literal"] if isinstance(spec, dict) and "literal" in spec else raw[spec]
        elif k in raw.columns and k not in needed:
            out[k] = raw[k]
        else:
            out[k] = None
    used = set(needed)
    extra_cols = [c for c in raw.columns if c not in used and c not in OPTIONAL]
    extras = raw[extra_cols].to_dict("records") if extra_cols else [{} for _ in range(len(raw))]
    out["extra"] = pd.Series(extras, index=raw.index, dtype=object)
    out = out.astype({"llm_output": "object"})
    return out.reset_index(drop=True)


class Dataset:
    """Rows in canonical form plus the mapping they came from."""

    def __init__(
        self,
        df: pd.DataFrame,
        schema_mapping: dict[str, Any] | None = None,
        input_template: str | None = None,
        source: str = "memory",
    ) -> None:
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            raise SchemaError(f"dataframe is not canonical; missing {missing}")
        self._df = df.reset_index(drop=True)
        self.schema_mapping = schema_mapping or {}
        self.input_template = input_template
        self.source = source

    @property
    def rows(self) -> int:
        return len(self._df)

    @property
    def calls(self) -> list[str]:
        return sorted(str(c) for c in self._df["call_name"].dropna().unique())

    def sample(self, n: int = 5) -> pd.DataFrame:
        return self._df.head(n)

    def to_pandas(self, call: str | None = None) -> pd.DataFrame:
        if call is None:
            return self._df.copy()
        return self._df[self._df["call_name"] == call].reset_index(drop=True)

    def for_call(self, call: str) -> Dataset:
        sub = self.to_pandas(call)
        if sub.empty:
            raise SchemaError(f"no rows for call {call!r}", f"calls in dataset: {self.calls}")
        return Dataset(sub, self.schema_mapping, self.input_template, self.source)

    def texts(self, call: str | None = None) -> list[Any]:
        """Model inputs: rendered text for text/multi_text, dicts for tabular."""
        df = self.to_pandas(call)
        out: list[Any] = []
        for v in df["input"]:
            if isinstance(v, dict) and v and all(_is_num(x) for x in v.values()):
                out.append(v)
            else:
                out.append(render_input(v, self.input_template))
        return out

    def label_counts(self, call: str | None = None) -> Counter[str]:
        labels, _ = resolve_labels(self.to_pandas(call))
        return Counter(labels)

    def __repr__(self) -> str:
        return f"Dataset(rows={self.rows}, calls={self.calls})"


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


_RE_WS = re.compile(r"\s+")


def clean_text(s: str) -> str:
    return _RE_WS.sub(" ", s).strip()
