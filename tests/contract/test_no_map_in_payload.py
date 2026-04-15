"""Skip-stub for DET-METRICS-03 (runtime guard): `mAP`/`map_50`/`map_75`
keys absent from WebStreamingViz._update_stats payload.

Replaced in full by 06-08-PLAN.md (Wave 2). Implementation constructs
a stats payload via a real WebStreamingViz instance and asserts
forbidden keys are not present at any nesting depth.
"""
import pytest
pytest.skip(
    "Wave 0 scaffold — payload runtime guard test lands in 06-08-PLAN.md",
    allow_module_level=True,
)
