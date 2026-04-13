# Research Summary: v3.0 Pluggable Perception & 3D Object Detection

**Project:** Multi-Robot 3D Reconstruction — Argus
**Domain:** Pluggable object-detection + real 3D oriented bounding-box regression on top of an existing multi-robot SLAM + FastAPI + React/Three.js stack (CPU-only MuJoCo simulation)
**Researched:** 2026-04-13
**Overall confidence:** MEDIUM-HIGH

---

## Executive Summary

v3.0 repeats the v2.0 play exactly: take a hardcoded, monolithic system component (`ObjectDetector`) and replace it with a `Protocol + Registry + pluggable backends` abstraction — the same pattern that v2.0 applied to SLAM. Every architectural decision, subprocess-isolation strategy, frontend picker flow, parameter schema, and metrics panel extension has a direct v2.0 analogue already verified in-tree. This is a known-good pattern applied to a new domain, which substantially de-risks the milestone.

The headline stack finding is that `facebook/BoxeR` is not a competitor to YOLO: it is a full 2D-to-3D lifting pipeline (OWLv2 + DINOv3 + BoxerNet transformer) that runs at 5–30 s/frame on CPU, has no pip package, and carries a CC-BY-NC-4.0 license. It is valuable as an offline / reference-quality backend and as the user's explicitly-named stretch goal, but must be treated as such — not as a real-time backend. For real-time CPU detection, the stack standardizes on three tiers: YOLOv11-nano (kept as default), RT-DETRv2-S via HuggingFace `transformers` as the transformer alternative (~100–180 ms/frame ONNX at 320px), and OWLv2 for open-vocabulary on-demand use. BoxeR integrates via a `SubprocessDetectorBridge` (ZMQ PAIR + msgpack, same pattern as `SubprocessSLAMBridge`) and is never loaded in-process.

The single largest technical upgrade in v3.0 is replacing the current "median-depth point" with a true oriented 3D bounding box. The correct CPU-viable method is Open3D `compute_oriented_bounding_box(robust=True)` on the depth-frustum point cluster carved out per 2D detection — PCA on a filtered pointcloud — running under 5 ms/detection on CPU using the already-present `open3d` dependency. Median-depth is explicitly wrong for oriented boxes (a chair at 45 degrees has 0.8–1.4 m depth range; the median hits neither face nor centroid) and is relegated to a named legacy fallback only. The wire format for oriented boxes is locked to `(center[3], half_extents[3], quaternion[4] in xyzw with qw >= 0)` — server owns all geometry, frontend is a dumb renderer. The current client-side focal-length back-projection in `DetectionBoxes.ts` is deleted.

---

## Key Findings

### Stack (NEW additions only — v1.0/v2.0 stack unchanged)

The existing `perception` extra in `pyproject.toml` already covers `torch>=2.10.0`, `transformers>=5.3.0`, `ultralytics>=8.4.24`. The v3.0 pip additions are minimal:

```toml
# extend [project.optional-dependencies] perception group:
"onnxruntime>=1.20.0",   # 2-3x CPU speedup for RT-DETR/RF-DETR ONNX
"timm>=1.0.11",           # RF-DETR DINOv2 backbone loader
"dill>=0.3.8",            # BoxeR subprocess worker serialization
```

BoxeR is NOT pip-installable. It installs into a subprocess worker venv via `scripts/setup_boxer_subprocess.sh` (git clone + dep install). It is never imported in the main FastAPI process. No new CUDA/GPU deps of any kind.

**Core new technologies:**

| Technology | Version | Role | Confidence |
|------------|---------|------|------------|
| HuggingFace `transformers` | >=5.3.0 (already declared) | Unified loading for RT-DETRv2, OWLv2, DINOv3 | HIGH |
| RT-DETRv2-S via transformers | `PekingU/rtdetr_v2_r18vd` checkpoint | Transformer real-time detector; 70–120 ms/frame ONNX 320px CPU | HIGH |
| OWLv2 via transformers | `google/owlv2-base-patch16-ensemble` | Open-vocabulary zero-shot detection; 1–4 s/frame, on-demand only | HIGH |
| onnxruntime | >=1.20.0 | 2–3x speedup over PyTorch for DETR-family on CPU | HIGH |
| facebook/BoxeR | git main, subprocess venv | Offline high-quality OBB backend; 5–30 s/frame CPU; CC-BY-NC-4.0 | MEDIUM |
| Open3D `compute_oriented_bounding_box` | >=0.18.0 (already present) | Default 3D OBB lifter; <5 ms/detection via PCA on depth frustum | HIGH |

**CPU latency reality check (single i7/i9, honest estimates):**

| Backend | Total latency | FPS | Role |
|---------|--------------|-----|------|
| YOLOv11-nano + PCA-OBB | 100–200 ms | 2–4 | Default real-time |
| RT-DETRv2-S ONNX 320px + PCA-OBB | 100–180 ms | 3–5 | Transformer real-time |
| OWLv2-base + PCA-OBB | 1.5–4 s | 0.25–0.5 | Open-vocab on-demand |
| BoxeR subprocess | 5–30 s | 0.03–0.2 | Offline reference-quality |

What NOT to add: CUDA/cuDNN/TensorRT (no GPU), mmdetection/detectron2 (500-dep toolbox), FCOS3D/ImVoxelNet/MonoFlex/CubeRCNN (outdoor KITTI-trained, will not transfer to indoor MuJoCo), Frustum-PointNets/VoteNet (require CUDA PointNet++ ops), Grounding DINO (8–15 s/frame CPU, OWLv2 strictly better at same cost), DeepSORT re-ID CNN (CPU killer — ByteTrack instead).

---

### Features (by category)

**DET-API — Table Stakes**

| ID | Feature | Notes |
|----|---------|-------|
| T1 | `DetectorProtocol` runtime-checkable interface | `process_frame -> Detections2D`, `reset`, `get_metrics`, `warmup`, `CAPABILITIES`, `PARAMETER_SCHEMA` |
| T2 | `DetectorRegistry` + `@detector_backend` decorator | Lazy class-path loading, `available: false + reason` for missing deps |
| T3 | YOLO refactored behind Protocol — zero behavioral regression | Proof the abstraction is correct; regression test on fixture frames |
| T4 | Confidence threshold, class filter, min-bbox-size as live-tunable schema params | Wire through `detector_param_update` WebSocket |
| T5 | Pre-session detector selection via REST + restart overlay | Mirror v2.0 SLAM picker; hot-swap explicitly deferred |
| T6 | Graceful fallback when backend deps missing | `available: false, reason: "..."` in registry listing |
| T10 | Per-camera / per-robot registry constructor kwargs | Constrains T1 API shape; no extra phase work |
| T11 | Async per-robot `DetectorWorker` with single-slot latest-frame queue | Per-robot, not shared; backpressure via newest-wins |

**DET-MODELS**

| ID | Feature | Notes |
|----|---------|-------|
| T7 | BoxeR subprocess backend + RT-DETRv2 in-process ONNX backend | BoxeR is primary pluggability regression test; RT-DETR is real-time transformer option |

**DET-3D — Table Stakes**

| ID | Feature | Notes |
|----|---------|-------|
| T8 | `Detection3DProtocol` + `Detection3DRegistry` + `PointClusterLifter` | PCA-OBB on depth frustum via Open3D; yaw-only for indoor MVP |
| T9 | Server-owned OBB geometry; delete client-side focal-length reconstruction | Frontend becomes dumb renderer of `(center, half_extents, quaternion)` |

**DET-UI — Table Stakes**

| ID | Feature | Notes |
|----|---------|-------|
| T12 | Live detection metrics in MetricsPanel | `inference_ms p50/p95`, `detections/frame`, `mean_confidence`, FPS |
| T13 | Frontend detector picker + lifter picker + capability badges + parameter panel | Mirror SLAM picker; `LifterDropdown` hides when `outputs_3d_natively` |
| T14 | `DetectorNode` + `BoxLiftNode` + `TrackerNode` in React Flow pipeline editor | `Detections2D`/`Detections3D` port types; `perception` category |

**Differentiators (should-have, Phase 8):**

| ID | Feature | Notes |
|----|---------|-------|
| D1 | ByteTrack multi-object tracker with persistent `track_id` | CPU-friendly, Apache-2.0, ~300 LOC |
| D2 | World-frame multi-robot detection fusion | Class + spatial IoU cluster per frame; 0.5 m radius default |
| D6 | MuJoCo GT body-position extractor + per-class `center_error_m` + recall | Honest sim-only metrics; forbid "mAP" without committed labeled GT |
| D4 | 2D bbox overlay on raw RGB camera feed panel | Simple canvas overlay (Phase 3) |
| D5 | Confidence histogram + per-class count sparklines | Rolling window in MetricsPanel (Phase 6) |
| D10 | Export detections JSONL per session | `/api/detections/export` (Phase 6) |
| D9 | Semantic map with TTL + ghosted Three.js layer | Depends on D1+D2 (Phase 8) |

**Explicit anti-features (hard no for v3.0):**

- Hot-swap detector mid-session (mirror v2.0 SLAM precedent)
- Multiple heavy detectors simultaneously on all robots (CPU budget collapse)
- DeepSORT CNN re-ID backbone (CPU killer; ByteTrack is the answer)
- GPU-required backends (BEVFormer, CenterPoint, WildDet3D) — defer to v4.0
- VLM `scene_describer.py` mixed into detection pipeline (3–5 s/frame; keep separate)
- Client-side 3D geometry reconstruction (T9 replaces this)
- Per-frame model re-initialization (load once, hold reference)

---

### Architecture — Locked Decisions

#### Decision A: Protocol Split — 2D and 3D are separate registries

`DetectorProtocol` (2D) and `Detection3DProtocol` (3D lifter) are separate runtime-checkable Protocols with separate registries (`DetectorRegistry` and `Detection3DRegistry`) in `src/perception/registry.py`. The 2D stage outputs `Detections2D`; the 3D stage consumes it and outputs `Detections3D` (list of `OrientedBox3D`). End-to-end backends signal `CAPABILITIES["outputs_3d_natively"] = True`; `DetectorWorker` bypasses the lifter registry for those. Frontend hides `LifterDropdown` when `activeDetector.outputs_3d_natively`.

#### Decision B: Per-Robot `DetectorWorker` (not shared thread)

One `DetectorWorker` thread per robot, not one shared thread draining all robots. Each worker owns a single-slot latest-frame queue (newest wins, backpressure). `DetectorWorkerPool = {rid -> DetectorWorker}` replaces `ObjectDetector._run_loop()`. MVP: all robots use the same backend. Stretch: `app.state.pending_detector_backend_per_robot` dict enables heterogeneous backends.

#### Decision C: Subprocess Bridge — separate class, same structural shape

`SubprocessDetectorBridge` is a distinct class (`src/perception/subprocess_bridge.py`) that mirrors `SubprocessSLAMBridge` structurally. Same ZMQ PAIR + msgpack multipart protocol, same 5 s `HANG_TIMEOUT_MS`, same `process.poll()` crash detection and fallback path. Sharing the SLAM bridge would couple failure domains. BoxeR requires subprocess isolation: heavy dep cocktail (DINOv3 + OWLv2 + BoxerNet + moderngl), CC-BY-NC-4.0 license, and 5–30 s/frame mean it cannot live in the main FastAPI process.

#### Decision D: Thread Config Moved to `_thread_config.py`

`torch.set_num_threads(2)` at module scope in `detector.py` (line 25) is removed. All thread-pool configuration (torch, OMP, MKL, OPENBLAS) moves to `src/_thread_config.py` imported at the top of `src/main.py` before any torch or numpy import. Budget: `detector_threads = max(2, C // (2 + N_robots))`. For the BoxeR subprocess, thread config is set inside the subprocess worker only.

#### Decision E: OBB Wire Format (canonical, locked)

Server sends per-detection:
```json
{
  "center": [cx, cy, cz],
  "half_extents": [hx, hy, hz],
  "quaternion": [qx, qy, qz, qw],
  "class_id": 42,
  "class_name": "chair",
  "score": 0.87,
  "track_id": 7
}
```
- Quaternion convention: `(x, y, z, w)` — scipy/Three.js order (NOT ROS `(w,x,y,z)`)
- Canonical form: `qw >= 0` enforced on serialize
- `half_extents` are half-widths along local axes (pre-rotation), in meters
- `center` is world-frame meters, rounded to 3 decimal places
- `OrientedBox3D.to_wire()` is the ONLY path to produce this payload; inline quaternion construction in backends is forbidden
- Round-trip test: `obb == OrientedBox3D.from_wire(obb.to_wire())` to +/-1e-6
- Frontend: `wireOBBToMesh()` wraps `THREE.Quaternion.fromArray([qx,qy,qz,qw])` — single conversion utility, no other conversion points

#### Decision F: 3D OBB Method — PCA on filtered pointcloud, NOT median depth

Median depth is kept only as `MedianDepthLifter` (legacy; identity quaternion; `outputs_oriented=False`). Default v3.0 3D lifter is `PointClusterLifter` using Open3D `compute_oriented_bounding_box(robust=True)` on the depth-frustum point cluster. Steps: (1) MAD-based depth filter on bbox ROI, (2) DBSCAN cluster (eps=0.05 m) to reject glass/sky pixels, (3) PCA on dominant cluster for yaw-only OBB (gravity-aligned, sufficient for indoor furniture MVP), (4) z-range from cluster min/max depth. Requires >=50 valid depth pixels; falls back to `MedianDepthLifter` if too few. ~1–5 ms/detection on CPU.

#### Decision G: Metrics — Honest and MuJoCo-grounded

Ship `detections_per_sec`, `inference_ms p50/p95`, `mean_confidence`, `3d_center_jitter_m` (stddev of persistent object's 3D center across 30 frames), per-robot queue depth, detection freshness (`sim_now - capture_timestamp`). For GT: extract MuJoCo body positions via `mj_name2id + data.xpos`; compute `center_error_m` and `per_class_recall`. **Forbid "mAP" in the UI** unless a labeled eval set is committed alongside the scene.

**Major components (Python):**

| Component | File | Responsibility |
|-----------|------|----------------|
| `DetectorProtocol`, `Detection3DProtocol`, `OrientedBox3D`, `Detections2D/3D` | `src/perception/protocol.py` | Contracts, dataclasses, wire types |
| `DetectorRegistry`, `Detection3DRegistry`, decorators | `src/perception/registry.py` | Lazy class-path loading, availability reporting |
| `YOLOv11Backend` | `src/perception/backends/yolov11_backend.py` | Wraps existing `ObjectDetector._detect()` — NOT rewritten |
| `BoxeRBackend` | `src/perception/backends/boxer_backend.py` | Subprocess bridge to BoxeR worker |
| `RTDETRv2Backend` | `src/perception/backends/rtdetr_backend.py` | In-process ONNX; `transformers.RTDetrV2ForObjectDetection` |
| `SubprocessDetectorBridge` | `src/perception/subprocess_bridge.py` | ZMQ PAIR + msgpack, 5 s watchdog, crash fallback |
| `MedianDepthLifter` | `src/perception/lifters/median_depth.py` | Legacy v1/v2 behavior, wraps `detection_3d.py` |
| `PointClusterLifter` | `src/perception/lifters/point_cluster.py` | PCA-OBB on depth frustum (default v3.0) |
| `DetectorWorker` / `DetectorWorkerPool` | `src/perception/detector_worker.py` | Per-robot thread, single-slot queue, 2D+3D pipeline |
| `detector_routes.py` | `backend/web/detector_routes.py` | REST `/api/detectors/*` mirror of `slam_routes.py` |
| `src/perception/geometry.py` | NEW | Single `unproject_pixel_to_world`; removes 70 deg hardcoded FoV and `CLOUD_CONFIGS` hack |

**Modified to gut/replace:**

- `src/perception/detector.py` — demoted to shim; `ObjectDetector` replaced by `DetectorWorkerPool` in Coordinator after BoxeR is green
- `src/perception/detection_3d.py` — moved into `MedianDepthLifter.lift()`
- `frontend/src/components/DetectionBoxes.ts` — client-side focal-length geometry math deleted; becomes dumb OBB renderer

---

### Critical Pitfalls

**P1: Transformer first-inference stall (5–30 s) blocks the simulation loop.**
HuggingFace DETR-family models trigger oneDNN kernel selection + lazy weight materialization on first call — 5–30 s on CPU. The simulation runs but detections appear frozen; first boxes attach to stale poses. Prevention: add explicit `warmup(dummy_rgb)` to `DetectorProtocol`; registry MUST call warmup on the worker thread before the UI reports "ready". Pre-fetch all model weights to `./models/` via `make download-models`. Track `detector_first_inference_ms` vs `detector_steady_state_ms` separately.

**P2: OBB orientation sign/convention drift across Python, wire, and Three.js.**
Open3D uses 3x3 matrix. SciPy uses `(x,y,z,w)`. Three.js uses `(x,y,z,w)`. ROS uses `(w,x,y,z)` in some bindings. Any two-library disagreement renders boxes rotated 180 degrees around a random axis. Prevention: `OrientedBox3D.to_wire()` is the ONLY path to produce wire quaternions. Lock format to `(qx,qy,qz,qw)` with `qw>=0`. Round-trip test to +/-1e-6. Frontend uses single `wireOBBToMesh()` utility.

**P3: Median depth is wrong for oriented 3D boxes.**
A chair at 45 degrees has 0.8–1.4 m depth range; the median gives ~1.1 m — neither face nor centroid. Glass/transparent MuJoCo objects leak background depth into the median. This is fine for a 2D center; it is actively wrong for orientation estimation. Prevention: `PointClusterLifter` always uses MAD-filtered cluster + PCA. `MedianDepthLifter` is a named legacy lifter, not the default.

**P4: Torch thread pool collision with SLAM and main process.**
`torch.set_num_threads(2)` at module scope in `detector.py` is a process-global setting that collides with Open3D/BLAS. Adding a transformer backend inverts the workload from BLAS-heavy (where the existing setting was invisible) to oneDNN-heavy (oneDNN reads `OMP_NUM_THREADS` at first call, ignoring torch's setting). Prevention: move ALL thread-pool configuration to `src/_thread_config.py` set at the top of `main.py` before any torch import. Run BoxeR in a subprocess so its thread pools cannot pollute the main process.

**P5: `eval()` + `torch.inference_mode()` forgotten — RAM blowup + 10x slowdown.**
PyTorch defaults are train-mode with gradient tracking. With a 2-FPS detector running for 5 minutes, retained activation tensors cause RSS to climb to 6–8 GB for a model that should sit at ~1.5 GB, eventually OOM-killing the coordinator. Prevention: every backend `__init__` MUST call `model.eval()` + freeze all parameters. Every `_detect()` MUST wrap inference in `with torch.inference_mode():`. Smoke test: 100 inferences, final RSS < initial RSS + 200 MB.

**Notable moderate pitfalls (address in respective phases):**

- **Fake mAP (P11):** Never display `mAP` without committed labeled GT. Use MuJoCo body positions for honest `center_error_m`.
- **Stale-pose detections (P8):** Attach `capture_pose` + `capture_timestamp` to every detection at submission time. Downstream consumers MUST use `capture_pose`, NOT current robot pose.
- **Registry circular imports (P9):** Module layout order is mandatory — `types.py` -> `protocol.py` -> `registry.py` -> `backends/`. Backends wrap heavy imports in try/except. Use explicit `register_builtin_backends()` from `main.py`.
- **Three.js GPU buffer leak (P14):** Use `InstancedMesh` for OBBs (mirror `VoxelManager` structure). Explicit `.dispose()` on unmount.
- **Preserve YOLO baseline (P16):** Wrap existing `ObjectDetector` as `YOLOv11Backend` without touching it. Only remove old code after BoxeR is green in CI for a full day.

---

## Implications for Roadmap

Suggested phase skeleton: **7 phases + 1 stretch phase (8 total)**. Final count from roadmapper.

### Phase 1: Detector API Foundation (DET-API)
**Rationale:** T1->T2->T3 is atomic. No other feature is buildable until the Protocol, Registry, and YOLO-behind-Protocol exist. Zero user-visible change.
**Delivers:** `DetectorProtocol` (with `warmup()`), `Detection3DProtocol`, `DetectorRegistry`, `Detection3DRegistry`, `YOLOv11Backend` wrapping existing `ObjectDetector`, `MedianDepthLifter` wrapping existing `detection_3d.py`, `_thread_config.py`, `RobotId` type, module layout (`types.py` / `protocol.py` / `registry.py` / `backends/`).
**Features:** T1, T2, T3, T6, T10
**Pitfalls addressed:** P4 (thread config moved), P9 (module layout prevents circular imports), P16 (YOLO preserved), P5 (eval mode baked into backend contract)
**Research flag:** Standard patterns — skip phase research

### Phase 2: Per-Robot Worker + REST/WS Plumbing (DET-API)
**Rationale:** Worker + wire plumbing before any backend integration or UI work. Mirrors v2.0 Phase 2 discipline: establish plumbing before painting UI.
**Delivers:** `DetectorWorker` + `DetectorWorkerPool` with per-robot single-slot queue; `capture_pose` + `capture_timestamp` on all detection payloads; `detector_routes.py` REST endpoints; `server.py` state fields + WS dispatch; `SubprocessDetectorBridge` skeleton; `OrientedBox3D.to_wire()` wire format + round-trip test.
**Features:** T4, T5 (server side), T11
**Pitfalls addressed:** P8 (capture_pose baked in from day one), P2 (wire format defined before any backend produces data)
**Research flag:** Standard patterns — skip phase research

### Phase 3: Frontend Picker + UI (DET-UI)
**Rationale:** Users need to see and control detection before any new model integrates. Reuses v2.0 UI components verbatim. Isolating UI here means it can land while backend work continues.
**Delivers:** `detectorStore` Zustand slice; `DetectorSection` (DetectorDropdown + LifterDropdown + ParameterPanel); capability badges; restart overlay wired to detector; `DetectionMetricsCard` stub; RGB bbox overlay on camera feed; warmup-complete before UI shows "ready".
**Features:** T5 (frontend), T12 (stub), T13, D4, D7
**Pitfalls addressed:** P1 (warmup-complete guard in UI)
**Research flag:** Standard patterns — skip phase research

### Phase 4: Real 3D OBB Pipeline (DET-3D)
**Rationale:** Core PROJECT.md deliverable. Must ship before the second backend so geometry is correct when BoxeR arrives. T8 and T9 are paired — server-side OBB is invisible until the frontend stops reconstructing boxes client-side.
**Delivers:** `PointClusterLifter` (PCA-OBB, Open3D); `src/perception/geometry.py` single-projection-path (removes 70 deg hardcoded FoV + `CLOUD_CONFIGS` hack); `OrientedBox3D.to_wire()` canonical quaternion; frontend `DetectionBoxManager` simplified to dumb OBB renderer; `OBBManager` using `InstancedMesh`; geometry convention test.
**Features:** T8, T9, D3
**Pitfalls addressed:** P2 (wire format + round-trip test), P3 (PCA replaces median depth), P14 (InstancedMesh)
**Research flag:** PCA-OBB is textbook — skip phase research

### Phase 5: Second Backend — BoxeR + RT-DETRv2 (DET-MODELS)
**Rationale:** T7 is the pluggability regression test — it proves the abstraction correct under a fundamentally different architecture. BoxeR runs last in the core set because every API decision made in Phases 1–4 must be locked before it can stress-test them.
**Delivers:** `BoxeRBackend` via `SubprocessDetectorBridge` (ZMQ PAIR + msgpack; 5 s watchdog; BoxeR worker venv via `scripts/setup_boxer_subprocess.sh`); `RTDETRv2Backend` in-process ONNX; `make download-models`; `model.eval()` + `torch.inference_mode()` enforced; warmup verified; LICENSES.md updated for CC-BY-NC-4.0.
**Features:** T7
**Pitfalls addressed:** P1 (warmup verified for HF backends), P5 (eval mode enforced), P7 (revision hash locked per checkpoint)
**Research flag:** NEEDS phase research — verify `facebook/boxer` repo state, current checkpoint names, and Python 3.12 compatibility via Context7 at phase-planning time. Do not trust April 2026 research memory for 2022 CVPR code.

### Phase 6: Detection Metrics + MuJoCo GT (DET-METRICS)
**Rationale:** Metrics are only meaningful after the full 2D->3D->wire pipeline is stable. MuJoCo GT extractor needs a known-stable detection layer to compare against.
**Delivers:** MetricsPanel fully populated (inference_ms p50/p95, detections/frame, mean confidence, 3d_center_jitter_m, per-robot queue depth, detection freshness); MuJoCo GT body-position extractor; per-class `center_error_m` + `per_class_recall`; detection JSONL export endpoint; RSS memory smoke test.
**Features:** T12 (complete), D5, D6, D10
**Pitfalls addressed:** P11 (honest metrics, no fake mAP), P5 (memory test catches eval-mode regressions)
**Research flag:** MuJoCo body introspection is well-documented. Flag if scene XML structure is unclear — 30-minute scene inventory check at phase-planning time.

### Phase 7: Pipeline Editor Perception Nodes (DET-PIPELINE)
**Rationale:** Pipeline editor nodes are the final integration surface — they reflect all underlying typed contracts. Doing them last avoids port-schema churn. Kahn's-algorithm validator is data-type agnostic; no algorithm changes needed.
**Delivers:** `DetectorNode`, `Detection3DNode`, `TrackerNode` node definitions; `Detections2D` + `Detections3D` port types; `perception` NodeCategory; per-edge type mismatch validation in `pipelineValidation.ts`; `perception_rgbd` built-in preset; `pipeline_routes.py` extended to map `detector_generic` nodes to `DetectorWorkerPool`.
**Features:** T14, D11 (partial)
**Pitfalls addressed:** P15 (port types centralized, not string literals)
**Research flag:** Standard patterns — skip phase research

### Phase 8 (Stretch): Tracker, Multi-Robot Fusion, Semantic Map
**Rationale:** High-value differentiators that depend on stable D3 + `track_id` infrastructure. Deferred to avoid scope creep in the core phases.
**Delivers:** ByteTrack multi-object tracker (`track_id` stable per class + spatial IoU); world-frame multi-robot detection fusion (class + 0.5 m cluster radius); `SemanticMap` with TTL + ghosted Three.js layer; per-robot detector selection; FP flagging UI.
**Features:** D1, D2, D9, D8, D12
**Research flag:** ByteTrack is well-documented. NEEDS phase research for multi-robot fusion spatial threshold tuning.

### Phase Ordering Rationale

- T1->T2->T3 is non-negotiable first: Registry does not exist without Protocol; YOLO cannot be safely wrapped without both.
- Worker + REST/WS (Phase 2) before frontend (Phase 3): establish plumbing before painting UI — direct v2.0 discipline reuse.
- Real 3D OBBs (Phase 4) before second backend (Phase 5): geometry must be correct before BoxeR outputs can be compared. Mis-ordered, BoxeR debug gets conflated with projection bugs.
- BoxeR in Phase 5 not Phase 3: it is the regression test for the entire abstraction. Running it before the abstraction is fully exercised produces a misleading signal.
- Metrics (Phase 6): only useful when there is something stable to measure.
- Pipeline editor last (Phase 7): reflects all contracts; doing it last prevents port-schema churn across other phases.

### Deferred to v4.0

- GPU-required SOTA 3D detectors (BEVFormer, WildDet3D, 3D-MOOD, CenterPoint)
- Open-vocabulary detection at useful FPS (Grounding DINO, full OWLv2 pipeline)
- Hot-swap detector mid-session
- Online active learning / model retraining
- Neural/implicit representation SLAM backends (already excluded v2.0/v3.0)

---

## Open Questions (flagged for phase-level resolution)

| Question | Phase | Disposition |
|---------|-------|-------------|
| Current `facebook/boxer` repo structure + checkpoint names | Phase 5 | Empirical — verify via Context7; do not trust April 2026 research memory for 2022 CVPR code |
| Actual BoxeR CPU latency at 640x480 MuJoCo scene resolution | Phase 5 | Benchmark on target hardware; 5–30 s is a wide bound |
| MuJoCo office scene XML — stable class-labeled geoms for GT extractor? | Phase 6 | 30-min scene inventory check at phase-planning time |
| ByteTrack spatial association threshold for indoor office scenes | Phase 8 | 0.5 m is starting default; tune empirically |
| Multi-robot detection fusion spatial threshold | Phase 8 | Architecturally supported; parameter tuning deferred |
| Hot-swap detector mid-session | Deferred | NOT in scope; mirror v2.0 pre-session-selection precedent |
| Heterogeneous per-robot backends at MVP | API ready Phase 1 | Full implementation deferred to Phase 8 |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All new pip deps verified with CPU wheel support; BoxeR subprocess pattern mirrors proven v2.0 ORB-SLAM3 approach; RT-DETRv2 latency from confirmed benchmarks; Open3D PCA-OBB API confirmed |
| Features | HIGH | v2.0 SLAM pattern directly applicable (in-tree verified); all feature IDs derived from in-tree code inspection; dependency ordering is non-speculative |
| Architecture | HIGH | Derived from direct read of all relevant in-tree files; Protocol/Registry/Worker/Bridge shapes specified to function-signature level; no architectural unknowns |
| Pitfalls | MEDIUM-HIGH | v2.0-learned pitfalls confirmed in this codebase; BoxeR-specific repo state is the one empirically-unknown item (flagged for Phase 5 research) |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **BoxeR repo state:** `facebook/boxer` was a 2022 CVPR repo. Exact current HuggingFace checkpoint structure, required `download_ckpts.sh` targets, and Python 3.12 compatibility need live verification at Phase 5 planning. Do not proceed to Phase 5 implementation without this.
- **Scene XML inventory:** Whether MuJoCo office scene files carry stable class-labeled geoms for the GT extractor (D6) is unknown without a direct XML inspection. Flag for Phase 6 planning (30-minute check).
- **RF-DETR-Nano as fallback:** Roboflow's `rfdetr` package pins older torch versions that may conflict with the existing venv. If it causes dependency conflicts, drop it and use RT-DETRv2-S exclusively. Treat RF-DETR as MEDIUM confidence and conditional.

---

## Sources

### Primary (HIGH confidence)
- `src/slam/protocol.py`, `src/slam/registry.py`, `src/slam/backends/subprocess_bridge.py` — v2.0 in-tree: Registry/Protocol/Bridge patterns verified directly
- `src/perception/detector.py`, `src/perception/detection_3d.py` — Current hardcoded YOLO path; sign-flip conventions and median-depth bugs documented
- `frontend/src/components/DetectionBoxes.ts` — Client-side geometry reconstruction to be deleted in T9
- [facebook/BoxeR on HuggingFace](https://huggingface.co/facebook/boxer) — Official model repo; CC-BY-NC-4.0 confirmed; CLI-only interface confirmed
- [OWLv2 transformers docs](https://huggingface.co/docs/transformers/en/model_doc/owlvit) — Stable since transformers v4.35
- [RT-DETRv2 HuggingFace checkpoint](https://huggingface.co/PekingU/rtdetr_v2_r18vd) — CPU-runnable confirmed
- [RF-DETR-Nano CPU benchmark issue #641](https://github.com/roboflow/rf-detr/issues/641) — ~180 ms @ 312x312 CPU confirmed (direct measurement)
- [Open3D OrientedBoundingBox API](https://www.open3d.org/docs/release/python_api/open3d.geometry.OrientedBoundingBox.html) — `compute_oriented_bounding_box(robust=True)` confirmed
- [facebookresearch/boxer GitHub](https://github.com/facebookresearch/boxer) — ~1.3 s/frame MPS reported by authors; no pip release

### Secondary (MEDIUM confidence)
- [Best Object Detection Models 2026 (Roboflow blog)](https://blog.roboflow.com/best-object-detection-models/) — Market landscape
- [RT-DETR vs YOLOv8 comparison (Ultralytics docs)](https://docs.ultralytics.com/compare/rtdetr-vs-yolov8/) — CPU latency estimates
- [Semantic SLAM survey](https://www.sciencedirect.com/article/pii/S2667305325001176) — Multi-robot detection fusion patterns
- [ByteTrack introduction](https://datature.io/blog/introduction-to-bytetrack-multi-object-tracking-by-associating-every-detection-box) — CPU-friendly tracker confirmed

### Tertiary (LOW confidence / deferred reference)
- [ovmono3d 3DV 2026](https://arxiv.org/abs/2411.16833) — No runnable checkpoint as of April 2026; revisit at v3.1
- [3D-MOOD monocular open-set 3D](https://arxiv.org/html/2507.23567) — GPU-only; cited as anti-feature reference only

---

*Research completed: 2026-04-13*
*Ready for roadmap: yes*
