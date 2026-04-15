"""DET-MODELS-07 — Download pipeline integration tests (Wave 0 skeleton, Plan 05-04).

Plan 05-11 (Wave 3) fills in the real assertions. Tests marked `network` because
they hit HuggingFace Hub + GitHub; skipped by default per pyproject marker registration.
"""
from __future__ import annotations

import pytest


@pytest.mark.network
def test_download_rtdetrv2(tmp_path) -> None:
    """snapshot_download + optimum ONNX export produce models/rtdetrv2/<SHA>/model.onnx (Plan 05-11)."""
    pytest.skip("Plan 05-11 (Wave 3) fills in: exercises scripts/download_models.py --backend rtdetrv2.")


@pytest.mark.network
def test_setup_boxer_idempotent(tmp_path) -> None:
    """D-01 — .ready marker short-circuits on second run (Plan 05-06 ships script, Plan 05-11 tests)."""
    pytest.skip("Plan 05-11 (Wave 3) fills in: run setup_boxer_subprocess.sh twice, second run is no-op.")


@pytest.mark.network
def test_sha256_manifest_verification(tmp_path) -> None:
    """T-5-03 mitigation — sha256 of downloaded model.onnx matches EXPECTED_SHA256."""
    pytest.skip("Plan 05-11 (Wave 3) fills in: after first download, EXPECTED_SHA256 lookup succeeds.")


@pytest.mark.network
def test_rollback_on_partial_failure(tmp_path, monkeypatch) -> None:
    """D-13 — partial download + exception leaves no orphan models/<backend>/<sha>/ dir."""
    pytest.skip("Plan 05-11 (Wave 3) fills in: inject optimum export exception; target dir removed.")
