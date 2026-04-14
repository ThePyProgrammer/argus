"""Unit tests for src/perception/geometry.py — the single projection entrypoint (DET-3D-06).

Locks the Pitfall 8 sign-flip convention (cam_pt = [cam_x, -cam_y, -depth])
and the Pitfall 10 invariant (no cloud_config import). These tests are
authored in Wave 0 so Plan 03 (median_depth migration) can rely on the
contract already being test-locked.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics


@pytest.fixture
def intrinsics():
    return CameraIntrinsics.from_fov(width=640, height=480, fov_degrees=70.0)


@pytest.fixture
def identity_pose():
    return np.eye(4)


def test_unproject_single_pixel_identity_pose_sign_convention(intrinsics, identity_pose):
    """Pitfall 8 lock: center pixel at depth=2.0 with identity pose -> (0, 0, -2)."""
    from src.perception.geometry import unproject_pixel_to_world
    out = unproject_pixel_to_world(
        u=intrinsics.cx, v=intrinsics.cy, depth=2.0,
        intrinsics=intrinsics, pose=identity_pose,
    )
    np.testing.assert_allclose(out, np.array([0.0, 0.0, -2.0]), atol=1e-9)


def test_unproject_batched_matches_single_pixel(intrinsics, identity_pose):
    from src.perception.geometry import (
        unproject_pixel_to_world,
        unproject_pixels_batched,
    )
    rng = np.random.default_rng(0)
    uvs = rng.uniform(low=0, high=[640, 480], size=(16, 2))
    depths = rng.uniform(low=0.5, high=5.0, size=16)
    batched = unproject_pixels_batched(uvs, depths, intrinsics, identity_pose)
    assert batched.shape == (16, 3)
    for i in range(16):
        single = unproject_pixel_to_world(
            u=float(uvs[i, 0]), v=float(uvs[i, 1]),
            depth=float(depths[i]), intrinsics=intrinsics, pose=identity_pose,
        )
        np.testing.assert_allclose(batched[i], single, atol=1e-9)


def test_unproject_applies_pose_rotation_and_translation(intrinsics):
    from scipy.spatial.transform import Rotation

    from src.perception.geometry import unproject_pixel_to_world
    # 90 deg rotation about +Z + translation [1, 2, 3]
    R = Rotation.from_euler("z", np.pi / 2).as_matrix()
    pose = np.eye(4)
    pose[:3, :3] = R
    pose[:3, 3] = [1.0, 2.0, 3.0]
    out = unproject_pixel_to_world(
        u=intrinsics.cx, v=intrinsics.cy, depth=1.0,
        intrinsics=intrinsics, pose=pose,
    )
    # Camera-frame point (0, 0, -1) under 90 deg Z rotation -> (0, 0, -1)
    # (z-rotation preserves z), then + translation -> (1, 2, 2).
    np.testing.assert_allclose(out, np.array([1.0, 2.0, 2.0]), atol=1e-9)


def test_legacy_parity_with_median_depth_intrinsics(intrinsics, identity_pose):
    """Bit-parity: the NEW geometry call at the bbox-center pixel matches the OLD
    median_depth.project_center_median_depth (PRE-Plan 03) to +/-1e-9. This pins
    the migration so Plan 03 can delete _LEGACY_FOV_DEG without changing behavior.
    """
    from src.perception.geometry import unproject_pixel_to_world
    from src.perception.lifters.median_depth import project_center_median_depth
    bbox = (100, 100, 200, 200)
    depth = np.full((480, 640), 2.5, dtype=np.float32)
    # Plan 04-03: project_center_median_depth now consumes intrinsics (no hardcoded FOV).
    # Passing CameraIntrinsics.from_fov(640, 480, 70.0) preserves bit-parity with the
    # pre-migration 70° default.
    legacy_out = project_center_median_depth(bbox, depth, identity_pose, intrinsics)
    assert legacy_out is not None
    legacy_world, legacy_d = legacy_out
    # New path: unproject the same bbox-center pixel at the same depth.
    cx_px = (bbox[0] + bbox[2]) // 2
    cy_px = (bbox[1] + bbox[3]) // 2
    new_world = unproject_pixel_to_world(
        u=float(cx_px), v=float(cy_px), depth=float(legacy_d),
        intrinsics=intrinsics, pose=identity_pose,
    )
    np.testing.assert_allclose(new_world, legacy_world, atol=1e-9)


def test_grep_no_fov_constants_outside_geometry():
    """Pitfall 9 lock (part 1): after Plan 03 lands, no FOV math executes
    outside geometry.py. This test ASSERTS the CURRENT state: _LEGACY_FOV_DEG
    may exist in median_depth.py (still) but must NOT appear in geometry.py's
    executable code (docstrings allowed). Plan 03 tightens this further."""
    perception_dir = Path(__file__).resolve().parents[2] / "src" / "perception"
    geometry_file = perception_dir / "geometry.py"
    src = geometry_file.read_text()
    # Allow _LEGACY_FOV_DEG only inside triple-quoted docstrings/comments;
    # forbid it as an executable identifier.
    code_lines = [
        ln for ln in src.split("\n")
        if ln.strip() and not ln.lstrip().startswith(("#", '"', "'"))
    ]
    joined = "\n".join(code_lines)
    assert "_LEGACY_FOV_DEG" not in joined, (
        "geometry.py must not define or reference _LEGACY_FOV_DEG in executable code"
    )
    # Positive: the function names expected by D-05 are present.
    assert "def unproject_pixel_to_world" in src
    assert "def unproject_pixels_batched" in src


def test_geometry_does_not_import_cloud_config():
    """Pitfall 10: src/perception/geometry.py MUST NOT import src.bridge.cloud_config."""
    # Force-import into a fresh module object
    sys.modules.pop("src.perception.geometry", None)
    sys.modules.pop("src.bridge.cloud_config", None)
    importlib.import_module("src.perception.geometry")
    assert "src.bridge.cloud_config" not in sys.modules, (
        "geometry.py pulled cloud_config into sys.modules -- forbidden per Pitfall 10"
    )


def test_geometry_module_uses_camera_intrinsics_type(intrinsics, identity_pose):
    """Confirm the module consumes the project's CameraIntrinsics dataclass, not a tuple."""
    from src.perception.geometry import unproject_pixel_to_world
    # Passing CameraIntrinsics works (test 1 already exercised this). Passing a
    # tuple should TypeError/AttributeError because the impl reads .fx etc.
    with pytest.raises((TypeError, AttributeError)):
        unproject_pixel_to_world(
            u=320.0, v=240.0, depth=2.0,
            intrinsics=(1.0, 2.0, 3.0, 4.0),  # tuple -- must fail
            pose=identity_pose,
        )


def test_legacy_fov_deg_absent_post_migration():
    """DET-3D-06 + D-06: after Plan 04-03, _LEGACY_FOV_DEG must NOT appear
    in ANY file under src/perception/. Pitfall 9: we check the exact token,
    not a substring, so unrelated '70' literals do not false-positive."""
    perception_root = Path(__file__).resolve().parents[2] / "src" / "perception"
    offenders: list[str] = []
    for py in perception_root.rglob("*.py"):
        txt = py.read_text()
        if "_LEGACY_FOV_DEG" in txt:
            offenders.append(str(py))
    assert offenders == [], f"_LEGACY_FOV_DEG still present in: {offenders}"


def test_no_math_tan_or_radians_in_perception_lifters():
    """DET-3D-06: lifters delegate all pinhole math to geometry.py; no file
    under src/perception/lifters/ may call math.tan(...) or math.radians(...)
    in executable code."""
    import re

    lifters_root = Path(__file__).resolve().parents[2] / "src" / "perception" / "lifters"
    pattern = re.compile(r"math\.(tan|radians)\s*\(")
    offenders: list[str] = []
    for py in lifters_root.rglob("*.py"):
        # Skip lines starting with common comment/docstring delimiters.
        for i, line in enumerate(py.read_text().split("\n"), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("#", '"""', "'''", '"', "'")):
                continue
            if pattern.search(line):
                offenders.append(f"{py}:{i}:{line.strip()}")
    assert offenders == [], f"math.tan/math.radians in lifter code: {offenders}"


def test_geometry_is_only_perception_module_with_executable_fov_math():
    """DET-3D-06 single-entrypoint gate: across the whole src/perception/ package,
    executable calls to math.tan() / math.radians() exist ONLY in geometry.py
    (and in practice, the Pattern Template 2 implementation doesn't even use
    them -- CameraIntrinsics.from_fov handles the derivation at capture time).
    """
    import re

    perception_root = Path(__file__).resolve().parents[2] / "src" / "perception"
    pattern = re.compile(r"math\.(tan|radians)\s*\(")
    allowed = {"geometry.py"}
    offenders: list[str] = []
    for py in perception_root.rglob("*.py"):
        for i, line in enumerate(py.read_text().split("\n"), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("#", '"""', "'''", '"', "'")):
                continue
            if pattern.search(line) and py.name not in allowed:
                offenders.append(f"{py}:{i}:{line.strip()}")
    assert offenders == [], (
        f"math.tan/math.radians outside geometry.py in perception pkg: {offenders}"
    )
