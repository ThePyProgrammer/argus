# Phase 14: Interactive ComfyUI-esque React Flow Pipeline Graph - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

A visual node-graph editor (ComfyUI-style) built with React Flow where users can customize the end-to-end SLAM pipeline by connecting processing nodes, swapping backends, inserting filters, and tuning parameters per node — all within the existing React C2 interface. The graph configuration maps to backend pipeline config via REST API. This phase builds the graph editor UI and the backend pipeline configuration system. Actual new processing nodes (beyond existing SLAM/merge backends) are implementation details, not new capabilities.

</domain>

<decisions>
## Implementation Decisions

### Graph node types & topology
- **Free-form node graph** — users can add, remove, and rewire nodes freely (not a fixed pipeline)
- **Four node categories:**
  1. **Core pipeline nodes** — Sensor Input (RGB-D + IMU), SLAM Backend (ICP, ORB-SLAM3, etc.), Map Merger (ICP Union, PGO), Visualization Output
  2. **Processing/filter nodes** — Point cloud filter, voxel downsample, coordinate transform, noise removal
  3. **Splitter/combiner nodes** — Split one stream to multiple consumers, combine multiple streams for parallel paths or multi-algorithm comparison
  4. **Custom parameter nodes** — Standalone tunable constants (like ComfyUI primitives) that feed values into downstream nodes via typed connections
- **Typed ports with visual hints** — each port has a data type (PointCloud, Pose, Image, Scalar). Only compatible types can connect. Incompatible ports gray out when dragging a connection. Colored sockets per type.
- **Auto-discover from registries** — SLAM backends and merge strategies auto-populate as available nodes from `SLAMRegistry` and `MergeRegistry`. New backends registered via decorators automatically appear in the node palette.

### Node parameter editing
- **Compact inline + detail panel** — nodes show 2-3 key params inline on the node body. Clicking/selecting a node opens a right-side inspector panel showing all parameters with full JSON Schema rendering (sliders, toggles).
- **Key params determined by schema metadata** — add a `primary: true` field to JSON Schema properties. Only primary-flagged params show inline on nodes. Requires updating backend PARAMETER_SCHEMA definitions.
- **Custom parameter nodes use typed connections** — a "voxel_size" parameter node has a Scalar output port. Connect it to any node's voxel_size input port. Visual, explicit. Overrides the node's own param value when connected.
- **Live-tunable vs startup-only distinction preserved** — same visual indicators as Phase 9 (lightning bolt for live, lock for startup-only). Live param changes send immediately via WebSocket. Startup-only changes require pipeline restart.

### Pipeline execution & persistence
- **Apply button triggers restart** — user edits graph freely, then hits "Apply Pipeline" to serialize the graph config and send it to the backend. Triggers `Coordinator.reset_for_restart()` with the new pipeline configuration. Same restart flow as Phase 8/9.
- **Named presets** — users save graph configs as named presets (e.g., "Fast ICP", "High-quality PGO"). Stored on backend as JSON files. Load from a dropdown. Ship with 2-3 built-in default presets.
- **JSON graph config format** — serialize as JSON: nodes array (type, id, params) + edges array (source_id:port → target_id:port). Backend has a PipelineBuilder that interprets this. Endpoint: `POST /api/pipeline/apply` with the JSON body.
- **Animated edges + node status while running** — edges animate (pulsing/flowing dots) when data passes through. Nodes show status badges (processing, idle, error). Throughput/frame rate shown on edges.

### Visual design & layout
- **Toggleable full-width panel** — a toggle button switches between "3D Viewer" and "Pipeline Editor" as the main content area. In editor mode, the graph takes the full hero space (~70%). Sidebar stays for context. Camera strip stays.
- **Node palette: sidebar + context menu** — collapsible left panel showing node categories (Sensors, SLAM Backends, Mergers, Filters). Drag nodes from palette onto canvas. Right-click on canvas also opens searchable add-node menu for quick access.
- **ComfyUI-style colored headers** — rectangular nodes with colored header bars per category (blue for sensors, green for SLAM, orange for mergers, purple for filters). Dark background canvas. Rounded ports on edges.
- **Minimap** — React Flow's built-in MiniMap component in bottom-right corner for graph navigation.

### Claude's Discretion
- React Flow configuration details (edge types, connection validation implementation)
- Exact port type color scheme and socket shapes
- Node layout algorithm (auto-layout on load vs manual placement only)
- Animation implementation for edge data flow
- Preset file storage location and naming convention
- PipelineBuilder architecture on the backend
- Graph validation error display (toast, inline, modal)
- Debounce strategy for live parameter updates from the graph
- Default presets content (which nodes, which connections)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing frontend
- `frontend/src/App.tsx` — Main app layout, hero/sidebar/camera strip structure
- `frontend/src/components/ControlPanel.tsx` — Current control panel with algorithm picker and params (Phase 9)
- `frontend/src/stores/slamStore.ts` — Zustand store for SLAM backends, active backend, parameters
- `frontend/src/stores/controlStore.ts` — Control state (start/stop, speed)
- `frontend/package.json` — Current deps: React 18, Three.js, Zustand 5 (no React Flow yet)

### Backend registries (auto-discovery source)
- `src/slam/registry.py` — SLAMRegistry with `list_backends()`, lazy loading, `@slam_backend` decorator
- `src/coordination/merge_registry.py` — MergeRegistry with `list_strategies()`, `@merge_strategy` decorator
- `src/slam/protocol.py` — SLAMProtocol with PARAMETER_SCHEMA and CAPABILITIES class attributes
- `src/coordination/merge_protocol.py` — MergeProtocol with same pattern

### REST API (to extend)
- `backend/web/slam_routes.py` — Existing SLAM + merge endpoints. Pipeline endpoints extend this or get own module.

### Restart mechanism
- `src/coordination/coordinator.py` — `Coordinator.reset_for_restart()` — pipeline restart flow

### Prior phase decisions
- `.planning/phases/09-frontend-algorithm-controls/09-CONTEXT.md` — Algorithm picker, param panel, JSON Schema rendering, slamStore design
- `.planning/phases/06-react-c2-web-interface-for-multi-robot-visualization-and-control/06-CONTEXT.md` — Dashboard layout, WebSocket architecture, Three.js setup

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `slamStore.ts`: Zustand store with `SLAMBackend` type, `fetchSlamState()`, parameter staging. Graph editor store can extend or compose with this.
- `ControlPanel.tsx`: JSON Schema parameter rendering (sliders, toggles, live-tunable indicators). The inspector panel can reuse this rendering logic.
- `ConfirmModal.tsx`: Existing modal component for confirmation dialogs. Reuse for "Apply Pipeline?" confirmation.
- `RestartOverlay.tsx`: Existing restart overlay with spinner. Reuse when applying pipeline config triggers restart.
- `SLAMRegistry.list_backends()` / `MergeRegistry.list_strategies()`: Return full backend info with capabilities and schemas. Node palette feeds from these.

### Established Patterns
- **Zustand stores**: Separate stores per concern (`controlStore`, `robotStore`, `slamStore`). Pipeline graph needs its own `pipelineStore.ts`.
- **REST for config, WebSocket for streaming**: Config changes (apply pipeline) go via REST. Live data flow status could stream via existing WebSocket.
- **JSON Schema for parameters**: All backend params declared as JSON Schema. Graph nodes inherit this pattern.
- **FastAPI static serving**: React build served as static files by FastAPI alongside WebSocket.

### Integration Points
- `App.tsx` main layout: Toggle between SceneViewer and PipelineEditor as hero content.
- `package.json`: Must add `@xyflow/react` (React Flow v12) as new dependency.
- `slam_routes.py` or new `pipeline_routes.py`: Pipeline apply/preset CRUD endpoints.
- `Coordinator`: Must accept pipeline config JSON and reconstruct pipeline accordingly.

</code_context>

<specifics>
## Specific Ideas

- The experience should feel like ComfyUI — dark canvas, colored node headers, drag-to-connect, animated edges showing data flow
- Node palette should feel browseable like a component library — categories with icons, search to filter
- Built-in presets should cover common use cases: "Default ICP" (current v1.0 pipeline), "PGO High Quality" (Open3D PGO merger + ICP SLAM), "Comparison Mode" (splitter feeding two SLAM backends in parallel)
- The "Apply Pipeline" button should be prominent and show a diff of what changed since last apply

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters*
*Context gathered: 2026-03-23*
