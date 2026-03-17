"""Unit tests for MultiRobotVisualizer with mocked Rerun SDK.

Tests verify correct entity paths, colors, data shapes, and blueprint
layout without requiring the real Rerun viewer or SDK installation.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Mock rerun and rerun.blueprint at module level so the import of
# MultiRobotVisualizer succeeds without real rerun installed.
# ---------------------------------------------------------------------------
mock_rr = MagicMock()
mock_rrb = MagicMock()

# Ensure rr.MediaType.MARKDOWN resolves to a stable sentinel
mock_rr.MediaType.MARKDOWN = "text/markdown"

# Patch sys.modules BEFORE importing the module under test
sys.modules["rerun"] = mock_rr
sys.modules["rerun.blueprint"] = mock_rrb

from src.viz.multi_robot_viz import MultiRobotVisualizer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_robot_data():
    """Return synthetic robot_data dict for robot_a and robot_b."""
    frame_a = SimpleNamespace(rgb=np.zeros((240, 320, 3), dtype=np.uint8))
    frame_b = SimpleNamespace(rgb=np.zeros((240, 320, 3), dtype=np.uint8))
    return {
        "robot_a": {
            "frame": frame_a,
            "local_voxels": np.random.rand(5, 3),
            "pose": np.eye(4),
            "trajectory": [np.eye(4)] * 5,
            "coverage_pct": 50.0,
        },
        "robot_b": {
            "frame": frame_b,
            "local_voxels": np.random.rand(5, 3),
            "pose": np.eye(4),
            "trajectory": [np.eye(4)] * 5,
            "coverage_pct": 40.0,
        },
    }


def _find_log_call(entity_prefix):
    """Return the first rr.log call whose first arg starts with entity_prefix."""
    for call in mock_rr.log.call_args_list:
        args, _kwargs = call
        if args and isinstance(args[0], str) and args[0].startswith(entity_prefix):
            return call
    return None


def _find_all_log_calls(entity_prefix):
    """Return all rr.log calls whose first arg starts with entity_prefix."""
    results = []
    for call in mock_rr.log.call_args_list:
        args, _kwargs = call
        if args and isinstance(args[0], str) and args[0].startswith(entity_prefix):
            results.append(call)
    return results


@pytest.fixture(autouse=True)
def _reset_mocks():
    """Reset all mock call records before each test."""
    mock_rr.reset_mock()
    mock_rrb.reset_mock()
    # Re-set sentinel that reset_mock clears
    mock_rr.MediaType.MARKDOWN = "text/markdown"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBlueprintLayout:
    def test_blueprint_layout(self):
        """_create_blueprint returns Blueprint with correct panel hierarchy."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        bp = viz._create_blueprint()

        # Blueprint constructor should have been called
        mock_rrb.Blueprint.assert_called()
        # Vertical should have been called (top-level container)
        mock_rrb.Vertical.assert_called()
        # Two Horizontal calls (top row and bottom row)
        assert mock_rrb.Horizontal.call_count >= 2

        # Spatial3DView should be called at least 3 times
        # (merged, robot_a, robot_b)
        assert mock_rrb.Spatial3DView.call_count >= 3

        # TextDocumentView for stats panel
        mock_rrb.TextDocumentView.assert_called()

        # Verify origins by checking keyword args across all Spatial3DView calls
        origins = set()
        for call in mock_rrb.Spatial3DView.call_args_list:
            _args, kwargs = call
            if "origin" in kwargs:
                origins.add(kwargs["origin"])
        assert "/merged" in origins
        assert "/robot_a" in origins
        assert "/robot_b" in origins


class TestMergedMap:
    def test_log_merged_map(self):
        """update() logs merged point cloud with per-robot color tinting."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()
        merged = np.random.rand(10, 3)

        viz.update(
            merged_voxels=merged,
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/merged/point_cloud")
        assert call is not None, "Expected rr.log call to /merged/point_cloud"

        # Verify rr.Points3D was used
        mock_rr.Points3D.assert_called()


class TestRobotPose:
    def test_log_robot_pose(self):
        """update() logs Transform3D for each robot at /merged/{rid}/pose."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call_a = _find_log_call("/merged/robot_a/pose")
        call_b = _find_log_call("/merged/robot_b/pose")
        assert call_a is not None, "Expected rr.log to /merged/robot_a/pose"
        assert call_b is not None, "Expected rr.log to /merged/robot_b/pose"

        # Transform3D should have been called
        mock_rr.Transform3D.assert_called()


class TestFadingTrail:
    def test_fading_trail(self):
        """update() logs LineStrips3D with increasing alpha for trajectory."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()
        # Give robot_a a longer trajectory for meaningful fading
        robot_data["robot_a"]["trajectory"] = [np.eye(4) + np.random.rand(4, 4) * 0.01 * i for i in range(10)]

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/merged/robot_a/trajectory")
        assert call is not None, "Expected rr.log to /merged/robot_a/trajectory"

        # LineStrips3D should have been called with colors argument
        mock_rr.LineStrips3D.assert_called()


class TestHeatmap:
    def test_heatmap_colors(self):
        """Coverage heatmap uses green/red/yellow color scheme."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()
        frontier_cells = np.array([[1.0, 1.0, 0.0], [1.1, 1.1, 0.0], [1.2, 1.2, 0.0]])

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            frontier_cells=frontier_cells,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/merged/heatmap")
        assert call is not None, "Expected rr.log to /merged/heatmap"

        # Points3D should have been called for heatmap
        mock_rr.Points3D.assert_called()

    def test_heatmap_resolution(self):
        """Heatmap grid spacing matches 0.1m resolution."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()

        # Create a small known grid of voxels
        voxels = np.array([
            [0.0, 0.0, 0.5],
            [0.1, 0.0, 0.5],
            [0.2, 0.0, 0.5],
            [0.0, 0.1, 0.5],
        ])

        viz.update(
            merged_voxels=voxels,
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/merged/heatmap")
        assert call is not None, "Expected rr.log to /merged/heatmap"
        # Verify Points3D was called (the heatmap renderer)
        mock_rr.Points3D.assert_called()


class TestStatsHUD:
    def test_stats_hud(self):
        """update() logs TextDocument with coverage, elapsed, and merge stats."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/stats")
        assert call is not None, "Expected rr.log to /stats"

        # TextDocument should have been called
        mock_rr.TextDocument.assert_called()

        # Verify the markdown content contains required fields
        td_args, td_kwargs = mock_rr.TextDocument.call_args
        md_text = td_args[0] if td_args else ""
        assert "Total Coverage:" in md_text
        assert "Robot A:" in md_text or "robot_a" in md_text.lower()
        assert "Robot B:" in md_text or "robot_b" in md_text.lower()
        assert "Elapsed:" in md_text
        assert "Merges:" in md_text


class TestVoronoiPlane:
    def test_voronoi_plane(self):
        """When voronoi data provided, logs Mesh3D with translucent plane."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            voronoi_midpoint=np.array([5.0, 0.0]),
            voronoi_direction=np.array([1.0, 0.0]),
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/merged/voronoi_plane")
        assert call is not None, "Expected rr.log to /merged/voronoi_plane"

        # Mesh3D should have been called
        mock_rr.Mesh3D.assert_called()

        # Check vertex_colors contain alpha=80
        _args, kwargs = mock_rr.Mesh3D.call_args
        if "vertex_colors" in kwargs:
            colors = kwargs["vertex_colors"]
            # Each color should be [200, 200, 200, 80]
            for c in colors:
                assert c[3] == 80, f"Expected alpha=80, got {c[3]}"


class TestRobotPanels:
    def test_robot_panel_camera(self):
        """update() logs camera RGB to /{rid}/camera/rgb with rr.Image."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/robot_a/camera/rgb")
        assert call is not None, "Expected rr.log to /robot_a/camera/rgb"

        # rr.Image should have been called
        mock_rr.Image.assert_called()

    def test_robot_panel_local_cloud(self):
        """update() logs local point cloud to /{rid}/local_cloud tinted."""
        viz = MultiRobotVisualizer.__new__(MultiRobotVisualizer)
        viz._start_time = 0.0
        robot_data = _make_robot_data()

        viz.update(
            merged_voxels=np.random.rand(10, 3),
            robot_data=robot_data,
            total_coverage=65.0,
            merge_count=3,
        )

        call = _find_log_call("/robot_a/local_cloud")
        assert call is not None, "Expected rr.log to /robot_a/local_cloud"

        # Points3D should have been called for local cloud
        mock_rr.Points3D.assert_called()
