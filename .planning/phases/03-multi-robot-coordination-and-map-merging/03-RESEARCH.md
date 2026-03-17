# Phase 3: Multi-Robot Coordination and Map Merging - Research

**Researched:** 2026-03-17
**Domain:** Multi-robot simulation, Voronoi partitioning, 3D map merging, inter-robot communication
**Confidence:** HIGH

## Summary

Phase 3 extends the single-robot exploration pipeline to two Go2 robots in a shared MuJoCo environment. The core challenges are: (1) loading two robots in one MuJoCo scene with independent control, (2) computing Voronoi-based region assignments from robot positions, (3) merging two independent OctoMap voxel grids and point clouds into a unified map in real-time, and (4) orchestrating the coordination lifecycle (boot exploration -> partition -> explore regions -> re-partition -> merge).

The existing codebase provides strong foundations: `MuJoCoBridge` handles single-robot MuJoCo interaction, `ExplorationLoop` drives frontier-based exploration, `OctoMapBuilder` accumulates occupancy grids, and `SLAMPipeline` estimates poses. All are designed as standalone Python classes with clear lifecycle methods, making them straightforward to instantiate twice. The DimOS `pLCMTransport` provides pickle-based pub/sub for typed data exchange between robot pipelines and the map merger.

**Primary recommendation:** Build incrementally -- first get two robots rendering/stepping in MuJoCo, then duplicate the SLAM+exploration pipeline per robot, add Voronoi partitioning as a frontier scoring bias, and finally implement the MapMerger class that subscribes to both robots' data and produces a unified map.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single MuJoCo environment with two Go2 bodies loaded at different spawn positions
- One physics step advances both robots simultaneously
- Configurable spawn positions defined in config (e.g., robot_a at origin, robot_b at [10, 0, 0]) -- known transforms are just config values
- COORD-01 reinterpreted for MuJoCo: "separate DimOS blueprint instances with namespaced streams" means separate object instances with namespaced data (robot_a.slam, robot_b.slam) in the same Python process
- Two SLAMPipeline objects, two OctoMapBuilder objects, two ExplorationLoop instances -- all in same process but operating on independent data
- Initial Voronoi partition computed AFTER a brief initial exploration phase, not from scene bounding box
- Soft constraint: frontiers in own region are prioritized (higher score), but robot CAN enter the other's region if no local frontiers remain
- Re-partition triggers when one robot's assigned region has zero remaining frontiers
- Dedicated MapMerger class -- takes two OctoMapBuilders + spawn transforms, produces unified occupancy grid + merged point cloud
- Frame alignment via configurable spawn transforms (MERGE-01) -- no ICP needed
- Voxel conflict resolution: union (OR) -- occupied if either robot says occupied
- Point cloud merging: voxel-downsampled to match occupancy resolution before merge
- Merge triggers on the same event as frontier rescan (distance/change trigger from Phase 2)
- DimOS pLCM transport for robot-to-robot data sharing
- Coordinator (partition assigner + merge trigger) runs in-process, not on LCM

### Claude's Discretion
- Initial exploration boot-up phase duration before first Voronoi partition
- Re-partition algorithm implementation details
- MuJoCo scene XML modifications for two-robot loading
- pLCM channel naming and message type design
- Multi-robot MuJoCoBridge extension (how to control two bodies independently)
- Exact integration with ExplorationLoop from Phase 2 (one loop per robot)

### Deferred Ideas (OUT OF SCOPE)
- MERGE-05: Conflict resolution for overlapping mapped regions -- v2
- MERGE-06: Merged map quality scoring against ground-truth -- v2
- COORD-05: Inter-robot communication protocol for sharing map fragments -- v2
- EXPL-05: Multi-robot collision avoidance -- v2
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COORD-01 | Two Go2 robots operate as separate DimOS blueprint instances with namespaced streams | Reinterpreted: two sets of Python objects (SLAMPipeline, OctoMapBuilder, ExplorationLoop) in same process with namespaced pLCM channels. MuJoCoBridge extended to control two bodies. |
| COORD-02 | System partitions the environment into regions using Voronoi splitting | scipy.spatial.Voronoi computes partitions from robot positions; frontier scoring bias steers robots to their assigned regions. |
| COORD-03 | System dynamically re-partitions regions when one robot's assigned area is fully explored | Re-partition triggered on zero frontiers in assigned region; Voronoi recomputed with shifted generator points to expand idle robot's zone. |
| MERGE-01 | System aligns robot-local maps to a shared global frame using known spawn transforms | Each robot's SLAM operates in world frame (MuJoCo ground-truth poses are already world-frame); spawn transform is a config-defined 4x4 offset applied to coordinate transform. |
| MERGE-02 | System fuses two 3D occupancy grids into a single unified navigation map via voxel merging | Union (OR) of two Open3D VoxelGrids: concatenate occupied voxel arrays, then re-voxelize at same resolution to deduplicate. |
| MERGE-03 | System merges point clouds from both robots into a unified 3D reconstruction | Concatenate clouds from both SLAMPipelines, voxel-downsample to occupancy resolution (0.1m). Open3D `+` operator + `voxel_down_sample()`. |
| MERGE-04 | Map merging operates incrementally in real-time as robots explore | Merge triggered on same event as frontier rescan (distance moved or voxel delta threshold). MapMerger subscribes to pLCM updates from both robots. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mujoco | >=3.0.0 | Physics simulation, multi-body scene | Already in pyproject.toml; body/attach or programmatic XML for two robots |
| Open3D | (installed) | VoxelGrid, PointCloud, voxel_down_sample | Already used in OctoMapBuilder and SLAMPipeline; natural choice for merge |
| scipy | (installed) | scipy.spatial.Voronoi for region partitioning | Standard scientific Python; no extra dependency |
| numpy | (installed) | Array operations, coordinate transforms | Already core dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dimos pLCMTransport | (installed) | Pickle-based LCM pub/sub for inter-robot data | Robot pipeline publishes occupancy/status; MapMerger subscribes |

### No New Dependencies Required
All required functionality is available through already-installed packages. No new pip installs needed.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── bridge/
│   ├── sim_bridge.py            # Extended: MultiRobotMuJoCoBridge
│   ├── env_config.py            # Extended: MultiRobotConfig with spawn positions
│   └── sensor_types.py          # Unchanged
├── slam/
│   ├── slam_pipeline.py         # Unchanged (instantiated twice)
│   └── octomap_builder.py       # Unchanged (instantiated twice)
├── exploration/
│   ├── exploration_loop.py      # Extended: accepts region_bias parameter
│   ├── frontier_detector.py     # Unchanged
│   ├── goal_selector.py         # Extended: region-biased scoring
│   └── ...
├── coordination/
│   ├── __init__.py
│   ├── multi_robot_config.py    # Robot spawn positions, partition config
│   ├── voronoi_partitioner.py   # Voronoi region computation and assignment
│   ├── map_merger.py            # Fuses two OctoMaps + point clouds
│   ├── robot_instance.py        # Per-robot pipeline container (SLAM + Octo + Explore)
│   └── coordinator.py           # Orchestrates lifecycle: boot -> partition -> explore -> re-partition -> merge
├── main.py                      # Extended: --control multi mode
└── multi_main.py                # Alternative: dedicated multi-robot entry point
```

### Pattern 1: Multi-Robot MuJoCo Scene via Programmatic XML
**What:** Generate a two-robot MuJoCo scene XML programmatically by duplicating the Go2 body with a name prefix and offset position.
**When to use:** Loading two Go2 robots from the same `go2.xml` model file.
**Approach:**

MuJoCo `go2.xml` uses `<include>` in `scene.xml`. Since MuJoCo does not allow including the same file twice, the two-robot scene must be built programmatically. Two approaches:

**Option A (Recommended): Python string templating** -- Read go2.xml, modify body/joint/actuator names with a prefix (e.g., `robot_b_`), set the root body position, and concatenate into a single scene XML. This is simple and the Go2 model is self-contained.

**Option B: dm_control MJCF library** -- Uses `dm_control.mjcf` to programmatically load and attach models. More complex dependency but handles naming automatically.

Recommendation: Option A. The Go2 model is well-structured and a simple prefix rename in Python is transparent and debuggable.

```python
# Conceptual: generate two-robot scene XML
def generate_two_robot_scene(
    go2_xml_path: str,
    robot_a_pos: tuple[float, float, float],
    robot_b_pos: tuple[float, float, float],
) -> str:
    """Generate MuJoCo XML with two Go2 robots at different positions."""
    import xml.etree.ElementTree as ET

    # Load base scene and robot
    # ... parse go2.xml, prefix all names for robot_b
    # ... insert both robot bodies into worldbody
    # ... prefix actuators for robot_b
    # Return combined XML string
```

### Pattern 2: Per-Robot Pipeline Container
**What:** A `RobotInstance` class that bundles one robot's entire pipeline (SLAM, OctoMap, ExplorationLoop) with a namespace ID.
**When to use:** Managing independent pipelines for each robot.

```python
@dataclass
class RobotInstance:
    """Container for one robot's complete pipeline."""
    robot_id: str  # "robot_a" or "robot_b"
    slam: SLAMPipeline
    octomap: OctoMapBuilder
    exploration: ExplorationLoop
    spawn_transform: np.ndarray  # 4x4 world-frame offset
    publisher: pLCMTransport  # publishes occupancy + status
```

### Pattern 3: Voronoi Region as Frontier Scoring Bias
**What:** Modify GoalSelector to accept a Voronoi region polygon and bias frontier scoring toward in-region frontiers.
**When to use:** COORD-02 -- after initial exploration boot phase.

```python
def select_with_region_bias(
    frontiers: list[FrontierCluster],
    robot_pose: np.ndarray,
    region_polygon: np.ndarray | None,  # (K, 2) vertices of Voronoi cell
    in_region_weight: float = 2.0,
) -> np.ndarray | None:
    """Select frontier with preference for own Voronoi region."""
    # Score each frontier: distance-based + region membership bonus
    # Frontiers inside region get multiplied score
    # If no in-region frontiers, fall back to any frontier (soft constraint)
```

### Pattern 4: MapMerger with Union (OR) Voxel Fusion
**What:** Dedicated class that takes two OctoMapBuilders and produces a unified occupancy grid and merged point cloud.
**When to use:** MERGE-02, MERGE-03, MERGE-04.

```python
class MapMerger:
    """Fuses two robots' local maps into a unified global map."""

    def __init__(
        self,
        resolution: float = 0.1,
        robot_a_transform: np.ndarray = np.eye(4),
        robot_b_transform: np.ndarray = np.eye(4),
    ):
        self._resolution = resolution
        self._transforms = {"robot_a": robot_a_transform, "robot_b": robot_b_transform}
        self._merged_cloud = o3d.geometry.PointCloud()

    def merge(
        self,
        octomap_a: OctoMapBuilder,
        octomap_b: OctoMapBuilder,
    ) -> tuple[np.ndarray, o3d.geometry.PointCloud]:
        """Merge two occupancy grids and point clouds.

        Returns:
            (unified_voxels, merged_cloud) where unified_voxels is (N, 3) float64
            and merged_cloud is a voxel-downsampled Open3D PointCloud.
        """
        voxels_a = octomap_a.get_occupied_voxels()  # already in world frame
        voxels_b = octomap_b.get_occupied_voxels()

        # Union: concatenate and re-voxelize to deduplicate
        all_voxels = np.vstack([voxels_a, voxels_b]) if len(voxels_a) > 0 and len(voxels_b) > 0 else ...
        # Voxel-deduplicate via rounding to grid
        unified = self._deduplicate_voxels(all_voxels, self._resolution)

        # Point cloud merge: concatenate + voxel downsample
        # ...
        return unified, merged_cloud
```

### Pattern 5: Coordinator Lifecycle
**What:** The Coordinator manages the multi-robot exploration lifecycle.
**Lifecycle:**
1. **Boot phase** (N steps): Both robots explore freely, building initial maps
2. **First partition**: Compute Voronoi from robot positions over discovered map extent
3. **Biased exploration**: Each robot prioritizes frontiers in its Voronoi region
4. **Re-partition**: When one robot has zero frontiers in its region, recompute Voronoi
5. **Merge**: On each frontier rescan event, MapMerger fuses both maps
6. **Termination**: Both robots have zero frontiers globally

### Anti-Patterns to Avoid
- **Shared mutable state between robots:** Each robot pipeline MUST operate on its own data. Never pass the same OctoMapBuilder to both robots.
- **Blocking merge on main loop:** Map merging must not block the step loop. Keep merge fast (numpy concat + voxel dedup) or run asynchronously.
- **Hard Voronoi constraints:** Hard region constraints cause deadlocks when one robot's region is fully explored but the other still has frontiers. Always use soft bias.
- **ICP for frame alignment:** With known spawn transforms in simulation, ICP is unnecessary overhead and can fail with partial overlaps. Use config transforms directly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Voronoi region computation | Custom region splitting | `scipy.spatial.Voronoi` | Edge cases with unbounded regions, vertex ordering; scipy handles correctly |
| Point-in-polygon test | Custom ray casting | `matplotlib.path.Path.contains_point` or `scipy` | Numerical robustness with edge cases |
| Voxel deduplication | Custom dict-based dedup | `np.unique` on rounded coordinates or Open3D `voxel_down_sample` | Vectorized and battle-tested |
| Quaternion/rotation math | Manual matrix construction | `scipy.spatial.transform.Rotation` | Already used in conftest.py; handles all edge cases |
| Point cloud concatenation | Manual array management | Open3D `cloud_a + cloud_b` operator | Handles colors, normals, metadata automatically |

**Key insight:** The merge operation is fundamentally array concatenation + deduplication. Open3D and numpy already provide all the primitives. The novel code is orchestration, not computation.

## Common Pitfalls

### Pitfall 1: MuJoCo Body Index Confusion
**What goes wrong:** After loading two robots, `qpos` indices shift. Robot A's freejoint is qpos[0:7], but Robot B's freejoint is NOT at qpos[7:14] if there are actuator joints in between.
**Why it happens:** MuJoCo orders qpos by body tree traversal order, not insertion order.
**How to avoid:** Use `mujoco.mj_name2id()` to look up body/joint indices by name, NEVER hardcode indices. Store `self._robot_a_qpos_start` and `self._robot_b_qpos_start` at init time.
**Warning signs:** Robot B's pose returns Robot A's data, or vice versa.

### Pitfall 2: Camera Assignment Per Robot
**What goes wrong:** Both robots render from the same camera, so Robot B sees Robot A's viewpoint.
**Why it happens:** Single `renderer.update_scene(data, camera=...)` call uses one camera.
**How to avoid:** Each robot needs its own camera attached to its body. The scene XML must define `robot_a_camera` and `robot_b_camera` as child sites of each robot's base body. Render twice per step (once per camera).
**Warning signs:** Both robots produce identical depth/RGB images.

### Pitfall 3: Voronoi with Only Two Points
**What goes wrong:** `scipy.spatial.Voronoi` with only 2 points produces degenerate results (infinite regions, no finite vertices).
**Why it happens:** Voronoi of 2 points is just a perpendicular bisector line.
**How to avoid:** For 2-robot case, skip scipy Voronoi entirely. Compute the bisector directly: the boundary is the perpendicular bisector of the line segment between two robot positions. Classify frontiers by which side of the bisector they fall on.
**Warning signs:** `scipy.spatial.Voronoi` raises errors or returns empty regions.

### Pitfall 4: Voxel Grid Origin Mismatch
**What goes wrong:** Merging two OctoMaps produces doubled voxels or gaps because their internal grid origins differ.
**Why it happens:** Each OctoMapBuilder's VoxelGrid has its own origin based on the first inserted point.
**How to avoid:** Always work with world-frame voxel centers from `get_occupied_voxels()`, NOT internal grid indices. Merge at the world-coordinate level, then re-voxelize.
**Warning signs:** Merged map shows duplicate walls or gaps at boundaries.

### Pitfall 5: ExplorationLoop Calls bridge.start()
**What goes wrong:** `ExplorationLoop.run()` currently calls `self._bridge.start()` on line 66, which would reset the MuJoCo simulation for both robots.
**Why it happens:** The loop was designed for single-robot mode where it owns the bridge lifecycle.
**How to avoid:** Refactor ExplorationLoop to NOT call `bridge.start()`. The Coordinator manages the bridge lifecycle. ExplorationLoop should accept a `step_fn` callback or operate in a "step" mode rather than owning the loop.
**Warning signs:** Simulation resets when second robot starts exploring.

### Pitfall 6: Render Performance with Two Cameras
**What goes wrong:** Rendering two cameras per step halves the frame rate.
**Why it happens:** MuJoCo offscreen rendering is CPU-bound; two renders = 2x cost.
**How to avoid:** Accept the 2x render cost (still fast enough at ~5Hz per robot). Do NOT try to render both views in one call. Consider reducing resolution if performance is an issue.
**Warning signs:** Step rate drops below 2Hz.

## Code Examples

### MuJoCo Two-Robot Scene XML (Programmatic Generation)
```python
# Source: MuJoCo modeling docs + project go2.xml structure
import xml.etree.ElementTree as ET
import copy

def prefix_all_names(element: ET.Element, prefix: str) -> None:
    """Recursively prefix 'name' attributes in an XML element tree."""
    for attr in ['name', 'joint', 'body', 'geom', 'site', 'class',
                 'target', 'jointinparent', 'body1', 'body2']:
        if attr in element.attrib:
            element.attrib[attr] = prefix + element.attrib[attr]
    for child in element:
        prefix_all_names(child, prefix)

def build_two_robot_scene(
    scene_template: str,
    go2_body_xml: str,
    spawn_a: tuple[float, float, float],
    spawn_b: tuple[float, float, float],
) -> str:
    """Build scene XML with two prefixed Go2 robots."""
    # Parse robot body subtree, clone for robot_b with prefix
    # Set root body positions to spawn_a and spawn_b
    # Insert both into worldbody of scene template
    ...
```

### Voronoi Partitioning for Two Robots (Perpendicular Bisector)
```python
# Source: scipy.spatial docs, adapted for 2-robot case
import numpy as np

def compute_bisector_assignment(
    pos_a: np.ndarray,   # (2,) XY position of robot A
    pos_b: np.ndarray,   # (2,) XY position of robot B
    frontier_centroids: np.ndarray,  # (N, 2) XY centroids
) -> np.ndarray:
    """Assign each frontier to the nearest robot using perpendicular bisector.

    Returns:
        (N,) int array: 0 for robot_a's region, 1 for robot_b's region.
    """
    midpoint = (pos_a + pos_b) / 2.0
    # Direction from A to B
    direction = pos_b - pos_a
    # For each frontier, check which side of the bisector it falls on
    # dot(frontier - midpoint, direction) > 0 means closer to B
    deltas = frontier_centroids - midpoint
    dots = deltas @ direction
    return (dots > 0).astype(int)
```

### Open3D Voxel Union Merge
```python
# Source: Open3D docs + project OctoMapBuilder pattern
import numpy as np
import open3d as o3d

def merge_voxel_grids(
    voxels_a: np.ndarray,  # (N, 3) from OctoMapBuilder.get_occupied_voxels()
    voxels_b: np.ndarray,  # (M, 3) from OctoMapBuilder.get_occupied_voxels()
    resolution: float = 0.1,
) -> np.ndarray:
    """Union-merge two voxel arrays, deduplicating overlapping voxels."""
    if voxels_a.size == 0:
        return voxels_b.copy() if voxels_b.size > 0 else np.empty((0, 3))
    if voxels_b.size == 0:
        return voxels_a.copy()

    combined = np.vstack([voxels_a, voxels_b])
    # Round to grid to find duplicates
    grid_indices = np.round(combined / resolution).astype(np.int64)
    # np.unique on rows
    _, unique_idx = np.unique(grid_indices, axis=0, return_index=True)
    return combined[unique_idx]


def merge_point_clouds(
    cloud_a: o3d.geometry.PointCloud,
    cloud_b: o3d.geometry.PointCloud,
    voxel_size: float = 0.1,
) -> o3d.geometry.PointCloud:
    """Merge and voxel-downsample two point clouds."""
    merged = cloud_a + cloud_b
    return merged.voxel_down_sample(voxel_size)
```

### pLCM Channel Design
```python
# Source: DimOS transport.py pLCMTransport API
from dimos.core.transport import pLCMTransport

# Channel naming convention: /{robot_id}/{data_type}
# Robot A publishes occupancy data
pub_a = pLCMTransport("/robot_a/occupancy")
pub_a.broadcast(None, {"voxels": voxels_a, "frontier_count": 5})

# MapMerger subscribes to both
sub_a = pLCMTransport("/robot_a/occupancy")
sub_a.subscribe(callback=on_robot_a_update, selfstream=None)

sub_b = pLCMTransport("/robot_b/occupancy")
sub_b.subscribe(callback=on_robot_b_update, selfstream=None)
```

### ExplorationLoop Refactoring for Multi-Robot
```python
# Current: ExplorationLoop.run() owns the bridge lifecycle
# Needed: ExplorationLoop operates in step-by-step mode

class ExplorationLoop:
    def step(self, frame: SensorFrame, region_bias: np.ndarray | None = None) -> tuple:
        """Process one frame in the exploration loop.

        Args:
            frame: Current sensor data (from external bridge.step())
            region_bias: Optional (K, 2) polygon defining preferred region

        Returns:
            (linear_vel, angular_vel, metrics_dict)
        """
        # Same logic as run() but for ONE iteration
        # Coordinator calls this per-robot per-step
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| dm_control MJCF for multi-robot | MuJoCo native body/attach (3.0+) | MuJoCo 3.0.0 | Simpler, no dm_control dependency; but for this project, programmatic XML is even simpler |
| ICP-based map alignment | Known-transform alignment (simulation) | Project decision | Eliminates alignment failure modes entirely |
| Probabilistic voxel merging | Union (OR) merging | Project decision (v1) | Simple, conservative; fine for v1 |
| Separate processes per robot | Same-process namespaced instances | Project decision | No IPC overhead; direct Python object access |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | pyproject.toml (via conftest.py) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COORD-01 | Two independent pipeline instances with namespaced data | unit | `python -m pytest tests/test_robot_instance.py -x` | No -- Wave 0 |
| COORD-02 | Voronoi/bisector partitioning assigns frontiers to regions | unit | `python -m pytest tests/test_voronoi_partitioner.py -x` | No -- Wave 0 |
| COORD-03 | Re-partition triggered on zero frontiers in assigned region | unit | `python -m pytest tests/test_coordinator.py::test_repartition -x` | No -- Wave 0 |
| MERGE-01 | Known spawn transform applied to align maps | unit | `python -m pytest tests/test_map_merger.py::test_frame_alignment -x` | No -- Wave 0 |
| MERGE-02 | Union voxel fusion produces correct unified grid | unit | `python -m pytest tests/test_map_merger.py::test_voxel_merge -x` | No -- Wave 0 |
| MERGE-03 | Point clouds merged and voxel-downsampled | unit | `python -m pytest tests/test_map_merger.py::test_point_cloud_merge -x` | No -- Wave 0 |
| MERGE-04 | Merge triggered incrementally during exploration | integration | `python -m pytest tests/test_coordinator.py::test_incremental_merge -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_map_merger.py` -- covers MERGE-01, MERGE-02, MERGE-03
- [ ] `tests/test_voronoi_partitioner.py` -- covers COORD-02
- [ ] `tests/test_robot_instance.py` -- covers COORD-01 (two independent instances)
- [ ] `tests/test_coordinator.py` -- covers COORD-03, MERGE-04 (lifecycle orchestration)
- [ ] `tests/test_multi_bridge.py` -- covers multi-robot MuJoCo bridge (two-body stepping)
- [ ] Update `tests/conftest.py` with multi-robot fixtures (MockMultiRobotBridge, mock dual voxel sets)

## Open Questions

1. **MuJoCo qpos layout for two freejointed robots**
   - What we know: Single Go2 uses qpos[0:7] (freejoint) + qpos[7:19] (12 actuators)
   - What's unclear: Exact qpos layout when two robots are loaded. Likely qpos[0:19] for robot_a, qpos[19:38] for robot_b, but must verify at load time.
   - Recommendation: At bridge.start(), use `mujoco.mj_name2id()` to discover indices dynamically. Store per-robot index ranges.

2. **ExplorationLoop refactoring scope**
   - What we know: Current `run()` method owns the full loop including bridge.start()/step()
   - What's unclear: Whether to add a `step()` method or refactor `run()` to accept an external step callback
   - Recommendation: Add a `step_once(frame, region_bias)` method that processes one iteration. Keep `run()` for backward compatibility (single-robot mode). Coordinator calls `step_once()` per robot per step.

3. **Initial exploration boot duration**
   - What we know: Need some initial free exploration before computing Voronoi
   - What's unclear: How many steps or what coverage threshold triggers first partition
   - Recommendation: Use a fixed step count (e.g., 200 steps = ~40 seconds at 5Hz) as the initial boot phase. Simple, predictable, easily tunable. Alternative: trigger on first frontier detection + minimum voxel count (e.g., 100 voxels per robot).

## Sources

### Primary (HIGH confidence)
- Project source code: `src/bridge/sim_bridge.py`, `src/slam/slam_pipeline.py`, `src/slam/octomap_builder.py`, `src/exploration/exploration_loop.py`, `src/exploration/goal_selector.py` -- read in full
- DimOS transport code: `dimos/dimos/core/transport.py` -- pLCMTransport API verified
- MuJoCo `body/attach` mechanism: [MuJoCo Discussion #1063](https://github.com/google-deepmind/mujoco/discussions/1063), [MuJoCo XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html)
- Project pyproject.toml: confirms `mujoco>=3.0.0`
- [SciPy Voronoi docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Voronoi.html)
- [Open3D VoxelGrid docs](https://www.open3d.org/docs/release/tutorial/geometry/voxelization.html)
- [Open3D PointCloud docs](https://www.open3d.org/docs/release/tutorial/geometry/pointcloud.html)

### Secondary (MEDIUM confidence)
- MuJoCo multi-robot patterns: [dm_control MJCF README](https://github.com/google-deepmind/dm_control/blob/main/dm_control/mjcf/README.md) -- automatic name disambiguation for multiple model instances
- [Voronoi-based multi-robot exploration research](https://www.researchgate.net/publication/28185791_Voronoi-Based_Space_Partitioning_for_Coordinated_Multi-Robot_Exploration) -- validates approach
- [DimOS GitHub](https://github.com/dimensionalOS/dimos) -- pLCM transport architecture

### Tertiary (LOW confidence)
- MuJoCo `body/attach` exact XML syntax with `prefix` attribute -- verified to exist in 3.0+, but exact syntax for Go2 duplication not tested. Programmatic XML generation recommended as more reliable approach.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and used in project
- Architecture: HIGH - patterns follow existing codebase conventions; straightforward extension of Phase 2
- Pitfalls: HIGH - identified from reading actual source code (ExplorationLoop.run() calling bridge.start(), qpos index layout, camera per-robot)
- MuJoCo two-robot loading: MEDIUM - programmatic XML approach is well-understood but specific Go2 XML prefixing needs implementation validation
- Voronoi for 2 robots: HIGH - perpendicular bisector is mathematically trivial for 2-point case

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain; MuJoCo and Open3D APIs unlikely to change)
