# Phase 6: React C2 Web Interface for Multi-Robot Visualization and Control - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

An integrated browser-based Command & Control (C2) interface in React.js that streams the 3D MuJoCo environment visualization, merged point cloud reconstruction, and per-robot camera feeds into a single web dashboard. Replaces the desktop Rerun + MuJoCo viewer with a unified web experience. Multi-robot generic — adapts dynamically to N robots without frontend code changes. Includes basic control (start/stop/speed) from the browser.

</domain>

<decisions>
## Implementation Decisions

### Dashboard Layout
- Mission control layout: large 3D viewer as hero (~70% of screen), right sidebar with robot status cards, collapsible camera feed strip at the bottom
- Single-page application, no tabs — everything visible at once
- Sidebar shows one status card per robot: colored dot (online/offline), name, coverage %, current action (exploring/idle/stuck), voxel count. Clicking a robot centers the 3D view on it
- Camera feed strip is collapsible with toggle — collapsed gives more room to 3D viewer, expanded shows all robot camera feeds side by side with horizontal scroll
- Control panel in sidebar: start/stop exploration, pause/resume, simulation speed slider

### 3D Rendering
- Three.js for in-browser 3D rendering with full orbit/zoom/pan interactivity
- MuJoCo office scene geometry (OBJ meshes + textures) exported and sent to client at startup — loaded once as static Three.js meshes
- Merged point cloud rendered natively as Three.js Points/BufferGeometry, updated via WebSocket
- Point cloud color mode: toggle between per-robot tinting (blue/orange/palette) and true RGB camera colors. Default is per-robot tinting
- Fading trajectory trails per robot in Three.js — same visual style as Phase 4 MuJoCo traces
- Robot positions shown as markers in the 3D scene (axis triads or colored spheres)

### Data Streaming Architecture
- WebSocket for all data transport (bidirectional — backend pushes data, frontend sends commands)
- FastAPI backend with native WebSocket support, serves React build as static files, runs alongside simulation in single process
- Camera feeds: JPEG-compressed frames sent as binary WebSocket messages (~30KB per frame at 320x240)
- Point cloud sync: hybrid delta + periodic full sync. Normal updates send only new voxels since last push. Full cloud sync every N seconds for robustness against missed messages
- Generic message envelope: all messages have `{type, robot_id?, payload}`. Types include: `robot_list`, `pose_update`, `cloud_delta`, `cloud_full`, `camera_frame`, `stats`, `command`

### Multi-Robot Genericity
- Dynamic robot registry: backend publishes robot list on WebSocket connect. All UI components (sidebar cards, camera feeds, 3D markers, trajectories) auto-generate from this list
- Adding a new robot = adding to the backend registry. No frontend code change needed
- Color assignment: curated 8-color colorblind-safe palette. Robot 1 = blue, Robot 2 = orange (backward compatible), Robot 3+ assigned sequentially from palette
- Camera strip uses horizontal scroll when many robots — each feed stays the same size, scroll to see more

### Claude's Discretion
- Three.js scene setup (lighting, camera defaults, orbit controls config)
- FastAPI WebSocket message serialization format (msgpack vs JSON for non-binary messages)
- React component architecture and state management (Context API vs Zustand vs Redux)
- Camera JPEG compression quality (balancing bandwidth vs visual quality)
- Point cloud delta tracking implementation (set diff vs timestamp-based)
- Full sync interval (every 5s, 10s, or based on cloud size)
- Scene mesh loading strategy (lazy vs eager, LOD levels)
- Exact colorblind-safe 8-color palette selection

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior visualization decisions
- `.planning/phases/04-visualization-and-integration/04-CONTEXT.md` — Phase 4 Rerun viz decisions (color scheme, layout patterns, update frequency, data flow)
- `.planning/phases/03-multi-robot-coordination-and-map-merging/03-CONTEXT.md` — Phase 3 multi-robot architecture (pLCM transport, MapMerger, Coordinator)

### Existing visualization code (reference implementations to replace)
- `src/viz/multi_robot_viz.py` — Current Rerun-based MultiRobotVisualizer (entity paths, data shapes, update pattern)
- `src/coordination/coordinator.py` — Coordinator.run() loop where viz.update() is called (integration point for web streaming)
- `src/bridge/multi_bridge.py` — MuJoCo bridge with render_overview() and viewer handle (data source for scene + cameras)

### Scene assets
- `dimos/data/mujoco_sim/scene_office1/` — Office OBJ meshes and textures that need to be served to Three.js
- `src/coordination/scene_builder.py` — Scene builder that produces XML + assets dict (knows where all mesh files are)

### Existing data types
- `src/bridge/sensor_types.py` — SensorFrame (rgb, depth, ground_truth_pose, sim_time)
- `src/coordination/multi_robot_config.py` — MultiRobotConfig (robot_ids, spawn_positions, resolution)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MultiRobotVisualizer` (src/viz/multi_robot_viz.py): Reference for what data to stream — merged_voxels, robot_data dict (frame, local_voxels, pose, trajectory, coverage_pct), stats
- `Coordinator.run()` loop: Integration point — currently calls viz.update() every 2 steps. Web streaming hooks in at the same point
- `MultiRobotBridge._capture_frame()`: Produces SensorFrame with RGB + depth per robot per step
- `OctoMapBuilder.get_occupied_voxels()`: Returns (N,3) float array of occupied voxel centers — the point cloud data to stream
- Office scene OBJ files in `dimos/data/mujoco_sim/scene_office1/office_split/` — ~1278 asset files to serve

### Established Patterns
- Configurable via dataclasses (MultiRobotConfig)
- Blue (66,133,244) / Orange (255,152,0) as first two robot colors
- Ground-truth pose from MuJoCo `cam_xpos` / `cam_xmat`
- 320x240 camera resolution
- Direct method calls from Coordinator to visualizer (will become WebSocket pushes)

### Integration Points
- FastAPI server needs to run alongside MuJoCo simulation (same process or threaded)
- WebSocket handler replaces direct viz.update() calls in Coordinator
- Static file serving for React build + OBJ scene meshes
- Control commands (start/stop/speed) from frontend need to reach Coordinator

</code_context>

<specifics>
## Specific Ideas

- "Treat it as an integrated Command & Control (C2) interface for easy control and visualisation of information from decentralised robotics"
- Mission control aesthetic — the 3D viewer is the centerpiece, everything else supports it
- Must work in a standard browser without plugins or desktop apps

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-react-c2-web-interface-for-multi-robot-visualization-and-control*
*Context gathered: 2026-03-18*
