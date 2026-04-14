# Roadmap: v3.0 Pluggable Perception & 3D Object Detection

## Overview

v3.0 repeats the v2.0 pattern on a new domain: decouple object detection from Ultralytics YOLO behind a generic `DetectorProtocol + DetectorRegistry` abstraction, add transformer-based backends (RT-DETRv2, OWLv2, facebook/BoxeR), and replace the depth-median 2D→3D projection with real oriented 3D bounding boxes via PCA on depth-frustum point clusters. The journey goes: (1) lock the Protocol/Registry contracts with YOLO refactored behind them, (2) stand up per-robot workers + REST/WS plumbing + canonical OBB wire format, (3) ship the frontend picker + parameter panel + RGB overlay, (4) replace median-depth geometry with true oriented boxes, (5) plug in three new backends (BoxeR in subprocess, RT-DETRv2 + OWLv2 in-process) as the pluggability regression test, (6) wire honest MuJoCo-grounded detection metrics, (7) expose perception nodes in the React Flow pipeline editor, and (8) if time allows, ship a ByteTrack tracker + multi-robot fusion + semantic map stretch phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: detector-api-foundation** - Protocol + Registry + YOLO-behind-Protocol + thread config + eval-mode contract (completed 2026-04-13)
- [x] **Phase 2: per-robot-worker-and-wire-plumbing** - Per-robot DetectorWorker, REST/WS plumbing, canonical OBB wire format + round-trip test (completed 2026-04-14)
- [ ] **Phase 3: frontend-picker-and-ui** - Detector dropdown, lifter dropdown, param panel, restart overlay, RGB bbox overlay
- [ ] **Phase 4: real-3d-obb-pipeline** - PointClusterLifter (PCA-OBB), single geometry path, dumb-renderer frontend
- [ ] **Phase 5: second-backends-boxer-rtdetr-owlv2** - BoxeR subprocess, RT-DETRv2 in-process ONNX, OWLv2 open-vocab, pinned checkpoints
- [ ] **Phase 6: detection-metrics-and-mujoco-gt** - MetricsPanel populated, MuJoCo GT extractor, center_error_m, JSONL export, RSS smoke test
- [ ] **Phase 7: pipeline-editor-perception-nodes** - DetectorNode, Detection3DNode, TrackerNode, per-edge type validation, perception_rgbd preset
- [ ] **Phase 8: stretch-tracker-fusion-semantic-map** - ByteTrack, multi-robot fusion, SemanticMap TTL layer, heterogeneous per-robot backends (time-gated)

## Phase Details

### Phase 1: detector-api-foundation
**Goal**: Establish `DetectorProtocol` / `Detection3DProtocol` / registries with YOLO refactored behind the new interface and process-global thread/inference-mode discipline baked into the contract.
**Depends on**: Nothing (first phase)
**Requirements**: DET-API-01, DET-API-02, DET-API-03, DET-API-06, DET-API-07, DET-MODELS-01
**Success Criteria** (what must be TRUE):
  1. `DetectorRegistry.list()` returns at least YOLOv11 and reports `available: true` with capability badges (framework, license, CPU latency hint) for it; missing-dep backends show `available: false` + install hint.
  2. Running the coordinator with the existing MuJoCo scene produces the same detection count and bbox coordinates on a fixture frame as the pre-refactor YOLO path (zero behavioral regression).
  3. A smoke test runs 100 YOLO inferences and final RSS is within +200 MB of initial RSS (proves `model.eval()` + `torch.inference_mode()` are enforced by the contract).
  4. No file outside `src/_thread_config.py` calls `torch.set_num_threads()` at module scope, and `main.py` imports `_thread_config` before any `torch` import.
  5. `Detection3DRegistry` exposes the placeholder `MedianDepthLifter` with `outputs_oriented=False` and an `outputs_3d_natively` capability flag is queryable on every detector.
**Plans**: 5 plans
- [x] 01-01-PLAN.md — Thread config + main.py wiring + detector.py:25 removal + grep invariant test
- [x] 01-02-PLAN.md — src/perception/types.py + protocol.py (DetectorProtocol, Detection3DProtocol, TorchBackendMixin)
- [x] 01-03-PLAN.md — src/perception/registry.py (DetectorRegistry + Detection3DRegistry + decorators + D-05/D-06 enforcement)
- [x] 01-04-PLAN.md — MedianDepthLifter + lifters package + ObjectDetector._detect rewire (closes Pitfall P3)
- [x] 01-05-PLAN.md — YOLOv11Backend + backends package + main.py side-effect imports + D-12 regression test + RSS smoke test
**Research flag**: standard

### Phase 2: per-robot-worker-and-wire-plumbing
**Goal**: Per-robot DetectorWorker pool with newest-wins backpressure, REST/WS detector selection with restart, and canonical OBB wire format locked before any new backend produces data.
**Depends on**: Phase 1
**Requirements**: DET-API-04, DET-API-05, DET-MODELS-05, DET-3D-03, DET-3D-04
**Success Criteria** (what must be TRUE):
  1. User hitting `POST /api/detectors/select` with a valid backend id triggers a coordinator restart and `GET /api/detectors/active` reflects the new selection after the restart completes.
  2. Every detection payload flowing over WebSocket carries `capture_pose` + `capture_timestamp` from submission time (verified by replaying a recorded WS session and confirming no detection uses current robot pose).
  3. Under sustained 30 Hz frame submission with a 2 FPS detector, each robot's worker queue depth stays at 1 (newest-wins) — verified via `inspect_worker_queues()` and logged queue-drop counter.
  4. Round-trip test `obb == OrientedBox3D.from_wire(obb.to_wire())` passes to ±1e-6 for 1000 randomized boxes; no backend code path constructs quaternions inline — only `OrientedBox3D.to_wire()` is called.
  5. `SubprocessDetectorBridge` skeleton handshake test (spawn dummy worker, ZMQ PAIR echo, msgpack round-trip, 5 s watchdog fires on hang) passes without the actual BoxeR code present.
**Plans**: TBD
**Research flag**: standard

### Phase 3: frontend-picker-and-ui
**Goal**: Users can see and control detection from the browser — pick a backend, tune parameters, watch RGB bbox overlays — with warmup-complete required before the UI reports "ready".
**Depends on**: Phase 2
**Requirements**: DET-UI-01, DET-UI-02, DET-UI-03, DET-UI-04, DET-UI-05, DET-UI-06
**Success Criteria** (what must be TRUE):
  1. User opens the C2 page and sees a Detector dropdown populated from `GET /api/detectors` with capability badges (framework, license, CPU latency hint); selecting a new backend shows a restart overlay that dismisses only after `detector_restart_complete` AND `warmup()` finishes.
  2. When the active detector has `outputs_3d_natively: true`, the Lifter dropdown is hidden; otherwise it lists `MedianDepthLifter` and (once Phase 4 ships) `PointClusterLifter`.
  3. Dragging a parameter slider in the detector panel sends a debounced `detector_param_update` WS message and the new value is visible in the next detection payload's metrics (e.g., confidence threshold cutoff).
  4. Camera feed panel renders a live 2D bbox overlay (class + confidence) per robot, synced to the same frame as the RGB image.
  5. `detectorStore` (Zustand) structure matches `slamStore` — flat state + setters + REST-fetched backend list + restart polling — verified by snapshot test diffing slice shape.
**Plans**: TBD
**Research flag**: standard
**UI hint**: yes

### Phase 4: real-3d-obb-pipeline
**Goal**: Replace depth-median 2D→3D projection with real oriented 3D bounding boxes via PCA on depth-frustum point clusters, with a single server-owned geometry path and a dumb-renderer frontend.
**Depends on**: Phase 2 (wire format), Phase 3 (frontend OBB consumer)
**Requirements**: DET-3D-01, DET-3D-02, DET-3D-05, DET-3D-06, DET-3D-07
**Success Criteria** (what must be TRUE):
  1. Running YOLOv11 + `PointClusterLifter` on a scene with a rotated chair produces an OBB whose yaw matches ground-truth within ±15° and whose center error is <0.15 m against MuJoCo body position.
  2. `DetectionBoxes.ts` client-side focal-length back-projection code is deleted; boxes render from wire format via `InstancedMesh` with `wireOBBToMesh()` as the only quaternion-conversion call site.
  3. Grepping the codebase for `70` (the hardcoded FOV) and `CLOUD_CONFIGS` returns no hits in perception modules; `src/perception/geometry.py::unproject_pixel_to_world` is the single projection entrypoint.
  4. When a detection's bbox has <50 valid depth pixels, the lifter silently falls back to `MedianDepthLifter` and the resulting OBB has identity quaternion + `outputs_oriented=False` in the wire payload.
  5. Switching lifter from `MedianDepthLifter` → `PointClusterLifter` via the Lifter dropdown changes the rendered box orientation visibly on a rotated object, with no server restart required.
**Plans**: TBD
**Research flag**: standard
**UI hint**: yes

### Phase 5: second-backends-boxer-rtdetr-owlv2
**Goal**: Plug in three new backends as the pluggability regression test — BoxeR in subprocess (3D-native OBBs), RT-DETRv2-S in-process ONNX (real-time transformer), OWLv2 for open-vocab — with pinned checkpoints, warmup, and crash-fallback to YOLO.
**Depends on**: Phase 4
**Requirements**: DET-MODELS-02, DET-MODELS-03, DET-MODELS-04, DET-MODELS-06, DET-MODELS-07, DET-MODELS-08
**Success Criteria** (what must be TRUE):
  1. User selects `RTDETRv2` from the dropdown, sees the restart overlay for ≤30 s (first inference warmup), then sees OBBs rendered at ≥3 FPS on the default MuJoCo scene.
  2. User selects `BoxeR` from the dropdown, the subprocess venv boots via `setup_boxer_subprocess.sh`, warmup completes, and 3D-native OBBs appear in Three.js (bypassing the lifter) within the BoxeR worker's first few frames.
  3. Killing the BoxeR subprocess manually (`kill -9 <pid>`) triggers a `crash_fallback` WS message within 5 s, the active detector auto-switches to YOLOv11, and a `CrashToast` appears in the frontend.
  4. `make download-models` pre-fetches every checkpoint to `./models/` and each backend loads with `revision=<sha>` pinned; running with network disabled after pre-fetch still boots all backends.
  5. OWLv2 accepts a text prompt via parameter panel, returns bboxes for the prompted class in 1–4 s/frame, and is visibly marked "on-demand, not real-time" in the capability badge.
  6. `LICENSES.md` contains the BoxeR CC-BY-NC-4.0 entry with upstream attribution link.
**Plans**: TBD
**Research flag**: needed (verify `facebook/boxer` repo structure, current checkpoint names, and Python 3.12 compatibility via Context7 at phase-planning time — do not trust April 2026 memory for 2022 CVPR code)

### Phase 6: detection-metrics-and-mujoco-gt
**Goal**: Honest, MuJoCo-grounded detection metrics — per-robot inference latency, 3D jitter, detection freshness, center_error against GT body positions, per-class recall, and session export. Forbid `mAP` without a committed labeled set.
**Depends on**: Phase 5 (stable multi-backend pipeline to measure)
**Requirements**: DET-METRICS-01, DET-METRICS-02, DET-METRICS-03, DET-METRICS-04, DET-METRICS-05
**Success Criteria** (what must be TRUE):
  1. MetricsPanel displays per-robot `inference_ms p50/p95`, `detections/frame`, `mean_confidence`, queue depth, freshness (`sim_now - capture_timestamp`), and `3d_center_jitter_m` (stddev of a persistent object's 3D center over 30 frames), all updating live.
  2. With a MuJoCo scene containing labeled body `chair_01`, the GT extractor resolves its `xpos` via `mj_name2id`, the coordinator matches detections whose `class_name` contains `chair`, and the panel shows `center_error_m` = 0.0X and `per_class_recall` for `chair`.
  3. The string `mAP` does not appear anywhere in the rendered UI; attempting to enable it requires a `--labeled-eval-set` flag pointing at a committed annotation file.
  4. `GET /api/detections/export` streams JSONL for the current session containing full OBB + class + confidence + capture_timestamp for every detection emitted, and the output parses losslessly round-trip through `OrientedBox3D.from_wire`.
  5. Running the memory smoke test against each backend (YOLOv11, RT-DETRv2, OWLv2, BoxeR) caps RSS growth at ≤200 MB over 100 inferences; regression causes CI failure.
**Plans**: TBD
**Research flag**: light (30-min MuJoCo scene XML class-labeled geom inventory at phase-planning time)

### Phase 7: pipeline-editor-perception-nodes
**Goal**: Expose detector, 3D lifter, and tracker stages as first-class React Flow nodes with typed ports, per-edge validation, a built-in preset, and runtime dispatch that swaps backends via node params without coordinator restart.
**Depends on**: Phase 6
**Requirements**: DET-PIPELINE-01, DET-PIPELINE-02, DET-PIPELINE-03, DET-PIPELINE-04, DET-PIPELINE-05
**Success Criteria** (what must be TRUE):
  1. User opens the pipeline editor, sees a `perception` category in the node palette with `DetectorNode`, `Detection3DNode`, `TrackerNode`, drags one onto the canvas, and connects typed `Detections2D` → `Detections3D` ports (with distinct colors) without a validation error.
  2. Connecting a `PointCloud` output to a `Detections2D` input shows a per-edge type-mismatch error in `pipelineValidation.ts` (the hardcoded-edge-type bug at `pipelineStore.ts:101` is fixed and a regression test locks it down).
  3. Loading the `perception_rgbd` built-in preset wires MuJoCoBridge → DetectorNode(YOLOv11) → Detection3DNode(PointCluster) → visualization and, on Apply, produces live OBBs in the 3D viewer end-to-end.
  4. Changing the `backend` param on a `DetectorNode` from `yolov11` to `rtdetrv2` and applying the pipeline swaps the per-robot `DetectorWorker` backend without a full coordinator restart (verified by watching PID stability in logs).
  5. `pipeline_routes.py` maps `detector_generic` node definitions to `DetectorWorkerPool` entries so node params flow through to worker construction kwargs.
**Plans**: TBD
**Research flag**: standard
**UI hint**: yes

### Phase 8: stretch-tracker-fusion-semantic-map
**Goal**: Time-gated differentiators — ByteTrack per-detection `track_id`, world-frame multi-robot detection fusion, SemanticMap with TTL rendered as a ghosted Three.js layer, and heterogeneous per-robot backends.
**Depends on**: Phase 7
**Requirements**: DET-STRETCH-01, DET-STRETCH-02, DET-STRETCH-03, DET-STRETCH-04
**Success Criteria** (what must be TRUE):
  1. Running a session with ByteTrack enabled produces stable `track_id` values across frames for the same physical object — verified by a persistent chair keeping a single `track_id` across ≥100 consecutive frames.
  2. Two robots detecting the same chair within a 0.5 m cluster radius in world frame produce a single fused detection with a shared `track_id` in the merged metrics view, not two separate entries.
  3. SemanticMap renders as a ghosted Three.js layer alongside the 3D reconstruction map; objects disappear from the layer after their per-object TTL expires (user observes a fade-out within TTL seconds of leaving FOV).
  4. Per-robot detector selection works end-to-end — user sets Robot 0 to `yolov11` and Robot 1 to `rtdetrv2` via UI, both robots' detections appear in MetricsPanel under their own backend labels, and the coordinator boots the appropriate worker per robot without crashes.
**Plans**: TBD
**Research flag**: light (ByteTrack spatial association threshold + multi-robot fusion radius tuning for indoor office scenes)
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. detector-api-foundation | 5/5 | Complete   | 2026-04-13 |
| 2. per-robot-worker-and-wire-plumbing | 12/12 | Complete   | 2026-04-14 |
| 3. frontend-picker-and-ui | 0/TBD | Not started | - |
| 4. real-3d-obb-pipeline | 0/TBD | Not started | - |
| 5. second-backends-boxer-rtdetr-owlv2 | 0/TBD | Not started | - |
| 6. detection-metrics-and-mujoco-gt | 0/TBD | Not started | - |
| 7. pipeline-editor-perception-nodes | 0/TBD | Not started | - |
| 8. stretch-tracker-fusion-semantic-map | 0/TBD | Not started | - |
