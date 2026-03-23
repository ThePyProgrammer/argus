"""Tests for mesh reconstruction with Open3D Poisson surface reconstruction.

Covers: happy path reconstruction, minimum points guard, availability check,
and graceful degradation when Open3D is not installed.
"""

import importlib
import sys

import numpy as np
import pytest

# Detect Open3D availability for conditional test skipping
try:
    import open3d  # noqa: F401

    _HAS_OPEN3D = True
except ImportError:
    _HAS_OPEN3D = False

import src.metrics.mesh_reconstruction as mesh_mod


@pytest.mark.skipif(not _HAS_OPEN3D, reason="Open3D not installed")
class TestReconstructMeshHappyPath:
    """Tests that require Open3D to be importable."""

    def test_reconstruct_mesh_returns_vertices_and_faces(self):
        """Test 1: reconstruct_mesh with 100 points on a sphere returns (N,3) vertices and (M,3) faces."""
        rng = np.random.default_rng(42)
        theta = rng.uniform(0, 2 * np.pi, 100)
        phi = rng.uniform(0, np.pi, 100)
        points = np.column_stack(
            [np.sin(phi) * np.cos(theta), np.sin(phi) * np.sin(theta), np.cos(phi)]
        )

        vertices, faces, vertex_colors = mesh_mod.reconstruct_mesh(points)

        assert isinstance(vertices, np.ndarray)
        assert isinstance(faces, np.ndarray)
        assert vertices.ndim == 2
        assert vertices.shape[1] == 3
        assert faces.ndim == 2
        assert faces.shape[1] == 3
        assert len(vertices) > 0
        assert len(faces) > 0

    def test_reconstruct_mesh_too_few_points_returns_empty(self):
        """Test 2: reconstruct_mesh with fewer than 10 points returns empty arrays."""
        points = np.random.default_rng(42).uniform(-1, 1, (5, 3))

        vertices, faces, vertex_colors = mesh_mod.reconstruct_mesh(points)

        assert vertices.shape == (0, 3)
        assert faces.shape == (0, 3)
        assert vertex_colors is None

    def test_reconstruct_mesh_available_returns_true(self):
        """Test 3: reconstruct_mesh_available returns True when Open3D is importable."""
        assert mesh_mod.reconstruct_mesh_available() is True


class TestReconstructMeshUnavailable:
    """Tests for graceful degradation when Open3D is not installed."""

    def test_reconstruct_mesh_raises_when_unavailable(self):
        """Test 4: When open3d is not importable, reconstruct_mesh raises ImportError with INSTALL_HINT."""
        saved_o3d = sys.modules.pop("open3d", None)
        saved_submodules = {
            k: v for k, v in sys.modules.items() if k.startswith("open3d.")
        }
        for k in saved_submodules:
            sys.modules.pop(k, None)
        # Make open3d raise ImportError on import
        sys.modules["open3d"] = None  # type: ignore[assignment]
        try:
            importlib.reload(mesh_mod)
            with pytest.raises(ImportError, match="Open3D"):
                mesh_mod.reconstruct_mesh(np.zeros((20, 3)))
        finally:
            # Restore open3d
            sys.modules.pop("open3d", None)
            if saved_o3d is not None:
                sys.modules["open3d"] = saved_o3d
            for k, v in saved_submodules.items():
                sys.modules[k] = v
            importlib.reload(mesh_mod)

    def test_reconstruct_mesh_available_false_when_unavailable(self):
        """Test 5: reconstruct_mesh_available returns False when Open3D is not importable."""
        saved_o3d = sys.modules.pop("open3d", None)
        saved_submodules = {
            k: v for k, v in sys.modules.items() if k.startswith("open3d.")
        }
        for k in saved_submodules:
            sys.modules.pop(k, None)
        sys.modules["open3d"] = None  # type: ignore[assignment]
        try:
            importlib.reload(mesh_mod)
            assert mesh_mod.reconstruct_mesh_available() is False
        finally:
            sys.modules.pop("open3d", None)
            if saved_o3d is not None:
                sys.modules["open3d"] = saved_o3d
            for k, v in saved_submodules.items():
                sys.modules[k] = v
            importlib.reload(mesh_mod)
