# Phase 2: Autonomous Exploration - Research

**Researched:** 2026-03-17
**Domain:** Frontier-based autonomous exploration with 3D voxel maps + discrete action navigation
**Confidence:** HIGH

## Summary

This phase implements a frontier-based autonomous exploration loop: the robot detects boundaries between explored and unexplored voxel space, selects a frontier goal, plans a path using A*, converts waypoints to discrete actions, navigates to the goal, and repeats. The OctoMapBuilder from Phase 1 provides the 3D voxel grid; frontier detection scans voxel boundaries. Navigation converts A* path waypoints into discrete SimWorld actions (Discrete(6)) via the existing `set_velocity()` pipeline.

DimOS ships a `WavefrontFrontierExplorer` module and `ReplanningAStarPlanner` module. However, both are deeply coupled to DimOS's LCM-based Module system (`In[OccupancyGrid]`, `Out[PoseStamped]`, LCM transport, threaded subscription model). This project uses standalone Python classes with a synchronous step loop, not DimOS Modules. The recommendation is to extract the **algorithms** from DimOS (wavefront BFS frontier detection, min-cost A*, comprehensive frontier scoring) and reimplement them in standalone classes compatible with the project's existing patterns. The DimOS source serves as a verified reference implementation.

The critical bridge problem is converting the project's Open3D VoxelGrid (3D voxel centers as float64 arrays) into 2D OccupancyGrid format suitable for frontier detection and A* pathfinding. This requires projecting 3D occupied voxels onto a 2D grid (XY plane), marking cells as FREE (observed but empty via ray-casting or proximity), OCCUPIED (voxel present), or UNKNOWN (never observed).

**Primary recommendation:** Build standalone `FrontierDetector`, `ExplorationPlanner` (A*-based path planner), and `ExplorationLoop` classes. Port the wavefront BFS algorithm from DimOS `WavefrontFrontierExplorer.detect_frontiers()` and the `min_cost_astar()` from DimOS. Adapt to work with 2D occupancy grids projected from the existing Open3D VoxelGrid.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full 3D frontier detection in voxel space (not projected to 2D)
- Re-detect frontiers on a distance/change trigger (robot moved N meters or map grew by M voxels), not every gym step
- Skip unreachable frontiers and try the next candidate; if all unreachable, trigger exploration complete
- No blacklist for failed frontiers -- unreachable ones are skipped this cycle but re-eligible on next scan
- Use DimOS replanning A* module for pathfinding (adapt to SimWorld if needed)
- Step-by-step action mapping: convert path waypoints to sequences of discrete actions using the existing `set_velocity()` -> discrete action pipeline in `sim_bridge.py`
- Replan paths when occupancy grid changes affect the current path (new obstacle or new shortcut), aligned with the distance/change trigger for frontier detection
- Exploration terminates when zero reachable frontier clusters remain
- Configurable maximum step limit as safety net (e.g., 10,000 steps) -- if reached, stop and report achieved coverage
- Periodic log output: coverage %, frontier count, and step count every N steps or on frontier re-evaluation

### Claude's Discretion
- Frontier extraction algorithm and noise filtering thresholds
- Goal selection strategy (nearest/largest/weighted)
- Frontier commitment vs re-evaluation mid-journey
- Stuck detection implementation
- Coverage metric calculation approach
- DimOS replanning A* integration details and any adaptations needed for 3D + discrete actions

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXPL-01 | System detects frontier boundaries (unexplored regions adjacent to explored space) | Wavefront BFS algorithm from DimOS `WavefrontFrontierExplorer.detect_frontiers()` -- operates on 2D occupancy grid, identifies unknown cells adjacent to free cells. Must be adapted for 3D voxel space per user decision. |
| EXPL-02 | Each robot autonomously selects frontier goals and navigates to them without human input | DimOS `min_cost_astar()` for path planning + `WavefrontFrontierExplorer._rank_frontiers()` for goal selection. WaypointRunner already converts paths to velocity commands. ExplorationLoop orchestrates the full cycle. |
| EXPL-03 | System tracks and reports exploration completeness (% of navigable area covered) | Coverage tracking via frontier exhaustion ratio (known cells / (known + unknown within bounding box)) or ground-truth comparison if available. Periodic logging per user decision. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Open3D | >=0.18.0 | 3D voxel grid backend, point cloud processing | Already used for OctoMapBuilder; provides VoxelGrid for spatial queries |
| numpy | >=1.26.0 | Array operations, occupancy grid representation | Universal numerical computing; all existing code uses it |
| scipy | >=1.15.0 | Spatial operations (KDTree for neighbor queries, distance calculations) | Already in dependencies; useful for efficient spatial neighbor lookups in 3D frontier detection |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rerun-sdk | >=0.30.0 | 3D visualization of frontiers, paths, exploration progress | Already used for viz; log frontier voxels, planned paths, robot trajectory |
| collections.deque | stdlib | BFS queue for wavefront frontier detection | Standard BFS data structure, used by DimOS reference implementation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom A* | DimOS `min_cost_astar()` directly | DimOS A* works on OccupancyGrid type with LCM deps; extracting the pure algorithm (heapq-based, 8-connected grid) and reimplementing in ~80 lines is cleaner than importing DimOS module infrastructure |
| Custom frontier detection | DimOS `WavefrontFrontierExplorer.detect_frontiers()` | Same coupling issue; the algorithm is ~100 lines of BFS but depends on DimOS OccupancyGrid/Vector3/CostValues types |
| scikit-image for frontier detection | Custom voxel boundary scan | Overkill; frontier detection in voxel space is simple neighbor checking |

**Installation:**
```bash
# No new packages needed -- all dependencies already in pyproject.toml
pip install -e .
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── exploration/
│   ├── __init__.py
│   ├── frontier_detector.py    # 3D voxel frontier detection (EXPL-01)
│   ├── goal_selector.py        # Frontier ranking and selection (EXPL-02)
│   ├── path_planner.py         # A* pathfinding on 2D projected grid (EXPL-02)
│   ├── exploration_loop.py     # Main autonomous loop orchestrator (EXPL-02)
│   └── coverage_tracker.py     # Coverage % computation and logging (EXPL-03)
├── bridge/                     # (existing)
├── slam/                       # (existing)
├── control/                    # (existing -- WaypointRunner reused)
├── metrics/                    # (existing)
└── viz/                        # (existing -- extend for exploration viz)
```

### Pattern 1: Synchronous Exploration Loop
**What:** A single-threaded loop that orchestrates sense-plan-act per sim step, with frontier re-evaluation on triggers.
**When to use:** Always -- this is the core exploration pattern.
**Example:**
```python
# Pseudocode for the exploration loop
class ExplorationLoop:
    def __init__(self, bridge, slam, frontier_detector, goal_selector,
                 path_planner, coverage_tracker, config):
        self.bridge = bridge
        self.slam = slam
        self.frontier_detector = frontier_detector
        self.goal_selector = goal_selector
        self.path_planner = path_planner
        self.coverage_tracker = coverage_tracker
        self.config = config

    def run(self, max_steps: int = 10000) -> ExplorationResult:
        frame = self.bridge.start()
        current_path = None
        current_goal = None
        last_frontier_scan_position = frame.ground_truth_pose[:3, 3].copy()
        last_voxel_count = 0

        for step in range(max_steps):
            # 1. Update SLAM with new observation
            self.slam.update(frame)
            current_pose = frame.ground_truth_pose

            # 2. Check if frontier re-evaluation is triggered
            if self._should_rescan_frontiers(current_pose, last_frontier_scan_position,
                                              last_voxel_count):
                frontiers = self.frontier_detector.detect(self.slam.get_voxel_grid())
                if not frontiers:
                    # Check if current goal still valid, else exploration complete
                    if current_goal is None:
                        break  # No frontiers, no goal = done
                goal = self.goal_selector.select(frontiers, current_pose)
                if goal is not None:
                    current_goal = goal
                    current_path = self.path_planner.plan(current_pose, goal,
                                                          self.slam.get_occupancy_grid())
                last_frontier_scan_position = current_pose[:3, 3].copy()
                last_voxel_count = self.slam.num_occupied

            # 3. Execute next action from path
            if current_path and not current_path.is_complete:
                linear, angular = current_path.get_velocity(current_pose)
                self.bridge.set_velocity(linear, angular)
            else:
                # Path complete or no path -- trigger rescan next iteration
                current_goal = None

            # 4. Step simulation
            frame = self.bridge.step()

            # 5. Periodic logging
            if step % self.config.log_interval == 0:
                self.coverage_tracker.log(step, len(frontiers) if frontiers else 0)

        return self.coverage_tracker.result()
```

### Pattern 2: 3D Voxel Frontier Detection
**What:** Identify frontier voxels as occupied voxels adjacent to unexplored space in 3D.
**When to use:** For EXPL-01 -- detecting exploration boundaries.
**Example:**
```python
# 3D frontier detection approach
class FrontierDetector:
    """Detect frontier voxels in 3D voxel space.

    A frontier voxel is an occupied (or free) voxel that has at least one
    neighbor position in the 26-connected neighborhood that is UNEXPLORED
    (no voxel exists there).

    Since OctoMapBuilder only tracks occupied voxels (not free space), we
    define frontiers as occupied voxels on the boundary of the known region --
    i.e., occupied voxels with at least one 26-neighbor that is not occupied.
    """

    def __init__(self, resolution: float = 0.1, min_cluster_size: int = 5):
        self.resolution = resolution
        self.min_cluster_size = min_cluster_size

    def detect(self, occupied_voxels: np.ndarray) -> list[FrontierCluster]:
        # 1. Build a set of occupied voxel indices for O(1) lookup
        voxel_indices = self._to_grid_indices(occupied_voxels)
        occupied_set = set(map(tuple, voxel_indices))

        # 2. Find boundary voxels (have at least one empty 26-neighbor)
        frontier_voxels = []
        for idx in occupied_set:
            for neighbor in self._get_26_neighbors(idx):
                if neighbor not in occupied_set:
                    frontier_voxels.append(idx)
                    break

        # 3. Cluster frontier voxels (connected components)
        clusters = self._cluster_frontiers(frontier_voxels)

        # 4. Filter by minimum cluster size
        return [c for c in clusters if len(c.voxels) >= self.min_cluster_size]
```

### Pattern 3: 2D Projection for Path Planning
**What:** Project 3D voxel data to a 2D occupancy grid for A* path planning.
**When to use:** Path planning operates on 2D grid; robot moves on ground plane.
**Example:**
```python
def project_to_2d_grid(occupied_voxels: np.ndarray, resolution: float,
                        z_min: float, z_max: float) -> OccupancyGrid2D:
    """Project 3D occupied voxels to 2D occupancy grid for navigation.

    Voxels within [z_min, z_max] height range are projected to XY plane.
    Cells with any occupied voxel above ground height become OCCUPIED.
    Cells adjacent to occupied cells that are observed become FREE.
    All other cells are UNKNOWN.
    """
    # Filter voxels by height
    mask = (occupied_voxels[:, 2] >= z_min) & (occupied_voxels[:, 2] <= z_max)
    ground_voxels = occupied_voxels[mask]

    # Discretize to 2D grid
    xy = ground_voxels[:, :2]
    grid_indices = ((xy - xy.min(axis=0)) / resolution).astype(int)
    # ... build grid, mark occupied, free, unknown
```

### Anti-Patterns to Avoid
- **Running frontier detection every step:** The user decision explicitly says use distance/change triggers. Frontier BFS on a large grid is O(n) where n is grid cells -- too expensive per step at 3-6 Hz.
- **Using DimOS Module system directly:** DimOS modules require LCM transport, threaded subscriptions, and DimOS-specific types. The project uses synchronous step loops. Extract algorithms, don't import modules.
- **Building a 2D-only occupancy grid:** User decision specifies "full 3D frontier detection in voxel space." However, A* path planning will still need a 2D projection for ground-plane navigation.
- **Replanning path every step:** Align path replanning with the frontier re-evaluation trigger to avoid excessive computation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| A* pathfinding | Custom A* from scratch | Port DimOS `min_cost_astar()` (80 lines, heapq-based, 8-connected) | Handles edge cases: diagonal costs, unknown cell penalties, cost thresholds. Has optional C++ acceleration. |
| Frontier scoring | Custom heuristic from scratch | Adapt DimOS `_compute_comprehensive_frontier_score()` | Balanced 5-factor scoring: distance, info gain, explored-goal distance, obstacle distance, momentum. Well-tuned weights. |
| Waypoint following | Custom path executor | Reuse existing `WaypointRunner` class | Already handles turn-then-drive, arrival detection, angular error wrapping. Proven with SimWorld's discrete actions. |
| Connected component clustering | BFS clustering from scratch | scipy.ndimage.label or manual BFS | scipy.ndimage.label is vectorized and handles 3D; for 2D grids it's a one-liner |

**Key insight:** The DimOS source code is the primary reference for algorithms, but its Module/LCM infrastructure is incompatible with this project's synchronous step loop. Extract the algorithms (BFS frontier detection, A* planning, frontier scoring) and wrap them in standalone classes.

## Common Pitfalls

### Pitfall 1: 3D Frontier Detection is Deceptively Expensive
**What goes wrong:** Scanning all 26 neighbors for every occupied voxel becomes slow as the map grows (10K+ voxels). KDTree or spatial hashing is needed.
**Why it happens:** Naive O(n * 26) with set lookup per neighbor is fine for small maps but scales poorly.
**How to avoid:** Use a hash set of voxel grid indices (tuples) for O(1) lookup. Pre-compute the 26-neighbor offsets. Profile at ~5K voxels and optimize if needed. Consider only re-scanning voxels near recently inserted scans.
**Warning signs:** Frontier detection taking >100ms per call.

### Pitfall 2: OctoMapBuilder Only Tracks Occupied Voxels
**What goes wrong:** The current `OctoMapBuilder.get_occupied_voxels()` returns only cells with points in them. There is no concept of "free space" (observed but empty) vs "unknown" (never observed). This makes frontier detection ambiguous -- every boundary of the occupied region looks like a frontier.
**Why it happens:** Open3D VoxelGrid only stores voxels containing points. It does not do ray-casting to mark empty space along sensor rays.
**How to avoid:** Implement a separate spatial awareness mechanism:
  1. **Option A (simpler):** Track the bounding box of all sensor observations. Cells within the observation bounding box but without occupied voxels are "free." Cells outside the bounding box are "unknown." Frontiers are at the boundary of the bounding box.
  2. **Option B (better):** Perform ray-casting from sensor origin through each depth point. All voxels along the ray before the hit point are "free." This gives true free-space information.
  3. **Option C (simplest for 3D):** Use the ground-truth robot trajectory to define an "explored region" -- all voxels within sensor range of any visited position are considered observed. Unoccupied observed voxels are free; unobserved are unknown.
**Warning signs:** All occupied voxels are classified as frontiers because there is no free/unknown distinction.

### Pitfall 3: Discrete Actions Make Path Following Coarse
**What goes wrong:** SimWorld actions are: forward, backward, left, right, turn-right (90 deg), turn-left (90 deg). The robot cannot make fine adjustments. WaypointRunner may oscillate between turn-left and turn-right when the heading error is near the threshold.
**Why it happens:** The `set_velocity()` mapping discretizes continuous velocity to 6 actions. Angular velocity threshold is 0.1 rad -- any angle error > ~6 degrees triggers turning.
**How to avoid:** Use coarse waypoints (every 1-2 meters, not every 0.1m). Accept that path following will be grid-like. Consider increasing the WaypointRunner arrival threshold to 1.0m+ for coarse navigation. Implement stuck detection (position hasn't changed for N steps) to break oscillation cycles.
**Warning signs:** Robot oscillates between turns at waypoints, step count grows without position change.

### Pitfall 4: Frontier Re-evaluation Trigger Thresholds
**What goes wrong:** If the distance/change trigger threshold is too small, frontiers are re-evaluated too often (performance hit). If too large, the robot commits to outdated goals.
**Why it happens:** The optimal trigger depends on map growth rate and environment size, which vary.
**How to avoid:** Start with conservative defaults: re-evaluate when robot moves 2.0m OR map grows by 500 voxels. Make both configurable. Log trigger counts to tune.
**Warning signs:** Re-evaluation happening every few steps (too frequent) or robot traveling far past stale frontiers (too infrequent).

### Pitfall 5: A* on Projected 2D Grid Needs Correct Origin and Bounds
**What goes wrong:** The 2D occupancy grid has an origin offset and resolution that must match the voxel grid. If misaligned, A* plans paths through walls or into unknown space.
**Why it happens:** Coordinate frame mismatch between 3D voxel centers (world frame, meters) and 2D grid indices.
**How to avoid:** Compute 2D grid bounds from the 3D voxel bounding box. Store the origin (min x, min y) and resolution. Verify by visualizing the 2D grid overlaid on the 3D voxel map in Rerun.
**Warning signs:** Planned paths go through obstacles, robot gets stuck at walls.

## Code Examples

### 3D Voxel Frontier Detection (adapted from DimOS wavefront BFS concept for 3D)
```python
import numpy as np
from scipy import ndimage

class FrontierDetector:
    """Detect frontier clusters in 3D voxel space.

    Uses the OctoMapBuilder's occupied voxels + a free-space model
    to identify boundary voxels between explored and unexplored space.
    """

    def __init__(self, resolution: float = 0.1, min_cluster_size: int = 5):
        self._resolution = resolution
        self._min_cluster_size = min_cluster_size

    def detect(self, occupied_voxels: np.ndarray,
               observed_bounds: np.ndarray) -> list[np.ndarray]:
        """Detect frontier clusters.

        Args:
            occupied_voxels: (N, 3) float64 voxel centers from OctoMapBuilder.
            observed_bounds: (M, 3) float64 positions the robot has visited
                (defines the observed region).

        Returns:
            List of frontier cluster centroids as (3,) arrays.
        """
        if len(occupied_voxels) == 0:
            return []

        # Convert to grid indices
        grid_min = occupied_voxels.min(axis=0) - self._resolution * 5
        indices = ((occupied_voxels - grid_min) / self._resolution).astype(int)
        occupied_set = set(map(tuple, indices))

        # Find boundary voxels (26-connected check)
        offsets = self._get_26_offsets()
        frontier_indices = []
        for idx in occupied_set:
            for offset in offsets:
                neighbor = (idx[0] + offset[0], idx[1] + offset[1], idx[2] + offset[2])
                if neighbor not in occupied_set:
                    frontier_indices.append(idx)
                    break

        if not frontier_indices:
            return []

        # Cluster using connected components
        clusters = self._cluster_bfs(frontier_indices)

        # Filter small clusters and compute centroids
        result = []
        for cluster in clusters:
            if len(cluster) >= self._min_cluster_size:
                centroid_idx = np.mean(cluster, axis=0)
                centroid_world = grid_min + centroid_idx * self._resolution
                result.append(centroid_world)

        return result

    @staticmethod
    def _get_26_offsets():
        offsets = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    offsets.append((dx, dy, dz))
        return offsets

    def _cluster_bfs(self, indices: list) -> list[list]:
        """Cluster frontier voxels using BFS on 26-connectivity."""
        from collections import deque
        index_set = set(map(tuple, indices))
        visited = set()
        clusters = []
        offsets = self._get_26_offsets()

        for idx in index_set:
            if idx in visited:
                continue
            cluster = []
            queue = deque([idx])
            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                if current in index_set:
                    cluster.append(current)
                    for offset in offsets:
                        neighbor = (current[0]+offset[0], current[1]+offset[1], current[2]+offset[2])
                        if neighbor in index_set and neighbor not in visited:
                            queue.append(neighbor)
            if cluster:
                clusters.append([list(c) for c in cluster])
        return clusters
```

### A* Path Planner (adapted from DimOS min_cost_astar)
```python
import heapq
import numpy as np

def plan_path_astar(grid: np.ndarray, start_xy: tuple, goal_xy: tuple,
                     resolution: float, origin: np.ndarray,
                     cost_threshold: int = 100) -> list[np.ndarray] | None:
    """Plan path on 2D occupancy grid using A*.

    Args:
        grid: (H, W) int8 array. 0=free, -1=unknown, >=100=occupied.
        start_xy: (grid_x, grid_y) start cell.
        goal_xy: (grid_x, grid_y) goal cell.
        resolution: meters per cell.
        origin: (2,) world coordinates of grid origin.

    Returns:
        List of (2,) world coordinate waypoints, or None if no path.
    """
    # Standard 8-connected A* with octile heuristic
    # (port from DimOS min_cost_astar, ~80 lines)
    ...
```

### Coverage Tracker
```python
class CoverageTracker:
    """Track exploration coverage over time."""

    def __init__(self):
        self._history: list[tuple[int, float, int]] = []  # (step, coverage%, frontier_count)

    def compute_coverage(self, occupied_voxels: np.ndarray,
                          bounding_box_volume: float,
                          resolution: float) -> float:
        """Coverage = observed volume / bounding box volume.

        'Observed volume' = number of occupied voxels * voxel_volume.
        This is a lower bound; true coverage includes free-space observations.
        """
        voxel_volume = resolution ** 3
        observed_volume = len(occupied_voxels) * voxel_volume
        return min(observed_volume / bounding_box_volume, 1.0) * 100.0 if bounding_box_volume > 0 else 0.0

    def log(self, step: int, coverage_pct: float, frontier_count: int) -> None:
        self._history.append((step, coverage_pct, frontier_count))
        print(f"[Step {step:5d}] Coverage: {coverage_pct:.1f}%  Frontiers: {frontier_count}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 2D occupancy grid frontier detection | 3D voxel-space frontier detection | User decision for this project | More accurate frontiers in multi-level environments; higher compute cost |
| DimOS Module with LCM transport | Standalone Python classes with sync loop | Project architecture decision (Phase 1) | Cannot use DimOS modules directly; must extract algorithms |
| octomap-python for occupancy | Open3D VoxelGrid | Phase 1 decision (build failure) | No built-in ray-casting/free-space tracking; must implement separately |

**Deprecated/outdated:**
- DimOS Module infrastructure: Not applicable to this project's sync loop pattern.
- 2D-only frontier detection: User explicitly chose 3D voxel-space detection.

## Open Questions

1. **Free-space representation in OctoMapBuilder**
   - What we know: OctoMapBuilder only stores occupied voxels. Frontier detection needs to distinguish "unknown" from "free" (observed but empty).
   - What's unclear: The best approach -- ray-casting (accurate but expensive), visited-position-radius (simpler), or bounding-box (simplest but least accurate).
   - Recommendation: Start with the visited-position-radius approach (mark all voxels within sensor range of visited positions as "observed"). This is computationally cheap and gives reasonable free-space estimates. Can upgrade to ray-casting later if frontier quality is poor. **This is Claude's discretion per CONTEXT.md.**

2. **DimOS A* adaptation for 3D + discrete actions**
   - What we know: DimOS A* operates on 2D OccupancyGrid with continuous cmd_vel output. SimWorld uses Discrete(6) actions.
   - What's unclear: Whether to plan in 3D or project to 2D for path planning.
   - Recommendation: Plan paths in 2D (project occupied voxels to XY ground plane for navigation grid). The robot moves on a ground plane -- 3D path planning adds complexity without benefit for ground locomotion. Use the existing WaypointRunner to convert path waypoints to discrete actions. **This is Claude's discretion per CONTEXT.md.**

3. **Coverage metric accuracy**
   - What we know: User wants coverage % reported periodically. Options are: frontier exhaustion ratio, bounding box coverage, or ground-truth comparison.
   - What's unclear: Whether SimWorld exposes ground-truth map data for comparison.
   - Recommendation: Use dual metric: (1) frontier exhaustion ratio (1 - remaining_frontier_voxels / initial_frontier_estimate) as the primary display metric, (2) bounding-box ratio as secondary metric. Both are computable without ground truth. **This is Claude's discretion per CONTEXT.md.**

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml (implicit) |
| Quick run command | `python -m pytest tests/ -x --timeout=30 -q` |
| Full suite command | `python -m pytest tests/ --timeout=60 -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXPL-01 | Frontier detection identifies boundary voxels between explored/unexplored space | unit | `python -m pytest tests/test_frontier_detector.py -x` | No -- Wave 0 |
| EXPL-01 | Frontier clustering filters noise (min cluster size) | unit | `python -m pytest tests/test_frontier_detector.py::test_min_cluster_filter -x` | No -- Wave 0 |
| EXPL-02 | Goal selector picks best frontier from ranked list | unit | `python -m pytest tests/test_goal_selector.py -x` | No -- Wave 0 |
| EXPL-02 | A* planner finds path on 2D grid (free/occupied/unknown) | unit | `python -m pytest tests/test_path_planner.py -x` | No -- Wave 0 |
| EXPL-02 | Exploration loop runs full cycle: detect -> select -> plan -> navigate | integration | `python -m pytest tests/test_exploration_loop.py -x --timeout=30` | No -- Wave 0 |
| EXPL-02 | Unreachable frontiers are skipped, next candidate tried | unit | `python -m pytest tests/test_exploration_loop.py::test_skip_unreachable -x` | No -- Wave 0 |
| EXPL-03 | Coverage tracker computes and reports % over time | unit | `python -m pytest tests/test_coverage_tracker.py -x` | No -- Wave 0 |
| EXPL-03 | Exploration terminates when zero reachable frontiers remain | integration | `python -m pytest tests/test_exploration_loop.py::test_termination -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x --timeout=30 -q`
- **Per wave merge:** `python -m pytest tests/ --timeout=60 -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_frontier_detector.py` -- covers EXPL-01 (frontier detection with synthetic voxel data)
- [ ] `tests/test_goal_selector.py` -- covers EXPL-02 (frontier ranking/selection)
- [ ] `tests/test_path_planner.py` -- covers EXPL-02 (A* on 2D grid)
- [ ] `tests/test_exploration_loop.py` -- covers EXPL-02, EXPL-03 (integration with mock bridge/SLAM)
- [ ] `tests/test_coverage_tracker.py` -- covers EXPL-03 (coverage computation)
- [ ] Update `tests/conftest.py` -- add fixtures for mock voxel grids, mock occupancy grids, mock exploration configs

## Sources

### Primary (HIGH confidence)
- DimOS `WavefrontFrontierExplorer` source code (`.venv/lib/.../dimos/navigation/frontier_exploration/wavefront_frontier_goal_selector.py`) -- wavefront BFS algorithm, frontier scoring, exploration loop pattern
- DimOS `ReplanningAStarPlanner` + `GlobalPlanner` source code (`.venv/lib/.../dimos/navigation/replanning_a_star/`) -- A* pathfinding, replanning triggers, stuck detection
- DimOS `OccupancyGrid` source code (`.venv/lib/.../dimos/msgs/nav_msgs/OccupancyGrid.py`) -- grid type definition, world/grid coordinate conversion, CostValues
- Project source: `src/slam/octomap_builder.py`, `src/bridge/sim_bridge.py`, `src/control/waypoint_runner.py` -- existing codebase patterns and APIs

### Secondary (MEDIUM confidence)
- `docs/simworld_discovery.md` -- SimWorld action space (Discrete(6)), step rate constraints (3-6 Hz), sensor data format

### Tertiary (LOW confidence)
- Coverage metric approaches -- based on standard robotics frontier exploration literature; specific formulas may need tuning based on runtime behavior

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use; no new dependencies
- Architecture: HIGH - patterns derived from reading actual DimOS source code + existing project code
- Pitfalls: HIGH - identified from concrete code analysis (OctoMapBuilder limitations, discrete action constraints, DimOS Module coupling)
- Frontier detection algorithm: MEDIUM - 3D voxel approach is novel for this project; DimOS reference is 2D. The 3D adaptation is straightforward but untested.
- Coverage metrics: MEDIUM - multiple approaches possible; no ground-truth comparison available to validate

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain; DimOS version locked in .venv)
