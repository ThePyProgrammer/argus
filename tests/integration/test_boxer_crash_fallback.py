"""DET-MODELS-06 — End-to-end kill -9 -> fallback within 5s (Wave 0 skeleton, Plan 05-04).

Plan 05-12 (Wave 3) fills in; marked `slow_boxer` because it requires the real
BoxeR subprocess to be killable.
"""
from __future__ import annotations

import pytest


@pytest.mark.slow_boxer
def test_kill_nine_triggers_fallback_within_5s() -> None:
    """SC#3 — os.kill(boxer_pid, SIGKILL); assert crash_fallback WS arrives + active backend switches within 5s."""
    pytest.skip("Plan 05-12 (Wave 3) fills in: spawns coordinator + BoxeR, SIGKILLs worker, measures elapsed.")
