"""DET-MODELS-07 — Offline boot gate (Wave 0 skeleton, Plan 05-04).

Plan 05-11 (Wave 3) fills in; marked `slow_boxer` because it spawns the real
BoxeR subprocess.
"""
from __future__ import annotations

import pytest


@pytest.mark.slow_boxer
def test_all_backends_boot_with_hf_hub_offline() -> None:
    """SC#4 — after `make download-models`, all 3 backends boot with HF_HUB_OFFLINE=1."""
    pytest.skip("Plan 05-11 (Wave 3) fills in: spawns coordinator with HF_HUB_OFFLINE=1 + empty HF_HOME.")
