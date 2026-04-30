# Phase 6: detection-metrics-and-mujoco-gt - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 06-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 6-detection-metrics-and-mujoco-gt
**Mode:** `--auto` (no interactive user prompts; Claude auto-selected recommended defaults for all gray areas)
**Areas discussed:** Metrics Aggregation Layer, Frontend Panel Structure, GT Name Matching, JSONL Export, 3D Jitter Identity, Memory Smoke Harness, mAP Enforcement

---

## Metrics Aggregation Layer (DET-METRICS-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel `DetectionMetricsTracker` class | Mirror `MetricsTracker` shape 1:1; new file; `WebStreamingViz` composes both trackers | ✓ (recommended) |
| Extend `MetricsTracker` | Add detection fields to existing tracker | |
| Inline in `streaming_viz` | No tracker class — ring buffers live directly on `WebStreamingViz` | |

**User's choice:** [auto] Parallel `DetectionMetricsTracker` class — recommended default
**Notes:** Preserves Phase v2.0 13-01 pattern; separation of concerns; keeps diff localized to a new file; no cross-subsystem field juggling.

---

## Frontend Panel Structure (DET-METRICS-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing `MetricsPanel.tsx` | Add detection subsection inside the "Live" tab below SLAM rows | ✓ (recommended) |
| New `DetectionMetricsPanel.tsx` sibling | Separate component mounted alongside `MetricsPanel` | |
| New tab in `MetricsPanel` ("Detections" alongside "Live" / "vs Baseline") | Third tab | |

**User's choice:** [auto] Extend existing `MetricsPanel.tsx` — recommended default
**Notes:** Single dashboard surface; one collapse toggle; one palette; avoids UX sprawl. Detection rows sit below `Status` row per robot column.

---

## MuJoCo GT Name Matching (DET-METRICS-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit mapping file (`scene_<name>_gt.yaml`) | COCO class name → list of MuJoCo body names; scene-local | ✓ (recommended) |
| Substring match (`class_name.lower() in body_name.lower()`) | Runtime heuristic | |
| MuJoCo custom body attributes / tags | Edit scene XML to embed class tags on each body | |

**User's choice:** [auto] Explicit mapping file — recommended default
**Notes:** `scene_office1.xml` body names (`body_Chocofur_free_12_plastic_cycles_013_BrownChair`) do NOT cleanly substring-match COCO classes. Substring matching would false-positive on `body_Cube_003_DefaultMaterial` and miss unusual correct names. Editing the scene XML is out of scope (scene is generated). Explicit mapping file is auditable, local, and honest.

---

## JSONL Export Streaming (DET-METRICS-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Append-on-emit to on-disk session file; `StreamingResponse` reads it | `/tmp/argus_sessions/<uuid>/detections.jsonl`, line-buffered | ✓ (recommended) |
| In-memory ring buffer (bounded) | Bounded deque in `WebStreamingViz`, serialized on export | |
| Unbounded in-memory list | No bound; drained on export, session-scoped | |

**User's choice:** [auto] Append-on-emit to disk — recommended default
**Notes:** Disk-backed survives crashes; supports arbitrarily long sessions; streams from file with `StreamingResponse`; `media_type="application/x-ndjson"`. Snapshot-at-request-time (not live tail).

---

## 3D Center Jitter Identity Tracking (DET-METRICS-01, SC#1)

| Option | Description | Selected |
|--------|-------------|----------|
| Nearest-neighbor match gate (0.5 m) | Degradable proxy until Phase 8 ships `track_id` | ✓ (recommended) |
| Match by class-name only (assume one instance per class) | Simplest; breaks with multi-chair scenes | |
| Require `track_id`; don't ship jitter until Phase 8 | Strictly honest; leaves the SC#1 metric empty for now | |

**User's choice:** [auto] Nearest-neighbor match gate — recommended default
**Notes:** SC#1's literal requires "stddev of a persistent object's 3D center over 30 frames"; Phase 6 ships an honest proxy with the limitation documented. When Phase 8 ships ByteTrack, the matching step swaps for a `track_id` lookup; the jitter math + ring-buffer + API are unchanged.

---

## Memory Smoke Test Harness (DET-METRICS-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Single parametrized pytest test | `@pytest.mark.parametrize("backend_id", [...])`; one file | ✓ (recommended) |
| Per-backend test files | `test_rss_smoke_yolov11.py`, `test_rss_smoke_rtdetrv2.py`, `test_rss_smoke_boxer.py` | |
| Standalone script outside pytest | `scripts/rss_smoke.py`; not in CI gate | |

**User's choice:** [auto] Single parametrized pytest — recommended default
**Notes:** DRY; Phase 1 ships YOLO RSS pattern — Phase 6 generalizes via parametrize; BoxeR marked `slow_boxer` (Phase 5 precedent); RT-DETRv2 + BoxeR honest-skip if model artifacts absent.

---

## `mAP`-Forbidden UI Enforcement (DET-METRICS-03, SC#3)

| Option | Description | Selected |
|--------|-------------|----------|
| Grep CI test asserts `mAP` absent in `frontend/src/` | Structural invariant; mirrors Phase 4 SC#3 grep pattern | ✓ (recommended) |
| Runtime assert in `streaming_viz` rejects `mAP` key | Payload validation; runs per tick | |
| CLI flag gate only (`--labeled-eval-set`) | No enforcement beyond "if flag absent, don't emit mAP" | |

**User's choice:** [auto] Grep CI test (plus belt-and-suspenders payload-key assert in `_update_stats`)
**Notes:** Phase 4 SC#3 established grep-based structural invariants; cheap, permanent, no runtime cost. Payload-key assert is defensive (not strictly needed if tracker never emits `mAP`). `--labeled-eval-set` CLI flag is RESERVED in `parse_args` with `NotImplementedError` handler — documents intent without shipping the feature.

---

## Claude's Discretion

Captured in 06-CONTEXT.md `<decisions>` section under "Claude's Discretion". Planner-level picks: exact ring-buffer sizes, jitter gate threshold, center_error match gate, `/tmp` path portability, reset lifecycle for export writer, subsection styling, possible merged history endpoint, YAML vs JSON mapping format, grep scope in D-10.

## Deferred Ideas

Captured in 06-CONTEXT.md `<deferred>` section. Highlights: vs-baseline tab for detection metrics, sparklines, `--labeled-eval-set` real implementation, ByteTrack jitter (Phase 8), multi-scene GT scaffolding, SSE/WebSocket export tail, session-replay API, per-class jitter breakdown, Parquet/Arrow export format, Windows session dir portability.

---

*Generated: 2026-04-15 by `/gsd-discuss-phase 6 --auto`*
