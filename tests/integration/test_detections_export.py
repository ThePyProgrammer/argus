"""Skip-stub for DET-METRICS-04: /api/detections/export JSONL round-trip.

Replaced in full by 06-09-PLAN.md (Wave 2). Implementation spawns a
coordinator for 30 frames against scene_office1.xml, hits the export
endpoint, and round-trips every line through `OrientedBox3D.from_wire`.
See CONTEXT.md D-14.
"""
import pytest
pytest.skip(
    "Wave 0 scaffold — export round-trip test lands in 06-09-PLAN.md",
    allow_module_level=True,
)
