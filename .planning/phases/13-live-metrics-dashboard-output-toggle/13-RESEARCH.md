# Phase 13: Live Metrics Dashboard + Output Toggle - Research

**Researched:** 2026-03-23
**Domain:** Real-time metrics dashboard (React/Zustand/WebSocket), Three.js multi-mode rendering, Open3D mesh reconstruction
**Confidence:** HIGH

## Summary

This phase adds three capabilities to the existing C2 web interface: (1) a live metrics panel showing ATE, RPE, ms/frame, and tracking status per robot, (2) a baseline comparison view with sparkline charts showing current algorithm vs ICP baseline, and (3) an output format toggle switching the Three.js viewer between point cloud, voxel grid, and mesh rendering modes.

The existing architecture is well-suited for this work. The backend already computes drift metrics via the `evo` library (`drift_metrics.py`), already streams per-frame timing data in `SLAMResult.metrics`, and already broadcasts stats via WebSocket through `WebStreamingViz._update_stats()`. The frontend already has the Zustand store pattern, WebSocket dispatch switch, CSS Grid layout, and inline styling conventions established. The primary engineering challenge is (a) computing metrics periodically on the backend without blocking the coordination loop, (b) efficiently rendering voxel grids via Three.js InstancedMesh, and (c) server-side mesh reconstruction via Open3D with reasonable latency.

**Primary recommendation:** Extend the existing `stats` WebSocket message with `slam_metrics` and `baseline` fields rather than creating new message types. Use Three.js `InstancedMesh` with `BoxGeometry` for voxel rendering. Use Open3D Poisson reconstruction for mesh generation. Build sparklines as raw SVG `<polyline>` elements (zero dependencies).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- New bottom panel between 3D viewer and camera strip -- dedicated horizontal panel row in CSS Grid layout
- Per-robot columns: each robot gets a column with its metrics (ATE, RPE, ms/frame, tracking status), color-coded to match robot colors (blue/orange palette)
- Collapsible with toggle -- expanded shows full table, collapsed shows a thin bar with key summary numbers (same pattern as camera strip)
- Tracking status uses colored dot indicators: green (#2ecc71) for OK, yellow (#f1c40f) for INITIALIZING/RELOCALIZING, red (#e74c3c) for LOST
- Sparkline charts showing metric history over time with ICP baseline as a horizontal reference line
- Baseline automatically captured from most recent ICP session's final metrics -- stored backend-side, resets when a new ICP session runs, no extra user action needed
- Toggle between two views in metrics panel: "Live" (per-robot table) and "vs Baseline" (sparkline comparison) -- only one visible at a time
- Toggle buttons in the sidebar ControlPanel alongside existing scene mesh toggle and color mode toggle
- Three rendering modes: Point Cloud (existing Three.js Points), Voxel Grid (BoxGeometry cubes at voxel centers), Mesh (triangulated surface)
- Mesh reconstruction computed server-side using Open3D (Poisson or BPA), sends vertices + faces to frontend via WebSocket
- Fade transition when switching modes: old geometry fades out while new fades in over ~300ms cross-fade
- Instant mode switch (no session restart required)
- ATE/RPE: computed every 10 frames using rolling window of last 50 frames (expensive evo library computation)
- ms/frame: updates every frame from SLAMResult.metrics dict (near-zero overhead)
- Tracking status: updates every frame from SLAMResult.tracking_status
- Extend existing 'stats' WebSocket message with slam_metrics and baseline fields -- no new message type
- Backend sends metric history arrays (ring buffer) with each update -- survives page refresh, no frontend accumulation needed
- New dedicated metricsStore.ts Zustand store for metrics, baseline, view mode (live/baseline), output mode (cloud/voxel/mesh), and per-robot metric histories

### Claude's Discretion
- Sparkline rendering implementation (canvas, SVG, or CSS-based)
- Exact sparkline dimensions and styling
- Ring buffer size for metric history (suggest ~60 entries)
- Open3D mesh reconstruction algorithm choice (Poisson vs BPA)
- Mesh update frequency (every N seconds vs on-demand)
- Fade animation implementation (CSS transitions vs requestAnimationFrame)
- Voxel cube sizing relative to actual voxel_size parameter

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CTRL-05 | Live metrics dashboard shows ATE, RPE, processing time (ms/frame), and tracking status per robot | Backend drift_metrics.py already computes ATE/RPE; SLAMResult.metrics carries timing; extend stats WS message; new metricsStore + MetricsPanel component |
| CTRL-06 | Metrics comparison view shows current algorithm vs baseline ICP side-by-side | Backend stores baseline from last ICP session; sparkline SVG with horizontal reference line; "vs Baseline" view toggle in metrics panel |
| CTRL-07 | Output format toggle switches Three.js viewer between point cloud, voxel grid, and mesh rendering modes | PointCloudManager exists; new VoxelManager (InstancedMesh), MeshManager (BufferGeometry); Open3D Poisson server-side; toggle in ControlPanel |

</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^18.3.1 | UI components | Already in project, functional component pattern |
| Zustand | ^5.0.0 | State management | Already used for robotStore, slamStore, controlStore |
| Three.js | ^0.170.0 | 3D rendering | Already in project for point cloud/scene viewer |
| FastAPI | >=0.100.0 | Backend HTTP/WS | Already in project, WebSocket push loop pattern |
| evo | >=1.0.0 | Trajectory metrics | Already in project, drift_metrics.py uses it |
| Open3D | >=0.18.0 | Mesh reconstruction | Already in pyproject.toml dependencies |

### Supporting (no new deps needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SVG (built-in) | N/A | Sparkline charts | Inline SVG polyline for metric history |
| collections.deque | stdlib | Ring buffer | Server-side metric history accumulation |
| numpy | >=1.26.0 | Array operations | Mesh vertex/face serialization |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw SVG sparklines | react-sparklines npm | Adds dependency for trivial feature; raw SVG is ~30 lines |
| InstancedMesh voxels | Merged BoxGeometry | InstancedMesh has 1 draw call vs N; critical for 10K+ voxels |
| Open3D Poisson | Open3D BPA | Poisson is more robust with noisy data; BPA needs careful radius tuning |

**Installation:** No new packages needed. All libraries already in project dependencies.

## Architecture Patterns

### Backend Metrics Pipeline

```
ExplorationLoop.step_once()
  -> SLAMResult (per-frame: metrics dict + tracking_status)
  -> Coordinator._send_viz_update() [every 10 frames]
    -> WebStreamingViz._update_stats()
      -> NEW: Compute drift metrics every 10 frames
      -> NEW: Include slam_metrics + baseline in stats message
      -> push_loop broadcasts to frontend
```

### Frontend Data Flow

```
WebSocket 'stats' message
  -> useWebSocket.ts (case 'stats')
    -> NEW: dispatch slam_metrics to metricsStore
    -> existing: dispatch stats to robotStore
  -> metricsStore.ts (new Zustand store)
    -> MetricsPanel subscribes (live view)
    -> MetricsPanel subscribes (baseline comparison)
  -> metricsStore.outputMode -> SceneViewer switches render manager
```

### Recommended New File Structure
```
frontend/src/
  stores/
    metricsStore.ts          # NEW: slam metrics, baseline, view/output modes
  components/
    MetricsPanel.tsx         # NEW: bottom panel with live + baseline views
    Sparkline.tsx            # NEW: SVG sparkline component
    VoxelManager.ts          # NEW: InstancedMesh voxel rendering
    MeshManager.ts           # NEW: BufferGeometry mesh rendering
backend/web/
  streaming_viz.py           # EXTEND: add slam_metrics to stats message
src/metrics/
  drift_metrics.py           # EXISTS: compute_drift_metrics()
  ground_truth.py            # EXISTS: GroundTruthCollector
  metrics_tracker.py         # NEW: per-robot ring buffer + baseline storage
```

### Pattern 1: metricsStore (Zustand flat state + setters)
**What:** Dedicated store for SLAM metrics, baseline data, view mode, and output mode
**When to use:** All metrics-related state
**Example:**
```typescript
// Follows existing slamStore/controlStore flat pattern
interface MetricsStoreState {
  // Per-robot live metrics
  perRobot: Record<string, RobotMetrics>;
  // Baseline from last ICP session
  baseline: BaselineMetrics | null;
  // View mode: "live" or "baseline"
  viewMode: 'live' | 'baseline';
  // Output rendering mode
  outputMode: 'cloud' | 'voxel' | 'mesh';
  // Per-robot metric history arrays (ring buffers sent by backend)
  history: Record<string, MetricHistory>;
  // Mesh data from server
  meshVertices: number[][] | null;
  meshFaces: number[][] | null;

  updateMetrics: (robotId: string, metrics: RobotMetrics) => void;
  setBaseline: (baseline: BaselineMetrics) => void;
  setViewMode: (mode: 'live' | 'baseline') => void;
  setOutputMode: (mode: 'cloud' | 'voxel' | 'mesh') => void;
  updateHistory: (robotId: string, history: MetricHistory) => void;
  setMeshData: (vertices: number[][], faces: number[][]) => void;
}
```

### Pattern 2: VoxelManager (InstancedMesh)
**What:** Renders voxel cubes using Three.js InstancedMesh for single-draw-call performance
**When to use:** When output mode is 'voxel'
**Example:**
```typescript
// Same imperative pattern as PointCloudManager
class VoxelManager {
  private mesh: THREE.InstancedMesh;
  private dummy = new THREE.Object3D();
  private maxVoxels = 200_000;

  constructor(scene: THREE.Object3D, voxelSize: number = 0.1) {
    const geometry = new THREE.BoxGeometry(voxelSize, voxelSize, voxelSize);
    const material = new THREE.MeshLambertMaterial({ vertexColors: false });
    this.mesh = new THREE.InstancedMesh(geometry, material, this.maxVoxels);
    this.mesh.count = 0;
    scene.add(this.mesh);
  }

  updateFull(positions: number[][], colors?: number[][]): void {
    const count = Math.min(positions.length, this.maxVoxels);
    for (let i = 0; i < count; i++) {
      this.dummy.position.set(positions[i][0], positions[i][1], positions[i][2]);
      this.dummy.updateMatrix();
      this.mesh.setMatrixAt(i, this.dummy.matrix);
      if (colors?.[i]) {
        this.mesh.setColorAt(i, new THREE.Color(
          colors[i][0] / 255, colors[i][1] / 255, colors[i][2] / 255
        ));
      }
    }
    this.mesh.count = count;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }
}
```

### Pattern 3: Server-side MetricsTracker
**What:** Accumulates per-robot metrics in ring buffers, manages baseline storage
**When to use:** Called from coordinator's viz update path
**Example:**
```python
from collections import deque

class MetricsTracker:
    """Per-robot SLAM metrics accumulator with baseline storage."""

    def __init__(self, history_size: int = 60):
        self._history_size = history_size
        self._per_robot: dict[str, deque] = {}
        self._frame_counts: dict[str, int] = {}
        self._baseline: dict | None = None  # Last ICP session final metrics

    def record_frame(self, robot_id: str, slam_result_metrics: dict,
                     tracking_status: str) -> None:
        """Record per-frame metrics (ms/frame, tracking_status)."""
        if robot_id not in self._per_robot:
            self._per_robot[robot_id] = deque(maxlen=self._history_size)
            self._frame_counts[robot_id] = 0
        self._frame_counts[robot_id] += 1

    def record_drift(self, robot_id: str, ate_rmse: float, rpe_rmse: float) -> None:
        """Record drift metrics computed every N frames."""
        entry = {
            "ate_rmse": ate_rmse,
            "rpe_rmse": rpe_rmse,
            "timestamp": time.monotonic(),
        }
        self._per_robot[robot_id].append(entry)

    def capture_baseline(self) -> None:
        """Snapshot current metrics as baseline (called when ICP session ends)."""
        ...

    def get_stats_payload(self) -> dict:
        """Return slam_metrics + baseline for stats WS message."""
        ...
```

### Anti-Patterns to Avoid
- **Frontend-side metric accumulation:** The user explicitly decided backend sends history arrays. Do NOT accumulate metrics in the frontend -- the ring buffer lives server-side and survives page refresh.
- **New WebSocket message type for metrics:** The user decided to extend the existing 'stats' message. Do NOT create a 'slam_metrics' message type.
- **Individual BoxGeometry per voxel:** This creates N draw calls. Always use InstancedMesh for voxel rendering.
- **Blocking mesh reconstruction in the coordination loop:** Open3D Poisson reconstruction is CPU-intensive (~100-500ms for 10K points). Run it asynchronously or on a timer, not on every frame.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ATE/RPE computation | Custom trajectory error math | evo library (already integrated) | Handles SE3 alignment, time sync, multiple statistical metrics |
| Mesh reconstruction | Triangle mesh from scratch | Open3D Poisson reconstruction | Handles normals, octree, regularization, density filtering |
| Voxel instancing | Manual matrix buffer | Three.js InstancedMesh | Built-in instance matrix management, GPU instancing |
| Ring buffer | Custom circular array | collections.deque(maxlen=N) | Thread-safe append, automatic eviction, stdlib |
| Normal estimation | Manual cross-product normals | Open3D estimate_normals() | KNN-based, orientation propagation, handles noise |

**Key insight:** Every computationally expensive operation in this phase (drift metrics, mesh reconstruction, normal estimation) has a battle-tested library already in the dependency tree. The engineering work is wiring them together and managing update frequencies.

## Common Pitfalls

### Pitfall 1: evo computation blocks the coordination loop
**What goes wrong:** `compute_drift_metrics()` with 50 pose pairs takes 5-20ms. If called every frame, it halves the simulation throughput.
**Why it happens:** The evo library does SE3 alignment and trajectory synchronization which is non-trivial.
**How to avoid:** Compute every 10 frames (user decision). Cache the last result for intermediate frames. The existing viz update already runs every 10 steps in `coordinator.run()`.
**Warning signs:** Simulation FPS drops when metrics dashboard is active.

### Pitfall 2: InstancedMesh color not updating
**What goes wrong:** Voxels render but all appear the same color.
**Why it happens:** `InstancedMesh` requires `instanceColor` to be flagged as needing update, AND requires `vertexColors: false` on the material (since instanced colors are per-instance, not per-vertex).
**How to avoid:** After calling `setColorAt()`, set `mesh.instanceColor.needsUpdate = true`. The material must NOT have `vertexColors: true`.
**Warning signs:** All cubes are the same default material color.

### Pitfall 3: Open3D Poisson needs normals
**What goes wrong:** `create_from_point_cloud_poisson()` returns empty mesh.
**Why it happens:** Both Poisson and BPA require the input PointCloud to have normals. Without normals, the method silently produces nothing.
**How to avoid:** Always call `pcd.estimate_normals()` before surface reconstruction. Orient normals consistently with `pcd.orient_normals_consistent_tangent_plane()`.
**Warning signs:** Mesh with 0 triangles returned from Open3D.

### Pitfall 4: Mesh data serialization size
**What goes wrong:** WebSocket message with 50K vertices and 100K faces is 10+ MB JSON.
**Why it happens:** Naively serializing numpy arrays as nested Python lists creates massive JSON.
**How to avoid:** Flatten vertex/face arrays, send as a compact format (flat arrays with stride), or use binary WebSocket encoding. Consider sending mesh only on demand or throttled (every 5-10 seconds).
**Warning signs:** WebSocket messages taking >100ms to serialize or >50ms network time.

### Pitfall 5: CSS Grid row insertion breaks layout
**What goes wrong:** Adding a new grid row between viewer and cameras misaligns the layout.
**Why it happens:** Current grid uses `grid-template-rows: 1fr auto`. Adding a row between requires careful grid-row assignments on all children.
**How to avoid:** Change to 3-row grid: `grid-template-rows: 1fr auto auto`. New metrics panel is row 2, cameras become row 3. Viewer stays row 1. Sidebar spans rows 1-2.
**Warning signs:** Metrics panel overlaps viewer or cameras scroll offscreen.

### Pitfall 6: Fade transition on Three.js objects
**What goes wrong:** opacity transition is jumpy or objects flicker during mode switch.
**Why it happens:** Three.js materials need `transparent: true` for opacity < 1. Changing opacity requires `material.needsUpdate` in some cases. Two overlapping semi-transparent objects cause z-fighting.
**How to avoid:** Use `requestAnimationFrame` loop for smooth fade. Set `material.transparent = true` and `material.depthWrite = false` during fade-out (prevents z-fighting). Re-enable depthWrite when fully opaque.
**Warning signs:** Visual artifacts when two rendering modes overlap during transition.

## Code Examples

### Extended StatsPayload (frontend type)
```typescript
// Extend existing StatsPayload in messageTypes.ts
export interface SlamMetrics {
  ate_rmse: number;
  ate_mean: number;
  rpe_rmse: number;
  rpe_mean: number;
  ms_per_frame: number;
  tracking_status: string;
}

export interface StatsPayload {
  total_coverage: number;
  merge_count: number;
  elapsed: number;
  robots: Record<string, { coverage_pct: number; voxel_count: number; action: string }>;
  // NEW fields
  slam_metrics?: Record<string, SlamMetrics>;
  baseline?: Record<string, SlamMetrics> | null;
  metric_history?: Record<string, {
    ate_rmse: number[];
    rpe_rmse: number[];
    ms_per_frame: number[];
    timestamps: number[];
  }>;
}
```

### SVG Sparkline Component (zero dependencies)
```typescript
// Recommendation: raw SVG polyline, no library needed
interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  baselineValue?: number;
  baselineColor?: string;
}

function Sparkline({ data, width = 120, height = 30, color = '#2ecc71',
                     baselineValue, baselineColor = '#555' }: SparklineProps) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1);

  const points = data.map((v, i) =>
    `${i * step},${height - ((v - min) / range) * height}`
  ).join(' ');

  // Baseline horizontal line
  const baseY = baselineValue != null
    ? height - ((baselineValue - min) / range) * height
    : null;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {baseY != null && (
        <line x1={0} y1={baseY} x2={width} y2={baseY}
              stroke={baselineColor} strokeWidth={1} strokeDasharray="3,2" />
      )}
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
    </svg>
  );
}
```

### Backend Metrics Integration Point
```python
# In WebStreamingViz._update_stats() -- extend existing method
def _update_stats(self, robot_data, total_coverage, merge_count):
    elapsed = time.monotonic() - self._start_time
    robots = {}
    slam_metrics = {}

    for rid, data in robot_data.items():
        robots[rid] = {
            "coverage_pct": data.get("coverage_pct", 0.0),
            "voxel_count": len(data.get("local_voxels", [])),
            "action": "exploring",
        }
        # NEW: Include SLAM metrics from metrics_tracker
        if self._metrics_tracker:
            slam_metrics[rid] = self._metrics_tracker.get_robot_metrics(rid)

    self._message_queue.append({
        "type": STATS,
        "payload": {
            "total_coverage": total_coverage,
            "merge_count": merge_count,
            "elapsed": elapsed,
            "robots": robots,
            # NEW fields
            "slam_metrics": slam_metrics,
            "baseline": self._metrics_tracker.baseline if self._metrics_tracker else None,
            "metric_history": self._metrics_tracker.get_histories() if self._metrics_tracker else None,
        },
    })
```

### Open3D Mesh Reconstruction
```python
import open3d as o3d
import numpy as np

def reconstruct_mesh(points: np.ndarray, colors: np.ndarray | None = None,
                     depth: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct triangle mesh from point cloud using Poisson reconstruction.

    Args:
        points: (N, 3) float64 point positions.
        colors: Optional (N, 3) float64 colors [0-1].
        depth: Octree depth for Poisson reconstruction (7-9 typical).

    Returns:
        (vertices, faces) as (V, 3) and (F, 3) numpy arrays.
    """
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    if colors is not None:
        pcd.colors = o3d.utility.Vector3dVector(colors)

    # Normals required for both Poisson and BPA
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(
        radius=0.2, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(k=15)

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth)

    # Remove low-density vertices (cleanup)
    densities = np.asarray(densities)
    vertices_to_remove = densities < np.quantile(densities, 0.01)
    mesh.remove_vertices_by_mask(vertices_to_remove)

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    return vertices, faces
```

### CSS Grid Layout Update
```css
/* Updated App.css: 3-row grid */
.app-container {
  display: grid;
  grid-template-columns: 1fr 320px;
  grid-template-rows: 1fr auto auto;  /* viewer | metrics | cameras */
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.viewer-area { grid-column: 1; grid-row: 1; }
.sidebar-area { grid-column: 2; grid-row: 1 / 3; }  /* spans viewer + metrics */
.metrics-area { grid-column: 1; grid-row: 2; }
.camera-strip-area { grid-column: 1 / -1; grid-row: 3; }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Individual geometries per voxel | InstancedMesh (1 draw call) | Three.js r123 (2021) | 100x fewer draw calls for voxel grids |
| Alpha shapes for mesh | Poisson/BPA in Open3D | Open3D 0.10+ (2020) | Robust mesh from noisy point clouds |
| Frontend metric accumulation | Server-side ring buffer | User decision (this phase) | Survives page refresh, single source of truth |
| Separate metric WS messages | Extended stats payload | User decision (this phase) | Fewer message types, backward compatible |

**Deprecated/outdated:**
- Three.js `Geometry` class: Removed in r125. Use `BufferGeometry` exclusively.
- Open3D `create_from_point_cloud_alpha_shape`: Still available but Poisson is preferred for noisy SLAM data.

## Open Questions

1. **Open3D availability in runtime environment**
   - What we know: `open3d>=0.18.0` is in pyproject.toml dependencies but was not importable during research (likely not installed in current venv).
   - What's unclear: Whether it will be available at runtime. The merge strategies already reference Open3D (pgo_open3d).
   - Recommendation: Follow the project's `AVAILABLE` class attribute pattern (like ORB-SLAM3 backend). If Open3D is unavailable, mesh mode is simply disabled with a tooltip explaining why. The existing `try/import, _AVAILABLE flag, ImportError in __init__` pattern handles this.

2. **Mesh reconstruction latency budget**
   - What we know: Poisson at depth=7 takes ~100-500ms for 10K points on CPU. The viz update runs every 10 frames.
   - What's unclear: Whether ~200ms mesh reconstruction every 10 frames will cause noticeable stutter.
   - Recommendation: Run mesh reconstruction on a separate thread (or every 5-10 seconds throttled), never in the coordination loop critical path. Frontend shows stale mesh between updates.

3. **Metric history payload size**
   - What we know: 60-entry ring buffer x 4 metrics x 2 robots = ~480 floats per stats message.
   - What's unclear: Whether including full history arrays in every stats message (every 10 frames) creates measurable overhead.
   - Recommendation: 480 floats is ~4KB JSON, negligible compared to existing cloud_delta messages (10K+ points). Include in every stats message as decided.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 + pytest-asyncio >=0.23.0 |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/web/ tests/slam/test_drift_metrics.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-05 | Stats message includes slam_metrics per robot | unit | `pytest tests/web/test_streaming_viz.py -x -q -k slam_metrics` | Wave 0 (extend) |
| CTRL-05 | MetricsTracker accumulates per-frame and drift metrics | unit | `pytest tests/web/test_metrics_tracker.py -x -q` | Wave 0 |
| CTRL-06 | Baseline captured from ICP session, included in stats | unit | `pytest tests/web/test_metrics_tracker.py -x -q -k baseline` | Wave 0 |
| CTRL-07 | Mesh reconstruction endpoint returns vertices + faces | unit | `pytest tests/web/test_mesh_reconstruction.py -x -q` | Wave 0 |
| CTRL-07 | Mesh reconstruction handles missing Open3D gracefully | unit | `pytest tests/web/test_mesh_reconstruction.py -x -q -k unavailable` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/web/ tests/slam/test_drift_metrics.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/web/test_metrics_tracker.py` -- covers MetricsTracker ring buffer, baseline capture, history serialization
- [ ] `tests/web/test_mesh_reconstruction.py` -- covers Open3D mesh generation, graceful degradation
- [ ] Extend `tests/web/test_streaming_viz.py` -- add test for slam_metrics in stats payload

*(Existing test infrastructure: pytest.ini configured, tests/web/ directory exists with test_streaming_viz.py and test_web_server.py)*

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection: `src/metrics/drift_metrics.py`, `src/slam/protocol.py`, `backend/web/streaming_viz.py`, `backend/web/server.py`, `frontend/src/stores/slamStore.ts`, `frontend/src/components/SceneViewer.tsx`, `frontend/src/components/PointCloud.ts`
- Open3D official docs: [Surface reconstruction tutorial](https://www.open3d.org/docs/release/tutorial/geometry/surface_reconstruction.html) -- Poisson and BPA API signatures verified
- Three.js official docs: InstancedMesh, BoxGeometry, BufferGeometry -- verified via project's installed three@0.170.0

### Secondary (MEDIUM confidence)
- [Codrops: Building Efficient Three.js Scenes](https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/) -- InstancedMesh best practices
- [Three.js forum: InstancedMesh vs InstancedBufferGeometry](https://discourse.threejs.org/t/instancedmesh-vs-instancedbuffergeometry/31058) -- performance comparison
- [Codrops: Turning 3D Models to Voxel Art with Three.js](https://tympanus.net/codrops/2023/03/28/turning-3d-models-to-voxel-art-with-three-js/) -- voxel rendering patterns

### Tertiary (LOW confidence)
- [fnando/sparkline GitHub](https://github.com/fnando/sparkline) -- zero-dependency SVG sparkline pattern (used as reference, not as dependency)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, APIs verified against codebase
- Architecture: HIGH -- extends proven patterns (Zustand stores, WS message dispatch, imperative Three.js managers)
- Pitfalls: HIGH -- derived from direct codebase analysis and verified Three.js/Open3D documentation
- Mesh reconstruction: MEDIUM -- Open3D Poisson API verified in docs but latency estimates are approximate (depends on point cloud density and hardware)

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable libraries, no fast-moving APIs)
