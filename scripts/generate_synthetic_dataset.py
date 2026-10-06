"""Generate the synthetic demo dataset (6,000 rows, seed 42) and the 300-row test fixture.

uv run python scripts/generate_synthetic_dataset.py
"""

from __future__ import annotations

from pathlib import Path

from pecca.data.synthetic import assert_clean, write_dataset

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out = ROOT / "data" / "pecca-demo-support-emails"
    df = write_dataset(out, n=6000, seed=42)
    assert len(df) == 6000, len(df)
    assert df["rfi"].nunique() == 60 and df["domain"].nunique() == 12
    assert_clean(df)  # no real bank names
    wc = df["email_body"].str.split().str.len()
    assert wc.min() >= 40 and wc.max() <= 120, (wc.min(), wc.max())
    mini = df.sample(300, random_state=42).sort_values("timestamp")
    fixtures = ROOT / "tests" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    mini.to_csv(fixtures / "mini.csv", index=False)
    print(f"wrote {len(df):,} rows -> {out}")
    print(f"wrote {len(mini)} rows -> {fixtures / 'mini.csv'}")
    print("languages:", df["language"].value_counts(normalize=True).round(3).to_dict())
    print(
        f"LLM accuracy: domain {(df.llm_domain == df.domain).mean():.3f}, rfi {(df.llm_rfi == df.rfi).mean():.3f}"
    )
    print(
        f"rows per RFI class: min {df['rfi'].value_counts().min()}, max {df['rfi'].value_counts().max()}"
    )


if __name__ == "__main__":
    main()
