"""Plan 07-10 target — DET-PIPELINE-04 SC#3 end-to-end.

Load perception_rgbd preset via POST /api/pipeline/apply, wait for restart
completion, assert:
  - At least one detection envelope flows through the WebSocket within 5 s.
  - Envelope carries non-empty OBBs (validates detector→lifter→tracker→viz chain).

Marked slow; optional MuJoCo scene boot (may be xfail when MuJoCo unavailable).
"""
import pytest

pytest.skip(
    "Wave 0 stub — DET-PIPELINE-04 SC#3 end-to-end (implemented in Plan 07-10)",
    allow_module_level=True,
)


@pytest.mark.slow_boxer  # reuse existing slow marker; phase 7 adds no new markers
def test_perception_rgbd_preset_end_to_end_emits_detections() -> None:
    # TODO Plan 07-10: this test is optional — mark xfail if MuJoCo scene boot
    # fails in CI. Primary SC#3 coverage comes from the contract test + manual UI verify.
    assert False, "implemented in Plan 07-10"
