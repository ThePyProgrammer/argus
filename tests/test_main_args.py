"""Skip-stub for DET-METRICS-03: --labeled-eval-set CLI reservation.

Replaced in full by 06-10-PLAN.md (Wave 3). Implementation asserts
`argus --labeled-eval-set /tmp/foo` raises NotImplementedError with
the exact CONTEXT D-10 message.
"""
import pytest
pytest.skip(
    "Wave 0 scaffold — CLI reservation test lands in 06-10-PLAN.md",
    allow_module_level=True,
)
