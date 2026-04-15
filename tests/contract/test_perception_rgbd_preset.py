"""Plan 07-10 — DET-PIPELINE-04 perception_rgbd preset contract lockdown."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.coordination.merge_registry import MergeRegistry
from src.coordination.pipeline_builder import PipelineBuilder
from src.slam.registry import SLAMRegistry


PRESET_PATH = Path(__file__).parent.parent.parent / "data" / "presets" / "builtin" / "perception_rgbd.json"


@pytest.fixture(autouse=True)
def _populate_registries():
    """Register minimal SLAM + merger entries (without importing the
    heavy-dependency backends like open3d). The preset validator only checks
    registry membership — class paths are never resolved in `build`.
    Perception/lifter/tracker registries are import-safe and registered via
    their package __init__ side effects.
    """
    SLAMRegistry._clear()
    MergeRegistry._clear()
    SLAMRegistry.register(
        "icp", "ICP Odometry", "src.slam.backends.icp_backend.ICPBackend"
    )
    MergeRegistry.register(
        "icp_union", "ICP Union",
        "src.coordination.merge_strategies.icp_union.ICPUnionStrategy",
    )
    # Force re-import of registry-populating packages so @decorators re-run
    # after any prior test's _clear. Python caches modules by default — a
    # second `import` is a no-op, so we drop cached entries first.
    import sys
    for _prefix in ("src.perception.backends", "src.perception.lifters", "src.tracking.trackers"):
        for _key in list(sys.modules):
            if _key == _prefix or _key.startswith(_prefix + "."):
                del sys.modules[_key]
    import src.perception.backends  # noqa: F401
    import src.perception.lifters   # noqa: F401
    import src.tracking.trackers    # noqa: F401
    yield
    SLAMRegistry._clear()
    MergeRegistry._clear()


def test_perception_rgbd_preset_builds_cleanly() -> None:
    preset = json.loads(PRESET_PATH.read_text())
    assert preset["name"] == "Perception + RGBD"
    config = PipelineBuilder().build({"nodes": preset["nodes"], "edges": preset["edges"]})
    assert config.backend_name == "icp"
    assert config.merger_name == "icp_union"
    assert config.detector_name == "yolov11"
    assert config.lifter_name == "point_cluster"
    assert config.tracker_name == "none"


def test_perception_rgbd_preset_has_expected_topology() -> None:
    preset = json.loads(PRESET_PATH.read_text())
    node_ids = sorted(n["id"] for n in preset["nodes"])
    assert node_ids == sorted([
        "sensor_1", "slam_1", "merger_1",
        "detector_1", "detection3d_1", "tracker_1",
        "viz_1",
    ])
    assert len(preset["edges"]) == 11

    # Every edge's endpoints resolve to a node id in the preset.
    ids = set(node_ids)
    for edge in preset["edges"]:
        assert edge["source"] in ids
        assert edge["target"] in ids
        assert "sourceHandle" in edge
        assert "targetHandle" in edge


def test_perception_rgbd_preset_positions_match_ui_spec() -> None:
    preset = json.loads(PRESET_PATH.read_text())
    by_id = {n["id"]: n for n in preset["nodes"]}
    assert by_id["sensor_1"]["position"] == {"x": 50, "y": 225}
    assert by_id["slam_1"]["position"] == {"x": 350, "y": 100}
    assert by_id["merger_1"]["position"] == {"x": 650, "y": 100}
    assert by_id["detector_1"]["position"] == {"x": 350, "y": 300}
    assert by_id["detection3d_1"]["position"] == {"x": 650, "y": 300}
    assert by_id["tracker_1"]["position"] == {"x": 950, "y": 300}
    assert by_id["viz_1"]["position"] == {"x": 1150, "y": 200}
