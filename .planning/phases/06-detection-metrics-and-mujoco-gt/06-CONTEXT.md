# Phase 6: detection-metrics-and-mujoco-gt - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning
**Source:** Discuss-phase `--auto` (7 gray areas, 7 recommended defaults selected — no user input, see DISCUSSION-LOG.md)

<domain>
## Phase Boundary

Honest, MuJoCo-grounded detection metrics — populate the existing `MetricsPanel` with per-robot detection metrics (inference latency p50/p95, detections/frame, mean_confidence, queue depth, freshness, 3D center jitter), add a MuJoCo ground-truth extractor that reports `center_error_m` and `per_class_recall` against `mj_name2id + data.xpos`, stream a per-session JSONL detection export via `GET /api/detections/export`, and lock `mAP` out of the UI unless a committed labeled eval set is provided. Add a parametrized RSS smoke test that runs ≥100 inferences per backend and fails CI at RSS growth >200 MB.

**In:**
- `src/metrics/detection_metrics_tracker.py` (new) — `DetectionMetricsTracker` class parallel to `MetricsTracker`, per-robot ring buffers: `inference_ms_history`, `detections_per_frame_history`, `confidence_history`, `queue_depth_history`, `freshness_history`, `jitter_history`.
- `src/metrics/mujoco_gt.py` (new) — `MuJoCoGTExtractor` — resolves class-name → body-ids via mapping file, reads `data.xpos` per tick, matches detections to GT by nearest-neighbor in world frame, computes `center_error_m` + `per_class_recall`.
- `data/scenes/scene_office1_gt.yaml` (new) — explicit COCO-class-name → MuJoCo body-name mapping (scene-local; co-located with `scene_office1.xml`). Example entries: `chair: [body_BezierCurve_009_SwivlChair, body_Chocofur_free_12_plastic_cycles_013_BrownChair]`.
- `backend/web/streaming_viz.py` — EXTEND `_update_stats` payload (additive — new `detection_metrics` + `detection_history` keys alongside existing `slam_metrics` / `baseline` / `metric_history`). `WebStreamingViz` composes a `DetectionMetricsTracker` alongside the existing `MetricsTracker`.
- `backend/web/detector_routes.py` — NEW `GET /api/detections/export` streaming JSONL endpoint (FastAPI `StreamingResponse` that tails the session's append-only JSONL file).
- `src/metrics/detection_export.py` (new) — `DetectionExportWriter` — append-on-emit JSONL writer; one file per session at `/tmp/argus_sessions/<session_id>/detections.jsonl`. Writes one line per detection (full OBB wire payload + `capture_timestamp` + `robot_id` + `backend_id`).
- `frontend/src/stores/metricsStore.ts` — EXTEND state with `detectionPerRobot: Record<robotId, DetectionMetrics>` + `detectionHistory: Record<robotId, DetectionMetricHistory>` + corresponding setters. Single-set `updateAllMetrics()` grows to accept the new keys (one re-render per stats message preserved).
- `frontend/src/components/MetricsPanel.tsx` — EXTEND the "Live" tab with a detection subsection below the SLAM metrics rows. New rows: `infer p50/p95`, `det/frame`, `conf`, `queue`, `fresh`, `jitter`. Use existing robot-keyed column layout + palette.
- `frontend/src/utils/messageTypes.ts` — NEW `DetectionMetrics` + `DetectionMetricHistory` types mirroring `SlamMetrics` + `MetricHistory` shape.
- Coordinator wiring (`src/main.py` or the per-robot coordinator): after each `DetectorWorker.inspect()` + `DetectorWorker.latest()` tick, pump values into `DetectionMetricsTracker.record_frame(robot_id, latest, inspect)` and `DetectionExportWriter.append(detection)` for every newly-emitted detection.
- Tests:
  - `tests/metrics/test_detection_metrics_tracker.py` — unit tests for percentile math + ring-buffer bounds + empty-state defaults.
  - `tests/metrics/test_mujoco_gt.py` — fixture scene + known body xpos → asserts `mj_name2id` resolution + center_error_m math against a synthetic detection at a known offset.
  - `tests/integration/test_detections_export.py` — spawns coordinator for 30 frames, hits `GET /api/detections/export`, asserts each line round-trips through `OrientedBox3D.from_wire`.
  - `tests/integration/test_rss_smoke_backends.py` — parametrized `@pytest.mark.parametrize("backend", ["yolov11", "rtdetrv2", "boxer"])`; runs 100 inferences, asserts RSS growth ≤200 MB; BoxeR marked `slow` (inherits from Phase 5).
  - `tests/contract/test_no_map_in_ui.py` — grep-based invariant: string `mAP` (case-sensitive) MUST NOT appear in `frontend/src/**/*.{ts,tsx,css}` OR in JSON payloads emitted by `streaming_viz`. Locks SC#3.

**Out:**
- ByteTrack / `track_id` generation for stable per-object jitter tracking (Phase 8 — Phase 6 uses nearest-neighbor matching as a degradable proxy, see D-09).
- Labeled-eval-set ingestion + actual `mAP` computation (the `--labeled-eval-set` flag is reserved but does NOT ship in Phase 6 — only the UI block + grep test).
- Multi-scene GT mapping (Phase 6 ships one mapping file for `scene_office1.xml`; new scenes get their own sibling mapping file under the same naming convention — not Phase 6 scope to build infrastructure for N scenes).
- Baseline comparison for detection metrics (SLAM has `capture_baseline()`; detection metrics ship live-only — add vs-baseline view in a later polish phase if the user wants it).
- Sparkline rendering for detection history (out of Phase 6 — add later; Phase 6 just populates the `detection_history` arrays in the store so sparklines are drop-in).
- Coordinator-side computation of drift-like trajectory metrics for detections (not applicable — detections are per-frame, not per-trajectory).

</domain>

<decisions>
## Implementation Decisions

### Metrics Aggregation Layer (DET-METRICS-01)

- **D-01 (Parallel `DetectionMetricsTracker` class):** New class `src/metrics/detection_metrics_tracker.py::DetectionMetricsTracker` lives alongside `src/metrics/metrics_tracker.py::MetricsTracker`. Mirrors the existing `MetricsTracker` shape 1:1 — per-robot `dict[str, {<metric_name>: float, <metric_name>_history: deque[maxlen=history_size]}]`, `record_frame()` + `get_stats_payload()` + `reset()`. Does NOT extend `MetricsTracker` (no inheritance, no kwargs juggling — SLAM metrics and detection metrics have zero shared fields). `WebStreamingViz.__init__` gains a second instance: `self._detection_metrics_tracker = DetectionMetricsTracker(history_size=60)`. Rationale: separation of concerns matches the existing SLAM tracker pattern (Phase v2.0 13-01), avoids cross-subsystem coupling, and keeps the diff localized.

- **D-02 (Metrics computed per-robot per-frame):** `DetectionMetricsTracker.record_frame(robot_id, latest: Detections3D | None, inspect: dict, backend_metrics: dict)` is called once per coordinator tick per robot. Inputs:
  - `latest` — `DetectorWorker.latest()` return (for `detections_per_frame` = `len(latest.boxes)`, `mean_confidence` = mean of `latest.boxes[*].score`, `freshness` = `sim_now - latest.capture_timestamp`).
  - `inspect` — `DetectorWorker.inspect()` return (for `queue_depth`, `drops_since_session_start`).
  - `backend_metrics` — `DetectorProtocol.get_metrics()` return (for `inference_ms_p50`, `inference_ms_p95`, `first_inference_ms`). Already populated by all three Phase 5 backends; see `src/perception/backends/boxer_backend.py:259-272` for the reference implementation.
  
  `record_frame` writes current values into the robot's entry and appends to the ring buffers. `get_stats_payload()` returns `{"detection_metrics": {<rid>: {...latest values...}}, "detection_history": {<rid>: {<metric>: [list values]}}}`. Zero SLAM-metric overlap.

- **D-03 (3D jitter computation — nearest-neighbor tracking):** "Persistent object 3D center jitter" is computed as the stddev of the 3D center (x,y,z) of a single tracked object over the last 30 frames. Because `track_id` is NOT available until Phase 8 (ByteTrack), Phase 6 uses nearest-neighbor matching as a degradable proxy:
  1. `DetectionMetricsTracker` keeps a per-robot `_tracked_center: np.ndarray | None` seeded on first detection of each class.
  2. On each `record_frame`, for each detection, find the closest prior `_tracked_center` within a 0.5 m gate; if found, append the new center to the tracked history (bounded ring-buffer, maxlen=30), update `_tracked_center` to the matched center.
  3. Report `3d_center_jitter_m` = `np.std(np.linalg.norm(history - mean, axis=1))` per class; UI shows the aggregate `max` across classes per robot (one number per robot per frame — easy to render in the existing compact layout).
  4. When Phase 8 ships `track_id`, the matching step swaps out for a `track_id == self._tracked_track_id` lookup. The history structure + stddev math is unchanged — jitter is a stable API.
  
  This is explicitly a proxy, not a Kalman filter — the user's SC#1 literal is "stddev of a persistent object's 3D center over 30 frames", not "per-track jitter". Nearest-neighbor + 0.5 m gate satisfies the letter while being straightforward to replace.

### Frontend Panel Structure (DET-METRICS-01)

- **D-04 (Extend existing `MetricsPanel.tsx`):** Add a detection subsection to the existing `MetricsPanel` under the "Live" tab, below the SLAM metric rows. Do NOT create a new component. Layout: same robot-keyed column flex-row as SLAM; new label rows sit below "Status". The SLAM section keeps "ATE / RPE / ms/frame / Status"; the detection section adds "infer p50 / infer p95 / det/frame / conf / queue / fresh / jitter". A single `{detection_metrics}` header row separates them. No collapse granularity (one collapse toggles the whole panel as today). Rationale: preserves a single-source-of-truth dashboard matching the v2.0 Phase 13 pattern; a separate panel creates UX sprawl and doubles the collapse/view-mode state.

- **D-05 (Baseline tab unaffected):** Detection metrics ship live-only. The "vs Baseline" tab continues to show SLAM metrics only. Phase 6 does not build `detectionBaseline` plumbing. If the user later wants detection-vs-baseline, it's a drop-in extension using the same pattern as `MetricsTracker.capture_baseline()`. Deferred; no code hooks.

- **D-06 (No sparklines in Phase 6):** `detectionHistory` arrays populate the store identically to `slamHistory`, but the panel renders current values only (no `<Sparkline>` yet). Drop-in later: add `<Sparkline data={detectionHistory[rid]?.inference_ms ?? []} ...>` under any metric row. SC#1's "updating live" is satisfied by the numeric refresh at the SLAM metrics cadence.

- **D-07 (Robot ordering + palette):** Detection metrics rows use the same `robotId` key order and `robotColor(index)` as SLAM (palette.ts). Visual consistency: left border color matches SLAM column; no additional per-class palette (color coding comes from CameraFeed bbox overlays — Phase 3 D-16, not from this panel).

### MuJoCo GT Extractor + Name Matching (DET-METRICS-02, DET-METRICS-03)

- **D-08 (Explicit mapping file — NOT substring matching):** The `scene_office1.xml` bodies have auto-generated names (e.g., `body_Chocofur_free_12_plastic_cycles_013_BrownChair`, `body_BezierCurve_009_SwivlChair`) that do NOT cleanly contain a lowercase class substring. Substring matching would false-positive on `body_Cube_003_DefaultMaterial` and miss correct-but-unusual names. Ship `data/scenes/scene_office1_gt.yaml`:
  ```yaml
  # COCO class name -> list of MuJoCo body names that represent instances of that class
  chair:
    - body_BezierCurve_009_SwivlChair
    - body_Chocofur_free_12_plastic_cycles_013_BrownChair
  dining_table:
    - body_Plane_029_meetingTable
    - body_Cube_013_BigWhiteTable
  # ... (planner fills the rest at planning time by reading scene_office1.xml body list)
  ```
  `MuJoCoGTExtractor.__init__(scene_xml_path, mapping_yaml_path, mj_model, mj_data)` reads the YAML at startup, resolves each body name to `mj_name2id(mjtObj.mjOBJ_BODY, name)`, and stores `{class_name: [body_id_1, body_id_2, ...]}`. Missing bodies raise at construction (fail-fast, not silent-fallback) — a scene-mapping mismatch is a config bug, not a runtime issue.

- **D-09 (Matching policy: nearest-neighbor in world frame, class-gated):** For each detection with `class_name = C`, the extractor:
  1. Looks up `body_ids = mapping[C]`. If `C` not in mapping, detection is unmatched (no GT, contributes 0 to recall numerator, skips error calculation).
  2. For each body_id, reads `data.xpos[body_id]` → 3D world-frame position.
  3. Matches the detection's OBB center (`center[3]`) to the nearest body_id by Euclidean distance.
  4. If match is within 1.0 m gate → record `center_error_m = distance`. Else → unmatched (false-positive — does not count toward recall, contributes to a separate `false_positive_count` that the UI does not currently render but is available in the payload).
  5. Per-class recall = `matched_instances / expected_instances` per frame, where `expected_instances = len(mapping[C])`. Ring-buffered over 60 frames for stability.
  
  The 1.0 m gate is deliberately loose — it's a "correct-instance" gate, not a "good-accuracy" gate. The accuracy signal IS the reported `center_error_m`. Rationale: SC#2 requires `center_error_m` be reported for chairs; tight gates suppress the number we are trying to measure.

- **D-10 (`mAP`-forbidden UI enforcement — grep test):** SC#3 requires the literal string `mAP` NOT appear in the rendered UI. Enforcement: ship `tests/contract/test_no_map_in_ui.py` that:
  ```python
  import subprocess
  def test_no_map_in_frontend():
      out = subprocess.run(["git", "grep", "-n", "mAP", "frontend/src/"], capture_output=True)
      assert out.returncode == 1, f"mAP string found in frontend: {out.stdout.decode()}"
  ```
  Plus a runtime guard in `WebStreamingViz._update_stats`: payload serialization asserts no key named `mAP`, `map_50`, or `map_75` (defensive; not strictly needed if the tracker never emits it, but cheap and catches regressions). The `--labeled-eval-set` CLI flag is RESERVED in `src/main.py::parse_args` with a placeholder handler that raises `NotImplementedError("Labeled eval set ingestion arrives in a future milestone")` — documents the intended gate without shipping the feature.

### JSONL Export Streaming (DET-METRICS-04)

- **D-11 (Append-on-emit to on-disk session file):** `DetectionExportWriter.__init__(session_id: str)` opens `/tmp/argus_sessions/<session_id>/detections.jsonl` in append mode (`open(..., "a", buffering=1)` — line-buffered so SIGKILL preserves what's been written). Each call to `writer.append(detection: OrientedBox3D, robot_id: str, backend_id: str, capture_timestamp: float)` writes one JSON line:
  ```json
  {"robot_id": "robot_0", "backend_id": "yolov11", "capture_timestamp": 12.345,
   "obb": {"center": [...], "half_extents": [...], "quaternion": [...],
           "class_id": 56, "class_name": "chair", "score": 0.87, "track_id": null}}
  ```
  `obb` is produced by `OrientedBox3D.to_wire()` (Phase 1 D-10 invariant — no inline quaternion). Rationale: disk-backed export survives crashes, supports arbitrarily long sessions, and `GET /api/detections/export` streams by opening the same file read-only.

- **D-12 (Session lifecycle):** `session_id` is a UUID4 generated on coordinator boot (`src/main.py` at app start). `WebStreamingViz` owns the writer (`self._detection_export = DetectionExportWriter(session_id)`). On `reset_cloud_tracking()` (already exists — called on restart/scene-reload), a NEW session_id is generated and a new file is opened; prior session files are NOT deleted automatically (they're debug artifacts — tmp cleanup is the user's problem, not Argus's). Directory `/tmp/argus_sessions/` is gitignored via `.gitignore` update.

- **D-13 (Streaming endpoint):** `GET /api/detections/export` returns a `StreamingResponse` with `media_type="application/x-ndjson"`. Handler:
  ```python
  async def export_detections(request: Request):
      session = request.app.state.streaming_viz.current_session_id()
      path = f"/tmp/argus_sessions/{session}/detections.jsonl"
      async def generate():
          with open(path, "rb") as f:
              while True:
                  chunk = f.read(65536)
                  if not chunk:
                      break
                  yield chunk
      return StreamingResponse(generate(), media_type="application/x-ndjson",
                               headers={"Content-Disposition": f'attachment; filename="detections-{session}.jsonl"'})
  ```
  Snapshot-at-request-time semantics (not follow-live-writes — no `tail -f`). If the user wants a live stream, that's a WebSocket, not a REST endpoint. SC#4's "streams JSONL for the current session" is satisfied.

- **D-14 (Round-trip test):** `tests/integration/test_detections_export.py` spawns the coordinator with YOLOv11 for 30 frames against `scene_office1.xml`, hits the export endpoint, parses each line, constructs an `OrientedBox3D` via `from_wire(obb)`, compares each round-trip to the in-memory detections the tracker saw. Asserts lossless ±1e-6 (reusing Phase 2 SC#4's tolerance from `test_obb_wire_roundtrip.py`).

### Memory Smoke Test Harness (DET-METRICS-05)

- **D-15 (Parametrized pytest harness):** Single test file `tests/integration/test_rss_smoke_backends.py`:
  ```python
  @pytest.mark.parametrize("backend_id", ["yolov11", "rtdetrv2", pytest.param("boxer", marks=pytest.mark.slow_boxer)])
  def test_rss_growth_capped(backend_id, fixture_frame, psutil_rss):
      backend = DetectorRegistry.create(backend_id)
      backend.warmup(fixture_frame)
      rss_before = psutil_rss()
      for _ in range(100):
          backend.process_frame(fixture_frame)
      rss_after = psutil_rss()
      assert (rss_after - rss_before) < 200 * 1024 * 1024, (
          f"{backend_id} leaked: +{(rss_after - rss_before) // (1024*1024)} MB over 100 inferences"
      )
  ```
  Phase 1 already ships this pattern for YOLO; Phase 6 generalizes it. `slow_boxer` mark already defined (Phase 5 D-04 / pyproject markers). BoxeR test requires the subprocess venv — gated by `setup_boxer_subprocess.sh` having been run (honest skip if `.ready` missing rather than false-pass). RT-DETRv2 requires `models/rtdetrv2/<sha>/model.onnx` — honest skip with "run `make download-models-rtdetrv2`" hint if missing.

- **D-16 (CI inclusion — fast tier only):** Default CI runs `yolov11` + `rtdetrv2` (both in-process, fast). BoxeR test is gated behind `-m slow_boxer` (matching Phase 5 precedent — opt-in because subprocess + multi-minute warmup blows CI budget). Fast tier catches 90% of the regression surface; slow tier covers the rest on a scheduled nightly or pre-release.

### Integration Wiring (runs once per coordinator tick, per robot)

- **D-17 (Coordinator hook site):** Detection-metrics pump lives in `src/main.py` at the existing per-robot streaming hook (the same loop that calls `WebStreamingViz.update_robot_data(...)`). After each tick:
  ```python
  for rid, worker in worker_pool.items():
      latest = worker.latest()                    # Detections3D | None
      inspect = worker.inspect()                  # {queue_depth, drops, last_submit}
      backend_metrics = worker.detector.get_metrics()
      streaming_viz.detection_metrics_tracker.record_frame(rid, latest, inspect, backend_metrics)
      if latest is not None and latest.boxes:
          for obb in latest.boxes:
              streaming_viz.detection_export.append(
                  obb, robot_id=rid, backend_id=backend_metrics.get("backend_id", "unknown"),
                  capture_timestamp=latest.capture_timestamp,
              )
  ```
  Thin integration — tracker + writer are both owned by `WebStreamingViz`; the coordinator just pumps data in. Zero new threads, zero new locks (tracker ring buffers are called from the single streaming-tick thread).

### Claude's Discretion (planner picks, within the decisions above)

- Exact `history_size` value for detection ring buffers (60 matches SLAM; planner may bump to 120 if frontend wants 2× sparkline density later — cheap).
- Exact 3D jitter gate threshold (0.5 m chosen as "chair-scale"; planner may tune via `scene_office1_gt.yaml` per-class override if scenes with smaller objects appear).
- Exact center_error matching gate (1.0 m chosen; planner may split into `match_gate` + `accuracy_gate` if SC#2's 0.0X reporting needs tighter coupling to "is this the right chair").
- Exact `/tmp/argus_sessions/` path (OS-portable alternative: `tempfile.gettempdir()` — planner's call).
- Whether `DetectionMetricsTracker.reset()` also closes/rotates the export writer (probably yes; scope confirm at planning time).
- Frontend detection-subsection label styling (spacing, separator visual — matches existing MetricsPanel idioms, not prescriptively specified).
- Whether to add `slam_metrics` + `detection_metrics` to a single merged `/api/metrics/history` REST endpoint (deferred — not in SC list, not scope creep worth planning).
- Exact CSV/JSON schema for `scene_office1_gt.yaml` (YAML vs JSON — YAML more readable for mapping tables; planner finalizes).
- Whether the grep test in D-10 also covers backend JSON payloads (recommended yes; planner decides the cleanest enforcement shape).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 spec
- `.planning/REQUIREMENTS.md` — DET-METRICS-01, DET-METRICS-02, DET-METRICS-03, DET-METRICS-04, DET-METRICS-05
- `.planning/ROADMAP.md` §"Phase 6: detection-metrics-and-mujoco-gt" — 5 success criteria (L132-L137); research flag `light`

### Existing metrics stack (MUST extend, NOT replace)
- `src/metrics/metrics_tracker.py::MetricsTracker` — reference implementation for per-robot ring-buffer pattern; `DetectionMetricsTracker` mirrors its shape
- `backend/web/streaming_viz.py::WebStreamingViz._update_stats` (L367-L394) — current stats payload emitter; Phase 6 adds `detection_metrics` + `detection_history` keys additively
- `frontend/src/stores/metricsStore.ts` — Zustand store with `perRobot: Record<robotId, SlamMetrics>`; Phase 6 adds `detectionPerRobot` + `detectionHistory` in a single `updateAllMetrics` call to preserve the single-re-render invariant
- `frontend/src/components/MetricsPanel.tsx` — existing "Live" + "vs Baseline" tabbed panel; Phase 6 extends "Live" with a detection subsection (does NOT create a new component)
- `frontend/src/utils/messageTypes.ts::SlamMetrics` + `MetricHistory` — mirror these for `DetectionMetrics` + `DetectionMetricHistory`

### Per-robot worker contract (MUST consume, NOT modify)
- `src/perception/worker.py::DetectorWorker.latest()` — returns `Detections3D | None`; source for `detections_per_frame` + `mean_confidence` + `freshness`
- `src/perception/worker.py::DetectorWorker.inspect()` (L197-L212) — returns `{queue_depth, drops_since_session_start, last_submit_sim_time}`; source for `queue_depth` + drops
- `src/perception/protocol.py::DetectorProtocol.get_metrics()` (L80-L87) — returns `inference_ms_p50`, `inference_ms_p95`, `first_inference_ms`, `detections_per_frame`, `mean_confidence`; source for inference latency metrics
- `src/perception/types.py::Detections3D` — has `capture_timestamp` (Phase 2 D-11); `freshness = sim_now - capture_timestamp`
- `src/perception/types.py::OrientedBox3D.to_wire()` — sole quaternion serialization path (Phase 1 D-10); JSONL export calls this, NEVER handcrafts

### MuJoCo scene fixture
- `data/scenes/scene_office1.xml` — target scene; chair bodies at lines 1257/1263 (swivl + brown), meeting table at 1302, big white table at 1275
- `src/bridge/scene_builder.py` — existing MuJoCo model loader; `MuJoCoGTExtractor` reuses its `mjModel` handle rather than re-loading the XML
- `src/bridge/sim_bridge.py` — owns `mj_data.xpos`; extractor reads this via a sim-tick hook

### Phase 5 + prior phase invariants (MUST hold)
- `src/_thread_config.py` — Phase 1 D-04; no module-scope thread setup in new code
- `src/perception/registry.py::DetectorRegistry` — enumerate backends via `list()` in smoke test; `create()` constructs fresh instances per test
- `src/perception/backends/boxer_backend.py::get_metrics` (L259-L272) — reference implementation for `inference_ms_p50/p95` via `np.median` + `np.percentile` on a bounded deque; `DetectionMetricsTracker` aligns to the same percentile convention
- `tests/perception/fixtures/scene_rotated_chair.xml` — Phase 4 fixture with labeled chair body — template for `test_mujoco_gt.py` fixture (smaller + self-contained)
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-CONTEXT.md` §"Checkpoints + Offline + LICENSES" — `make download-models` is the pre-fetch gate; RSS smoke test skips honestly if models absent
- `.planning/phases/01-detector-api-foundation/01-CONTEXT.md` — original `get_metrics()` recommended keys (Phase 6 formalizes these — see protocol.py L83-L85)

### FastAPI streaming
- `backend/web/server.py` — FastAPI app factory; add `detector_routes.export_detections` route registration
- `backend/web/detector_routes.py` — existing detector REST endpoints; Phase 6 adds `GET /api/detections/export`
- FastAPI `StreamingResponse` docs: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse (verify current signature + `media_type="application/x-ndjson"` pattern at planning time)

### MuJoCo GT extraction (research, verify at planning time)
- `mujoco` Python bindings — `mj_name2id(model, mjtObj.mjOBJ_BODY, name)` → `body_id`; `data.xpos[body_id]` → `np.ndarray[3]` in world frame. `mujoco.mjtObj.mjOBJ_BODY` import path may have changed; verify via Context7 at planning time (Phase 6 research flag: `light`).
- Research ref: `.planning/research/` — check for any GT extractor notes if present (scene inventory at planning time per ROADMAP.md L139).

### Serialization pattern
- Phase 2 D-17 msgpack schema (subprocess bridge) — NOT reused here; JSONL export is human-readable, not msgpack. Kept separate on purpose.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (compose, don't rebuild)
- `src/metrics/metrics_tracker.py::MetricsTracker` — 1:1 structural template for `DetectionMetricsTracker`. Copy `_ensure_robot` + `record_frame` + `get_stats_payload` + `reset` pattern.
- `backend/web/streaming_viz.py::WebStreamingViz` — already owns `_metrics_tracker`; Phase 6 adds `_detection_metrics_tracker` and `_detection_export` as parallel fields. Zero architectural change.
- `frontend/src/stores/metricsStore.ts::updateAllMetrics` — single-set pattern preserves the one-re-render-per-stats-message invariant (Phase v2.0 13-01 finding). Extend kwargs, do not split into multiple setters.
- `frontend/src/components/MetricsPanel.tsx` — "Live" tab has the robot-keyed column layout. Extend by adding rows inside the existing `.map((robotId, index) => ...)` block.
- `src/perception/backends/boxer_backend.py::get_metrics` — reference for `inference_ms_p50/p95` via `np.median` / `np.percentile` on bounded deque; RTDETRv2 + YOLOv11 follow the same shape.
- `data/scenes/scene_office1.xml` — chairs at L1257 + L1263 provide concrete GT bodies; meeting table at L1302 provides a second class; mapping file is a short static list.
- `tests/perception/fixtures/scene_rotated_chair.xml` (Phase 4) — minimal scene with labeled chair; reuse for `test_mujoco_gt.py` unit test.

### Established patterns (follow these)
- **Ring buffer via `deque(maxlen=N)`** — Phase v2.0 13-01; used by `MetricsTracker._ensure_robot`. Matches `deque` in existing `BoxeRBackend._inference_times`. Use `deque(maxlen=60)` for detection ring buffers.
- **Single-re-render setter** — `updateAllMetrics` accepts all stats message fields in one `set()` call; Phase 6 adds detection fields to the same signature.
- **Percentile convention** — `np.median` + `np.percentile(arr, 95)`; matches BoxeR + RT-DETRv2.
- **`reset_cloud_tracking` lifecycle hook** — session rotation fires here; JSONL export lifecycle piggybacks on this existing signal.
- **Grep-based invariants** — Phase 4 SC#3 established the pattern (`grep codebase for 70` returns no hits); Phase 6 mirrors it for `mAP`.
- **Honest skip** — Phase 5 pattern: integration tests skip with a clear "run `make download-models`" message when artifacts absent. RSS smoke test follows.

### Integration points
- `src/main.py` coordinator tick — insert detection-metrics pump after existing SLAM metrics pump; one call per robot per tick.
- `backend/web/server.py` — register `GET /api/detections/export` on app startup alongside existing detector routes.
- `pyproject.toml [project.optional-dependencies].perception` — already has `psutil` (used by Phase 1 RSS smoke test); no new runtime deps. YAML parsing via `PyYAML` — verify presence; if absent, add to `perception` extra (trivial dep, stdlib-adjacent; a single `import yaml` in `mujoco_gt.py`).
- `.gitignore` — add `/tmp/argus_sessions/` is pointless (tmp is already ignored), but add `data/scenes/*_gt.yaml` is WRONG — mapping files are source, MUST be committed. Just add `sessions/` if we fall back to a repo-local session dir on a non-Linux host. Planner confirms OS portability.

### Caveats (easy-to-miss)
- `scene_office1.xml` body names are NOT a substring match for COCO class names. The mapping file is the only honest way to wire them up. Do not skip D-08 and add a substring fallback — it will false-positive.
- `Detections3D.capture_timestamp` is sim-time (seconds), not wall-clock. `freshness = sim_now - capture_timestamp` must use `sim_now` from `sim_bridge`, NOT `time.time()`. Phase 2 D-13 invariant.
- `DetectorWorker.inspect().drops_since_session_start` is session-lifetime (never reset by `worker.reset()`). The detection-metrics tracker should surface the delta if a rate is desired, or just show the absolute count (simpler; matches SLAM's monotonic counter pattern).
- Grep test in D-10 must exclude `.planning/` paths (we reference `mAP` in requirements/roadmap — that's documentation, not UI). Use `frontend/src/` scope.
- `track_id` is `Optional[int]` on `OrientedBox3D` today; Phase 6 emits `null` until Phase 8 ships ByteTrack. Do NOT gate JSONL export on `track_id != null`.
- BoxeR RSS smoke test involves subprocess boot — it's slow (setup + warmup dominates over 100 inferences). Mark as `slow_boxer` + honest-skip if `subprocess_venvs/boxer/.ready` missing.

</code_context>

<specifics>
## Specific Ideas

- "Every metric the panel shows must be truthful" — Phase 6's entire premise. `mAP` is forbidden because we don't have a labeled eval set; `center_error_m` against MuJoCo GT is honest; `3d_center_jitter_m` as nearest-neighbor proxy is honest with the proxy explicitly documented (D-09). Do not add any metric that requires a label file Argus doesn't have.
- `make download-models` precedent (Phase 5 D-13) continues — RSS smoke test honestly skips if models absent with the exact command hint. Do not auto-download at test time.
- Single dashboard surface preserved — detection metrics live inside the existing `MetricsPanel`, not a new sibling panel. One collapse toggle, one tab bar, one palette. Philosophy: panels are facts, not feature silos.
- JSONL export is a debug/audit artifact, not a product surface — `/tmp/argus_sessions/` placement signals this. Don't grow it into a session-playback API.
- Nearest-neighbor jitter is a proxy, explicitly labeled as such (D-03, D-09). When Phase 8 ships `track_id`, swap the matching step and keep the math — jitter is a stable API.
- Mapping file format is YAML because the user reads it to debug; JSON would work but loses readability. Stays scene-local (`<scene>_gt.yaml`) for scoping.
- The 1.0 m center_error gate is a "correct-instance" gate, not an "accuracy" gate — the actual accuracy number is what we REPORT. Tight gates suppress the signal we are trying to measure.

</specifics>

<deferred>
## Deferred Ideas

- **Detection metrics vs-baseline tab** — SLAM has `capture_baseline()`; detection metrics could too. Out of Phase 6 scope; revisit as a polish phase after user sees live metrics in anger.
- **Sparkline rendering for detection history** — store populates the arrays in Phase 6; UI renders them later. Drop-in pattern.
- **`--labeled-eval-set` implementation** — flag is RESERVED with `NotImplementedError`; actual labeled-set ingestion + true mAP computation is a future milestone (requires committing an annotation format + labels for `scene_office1.xml`, which is real work).
- **ByteTrack per-object jitter tracking** — Phase 8 (DET-STRETCH-01). Phase 6 uses nearest-neighbor proxy; the jitter math is stable API.
- **Multi-scene GT mapping infrastructure** — Phase 6 ships one scene's mapping file; N-scene scaffolding is premature.
- **Live-tail `/api/detections/export?follow=true`** — SSE or WebSocket for real-time tail; Phase 6 snapshots at request time only. Revisit if export becomes a first-class monitoring surface.
- **Structured session-replay API** — the JSONL export could feed a "replay this session" frontend feature. Not Phase 6 scope; that's a product feature, not a metrics feature.
- **Per-class jitter breakdown in UI** — store has per-class data if we build it; panel shows aggregate-max per robot. Expand later if a user asks "which class is jittering?".
- **Runtime mAP assertion in every payload** — D-10 ships a grep test + a payload-time assertion; the payload-time one is belt-and-suspenders. Keep minimal; don't build a payload validator.
- **Export format alternatives (Parquet, Arrow)** — JSONL chosen for human-readability + tail-friendly streaming. Only revisit if session sizes blow past GBs.
- **OS-portable session directory (Windows)** — `/tmp/argus_sessions/` is Linux-only; `tempfile.gettempdir()` is cross-platform. Planner may upgrade; not a phase-level decision.
- **Jitter gate tuning per scene** — 0.5 m works for chair-scale objects in `scene_office1.xml`; smaller objects in future scenes may need per-class overrides. Deferred until a scene needs it.
- **First-inference_ms surfaced in the panel** — backends expose `first_inference_ms` via `get_metrics`; currently not rendered. Revisit if warmup UX debugging becomes a topic.

</deferred>

---

*Phase: 06-detection-metrics-and-mujoco-gt*
*Context gathered: 2026-04-15 (auto-mode — 7/7 recommended defaults selected without user prompt; see 06-DISCUSSION-LOG.md for the audit trail)*
*Discussion log: 06-DISCUSSION-LOG.md*
