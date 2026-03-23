# Phase 11: ORB-SLAM3 Backend - Research

**Researched:** 2026-03-23
**Domain:** ORB-SLAM3 visual SLAM integration via Python bindings, MuJoCo texture augmentation
**Confidence:** MEDIUM (Python 3.14 compatibility is unverified; orbslam3-python API confirmed but wheels only exist for 3.8-3.12)

## Summary

Integrating ORB-SLAM3 as a second SLAM backend requires wrapping the `orbslam3-python` PyPI package (v2.0.0) behind the existing `SLAMProtocol` interface, following the `ICPBackend` template exactly. The API is straightforward: `orbslam3.System(vocab_path, settings_path, orbslam3.Sensor.RGBD)` constructs the system, `slam.process_image_rgbd(rgb, depth, timestamp)` processes frames, and `slam.get_frame_pose()` returns a 4x4 numpy pose. Dense point clouds are generated from depth images using the existing `depth_to_pointcloud()` utility with ORB-SLAM3-estimated poses, not from ORB-SLAM3's sparse map points.

The critical risk is Python version compatibility: the project runs Python 3.14.3 but `orbslam3-python` only ships wheels for Python 3.8-3.12. Building from source requires Pangolin, Eigen3, OpenCV, and Boost as system dependencies. The build system expects a pre-installed ORB-SLAM3, not a self-contained build. The recommended mitigation is to attempt a source build first, with a fallback plan of creating a thin pybind11 wrapper around a locally compiled ORB-SLAM3.

ORB-SLAM3 uses camera-optical coordinate convention (z-forward, x-right, y-down) while the project uses MuJoCo's z-up world frame. A static `T_world_from_camera` transform must be applied to every pose output. MuJoCo scenes need texture additions (checkerboard walls, wood grain floors) so ORB features can be extracted from the currently flat-colored synthetic images.

**Primary recommendation:** Follow the ICPBackend 1:1 as a structural template. Wrap orbslam3-python's System class. Generate ORB-SLAM3 YAML config from CameraIntrinsics at startup. Handle the coordinate frame transform. Add textures to MuJoCo XML. Guard the import with try/except so the backend is unavailable when orbslam3-python is not installed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use **full ORB-SLAM3 output**: pose estimates + sparse ORB feature map for visualization/debugging + depth-generated dense cloud for downstream consumers
- Backend calls `depth_to_pointcloud(frame.depth, frame.rgb, intrinsics)` internally using its estimated pose -- same utility as ICP, consistent output
- Sparse ORB features available as a secondary layer (SLAMResult.metrics can carry sparse point count and feature positions)
- Supports both **RGB-D** and **monocular** modes, selectable from the parameter panel
- **Hybrid approach**: Add textures to MuJoCo scene XML (checkerboard/wood grain on walls/floors) AND tune ORB-SLAM3 feature extraction params
- Expose key ORB-SLAM3 params in PARAMETER_SCHEMA: `nFeatures` (default 1000), `scaleFactor` (default 1.2), `nLevels` (default 8)
- **When LOST**: Return `tracking_status=LOST` + last known pose. Robot stops navigating until tracking recovers. ExplorationLoop's stuck detection handles recovery.
- **Frontend status indicator**: Each robot marker in Three.js changes color -- green=OK, red=LOST, yellow=RELOCALIZING
- **During INITIALIZING**: Robot drives forward slowly to provide diverse viewpoints for faster initialization
- **Vocabulary file + camera config**: Store in `models/orbslam3/`. Git-track the YAML config, `.gitignore` the vocabulary file (~40MB). Include download script (`scripts/download_orbslam3_vocab.sh`)
- **Camera calibration**: Backend generates a temporary YAML file from `CameraIntrinsics` on initialization. ORB-SLAM3 reads it. Cleaned up on `reset()`
- **Process model**: In-process via pybind11 (orbslam3-python). No subprocess isolation

### Claude's Discretion
- Exact temporary YAML file format and location (tempfile vs models/ subdirectory)
- How to expose sparse ORB features in SLAMResult.metrics (point list vs count-only)
- Error handling for orbslam3-python import failure (ImportError -> mark unavailable in registry)
- Exact MuJoCo XML texture additions (material/texture choice)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-01 | ORB-SLAM3 backend integrates via orbslam3-python, producing pose estimates from RGB-D frames | orbslam3-python API verified: `System(vocab, yaml, Sensor.RGBD)` + `process_image_rgbd(rgb, depth, ts)` + `get_frame_pose()`. Coordinate frame transform from camera-optical to MuJoCo world frame required. |
| BACK-02 | ORB-SLAM3 backend uses SLAM-estimated poses with depth-image-generated dense clouds (not sparse ORB features) for downstream consumers | Existing `depth_to_pointcloud()` utility in `src/slam/depth_to_cloud.py` generates dense clouds from depth+intrinsics. Backend applies ORB-SLAM3 pose to transform cloud to world frame, same pattern as ICPBackend. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| orbslam3-python | 2.0.0 | ORB-SLAM3 pybind11 bindings | Only pip-installable ORB-SLAM3 wrapper with full SLAM system (not just feature extraction). Provides System class, RGBD/mono/stereo modes, pose+map output. |
| ORBvoc.txt (vocabulary) | n/a | ORB feature vocabulary for bag-of-words place recognition | Required by ORB-SLAM3 for loop closure and relocalization. ~40MB text, ~140MB binary. Ships with ORB-SLAM3 source. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tempfile (stdlib) | n/a | Generate ephemeral YAML config for ORB-SLAM3 | At backend initialization: write CameraIntrinsics as YAML, pass path to System constructor |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| orbslam3-python (PyPI) | pyOrbSlam3 (JHMeusener) | More transparent wrapper but requires building ORB-SLAM3 from source -- same Python 3.14 risk |
| orbslam3-python (PyPI) | edavalosanaya/pyorbslam | Still in development, less mature, same build requirements |
| python-orb-slam3 (PyPI) | n/a | This is ONLY a feature extractor (ORBExtractor.detectAndCompute), NOT a full SLAM system. Cannot be used. |

**Installation:**
```bash
# Attempt 1: pip (only works for Python 3.8-3.12)
pip install orbslam3-python==2.0.0

# Attempt 2: source build for Python 3.14
# Requires: Eigen3, OpenCV 4.x, Boost, Pangolin, CMake >= 3.4
pip install orbslam3-python --no-binary :all:
```

**CRITICAL: Python 3.14 Compatibility Issue**

The project runs Python 3.14.3 (verified). `orbslam3-python` only provides wheels for Python 3.8-3.12. The `pyproject.toml` says `requires-python = ">=3.10,<3.13"` but the active interpreter is 3.14. This creates a hard blocker.

**Mitigation strategy (in priority order):**
1. Try `pip install orbslam3-python --no-binary :all:` to build from source on 3.14
2. If that fails, clone the source repo and build with local pybind11 >= 2.13 (which supports Python 3.14)
3. If ORB-SLAM3 C++ build proves too painful, wrap the import in try/except and mark the backend as `available: false` in the registry -- the system still works with ICP

## Architecture Patterns

### Recommended Project Structure
```
src/slam/backends/
    __init__.py              # Add: from src.slam.backends import orbslam3_backend
    icp_backend.py           # Existing reference template
    orbslam3_backend.py      # NEW: ORB-SLAM3 backend

models/orbslam3/
    ORBvoc.txt               # .gitignored, downloaded by script
    README.md                # Instructions for vocabulary download

scripts/
    download_orbslam3_vocab.sh  # NEW: wget/curl vocabulary file
```

### Pattern 1: Backend Delegation (follow ICPBackend exactly)
**What:** ORB-SLAM3 backend wraps orbslam3-python's System class, same as ICPBackend wraps SLAMPipeline.
**When to use:** Always -- this is the established pattern.
**Example:**
```python
# Source: existing ICPBackend pattern + orbslam3-python API
import tempfile
import numpy as np

try:
    import orbslam3
    _ORBSLAM3_AVAILABLE = True
except ImportError:
    _ORBSLAM3_AVAILABLE = False

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.depth_to_cloud import depth_to_pointcloud
from src.slam.protocol import SLAMResult, TrackingStatus
from src.slam.registry import slam_backend


@slam_backend(name="orbslam3", display="ORB-SLAM3")
class ORBSlam3Backend:
    CAPABILITIES: dict = {
        "supports_imu": False,
        "outputs_dense": True,  # via depth_to_pointcloud, not native
        "supports_loop_closure": True,
        "supports_stereo": False,
    }

    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "nFeatures": {
                "type": "integer",
                "default": 1000,
                "minimum": 100,
                "maximum": 5000,
                "description": "Number of ORB features per frame",
                "live_tunable": False,
            },
            "scaleFactor": {
                "type": "number",
                "default": 1.2,
                "minimum": 1.01,
                "maximum": 2.0,
                "description": "Pyramid decimation ratio",
                "live_tunable": False,
            },
            "nLevels": {
                "type": "integer",
                "default": 8,
                "minimum": 1,
                "maximum": 16,
                "description": "Number of pyramid levels",
                "live_tunable": False,
            },
            "mode": {
                "type": "string",
                "default": "rgbd",
                "enum": ["rgbd", "monocular"],
                "description": "ORB-SLAM3 sensor mode",
                "live_tunable": False,
            },
        },
    }

    def __init__(
        self,
        intrinsics: CameraIntrinsics,
        nFeatures: int = 1000,
        scaleFactor: float = 1.2,
        nLevels: int = 8,
        mode: str = "rgbd",
    ):
        if not _ORBSLAM3_AVAILABLE:
            raise ImportError("orbslam3-python is not installed")
        self._intrinsics = intrinsics
        self._mode = mode
        self._last_pose = np.eye(4)
        self._poses: list[np.ndarray] = []
        self._global_points = np.empty((0, 3))
        self._global_colors = np.empty((0, 3))
        self._num_frames = 0

        # Generate temp YAML config
        self._config_path = self._write_config(
            intrinsics, nFeatures, scaleFactor, nLevels
        )

        # Vocabulary path
        vocab_path = "models/orbslam3/ORBvoc.txt"
        sensor = (
            orbslam3.Sensor.RGBD if mode == "rgbd"
            else orbslam3.Sensor.MONOCULAR
        )
        self._slam = orbslam3.System(vocab_path, self._config_path, sensor)
        self._slam.set_use_viewer(False)
        self._slam.initialize()
```

### Pattern 2: Coordinate Frame Transform
**What:** ORB-SLAM3 outputs poses in camera-optical frame (z-forward, x-right, y-down). MuJoCo uses z-up. Apply a static rotation.
**When to use:** Every `process_frame` call -- transform the 4x4 pose from ORB-SLAM3's frame to world frame.
**Example:**
```python
# Camera-optical (z-forward, y-down) to MuJoCo world (z-up, x-forward)
# The exact transform depends on how the MuJoCo camera is oriented.
# For ORB-SLAM3 pure visual SLAM: world = first camera frame.
# We need to convert from camera-optical to MuJoCo convention.
T_MUJOCO_FROM_OPTICAL = np.array([
    [0,  0, 1, 0],   # MuJoCo x = optical z (forward)
    [-1, 0, 0, 0],   # MuJoCo y = -optical x (left)
    [0, -1, 0, 0],   # MuJoCo z = -optical y (up)
    [0,  0, 0, 1],
], dtype=np.float64)

def _convert_pose(self, orbslam_pose: np.ndarray) -> np.ndarray:
    """Convert ORB-SLAM3 camera pose to MuJoCo world frame."""
    return T_MUJOCO_FROM_OPTICAL @ orbslam_pose
```

### Pattern 3: YAML Config Generation from CameraIntrinsics
**What:** ORB-SLAM3 reads camera params from a YAML file. Generate it from CameraIntrinsics at startup.
**When to use:** In `__init__` before creating the System object.
**Example:**
```python
def _write_config(
    self,
    intrinsics: CameraIntrinsics,
    nFeatures: int,
    scaleFactor: float,
    nLevels: int,
) -> str:
    """Write ORB-SLAM3 YAML config to a temp file, return path."""
    yaml_content = f"""%YAML:1.0
Camera.type: "PinHole"
Camera.fx: {intrinsics.fx}
Camera.fy: {intrinsics.fy}
Camera.cx: {intrinsics.cx}
Camera.cy: {intrinsics.cy}
Camera.k1: 0.0
Camera.k2: 0.0
Camera.p1: 0.0
Camera.p2: 0.0
Camera.k3: 0.0
Camera.width: {intrinsics.width}
Camera.height: {intrinsics.height}
Camera.fps: 30.0
Camera.RGB: 1
ThDepth: 40.0
DepthMapFactor: 1.0
ORBextractor.nFeatures: {nFeatures}
ORBextractor.scaleFactor: {scaleFactor}
ORBextractor.nLevels: {nLevels}
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7
Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1.0
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2.0
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3.0
Viewer.ViewpointX: 0.0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500.0
"""
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix="orbslam3_",
        delete=False,
    )
    fd.write(yaml_content)
    fd.close()
    return fd.name
```

### Pattern 4: Graceful Import Failure
**What:** If orbslam3-python is not installed, the backend registers but marks itself unavailable.
**When to use:** Module-level try/except around import.
**Example:**
```python
# At module top level:
try:
    import orbslam3
    _ORBSLAM3_AVAILABLE = True
except ImportError:
    _ORBSLAM3_AVAILABLE = False

# The @slam_backend decorator still registers the class.
# SLAMRegistry.list_backends() will try to load the class and
# if _ORBSLAM3_AVAILABLE is False, the constructor raises ImportError.
# The registry's _load_class catches this and marks available=False.
```

### Anti-Patterns to Avoid
- **Running ORB-SLAM3 as a subprocess:** The decision is in-process via pybind11. Subprocess isolation is reserved for Phase 12 backends (OpenVINS, SVO Pro).
- **Using ORB-SLAM3's sparse map points as the dense cloud:** BACK-02 explicitly requires depth-generated dense clouds. Sparse ORB features go in `SLAMResult.metrics`, not `SLAMResult.points`.
- **Hardcoding camera parameters:** Always generate from CameraIntrinsics. Different MuJoCo scenes may have different FOV.
- **Blocking on vocabulary load in the main thread:** Vocabulary loading takes 0.5-20s depending on format. Consider loading in backend constructor (acceptable for pre-session selection).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dense cloud from depth | Custom deprojection math | `depth_to_pointcloud()` in `src/slam/depth_to_cloud.py` | Already handles intrinsics, Y/Z flips, color mapping, Open3D integration |
| ORB feature extraction | OpenCV ORB + custom matching | orbslam3-python full SLAM system | ORB-SLAM3 includes tracking, mapping, loop closure, relocalization -- not just feature extraction |
| YAML config file writing | Custom YAML library | f-string template + tempfile | ORB-SLAM3 YAML is simple key-value, no nested structures. PyYAML not needed. |
| Backend registration | Manual import management | `@slam_backend` decorator + `__init__.py` import | Registry handles lazy loading, availability checking |

**Key insight:** The backend is a thin adapter between orbslam3-python's API and SLAMProtocol. The existing infrastructure (registry, depth_to_cloud, protocol types) does the heavy lifting. The new code is ~200 lines.

## Common Pitfalls

### Pitfall 1: Python 3.14 Incompatibility with orbslam3-python Wheels
**What goes wrong:** `pip install orbslam3-python` fails because no cp314 wheels exist on PyPI.
**Why it happens:** orbslam3-python v2.0.0 only ships manylinux wheels for Python 3.8-3.12. Python 3.14 is too new.
**How to avoid:** Attempt source build with `--no-binary :all:`. If that fails, the backend simply stays unavailable -- the system works fine with ICP only. Document the Python version requirement clearly.
**Warning signs:** `pip install` fails with "no matching distribution" or build errors during `cmake`.

### Pitfall 2: ORB Feature Tracking Fails on Flat MuJoCo Surfaces
**What goes wrong:** ORB-SLAM3 extracts zero or too few features from MuJoCo's default flat-colored walls and floors, causing immediate tracking loss.
**Why it happens:** ORB features need texture gradients. Default MuJoCo scenes use solid colors.
**How to avoid:** Add checkerboard/gradient textures to walls, floors, and obstacle surfaces in the MuJoCo scene XML. The scene already has a checkerboard ground plane -- extend this to walls and vertical surfaces.
**Warning signs:** `tracking_status` stays at `INITIALIZING` or immediately goes to `LOST`.

### Pitfall 3: Coordinate Frame Mismatch Produces Rotated Trajectories
**What goes wrong:** Robot appears to move sideways or vertically. Map points are rotated 90 degrees from expected orientation.
**Why it happens:** ORB-SLAM3 uses camera-optical convention (z-forward, y-down). MuJoCo uses z-up. Without the `T_world_from_camera` transform, poses are in the wrong frame.
**How to avoid:** Apply the static rotation matrix documented in Architecture Patterns above. Verify by comparing the first pose's position against ground truth. Write a test that checks trajectory direction matches MuJoCo ground truth.
**Warning signs:** Pose[:3,3] position components are swapped (e.g., depth shows up as height).

### Pitfall 4: Vocabulary File Not Found at Runtime
**What goes wrong:** ORB-SLAM3 crashes or throws when `models/orbslam3/ORBvoc.txt` does not exist.
**Why it happens:** The vocabulary file is .gitignored (40MB+). New clones or CI environments won't have it.
**How to avoid:** Check file existence in `__init__`. Provide a clear error message pointing to the download script. Add a check in the download script that verifies file integrity (size or checksum).
**Warning signs:** Segfault or cryptic C++ exception from ORB-SLAM3 initialization.

### Pitfall 5: DepthMapFactor Mismatch
**What goes wrong:** ORB-SLAM3 treats depth values as millimeters when they're actually meters, producing a map 1000x too large or too small.
**Why it happens:** ORB-SLAM3's `DepthMapFactor` scales raw depth values. TUM datasets use 5000 (depth in mm / 5000 = meters). MuJoCo's depth is already in meters.
**How to avoid:** Set `DepthMapFactor: 1.0` in the generated YAML. MuJoCo depth from `sim_bridge.py` is in meters, no conversion needed.
**Warning signs:** Map scale is wildly wrong. Points appear at 5000m instead of 5m.

### Pitfall 6: Temporary YAML File Leaks on Crash
**What goes wrong:** Temp YAML files accumulate in /tmp if the process crashes without calling `reset()`.
**Why it happens:** `tempfile.NamedTemporaryFile(delete=False)` creates persistent files.
**How to avoid:** Use `atexit.register()` to clean up, or store the path and clean in `__del__`. Also clean in `reset()`.

## Code Examples

### ORB-SLAM3 System Initialization (verified from orbslam3-python examples)
```python
# Source: github.com/AlexandruRO45/ORB_SLAM-PythonBindings/examples/orbslam_rgbd_tum.py
import orbslam3

slam = orbslam3.System(
    vocab_path,          # str: path to ORBvoc.txt
    settings_path,       # str: path to camera config YAML
    orbslam3.Sensor.RGBD # enum: RGBD, MONOCULAR, STEREO, IMU_MONOCULAR, etc.
)
slam.set_use_viewer(False)  # Disable Pangolin viewer
slam.initialize()

# Process one RGB-D frame
slam.process_image_rgbd(rgb_image, depth_image, timestamp)

# Get results
pose_4x4 = slam.get_frame_pose()           # numpy (4,4) float64
points = slam.get_current_points()          # list of ((wx,wy,wz), (u,v)) tuples
camera_matrix = slam.get_camera_matrix()    # numpy array
```

### ORB-SLAM3 Monocular Mode
```python
# Source: github.com/AlexandruRO45/ORB_SLAM-PythonBindings/examples/orbslam_mono_kitti.py
slam = orbslam3.System(vocab_path, settings_path, orbslam3.Sensor.MONOCULAR)
slam.set_use_viewer(False)
slam.initialize()

slam.process_image_mono(rgb_image, timestamp)
pose = slam.get_frame_pose()
```

### ORB-SLAM3 YAML Config Format (verified from ORB_SLAM3/Examples/RGB-D/TUM1.yaml)
```yaml
%YAML:1.0

# Camera calibration (PinHole model)
Camera.type: "PinHole"
Camera.fx: 517.306408
Camera.fy: 516.469215
Camera.cx: 318.643040
Camera.cy: 255.313989

# Distortion (0 for simulated cameras)
Camera.k1: 0.0
Camera.k2: 0.0
Camera.p1: 0.0
Camera.p2: 0.0
Camera.k3: 0.0

# Image dimensions and frame rate
Camera.width: 640
Camera.height: 480
Camera.fps: 30.0
Camera.RGB: 1

# Stereo/depth thresholds
ThDepth: 40.0
DepthMapFactor: 1.0  # MuJoCo depth is in meters

# ORB feature extractor
ORBextractor.nFeatures: 1000
ORBextractor.scaleFactor: 1.2
ORBextractor.nLevels: 8
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7
```

### MuJoCo Texture Additions (for ORB feature extraction)
```xml
<!-- Source: MuJoCo XML Reference - asset/texture and asset/material -->
<!-- Add to scene.xml <asset> section -->

<!-- Checkerboard for walls -->
<texture name="wall_checker" type="2d" builtin="checker"
         rgb1="0.8 0.7 0.6" rgb2="0.6 0.5 0.4"
         width="512" height="512"/>
<material name="wall_checker" texture="wall_checker"
          texrepeat="4 4" texuniform="true"/>

<!-- Wood grain pattern for floor (supplement existing groundplane) -->
<texture name="wood_floor" type="2d" builtin="checker"
         rgb1="0.55 0.35 0.15" rgb2="0.45 0.28 0.12"
         markrgb="0.6 0.4 0.2"
         width="512" height="512"/>
<material name="wood_floor" texture="wood_floor"
          texrepeat="8 8" texuniform="true"/>

<!-- Gradient for variety -->
<texture name="wall_gradient" type="2d" builtin="gradient"
         rgb1="0.9 0.85 0.8" rgb2="0.7 0.65 0.6"
         width="512" height="512"/>
<material name="wall_gradient" texture="wall_gradient"
          texrepeat="2 2" texuniform="true"/>

<!-- Apply to wall geoms -->
<geom name="wall_north" type="box" size="5 0.1 2" pos="0 5 1"
      material="wall_checker"/>
```

### Frontend Tracking Status Color Change
```typescript
// In RobotMarkerManager.updateRobot() -- add trackingStatus parameter
// Reuse existing mesh material, just change color
const STATUS_COLORS = {
  ok: 0x00cc00,            // green
  lost: 0xcc0000,          // red
  relocalizing: 0xcccc00,  // yellow
  initializing: 0xcccc00,  // yellow
} as const;

// In updateRobot, after position update:
if (trackingStatus && existing) {
  const color = new THREE.Color(STATUS_COLORS[trackingStatus] ?? 0x00cc00);
  existing.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) {
      const mat = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
      mat.color.copy(color);
      mat.emissive.copy(color);
    }
  });
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Build ORB-SLAM3 from source | orbslam3-python pip install | Oct 2025 (v2.0.0) | Eliminates CMake/Pangolin build pain for Python 3.8-3.12 |
| ORBvoc.txt (text, 20s load) | ORBvoc.bin (binary, 0.5s load) | Available since ORB-SLAM2 | Use binary format for faster backend initialization |
| ORB-SLAM3 sparse-only output | Depth-based dense cloud + sparse features | Project decision | Avoids sparse/dense mismatch with ICP baseline |

**Deprecated/outdated:**
- ORB-SLAM2 Python bindings (thunber, 2018): Superseded by ORB-SLAM3 wrappers
- python-orb-slam3 (mnixry): Only wraps feature extraction, not the full SLAM system

## Open Questions

1. **Will orbslam3-python build from source on Python 3.14?**
   - What we know: Wheels exist for 3.8-3.12 only. Build requires Pangolin, Eigen3, OpenCV, Boost.
   - What's unclear: Whether pybind11 in the orbslam3-python source supports Python 3.14's C API changes.
   - Recommendation: Attempt the build as Wave 0 task. If it fails, mark backend as unavailable and document. The system still works with ICP.

2. **Binary vs text vocabulary format support in orbslam3-python**
   - What we know: ORB-SLAM3 C++ supports both. Binary loads 40x faster.
   - What's unclear: Whether orbslam3-python's System constructor accepts .bin format or only .txt.
   - Recommendation: Start with .txt (guaranteed compatible). Try .bin as optimization if load time is a problem.

3. **Exact coordinate frame transform for MuJoCo camera convention**
   - What we know: ORB-SLAM3 uses optical frame (z-forward). MuJoCo camera xyaxes in scene_builder.py is `"0 -1 0 0 0 1"`.
   - What's unclear: The exact rotation between ORB-SLAM3's first-frame world and MuJoCo's world frame.
   - Recommendation: Implement the transform, then validate by running 10 frames and comparing pose[:3,3] against ground_truth_pose[:3,3]. Adjust if axes are swapped.

4. **Does the office scene (scene_office1.xml from DimOS) already have textures?**
   - What we know: The basic scene.xml has a checkerboard ground. The office scene is loaded from DimOS data.
   - What's unclear: Whether DimOS scene has sufficient texture for ORB features.
   - Recommendation: Test ORB-SLAM3 on the office scene first. Add textures only to surfaces where tracking fails.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml [tool.pytest] (implicit) |
| Quick run command | `python -m pytest tests/slam/test_orbslam3_backend.py -x` |
| Full suite command | `python -m pytest tests/slam/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BACK-01 | ORB-SLAM3 produces pose estimates from RGB-D frames | integration | `pytest tests/slam/test_orbslam3_backend.py::TestORBSlam3Behavior::test_process_frame_returns_pose -x` | Wave 0 |
| BACK-01 | Backend registers in SLAMRegistry | unit | `pytest tests/slam/test_orbslam3_backend.py::TestORBSlam3Registry::test_registry_registration -x` | Wave 0 |
| BACK-01 | Backend satisfies SLAMProtocol | unit | `pytest tests/slam/test_orbslam3_backend.py::TestORBSlam3Protocol::test_isinstance_protocol -x` | Wave 0 |
| BACK-02 | Dense cloud from depth (not sparse features) | unit | `pytest tests/slam/test_orbslam3_backend.py::TestORBSlam3Behavior::test_dense_cloud_from_depth -x` | Wave 0 |
| BACK-02 | SLAMResult.points has dense cloud, sparse in metrics | unit | `pytest tests/slam/test_orbslam3_backend.py::TestORBSlam3Behavior::test_sparse_in_metrics -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/slam/test_orbslam3_backend.py -x`
- **Per wave merge:** `python -m pytest tests/slam/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/slam/test_orbslam3_backend.py` -- covers BACK-01, BACK-02 (mirror test_icp_backend.py structure)
- [ ] Mock/skip strategy for when orbslam3-python is not installed (`pytest.importorskip("orbslam3")`)

## Sources

### Primary (HIGH confidence)
- [orbslam3-python PyPI](https://pypi.org/project/orbslam3-python/) -- Package version, wheel availability, Python support (3.8-3.12)
- [orbslam3-python GitHub (AlexandruRO45)](https://github.com/AlexandruRO45/ORB_SLAM-PythonBindings/) -- API: System constructor, process_image_rgbd, get_frame_pose, get_current_points
- [ORB-SLAM3 official repo (UZ-SLAMLab)](https://github.com/UZ-SLAMLab/ORB_SLAM3) -- YAML config format, vocabulary file, coordinate conventions
- [ORB-SLAM3 coordinate system issue #681](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/681) -- Camera-optical convention (z-forward, y-down)
- [MuJoCo XML Reference](https://mujoco.readthedocs.io/en/latest/XMLreference.html) -- Texture/material element attributes and builtin types
- Existing codebase: `src/slam/backends/icp_backend.py`, `src/slam/protocol.py`, `src/slam/registry.py`, `src/slam/depth_to_cloud.py` -- Verified template patterns

### Secondary (MEDIUM confidence)
- [ORB-SLAM3 TUM1.yaml example](https://github.com/UZ-SLAMLab/ORB_SLAM3/blob/master/Examples/RGB-D/TUM1.yaml) -- YAML format verified but may differ for orbslam3-python wrapper
- [Binary vocabulary speedup PR](https://github.com/raulmur/ORB_SLAM2/pull/21) -- 40x speedup verified for ORB-SLAM2, assumed same for ORB-SLAM3
- [ORB-SLAM3 build issues](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/668) -- Build dependency pain points

### Tertiary (LOW confidence)
- orbslam3-python source build on Python 3.14 -- Untested, flagged as open question
- Exact T_world_from_camera rotation matrix -- Needs empirical validation against MuJoCo ground truth

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM -- orbslam3-python API verified but Python 3.14 wheels unavailable
- Architecture: HIGH -- follows verified ICPBackend pattern 1:1, all interfaces are known
- Pitfalls: HIGH -- well-documented from project's own PITFALLS.md + official GitHub issues
- Coordinate transform: LOW -- needs empirical validation
- MuJoCo textures: HIGH -- XML reference verified, existing scene already uses textures

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (orbslam3-python is stable; unlikely to release 3.14 wheels soon)
