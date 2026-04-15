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
    """Snapshot + optimum ONNX export + sha256 verify + rollback on failure.

    Order of operations:
      1. Short-circuit if models/rtdetrv2/<SHA>/model.onnx exists AND sha256
         matches EXPECTED_SHA256 (idempotent re-run).
      2. mkdir -p models/rtdetrv2/<SHA>/
      3. snapshot_download(PekingU/rtdetr_v2_r18vd, revision=SHA) →
         models/rtdetrv2/<SHA>/pt/
      4. optimum.exporters.onnx.main_export(pt/, 320x320) →
         models/rtdetrv2/<SHA>/model.onnx  (D-08 static 320x320)
      5. sha256 verify model.onnx (record on first run — stdout "[NEW SHA]"
         line for the developer to commit; enforce-on-subsequent).
      6. On ANY exception between steps 2-5, shutil.rmtree(
         models/rtdetrv2/<SHA>/) and re-raise (T-5-03 rollback mitigation).

    The EXPECTED_SHA256 manifest starts empty; after the first successful
    download the developer copies the printed "[NEW SHA]" line into this
    file's EXPECTED_SHA256 dict and commits it. CI then enforces the pin.
    """
    target = RT_DETRV2_MODEL_DIR
    pt_dir = target / "pt"
    onnx_path = target / "model.onnx"

    # Short-circuit if the artifact already exists AND sha256 matches — idempotent re-run
    if onnx_path.exists():
        try:
            verify_or_record(onnx_path)
            print(f"[download_rtdetrv2] {onnx_path} already present and verified; skipping.")
            return
        except RuntimeError as exc:
            print(f"[download_rtdetrv2] existing artifact failed sha256 check: {exc}")
            print(f"[download_rtdetrv2] removing {target} and re-downloading.")
            shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)

    try:
        # Step 2-3: HuggingFace snapshot at pinned revision.
        from huggingface_hub import snapshot_download  # noqa: PLC0415
        print(f"[download_rtdetrv2] snapshot_download {RT_DETRV2_REPO}@{RT_DETRV2_SHA} -> {pt_dir}")
        snapshot_download(
            repo_id=RT_DETRV2_REPO,
            revision=RT_DETRV2_SHA,
            local_dir=str(pt_dir),
            local_dir_use_symlinks=False,
        )

        # Step 4: ONNX export via torch.onnx.export (static 1x3x320x320 per D-08).
        #
        # Why not optimum: optimum 2.x split its exporters into the `optimum-onnx`
        # package, which hard-pins `transformers<5` (incompatible with this
        # project's `transformers>=5.3.0` requirement). Direct torch.onnx.export
        # works with any transformers version and has no extra deps — the model
        # is already a plain `torch.nn.Module` after `from_pretrained`.
        import torch  # noqa: PLC0415
        from transformers import AutoModelForObjectDetection  # noqa: PLC0415

        print(f"[download_rtdetrv2] torch.onnx.export -> {onnx_path}")
        model = AutoModelForObjectDetection.from_pretrained(str(pt_dir))
        model.eval()

        class _ExportWrapper(torch.nn.Module):
            """Convert HF ModelOutput dict → tuple so ONNX emits named outputs."""
            def __init__(self, m: torch.nn.Module) -> None:
                super().__init__()
                self.m = m

            def forward(self, pixel_values: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
                out = self.m(pixel_values=pixel_values)
                return out.logits, out.pred_boxes

        wrapped = _ExportWrapper(model)
        dummy = torch.zeros(1, 3, 320, 320, dtype=torch.float32)

        with torch.inference_mode():
            torch.onnx.export(
                wrapped,
                dummy,
                str(onnx_path),
                input_names=["pixel_values"],
                output_names=["logits", "pred_boxes"],
                opset_version=17,
                do_constant_folding=True,
                dynamo=False,  # legacy TorchScript path — avoids onnxscript dep
            )

        # Step 5: sha256 verify (or record on first run).
        if not onnx_path.exists():
            raise RuntimeError(
                f"optimum export completed but {onnx_path} not found — "
                f"check optimum's output_dir handling."
            )
        verify_or_record(onnx_path)
        print(f"[download_rtdetrv2] done. artifact at {onnx_path}")

    except Exception as exc:  # noqa: BLE001 — T-5-03 rollback must catch EVERYTHING
        # Rollback: remove the entire pinned-SHA directory so the next
        # invocation starts clean. Do NOT leave a half-populated dir.
        print(f"[download_rtdetrv2] FAILED: {exc}. Rolling back {target}.")
        if target.exists():
            shutil.rmtree(target, ignore_errors=False)
        raise


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
