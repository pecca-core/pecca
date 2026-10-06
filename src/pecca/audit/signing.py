"""sha256 manifest and optional GPG detached signature."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def hashes(
    directory: Path, exclude: tuple[str, ...] = ("manifest.sha256", "manifest.sha256.sig")
) -> list[tuple[str, str]]:
    return [
        (p.name, sha256_file(p))
        for p in sorted(directory.iterdir())
        if p.is_file() and p.name not in exclude
    ]


def write_manifest(directory: Path, gpg_key: str | None = None) -> bool:
    """Write ``manifest.sha256``; sign it with gpg if ``gpg_key`` is set. Returns True if gpg-signed."""
    lines = [f"{h}  {n}" for n, h in hashes(directory)]
    mf = directory / "manifest.sha256"
    mf.write_text("\n".join(lines) + "\n")
    if gpg_key:
        r = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--local-user",
                gpg_key,
                "--detach-sign",
                "--output",
                str(directory / "manifest.sha256.sig"),
                str(mf),
            ],
            capture_output=True,
            check=False,
        )
        return r.returncode == 0
    return False
