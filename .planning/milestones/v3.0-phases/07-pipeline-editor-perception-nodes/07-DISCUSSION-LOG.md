# Phase 7: pipeline-editor-perception-nodes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 07-pipeline-editor-perception-nodes
**Mode:** `--auto` (recommended defaults selected without user input)
**Areas discussed:** Node surface pattern, Port types + edge validation, Hot-swap apply path, Tracker scope, Built-in preset

---

## Node Surface Pattern (DET-PIPELINE-01)

**Gray area:** Do we ship concrete per-backend node types (DetectorNode_YOLOv11, DetectorNode_RTDETR, DetectorNode_BoxeR) or registry-driven generic node types (`detector_generic` + `detection3d_generic` + `tracker_generic`) with the backend picked via node param?

| Option | Description | Selected |
|--------|-------------|----------|
| Registry-driven generic (`detector_generic` + `detection3d_generic` + `tracker_generic`) | Mirror existing `slam_generic` / `merger_generic` pattern. One node type per stage; backend picked via `registryName` + `backend` param. Catalog auto-enumerates registry. | ✓ |
| Per-backend concrete node types | Ship `detector_yolov11`, `detector_rtdetrv2`, `detector_boxer` as distinct node defs. Each has hardcoded ports + labels. | |

**Selected option (auto):** Registry-driven generic — matches existing SLAM/merger pattern, halves maintenance cost for new backends, enables topology-preserving hot-swap via param change (SC#4).
**Rationale:** PROJECT.md explicitly frames DetectorRegistry as a mirror of SLAMRegistry; the pipeline editor should reflect that same abstraction. Concrete node types would create a second place that every new backend must be registered (node def file), with no UX benefit.

---

## Port Types + Edge Validation (DET-PIPELINE-02, DET-PIPELINE-03)

**Gray area A:** What new port types do we add to `PortDataType`?

| Option | Description | Selected |
|--------|-------------|----------|
| `Detections2D` + `Detections3D` + `Tracks` | Three new types, one per perception stage output. | ✓ |
| `DetectionEnvelope` (single type covering 2D + 3D) | One broader type; validation is weaker. | |
| `Detections2D` + `Detections3D` only (no `Tracks`) | Tracks reuse `Detections3D` type; tracker is transparent. | |

**Selected option (auto):** Three new types — preserves strict per-edge typing; SC#1 specifies three distinct nodes with typed ports.

**Gray area B:** How do we fix `pipelineStore.ts:101`'s hardcoded `dataType: 'PointCloud'`?

| Option | Description | Selected |
|--------|-------------|----------|
| Infer dataType from source handle's `PortDef.dataType` (with defensive fallback) | Resolve source node → output port → use its dataType. Single source of truth (port def). | ✓ |
| Pass dataType explicitly through React Flow's `Connection` callback | Require caller to supply dataType; more invasive. | |
| Leave hardcoded + add runtime validation catch | Does not fix SC#2. | |

**Selected option (auto):** Handle-based inference — the port definition is the single source of truth; regression test locks down the fix.

**Gray area C:** Per-edge type mismatch validation — where does it live?

| Option | Description | Selected |
|--------|-------------|----------|
| `pipelineValidation.ts::findPortTypeMismatches` before `findMissingOutput` | Pure frontend; visible on every graph mutation; consistent with existing cycle/unconnected checks. | ✓ |
| Backend-only in `PipelineBuilder.build` | User only sees mismatch on Apply; degraded UX. | |
| Both client + server | Duplicate logic; no benefit over client-first with server as secondary guard. | |

**Selected option (auto):** Client-side in `pipelineValidation.ts` — matches SC#2 literal ("`pipelineValidation.ts` reports per-edge type mismatches").

---

## Hot-Swap Apply Path (DET-PIPELINE-05, SC#4)

**Gray area:** How is "change backend param + apply = hot-swap without restart" implemented?

| Option | Description | Selected |
|--------|-------------|----------|
| Server-side diff in `/api/pipeline/apply` | Compare new PipelineConfig against `last_applied_pipeline_config`; if only perception params changed, call `pool.swap_backend` / `pool.swap_lifter` directly and skip restart callback. | ✓ |
| Client-side short-circuit (new `/api/pipeline/hot-apply` endpoint) | Frontend computes diff; picks endpoint. | |
| Both endpoints; client picks which | Duplicates diff logic. | |
| Always restart (accept SC#4 failure) | Does not satisfy SC#4. | |

**Selected option (auto):** Server-side diff — the diff rules live with PipelineConfig in Python (single source of truth); client reacts to two-valued response (`hot-applied` / `restarting`). Avoids duplicating topology-digest math in TypeScript.

**Follow-up:** Which changes qualify as hot-swap-eligible?

| Field | Hot-swap? | Reason |
|-------|-----------|--------|
| detector_name / detector_params | ✓ | Pool supports `swap_backend` (new, D-11). |
| lifter_name / lifter_params | ✓ | Pool already supports `swap_lifter` (Phase 4). |
| backend_name (SLAM) | ✗ | SLAM state + spawn positions invalidate on swap. |
| merger_name / merger_params | ✗ | Merger reconstructs map state. |
| filter_chain | ✗ | Filter pump not currently factored for live mutation. |
| tracker_name / tracker_params | ✗ | Phase 7 does not run tracker in pool (D-14); Phase 8 when live. |
| Topology (nodes/edges) | ✗ | Graph restructure = full rebuild. |

---

## Tracker Scope (SC#1 passthrough)

**Gray area:** How does the TrackerNode participate in Phase 7 if ByteTrack is Phase 8?

| Option | Description | Selected |
|--------|-------------|----------|
| Ship `TrackerRegistry` + `tracker_none` passthrough in Phase 7 | Creates `src/tracking/` package, registers a trivial `none` tracker (stamps monotonic `track_id`). TrackerNode drags + connects end-to-end. Pool-side tracker invocation deferred to Phase 8. | ✓ |
| Ship only the TrackerNode definition (no registry/backends) | `tracker_generic` catalog entry would be empty; `registryName` unresolved. SC#1 fails for the tracker portion. | |
| Defer TrackerNode entirely to Phase 8 | SC#1 literal says "DetectorNode, Detection3DNode, TrackerNode" — dropping one violates the criterion. | |

**Selected option (auto):** TrackerRegistry + `tracker_none` passthrough — minimum viable scaffolding to satisfy SC#1 + SC#3 preset end-to-end; ByteTrack registers as a drop-in Phase 8 without editor surface changes.

**Follow-up:** Does the coordinator pump invoke `tracker.track()` in Phase 7?

| Option | Description | Selected |
|--------|-------------|----------|
| Editor-surface only — no pool integration | `tracker_none` exists in graph/preset but coordinator does NOT call it. `track_id` remains None per box. | ✓ |
| Wire `NoneTracker.track()` into pool in Phase 7 | Increases Phase 7 scope; `track_id` stamping lands Phase 8 anyway with real semantics. | |

**Selected option (auto):** Editor-surface only — Phase 7 stays focused on pipeline editor work; runtime tracker integration is Phase 8's first plan.

---

## Built-in Preset (DET-PIPELINE-04)

**Gray area:** What is the topology of `perception_rgbd.json`?

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel SLAM + perception branches feeding shared viz | sensor_rgbd fans out to slam_icp AND detector_generic; both branches terminate at viz_output. Matches live v3.0 runtime (SLAM + detection simultaneously). | ✓ |
| Perception-only (no SLAM branch) | Minimal preset; matches SC#3 literal wording ("MuJoCoBridge → DetectorNode → Detection3DNode → visualization"). But loading it kills the map — breaks v3.0 core value. | |
| Two presets: `perception_only` + `perception_plus_slam` | Doubles built-in preset count for low marginal value. | |

**Selected option (auto):** Parallel branches — SC#3 wording is additive not exclusive; the preset must not drop SLAM when loaded. PROJECT.md's "real-time map + live detection" is non-negotiable.

---

## Claude's Discretion

Decisions where auto-mode defers to planner-level choices:
- Exact TypeScript type-narrowing on the expanded `PortDataType` union (maintain exhaustive color/shape maps).
- ApplyBar toast styling for `hot-applied` response (reuse existing palette).
- Hot-apply response auxiliary keys (`elapsed_ms`, `active_detector` echoes — additive, client reads `status` + `changed`).
- Diff implementation style (field-by-field vs `dataclasses.asdict` equality).
- Palette label wording ("Perception" vs "Perception Nodes" vs "Object Detection Nodes").
- New WS event type vs reused `detector_restart_complete` with discriminator (slight preference for new `detector_swap_complete` type).
- `NoneTracker` counter scope (per-frame reset vs session-monotonic).

## Deferred Ideas

- ByteTrack tracker implementation — Phase 8 DET-STRETCH-01.
- Per-robot heterogeneous detector dispatch from pipeline graph — Phase 8 DET-STRETCH-04.
- SLAM / merger / filter hot-swap — out of Phase 7 scope.
- `Any` / polymorphic port type — deferred; revisit when Splitter needs generic typing.
- NodeInspector vs DetectorParameterPanel unification — Phase 8+ polish.
- Frontend structured pipeline diff display — polish.
- Input-type (`RGB_TEXT_PROMPT`) dynamic port set — dropped alongside OWLv2 (Phase 5 D-10).
- `detection3d_generic.cloud_in: PointCloud` port — add when a future lifter needs external cloud input.
- Saving user pipelines containing perception nodes — existing save path is transparent to the changes.
- Tracker ParameterPanel — `tracker_none` has no params; ByteTrack introduces it in Phase 8.

---

*Mode: --auto (no interactive selection)*
*Auto-selections logged above with "Selected option (auto)" markers*
*This log is for audit only; downstream agents read CONTEXT.md.*
