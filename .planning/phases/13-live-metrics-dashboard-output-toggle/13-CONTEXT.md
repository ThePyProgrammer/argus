# Phase 13: Live Metrics Dashboard + Output Toggle - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can compare SLAM algorithm performance in real time and switch between visualization modes to inspect map quality. Algorithm picker, parameter tuning, and backend abstraction are prior phases. New SLAM backends are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Metrics panel placement & layout
- New bottom panel between 3D viewer and camera strip — dedicated horizontal panel row in the CSS Grid layout
- Per-robot columns: each robot gets a column with its metrics (ATE, RPE, ms/frame, tracking status), color-coded to match robot colors (blue/orange palette)
- Collapsible with toggle — expanded shows full table, collapsed shows a thin bar with key summary numbers (same pattern as camera strip)
- Tracking status uses colored dot indicators: green (#2ecc71) for OK, yellow (#f1c40f) for INITIALIZING/RELOCALIZING, red (#e74c3c) for LOST

### Baseline comparison display
- Sparkline charts showing metric history over time with ICP baseline as a horizontal reference line
- Baseline automatically captured from the most recent ICP session's final metrics — stored backend-side, resets when a new ICP session runs, no extra user action needed
- Toggle between two views in the metrics panel: "Live" (per-robot table) and "vs Baseline" (sparkline comparison) — only one visible at a time
- Sparklines show current values and percentage delta from baseline

### Output format toggle design
- Toggle buttons in the sidebar ControlPanel alongside existing scene mesh toggle and color mode toggle
- Three rendering modes: Point Cloud (existing Three.js Points), Voxel Grid (BoxGeometry cubes at voxel centers), Mesh (triangulated surface)
- Mesh reconstruction computed server-side using Open3D (Poisson or BPA), sends vertices + faces to frontend via WebSocket
- Fade transition when switching modes: old geometry fades out while new fades in over ~300ms cross-fade
- Instant mode switch (no session restart required)

### Metrics update frequency & data flow
- ATE/RPE: computed every 10 frames using rolling window of last 50 frames (expensive evo library computation)
- ms/frame: updates every frame from SLAMResult.metrics dict (near-zero overhead)
- Tracking status: updates every frame from SLAMResult.tracking_status
- Extend existing 'stats' WebSocket message with `slam_metrics` and `baseline` fields — no new message type
- Backend sends metric history arrays (ring buffer) with each update — survives page refresh, no frontend accumulation needed
- New dedicated `metricsStore.ts` Zustand store for metrics, baseline, view mode (live/baseline), output mode (cloud/voxel/mesh), and per-robot metric histories

### Claude's Discretion
- Sparkline rendering implementation (canvas, SVG, or CSS-based)
- Exact sparkline dimensions and styling
- Ring buffer size for metric history (suggest ~60 entries)
- Open3D mesh reconstruction algorithm choice (Poisson vs BPA)
- Mesh update frequency (every N seconds vs on-demand)
- Fade animation implementation (CSS transitions vs requestAnimationFrame)
- Voxel cube sizing relative to actual voxel_size parameter

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Metrics computation (backend)
- `src/metrics/drift_metrics.py` — ATE/RPE computation using evo library. Takes slam_poses, gt_poses, timestamps. Returns ate_rmse, ate_mean, rpe_rmse, rpe_mean
- `src/metrics/ground_truth.py` — Ground truth pose extraction from MuJoCo
- `src/slam/protocol.py` — SLAMResult dataclass with `metrics: dict` and `tracking_status: TrackingStatus` enum (OK/LOST/INITIALIZING/RELOCALIZING)

### Existing WebSocket stats pipeline
- `frontend/src/utils/messageTypes.ts` — WSMessage type union, StatsPayload interface
- `frontend/src/hooks/useWebSocket.ts` — Stats message handler dispatching to robotStore
- `frontend/src/stores/robotStore.ts` — updateStats() method consuming StatsPayload

### Frontend infrastructure (Phase 9)
- `frontend/src/stores/slamStore.ts` — Existing SLAM Zustand store (backends, active, params, restart state)
- `frontend/src/components/ControlPanel.tsx` — Where output format toggle buttons will be added
- `frontend/src/components/SceneViewer.tsx` — Three.js viewer with PointCloudManager, needs voxel and mesh rendering
- `frontend/src/components/PointCloud.ts` — Existing point cloud Three.js manager
- `frontend/src/App.tsx` — CSS Grid layout that needs a new metrics row
- `frontend/src/App.css` — Grid area definitions

### Phase 9 context
- `.planning/phases/09-frontend-algorithm-controls/09-CONTEXT.md` — slamStore, dark theme, inline styles, WebSocket sendRaw pattern, collapsible sections

### Phase 6 context
- `.planning/phases/06-react-c2-web-interface-for-multi-robot-visualization-and-control/06-CONTEXT.md` — Mission control layout, CSS Grid, Zustand, WebSocket transport

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `drift_metrics.py`: Already computes ATE/RPE — just needs to be called periodically and results forwarded to frontend
- `SLAMResult.metrics`: Per-frame dict already carries timing data from backends — just needs to be streamed
- `StatsPayload` + `updateStats()`: Existing stats WebSocket pipeline — extend with slam_metrics fields
- `PointCloudManager`: Existing Three.js point cloud rendering — base for cloud mode, reference for voxel/mesh managers
- `ControlPanel.tsx`: Existing toggle buttons (scene mesh, color mode) — same pattern for output format toggle
- Colorblind-safe palette in `palette.ts`: Robot colors for per-robot column headers

### Established Patterns
- **Zustand stores**: Flat state + setters (controlStore, robotStore, slamStore). New metricsStore follows same pattern
- **Dark theme**: #1a1a3e background, #2a2a4a borders, #888/#aaa text, #2ecc71 accent
- **Inline styles**: All components use React inline styles
- **WebSocket message dispatch**: Switch on msg.type in useWebSocket.ts, dispatch to appropriate store
- **Collapsible sections**: Click-to-toggle with arrow indicators
- **CSS Grid layout**: App.tsx uses named grid areas (viewer, sidebar, cameras)

### Integration Points
- `App.tsx` / `App.css`: Add new grid row for metrics panel between viewer and cameras
- `useWebSocket.ts`: Extend stats handler to dispatch slam_metrics to metricsStore
- `ControlPanel.tsx`: Add output format toggle buttons
- `SceneViewer.tsx`: Add VoxelManager and MeshManager alongside PointCloudManager, switch based on output mode
- Backend `push_loop` or coordinator: Compute drift metrics every 10 frames, include in stats message

</code_context>

<specifics>
## Specific Ideas

- Sparkline charts should feel like GitHub contribution graphs or stock ticker micro-charts — compact, information-dense, dark-themed
- The metrics panel should feel like a flight telemetry strip — dense, real-time numbers updating live
- Fade transition between rendering modes gives a polished feel without being slow

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-live-metrics-dashboard-output-toggle*
*Context gathered: 2026-03-23*
