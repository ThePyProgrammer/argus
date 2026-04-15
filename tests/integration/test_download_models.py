"""DET-MODELS-07 — Download pipeline integration tests (Plan 05-11 activation).

All tests ``@pytest.mark.network`` — skipped by default per pyproject marker
config. Run explicitly:

    uv run pytest tests/integration/test_download_models.py -m network -x

These tests exercise the real download pipeline (HuggingFace Hub + GitHub
clones, optimum ONNX export, sha256 manifest verification, T-5-03 rollback).
They are NOT selected by the default `pytest` invocation; CI runs a separate
nightly network-marked job.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.network
def test_download_rtdetrv2(tmp_path) -> None:
    """snapshot_download + optimum export produce models/rtdetrv2/<SHA>/model.onnx."""
    from scripts import download_models
    # Redirect RT_DETRV2_MODEL_DIR to tmp_path so we don't touch real models/ tree.
    fake_dir = tmp_path / "rtdetrv2" / download_models.RT_DETRV2_SHA
    with patch.object(download_models, "RT_DETRV2_MODEL_DIR", fake_dir):
        download_models.download_rtdetrv2()
    assert (fake_dir / "model.onnx").is_file()
    assert (fake_dir / "pt").is_dir()


@pytest.mark.network
def test_setup_boxer_idempotent(tmp_path) -> None:
    """D-01 — second run of setup_boxer_subprocess.sh short-circuits on .ready marker."""
    script = REPO_ROOT / "scripts" / "setup_boxer_subprocess.sh"
    # The script uses $REPO_ROOT internally; we can't easily redirect that, so
    # assert idempotency by pre-creating a .ready marker in the real location
    # and confirming the script exits 0 immediately without re-cloning.
    ready = REPO_ROOT / "subprocess_venvs" / "boxer" / ".ready"
    created_here = False
    if not ready.exists():
        ready.parent.mkdir(parents=True, exist_ok=True)
        ready.touch()
        created_here = True
    try:
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"setup script failed: {result.stderr}"
        assert (
            "skipping" in result.stdout.lower()
            or "ready exists" in result.stdout.lower()
            or "already" in result.stdout.lower()
        )
    finally:
        if created_here:
            shutil.rmtree(ready.parent, ignore_errors=True)


@pytest.mark.network
def test_sha256_manifest_verification(tmp_path) -> None:
    """T-5-03 — sha256 mismatch raises on subsequent invocations."""
    from scripts import download_models
    fake_file = tmp_path / "fake.onnx"
    fake_file.write_bytes(b"known content")
    expected_hash = download_models.sha256_of(fake_file)

    with patch.dict(download_models.EXPECTED_SHA256, {str(fake_file): expected_hash}):
        # Correct hash — no raise.
        download_models.verify_or_record(fake_file)

    wrong_hash = "0" * 64
    with patch.dict(download_models.EXPECTED_SHA256, {str(fake_file): wrong_hash}):
        with pytest.raises(RuntimeError, match="sha256 mismatch"):
            download_models.verify_or_record(fake_file)


@pytest.mark.network
def test_rollback_on_partial_failure(tmp_path, monkeypatch) -> None:
    """D-13 — exception in optimum export → shutil.rmtree cleanup."""
    from scripts import download_models
    fake_dir = tmp_path / "rtdetrv2" / download_models.RT_DETRV2_SHA
    monkeypatch.setattr(download_models, "RT_DETRV2_MODEL_DIR", fake_dir)

    # Inject a snapshot_download that succeeds (creates the dir) then optimum that fails.
    def fake_snapshot(**kwargs):
        pt_dir = Path(kwargs["local_dir"])
        pt_dir.mkdir(parents=True, exist_ok=True)
        (pt_dir / "config.json").write_text("{}")

    def fake_export(**kwargs):
        raise RuntimeError("simulated optimum failure")

    with patch("huggingface_hub.snapshot_download", fake_snapshot), \
         patch("optimum.exporters.onnx.main_export", fake_export):
        with pytest.raises(RuntimeError, match="simulated optimum failure"):
            download_models.download_rtdetrv2()

    # After failure, the target dir must be removed (rollback).
    assert not fake_dir.exists(), f"rollback failed — {fake_dir} still exists"
