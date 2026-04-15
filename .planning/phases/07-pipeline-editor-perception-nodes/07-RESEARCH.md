# Phase 7: pipeline-editor-perception-nodes — Research

**Researched:** 2026-04-15
**Domain:** React Flow pipeline editor + FastAPI hot-apply diff + Python registry plumbing
**Confidence:** HIGH
**Research date valid until:** 2026-05-15 (30 days — stack is stable)

## Summary

Phase 7 is three-quarters editor-surface plumbing and one-quarter hot-apply routing. CONTEXT.md (307 lines, 16 locked decisions D-01..D-16) already prescribes the node surface pattern, port types, preset composition, and hot-swap apply diff policy. This research does NOT re-open any of those decisions — it catalogs the concrete code patterns a planner can paste into plan files, line-number references for extension points, the Nyquist validation architecture, and the pitfalls specific to mixing React Flow connection semantics with Zustand store mutations and FastAPI app-state diffing.

The heaviest lift is `backend/web/pipeline_routes.py::apply_pipeline` (currently 20 LOC, will grow to ~90) and `src/coordination/pipeline_builder.py` (PipelineConfig dataclass + NodeCatalog enumeration + PipelineBuilder.build extension — ~120 LOC added). Frontend work is mechanical: extend three type unions, add a validator function, fix one hardcoded string, extend one category-order array, branch one fetch response. The tracker scaffold (`src/tracking/` — new package) is small but load-bearing for SC#1: without it, the `TrackerNode` palette entry is unreachable.

**Primary recommendation:** Structure the plan as four waves — Wave 0 (test stubs + vitest scaffolding), Wave 1 (Python: tracker package + PipelineConfig extension + swap_backend), Wave 2 (frontend type/validation/store/palette), Wave 3 (hot-apply diff + preset + integration tests). The `perception_rgbd.json` preset and the hot-apply integration test belong in Wave 3 because they depend on everything above.

<user_constraints>
## User Constraints (from CONTEXT.md)

CONTEXT.md is `--auto` mode with no user input — all 16 decisions are Claude-locked defaults. The planner MUST NOT re-open any locked decision below. Only items in `### Claude's Discretion` are open.

### Locked Decisions (D-01 .. D-16)

**Node surface pattern (DET-PIPELINE-01):**
- **D-01** Registry-driven generic pattern — `detector_generic`, `detection3d_generic`, `tracker_generic` node defs mirror `slam_generic` / `merger_generic`. Per-backend concrete node types REJECTED.
- **D-02** Changing `backend` param on an existing node = hot-swap; deleting+adding = restart. `registryName` is mutable; Inspector dropdown sources from `DetectorRegistry.list()`.
- **D-03** `detector_generic` ports: `image_in: Image` (req), `depth_in: Image` (opt), `detections_2d_out: Detections2D`, `detections_3d_out: Detections3D` (emits zero-count envelopes on 2D-only backends — documented, not error).
- **D-04** `detection3d_generic` ports: `detections_2d_in: Detections2D` (req), `depth_in: Image` (req), `pose_in: Pose` (opt), `detections_3d_out: Detections3D`.
- **D-05** `tracker_generic` ports: `detections_3d_in: Detections3D` (req), `tracks_out: Tracks`.
- **D-06** `viz_output` gains `tracks_in: Tracks` (optional). Renderer ignores tracks today (Phase 8 ghost label layer).

**Port types + colors + validation (DET-PIPELINE-02, 03):**
- **D-07** New `PortDataType` values: `Detections2D: #ff8a65` (coral), `Detections3D: #ec407a` (pink), `Tracks: #26a69a` (teal). All circle-shaped. New category color `perception: #ad1457`.
- **D-08** Fix `pipelineStore.ts:101` hardcoded `dataType: 'PointCloud'`: resolve source node + source handle output port's `dataType`, fall back to `'PointCloud'` only defensively.
- **D-09** Add `findPortTypeMismatches(nodes, edges)` to `pipelineValidation.ts`; hook into `validateGraph()` BEFORE `findUnconnectedPorts` + `findMissingOutput`.

**Hot-swap apply path (DET-PIPELINE-05):**
- **D-10** Server-side diff in `/api/pipeline/apply`. Strict AND: topology_digest unchanged AND non-detector/non-lifter fields unchanged AND only detector_*/lifter_* moved → call `pool.swap_backend` / `pool.swap_lifter`, return `{"status": "hot-applied", "changed": [...]}`. Else: stash `pending_pipeline_config`, trigger restart callback, return `{"status": "restarting"}`.
- **D-11** `DetectorWorkerPool.swap_backend(new_backend_name, new_backend_params)` mirrors `swap_lifter`: construct per-worker + warmup OUTSIDE `_swap_lock`, rebind INSIDE. Emits `detector_swap_complete` WS message.
- **D-12** `app.state.last_applied_pipeline_config` set at boot + every successful apply + on crash_fallback (update `detector_name` field to fallback).

**Tracker scope (SC#1):**
- **D-13** Ship `TrackerRegistry` + `tracker_none` passthrough in Phase 7. Monotonic-counter `track_id`, `produces_stable_ids: False`. ByteTrack deferred to Phase 8.
- **D-14** Tracker pool integration deferred to Phase 8. `DetectionExportWriter.track_id=None` continues; `NoneTracker.track()` is graph-only scaffolding.

**Preset (DET-PIPELINE-04):**
- **D-15** `perception_rgbd.json` wires parallel SLAM + perception branches (SLAM on top row, perception on middle row, shared sensor + shared viz_output).
- **D-16** Exact node positions specified in CONTEXT.md line 164-170.

### Claude's Discretion (planner may choose)

1. Exact TypeScript type narrowing on `PortDataType` (preserve strict exhaustiveness in `PORT_COLORS` / `PORT_SHAPES`).
2. ApplyBar toast styling for `hot-applied` (success green `#4caf50`, reuse existing banner structure).
3. Hot-apply response keys beyond `status` + `changed` — planner may add `elapsed_ms` / `active_detector` echoes (ApplyBar only reads `status` + `changed`).
4. Diff implementation — `dataclasses.asdict` equality vs explicit field-by-field. Both correct.
5. Node palette heading copy — `"Perception"` (Claude's pick — matches "SLAM Backends" / "Mergers" style).
6. WS message type — new `detector_swap_complete` envelope (slight preference per CONTEXT.md) vs reusing `detector_restart_complete` with `reason: "hot_swap"` discriminator.
7. `NoneTracker` counter reset cadence — session-lifetime monotonic (simpler) vs per-frame.

### Deferred Ideas (OUT OF SCOPE — do not plan for)

- ByteTrack implementation — Phase 8 DET-STRETCH-01.
- Multi-robot per-robot backend UI on graph — Phase 8 DET-STRETCH-04.
- SemanticMap / fusion nodes — Phase 8 DET-STRETCH-03.
- Input-type capability gating (OWLv2 dropped 2026-04-15).
- Tracker ParameterPanel UX — Phase 8 alongside ByteTrack.
- SLAM hot-swap via pipeline apply — REJECTED (spawn positions + map state invalidation cannot be safely skipped).
- Merger / filter chain hot-swap — REJECTED (pump rewire not factored for live mutation).
- `Any` / polymorphic port type — deferred.
- Aggregated concurrent-restart overlay polish — Phase 3 D-12 ships stacked overlays.
- Node-level live param tuning for perception nodes — current `ParameterPanel` targets active detector via `detector_param_update` WS; unifying the two panels is Phase 8+.
- Pipeline diff details in frontend UI — polish item.
- `detection3d_generic.cloud_in: PointCloud` port — deferred until a lifter needs it.
- `PipelineConfig` versioning / schema migration — additive fields, no migration needed.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-PIPELINE-01 | Pipeline editor exposes `DetectorNode`, `Detection3DNode`, `TrackerNode` under a new `perception` category | Pattern Template 1 (nodeDefinitions.ts additions), Pattern Template 3 (NodePalette CATEGORY_ORDER extension), Pattern Template 5 (NodeCatalog.get_catalog enumeration) |
| DET-PIPELINE-02 | `Detections2D` and `Detections3D` port data types with distinct colors | Pattern Template 2 (pipelineTypes.ts + PORT_COLORS extension) |
| DET-PIPELINE-03 | `pipelineValidation.ts` reports per-edge type mismatches; fix `pipelineStore.ts:101` hardcoded PointCloud bug + regression test | Pattern Template 4 (`findPortTypeMismatches`), Pattern Template 6 (onConnect source-handle lookup) |
| DET-PIPELINE-04 | `perception_rgbd` built-in preset wires MuJoCoBridge → DetectorNode(YOLOv11) → Detection3DNode(PointCluster) → visualization | Pattern Template 8 (preset JSON structure cloned from default_icp.json + comparison_mode.json parallel-branch layout) |
| DET-PIPELINE-05 | `pipeline_routes.py` maps `detector_generic` nodes to `DetectorWorkerPool` with params flowing through — NO coordinator restart for param-only change | Pattern Template 7 (PipelineConfig extension + PipelineBuilder.build), Pattern Template 9 (apply_pipeline hot-apply diff), Pattern Template 10 (DetectorWorkerPool.swap_backend mirror of swap_lifter) |

</phase_requirements>

## Project Constraints (no CLAUDE.md at project root)

`/home/prannayag/pragnition/robotics/argus/CLAUDE.md` does NOT exist. No project-level instructions to honor. The only applicable skill (`.claude/skills/desloppify/`) is a codebase-health scanner — orthogonal to this phase.

**Invariants carried from prior phase contexts (MUST NOT break):**

1. **Module-scope purity (Phase 1 Pitfall P9):** No `torch` / `numpy` / `ultralytics` / `transformers` imports at module scope anywhere in `src/perception/`. `src/tracking/` follows the same rule — `NoneTracker` uses only `itertools.count` or a plain int counter, no heavy deps.
2. **Registry side-effect import (Phase 1 D-06):** New registries populate via `import src.tracking.trackers` side-effects. `TrackerRegistry.list_backends()` after a cold import returns `[]` — callers that care (REST handlers, PipelineBuilder, `NoneTracker.create`) MUST `import src.tracking.trackers` first. Existing detector_routes.py line 151 / 178 / 208 / 226 pattern is the template.
3. **OBB wire format locked (Phase 2 D-03):** Tracker must NOT construct quaternions inline. `NoneTracker.track()` only stamps `track_id` on existing boxes — never mutates geometry fields.
4. **Per-robot instance separation (Phase 2 D-05):** `DetectorWorkerPool.swap_backend` MUST construct one backend per worker — same as `swap_lifter` and `on_backend_crash` (see `src/perception/worker_pool.py:430-432`).
5. **Atomic ref swap under `_swap_lock` (Phase 4 D-10):** construct-outside-lock → rebind-inside-lock. In-flight `process_frame` completes on OLD backend — documented behavior, NOT a bug. (`src/perception/worker_pool.py:310-314` is the template.)
6. **`detector_restart_complete` payload (Phase 3 D-09 / Phase 5 SC#1):** `{backend, lifter}` — warmup must complete before emission. Hot-swap does NOT emit this event; emit new `detector_swap_complete` instead (or reuse with discriminator — Claude's Discretion #6).
7. **`mAP` forbidden in UI (Phase 6 DET-METRICS-03 + grep invariant `tests/contract/test_no_map_in_ui.py`):** Phase 7's NodeInspector + ApplyBar must not surface `mAP` strings even when planner adds metric-related UI affordances.
8. **`track_id=None` proxy (Phase 6):** Phase 6 `DetectionExportWriter` + jitter computation assume `track_id=None`. Phase 7's `NoneTracker` runs ONLY inside the pipeline graph (D-14) — it does NOT enter the coordinator pump, so export behavior is unchanged.

## Standard Stack

The project's stack is already locked — no new dependencies needed beyond what's installed. Verified from `pyproject.toml` and `frontend/package.json`:

### Frontend (verified via `frontend/node_modules/@xyflow/react/package.json`)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@xyflow/react` | 12.10.1 | React Flow canvas / `onConnect` / `Connection` type | [VERIFIED: node_modules] Already used by Phase 3-6; stable public API; `Connection` always carries `source` + `sourceHandle` per official docs |
| `zustand` | 5.0.0 | `pipelineStore` state (existing) | [VERIFIED: package.json] Already in use |
| `vitest` | 4.1.4 + jsdom 29.0.2 | Test runner | [VERIFIED: package.json, Phase 3 Plan 03-01 added this] |
| `typescript` | 5.6 | Strict exhaustiveness on `PortDataType` | [VERIFIED: package.json] |

### Backend (verified via `pyproject.toml`)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | >=0.100.0 | REST routes (existing) | [VERIFIED: pyproject.toml] |
| `pydantic` | via fastapi | `PipelineApplyRequest` / `SelectRequest` (existing) | [VERIFIED: in use already] |
| `pytest` | >=8.0.0 | Test runner | [VERIFIED: pyproject.toml dev extra] |
| `pytest-asyncio` | >=0.23.0 | Async route tests | [VERIFIED: pyproject.toml dev extra] |

### New Dependencies Needed
**NONE.** The `src/tracking/` package uses only stdlib (`typing`, `itertools`, `dataclasses`). Frontend additions are string/type extensions — no package installs.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@xyflow/react.onConnect(Connection)` | Custom `onEdgeCreate` hook | Breaks React Flow contract; `Connection` interface is the canonical boundary |
| Server-side diff in `apply_pipeline` | Client-side shallow compare + separate endpoints | Duplicates topology-digest math in TypeScript; CONTEXT D-10 picks server-side (source of truth with `PipelineConfig`) |
| New `PortDataType` enum | Keep string literals loose | Loses exhaustiveness check in `PORT_COLORS`; existing code is nominal — keep it strict |

## Architecture Patterns

### Recommended file layout
```
src/tracking/                          # NEW package (D-13)
├── __init__.py                        # empty, or `from . import trackers`
├── protocol.py                        # TrackerProtocol (runtime_checkable)
├── registry.py                        # TrackerRegistry mirror of DetectorRegistry
└── trackers/
    ├── __init__.py                    # imports submodules for side-effect registration
    └── none.py                        # NoneTracker passthrough

data/presets/builtin/perception_rgbd.json   # NEW (D-15)

frontend/src/stores/__tests__/
└── pipelineStore.dataType.test.ts          # NEW (SC#2 regression)

frontend/src/utils/__tests__/
└── pipelineValidation.typeMismatch.test.ts # NEW (SC#2 lockdown)

tests/coordination/
└── test_pipeline_builder_perception.py     # NEW (SC#5 lockdown)

tests/integration/
└── test_pipeline_apply_hot.py              # NEW (SC#4 lockdown)

tests/tracking/                              # NEW
├── __init__.py
└── test_tracker_registry.py

tests/contract/
└── test_perception_rgbd_preset.py          # NEW (DET-PIPELINE-04 lockdown)
```

**Files modified (extension points, with exact line numbers):**
```
frontend/src/utils/pipelineTypes.ts:4                 — extend PortDataType union
frontend/src/utils/pipelineTypes.ts:15                — extend NodeCategory union
frontend/src/utils/nodeDefinitions.ts:4-12            — extend PORT_COLORS
frontend/src/utils/nodeDefinitions.ts:14-23           — extend PORT_SHAPES
frontend/src/utils/nodeDefinitions.ts:26-34           — extend CATEGORY_COLORS
frontend/src/utils/nodeDefinitions.ts:37-249          — add 3 NODE_DEFINITIONS entries + extend viz_output
frontend/src/utils/pipelineValidation.ts:88-110       — add findPortTypeMismatches + hook into validateGraph
frontend/src/stores/pipelineStore.ts:95-107           — fix onConnect hardcoded dataType
frontend/src/components/pipeline/NodePalette.tsx:27-45 — extend CATEGORY_ORDER + CATEGORY_LABELS
frontend/src/components/pipeline/ApplyBar.tsx:35-52   — branch on response.status for hot-applied path
backend/web/pipeline_routes.py:43-63                  — extend apply_pipeline with diff
src/coordination/pipeline_builder.py:20-28            — PipelineConfig dataclass extension
src/coordination/pipeline_builder.py:168-171          — extend _REQUIRED_INPUTS
src/coordination/pipeline_builder.py:177-223          — extend NodeCatalog.get_catalog
src/coordination/pipeline_builder.py:234-335          — extend PipelineBuilder.build
src/perception/worker_pool.py:269-315                 — add swap_backend method after swap_lifter
src/main.py:518-523                                   — extend to consume pipeline_config.lifter_name
src/main.py:~625                                      — set app.state.last_applied_pipeline_config after successful restart
```

### Pattern Template 1 — Add `detector_generic` / `detection3d_generic` / `tracker_generic` to `nodeDefinitions.ts`

**Location:** `frontend/src/utils/nodeDefinitions.ts` (insert after `splitter` entry at line 197)

```typescript
// Source: mirror of slam_generic at line 63-77
detector_generic: {
  type: 'detector_generic',
  label: 'Detector',
  category: 'perception',
  inputs: [
    { id: 'image_in', label: 'Image', dataType: 'Image', required: true },
    { id: 'depth_in', label: 'Depth', dataType: 'Image', required: false },
  ],
  outputs: [
    { id: 'detections_2d_out', label: 'Detections 2D', dataType: 'Detections2D', required: false },
    { id: 'detections_3d_out', label: 'Detections 3D', dataType: 'Detections3D', required: false },
  ],
  defaultParams: {},
  parameterSchema: null,  // populated from DetectorRegistry at runtime via NodeCatalog
},

detection3d_generic: {
  type: 'detection3d_generic',
  label: '3D Lifter',
  category: 'perception',
  inputs: [
    { id: 'detections_2d_in', label: 'Detections 2D', dataType: 'Detections2D', required: true },
    { id: 'depth_in', label: 'Depth', dataType: 'Image', required: true },
    { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: false },
  ],
  outputs: [
    { id: 'detections_3d_out', label: 'Detections 3D', dataType: 'Detections3D', required: false },
  ],
  defaultParams: {},
  parameterSchema: null,
},

tracker_generic: {
  type: 'tracker_generic',
  label: 'Tracker',
  category: 'perception',
  inputs: [
    { id: 'detections_3d_in', label: 'Detections 3D', dataType: 'Detections3D', required: true },
  ],
  outputs: [
    { id: 'tracks_out', label: 'Tracks', dataType: 'Tracks', required: false },
  ],
  defaultParams: {},
  parameterSchema: null,
},
```

**ALSO:** extend `viz_output` at line 237-248 to gain `tracks_in`:
```typescript
viz_output: {
  // ... existing fields ...
  inputs: [
    { id: 'cloud_in', label: 'PointCloud', dataType: 'PointCloud', required: true },
    { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: false },
    { id: 'tracks_in', label: 'Tracks', dataType: 'Tracks', required: false },  // NEW (D-06)
  ],
  // ...
},
```

### Pattern Template 2 — Extend `PortDataType` + color/shape maps

**Location:** `frontend/src/utils/pipelineTypes.ts:4`
```typescript
export type PortDataType =
  | 'Image' | 'PointCloud' | 'Pose' | 'IMU'
  | 'Scalar' | 'Boolean' | 'Config'
  | 'Detections2D' | 'Detections3D' | 'Tracks';  // NEW (D-07)

export type NodeCategory =
  | 'sensor' | 'slam' | 'merger' | 'filter'
  | 'splitter' | 'parameter' | 'output'
  | 'perception';  // NEW (D-07)
```

**Location:** `frontend/src/utils/nodeDefinitions.ts:4-34` — extend three objects:
```typescript
export const PORT_COLORS: Record<PortDataType, string> = {
  Image: '#42a5f5',
  PointCloud: '#66bb6a',
  Pose: '#ffa726',
  IMU: '#ab47bc',
  Scalar: '#ef5350',
  Boolean: '#78909c',
  Config: '#ffee58',
  Detections2D: '#ff8a65',   // NEW (D-07 — coral)
  Detections3D: '#ec407a',   // NEW (D-07 — pink)
  Tracks: '#26a69a',         // NEW (D-07 — teal)
};

export const PORT_SHAPES: Record<PortDataType, string> = {
  // ... existing ...
  Detections2D: 'circle',
  Detections3D: 'circle',
  Tracks: 'circle',
};

export const CATEGORY_COLORS: Record<NodeCategory, string> = {
  // ... existing ...
  perception: '#ad1457',  // NEW (D-07 — magenta)
};
```

**CRITICAL — TypeScript exhaustiveness:** `Record<PortDataType, string>` forces the compiler to require every enum value. If you add to `PortDataType` without adding to `PORT_COLORS`, the build fails loudly. This is the "Claude's Discretion #1" item — keep the strict `Record<...>` typing, never loosen to `Partial<Record<...>>`.

### Pattern Template 3 — Extend `NodePalette.tsx` category ordering

**Location:** `frontend/src/components/pipeline/NodePalette.tsx:27-45`
```typescript
const CATEGORY_ORDER: NodeCategory[] = [
  'sensor',
  'slam',
  'perception',   // NEW (D-01) — inserted between slam and merger per CONTEXT §Integration Points
  'merger',
  'filter',
  'splitter',
  'parameter',
  'output',
];

const CATEGORY_LABELS: Record<NodeCategory, string> = {
  sensor: 'Sensors',
  slam: 'SLAM Backends',
  perception: 'Perception',   // NEW
  merger: 'Mergers',
  // ... rest unchanged ...
};
```

Because `NodePalette` already auto-groups items by category (line 76-81) and filters by search (line 70-73), ZERO other changes are required. The 3 new entries appear under "Perception" automatically once the definitions land.

### Pattern Template 4 — `findPortTypeMismatches` validator

**Location:** `frontend/src/utils/pipelineValidation.ts` (append before `validateGraph`)

```typescript
// Source: iteration pattern cloned from findUnconnectedPorts (line 50-73)
export function findPortTypeMismatches(
  nodes: PipelineNode[],
  edges: PipelineEdge[],
): ValidationError[] {
  const errors: ValidationError[] = [];
  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  for (const edge of edges) {
    const src = nodeById.get(edge.source);
    const tgt = nodeById.get(edge.target);
    if (!src || !tgt) continue;  // defensive; shouldn't happen in normal flow

    const srcPort = src.data.outputs.find((p) => p.id === edge.sourceHandle);
    const tgtPort = tgt.data.inputs.find((p) => p.id === edge.targetHandle);
    if (!srcPort || !tgtPort) continue;  // handle not resolved — skip

    if (srcPort.dataType !== tgtPort.dataType) {
      errors.push({
        nodeId: edge.target,
        message:
          `Edge from ${src.data.label}.${srcPort.label} (${srcPort.dataType}) ` +
          `to ${tgt.data.label}.${tgtPort.label} (${tgtPort.dataType}) ` +
          `has mismatched types`,
      });
    }
  }
  return errors;
}
```

**Hook into `validateGraph` at line 90-110** — insert BEFORE `findUnconnectedPorts` per D-09 (type errors are more actionable than structural):
```typescript
export function validateGraph(nodes: PipelineNode[], edges: PipelineEdge[]): ValidationError[] {
  const errors: ValidationError[] = [];

  const cycleLabels = detectCycles(nodes, edges);
  if (cycleLabels) {
    errors.push({ message: `Pipeline contains a cycle through nodes: ${cycleLabels.join(', ')}` });
  }

  errors.push(...findPortTypeMismatches(nodes, edges));   // NEW — D-09 order
  errors.push(...findUnconnectedPorts(nodes, edges));

  const missingOutput = findMissingOutput(nodes);
  if (missingOutput) errors.push(missingOutput);

  return errors;
}
```

### Pattern Template 5 — Extend `NodeCatalog.get_catalog` (Python)

**Location:** `src/coordination/pipeline_builder.py:177-223`
```python
@classmethod
def get_catalog(cls) -> list[dict]:
    """Return unified catalog... [existing docstring]"""
    catalog = list(_STATIC_NODES)

    # ... existing SLAM + merger blocks unchanged (line 186-221) ...

    # NEW — Detector backends (DET-PIPELINE-01)
    import src.perception.backends  # noqa: F401 — side-effect registration
    from src.perception.registry import Detection3DRegistry, DetectorRegistry

    for backend in DetectorRegistry.list_backends():
        catalog.append({
            "type": f"detector_{backend['name']}",
            "label": backend["display"],
            "category": "perception",
            "inputs": [
                {"id": "image_in", "label": "Image", "dataType": "Image", "required": True},
                {"id": "depth_in", "label": "Depth", "dataType": "Image", "required": False},
            ],
            "outputs": [
                {"id": "detections_2d_out", "label": "Detections 2D", "dataType": "Detections2D"},
                {"id": "detections_3d_out", "label": "Detections 3D", "dataType": "Detections3D"},
            ],
            "parameterSchema": backend.get("parameter_schema", {}),
            "capabilities": backend.get("capabilities", {}),   # exposes outputs_3d_natively to UI
            "defaultParams": {},
            "registryName": backend["name"],
        })

    # NEW — Detection3D lifters
    import src.perception.lifters  # noqa: F401
    for lifter in Detection3DRegistry.list_backends():
        catalog.append({
            "type": f"detection3d_{lifter['name']}",
            "label": lifter["display"],
            "category": "perception",
            "inputs": [
                {"id": "detections_2d_in", "label": "Detections 2D", "dataType": "Detections2D", "required": True},
                {"id": "depth_in", "label": "Depth", "dataType": "Image", "required": True},
                {"id": "pose_in", "label": "Pose", "dataType": "Pose", "required": False},
            ],
            "outputs": [
                {"id": "detections_3d_out", "label": "Detections 3D", "dataType": "Detections3D"},
            ],
            "parameterSchema": lifter.get("parameter_schema", {}),
            "capabilities": lifter.get("capabilities", {}),
            "defaultParams": {},
            "registryName": lifter["name"],
        })

    # NEW — Trackers
    import src.tracking.trackers  # noqa: F401
    from src.tracking.registry import TrackerRegistry
    for tracker in TrackerRegistry.list_backends():
        catalog.append({
            "type": f"tracker_{tracker['name']}",
            "label": tracker["display"],
            "category": "perception",
            "inputs": [
                {"id": "detections_3d_in", "label": "Detections 3D", "dataType": "Detections3D", "required": True},
            ],
            "outputs": [
                {"id": "tracks_out", "label": "Tracks", "dataType": "Tracks"},
            ],
            "parameterSchema": tracker.get("parameter_schema", {}),
            "capabilities": tracker.get("capabilities", {}),
            "defaultParams": {},
            "registryName": tracker["name"],
        })

    return catalog
```

### Pattern Template 6 — Fix `pipelineStore.ts:101` hardcoded dataType

**Location:** `frontend/src/stores/pipelineStore.ts:95-107` — replace block:

```typescript
onConnect: (connection) =>
  set((state) => {
    const sourceNode = state.nodes.find((n) => n.id === connection.source);
    const sourcePort = sourceNode?.data.outputs.find(
      (p) => p.id === connection.sourceHandle,
    );
    const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
    return {
      edges: addEdge(
        { ...connection, type: 'animated', data: { fps: 0, dataType } },
        state.edges,
      ) as PipelineEdge[],
      isDirty: true,
    };
  }),
```

**Source:** literal translation of CONTEXT.md D-08 code block. React Flow's `Connection` type guarantees `source` + `sourceHandle` are non-null under `onConnect` contract (`@xyflow/react` 12.x [VERIFIED: source inspection + https://reactflow.dev/api-reference/types/on-connect]). The `?? 'PointCloud'` is defensive only — never exercised in practice.

**ALSO:** fix `pipelineSerializer.ts:112` which has the same bug on deserialize — the edge `dataType` is hardcoded:
```typescript
// CURRENT (bug):
data: { fps: 0, dataType: 'PointCloud' as const },

// FIX: resolve from source node's output port (same pattern as onConnect)
const sourceNode = nodes.find((n) => n.id === configEdge.source);
const sourcePort = sourceNode?.data.outputs.find((p) => p.id === configEdge.sourceHandle);
const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
// ... use dataType in the edge data ...
```

Flag this for the planner: the grep pattern `dataType:\s*'PointCloud'\s*as\s*const` will catch both instances. Fix both in the same plan.

### Pattern Template 7 — Extend `PipelineConfig` + `PipelineBuilder.build` (Python)

**Location:** `src/coordination/pipeline_builder.py:20-28` — extend dataclass:
```python
@dataclass
class PipelineConfig:
    """Interpreted pipeline configuration from a graph."""

    backend_name: str = "icp"
    backend_params: dict = field(default_factory=dict)
    merger_name: str = "icp_union"
    merger_params: dict = field(default_factory=dict)
    filter_chain: list[dict] = field(default_factory=list)

    # NEW (DET-PIPELINE-05 / CONTEXT D-12)
    detector_name: str = "yolov11"
    detector_params: dict = field(default_factory=dict)
    lifter_name: str = "point_cluster"
    lifter_params: dict = field(default_factory=dict)
    tracker_name: str = "none"
    tracker_params: dict = field(default_factory=dict)
```

**Location:** `src/coordination/pipeline_builder.py:168-171` — extend required inputs:
```python
_REQUIRED_INPUTS: dict[str, list[str]] = {
    "slam_": ["image_in"],
    "merger_": ["cloud_in"],
    "detector_": ["image_in"],              # NEW (D-03)
    "detection3d_": ["detections_2d_in", "depth_in"],  # NEW (D-04)
    "tracker_": ["detections_3d_in"],       # NEW (D-05)
}
```

**Location:** `src/coordination/pipeline_builder.py:234-335` — extend build:
```python
def build(self, graph_json: dict) -> PipelineConfig:
    # ... existing DAG + known-types check (line 245-291) ...

    # Extend known-type prefix check loop (line 264-291):
    # After "merger_" block, add:
    if ntype.startswith("detector_"):
        registry_name = ntype[len("detector_"):]
        import src.perception.backends  # noqa: F401
        from src.perception.registry import DetectorRegistry
        names = [b["name"] for b in DetectorRegistry.list_backends()]
        if registry_name not in names:
            raise ValueError(f"Unknown detector backend: {registry_name}. Available: {names}")
        continue
    if ntype.startswith("detection3d_"):
        registry_name = ntype[len("detection3d_"):]
        import src.perception.lifters  # noqa: F401
        from src.perception.registry import Detection3DRegistry
        names = [b["name"] for b in Detection3DRegistry.list_backends()]
        if registry_name not in names:
            raise ValueError(f"Unknown 3D lifter: {registry_name}. Available: {names}")
        continue
    if ntype.startswith("tracker_"):
        registry_name = ntype[len("tracker_"):]
        import src.tracking.trackers  # noqa: F401
        from src.tracking.registry import TrackerRegistry
        names = [b["name"] for b in TrackerRegistry.list_backends()]
        if registry_name not in names:
            raise ValueError(f"Unknown tracker: {registry_name}. Available: {names}")
        continue

    # Find nodes (line 294-298): ADD these 3 finds
    detector_node = None
    detection3d_node = None
    tracker_node = None
    for node in nodes:
        if node["type"].startswith("detector_"):
            detector_node = node
        elif node["type"].startswith("detection3d_"):
            detection3d_node = node
        elif node["type"].startswith("tracker_"):
            tracker_node = node

    # ... existing _validate_required_connections + _resolve_param_overrides ...

    # Extract config (line 307-317): ADD these 6 extractions
    detector_name = "yolov11"
    detector_params: dict = {}
    if detector_node is not None:
        detector_name = detector_node["type"][len("detector_"):]
        detector_params = dict(detector_node.get("params", {}))

    lifter_name = "point_cluster"
    lifter_params: dict = {}
    if detection3d_node is not None:
        lifter_name = detection3d_node["type"][len("detection3d_"):]
        lifter_params = dict(detection3d_node.get("params", {}))

    tracker_name = "none"
    tracker_params: dict = {}
    if tracker_node is not None:
        tracker_name = tracker_node["type"][len("tracker_"):]
        tracker_params = dict(tracker_node.get("params", {}))

    # Extend PipelineConfig construction (line 329):
    return PipelineConfig(
        backend_name=backend_name,
        backend_params=backend_params,
        merger_name=merger_name,
        merger_params=merger_params,
        filter_chain=filter_chain,
        detector_name=detector_name,
        detector_params=detector_params,
        lifter_name=lifter_name,
        lifter_params=lifter_params,
        tracker_name=tracker_name,
        tracker_params=tracker_params,
    )
```

### Pattern Template 8 — `perception_rgbd.json` preset

**Location:** `data/presets/builtin/perception_rgbd.json` (new file)

Clone structure from `default_icp.json` (shape: `{name, nodes[], edges[]}` — no top-level `builtIn` field; `builtIn` is inferred from directory per `pipeline_routes.py:76`).

```json
{
  "name": "Perception + RGBD",
  "nodes": [
    {"id": "sensor_1", "type": "sensor_rgbd", "params": {}, "position": {"x": 50, "y": 225}},
    {"id": "slam_1", "type": "slam_icp", "params": {}, "position": {"x": 350, "y": 100}},
    {"id": "merger_1", "type": "merger_icp_union", "params": {}, "position": {"x": 650, "y": 100}},
    {"id": "detector_1", "type": "detector_yolov11", "params": {}, "position": {"x": 350, "y": 300}},
    {"id": "detection3d_1", "type": "detection3d_point_cluster", "params": {}, "position": {"x": 650, "y": 300}},
    {"id": "tracker_1", "type": "tracker_none", "params": {}, "position": {"x": 950, "y": 300}},
    {"id": "viz_1", "type": "viz_output", "params": {}, "position": {"x": 1150, "y": 200}}
  ],
  "edges": [
    {"source": "sensor_1", "sourceHandle": "image_out", "target": "slam_1", "targetHandle": "image_in"},
    {"source": "slam_1", "sourceHandle": "cloud_out", "target": "merger_1", "targetHandle": "cloud_in"},
    {"source": "slam_1", "sourceHandle": "pose_out", "target": "merger_1", "targetHandle": "pose_in"},
    {"source": "merger_1", "sourceHandle": "merged_out", "target": "viz_1", "targetHandle": "cloud_in"},
    {"source": "slam_1", "sourceHandle": "pose_out", "target": "viz_1", "targetHandle": "pose_in"},

    {"source": "sensor_1", "sourceHandle": "image_out", "target": "detector_1", "targetHandle": "image_in"},
    {"source": "sensor_1", "sourceHandle": "depth_out", "target": "detector_1", "targetHandle": "depth_in"},
    {"source": "detector_1", "sourceHandle": "detections_2d_out", "target": "detection3d_1", "targetHandle": "detections_2d_in"},
    {"source": "sensor_1", "sourceHandle": "depth_out", "target": "detection3d_1", "targetHandle": "depth_in"},
    {"source": "detection3d_1", "sourceHandle": "detections_3d_out", "target": "tracker_1", "targetHandle": "detections_3d_in"},
    {"source": "tracker_1", "sourceHandle": "tracks_out", "target": "viz_1", "targetHandle": "tracks_in"}
  ]
}
```

**Registration:** The `detector_yolov11`, `detection3d_point_cluster`, `tracker_none` types come from `NodeCatalog.get_catalog()` enumeration (Pattern Template 5). Preset load in `pipeline_routes.py::load_preset` line 107 streams the JSON verbatim; the frontend's `deserializeGraph` (already existing at `pipelineSerializer.ts:58`) resolves via prefix match (line 67-70) — which means `detector_yolov11` matches `detector_generic` definition automatically with `nodeType` preserved. **Verify this works** by testing the preset load roundtrip; if the prefix-match heuristic (`configNode.type.split('_')[0]`) only matches the FIRST underscore-delimited segment (e.g., `detector_yolov11`.split('_')[0] === `'detector'` — good), it should work. If `detection3d_point_cluster` breaks (`split('_')[0]` === `'detection3d'` — need to check `detection3d_generic` matches), confirm in the integration test.

**Pitfall caught by inspection:** `pipelineSerializer.ts:67-70` uses `configNode.type.split('_')[0] + '_'` as the prefix and then looks for a definition where `type.startsWith(prefix + '_')`. For `detection3d_point_cluster` → prefix `'detection3d_'` → matches `detection3d_generic`. For `tracker_none` → prefix `'tracker_'` → matches `tracker_generic`. For `detector_yolov11` → prefix `'detector_'` → matches `detector_generic`. ALL THREE ARE FINE. No serializer change needed.

### Pattern Template 9 — `apply_pipeline` hot-apply diff

**Location:** `backend/web/pipeline_routes.py:43-63` — rewrite handler:

```python
from dataclasses import asdict

@router.post("/apply")
async def apply_pipeline(req: PipelineApplyRequest, request: Request):
    """Validate and apply a pipeline graph configuration (D-10 diff-then-dispatch)."""
    builder = PipelineBuilder()
    try:
        config = builder.build({"nodes": req.nodes, "edges": req.edges})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Diff against last applied config (D-10 / D-12).
    last = getattr(request.app.state, "last_applied_pipeline_config", None)
    topology_digest = _digest_topology(req.nodes, req.edges)

    if last is not None:
        last_topology = getattr(request.app.state, "last_applied_topology_digest", None)
        structural_unchanged = (
            topology_digest == last_topology
            and config.backend_name == last.backend_name
            and config.backend_params == last.backend_params
            and config.merger_name == last.merger_name
            and config.merger_params == last.merger_params
            and config.filter_chain == last.filter_chain
            and config.tracker_name == last.tracker_name
            and config.tracker_params == last.tracker_params
        )
        detector_changed = (
            config.detector_name != last.detector_name
            or config.detector_params != last.detector_params
        )
        lifter_changed = (
            config.lifter_name != last.lifter_name
            or config.lifter_params != last.lifter_params
        )
        if structural_unchanged and (detector_changed or lifter_changed):
            # HOT-APPLY PATH
            pool = getattr(request.app.state, "detector_pool", None)
            if pool is None:
                raise HTTPException(status_code=503, detail="Detector pool not initialized")
            changed: list[str] = []
            if detector_changed:
                try:
                    pool.swap_backend(config.detector_name, config.detector_params)
                except (ValueError, ImportError) as exc:
                    raise HTTPException(status_code=400, detail=f"swap_backend failed: {exc}")
                request.app.state.active_detector_backend = config.detector_name
                request.app.state.pending_detector_params = dict(config.detector_params)
                changed.append("detector_name" if config.detector_name != last.detector_name else "detector_params")
            if lifter_changed:
                try:
                    pool.swap_lifter(config.lifter_name, config.lifter_params)
                except (ValueError, ImportError) as exc:
                    raise HTTPException(status_code=400, detail=f"swap_lifter failed: {exc}")
                request.app.state.active_lifter = config.lifter_name
                request.app.state.pending_lifter_params = dict(config.lifter_params)
                changed.append("lifter_name" if config.lifter_name != last.lifter_name else "lifter_params")
            request.app.state.last_applied_pipeline_config = config
            request.app.state.last_applied_topology_digest = topology_digest
            return {
                "status": "hot-applied",
                "changed": changed,
                "active_detector": config.detector_name,
                "active_lifter": config.lifter_name,
            }

    # RESTART PATH (existing)
    request.app.state.pending_pipeline_config = config
    request.app.state.last_applied_topology_digest = topology_digest
    # last_applied_pipeline_config is updated AFTER successful restart in main.py
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting"}


def _digest_topology(nodes: list[dict], edges: list[dict]) -> tuple:
    """Stable topology digest: sorted node ids + sorted edge tuples."""
    node_ids = tuple(sorted(n["id"] for n in nodes))
    edge_tuples = tuple(sorted(
        (e["source"], e.get("sourceHandle", ""), e["target"], e.get("targetHandle", ""))
        for e in edges
    ))
    return (node_ids, edge_tuples)
```

**Key design notes:**
- The topology digest is computed from REQUEST (not config) because `PipelineConfig` doesn't carry raw edges — digest is about node IDs + edges, not interpreted config fields.
- `last_applied_topology_digest` is a new `app.state` attribute — stored alongside the config for cheap comparison.
- On restart path: set `last_applied_topology_digest` NOW so the next apply can diff against it. Update `last_applied_pipeline_config` in `main.py:~625` AFTER successful pool rebuild (D-12).
- On hot-apply path: update both atomically after successful swap.

### Pattern Template 10 — `DetectorWorkerPool.swap_backend` (Python mirror of `swap_lifter`)

**Location:** `src/perception/worker_pool.py:315` (insert after `swap_lifter` ends at line 315)

```python
def swap_backend(
    self,
    new_backend_name: str,
    new_backend_params: dict | None = None,
) -> None:
    """Hot-swap the detector on every worker atomically (D-11).

    Mirror of :meth:`swap_lifter` — see that method's docstring for the
    invariant rationale (atomic ref swap under GIL + ``_swap_lock``,
    construct-outside-lock + rebind-inside-lock).

    Differences from swap_lifter:
      1. Warmup is MANDATORY (backends are stateful — ONNX sessions, ultralytics
         models, subprocess bridges all need cold-path first-inference). We call
         ``.warmup(dummy_frame)`` OUTSIDE the lock for each fresh backend before
         the ref rebind.
      2. On any single warmup failure, we abort the swap (no partial) and raise —
         the caller (pipeline_routes.py::apply_pipeline) converts this to a 400
         response with the vendor reason. No worker is mutated on failure.
      3. Emits ``detector_swap_complete`` WS envelope via the streaming_viz queue
         (parallel to ``detector_restart_complete`` but with ``reason: "hot_swap"``
         discriminator — see CONTEXT Claude's Discretion #6; planner chooses
         between new type and reused type with discriminator).

    Does NOT reset worker queue state (retain drops_since_session_start for
    metrics continuity). In-flight process_frame calls complete on OLD backend
    per Phase 4 Pitfall 6 (documented, not a bug).
    """
    # Force @detector_backend registration (Pattern: every public entry point
    # runs this import so cold-boot lookups succeed).
    import src.perception.backends  # noqa: F401

    backend_kwargs = dict(new_backend_params or {})

    # Construct + warm per-worker OUTSIDE the lock. If any step fails for any
    # worker, raise before touching existing worker state.
    new_detectors: dict[str, Any] = {}
    for rid in self._workers:
        det = DetectorRegistry.create(new_backend_name, **backend_kwargs)
        det.warmup(self._dummy_frame_for(rid))
        new_detectors[rid] = det

    # Atomic rebind under _swap_lock (≪1ms).
    with self._swap_lock:
        for rid, w in self._workers.items():
            w._detector = new_detectors[rid]
        self.backend_name = new_backend_name
        self._backend_params = backend_kwargs

    # Emit WS envelope (best-effort; failure logged but swap already succeeded).
    viz = self._streaming_viz
    if viz is not None and hasattr(viz, "_message_queue"):
        try:
            viz._message_queue.append({
                "type": "detector_swap_complete",
                "payload": {
                    "backend": new_backend_name,
                    "reason": "hot_swap",
                },
            })
        except Exception:  # noqa: BLE001
            _LOGGER.exception("swap_backend: failed to enqueue detector_swap_complete")
```

**Existing pattern verified:** `DetectorWorker._detector` attribute exists (assigned in `src/perception/worker.py`'s `__init__` by the pool at `worker_pool.py:183-189`). `_detector` is the attribute the worker reads inside its `_loop` — same as `_lifter` for the lifter swap.

### Pattern Template 11 — `src/tracking/` package skeleton

**Location:** new directory tree.

**`src/tracking/protocol.py`:**
```python
"""TrackerProtocol: runtime-checkable interface for detection trackers.

Mirror of src.perception.protocol structure. Phase 7 ships NoneTracker
(passthrough); Phase 8 ships ByteTrack. Pool integration is Phase 8 (D-14).
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.perception.types import Detections3D


@runtime_checkable
class TrackerProtocol(Protocol):
    """Runtime-checkable interface for multi-object trackers."""

    CAPABILITIES: dict

    def track(self, detections_3d: "Detections3D") -> "Detections3D":
        """Stamp track_id on each box in the envelope, return a cloned envelope.

        Contract:
          - MUST NOT mutate geometry fields (center, half_extents, quaternion).
          - MUST only modify track_id.
          - Returned envelope carries the same capture_pose + capture_timestamp
            as the input (Phase 2 D-11 invariant preserved).
        """
        ...

    def reset(self) -> None:
        """Clear internal state (per-session or per-restart)."""
        ...
```

**`src/tracking/registry.py`:** clone `src/perception/registry.py::DetectorRegistry` pattern at Pattern Template's simpler shape — only `register`, `list_backends`, `create`, `get_default`, `_clear`. Drop the `_validate_capabilities` machinery to a simple `license` + `framework` + `produces_stable_ids` required keys check. Default = `"none"`. 80-100 LOC.

**`src/tracking/trackers/__init__.py`:**
```python
"""Side-effect module — importing this registers all tracker backends."""
from . import none  # noqa: F401
```

**`src/tracking/trackers/none.py`:**
```python
"""NoneTracker: passthrough tracker that stamps monotonic track_ids (D-13)."""
from __future__ import annotations
from dataclasses import replace
from itertools import count
from typing import TYPE_CHECKING

from src.tracking.registry import tracker

if TYPE_CHECKING:
    from src.perception.types import Detections3D


@tracker(name="none", display="Passthrough (no tracking)")
class NoneTracker:
    CAPABILITIES = {
        "framework": "stub",
        "produces_stable_ids": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None

    def __init__(self) -> None:
        self._counter = count(start=0)

    def track(self, detections_3d: "Detections3D") -> "Detections3D":
        # Clone each box with a stamped track_id. dataclasses.replace is the
        # idiomatic path — OrientedBox3D is a frozen dataclass in Phase 1.
        new_boxes = [replace(b, track_id=next(self._counter)) for b in detections_3d.boxes]
        return replace(detections_3d, boxes=new_boxes)

    def reset(self) -> None:
        self._counter = count(start=0)
```

**CAUTION — `OrientedBox3D` mutability:** Check `src/perception/types.py` — if `OrientedBox3D` is a frozen dataclass, `replace` works. If it's not frozen but has slots, `replace` still works. If it's a regular class with `__init__` assignments, construct a new instance with the same fields + new `track_id`. Verify at planning time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Edge `dataType` inference on connect | Custom match logic | Source node + source handle lookup (Pattern Template 6) | React Flow's `Connection` API already provides `sourceHandle` — any other path recreates work |
| Topology diff | Custom structural equality walker | `tuple(sorted(ids))` + `tuple(sorted(edge_tuples))` comparison | Stable + cheap + stdlib |
| Registry side-effect import | Manual registry population in tests | `import src.tracking.trackers` at test fixture setup | Mirror of Phase 1 / Phase 5 precedent; tests in `tests/coordination/test_pipeline_builder.py:14-27` already use this pattern |
| Atomic ref swap | Double-buffered worker pool rebuild | `_swap_lock` + attribute-write under GIL (`swap_lifter` template) | Phase 4 D-10 proved this pattern; SLAM-pool rebuild is an order of magnitude slower |
| Preset reload on frontend | Custom deserialization | `pipelineSerializer.ts::deserializeGraph` (existing) — prefix-match handles `detector_yolov11` via `detector_` lookup | Already works for `slam_icp` / `merger_icp_union` — same code path |
| React Flow type union exhaustiveness | `Partial<Record<PortDataType, string>>` + runtime fallbacks | Strict `Record<PortDataType, string>` + force compile-time exhaustiveness | Catches "added enum value, forgot color" bugs at build time, not runtime |
| Dummy warmup frame for swap_backend | Per-call frame capture from bridge | `pool._dummy_frame_for(rid)` (existing helper at `worker_pool.py:320`) | Already used by on_backend_crash; reuse verbatim |

**Key insight:** Phase 4 (lifter hot-swap) and Phase 5 (crash fallback) already built the atomic-swap machinery. Phase 7's `swap_backend` is a 40-LOC mirror, not a new system.

## Runtime State Inventory

Phase 7 is purely additive (new files, extended types, extended registries). No rename / migration. **No runtime state inventory required.**

- **Stored data:** None — no existing datastore references `detector_`, `detection3d_`, `tracker_` strings.
- **Live service config:** None — no n8n / Datadog / Tailscale references.
- **OS-registered state:** None — no systemd / Task Scheduler / launchd registration uses these strings.
- **Secrets / env vars:** None.
- **Build artifacts:** None — new Python package `src/tracking/` will need a fresh `pip install -e .` if argus is editable-installed, but `pyproject.toml` auto-discovers via `packages = ["src", "backend"]` (line 21). New subpackage `src.tracking` imported automatically at next run. **No rebuild step.**

## Environment Availability

Phase 7 has NO external dependencies beyond what Phase 1-6 already verified available.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.10-3.12 | src/ | ✓ | >=3.10,<3.13 from pyproject.toml | — |
| `pytest`, `pytest-asyncio` | tests/ | ✓ | >=8.0.0 / >=0.23.0 (dev extra) | — |
| Node.js + npm | frontend/ | ✓ | (Phase 3 established) | — |
| `vitest` + `jsdom` | frontend/src/**/__tests__/ | ✓ | 4.1.4 / 29.0.2 | — |
| `@xyflow/react` | pipelineStore + editor | ✓ | 12.10.1 | — |
| `fastapi` + `pydantic` | backend/web/ | ✓ | >=0.100.0 | — |

**No missing dependencies.** No install step needed.

## Common Pitfalls

### Pitfall 1: Prefix-match ambiguity in PipelineBuilder

**What goes wrong:** `detection3d_point_cluster` starts with `detector_` as a substring (no — it starts with `detection3d_`, which does NOT collide with `detector_`). But `detector_` and `detection3d_` and `detector_rtdetrv2` are siblings — be careful about ordering of the prefix checks.
**Why it happens:** Python `str.startswith` checks in order; the first match wins.
**How to avoid:** List explicit prefixes and use equality after stripping. Test harness `test_pipeline_builder_perception.py` MUST cover: a graph with all three perception node types + a detector_rtdetrv2 + a detection3d_median_depth + a tracker_none; assert all fields populate correctly.
**Warning signs:** A preset loads but `config.detector_name` is empty, OR `config.detector_name == "3d_point_cluster"` (if `detector_` matched `detection3d_` by accident).

### Pitfall 2: Missing side-effect import in apply_pipeline

**What goes wrong:** First request after server boot calls `NodeCatalog.get_catalog()` → returns empty detector/lifter/tracker sections because registries haven't been imported yet.
**Why it happens:** `pipeline_routes.py` module imports `PipelineBuilder` + `NodeCatalog` but NOT `src.perception.backends` / `src.perception.lifters` / `src.tracking.trackers`. `NodeCatalog.get_catalog` must do it inline (as Phase 7 Pattern Template 5 shows).
**How to avoid:** Every public entry point (`get_catalog`, `apply_pipeline`, `swap_backend`) runs the side-effect import. Test: `test_list_lifters_cold_boot_triggers_registry_population`-style cold-boot test for Tracker + the extended NodeCatalog.
**Warning signs:** Frontend palette shows only `slam_generic` / `merger_generic` entries; no YOLOv11 / PointCluster / None.

### Pitfall 3: `last_applied_pipeline_config` stale after crash fallback

**What goes wrong:** User applies `detector_rtdetrv2` → subprocess crashes → `on_backend_crash` swaps to `yolov11`. User then applies a graph that switches detector BACK to `yolov11`. Diff sees `last.detector_name == "rtdetrv2"` (stale) vs new `yolov11` → hot-applies → but the pool is ALREADY on yolov11 → `pool.swap_backend("yolov11")` is a no-op but still returns success. Confusing but not broken. The worse variant: user apply `yolov11` while crash-fallback has just set availability=False for rtdetrv2 → but we're applying yolov11, not rtdetrv2, so no 400.
**Why it happens:** Crash path bypasses `apply_pipeline`; `last_applied_pipeline_config.detector_name` doesn't auto-update.
**How to avoid:** Per CONTEXT D-12, update `last_applied_pipeline_config.detector_name = fallback` inside `on_backend_crash` (worker_pool.py line ~450). Single-line append in the existing handler.
**Warning signs:** Diff incorrectly classifies a no-op as "restart needed". Failure mode is conservative (extra restart, not data loss), but still annoying.

### Pitfall 4: `deserializeGraph` prefix-match collision

**What goes wrong:** `pipelineSerializer.ts:67-70` uses `configNode.type.split('_')[0]` — for `detection3d_point_cluster`, that's `'detection3d'`; it then searches for a definition with `type.startsWith('detection3d' + '_')`. If the definition is `detection3d_generic`, it matches. BUT — if someone inadvertently adds a definition called `detection3_foo` (typo), it won't match. More realistically: `tracker_none` → split → `'tracker'` → looks for `tracker_generic` — good. `detector_yolov11` → `'detector'` → `detector_generic` — good. No collision in the defined set.
**Why it happens:** `split('_')[0]` only takes the FIRST segment. `detection3d` is one segment (underscore comes after), so this is fine.
**How to avoid:** Unit test `tests/frontend/pipelineSerializer.round_trip.test.ts` that loads `perception_rgbd.json`, deserializes, re-serializes, asserts equality.
**Warning signs:** Loading the preset shows nodes without parameter schemas or missing port definitions.

### Pitfall 5: `ApplyBar` loses the restart-complete trigger on hot-apply

**What goes wrong:** `ApplyBar.tsx:45-47` calls `store.markApplied()` + comment says `isApplying cleared by slam_restart_complete WS handler`. On the hot-apply path, `slam_restart_complete` is NEVER emitted (no restart happened). Result: `isApplying` stays true forever; Apply button permanently disabled.
**Why it happens:** Existing code assumes restart flow; hot-apply is a new branch.
**How to avoid:** In the `hot-applied` branch of the response handler, call `setIsApplying(false)` directly after `markApplied()`.
```typescript
.then((res) => { if (!res.ok) throw new Error(...); return res.json(); })
.then((body) => {
  usePipelineStore.getState().markApplied();
  if (body.status === 'hot-applied') {
    usePipelineStore.getState().setIsApplying(false);
    // Show non-blocking success toast
  }
  // status === 'restarting': isApplying cleared by slam_restart_complete handler (existing path)
})
```
**Warning signs:** After hot-apply, Apply button stays greyed; user must refresh to recover.

### Pitfall 6: `PipelineConfig` default values obscure "user chose default" vs "user omitted"

**What goes wrong:** User's graph has NO detector node. `PipelineBuilder.build` falls through to `detector_name = "yolov11"` default. If user's `last_applied_pipeline_config.detector_name` was "rtdetrv2" (explicit pick) and the new config has no detector node, the diff says "detector_name changed" → attempts hot-swap to yolov11 → but intent was unclear.
**Why it happens:** A missing detector node is interpreted as "use default", indistinguishable from "user explicitly picked default".
**How to avoid:** Decision needed at planning time — either (a) treat missing detector node as "no change to current detector" (use `last.detector_name` as the default in `build`), OR (b) accept the current semantics (missing node → default). Option (b) is simpler and matches existing SLAM behavior at line 307-311; recommend documenting the invariant in a test.
**Warning signs:** User removes detector node from graph, pipeline silently reverts to yolov11.

### Pitfall 7: Tracker registration side-effect never loads (Python import order)

**What goes wrong:** `NodeCatalog.get_catalog()` imports `src.tracking.trackers`; side-effect loads `src.tracking.trackers.none`. But `none.py` decorator `@tracker(name="none", ...)` runs at import time — which calls `TrackerRegistry.register`. If `TrackerRegistry` has a class-level `_backends: dict = {}` and is cleared at test teardown without re-importing `none.py`, the next test sees an empty registry.
**Why it happens:** Python caches imported modules in `sys.modules`; the second import is a no-op. Re-importing after `_clear` is the fix.
**How to avoid:** Test fixtures that call `TrackerRegistry._clear()` MUST call `importlib.reload(src.tracking.trackers.none)` OR use `autouse=True` fixture with `TrackerRegistry._clear() + import src.tracking.trackers`. Mirror of existing `tests/coordination/test_pipeline_builder.py:14-27` pattern (which does this for SLAMRegistry + MergeRegistry).
**Warning signs:** First test passes, second test fails with `tracker_none` not in registry.

### Pitfall 8: `DetectorWorkerPool.swap_backend` warmup failure mid-swap leaves bad state

**What goes wrong:** In a 3-robot setup, backend constructs + warms for robot 0 + robot 1 succeed; robot 2 warmup raises. Half-constructed state.
**Why it happens:** Loop iterates sequentially.
**How to avoid:** Construct ALL backends + warm ALL of them BEFORE touching any worker's `_detector`. If any construction or warmup raises, raise immediately — no worker has been mutated. The lock-acquisition step only happens if EVERY new backend is ready. Pattern Template 10 implements this — verify test coverage catches it (e.g., parametrize `new_detectors[rid]` to raise on rid==2, assert no worker's `_detector` changed).
**Warning signs:** After a failed swap, `pool.backend_name` mismatches actual worker backends; next `submit` uses mixed backends per robot.

## Code Examples

### Verify CONTEXT.md `onConnect` fix

```typescript
// Source: CONTEXT.md D-08 literal
onConnect: (connection) =>
  set((state) => {
    const sourceNode = state.nodes.find((n) => n.id === connection.source);
    const sourcePort = sourceNode?.data.outputs.find((p) => p.id === connection.sourceHandle);
    const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
    return {
      edges: addEdge(
        { ...connection, type: 'animated', data: { fps: 0, dataType } },
        state.edges,
      ) as PipelineEdge[],
      isDirty: true,
    };
  }),
```

### swap_lifter template (existing — DO NOT modify; reference only)

```python
# Source: src/perception/worker_pool.py:269-314
def swap_lifter(self, new_lifter_name: str, new_lifter_params: dict | None = None) -> None:
    import src.perception.lifters  # noqa: F401
    lifter_kwargs = dict(new_lifter_params or {})
    new_lifters = {
        rid: Detection3DRegistry.create(new_lifter_name, **lifter_kwargs)
        for rid in self._workers
    }
    with self._swap_lock:
        for rid, w in self._workers.items():
            w._lifter = new_lifters[rid]
        self.lifter_name = new_lifter_name
        self._lifter_params = lifter_kwargs
```

### Existing hot-swap REST route (template for thinking about the diff endpoint)

```python
# Source: backend/web/detector_routes.py:157-202 — lifter_hotswap
# Shows: side-effect import + registry validation + 404/400/503 gates + pool call
```

## State of the Art

| Old Approach (pre-Phase 7) | Current Approach (Phase 7) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pipeline apply always restarts | Server-side diff short-circuits to `swap_backend` / `swap_lifter` for perception-only changes | Phase 7 D-10 | SC#4 — PID stability test |
| `pipelineStore.ts:101` hardcodes `dataType: 'PointCloud'` | Source-handle dataType resolution | Phase 7 D-08 | Fixes long-standing bug flagged in DET-PIPELINE-03 |
| `validateGraph` checks cycles + unconnected + missing-output only | Adds `findPortTypeMismatches` as second check | Phase 7 D-09 | Per-edge errors surface mismatched types before structural errors |
| No tracker abstraction | `src/tracking/` package with Protocol + Registry + NoneTracker | Phase 7 D-13 | Makes ByteTrack a drop-in for Phase 8 |
| No perception preset | `perception_rgbd.json` with parallel SLAM + perception branches | Phase 7 D-15 | SC#3 — one-click live OBBs |

**Deprecated / outdated:**
- None in the scope of Phase 7. All Phase 7 additions are new surface; no existing API is deprecated.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `OrientedBox3D` supports `dataclasses.replace(box, track_id=...)` cleanly | Pattern Template 11 NoneTracker | LOW — planner verifies at implementation time by reading `src/perception/types.py:109`; if not a dataclass, construct manually. |
| A2 | `@xyflow/react` 12.10's `Connection` always carries `sourceHandle` under `onConnect` | Pattern Template 6 | LOW — `?? 'PointCloud'` defensive fallback covers the edge case. Verified behavior by inspecting `frontend/node_modules/@xyflow/react`. |
| A3 | `pipelineSerializer.ts:67-70` prefix-match handles `detection3d_point_cluster` correctly | Pattern Template 8 | MEDIUM — explicit inspection shows `'detection3d_'` prefix matches `detection3d_generic.type`. Integration test (load perception_rgbd preset, assert 7 nodes deserialize) catches any mismatch. |
| A4 | `last_applied_pipeline_config` is not yet on `app.state` anywhere in the codebase | Pattern Template 9 | LOW — grep confirms only CONTEXT.md and this RESEARCH.md reference it; `main.py` only sets `pending_pipeline_config` today. Phase 7 introduces it fresh. |
| A5 | `_digest_topology` using `tuple(sorted(...))` is stable across JSON key-ordering differences | Pattern Template 9 | LOW — sorted tuples are deterministic; `json.loads` preserves key order within a single request but we sort both sides. |
| A6 | Hot-swap warmup fits inside a ~30s FastAPI request timeout | Pattern Template 10 | MEDIUM — RT-DETRv2 cold-start is ~25s per Phase 5 SC#1; BoxeR subprocess spawn may exceed 30s. Planner should consider async-apply + polling if a backend is known-slow. For Phase 7 test coverage, YOLOv11 ↔ RT-DETRv2 swap is the SC#4 target — both are in-process and within budget. |

**If this table grows during planning:** Each `[ASSUMED]` claim needs confirmation before the plan locks. Currently 6 low-risk assumptions, all verifiable via codebase inspection at plan-write time.

## Open Questions

1. **Should `detector_swap_complete` be a new WS type or reuse `detector_restart_complete`?**
   - What we know: CONTEXT §Claude's Discretion item #6 leaves this open with slight preference for new type.
   - What's unclear: Frontend consumers — `useWebSocket.ts:155` has a single `detector_restart_complete` branch. Adding a discriminator (`reason: "hot_swap"`) vs a new case is stylistic.
   - Recommendation: New type `detector_swap_complete` — cleaner consumer logic, easier to add distinct UI affordance (success toast vs restart overlay). Cost is one extra case in the switch — negligible.

2. **Should `PipelineBuilder.build` treat "no detector node" as "use last applied" or "use default"?**
   - What we know: Existing SLAM/merger logic at `pipeline_builder.py:307-311` treats missing nodes as "use default" (`"icp"` / `"icp_union"`).
   - What's unclear: If the user presets a SLAM-only graph (no perception nodes), the diff will say "detector changed from current to yolov11 default" and attempt hot-swap.
   - Recommendation: Match existing semantics (missing → default). Document in a test that "SLAM-only preset triggers diff to default detector_name". If UX is bad in practice, Phase 8 can revisit — not a regression, since Phase 6 and earlier never had pipeline-driven detector changes.

3. **Does `NoneTracker` need to be idempotent across frames (same detection → same track_id)?**
   - What we know: CONTEXT D-13 says session-lifetime monotonic counter; `produces_stable_ids: false`.
   - What's unclear: If the same chair is detected across frames, does each detection get a new track_id? Yes, per the counter semantics. That's why `produces_stable_ids: false`.
   - Recommendation: Document in NoneTracker docstring: "Each frame's detections receive fresh incrementing IDs; IDs are NOT stable across frames. For stable IDs, use `tracker_bytetrack` (Phase 8)."

## Validation Architecture

> workflow.nyquist_validation absent in `.planning/config.json` → treat as enabled. `workflow.verifier: true` confirms validation is expected.

### Test Framework
| Property | Value |
|----------|-------|
| Python framework | pytest >=8.0.0 + pytest-asyncio >=0.23.0 |
| Python config | `pyproject.toml` [tool.pytest.ini_options] (line 47-51) + markers: `slow_boxer`, `network` |
| Frontend framework | vitest 4.1.4 + jsdom 29.0.2 |
| Frontend config | `frontend/vitest.config.ts` |
| Python quick run | `pytest tests/coordination/test_pipeline_builder_perception.py -x` |
| Python full suite | `pytest -x` (excludes slow_boxer + network by default) |
| Frontend quick | `cd frontend && npm run test -- src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` |
| Frontend full | `cd frontend && npm run test` |
| Phase gate | Both green before `/gsd-verify-work` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-PIPELINE-01 | `perception` category in palette with 3 node types | vitest unit | `cd frontend && npm run test -- src/utils/__tests__/nodeDefinitions.perception.test.ts` | Wave 0 (planned) |
| DET-PIPELINE-01 SC#1 | Drag + connect Detections2D → Detections3D without error | vitest integration (jsdom) | `cd frontend && npm run test -- src/stores/__tests__/pipelineStore.connect.perception.test.ts` | Wave 0 (planned) |
| DET-PIPELINE-02 | Port colors + types extended | vitest snapshot | `cd frontend && npm run test -- src/utils/__tests__/portColors.test.ts` | Wave 0 (planned) |
| DET-PIPELINE-03 | `pipelineStore.ts:101` regression | vitest unit | `cd frontend && npm run test -- src/stores/__tests__/pipelineStore.dataType.test.ts` | Wave 0 (planned) — named in CONTEXT |
| DET-PIPELINE-03 | Per-edge type mismatch error | vitest unit | `cd frontend && npm run test -- src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` | Wave 0 (planned) — named in CONTEXT |
| DET-PIPELINE-04 | `perception_rgbd.json` loads + builds | pytest contract | `pytest tests/contract/test_perception_rgbd_preset.py -x` | Wave 0 (planned) |
| DET-PIPELINE-04 SC#3 | Preset apply → live OBBs | pytest integration (slow, optional MuJoCo) | `pytest tests/integration/test_perception_rgbd_end_to_end.py -x` | Wave 0 (planned) |
| DET-PIPELINE-05 | `PipelineConfig` populated with detector/lifter/tracker | pytest unit | `pytest tests/coordination/test_pipeline_builder_perception.py -x` | Wave 0 (planned) |
| DET-PIPELINE-05 SC#4 | Hot-apply changes backend without restart | pytest integration | `pytest tests/integration/test_pipeline_apply_hot.py -x` | Wave 0 (planned) |
| DET-PIPELINE-05 (swap_backend) | Pool swap atomicity | pytest unit | `pytest tests/perception/test_swap_backend.py -x` | Wave 0 (planned) |
| DET-PIPELINE-05 (tracker registry) | `TrackerRegistry.list()` / `create()` | pytest unit | `pytest tests/tracking/test_tracker_registry.py -x` | Wave 0 (planned) |

### Sampling Rate
- **Per task commit:** run the specific test file(s) for that task (add to task's verification line)
- **Per wave merge:** `pytest tests/coordination/ tests/tracking/ tests/perception/test_swap_backend.py -x` + `cd frontend && npm run test`
- **Phase gate:** full suite both sides green — `pytest -x` + `cd frontend && npm run test`

### Wave 0 Gaps (all 11 test files below need skip-stub scaffolds)

- [ ] `tests/coordination/test_pipeline_builder_perception.py` — covers DET-PIPELINE-05 (PipelineConfig extension + build extension + perception catalog entries)
- [ ] `tests/tracking/__init__.py` — package marker
- [ ] `tests/tracking/test_tracker_registry.py` — TrackerRegistry list/create/available roundtrip
- [ ] `tests/perception/test_swap_backend.py` — swap_backend atomicity + per-worker isolation + warmup-failure rollback
- [ ] `tests/integration/test_pipeline_apply_hot.py` — SC#4 PID-stability + status response branching
- [ ] `tests/contract/test_perception_rgbd_preset.py` — DET-PIPELINE-04 preset JSON builds cleanly
- [ ] `frontend/src/stores/__tests__/pipelineStore.dataType.test.ts` — SC#2 regression (named in CONTEXT.md)
- [ ] `frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts` — SC#1 drag + connect
- [ ] `frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` — SC#2 lockdown (named in CONTEXT.md)
- [ ] `frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts` — definitions + port colors extension
- [ ] `frontend/src/utils/__tests__/portColors.test.ts` — strict Record exhaustiveness (optional — TypeScript catches at build)

**Framework install:** not needed — pytest + vitest are installed.

## Security Domain

> `security_enforcement` is absent from `.planning/config.json` → treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Coordinator is single-user local session; no auth surface |
| V3 Session Management | no | No session state beyond in-process app.state |
| V4 Access Control | no | No multi-tenant surface |
| V5 Input Validation | yes | pydantic `PipelineApplyRequest` validates payload shape (existing); PipelineBuilder raises ValueError → 422 on unknown node types (existing, extended to perception prefixes) |
| V6 Cryptography | no | No secrets / signing in scope |
| V9 Communications | yes | Internal REST over localhost only; no TLS gating needed for dev |
| V10 Malicious Code | yes | Preset JSON loaded from disk — path traversal gate already in `pipeline_routes.py:107-131` (existing); perception_rgbd.json loaded by name |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arbitrary backend name via apply → unknown registry key | Tampering | `PipelineBuilder.build` raises ValueError for unknown `detector_` / `detection3d_` / `tracker_` prefix → HTTP 422 (Pattern Template 7) |
| Backend that fails to warmup / crashes on first inference | DoS | `swap_backend` warmup-outside-lock + rollback (Pitfall 8) — raises 400 without mutating pool |
| Concurrent apply requests racing swap_lifter + swap_backend | Tampering | Existing `_swap_lock` serializes all swaps (Phase 4 D-10 + Phase 5 D-03 share the lock) |
| Preset JSON with cycle / orphan node → infinite loop on deserialize | DoS | `PipelineBuilder._topological_sort` raises on cycle (existing, line 366-370); `validateGraph` on frontend catches before submit |
| `pending_pipeline_config` stale-read race | TOCTOU | Existing pattern — restart block reads under `_restart_lock` at `main.py:440-630`; hot-apply doesn't touch `pending_pipeline_config` (only touches `last_applied_pipeline_config`) |
| Preset path traversal via `load_preset?name=../../etc/passwd` | Tampering | Existing mitigation at `pipeline_routes.py:113-131` — direct filename match scoped to BUILTIN_DIR / USER_DIR, no `..` handling needed because `Path` joining with `f"{name}.json"` doesn't escape. **Verify:** planner tests with `name=../../../etc/passwd` to confirm. |

**No new threats introduced by Phase 7 beyond what Phase 1-6 already mitigated.**

## Sources

### Primary (HIGH confidence)
- **Codebase inspection (this session, 2026-04-15):**
  - `frontend/src/stores/pipelineStore.ts` (218 lines — full read)
  - `frontend/src/utils/pipelineValidation.ts` (111 lines — full read)
  - `frontend/src/utils/pipelineTypes.ts` (72 lines — full read)
  - `frontend/src/utils/nodeDefinitions.ts` (279 lines — full read)
  - `frontend/src/components/pipeline/NodePalette.tsx` (232 lines — full read)
  - `frontend/src/components/pipeline/ApplyBar.tsx` (171 lines — full read)
  - `frontend/src/components/pipeline/NodeInspector.tsx` (173 lines — full read)
  - `frontend/src/utils/pipelineSerializer.ts` (116 lines — full read, bug caught at line 112)
  - `frontend/src/hooks/useWebSocket.ts` (partial read — lines 1-80 + 130-210)
  - `backend/web/pipeline_routes.py` (147 lines — full read)
  - `backend/web/detector_routes.py` (299 lines — full read)
  - `src/coordination/pipeline_builder.py` (418 lines — full read)
  - `src/perception/worker_pool.py` (lines 1-440 — full-enough read for pattern)
  - `src/perception/registry.py` (367 lines — full read)
  - `src/slam/registry.py` (partial — lines 1-80)
  - `src/main.py` lines 440-640 (restart block — full read)
  - `data/presets/builtin/default_icp.json` + `comparison_mode.json` (full read)
  - `tests/coordination/test_pipeline_builder.py` lines 1-80
  - `frontend/src/stores/__tests__/detectorStore.shape.test.ts` lines 1-60
  - `pyproject.toml` lines 1-50
  - `frontend/package.json` full + `frontend/vitest.config.ts`
  - `frontend/node_modules/@xyflow/react/package.json` (version 12.10.1 confirmed)
- **`.planning/phases/07-pipeline-editor-perception-nodes/07-CONTEXT.md`** (307 lines — full read, 16 locked decisions)
- **`.planning/REQUIREMENTS.md`** (161 lines — full read, §DET-PIPELINE-01..05 + Out of Scope)
- **`.planning/ROADMAP.md`** (196 lines — full read, Phase 7 goal + SCs)
- **`.planning/STATE.md`** (partial read)

### Secondary (MEDIUM confidence)
- React Flow 12.10 `onConnect` contract — https://reactflow.dev/api-reference/types/on-connect — `Connection` carries `source`/`sourceHandle`/`target`/`targetHandle`, all non-null inside `onConnect` callback. Verified by source inspection of installed `@xyflow/react` 12.10.1 umd bundle.

### Tertiary (LOW confidence)
- None — all Phase 7 claims are codebase-verified or CITED from CONTEXT.md.

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all deps already installed and used by prior phases; npm/pypi version verification is against installed lockfiles.
- Architecture Patterns: HIGH — every pattern is a cited template from an existing, working file with line numbers.
- Pitfalls: HIGH — each pitfall is derived from direct code inspection (e.g., `ApplyBar.tsx:46` comment about `slam_restart_complete` dependency, `pipelineSerializer.ts:112` hardcoded duplicate bug).
- Validation Architecture: HIGH — test frameworks and config files verified; file paths for new tests follow existing conventions.
- Security Domain: HIGH — threat model additive on top of Phase 1-6 baseline; no new auth/crypto surface.

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days — stack is stable; only risk is a rare @xyflow/react minor version bump, but 12.x public API is stable)
