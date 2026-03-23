# Phase 8: Backend Abstraction + ICP Wrap - Research

**Researched:** 2026-03-23
**Domain:** Python Protocol/ABC + Registry pattern for pluggable SLAM backends, FastAPI REST endpoints
**Confidence:** HIGH

## Summary

Phase 8 introduces a pluggable SLAM backend abstraction layer. The existing `SLAMPipeline` class (157 LOC) is the only SLAM implementation and must be wrapped -- not rewritten -- as the first backend. The abstraction requires four new components: `SLAMProtocol` (typing.Protocol defining the contract), `SLAMResult` (dataclass replacing the raw `np.ndarray` return), `SLAMRegistry` (decorator-based discovery with lazy loading), and `ICPBackend` (thin wrapper around existing `SLAMPipeline`).

The codebase has 14 call sites across 5 files that reference `SLAMPipeline` directly: `robot_instance.py` (type annotation + construction), `coordinator.py` (property access: `slam_poses`, `last_frame_cloud`, `get_cloud_points`, `get_cloud_colors`, `num_frames_processed`), `exploration_loop.py` (type annotation + `process_frame` + `last_frame_cloud`), and `main.py` (2 direct constructions in `run_explore_mode` and single-robot mode). All must migrate to `SLAMProtocol`. The REST API adds 4 new endpoints under `/api/slam/` using the existing FastAPI app.

**Primary recommendation:** Wrap `SLAMPipeline` inside `ICPBackend` without modifying `SLAMPipeline` at all. Define `SLAMProtocol` as a `typing.Protocol` (not ABC) to match the existing `BridgeProtocol` pattern in `sensor_types.py`. Use a decorator-based registry with lazy loading (import strings, not instances).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `process_frame(frame: SensorFrame) -> SLAMResult` replaces the current `-> np.ndarray` return
- `SLAMResult` is a dataclass with: `pose` (4x4 ndarray), `points` (Nx3 ndarray), `colors` (Nx3 ndarray), `metrics` (dict), `tracking_status` (TrackingStatus enum)
- `TrackingStatus` is a mandatory enum: `OK`, `LOST`, `INITIALIZING`, `RELOCALIZING`
- Each backend is responsible for producing its own per-frame cloud (not delegated to consumer)
- Full lifecycle protocol: `process_frame()`, `reset()`, `get_global_cloud()`, `get_poses()` all required
- Decorator pattern: `@slam_backend(name='icp', display='ICP Odometry')` on the class auto-registers on import
- Lazy-loading: Only the selected backend is imported. Registry stores class paths (strings), not instances
- Class-level attributes for metadata: each backend class has `CAPABILITIES: dict` and `PARAMETER_SCHEMA: dict`
- ICP as default: If no backend explicitly selected, fall back to ICP
- Full JSON Schema for parameter declarations
- Live-tunable where supported: Backend declares which params are live-tunable vs startup-only
- ICP exposes key params only: `voxel_size` and `max_cloud_points`
- In-process teardown+rebuild: Algorithm selection calls `Coordinator.reset_for_restart()`, recreates `RobotInstance` objects with the new backend. No process restart
- Endpoint structure nested under `/api/slam/`: GET backends, POST select, GET active, PATCH params
- Availability with install hints: Each backend shows `available: true/false` + reason string

### Claude's Discretion
- Exact decorator implementation details (metaclass vs simple function decorator)
- Error handling for backend crashes during process_frame
- Exact SLAMResult field naming and optional fields
- How to handle the transition from current `np.ndarray` return to `SLAMResult` in tests

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ABST-01 | System defines a SLAMProtocol interface with process_frame(rgb, depth, timestamp) -> SLAMResult(pose, points, metrics) | Protocol pattern from `BridgeProtocol` in sensor_types.py; SLAMResult dataclass design; full method surface from codebase grep (14 call sites) |
| ABST-02 | System provides a SLAMRegistry that discovers, lists, and instantiates available backends by name | Decorator-based registry pattern; lazy-loading via importlib; availability checking via try-import |
| ABST-03 | Each backend declares its parameters as a JSON schema (voxel_size, feature_count, etc.) | JSON Schema class attributes; live-tunable vs startup-only distinction; PATCH endpoint for param updates |
| ABST-04 | Each backend declares capabilities (supports_imu, outputs_dense, supports_loop_closure, supports_stereo) | CAPABILITIES dict as class attribute; used by GET /api/slam/backends response |
| ABST-05 | User can select a SLAM algorithm via REST API before starting a session, triggering system restart with the new backend | POST /api/slam/select triggers Coordinator.reset_for_restart(); existing restart mechanism in main.py _run_simulation_loop already handles teardown+rebuild |
| ABST-06 | Existing ICP-based SLAMPipeline is wrapped as the first backend with zero behavioral change | ICPBackend wraps SLAMPipeline without modification; SLAMResult constructed from existing return values; regression testing against v1.0 behavior |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python typing.Protocol | stdlib | SLAMProtocol interface definition | Already used for BridgeProtocol in this codebase; structural subtyping without inheritance |
| dataclasses | stdlib | SLAMResult, TrackingStatus | Already used throughout (SensorFrame, RobotInstance, CameraIntrinsics) |
| enum | stdlib | TrackingStatus enum | Standard Python enum for OK/LOST/INITIALIZING/RELOCALIZING |
| importlib | stdlib | Lazy backend loading from class path strings | Standard mechanism for deferred imports |
| FastAPI | >=0.100.0 | REST endpoints for /api/slam/* | Already in project dependencies (web optional dep) |
| Pydantic | 2.12.5 | Request/response models for REST API | Already installed; FastAPI's native validation layer |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| open3d | >=0.18.0 | ICP backend's underlying implementation | Already used by SLAMPipeline; stays internal to ICPBackend |
| numpy | >=1.26.0 | Array types in SLAMResult (pose, points, colors) | Already used everywhere |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| typing.Protocol | abc.ABC | ABC requires explicit inheritance; Protocol uses structural subtyping matching existing BridgeProtocol pattern |
| importlib lazy loading | Direct imports with try/except | Direct imports load all C++ bindings at startup; lazy loading defers until selection |
| Class-level CAPABILITIES dict | capabilities() method | Method requires instantiation to query; class attribute readable from registry without importing the backend |

**Installation:**
```bash
# No new dependencies needed -- all are stdlib or already installed
pip install -e ".[web,dev]"
```

## Architecture Patterns

### Recommended Project Structure
```
src/slam/
  protocol.py          # SLAMProtocol, SLAMResult, TrackingStatus
  registry.py          # SLAMRegistry, @slam_backend decorator
  slam_pipeline.py     # UNCHANGED -- existing ICP implementation
  depth_to_cloud.py    # UNCHANGED -- shared utility
  octomap_builder.py   # UNCHANGED
  backends/
    __init__.py        # Imports trigger decorator registration for built-in backends
    icp_backend.py     # ICPBackend wrapping SLAMPipeline
backend/web/
  slam_routes.py       # FastAPI router for /api/slam/* endpoints
  server.py            # Modified: include slam_routes router
```

### Pattern 1: SLAMProtocol (typing.Protocol)

**What:** Define the SLAM backend contract using `typing.Protocol` with `@runtime_checkable`.
**When to use:** This is the core interface -- all backends implement it, all consumers type-hint against it.
**Example:**
```python
# src/slam/protocol.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable
import numpy as np
from src.bridge.sensor_types import SensorFrame

class TrackingStatus(Enum):
    OK = "ok"
    LOST = "lost"
    INITIALIZING = "initializing"
    RELOCALIZING = "relocalizing"

@dataclass
class SLAMResult:
    pose: np.ndarray           # (4, 4) float64 homogeneous transform
    points: np.ndarray         # (N, 3) float64 frame cloud in world frame
    colors: np.ndarray         # (N, 3) float64 frame cloud colors
    metrics: dict              # backend-specific timing/quality metrics
    tracking_status: TrackingStatus = TrackingStatus.OK

@runtime_checkable
class SLAMProtocol(Protocol):
    """Contract for pluggable SLAM backends.

    All poses MUST be in MuJoCo world frame (z-up, right-handed).
    Mirrors BridgeProtocol pattern from sensor_types.py.
    """
    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def process_frame(self, frame: SensorFrame) -> SLAMResult: ...
    def reset(self) -> None: ...
    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]: ...
    def get_poses(self) -> list[np.ndarray]: ...
```

**Key design note:** The existing codebase accesses `slam.slam_poses`, `slam.last_frame_cloud`, `slam.get_cloud_points()`, `slam.get_cloud_colors()`, and `slam.num_frames_processed` through property access. The Protocol consolidates these:
- `slam_poses` / `get_poses()` -> `get_poses()` method
- `last_frame_cloud` / `last_frame_colors` -> returned inside `SLAMResult.points` / `SLAMResult.colors`
- `get_cloud_points()` / `get_cloud_colors()` -> `get_global_cloud()` returning `(points, colors)` tuple
- `num_frames_processed` -> can be a property on the protocol or derived from `len(get_poses())`

### Pattern 2: Decorator-Based Registry with Lazy Loading

**What:** A decorator that registers backend class paths (not instances) for deferred import.
**When to use:** Backend registration -- each backend module decorates its class.

```python
# src/slam/registry.py
import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

class SLAMRegistry:
    _backends: dict[str, dict] = {}  # name -> {class_path, display, ...}
    _default: str = "icp"

    @classmethod
    def register(cls, name: str, display: str, class_path: str) -> None:
        cls._backends[name] = {
            "class_path": class_path,
            "display": display,
        }

    @classmethod
    def list_backends(cls) -> list[dict]:
        result = []
        for name, info in cls._backends.items():
            backend_cls = cls._load_class(info["class_path"])
            available = backend_cls is not None
            entry = {
                "name": name,
                "display": info["display"],
                "available": available,
                "capabilities": getattr(backend_cls, "CAPABILITIES", {}) if available else {},
                "parameter_schema": getattr(backend_cls, "PARAMETER_SCHEMA", {}) if available else {},
            }
            if not available:
                entry["reason"] = f"Import failed for {info['class_path']}"
            result.append(entry)
        return result

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        info = cls._backends.get(name or cls._default)
        if info is None:
            raise ValueError(f"Unknown SLAM backend: {name}")
        backend_cls = cls._load_class(info["class_path"])
        if backend_cls is None:
            raise ImportError(f"Cannot load backend: {name}")
        return backend_cls(**kwargs)

    @classmethod
    def _load_class(cls, class_path: str) -> type | None:
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.debug("Backend unavailable: %s (%s)", class_path, e)
            return None

def slam_backend(name: str, display: str):
    """Decorator that registers a SLAM backend class."""
    def decorator(cls):
        class_path = f"{cls.__module__}.{cls.__qualname__}"
        SLAMRegistry.register(name, display, class_path)
        return cls
    return decorator
```

**Lazy loading detail:** The decorator runs at import time of the backend module, but only records the class path string. `_load_class()` performs the actual import only when `list_backends()` or `create()` is called. For `list_backends()`, the import is needed to read `CAPABILITIES` and `PARAMETER_SCHEMA` class attributes -- this is acceptable because listing is an infrequent operation. For `create()`, only the selected backend is fully instantiated.

**Built-in backend registration:** `src/slam/backends/__init__.py` imports `icp_backend` to trigger the decorator. Future backends (ORB-SLAM3, etc.) are imported conditionally or registered via entry points.

### Pattern 3: ICPBackend Wrapper (Adapter Pattern)

**What:** Thin adapter wrapping the existing `SLAMPipeline` without any modifications to it.
**When to use:** The ICP backend implementation.

```python
# src/slam/backends/icp_backend.py
from src.slam.registry import slam_backend
from src.slam.protocol import SLAMProtocol, SLAMResult, TrackingStatus
from src.slam.slam_pipeline import SLAMPipeline
from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
import numpy as np

@slam_backend(name="icp", display="ICP Odometry")
class ICPBackend:
    CAPABILITIES = {
        "supports_imu": False,
        "outputs_dense": True,
        "supports_loop_closure": False,
        "supports_stereo": False,
    }
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "voxel_size": {
                "type": "number", "default": 0.03,
                "minimum": 0.01, "maximum": 0.2,
                "description": "Voxel size for downsampling (meters)",
                "live_tunable": False,
            },
            "max_cloud_points": {
                "type": "integer", "default": 500000,
                "minimum": 10000, "maximum": 5000000,
                "description": "Maximum accumulated cloud points before aggressive downsampling",
                "live_tunable": False,
            },
        },
    }

    def __init__(self, intrinsics: CameraIntrinsics, voxel_size: float = 0.03):
        self._pipeline = SLAMPipeline(intrinsics, voxel_size=voxel_size)

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        pose = self._pipeline.process_frame(frame)
        return SLAMResult(
            pose=pose,
            points=self._pipeline.last_frame_cloud,
            colors=self._pipeline._last_frame_colors,
            metrics={"fitness": 1.0},  # ICP doesn't expose per-frame fitness currently
            tracking_status=TrackingStatus.OK,
        )

    def reset(self) -> None:
        self._pipeline.reset()

    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
        return self._pipeline.get_cloud_points(), self._pipeline.get_cloud_colors()

    def get_poses(self) -> list[np.ndarray]:
        return self._pipeline.slam_poses
```

### Pattern 4: REST API Router

**What:** FastAPI APIRouter for `/api/slam/` endpoints.
**When to use:** All SLAM backend discovery, selection, and parameter management.

```python
# backend/web/slam_routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.slam.registry import SLAMRegistry

router = APIRouter(prefix="/api/slam", tags=["slam"])

class SelectRequest(BaseModel):
    backend: str

class ParamPatch(BaseModel):
    params: dict

@router.get("/backends")
async def list_backends():
    return {"backends": SLAMRegistry.list_backends()}

@router.post("/select")
async def select_backend(req: SelectRequest, app_state=...):
    # Validate backend exists and is available
    # Trigger Coordinator.reset_for_restart() with new backend
    ...

@router.get("/active")
async def get_active():
    # Return current backend name + config
    ...

@router.patch("/params")
async def patch_params(patch: ParamPatch):
    # Update live-tunable params; return restart-required for startup-only
    ...
```

### Anti-Patterns to Avoid
- **Modifying SLAMPipeline directly:** The existing class MUST remain untouched. ICPBackend wraps it via delegation.
- **Importing all backends at startup:** Lazy loading is critical. Future C++ backends (ORB-SLAM3) import heavy bindings that should not load unless selected.
- **Using ABC instead of Protocol:** The codebase already uses `typing.Protocol` for `BridgeProtocol`. Stay consistent. Protocol enables structural subtyping -- backends don't need to explicitly inherit.
- **Putting registry state on instances:** The registry is a class-level singleton pattern (`_backends` is a class variable). Do not create registry instances.
- **Coupling REST endpoints to Coordinator internals:** The `/api/slam/select` endpoint should set a "pending backend" flag. The restart loop in `main.py:_run_simulation_loop` already handles teardown+rebuild -- extend it to pass the new backend name through.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema validation | Custom param validator | Pydantic model with JSON Schema export | Pydantic is already installed; JSON Schema validation is its core feature |
| REST request/response models | Raw dict parsing | Pydantic BaseModel | Type safety, automatic OpenAPI docs, validation |
| Module lazy loading | Custom import machinery | `importlib.import_module()` | Standard library, well-tested, handles edge cases |
| API router organization | All endpoints in server.py | FastAPI `APIRouter` | Clean separation, standard FastAPI pattern |

**Key insight:** This phase is pure Python architecture -- no new external dependencies needed. Everything is stdlib + already-installed FastAPI/Pydantic.

## Common Pitfalls

### Pitfall 1: Breaking Existing ICP Behavior During Abstraction
**What goes wrong:** The refactor from `process_frame() -> np.ndarray` to `-> SLAMResult` breaks 14 call sites across 5 files. If any call site still expects a raw ndarray, the system crashes.
**Why it happens:** The return type change is viral -- every consumer of `process_frame()` must be updated.
**How to avoid:**
1. Write characterization tests BEFORE refactoring: capture exact pose outputs for a 10-frame synthetic sequence
2. ICPBackend wraps SLAMPipeline without modifying it -- SLAMPipeline.process_frame() still returns ndarray internally
3. Update all 14 call sites in a single atomic change: `pose = slam.process_frame(frame)` becomes `result = slam.process_frame(frame); pose = result.pose`
4. The key consumer `ExplorationLoop._update_slam()` (line 198) accesses both `process_frame()` return AND `slam.last_frame_cloud` -- both are now in `SLAMResult`
**Warning signs:** Any test that compares `process_frame()` output to an ndarray will fail immediately.

### Pitfall 2: Coordinator Property Access Mismatch
**What goes wrong:** `Coordinator` accesses SLAM through property chains: `robot.slam.slam_poses[-1][:3, 3]`, `robot.slam.last_frame_cloud`, `robot.slam.num_frames_processed`. These are properties on `SLAMPipeline` but the Protocol uses methods (`get_poses()`, `get_global_cloud()`).
**Why it happens:** Protocol methods and SLAMPipeline properties have different access patterns.
**How to avoid:** Either (a) add property equivalents to the Protocol, or (b) update Coordinator to use method calls. Option (b) is cleaner but touches more code. Recommend: keep backward-compatible properties on ICPBackend that delegate to the wrapped SLAMPipeline, AND update the Protocol to include them. The Protocol can define properties if needed:
```python
class SLAMProtocol(Protocol):
    @property
    def num_frames_processed(self) -> int: ...
```
**Warning signs:** `AttributeError: 'ICPBackend' object has no attribute 'slam_poses'` at runtime.

### Pitfall 3: Restart Flow Race Condition
**What goes wrong:** POST `/api/slam/select` triggers `Coordinator.reset_for_restart()` from the FastAPI async thread, but the simulation runs in a background thread (`_run_simulation_loop`). If both access `self._robots` simultaneously, dict mutation during iteration causes `RuntimeError: dictionary changed size during iteration`.
**Why it happens:** The existing restart mechanism in `main.py` uses a `_restart_lock` and a `_restart_requested` flag, but the new REST endpoint must integrate with this existing pattern, not bypass it.
**How to avoid:** POST `/api/slam/select` should ONLY set `coordinator._restart_requested = True` and store the selected backend name. The existing `_run_simulation_loop` in main.py already checks `coordinator.restart_requested` and performs teardown+rebuild inside the lock. Extend this to read the pending backend name and pass it to `RobotInstance.create()`.
**Warning signs:** Sporadic crashes on algorithm switch; works in testing but fails under load.

### Pitfall 4: SLAMResult.points Ownership Semantics
**What goes wrong:** `SLAMPipeline.last_frame_cloud` returns a reference to an internal array that gets overwritten on the next frame. If `SLAMResult.points` stores this reference (not a copy), downstream consumers reading from a previous result get corrupted data.
**Why it happens:** The existing code in `SLAMPipeline` does `.copy()` on `last_frame_cloud` (line 105), but `_last_frame_colors` access may not always copy.
**How to avoid:** ICPBackend must ensure `SLAMResult.points` and `SLAMResult.colors` are owned copies, not views into mutable internal state. The existing `.copy()` in SLAMPipeline line 105-106 handles this for the frame cloud, but verify colors are also copied.
**Warning signs:** Visualization shows garbage/repeated point clouds; data corruption that only appears at high frame rates.

## Code Examples

### Consumer Migration: ExplorationLoop._update_slam()

Before (current):
```python
def _update_slam(self, frame: SensorFrame) -> tuple[np.ndarray, np.ndarray]:
    pose = self._slam.process_frame(frame)
    current_pos = pose[:3, 3].copy()
    frame_cloud = self._slam.last_frame_cloud
    if len(frame_cloud) > 0:
        self._octomap.insert_scan(frame_cloud, current_pos)
    self._robot_positions.append(current_pos)
    return pose, current_pos
```

After (with SLAMProtocol):
```python
def _update_slam(self, frame: SensorFrame) -> tuple[np.ndarray, np.ndarray]:
    result = self._slam.process_frame(frame)
    pose = result.pose
    current_pos = pose[:3, 3].copy()
    if len(result.points) > 0:
        self._octomap.insert_scan(result.points, current_pos)
    self._robot_positions.append(current_pos)
    return pose, current_pos
```

### Consumer Migration: RobotInstance

Before:
```python
@dataclass
class RobotInstance:
    slam: SLAMPipeline
    ...
    def get_pose(self) -> np.ndarray:
        if self.slam.slam_poses:
            return self.slam.slam_poses[-1]
        return np.eye(4, dtype=np.float64)

    def get_cloud_data(self) -> tuple[np.ndarray, np.ndarray]:
        return self.slam.get_cloud_points(), self.slam.get_cloud_colors()
```

After:
```python
@dataclass
class RobotInstance:
    slam: SLAMProtocol  # Type change: SLAMPipeline -> SLAMProtocol
    ...
    def get_pose(self) -> np.ndarray:
        poses = self.slam.get_poses()
        if poses:
            return poses[-1]
        return np.eye(4, dtype=np.float64)

    def get_cloud_data(self) -> tuple[np.ndarray, np.ndarray]:
        return self.slam.get_global_cloud()
```

### Consumer Migration: RobotInstance.create() Factory

Before:
```python
@classmethod
def create(cls, robot_id, bridge, intrinsics, config=None, spawn_position=(0,0,0.3)):
    slam = SLAMPipeline(intrinsics)
    ...
```

After:
```python
@classmethod
def create(cls, robot_id, bridge, intrinsics, config=None, spawn_position=(0,0,0.3),
           backend_name: str | None = None):
    slam = SLAMRegistry.create(backend_name or "icp", intrinsics=intrinsics)
    ...
```

### Backend Discovery Endpoint Response Format

```json
{
  "backends": [
    {
      "name": "icp",
      "display": "ICP Odometry",
      "available": true,
      "capabilities": {
        "supports_imu": false,
        "outputs_dense": true,
        "supports_loop_closure": false,
        "supports_stereo": false
      },
      "parameter_schema": {
        "type": "object",
        "properties": {
          "voxel_size": {"type": "number", "default": 0.03, "minimum": 0.01, "maximum": 0.2, "description": "...", "live_tunable": false},
          "max_cloud_points": {"type": "integer", "default": 500000, "minimum": 10000, "maximum": 5000000, "description": "...", "live_tunable": false}
        }
      }
    },
    {
      "name": "orbslam3",
      "display": "ORB-SLAM3",
      "available": false,
      "reason": "orbslam3-python not installed",
      "capabilities": {},
      "parameter_schema": {}
    }
  ]
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `SLAMPipeline.process_frame() -> np.ndarray` | `SLAMProtocol.process_frame() -> SLAMResult` | This phase | All consumers must handle SLAMResult instead of raw pose |
| Direct `SLAMPipeline(intrinsics)` construction | `SLAMRegistry.create("icp", intrinsics=intrinsics)` | This phase | All construction goes through registry |
| `robot.slam.slam_poses` property access | `robot.slam.get_poses()` method | This phase | Coordinator and viz code updated |
| `robot.slam.last_frame_cloud` property | Returned in SLAMResult.points | This phase | ExplorationLoop reads from result, not slam object |
| No REST API for SLAM | `/api/slam/` endpoint group | This phase | Frontend can discover and select backends |

## Open Questions

1. **num_frames_processed in Protocol**
   - What we know: Coordinator and main.py access `slam.num_frames_processed` for logging/stats
   - What's unclear: Whether to include it in Protocol or derive from `len(get_poses())`
   - Recommendation: Add as property in Protocol for simplicity; ICPBackend delegates to `SLAMPipeline.num_frames_processed`

2. **Error handling for backend crashes**
   - What we know: CONTEXT.md lists this as Claude's discretion
   - What's unclear: Should process_frame catch exceptions and return a "LOST" SLAMResult, or propagate?
   - Recommendation: Catch exceptions in process_frame, return SLAMResult with TrackingStatus.LOST and the previous pose. Log the error. This prevents a single bad frame from crashing the simulation loop.

3. **Active backend state storage**
   - What we know: The REST API needs GET /api/slam/active to return current backend
   - What's unclear: Where to persist the active backend name (Coordinator? app.state? Registry?)
   - Recommendation: Store on `app.state.active_slam_backend` (string name) alongside existing app.state fields. Coordinator reads this on restart.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 (dev dependency) |
| Config file | None -- uses default pytest discovery |
| Quick run command | `python -m pytest tests/slam/ -x -q` |
| Full suite command | `python -m pytest tests/ -x -q --timeout=30` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ABST-01 | SLAMProtocol interface defined; process_frame returns SLAMResult | unit | `python -m pytest tests/slam/test_protocol.py -x` | Wave 0 |
| ABST-02 | SLAMRegistry discovers, lists, instantiates backends | unit | `python -m pytest tests/slam/test_registry.py -x` | Wave 0 |
| ABST-03 | Backend declares JSON Schema parameters | unit | `python -m pytest tests/slam/test_registry.py::test_parameter_schema -x` | Wave 0 |
| ABST-04 | Backend declares capabilities dict | unit | `python -m pytest tests/slam/test_registry.py::test_capabilities -x` | Wave 0 |
| ABST-05 | REST select triggers restart with new backend | integration | `python -m pytest tests/web/test_slam_routes.py -x` | Wave 0 |
| ABST-06 | ICP backend wraps SLAMPipeline with zero regression | unit + regression | `python -m pytest tests/slam/test_icp_backend.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/slam/ tests/web/test_slam_routes.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/slam/test_protocol.py` -- covers ABST-01: SLAMResult construction, TrackingStatus enum, Protocol structural check
- [ ] `tests/slam/test_registry.py` -- covers ABST-02, ABST-03, ABST-04: register, list, create, param schema, capabilities
- [ ] `tests/slam/test_icp_backend.py` -- covers ABST-06: ICPBackend wraps SLAMPipeline, process_frame returns SLAMResult, regression vs raw SLAMPipeline
- [ ] `tests/web/test_slam_routes.py` -- covers ABST-05: GET /api/slam/backends, POST /api/slam/select, GET /api/slam/active, PATCH /api/slam/params
- [ ] Update `tests/slam/test_slam_pipeline.py` -- existing tests still pass (SLAMPipeline unchanged)
- [ ] Update `tests/coordination/test_coordinator.py` -- adapt for SLAMProtocol type change
- [ ] Update `tests/exploration/test_exploration_loop.py` -- adapt mock from ndarray return to SLAMResult

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `src/slam/slam_pipeline.py`, `src/coordination/robot_instance.py`, `src/coordination/coordinator.py`, `src/exploration/exploration_loop.py`, `src/main.py`, `src/bridge/sensor_types.py`, `backend/web/server.py`
- `.planning/research/ARCHITECTURE.md` -- v2.0 architecture design with data flow diagrams
- `.planning/research/PITFALLS.md` -- 13 pitfalls covering abstraction design
- `.planning/research/FEATURES.md` -- Feature landscape for pluggable SLAM API

### Secondary (MEDIUM confidence)
- `.planning/phases/08-backend-abstraction-icp-wrap/08-CONTEXT.md` -- User decisions constraining implementation

### Tertiary (LOW confidence)
- None -- all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib or already-installed packages; no new dependencies
- Architecture: HIGH -- based on direct codebase analysis of all 14 call sites and existing patterns (BridgeProtocol, dataclass-heavy design)
- Pitfalls: HIGH -- identified from direct code reading (race condition in restart, property vs method mismatch, ownership semantics)

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable -- pure Python architecture, no external API dependencies)
