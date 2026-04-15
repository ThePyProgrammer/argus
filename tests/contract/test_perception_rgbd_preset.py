"""Plan 07-10 target — DET-PIPELINE-04 (perception_rgbd preset integrity).

Loads data/presets/builtin/perception_rgbd.json, runs through PipelineBuilder.build,
asserts no ValueError + resulting PipelineConfig has:
  - detector_name == "yolov11"
  - lifter_name == "point_cluster"
  - tracker_name == "none"
  - backend_name == "icp"
  - merger_name == "icp_union"
"""
import pytest

pytest.skip(
    "Wave 0 stub — DET-PIPELINE-04 preset contract (implemented in Plan 07-10)",
    allow_module_level=True,
)


def test_perception_rgbd_preset_builds_cleanly() -> None:
    # TODO Plan 07-10: json.loads the preset file, call PipelineBuilder().build,
    # assert all 5 fields above.
    assert False, "implemented in Plan 07-10"


def test_perception_rgbd_preset_has_expected_topology() -> None:
    # TODO Plan 07-10: assert preset contains exactly 7 nodes with ids
    # sensor_1, slam_1, merger_1, detector_1, detection3d_1, tracker_1, viz_1
    # and 11 edges linking them per CONTEXT D-15.
    assert False, "implemented in Plan 07-10"


def test_perception_rgbd_preset_positions_match_ui_spec() -> None:
    # TODO Plan 07-10: assert detector_1.position == {"x": 350, "y": 300}, etc.
    # per CONTEXT D-16 exact coordinates.
    assert False, "implemented in Plan 07-10"
