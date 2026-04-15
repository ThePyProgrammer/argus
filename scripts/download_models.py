#!/usr/bin/env python3
"""Phase 5 (D-13): pre-fetch pinned checkpoints to ./models/ for offline/CI.

Skeleton (Wave 0 Plan 03). Wave 3 Plan 11 fills in the real download_rtdetrv2()
body (snapshot_download + optimum.exporters.onnx.main_export + sha256 verify +
rollback). This skeleton exists so:
  * `make download-models` + `make download-models-rtdetrv2` resolve without error
  * Wave 2 RT-DETRv2 backend can reference RT_DETRV2_SHA + RT_DETRV2_REPO + RT_DETRV2_MODEL_DIR
    (these constants are imported FROM the backend module, not from this script —
    this script simply re-exports them for tooling convenience)
  * Wave 0 validation test can assert `python scripts/download_models.py --help` works

Usage:
    uv run python scripts/download_models.py --backend rtdetrv2
    uv run python scripts/download_models.py --backend boxer
    uv run python scripts/download_models.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

# Verified SHAs per Phase 5 RESEARCH.md D-12 (HF + GitHub API calls 2026-04-15).
# Duplicated from the backend modules to keep this script importable even when
# the `perception` extra is not installed (download is a prerequisite for
# installing the deps that consume the checkpoints — chicken/egg avoided).
RT_DETRV2_SHA: str = "5650961749fa93567c0d46fc7f43ea4f9e914107"
RT_DETRV2_REPO: str = "PekingU/rtdetr_v2_r18vd"
RT_DETRV2_MODEL_DIR: Path = Path("models") / "rtdetrv2" / RT_DETRV2_SHA

BOXER_SHA: str = "df474128a76ba42b05bc81feca7ac1a53fab41af"
BOXER_REPO_URL: str = "https://github.com/facebookresearch/boxer"
BOXER_MODEL_DIR: Path = Path("models") / "boxer" / BOXER_SHA

# sha256 manifest — Plan 11 populates after first successful download and
# commits these literals so CI can re-verify. Empty at skeleton stage.
EXPECTED_SHA256: dict[str, str] = {}


def sha256_of(path: Path) -> str:
    """Compute the sha256 hex digest of a file using 1 MiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_or_record(path: Path) -> None:
    """Record-on-first-run or verify-on-CI sha256 for a downloaded artifact.

    Plan 11 will expand EXPECTED_SHA256 with real hashes once the first
    successful download committed them. At skeleton stage this function is
    safe to call — it just records hashes to stdout.
    """
    rel = str(path)
    actual = sha256_of(path)
    expected = EXPECTED_SHA256.get(rel)
    if expected is None:
        print(f"[NEW SHA] {rel}: {actual}  # add to EXPECTED_SHA256 to lock")
        return
    if expected != actual:
        raise RuntimeError(
            f"sha256 mismatch for {rel}\n  expected {expected}\n  actual   {actual}"
        )


def download_rtdetrv2() -> None:
    """Download RT-DETRv2 snapshot + export to ONNX. Plan 11 fills this in.

    Skeleton raises NotImplementedError with the tracking reference so CI
    and humans both see a clear "not yet implemented" signal instead of a
    silent pass that would mask a broken download pipeline.
    """
    raise NotImplementedError(
        "Plan 05-11 (Wave 3) fills in this function body. See "
        ".planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-RESEARCH.md "
        "'Makefile + download_models.py Contract (D-13)' for the full impl."
    )


def download_boxer() -> None:
    """Delegate to setup_boxer_subprocess.sh — BoxeR fetch needs subprocess venv.

    This wrapper exists so `--backend boxer` and `--all` both resolve. Plan 06
    creates the shell script; Plan 11 may extend this to add argus-side post-
    processing (e.g., post-copy BoxeR ckpts from repo-local default location
    into models/boxer/<sha>/ if the upstream script doesn't honor our layout).
    """
    script = Path(__file__).parent / "setup_boxer_subprocess.sh"
    if not script.exists():
        raise FileNotFoundError(
            f"Expected {script}. Phase 5 Plan 06 creates this file — run that plan first."
        )
    subprocess.run(["bash", str(script)], check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Pre-fetch pinned detector checkpoints to ./models/ (Phase 5 D-13).",
    )
    ap.add_argument(
        "--backend",
        choices=["rtdetrv2", "boxer"],
        help="Which backend to fetch (omit + pass --all to fetch everything).",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Fetch every registered backend's checkpoints.",
    )
    args = ap.parse_args(argv)
    if not args.all and args.backend is None:
        ap.error("specify --backend {rtdetrv2,boxer} or --all")
    if args.all or args.backend == "rtdetrv2":
        download_rtdetrv2()
    if args.all or args.backend == "boxer":
        download_boxer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
