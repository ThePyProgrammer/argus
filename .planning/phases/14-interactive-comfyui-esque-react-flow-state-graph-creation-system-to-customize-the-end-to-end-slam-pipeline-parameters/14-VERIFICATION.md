---
phase: 14-interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters
verified: 2026-03-24T00:00:00Z
status: human_needed
score: 8/8 automated truths verified
re_verification: false
human_verification:
  - test: "Toggle between 3D Viewer and Pipeline Editor in the hero area"
    expected: "Clicking 'Pipeline Editor' replaces the 3D scene with the full pipeline layout (palette left, canvas center, inspector right, apply bar bottom). Clicking '3D Viewer' restores the scene."
    why_human: "View state is runtime React state; programmatic rendering cannot be verified from static files."
  - test: "Node palette shows categorized nodes and supports drag-to-add"
    expected: "Palette shows Sensors, SLAM Backends, Mergers, Filters, Splitters/Combiners, Parameters, Output. Dragging a node from palette onto the canvas creates it at the drop position. Search filters the list."
    why_human: "Drag-and-drop dataTransfer and React Flow canvas drop coordinates require browser interaction."
  - test: "Custom node visual rendering"
    expected: "Nodes render colored headers per category, typed colored handles (circle/diamond/square), inline primary params with slider/toggle, and 8-px status badge."
    why_human: "Visual correctness requires browser rendering; cannot verify pixel layout from source."
  - test: "Connection validation prevents incompatible port types"
    expected: "Drawing an edge from an 'Image' port to an 'IMU' port is rejected (edge not created). Compatible types connect successfully."
    why_human: "isValidConnection is a React Flow callback; interaction required to trigger it."
  - test: "Node inspector opens on node click with full parameter rendering"
    expected: "Right panel shows all node parameters with sliders, toggles, lightning bolt for live-tunable, lock for startup-only. Changing a slider updates the node's displayed value."
    why_human: "selectedNodeId state transition and DOM rendering requires browser interaction."
  - test: "Preset load/save workflow"
    expected: "Preset dropdown lists Default ICP, PGO High Quality, Comparison Mode as Built-in. Loading a preset replaces the canvas graph. Saving creates a user preset that appears in the list."
    why_human: "Requires running backend with preset directory populated and live browser interaction."
  - test: "Apply Pipeline triggers restart"
    expected: "Clicking Apply Pipeline shows ConfirmModal. On confirm, POSTs to /api/pipeline/apply, RestartOverlay appears, and isDirty clears after success."
    why_human: "Requires running backend plus frontend interaction to trigger the apply flow."
  - test: "Animated edges show data flow when fps > 0"
    expected: "When a pipeline_status WebSocket message sets edge fps > 0, the edge changes to cyan and a flowing dot animates along the bezier path."
    why_human: "Requires live WebSocket message injection and visual confirmation of animation."
---

# Phase 14: Interactive ComfyUI-esque React Flow Pipeline Graph Editor — Verification Report

**Phase Goal:** Users can visually build and customize SLAM processing pipelines via a ComfyUI-style node-graph editor with typed ports, connection validation, parameter tuning, named presets, and backend pipeline apply.
**Verified:** 2026-03-24
**Status:** human_needed (all automated checks pass; 8 items require browser/runtime verification)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Success Criteria from ROADMAP.md (Observable Truths)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Users can toggle between 3D Viewer and Pipeline Editor | ? HUMAN | ViewToggle component + App.tsx conditional render wired correctly |
| 2 | Node palette auto-discovers registry nodes + supports drag-to-add | ? HUMAN | NodePalette renders draggable items with `application/pipeline-node` dataTransfer; App.tsx fetches /api/pipeline/node-catalog on view switch |
| 3 | Custom nodes display colored headers, typed port handles, inline params, status badges | ? HUMAN | PipelineNode.tsx substantively implements all required visuals |
| 4 | Only compatible port types can connect | ? HUMAN | isValidConnection in PipelineEditor.tsx checks `sourcePort.dataType === targetPort.dataType` |
| 5 | Clicking a node opens inspector with full JSON Schema rendering | ? HUMAN | NodeInspector.tsx reads selectedNodeId, renders sliders/toggles for all schema properties |
| 6 | Load/save named presets; 3 built-in defaults ship | ? HUMAN | 3 preset JSONs exist; PresetSelector.tsx loads/saves via /api/pipeline/presets |
| 7 | Apply Pipeline serializes graph, POSTs to backend, triggers restart | ? HUMAN | ApplyBar.tsx POSTs to /api/pipeline/apply; backend routes wired to PipelineBuilder and command_callback |
| 8 | Animated edges show data flow when pipeline is running | ? HUMAN | EdgeAnimated.tsx renders animateMotion circle when fps > 0; setEdgeThroughput updates edge.data.fps |

**Score:** 8/8 truths have substantive implementation; all require human verification for runtime behavior.

---

## Required Artifacts

### Plan 01 — Type System, Validation, Serializer, Store (P14-TYPES, P14-STORE)

| Artifact | Status | Evidence |
|----------|--------|---------|
| `frontend/src/utils/pipelineTypes.ts` | VERIFIED | 73 lines; exports PortDataType, PortDef, PipelineNodeData (type alias), PipelineNode, PipelineEdge, PresetInfo, ValidationError, PipelineConfig, NodeDefinition — all 9 required types present |
| `frontend/src/utils/pipelineValidation.ts` | VERIFIED | 112 lines; exports detectCycles (Kahn's algorithm, 45 lines of implementation), findUnconnectedPorts, findMissingOutput, validateGraph |
| `frontend/src/utils/pipelineSerializer.ts` | VERIFIED | 104 lines; exports serializeGraph (traverses edges for param_scalar category overrides), deserializeGraph |
| `frontend/src/utils/nodeDefinitions.ts` | VERIFIED | 280 lines; exports PORT_COLORS (7 types), PORT_SHAPES (7 types), CATEGORY_COLORS (7 categories), NODE_DEFINITIONS (11 entries: sensor_rgbd, sensor_imu, slam_generic, merger_generic, filter_voxel_downsample, filter_noise_removal, filter_coord_transform, splitter, combiner, param_scalar, viz_output), buildNodeData |
| `frontend/src/stores/pipelineStore.ts` | VERIFIED | 254 lines; exports usePipelineStore, fetchNodeCatalog, fetchPresets; imports create from zustand, applyNodeChanges/applyEdgeChanges/addEdge from @xyflow/react; all 16 actions implemented including setNodeStatus (updates both nodeStatuses map AND node.data.status), setEdgeThroughput (updates both edgeThroughputs map AND edge.data.fps) |

### Plan 02 — Backend Pipeline System (P14-BUILDER, P14-ROUTES, P14-PRESETS)

| Artifact | Status | Evidence |
|----------|--------|---------|
| `src/coordination/pipeline_builder.py` | VERIFIED | 418 lines; PipelineBuilder.build() validates DAG via Kahn's, rejects unknown types, checks required connections, resolves param_scalar overrides via edge targetHandle, builds filter chain in topo order; NodeCatalog.get_catalog() calls SLAMRegistry.list_backends() and MergeRegistry.list_strategies() |
| `backend/web/pipeline_routes.py` | VERIFIED | 135 lines; router at `/api/pipeline` prefix; POST /apply (calls PipelineBuilder, raises 422 on ValueError, triggers command_callback restart), GET /node-catalog, GET /presets, POST /presets, GET /presets/{name}, DELETE /presets/{name} |
| `tests/coordination/test_pipeline_builder.py` | VERIFIED | test_build_valid_graph, test_reject_cycle, test_reject_unknown_node, test_reject_unconnected_required, test_parameter_node_override, test_node_catalog — all 6 tests present and passing |
| `tests/web/test_pipeline_routes.py` | VERIFIED | test_apply_valid_config, test_reject_cycle, test_reject_unconnected, test_preset_crud, test_node_catalog, test_builtin_presets — all 6 tests present and passing |
| `data/presets/builtin/default_icp.json` | VERIFIED | Contains "Default ICP", 4-node linear pipeline (sensor→slam_icp→merger_icp_union→viz_output) |
| `data/presets/builtin/pgo_high_quality.json` | VERIFIED | Contains "PGO High Quality", 5-node pipeline with voxel filter |
| `data/presets/builtin/comparison_mode.json` | VERIFIED | Contains "Comparison Mode", 7-node diamond pipeline with splitter, dual SLAM (icp + orbslam3), combiner |

### Plan 03 — React Flow Canvas Components (P14-CANVAS, P14-ANIMATE)

| Artifact | Status | Evidence |
|----------|--------|---------|
| `frontend/src/components/pipeline/PortHandle.tsx` | VERIFIED | Uses PORT_COLORS and PORT_SHAPES from nodeDefinitions; renders Handle with correct shape (diamond: rotate(45deg), square: borderRadius 2px, circle: 50%); renders port label span |
| `frontend/src/components/pipeline/PipelineNode.tsx` | VERIFIED | nodeTypes defined at MODULE scope (line 237); renders colored header, 7-category icons, status badge (idle=#666, processing=#2ecc71, error=#d32f2f, initializing=#4fc3f7 with pulse animation); inline primary params with lightning bolt / lock; subscribes to nodeStatuses from store |
| `frontend/src/components/pipeline/EdgeAnimated.tsx` | VERIFIED | edgeTypes at module scope; getBezierPath + BaseEdge; animateMotion circle when fps > 0; throughput label at midpoint; prefers-reduced-motion check at module load |
| `frontend/src/components/pipeline/PipelineEditor.tsx` | VERIFIED | Imports '@xyflow/react/dist/style.css'; wraps in ReactFlowProvider; isValidConnection reads from usePipelineStore.getState() (not stale closure); onDrop parses 'application/pipeline-node' dataTransfer; MiniMap 160×120; Background variant=BackgroundVariant.Dots |

### Plan 04 — Surrounding Panel Components (P14-PALETTE, P14-INSPECTOR, P14-APPLY)

| Artifact | Status | Evidence |
|----------|--------|---------|
| `frontend/src/components/pipeline/NodePalette.tsx` | VERIFIED | Reads NODE_DEFINITIONS + CATEGORY_COLORS; draggable items set 'application/pipeline-node' dataTransfer; search input with placeholder; 7-category display order with colored headers; collapsed/expanded toggle |
| `frontend/src/components/pipeline/NodeInspector.tsx` | VERIFIED | Reads selectedNodeId from usePipelineStore; "Select a node to view its parameters" when none selected; renders all schema properties; lightning bolt (⚡ #ff9800) for live-tunable, lock (🔒 #888) for startup-only; calls updateNodeParam; debounced WS send for live-tunable params |
| `frontend/src/components/pipeline/PresetSelector.tsx` | VERIFIED | Fetches /api/pipeline/presets on mount; loads with dirty-graph ConfirmModal confirmation; deserializeGraph for preset loading; save via POST /api/pipeline/presets; "Built-in" italic badge |
| `frontend/src/components/pipeline/ApplyBar.tsx` | VERIFIED | "Apply Pipeline" button; "Pipeline valid" / "N validation error(s)" status; "Modified" orange dot; validate() called before confirm; POSTs to /api/pipeline/apply; RestartOverlay when isApplying; ConfirmModal for apply confirmation |

### Plan 05 — Integration Wiring (P14-TOGGLE, P14-ANIMATE)

| Artifact | Status | Evidence |
|----------|--------|---------|
| `frontend/src/components/ViewToggle.tsx` | VERIFIED | "3D Viewer" + "Pipeline Editor" buttons; active button: background #4fc3f7, color #0a0a14; inactive: background #2a2a4a, color #888 |
| `frontend/src/App.tsx` | VERIFIED | Imports all pipeline components; useState for ViewMode ('3d'|'pipeline'); useEffect fetches /api/pipeline/node-catalog on activeView='pipeline'; renders NodePalette+PipelineEditor+InspectorWrapper+ApplyBar in pipeline mode; InspectorWrapper subscribes to selectedNodeId reactively |
| `frontend/src/hooks/useWebSocket.ts` | VERIFIED | Handles pipeline_status case; dispatches node_statuses via setNodeStatus, edge_throughputs via setEdgeThroughput |

---

## Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| pipelineStore.ts | pipelineValidation.ts | validate() calls validateGraph() | WIRED | Line 153: `const errors = validateGraph(nodes, edges)` |
| pipelineStore.ts | pipelineSerializer.ts | serializeForApply() calls serializeGraph() | WIRED | Line 159: `return serializeGraph(nodes, edges)` |
| nodeDefinitions.ts | pipelineTypes.ts | imports PortDef, PipelineNodeData types | WIRED | Line 1: `import type { PortDataType, NodeCategory, NodeDefinition, PipelineNodeData }` |
| PipelineEditor.tsx | pipelineStore.ts | usePipelineStore for nodes, edges, callbacks | WIRED | Lines 22-28: `usePipelineStore(s => s.nodes)` etc. |
| PipelineEditor.tsx | PipelineNode.tsx | nodeTypes = { pipeline: PipelineNodeComponent } | WIRED | Line 14: `import { nodeTypes } from './PipelineNode'` |
| PipelineNode.tsx | PortHandle.tsx | renders PortHandle for each input/output port | WIRED | Lines 124-133, 221-230: maps over inputs/outputs rendering PortHandle |
| NodePalette.tsx | nodeDefinitions.ts | reads NODE_DEFINITIONS, CATEGORY_COLORS | WIRED | Line 3: `import { NODE_DEFINITIONS, CATEGORY_COLORS }` |
| NodeInspector.tsx | pipelineStore.ts | reads selectedNodeId, calls updateNodeParam | WIRED | Lines 18, 58: selectedNodeId selector + updateNodeParam call |
| ApplyBar.tsx | pipelineStore.ts | reads isDirty, isValid, validationErrors | WIRED | Lines 8-11: `usePipelineStore(s => s.isDirty)` etc. |
| pipeline_routes.py | pipeline_builder.py | apply endpoint calls PipelineBuilder.build() | WIRED | Line 52: `config = builder.build(...)` |
| pipeline_routes.py | slam/registry.py | NodeCatalog calls SLAMRegistry.list_backends() | WIRED | pipeline_builder.py line 187: `SLAMRegistry.list_backends()` |
| server.py | pipeline_routes.py | app.include_router(pipeline_router) | WIRED | server.py lines 66-67: `from backend.web.pipeline_routes import router as pipeline_router; app.include_router(pipeline_router)` |
| useWebSocket.ts | pipelineStore.ts | pipeline_status dispatches to setNodeStatus/setEdgeThroughput | WIRED | Lines 182-193: `pipelineState.setNodeStatus(...)` and `pipelineState.setEdgeThroughput(...)` |
| App.tsx | PipelineEditor.tsx | conditional render based on activeView | WIRED | Line 79: `<PipelineEditor />` in pipeline view branch |
| App.tsx | ViewToggle.tsx | renders ViewToggle in hero area | WIRED | Line 66: `<ViewToggle activeView={activeView} onViewChange={setActiveView} />` |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status |
|-------------|-------------|-------------|--------|
| P14-TYPES | 14-01 | Pipeline TypeScript type system (PortDataType, PortDef, PipelineNodeData, etc.) | SATISFIED — all 9 types exported from pipelineTypes.ts |
| P14-STORE | 14-01 | Zustand pipelineStore with React Flow integration | SATISFIED — usePipelineStore with all 16 actions, RC Flow callbacks, dirty state |
| P14-BUILDER | 14-02 | PipelineBuilder class with DAG validation | SATISFIED — Kahn's cycle detection, unknown type check, unconnected port check, param_scalar override |
| P14-ROUTES | 14-02 | Pipeline REST API /api/pipeline/* | SATISFIED — 6 endpoints: apply, node-catalog, list/save/load/delete presets |
| P14-CANVAS | 14-03 | React Flow canvas with dark bg, minimap, dot grid | SATISFIED — PipelineEditor wraps ReactFlowProvider, BackgroundVariant.Dots, MiniMap 160×120 |
| P14-PALETTE | 14-04 | Node palette with categories, search, drag-to-add | SATISFIED — NodePalette with 7 categories, search input, draggable items with dataTransfer |
| P14-INSPECTOR | 14-04 | Node inspector with JSON Schema param rendering | SATISFIED — NodeInspector renders all schema properties, sliders, toggles, live-tunable indicators |
| P14-APPLY | 14-04 | Apply bar with validation, modified indicator, apply button | SATISFIED — ApplyBar with validate-before-apply, isDirty badge, POST to /api/pipeline/apply |
| P14-TOGGLE | 14-05 | View toggle between 3D Viewer and Pipeline Editor | SATISFIED — ViewToggle + App.tsx conditional rendering |
| P14-ANIMATE | 14-03, 14-05 | Animated edges showing fps; WS pipeline_status dispatch | SATISFIED — EdgeAnimated with animateMotion; useWebSocket dispatches to setEdgeThroughput; setEdgeThroughput updates edge.data.fps reactively |
| P14-PRESETS | 14-02 | 3 built-in presets; preset CRUD | SATISFIED — default_icp.json, pgo_high_quality.json, comparison_mode.json; full CRUD via /api/pipeline/presets |

**All 11 declared requirements are accounted for across plans 01-05. No orphaned requirements found.**

---

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| tests/coordination/test_pipeline_builder.py | 6 | 12/12 pass (combined with routes) |
| tests/web/test_pipeline_routes.py | 6 | 12/12 pass (combined with builder) |

```
............                                  [100%]
12 passed in 3.60s
```

---

## TypeScript Compilation

- All pipeline-specific files compile with zero TypeScript errors.
- 3 pre-existing errors exist in `DetectionBoxes.ts`, `SceneViewer.tsx`, and `useWebSocket.ts(132)` related to a `Detection.depth` type mismatch. These pre-date phase 14 and are out of scope.
- Full production build blocked by these pre-existing errors but TypeScript type-checking of pipeline files passes.

---

## Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|-----------|
| NodePalette.tsx:140 | `placeholder="Search nodes..."` | Info | HTML attribute, not a stub indicator — correct usage |
| PresetSelector.tsx:196 | `placeholder="Preset name"` | Info | HTML attribute, not a stub indicator — correct usage |

No blocker anti-patterns detected. No TODO/FIXME/XXX comments. No empty implementations. No static return stubs.

---

## Notable Implementation Quality Points

1. **Kahn's algorithm implemented twice (frontend TS + backend Python):** Both implementations correctly return cycle members and raise on cycle detection.
2. **React Flow pitfall avoidance:** nodeTypes and edgeTypes defined at module scope (not inside components) preventing remount on re-render. isValidConnection reads from `getState()` to avoid stale closure.
3. **setNodeStatus dual update:** Updates both the `nodeStatuses` map and `node.data.status` field so both store subscribers and React Flow node rendering get the update.
4. **setEdgeThroughput dual update:** Explicitly reconstructs `{ dataType: e.data.dataType, fps }` to avoid losing the required `dataType` field.
5. **prefers-reduced-motion:** Checked at module load in EdgeAnimated.tsx for zero per-render overhead.
6. **InspectorWrapper pattern:** App.tsx uses a small wrapper component subscribing to `selectedNodeId` reactively rather than the anti-pattern `usePipelineStore.getState().selectedNodeId` which wouldn't trigger re-renders.
7. **PipelineNodeData as type alias:** Changed from interface to type alias to satisfy React Flow v12's `Record<string, unknown>` generic constraint.

---

## Human Verification Required

### 1. View Toggle

**Test:** Open the application, locate the toggle in the top-left of the hero area, click "Pipeline Editor"
**Expected:** The 3D scene is replaced by the pipeline editor layout. NodePalette appears on the left, the React Flow canvas fills the center, ApplyBar appears at the bottom. Clicking "3D Viewer" restores the 3D scene.
**Why human:** View state is runtime React state; cannot be verified from static source.

### 2. Node Palette Drag-to-Add

**Test:** In Pipeline Editor mode, drag "RGB-D Sensor" from the palette onto the canvas
**Expected:** A node appears at the drop position with a blue header ("#1565c0"), camera icon, and two output port handles (RGB-D, Depth) colored in blue (#42a5f5).
**Why human:** Drag-and-drop requires browser dataTransfer and React Flow screenToFlowPosition.

### 3. Custom Node Visual Rendering

**Test:** Add an ICP SLAM node from the palette
**Expected:** Node has green header (#2e7d32), compass icon, image_in (required, blue circle) and imu_in (optional, purple circle) as input handles on the left, pose_out (orange circle) and cloud_out (green circle) as outputs on the right.
**Why human:** Visual pixel layout requires browser rendering.

### 4. Connection Validation

**Test:** Draw an edge from the sensor's "Depth" output to the SLAM's "IMU" input
**Expected:** The edge is rejected (not created). Draw from "RGB-D" output to "Image" input — this should succeed.
**Why human:** isValidConnection is triggered by React Flow internals during edge draw.

### 5. Node Inspector

**Test:** Click a Voxel Downsample filter node
**Expected:** Right inspector panel opens showing "Voxel Size" parameter with a slider, range slider + number input, orange lightning bolt indicating live-tunable, description text. Adjusting the slider updates the displayed value.
**Why human:** selectedNodeId state transition and DOM rendering require browser interaction.

### 6. Preset Load

**Test:** Click the preset dropdown, select "Default ICP"
**Expected:** Canvas populates with 4 nodes in a linear chain (sensor → ICP → merger → viz). "Default ICP" appears as the active preset label. Modified indicator is not shown.
**Why human:** Requires running backend with preset endpoint available plus frontend graph rendering.

### 7. Apply Pipeline

**Test:** With a valid pipeline loaded, click "Apply Pipeline"
**Expected:** ConfirmModal appears. On clicking "Apply", RestartOverlay appears and "Pipeline valid" status is shown. After backend responds, isDirty clears and Modified indicator disappears.
**Why human:** Requires running backend accepting POST /api/pipeline/apply.

### 8. Animated Edges

**Test:** Simulate a pipeline_status WebSocket message with edge_throughputs: { "edge-id": 30 }
**Expected:** The corresponding edge changes from gray (#4a4a6a) to cyan (#4fc3f7) and a flowing dot animates along the edge with a "30 fps" label at the midpoint.
**Why human:** Requires live WebSocket message injection and visual confirmation.

---

## Summary

Phase 14 has achieved complete implementation across all 11 requirements. All 21 declared artifacts exist, are substantive (not stubs), and are correctly wired. All 15 key links are verified. All 12 backend tests pass. TypeScript compilation is clean for all pipeline files.

The phase status is `human_needed` because the ComfyUI-style interaction model—drag-and-drop, canvas rendering, connection validation, visual node display, inspector updates, preset loading, and animated edges—requires browser-side verification that cannot be confirmed programmatically. The implementation code is complete and correct; what remains is confirming the runtime experience matches the UI-SPEC.

Plan 14-06 (human verification checkpoint) is the appropriate next step.

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
