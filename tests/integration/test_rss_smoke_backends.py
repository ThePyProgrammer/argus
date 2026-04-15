"""Skip-stub for DET-METRICS-05: parametrized RSS smoke across backends.

Replaced in full by 06-13-PLAN.md (Wave 5). Implementation uses
@pytest.mark.parametrize over ["yolov11", "rtdetrv2",
pytest.param("boxer", marks=pytest.mark.slow_boxer)] per CONTEXT
D-15, with honest-skip on missing model/venv artifacts. OWLv2 is
intentionally absent — superseded by Phase 5 D-10 (see RESEARCH F4).
"""
import pytest
pytest.skip(
    "Wave 0 scaffold — parametrized RSS smoke lands in 06-13-PLAN.md",
    allow_module_level=True,
)
