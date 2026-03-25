# Phase 10: Pose-Graph Map Merger - Research

**Researched:** 2026-03-23
**Domain:** Pose-graph optimization for multi-robot map merging
**Confidence:** HIGH

## Summary

This phase replaces the naive ICP union merge with a pluggable merge strategy system supporting three backends: ICP union (existing baseline), Open3D pose-graph optimization (PGO), and GTSAM incremental PGO (iSAM2). The architecture mirrors the existing SLAM backend registry pattern exactly -- decorator-based registration, lazy loading, JSON Schema parameters, and REST API endpoints.

Open3D (already a dependency at >=0.18.0) provides `PoseGraph`, `PoseGraphNode`, `PoseGraphEdge`, `GlobalOptimizationLevenbergMarquardt`, and `registration_icp` -- all the building blocks for a full PGO merge strategy without additional dependencies. GTSAM provides `ISAM2` for incremental optimization via `BetweenFactorPose3` and `PriorFactorPose3` with 6D noise models, available on PyPI as an optional dependency.

The existing `MapMerger` class (150 LOC) wraps cleanly as the ICP union baseline strategy. The Coordinator integration requires changing `_merger` type from `MapMerger` to `MergeProtocol`, passing richer `RobotMapData` instead of raw voxel arrays, and accumulating per-robot pose history for PGO strategies to consume.

**Primary recommendation:** Mirror the Phase 8 SLAM backend pattern exactly (protocol, registry, decorator, routes) for merge strategies, with Open3D PGO as the primary new capability and GTSAM as an optional advanced backend.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Registry pattern** matching Phase 8 SLAM backends: `@merge_strategy(name='pgo_open3d', display='Open3D Pose-Graph')` decorator auto-registers on import
- Strategies are classes implementing `MergeProtocol` with a `merge()` method
- Each strategy declares `PARAMETER_SCHEMA` (JSON Schema) and `CAPABILITIES` dict -- same pattern as SLAM backends
- Lazy-loading: only the selected strategy is imported. Registry stores class paths as strings.
- Extend existing `/api/slam/` namespace with merge-strategy endpoints: `GET /api/slam/merge-strategies`, `POST /api/slam/merge-strategy`, `GET /api/slam/merge-strategy`, `PATCH /api/slam/merge-params`
- Strategy change triggers same `Coordinator.reset_for_restart()` flow
- **Geometric ICP matching** on overlapping point cloud regions for loop closure detection
- Loop closure checks run every N merge cycles to amortize cost
- On ICP failure: fall back to known spawn transforms from MuJoCo config
- **Both Open3D PGO and GTSAM** as separate merge strategies
- Open3D PGO: full graph optimization each cycle
- GTSAM: incremental optimization (iSAM2)
- **GTSAM is optional dependency** with try-import availability check
- **MergeResult dataclass**: `merged_voxels`, `merged_cloud`, `optimized_poses`, `metrics`
- **Input contract**: `Dict[robot_id, RobotMapData]` where `RobotMapData` contains: `poses`, `frame_clouds`, `current_voxels`
- PGO strategies re-project raw clouds using optimized poses then union-merge
- All strategies produce `last_merged_voxels` and `last_merged_cloud`

### Claude's Discretion
- Exact MergeProtocol method signatures beyond `merge()`
- ICP registration parameters (max correspondence distance, fitness threshold for loop closure acceptance)
- How `RobotMapData` accumulates frame clouds (buffer size, decimation)
- GTSAM factor graph structure (noise models, prior factors)
- Open3D PoseGraph edge/node construction details
- Exact N for "every N merge cycles" loop closure check frequency

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MERG-01 | System supports pluggable merge strategies: ICP union (existing), Open3D PGO, and GTSAM incremental PGO | Registry pattern mirrors SLAMRegistry; MergeProtocol mirrors SLAMProtocol; three strategy implementations |
| MERG-02 | User can select merge strategy from frontend alongside SLAM algorithm selection | REST API endpoints extend `/api/slam/` namespace; frontend selector is Phase 9 scope (CTRL-02), this phase provides the backend API |
| MERG-03 | Pose-graph merger accepts inter-robot loop closure constraints for globally consistent maps | Open3D `registration_icp` for loop closure detection; PoseGraph with `uncertain=True` edges for loop closures; GTSAM `BetweenFactorPose3` for inter-robot constraints |
| MERG-04 | Merged map output is API-compatible with existing visualization pipeline | MergeResult provides `last_merged_voxels` and `last_merged_cloud` properties; `streaming_viz.py` reads these unchanged |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| open3d | >=0.18.0 (current: 0.19.0) | PoseGraph, registration_icp, GlobalOptimization, PointCloud | Already a project dependency; has built-in PGO and ICP registration |
| gtsam | 4.2 (stable) / 4.3a0 (pre-release) | ISAM2 incremental pose-graph optimization | Standard robotics PGO library; pip-installable; optional dependency |
| numpy | >=1.26.0 | Array operations, pose transforms | Already a project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy | >=1.15.0 | spatial.transform.Rotation for conversion utilities | Already in deps; use for Rot3 conversions if needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GTSAM | g2o-python | g2o has worse Python bindings and less active maintenance |
| Open3D PGO | Custom least-squares | Open3D PGO is battle-tested; custom is error-prone |

**Installation (GTSAM optional):**
```bash
pip install gtsam  # optional: enables GTSAM iSAM2 merge strategy
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  coordination/
    merge_protocol.py       # MergeProtocol, MergeResult, RobotMapData
    merge_registry.py       # MergeRegistry + @merge_strategy decorator
    merge_strategies/
      __init__.py            # Imports all strategies to trigger registration
      icp_union.py           # Wraps existing MapMerger as baseline
      pgo_open3d.py          # Open3D PoseGraph optimization
      pgo_gtsam.py           # GTSAM iSAM2 (optional dep)
    map_merger.py            # Existing MapMerger (kept as implementation detail)
    coordinator.py           # Updated to use MergeProtocol
backend/
  web/
    slam_routes.py           # Extended with merge-strategy endpoints
```

### Pattern 1: MergeProtocol (mirrors SLAMProtocol)
**What:** Runtime-checkable Protocol defining the merge strategy interface
**When to use:** Every merge strategy must implement this
**Example:**
```python
# Source: mirrors src/slam/protocol.py pattern
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
import numpy as np
import open3d as o3d


@dataclass
class RobotMapData:
    """Per-robot input to merge strategies."""
    robot_id: str
    poses: list[np.ndarray]          # List of (4,4) transforms
    frame_clouds: list[np.ndarray]   # List of (N,3) point arrays per frame
    current_voxels: np.ndarray       # (M,3) current occupied voxels


@dataclass
class MergeResult:
    """Standard return type from MergeProtocol.merge()."""
    merged_voxels: np.ndarray          # (N,3) float64
    merged_cloud: o3d.geometry.PointCloud
    optimized_poses: dict[str, list[np.ndarray]]  # robot_id -> list of 4x4
    metrics: dict = field(default_factory=dict)


@runtime_checkable
class MergeProtocol(Protocol):
    """Interface that all merge strategies must implement."""
    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
        """Merge maps from multiple robots."""
        ...

    def reset(self) -> None:
        """Clear accumulated state."""
        ...

    @property
    def last_merged_voxels(self) -> np.ndarray: ...

    @property
    def last_merged_cloud(self) -> o3d.geometry.PointCloud: ...
```

### Pattern 2: MergeRegistry (mirrors SLAMRegistry)
**What:** Decorator-based registry with lazy loading
**When to use:** Auto-discovers merge strategies
**Example:**
```python
# Source: mirrors src/slam/registry.py pattern
class MergeRegistry:
    _strategies: dict[str, dict] = {}
    _default: str = "icp_union"

    @classmethod
    def register(cls, name: str, display: str, class_path: str) -> None:
        cls._strategies[name] = {"class_path": class_path, "display": display}

    @classmethod
    def list_strategies(cls) -> list[dict]: ...

    @classmethod
    def create(cls, name: str | None = None, **kwargs) -> Any: ...


def merge_strategy(name: str, display: str):
    """Decorator to register a merge strategy."""
    def decorator(klass):
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        MergeRegistry.register(name, display, class_path)
        return klass
    return decorator
```

### Pattern 3: Open3D PGO Strategy
**What:** Full pose-graph optimization using Open3D built-ins
**When to use:** Default PGO strategy (always available since Open3D is a dep)
**Example:**
```python
# Source: Open3D multiway registration tutorial
import open3d as o3d
import numpy as np

def build_pose_graph(
    robot_data: dict[str, RobotMapData],
    max_corr_distance: float = 0.15,
) -> o3d.pipelines.registration.PoseGraph:
    pose_graph = o3d.pipelines.registration.PoseGraph()
    node_id = 0
    robot_node_ranges = {}  # robot_id -> (start_node, end_node)

    for robot_id, data in robot_data.items():
        start = node_id
        for i, pose in enumerate(data.poses):
            pose_graph.nodes.append(
                o3d.pipelines.registration.PoseGraphNode(pose)
            )
            # Odometry edge (consecutive poses)
            if i > 0:
                relative = np.linalg.inv(data.poses[i-1]) @ pose
                cloud_src = o3d.geometry.PointCloud()
                cloud_src.points = o3d.utility.Vector3dVector(data.frame_clouds[i-1])
                cloud_tgt = o3d.geometry.PointCloud()
                cloud_tgt.points = o3d.utility.Vector3dVector(data.frame_clouds[i])
                info = o3d.pipelines.registration.get_information_matrix_from_point_clouds(
                    cloud_src, cloud_tgt, max_corr_distance, relative
                )
                pose_graph.edges.append(
                    o3d.pipelines.registration.PoseGraphEdge(
                        node_id - 1, node_id, relative, info, uncertain=False
                    )
                )
            node_id += 1
        robot_node_ranges[robot_id] = (start, node_id - 1)

    # Inter-robot loop closure edges (uncertain=True)
    # Use registration_icp on overlapping regions
    return pose_graph


def optimize_pose_graph(pose_graph):
    option = o3d.pipelines.registration.GlobalOptimizationOption(
        max_correspondence_distance=0.15,
        edge_prune_threshold=0.25,
        reference_node=0,
    )
    o3d.pipelines.registration.global_optimization(
        pose_graph,
        o3d.pipelines.registration.GlobalOptimizationLevenbergMarquardt(),
        o3d.pipelines.registration.GlobalOptimizationConvergenceCriteria(),
        option,
    )
```

### Pattern 4: GTSAM iSAM2 Strategy
**What:** Incremental pose-graph optimization using GTSAM
**When to use:** When GTSAM is installed; provides incremental updates without re-solving
**Example:**
```python
# Source: GTSAM Pose3ISAM2Example.py
import gtsam
import numpy as np

# Noise models for 3D poses (6D: rx, ry, rz, tx, ty, tz)
PRIOR_NOISE = gtsam.noiseModel.Diagonal.Sigmas(np.array([
    0.01, 0.01, 0.01,   # rotation sigmas (radians)
    0.05, 0.05, 0.05,   # translation sigmas (meters)
]))
ODOM_NOISE = gtsam.noiseModel.Diagonal.Sigmas(np.array([
    0.05, 0.05, 0.05,   # rotation
    0.1, 0.1, 0.1,      # translation
]))
LOOP_CLOSURE_NOISE = gtsam.noiseModel.Diagonal.Sigmas(np.array([
    0.1, 0.1, 0.1,      # rotation (less certain)
    0.2, 0.2, 0.2,      # translation (less certain)
]))

# Convert 4x4 numpy to gtsam.Pose3
def numpy_to_pose3(mat: np.ndarray) -> gtsam.Pose3:
    return gtsam.Pose3(mat)

# iSAM2 setup
params = gtsam.ISAM2Params()
params.setRelinearizeThreshold(0.1)
params.relinearizeSkip = 1
isam = gtsam.ISAM2(params)

# Incremental update
graph = gtsam.NonlinearFactorGraph()
initial = gtsam.Values()
# Add prior on first node
graph.push_back(gtsam.PriorFactorPose3(1, numpy_to_pose3(first_pose), PRIOR_NOISE))
initial.insert(1, numpy_to_pose3(first_pose))
# Add odometry factors
graph.push_back(gtsam.BetweenFactorPose3(i, i+1, relative_pose, ODOM_NOISE))
# Add loop closure factors
graph.push_back(gtsam.BetweenFactorPose3(node_a, node_b, relative_pose, LOOP_CLOSURE_NOISE))
# Update
isam.update(graph, initial)
result = isam.calculateEstimate()
# Clear for next incremental batch
graph = gtsam.NonlinearFactorGraph()
initial = gtsam.Values()
```

### Pattern 5: Loop Closure via ICP
**What:** Detect inter-robot overlapping regions using ICP registration
**When to use:** Every N merge cycles, between robots' latest point clouds
**Example:**
```python
# Source: Open3D registration_icp docs
def detect_loop_closure(
    cloud_a: o3d.geometry.PointCloud,
    cloud_b: o3d.geometry.PointCloud,
    max_correspondence_distance: float = 0.3,
    fitness_threshold: float = 0.3,
) -> tuple[bool, np.ndarray, float]:
    """Attempt ICP alignment between two clouds.

    Returns (success, transform_4x4, fitness_score).
    """
    result = o3d.pipelines.registration.registration_icp(
        cloud_a, cloud_b,
        max_correspondence_distance,
        np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )
    success = result.fitness >= fitness_threshold
    return success, result.transformation, result.fitness
```

### Anti-Patterns to Avoid
- **Building custom graph optimizer:** Open3D and GTSAM both provide battle-tested PGO. Do not implement Levenberg-Marquardt or Gauss-Newton manually.
- **Running loop closure every merge cycle:** ICP on full clouds is expensive. Amortize by checking every N cycles (recommended: N=5).
- **Mutating the existing MapMerger:** Wrap it as a strategy instead; keep the original class as the internal implementation of `icp_union`.
- **Tight coupling between Coordinator and strategy internals:** Coordinator should only call `merge()` and read `last_merged_voxels`/`last_merged_cloud`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pose-graph optimization | Custom least-squares solver | Open3D `global_optimization` / GTSAM `ISAM2` | Convergence, numerical stability, edge pruning |
| Point cloud registration | Custom nearest-neighbor matching | Open3D `registration_icp` | KD-tree acceleration, robust estimation methods |
| Information matrix computation | Manual Hessian approximation | Open3D `get_information_matrix_from_point_clouds` | Correctly weights edges by alignment quality |
| 3D rotation handling | Manual Euler/matrix conversion | GTSAM `Pose3(matrix)` / `Rot3` | Gimbal lock, quaternion normalization |
| Registry with lazy loading | Custom importlib boilerplate | Copy `SLAMRegistry` pattern | Already proven in Phase 8 |

**Key insight:** The entire PGO pipeline is available through Open3D's `pipelines.registration` module. GTSAM adds incremental optimization but is not required for correctness -- Open3D PGO on simulation-scale graphs (tens to hundreds of nodes) runs fast enough with full re-optimization.

## Common Pitfalls

### Pitfall 1: Empty or Degenerate Point Clouds in ICP
**What goes wrong:** `registration_icp` returns garbage transformation when clouds have zero or very few points
**Why it happens:** Early in exploration, robots have sparse maps; ICP needs sufficient overlap
**How to avoid:** Check `len(cloud.points) >= MIN_POINTS` (e.g., 50) before running ICP. Return identity transform with zero fitness on failure.
**Warning signs:** `result.fitness == 0.0` or `result.fitness` below threshold

### Pitfall 2: Node ID Collision in Multi-Robot Pose Graph
**What goes wrong:** Two robots both start node IDs at 0, causing graph corruption
**Why it happens:** Naive sequential numbering per robot
**How to avoid:** Use offset ranges per robot (e.g., robot_a: 0-999, robot_b: 1000-1999) or prefix-based keys. For GTSAM, use `gtsam.symbol('a', frame_idx)` to generate unique keys.
**Warning signs:** Pose graph has fewer nodes than expected; optimization produces NaN

### Pitfall 3: GTSAM Noise Model Dimension Mismatch
**What goes wrong:** `noiseModel.Diagonal.Sigmas` expects 6D for Pose3 (3 rotation + 3 translation), not 3D
**Why it happens:** Confusing Pose2 (3D noise) with Pose3 (6D noise)
**How to avoid:** Always use 6-element sigma arrays for Pose3: `[rx, ry, rz, tx, ty, tz]`
**Warning signs:** Runtime error about dimension mismatch in factor construction

### Pitfall 4: Frame Cloud Memory Explosion
**What goes wrong:** Storing every frame's point cloud per robot consumes gigabytes
**Why it happens:** Each frame produces ~50K-500K points; hundreds of frames per robot
**How to avoid:** Decimate frame clouds (voxel downsample to ~0.05m before storing). Only keep last N frames in a circular buffer. Use `RobotMapData.frame_clouds` as a sliding window.
**Warning signs:** Memory usage growing linearly with step count

### Pitfall 5: Coordinator Type Change Breaking Visualization
**What goes wrong:** `streaming_viz.py` reads `merger.last_merged_voxels` -- if MergeProtocol drops this property, viz breaks
**Why it happens:** Protocol change without maintaining the property interface
**How to avoid:** MergeProtocol must define `last_merged_voxels` and `last_merged_cloud` as properties. Each strategy must update these after `merge()`.
**Warning signs:** Frontend shows empty map after merge strategy switch

### Pitfall 6: ICP Loop Closure Producing Wrong Transform Direction
**What goes wrong:** Transform goes A->B but edge expects B->A, producing divergent optimization
**Why it happens:** Open3D `registration_icp(source, target)` returns transform that maps source to target
**How to avoid:** Be consistent: if edge connects node_a to node_b, transform should map a's cloud into b's frame. Document the convention explicitly.
**Warning signs:** Optimized poses flip or diverge; map "explodes"

## Code Examples

### ICP Union Strategy (wrapping existing MapMerger)
```python
# Source: project pattern from src/slam/backends/icp_backend.py
from src.coordination.merge_registry import merge_strategy
from src.coordination.merge_protocol import MergeProtocol, MergeResult, RobotMapData
from src.coordination.map_merger import MapMerger

@merge_strategy(name="icp_union", display="ICP Union (Baseline)")
class ICPUnionStrategy:
    CAPABILITIES = {"supports_loop_closure": False, "incremental": False}
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "resolution": {
                "type": "number", "default": 0.1,
                "minimum": 0.01, "maximum": 0.5,
                "description": "Voxel resolution for deduplication (meters)",
                "live_tunable": False,
            },
        },
    }

    def __init__(self, resolution: float = 0.1):
        self._merger = MapMerger(resolution=resolution)

    def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
        all_voxels = [d.current_voxels for d in robot_data.values() if len(d.current_voxels) > 0]
        if len(all_voxels) >= 2:
            combined = np.vstack(all_voxels)
            self._merger.merge_from_voxels(all_voxels[0], combined[len(all_voxels[0]):])
        elif len(all_voxels) == 1:
            self._merger.last_merged_voxels = all_voxels[0]
        return MergeResult(
            merged_voxels=self._merger.last_merged_voxels,
            merged_cloud=self._merger.last_merged_cloud,
            optimized_poses={rid: d.poses for rid, d in robot_data.items()},
            metrics={"strategy": "icp_union"},
        )

    def reset(self) -> None:
        self._merger.last_merged_voxels = np.empty((0, 3))

    @property
    def last_merged_voxels(self) -> np.ndarray:
        return self._merger.last_merged_voxels

    @property
    def last_merged_cloud(self):
        return self._merger.last_merged_cloud
```

### REST API Extension Pattern
```python
# Source: mirrors backend/web/slam_routes.py pattern
from src.coordination.merge_registry import MergeRegistry

class MergeSelectRequest(BaseModel):
    strategy: str

@router.get("/merge-strategies")
async def list_merge_strategies():
    return {"strategies": MergeRegistry.list_strategies()}

@router.post("/merge-strategy")
async def select_merge_strategy(req: MergeSelectRequest, request: Request):
    strategies = {s["name"]: s for s in MergeRegistry.list_strategies()}
    if req.strategy not in strategies:
        raise HTTPException(status_code=404, detail=f"Unknown strategy: {req.strategy}")
    if not strategies[req.strategy]["available"]:
        raise HTTPException(status_code=400, detail="Strategy unavailable")
    request.app.state.pending_merge_strategy = req.strategy
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting", "strategy": req.strategy}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Naive voxel union merge | Pose-graph optimization | Standard since ORB-SLAM2 (2017) | Globally consistent maps instead of drifting unions |
| Full batch PGO every cycle | Incremental iSAM2 | GTSAM 4.0+ (2019) | O(affected nodes) instead of O(all nodes) per update |
| Manual loop closure | Geometric ICP-based detection | Open3D 0.10+ (2020) | Automated inter-robot constraint discovery |

**Deprecated/outdated:**
- Open3D `open3d.registration.*` (old module path): Use `open3d.pipelines.registration.*` instead (changed in Open3D 0.13)

## Open Questions

1. **Frame cloud buffer size**
   - What we know: Must balance memory vs PGO quality. More frames = better graph but more memory.
   - What's unclear: Optimal buffer size for simulation-scale exploration
   - Recommendation: Start with last 50 frames per robot with 0.05m voxel downsample. Make configurable via PARAMETER_SCHEMA.

2. **GTSAM key strategy for multi-robot**
   - What we know: GTSAM `gtsam.symbol(char, index)` creates unique int keys from a character + index
   - What's unclear: Whether to use character-based keys ('a','b') or offset ranges
   - Recommendation: Use `gtsam.symbol(ord(robot_id[-1]), frame_idx)` -- maps robot_a->97, robot_b->98 etc.

3. **Loop closure check frequency**
   - What we know: Every merge cycle is too expensive; amortization needed
   - What's unclear: Optimal N for "every N merge cycles"
   - Recommendation: Default N=5, expose as `loop_closure_interval` in PARAMETER_SCHEMA

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 with pytest-timeout |
| Config file | pytest.ini |
| Quick run command | `python -m pytest tests/coordination/ -x -q --timeout=30` |
| Full suite command | `python -m pytest tests/ -x -q --timeout=30` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MERG-01 | MergeRegistry discovers and creates all 3 strategies | unit | `python -m pytest tests/coordination/test_merge_registry.py -x` | Wave 0 |
| MERG-01 | Each strategy produces valid MergeResult from RobotMapData input | unit | `python -m pytest tests/coordination/test_merge_strategies.py -x` | Wave 0 |
| MERG-02 | REST API lists/selects/queries merge strategies | unit | `python -m pytest tests/web/test_merge_routes.py -x` | Wave 0 |
| MERG-03 | PGO strategies detect and use loop closure constraints | unit | `python -m pytest tests/coordination/test_merge_strategies.py::TestPGOLoopClosure -x` | Wave 0 |
| MERG-03 | Loop closure falls back to spawn transforms on ICP failure | unit | `python -m pytest tests/coordination/test_merge_strategies.py::TestLoopClosureFallback -x` | Wave 0 |
| MERG-04 | MergeResult populates last_merged_voxels and last_merged_cloud | unit | `python -m pytest tests/coordination/test_merge_strategies.py::TestMergeOutputCompat -x` | Wave 0 |
| MERG-04 | Coordinator uses MergeProtocol without breaking viz pipeline | unit | `python -m pytest tests/coordination/test_coordinator.py -x` | Exists (update needed) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/coordination/ -x -q --timeout=30`
- **Per wave merge:** `python -m pytest tests/ -x -q --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/coordination/test_merge_registry.py` -- covers MERG-01 registry
- [ ] `tests/coordination/test_merge_strategies.py` -- covers MERG-01, MERG-03, MERG-04
- [ ] `tests/web/test_merge_routes.py` -- covers MERG-02
- [ ] Update `tests/coordination/test_coordinator.py` -- verify MergeProtocol integration

## Sources

### Primary (HIGH confidence)
- Open3D 0.19.0 docs: [Multiway registration tutorial](https://www.open3d.org/docs/release/tutorial/pipelines/multiway_registration.html) -- PoseGraph construction, GlobalOptimization, information matrix
- Open3D 0.19.0 docs: [PoseGraph API](https://www.open3d.org/docs/release/python_api/open3d.pipelines.registration.PoseGraph.html) -- PoseGraphNode, PoseGraphEdge constructors
- Open3D 0.19.0 docs: [GlobalOptimizationLevenbergMarquardt](https://www.open3d.org/docs/release/python_api/open3d.pipelines.registration.GlobalOptimizationLevenbergMarquardt.html)
- GTSAM docs: [Pose3ISAM2Example.py](http://docs.ros.org/en/melodic/api/gtsam/html/Pose3ISAM2Example_8py_source.html) -- iSAM2 with Pose3, BetweenFactorPose3, noise models
- GTSAM by Example: [Pose2 iSAM2](https://gtbook.github.io/gtsam-examples/Pose2ISAM2Example.html) -- incremental update pattern
- [GTSAM on PyPI](https://pypi.org/project/gtsam/) -- version 4.2 stable, 4.3a0 pre-release

### Secondary (MEDIUM confidence)
- Project codebase: `src/slam/protocol.py`, `src/slam/registry.py`, `src/slam/backends/icp_backend.py` -- established patterns to mirror
- Project codebase: `src/coordination/map_merger.py` -- existing merge implementation to wrap
- Project codebase: `backend/web/slam_routes.py` -- REST API pattern to extend

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Open3D already in deps, GTSAM well-documented on PyPI
- Architecture: HIGH -- mirrors established Phase 8 patterns exactly
- Pitfalls: HIGH -- derived from Open3D/GTSAM docs and multi-robot SLAM literature
- Code examples: HIGH -- verified against project codebase patterns and official docs

**Research date:** 2026-03-23
**Valid until:** 2026-04-22 (stable libraries, 30-day validity)
