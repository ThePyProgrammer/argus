"""DET-MODELS-07 — Offline boot gate (Plan 05-12 activation).

Marked slow_boxer — requires the full model tree pre-fetched:
  * ``models/rtdetrv2/<SHA>/model.onnx`` (Plan 05-11 + D-06 ONNX export)
  * ``subprocess_venvs/boxer/.ready`` (Plan 05-06 setup script)
Skipped by default via pytest.ini addopts ``-m "not slow_boxer and not network"``.
Run explicitly via ``pytest -m slow_boxer`` (nightly CI).

Test approach (SC#4 — coordinator boots under HF_HUB_OFFLINE=1):
  Subprocess-spawn a short Python probe under HF_HUB_OFFLINE=1 +
  HF_HUB_DISABLE_TELEMETRY=1 + HF_HOME=<empty tmpdir> +
  TRANSFORMERS_OFFLINE=1. The probe imports ``src.perception.backends``
  (side-effect registration of all three detectors) and enumerates
  ``DetectorRegistry.list_backends()``. Assert YOLOv11, RT-DETRv2, and
  BoxeR ALL report ``available=True`` — i.e. none of them secretly
  reach the HF hub during module import or the available() probe.

  ``HF_HUB_OFFLINE=1`` is the gate; the HF + transformers libraries
  honor it by raising instead of silently downloading. We do NOT
  physically unplug the network — the env gate is sufficient and keeps
  the test reproducible without sudo / firewall manipulation.

This catches regressions like:
  * ``rtdetrv2_backend.py`` adding a module-scope HF snapshot_download.
  * ``boxer_backend.py`` opening a network socket during ``available()``.
  * ``onnxruntime`` downloading EP plugins at import time (it doesn't,
    but if a future upgrade changes that, this test fires).
  * ``transformers`` tokenizer loaders hitting the hub for config JSON.

Subprocess-isolation is deliberate: setting HF_HUB_OFFLINE in the
parent process only would leak across OTHER tests and bleed into
subsequent pytest sessions' HF cache state. Spawning a fresh Python
interpreter per probe keeps the gate scoped to the SC#4 verification.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ``tests/integration/test_offline_boot.py`` lives two dirs below repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.slow_boxer
def test_all_backends_boot_with_hf_hub_offline() -> None:
    """SC#4 — all 3 backends enumerable + available under HF_HUB_OFFLINE=1."""
    # Preconditions — the `make download-models` step must have been run
    # ahead of this test. Skip with actionable messages if artifacts
    # aren't on disk; the marker itself gates most CI lanes, this is
    # the second gate for when the marker IS selected but the nightly
    # provisioning hasn't run.
    onnx_root = REPO_ROOT / "models" / "rtdetrv2"
    boxer_ready = REPO_ROOT / "subprocess_venvs" / "boxer" / ".ready"

    if not onnx_root.exists() or not any(
        onnx_root.glob("*/model.onnx")
    ):
        pytest.skip(
            f"{onnx_root}/<SHA>/model.onnx missing — "
            f"run `make download-models-rtdetrv2` first."
        )
    if not boxer_ready.exists():
        pytest.skip(
            f"{boxer_ready} missing — run `make download-models-boxer` first."
        )

    with tempfile.TemporaryDirectory() as empty_hf_cache:
        env = os.environ.copy()
        # The offline gate. HF libraries honor this by raising
        # LocalEntryNotFoundError instead of reaching out to the hub.
        env["HF_HUB_OFFLINE"] = "1"
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        # Empty HF_HOME ensures no previously-cached snapshot can mask a
        # backend that would otherwise try to download — the only files
        # visible to the probe are the ones we pre-staged in models/.
        env["HF_HOME"] = str(empty_hf_cache)
        env["TRANSFORMERS_OFFLINE"] = "1"

        probe_script = (
            "import json, sys\n"
            "import src.perception.backends  # side-effect registration\n"
            "from src.perception.registry import DetectorRegistry\n"
            "entries = DetectorRegistry.list_backends()\n"
            "out = {e['name']: {'available': e['available'], "
            "'reason': e.get('reason')} for e in entries}\n"
            "sys.stdout.write(json.dumps(out))\n"
        )

        result = subprocess.run(
            [sys.executable, "-c", probe_script],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"offline probe failed (exit={result.returncode}). "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # Parse the last line of stdout as JSON — import-time logging on
        # some of the dependency chain writes to stdout first.
        last_line = result.stdout.strip().splitlines()[-1]
        entries = json.loads(last_line)

        for name in ("yolov11", "rtdetrv2", "boxer"):
            assert name in entries, (
                f"{name} missing from DetectorRegistry enumeration; "
                f"got {list(entries.keys())}"
            )
            assert entries[name]["available"], (
                f"{name} not available under HF_HUB_OFFLINE=1: "
                f"reason={entries[name]['reason']!r} — a backend silently "
                f"reached out to the HF hub during import or available() probe."
            )
