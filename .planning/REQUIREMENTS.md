# Requirements: v3.0 Pluggable Perception & 3D Object Detection

**Defined:** 2026-04-13
**Core Value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time — with user-selectable SLAM algorithms, detection backends, and live metrics.

---

## v3.0 Requirements

Each requirement maps to exactly one roadmap phase (filled in by roadmapper).

### DET-API — Pluggable Detector Abstraction

- [ ] **DET-API-01**: System exposes `DetectorProtocol` runtime-checkable interface with `process_frame`, `reset`, `warmup`, `get_metrics`, `CAPABILITIES`, `PARAMETER_SCHEMA`
- [ ] **DET-API-02**: System exposes `DetectorRegistry` with `@detector_backend` decorator, lazy class-path loading, and availability reporting (`available: false` + install hint when deps missing)
- [ ] **DET-API-03**: System exposes separate `Detection3DProtocol` + `Detection3DRegistry` for 3D lifters (PCA-OBB, median-depth, etc.), with `outputs_3d_natively` capability flag so end-to-end backends bypass the lifter
- [ ] **DET-API-04**: Each robot runs its own `DetectorWorker` thread with a single-slot latest-frame queue (newest-wins backpressure); worker pool is keyed by robot_id
- [ ] **DET-API-05**: Every detection result carries `capture_pose` + `capture_timestamp` from the submission time so downstream consumers do not re-associate stale poses
- [ ] **DET-API-06**: Process-global thread-pool configuration (`torch`, `OMP`, `MKL`, `OPENBLAS`) is set in `src/_thread_config.py` before any torch import; no module-scope `torch.set_num_threads()` in individual files
- [ ] **DET-API-07**: Every backend `__init__` calls `model.eval()` and wraps inference in `torch.inference_mode()`; enforced by a smoke test that caps RSS growth at 200 MB after 100 inferences

### DET-MODELS — Detection Backends

- [ ] **DET-MODELS-01**: Existing Ultralytics YOLOv11-nano detector is refactored behind `DetectorProtocol` as `YOLOv11Backend` with zero behavioral regression (verified by fixture-frame regression test)
- [ ] **DET-MODELS-02**: RT-DETRv2-S backend (`PekingU/rtdetr_v2_r18vd`) ships as an in-process ONNX-accelerated real-time transformer detector, ≤250 ms/frame at 320px on CPU
- [ ] **DET-MODELS-03**: facebook/BoxeR ships as a subprocess-isolated backend via `SubprocessDetectorBridge` (ZMQ PAIR + msgpack, 5 s watchdog, crash fallback); installs into its own worker venv and emits 3D OBBs natively
- [ ] **DET-MODELS-04**: OWLv2 open-vocabulary backend (`google/owlv2-base-patch16-ensemble`) ships for zero-shot text-prompted detection; marked as on-demand (not a real-time backend)
- [ ] **DET-MODELS-05**: User can select detector backend pre-session via REST (`POST /api/detectors/select`) which triggers restart — hot-swap mid-session is explicitly out of scope
- [ ] **DET-MODELS-06**: Backend crash in BoxeR subprocess emits `crash_fallback` WS message, falls back to YOLOv11, and shows a `CrashToast` in the frontend
- [ ] **DET-MODELS-07**: Every checkpoint is pinned by `revision=` SHA; `make download-models` script pre-fetches all weights to `./models/` for offline / CI
- [ ] **DET-MODELS-08**: LICENSES.md documents BoxeR CC-BY-NC-4.0 restriction

### DET-3D — Real Oriented 3D Bounding Boxes

- [ ] **DET-3D-01**: `PointClusterLifter` is the default 3D lifter — MAD-filtered depth frustum + DBSCAN cluster rejection + Open3D `compute_oriented_bounding_box(robust=True)`, yaw-only for indoor MVP, gravity-aligned
- [ ] **DET-3D-02**: `MedianDepthLifter` is kept as a named legacy lifter with `outputs_oriented=False` (wraps existing `detection_3d.py` behavior) — for compatibility, not default
- [ ] **DET-3D-03**: Server emits canonical OBB wire format: `(center[3], half_extents[3], quaternion[4] in xyzw with qw>=0, class_id, class_name, score, track_id)` via `OrientedBox3D.to_wire()`; inline quaternion construction in backends is forbidden
- [ ] **DET-3D-04**: Round-trip test enforces `obb == OrientedBox3D.from_wire(obb.to_wire())` to ±1e-6 across all backends and lifters
- [ ] **DET-3D-05**: Frontend `DetectionBoxManager` / `OBBManager` renders OBBs verbatim from wire format via `InstancedMesh`; client-side focal-length / FoV back-projection is deleted
- [ ] **DET-3D-06**: Single projection path lives in `src/perception/geometry.py` — removes the hardcoded 70° FOV + duplicate projection paths that previously existed in `detector.py` and `detection_3d.py`
- [ ] **DET-3D-07**: Lifter falls back to `MedianDepthLifter` when the depth frustum has fewer than 50 valid pixels, preserving behavior for degenerate cases

### DET-UI — Frontend Controls

- [ ] **DET-UI-01**: Frontend exposes a Detector dropdown with capability badges (framework, license, CPU latency hint), mirroring the v2.0 SLAM picker
- [ ] **DET-UI-02**: Frontend exposes a Lifter dropdown; hidden when the active detector has `outputs_3d_natively: true`
- [ ] **DET-UI-03**: Parameter panel renders detector `PARAMETER_SCHEMA` as sliders/toggles with debounced `detector_param_update` WebSocket sends, mirroring SLAM param panel
- [ ] **DET-UI-04**: Backend switch shows restart overlay until `detector_restart_complete` is received; UI does not report "ready" until `warmup()` completes
- [ ] **DET-UI-05**: Camera feed panel renders 2D bbox overlay (class + confidence) per robot
- [ ] **DET-UI-06**: `detectorStore` (Zustand) mirrors `slamStore` structure (flat state + setters, REST-fetched backend list, restart polling)

### DET-METRICS — Honest Measurement

- [ ] **DET-METRICS-01**: MetricsPanel shows per-robot detection metrics: `inference_ms p50/p95`, `detections/frame`, `mean_confidence`, queue depth, freshness (`sim_now - capture_timestamp`), `3d_center_jitter_m` (stddev of a persistent object's 3D center over 30 frames)
- [ ] **DET-METRICS-02**: MuJoCo ground-truth extractor pulls body positions via `mj_name2id + data.xpos`; coordinator matches detected class_name to body name
- [ ] **DET-METRICS-03**: System reports `center_error_m` and `per_class_recall` against MuJoCo GT; `mAP` is explicitly forbidden in the UI unless a labeled eval set is committed alongside the scene
- [ ] **DET-METRICS-04**: Detection history export endpoint (`GET /api/detections/export`) streams per-session JSONL with full OBB + class + confidence + timestamps
- [ ] **DET-METRICS-05**: Memory smoke test caps RSS growth at 200 MB over 100 inferences per backend (catches forgotten `eval()` / `inference_mode()` regressions)

### DET-PIPELINE — React Flow Integration

- [ ] **DET-PIPELINE-01**: Pipeline editor exposes `DetectorNode`, `Detection3DNode`, `TrackerNode` node definitions under a new `perception` category
- [ ] **DET-PIPELINE-02**: Pipeline editor gains `Detections2D` and `Detections3D` port data types with distinct colors
- [ ] **DET-PIPELINE-03**: `pipelineValidation.ts` reports per-edge type mismatches (today's code has a hardcoded PointCloud edge type bug at `pipelineStore.ts:101` — fix as part of this requirement)
- [ ] **DET-PIPELINE-04**: A `perception_rgbd` built-in preset wires MuJoCoBridge → DetectorNode(YOLOv11) → Detection3DNode(PointCluster) → visualization
- [ ] **DET-PIPELINE-05**: `pipeline_routes.py` maps `detector_generic` nodes to `DetectorWorkerPool` so the pipeline can swap backends via node params without a full restart

### DET-STRETCH — Differentiators (Phase 8, time-gated)

- [ ] **DET-STRETCH-01**: ByteTrack multi-object tracker assigns stable `track_id` per detection (class + spatial IoU association, Apache-2.0)
- [ ] **DET-STRETCH-02**: World-frame multi-robot detection fusion merges same-class detections within a 0.5 m cluster radius across robots
- [ ] **DET-STRETCH-03**: `SemanticMap` with per-object TTL renders as a ghosted Three.js layer alongside the 3D map
- [ ] **DET-STRETCH-04**: Heterogeneous per-robot backends — each robot may run a different detector (architectural support is in Phase 1; UI + coordinator wiring land here)

---

## Future Requirements (v4.0+)

- Hot-swap detector mid-session (mirror of v2.0 SLAM precedent — pre-session selection is sufficient for v3.0)
- GPU-required SOTA 3D detectors (BEVFormer, WildDet3D, 3D-MOOD, CenterPoint, CubeRCNN) — requires NVIDIA GPU, not a CPU-sim deliverable
- Open-vocabulary detection at useful FPS (Grounding DINO full pipeline)
- Online active learning / model retraining in sim
- Semantic SLAM loop closure using detected objects as landmarks
- RF-DETR-Nano as a third real-time transformer option (blocked on torch pin conflicts)

---

## Out of Scope

- **Hot-swap detector mid-session** — v2.0 SLAM precedent: pre-session selection with restart is sufficient; complexity of mid-session swap not justified by UX benefit.
- **GPU-dependent detectors** — hard CPU-only constraint from MuJoCo platform.
- **Multiple heavy detectors running simultaneously on all robots** — CPU budget collapse; one active backend per session is the supported mode.
- **Client-side 3D geometry reconstruction from 2D bbox + focal length** — actively harmful; DET-3D-05 explicitly deletes the existing implementation.
- **DeepSORT CNN re-ID tracker** — CPU killer on our budget; ByteTrack chosen instead.
- **VLM `scene_describer` mixed into detection pipeline** — 3–5 s/frame, kept as a separate subsystem.
- **`mAP` reporting without committed labeled evaluation set** — forbidden; `center_error_m` + `per_class_recall` against MuJoCo GT is the honest replacement.
- **Per-frame model re-initialization** — models load once, backend instance holds the reference.
- **Real-time BoxeR** — 5–30 s/frame on CPU; shipped as offline / reference-quality backend only. Not a regression target.

---

## Traceability

Filled in by roadmapper. Each requirement must map to exactly one phase.

| Requirement | Phase |
|-------------|-------|
| DET-API-01..07 | TBD |
| DET-MODELS-01..08 | TBD |
| DET-3D-01..07 | TBD |
| DET-UI-01..06 | TBD |
| DET-METRICS-01..05 | TBD |
| DET-PIPELINE-01..05 | TBD |
| DET-STRETCH-01..04 | TBD (stretch, last phase) |

---

*Defined: 2026-04-13 — pre-roadmap*
