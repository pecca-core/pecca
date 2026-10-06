"""Upload the demo dataset and model to the Hugging Face ``pecca-core`` org. Idempotent.

Requires ``hf auth login`` (write token) done by you. Nothing is uploaded with --dry-run.

    uv run python scripts/upload_to_hf.py --dry-run
    uv run python scripts/upload_to_hf.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ("dataset", "pecca-core/demo-support-emails", ROOT / "data" / "pecca-demo-support-emails"),
    ("model", "pecca-core/demo-router-e5-logreg", ROOT / "models" / "pecca-demo-router"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for kind, repo, folder in TARGETS:
        if not folder.is_dir():
            raise SystemExit(f"missing {folder}; run the generate/train scripts first")
        files = sorted(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())
        print(f"{kind} {repo}: {len(files)} files from {folder}")
        for f in files:
            print("   ", f)
        if a.dry_run:
            continue
        from huggingface_hub import HfApi

        api = HfApi()
        api.create_repo(repo, repo_type=kind, exist_ok=True)
        card = folder / ("README.md" if kind == "dataset" else "model_card.md")
        api.upload_folder(
            repo_id=repo,
            repo_type=kind,
            folder_path=str(folder),
            commit_message="Upload from scripts/upload_to_hf.py",
        )
        if kind == "model":  # the Hub reads README.md as the card
            api.upload_file(
                path_or_fileobj=str(card), path_in_repo="README.md", repo_id=repo, repo_type=kind
            )
        print(f"uploaded https://huggingface.co/{'datasets/' if kind == 'dataset' else ''}{repo}")


if __name__ == "__main__":
    main()
