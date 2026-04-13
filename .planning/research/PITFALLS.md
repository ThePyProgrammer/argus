# Pitfalls Research

**Domain:** Pluggable object detection + 3D oriented bounding box regression layered onto an existing multi-robot SLAM + FastAPI + React/Three.js stack (CPU-only MuJoCo simulation)
**Researched:** 2026-04-13
**Confidence:** MEDIUM-HIGH (HuggingFace transformer + torch CPU pitfalls verified via official docs and widely-reported GitHub issues; v2.0 integration pitfalls verified directly against current codebase in `src/perception/detector.py`, `src/perception/detection_3d.py`, `src/slam/protocol.py`, and `src/slam/backends/`)

Scope guardrails:
- Only pitfalls specific to ADDING pluggable detection + real 3D OBB regression to THIS codebase.
- Each pitfall names the concrete file, message type, store, or subprocess surface it touches.
- v2.0-learned pitfalls (subprocess crash recovery, restart overlay, schema-driven params, coordinate frame mismatch) are treated as already-learned and only called out when the v3.0 feature set opens a new failure mode on top of the v2.0 solution.
- Each pitfall maps to a concrete v3.0 phase/plan in the Pitfall-to-Phase Mapping table at the end.

---

## Critical Pitfalls

### Pitfall 1: Transformer Detector First-Inference Stall Blocks the Simulation Loop

**What goes wrong:**
On the first call, HuggingFace detection transformers (BoxeR/DETR-family, Grounding DINO, OWL-ViT) trigger expensive one-time costs: PyTorch autotune/oneDNN/NNPACK kernel selection, lazy parameter materialization, CUDA-graph / torch.compile tracing if enabled, and first-time `AutoProcessor`/`AutoTokenizer` HuggingFace Hub download. On CPU this is dominated by oneDNN/MKL convolution kernel selection and Python-side graph construction, commonly 5-30 seconds for a DETR-class encoder at 640px. The existing `ObjectDetector._run_loop()` (detector.py:146) calls `self._model(rgb, ...)` synchronously in a thread that also submits new frames — the first inference blocks submissions, and because `submit_frame()` keeps only the latest frame per robot (detector.py:128-131), the simulation still runs, but the detection pipeline appears "stuck" and the first reported detection is aligned to a pose that is already 5-30s stale.

**Why it happens:**
The v1/v2 detector was a small YOLO-nano which hides this problem (first inference ≈ 200-400ms on CPU). Teams swap in a transformer behind the same interface and assume "same shape of call, same latency envelope." The model's docstring advertises steady-state throughput, not cold-start. Worse, HuggingFace's default `from_pretrained(...)` will hit the network on first run (weights + `preprocessor_config.json` + tokenizer/processor files) and that network fetch is indistinguishable from "the model is slow" from the outside.

**How to avoid:**
- Introduce an explicit `warmup(dummy_rgb)` method on the detector protocol. The detector registry MUST call `warmup()` on the worker thread BEFORE the UI reports "ready" and before any real frame is submitted.
- Cache model weights to a project-local `./models/` directory (`HF_HOME=./models` or `cache_dir=`) and ship a `make download-models` / `scripts/fetch_models.py` entrypoint that pre-fetches weights so a clean checkout isn't racing the simulation.
- Record two separate metrics into `MetricsPanel`: `detector_first_inference_ms` and `detector_steady_state_ms`. If they differ by >3x, warmup is incomplete.
- Run warmup with the same image size and same dtype (incl. `torch.no_grad()`, `.eval()`) as real inference. A warmup at 224×224 does not cover the 640×480 MuJoCo capture path.
- For Grounding DINO / OWL-ViT, the **text prompt** path has its own first-call stall (tokenizer build + text encoder). Warmup MUST include a representative prompt, not just the image.

**Warning signs:**
- First `detector_ms` metric >5x steady-state.
- 3D boxes for the first few seconds appear attached to stale robot poses (wrong room, through walls).
- `HF_HUB_OFFLINE=1` produces a confusing "connection error" — means weights weren't pre-fetched.

**Phase to address:** Phase 2 — Detector API + Registry (define `warmup()` in the protocol); Phase 3 — BoxeR backend (implement + verify); Phase 6 — UX polish (loading overlay tied to warmup completion).

---

### Pitfall 2: Torch Thread Pool Collision Between SLAM, Detector, and Main Process

**What goes wrong:**
`src/perception/detector.py:25` sets `torch.set_num_threads(2)` at import time. This is a process-global setting. In v3.0 it collides with: (a) Open3D's internal parallelism (mesh reconstruction, PGO — both already in v2.0), (b) NumPy's BLAS thread pool (MKL/OpenBLAS default = all cores), and (c) a second detector backend if two are imported (the later import may silently re-set the thread count, or MKL/oneDNN may honor only the first call). With N=2+ robots each submitting frames to a single detector thread that calls BoxeR (which uses ALL torch threads it's given), the exploration planner's A* + Voronoi re-partitioning starves for CPU and the robots stutter.

**Why it happens:**
Torch, NumPy/BLAS, oneDNN, and OpenMP each have their own thread pool controls (`torch.set_num_threads`, `torch.set_num_interop_threads`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`). Setting one does not constrain the others. The v2 ICP+Open3D workload is dominated by BLAS and Open3D's internal TBB, not torch — so the existing `set_num_threads(2)` has been invisible. A transformer detector inverts this: most CPU goes through torch's oneDNN path, and oneDNN reads `OMP_NUM_THREADS` at first call, not `torch.set_num_threads()` issued later.

**How to avoid:**
- Set threading envs at process start, BEFORE torch or numpy are imported. Do this in `src/main.py` top-of-file or in a `src/_thread_config.py` imported first.
- Budget explicitly: total CPU cores = C. Allocate `detector_threads = max(2, C // (2 + N_robots))`, `slam_threads = C - detector_threads - 2`. Expose both as settings. Document the arithmetic in code.
- Set BOTH torch (`torch.set_num_threads`, `torch.set_num_interop_threads=1`) AND env vars (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`) to the same detector budget inside the detector subprocess only.
- Run detector in a subprocess (reuse `src/slam/backends/subprocess_bridge.py` ZMQ PAIR pattern) so its thread pool cannot poison the main process. This is the v2.0 lesson from ORB-SLAM3 applied to BoxeR — same justification: heavy C/C++ thread pool + crash isolation.
- Forbid `torch.set_num_threads()` outside the subprocess. Add a lint rule or `_thread_config.py` guard.

**Warning signs:**
- Frame-rate in the MuJoCo viewer halves when detector is enabled.
- `htop` shows torch/oneDNN threads pinned at 100% while the robot controller loop reports `loop_ms` spikes.
- A second detector backend import mysteriously changes SLAM timing.

**Phase to address:** Phase 1 — research-driven backend shortlist (budget thread count after backend choice is locked); Phase 2 — Detector API (subprocess bridge reuse); Phase 3 — BoxeR backend (actual thread config).

---

### Pitfall 3: RGB-D 3D Center Uses Camera-Optical Convention, SLAM Cloud Uses World Convention — Silent Off-Axis Drift

**What goes wrong:**
The current 3D projection code exists in TWO places with TWO different sign conventions:
- `src/perception/detector.py:224-236` hard-codes `fov_rad = 70°` and flips Y and Z (`cam_pt = np.array([cam_x, -cam_y, -d])`) with comment "Apply same Y/Z flip as SLAM cloud (config 1: Y- Z-)". The pose is applied as `pose[:3,:3] @ cam_pt + pose[:3,3]` — the pose matrix is assumed to already be in world frame with no transpose.
- `src/perception/detection_3d.py:64-78` uses `CameraIntrinsics` (real fx/fy/cx/cy), reads the sign flip from `CLOUD_CONFIGS[get_active_config()]`, and even has a `cfg["sx"]` path that is referenced but not defined consistently in the first branch (the ternary `cfg["fy"] * cam_x if cfg.get("sx") is not None else cam_x` is structurally suspicious).

These two paths diverge: different FoV assumption (70° hardcoded vs. intrinsics), different sign-flip source (hardcoded vs. config), different guards against invalid bbox (20px filter vs. none). When v3.0 adds the 3D OBB backend, the third 3D path will almost certainly copy from one of these and inherit whichever is wrong.

**Why it happens:**
v1 grew `detector.py` as a self-contained module; v1.5 added `detection_3d.py` as a separate utility without retiring the inline path; nobody enforced a single projection pipeline. In v3.0, oriented 3D box regression is strictly harder (now 6-DOF orientation on top of a 3D center) — copy-pasting either of these broken paths bakes in drift that is orientation-dependent and hard to spot visually (a chair 20cm off is obvious; a chair rotated 12° in yaw looks plausible).

**How to avoid:**
- Consolidate to a single `src/perception/geometry.py` with ONE function `unproject_pixel_to_world(u, v, depth, intrinsics, T_world_cam) -> np.ndarray` and ONE function `unproject_obb_to_world(center2d, size2d, orientation, depth_map, intrinsics, T_world_cam) -> OrientedBBox3D`. Delete the duplicate paths in `detector.py` and `detection_3d.py`.
- Remove the 70° hardcoded FoV. Always read `CameraIntrinsics` from the sensor frame. If MuJoCo doesn't publish it already, add it once.
- Define `CameraFrame` convention explicitly: OpenCV optical (X-right, Y-down, Z-forward). Document that `T_world_cam` in `SensorFrame` is world-from-optical. Write ONE conversion test: "a pixel at principal point, depth=1m, identity pose → world point `(0, 0, 1)` in optical, and world `(X_world, Y_world, Z_world)` after applying the MuJoCo convention transform."
- The `CLOUD_CONFIGS` legacy sign-flip hack from v1 is a smell. Bake the chosen convention into the MuJoCo bridge once and delete `CLOUD_CONFIGS` as v3.0 exits. Carry it as tech debt during migration; do not extend it.
- Add a `test_geometry_agrees_with_slam_cloud` that compares the projected 3D center against the nearest point in the SLAM global cloud for the same pixel; if they disagree by >depth*0.02m, fail.

**Warning signs:**
- Detections labels float ABOVE or BESIDE the actual object in the Three.js viewer (consistent direction → sign flip; random direction → noise).
- 3D boxes look right for robot 1 and wrong for robot 2 (different camera extrinsics exposing the convention bug).
- 3D center moves when you change MuJoCo FoV without any code change.

**Phase to address:** Phase 2 — Detector API (MUST define the single geometry module before BoxeR integration); Phase 4 — 3D OBB regression (consumes the unified geometry).

---

### Pitfall 4: 3D OBB Regression from RGB-D — Median Depth Is Wrong for the Whole Object

**What goes wrong:**
Current code uses median depth inside the 2D bbox as THE depth for the detection (`detector.py:219`, `detection_3d.py:58`). For a 2D center this is a defensible robust estimator. For a **3D oriented box** it is actively wrong:
- A chair viewed from 45° has depths ranging 0.8m (front leg) to 1.4m (back rest). The median gives ~1.1m, which is neither the near face nor the centroid.
- A table viewed obliquely has depths varying linearly across the bbox — the median is the CENTER pixel's depth, not the geometric centroid of the object surface.
- Glass/transparent objects (common in office scenes, including MuJoCo's sample "office" scene which has windows) return MuJoCo's background depth through them — a cluster of "sky-depth" pixels median-blends with "near chair" pixels and gives a fictitious intermediate depth.
- Objects that cross the frustum edge have HALF their depth pixels clipped — median snaps to one side of the object, not the center.
- Sky/void pixels in the 0-clip path (`roi > 0.1 & roi < 10.0` at `detection_3d.py:53`) are filtered, but MuJoCo sky is depth ≈ `z_far` (often valid-looking). A `< 10.0` filter is scene-specific.

**Why it happens:**
Median depth is the textbook trick for "2D to 3D projection" and works on centered objects at moderate range. Teams carry the trick forward to 3D box regression because it's already in the codebase. The 2D→3D failure is tolerable (error on one axis); the 2D→3D-OBB failure is not (error propagates through orientation estimation because the depth plane is fit to wrong points).

**How to avoid:**
- For a 3D center, replace median-of-bbox with: (a) filter the bbox ROI to depths within `median ± 2σ` (MAD-based), (b) cluster the remaining points in 3D (DBSCAN with eps = 0.05m or pointwise within `depth_std * 3`), (c) take the **largest cluster** centroid. This rejects sky-through-glass and neighboring objects.
- For a 3D OBB, do NOT regress from a single depth scalar. Either:
  - **Approach A (geometric):** Back-project ALL bbox pixels to a 3D point set, cluster, fit an OBB via PCA on the dominant cluster (axes = eigenvectors of covariance, size = 2x std along each axis, or min-volume rectangle on the top-down projection for yaw-only OBBs which is the sane default for indoor objects on the floor).
  - **Approach B (model-predicted):** Use a backbone that predicts 3D OBB directly (Cube R-CNN, OmniDet, MonoCon) — but on CPU these have their own cost. Verify Context7 / official docs for CPU viability before committing.
- For MVP, **yaw-only OBBs** are sufficient (most indoor furniture has its other axes aligned to gravity). Do not regress roll/pitch until there's a concrete user-visible reason.
- Define a per-class depth validity mask: "chair → reject depth > 6m, reject depth < 0.3m"; "potted plant → reject depth > 4m". Put this in the class config, not the projection function.

**Warning signs:**
- OBB extent along the depth axis is larger than typical object size (>2m for a chair) — telltale sign of sky pixels leaking in.
- OBB orientation flips 90° when the camera moves — telltale sign of PCA on too few points or near-circular footprint.
- 3D box is in front of / behind the point cloud of the same object in the viewer.

**Phase to address:** Phase 4 — 3D OBB regression (primary); Phase 5 — metrics & per-class eval (validation).

---

### Pitfall 5: OBB Orientation Sign/Parameterization Drift Across Python, Wire, and Three.js

**What goes wrong:**
An oriented bounding box has 3 natural parameterizations:
1. **3x3 rotation matrix** (9 floats, but only 3 DOF — must be orthonormal).
2. **Quaternion** (4 floats — MUST be unit; has sign ambiguity: `q` and `-q` encode the same rotation).
3. **Euler angles** (3 floats — MUST specify convention: XYZ intrinsic, ZYX extrinsic, roll-pitch-yaw, etc.).

Each tool in the stack has its own favorite: Open3D uses 3x3 + center + extent. SciPy uses quaternion `(x, y, z, w)`. Three.js uses quaternion `(x, y, z, w)` OR Euler with a settable order. scipy.spatial.transform.Rotation can emit either but uses `(x, y, z, w)` — this is the opposite of ROS `(w, x, y, z)`. When any two of these disagree on convention, boxes render rotated 180° around a random axis.

Additionally: wire serialization through `detections` WS payload today uses `bbox: [x1, y1, x2, y2]` plus `pos_3d: [x, y, z]` (see `detection_3d.py:80`). v3.0 adds `orientation` — if the first backend writes Euler and the second writes quaternion, the frontend is forever forked.

**Why it happens:**
Every library documents "pose" or "orientation" without qualifying the convention. Three.js's `Quaternion` constructor is `(x, y, z, w)`, ROS's `geometry_msgs/Quaternion` is `(x, y, z, w)` in wire order but `(w, x, y, z)` in message-constructor order in many bindings. Developers test in one coordinate frame and ship.

**How to avoid:**
- **One wire format, one time, documented:** `orientation: [qx, qy, qz, qw]` (scipy/Three.js order) in world frame, unit quaternion, positive hemisphere (`qw >= 0`). Center is `[cx, cy, cz]` meters world. Size is `[sx, sy, sz]` meters along LOCAL axes (pre-rotation).
- Write a `OrientedBBox3D` dataclass with `from_matrix / to_matrix / from_euler / to_euler` that is the ONLY path to produce a wire payload. Forbid inline quaternion construction in backends.
- Add a round-trip test: `obb == OrientedBBox3D.from_wire(obb.to_wire())` to ±1e-6.
- Frontend: wrap Three.js `Quaternion.fromArray([qx, qy, qz, qw])` in one utility, `wireOBBToMesh`. Forbid any other conversion.
- Canonicalize: force `qw >= 0` on serialize. Makes diffs readable and avoids the "same box, different numbers" confusion when debugging.

**Warning signs:**
- Box is rotated ~180° from the object in Three.js when the backend is changed.
- `q` sign flips every frame (visible in WS payload inspection) — sign canonicalization missing.
- TypeScript port type accepts `number[]` without length constraint — should be `[number, number, number, number]` tuple.

**Phase to address:** Phase 4 — 3D OBB regression (dataclass + wire spec); Phase 5 — transport layer (TypeScript tuple types + round-trip test).

---

### Pitfall 6: Eval.Mode Forgotten → Gradients Tracked → CPU RAM Blowup, 10x Slowdown

**What goes wrong:**
Standard HuggingFace example code constructs a model, loads weights, and calls `model(**inputs)`. Nothing in that path disables gradient tracking. On CPU this costs 2-3x steady-state time and, more importantly, leaks activation tensors (every intermediate attention map retained for backprop). With a 2-FPS detector running for 5 minutes, tensor allocator fragmentation causes RSS to climb to 6-8GB for a model that should sit at ~1.5GB. Eventually the coordinator process (not the detector subprocess!) gets OOM-killed because it shares the python arena on Linux without hard isolation.

Additionally: forgetting `model.eval()` means BatchNorm (in ResNet/ResNet-backbone DETR) and Dropout run in train mode, giving subtly different outputs per call — the detector appears non-deterministic.

**Why it happens:**
PyTorch defaults favor training ergonomics. `requires_grad=True` is the default on loaded weights. `model.train()` is the default state. HuggingFace examples frequently omit `.eval()` and `torch.no_grad()` because the upstream examples target fine-tuning workflows.

**How to avoid:**
- Every detector backend's `__init__` MUST call `self._model.eval()` and freeze: `for p in self._model.parameters(): p.requires_grad_(False)`.
- Every `_detect()` MUST be wrapped in `with torch.inference_mode():` (stronger than `torch.no_grad()` — disables view tracking too, ~5-15% faster on CPU).
- Pin dtype: `self._model.to(torch.float32)` or explicitly `.to(torch.bfloat16)` if the backend supports CPU bfloat16 (newer torch). Never leave dtype implicit.
- Add a smoke test: run 100 inferences, assert final RSS < initial RSS + 200MB.
- Use `psutil` to log RSS into metrics every 10s; if it grows monotonically for 60s, fail with a loud warning.

**Warning signs:**
- Process RSS grows linearly with detection count.
- First 10 frames take 500ms each; frames 1000+ take 1500ms each.
- Two consecutive calls on the same image produce different box counts/scores.

**Phase to address:** Phase 3 — BoxeR / HuggingFace backend integration; Phase 5 — metrics (memory tracking).

---

### Pitfall 7: Tokenizer/Processor Version Drift — "Works on My Machine" on CPU-Only Rigs

**What goes wrong:**
Open-vocabulary detectors (Grounding DINO, OWL-ViT) require a text tokenizer; DETR-family (BoxeR) requires an image processor. HuggingFace loads these via `AutoProcessor.from_pretrained(model_id)` which snaps to the **latest** processor config compatible with the installed `transformers` version. When `transformers` updates (e.g., 4.40 → 4.45), a processor that used to emit `pixel_values` dtype=float32 starts emitting float16, or a tokenizer starts producing `attention_mask` when it didn't before, or the `size` parameter changes from scalar to dict `{shortest_edge, longest_edge}`. The model signature silently drifts and accuracy collapses without an error.

**Why it happens:**
HuggingFace ships fast iterations. Pinning `transformers==X.Y.Z` often conflicts with `ultralytics` (which pins torch), `torch` itself, and `accelerate`. Teams upgrade one, another breaks.

**How to avoid:**
- Pin `transformers`, `tokenizers`, `safetensors`, and the model checkpoint's `revision=` hash in `requirements.txt` / `pyproject.toml`. Use `revision="<commit-sha>"` when loading, not a tag, not `main`.
- Ship `tests/perception/test_backend_<name>_regression.py`: feed 3 fixed images (committed to `tests/fixtures/`), assert bboxes within IoU 0.95 of recorded outputs. Runs in CI and in pre-commit. If `transformers` is bumped and this test moves by >5%, require an explicit recorded-baseline update.
- Document (in docstring + `STACK.md`) the exact `(transformers_version, model_id, model_revision)` tuple for each backend.
- For BoxeR specifically — verify with Context7 the current `facebook/boxer-*` repo structure (some facebook models get renamed/moved — confirm at integration time, not from memory).

**Warning signs:**
- CI passes today, fails on a dependabot/renovate bump with no code change.
- Detector outputs "no detections" on a scene where YOLO finds 5 objects.
- HuggingFace Hub issues a deprecation warning on processor load (read them).

**Phase to address:** Phase 1 — research + backend selection (verify what's actually current via Context7 at research time); Phase 3 — BoxeR backend (lock revision); Phase 7 — stability testing.

---

### Pitfall 8: Detector-Slower-Than-Producer Backpressure Loses Synchronization to Robot Pose

**What goes wrong:**
Current `submit_frame()` (detector.py:119-131) stores ONLY the latest frame per robot. When detector is 0.5 FPS and simulation produces frames at 30 FPS, every submitted frame overwrites 59 unprocessed ones. When detection finally completes, it uses the pose captured at submission time — but the simulation has moved 2 seconds forward. If the pose stored in `_pending_frames` is the pose AT submission (currently it is — `pose` is captured into the tuple), the detection is correctly aligned to old pose. BUT: the downstream consumer (Coordinator merging detection into the map) reads `self._results[robot_id]` (no pose stored in `RobotDetections`!) and uses the CURRENT robot pose to place the detection. This is the 2-second-stale-pose bug.

In v3.0 with BoxeR at 0.5 FPS on CPU and MuJoCo at 30Hz, this drift ≈ robot speed * 2s ≈ 0.4m — bigger than the 3D box itself. Detections land in the wrong voxel, wrong room, through walls.

**Why it happens:**
`Detection.center_3d` (detector.py:40) is computed inside `_detect()` at submission-time pose, so it's correct in isolation. But the 2D `bbox` is ALSO published, and anything that re-projects or associates it against current pose (new in v3.0: the pipeline editor node, multi-robot OBB merge) will implicitly read current pose. The current code gets away with this because it only uses the 3D center, precomputed.

**How to avoid:**
- Attach a `capture_timestamp` (MuJoCo sim time) and a `capture_pose` (4x4) to EVERY `Detection` and the enclosing `RobotDetections`. Publish these on the wire.
- Downstream consumers MUST use `capture_pose`, not "current robot pose." Any code doing `coordinator.robot_pose(robot_id)` to re-project a detection is a bug.
- Define a "detection freshness" metric: `sim_now - capture_timestamp`. Surface it in `MetricsPanel`. Over some threshold (e.g., 1.0s), flag it red — indicates detector is falling behind.
- For pipeline-editor stages downstream of the detector: pass the entire `(detection, capture_pose, capture_timestamp, intrinsics)` bundle along the edge, not a bare detection. Encode this in the port type.
- If the detector falls further behind over time (queue-less latest-wins but latency creeps up as a thread backs up), add a hard watchdog: if `_detect()` exceeds `3 * 1/max_fps`, log and reset the thread.

**Warning signs:**
- 3D box labels appear at the position the robot WAS, not where it IS — classic signature.
- Boxes pile up in "hallway" voxels even though no objects are there, because that's where the robot crossed through while BoxeR was running.
- Detection freshness metric grows monotonically.

**Phase to address:** Phase 2 — Detector API (add `capture_pose` + `capture_timestamp` to protocol result); Phase 4 — 3D OBB consumers use capture_pose; Phase 6 — pipeline editor port type encodes pose+time bundle.

---

### Pitfall 9: Registry Circular Import Blows Up at `main.py` Startup

**What goes wrong:**
The v2.0 `SLAMRegistry` pattern (`src/slam/registry.py` + decorator-based registration) works because backends are imported once at startup and the registry is a simple dict. Repeating this for detectors with the current shape risks two new cycles:

1. `detector_registry` imports backends → backends import `Detection` dataclass from `detector.py` → `detector.py` (the EXISTING file) imports `ultralytics` at module scope → registry now fails on systems without ultralytics, even if the user selected BoxeR.

2. Pipeline editor node catalog imports detector registry to populate node types; detector registry imports `SensorFrame`; `SensorFrame` lives in `src/bridge/sensor_types.py`; bridge imports something from `coordination`; coordination imports the pipeline builder. This is the v2.0 shape that ALREADY exists, and adding detector registration at the wrong layer closes the cycle.

**Why it happens:**
The existing `detector.py` conflates (a) the `Detection` dataclass, (b) the YOLO-specific detector, and (c) the module-level `ultralytics` import. When the registry pattern is overlaid, every backend pulls in this file as an entry point.

**How to avoid:**
- **Move the dataclasses first.** Create `src/perception/types.py` with `Detection`, `RobotDetections`, `OrientedBBox3D`, `DetectorResult`, `TrackingStatus`-equivalent. Zero third-party imports; numpy only.
- **Protocol second.** `src/perception/protocol.py` with `DetectorProtocol`, `DETECTOR_CAPABILITIES`, `PARAMETER_SCHEMA`. Imports only from `types.py` and `bridge/sensor_types.py`.
- **Registry third.** `src/perception/registry.py` with a decorator and a dict. Imports protocol + types ONLY.
- **Backends fourth.** Each backend is in `src/perception/backends/<name>_backend.py`. Module-level imports of heavy deps (ultralytics, transformers, torch) are wrapped in `try/except ImportError` with an `AVAILABLE` flag — the v2.0 pattern from SLAM.
- **Backend registration is explicit, not decorator-at-module-import.** Provide `register_builtin_backends()` called from `main.py` after config loads — this is the v2.0 lesson learned, avoids the import-order trap.
- Add `test_registry_no_heavy_imports`: `import src.perception.registry` must not import torch, transformers, or ultralytics. Verify with `sys.modules` introspection.

**Warning signs:**
- `import src.perception` takes >500ms (torch is being imported eagerly).
- Removing `ultralytics` from venv breaks import of the registry even when BoxeR is selected.
- `pytest` on a single unrelated test triggers a model download.

**Phase to address:** Phase 2 — Detector API + Registry (bake this layout from the start; don't grow organically).

---

### Pitfall 10: "One Model, N Robots" vs. "N Models" — GIL Serialization Kills Throughput

**What goes wrong:**
Two defensible designs:
- **Shared:** one `ObjectDetector` instance across robots (current design), submits are queued.
- **Per-robot:** one detector PER robot.

Current code is shared-but-single-threaded — `_run_loop()` iterates robots sequentially (detector.py:156-164), so 2 robots at 2 FPS budget means each robot gets 1 FPS. On a transformer backend at 0.5 FPS total, each robot gets 0.25 FPS.

Naive fix: spawn N detector threads. Doesn't help on CPU-only: torch/oneDNN is not GIL-bound BUT it's bottlenecked on compute, not concurrency. Two threads each calling `model(...)` at 0.5 FPS share the oneDNN thread pool and both run at ~0.25 FPS. No throughput gain; only added overhead.

Naive fix 2: load N copies of the model. 1 model × 1.5GB × 4 robots = 6GB RSS, blows past the CPU-only RAM budget.

**Why it happens:**
Python threading looks like concurrency but the CPU-bound model is globally serialized by the compute units, not the GIL.

**How to avoid:**
- **Shared detector, round-robin queue is the right default.** Budget the aggregate FPS across all robots: `per_robot_fps = total_fps / N_robots`. Document this in `STACK.md`.
- For N>3 or where per-robot latency matters, move the detector into ONE subprocess that batches frames across robots in a single forward pass. Transformer detectors accept `batch_size=N` natively. Batched inference at batch=N is typically 1.3-1.6x the cost of batch=1 on CPU — a big win over sequential single-image passes.
- Do NOT multiply models across robots; multiply via batching.
- Surface per-robot latency + per-robot queue depth in metrics. If queue depth >3 for any robot, the shared-detector model is saturating and users should either reduce `max_fps` or reduce detector complexity.

**Warning signs:**
- Detector FPS doesn't scale when you reduce the robot count.
- RSS jumps linearly with robot count — someone instantiated per-robot models.
- Robot B's detections are 2x more stale than robot A's (latest-wins queue is not fair across robots).

**Phase to address:** Phase 3 — BoxeR backend (measure batched vs. sequential); Phase 5 — metrics (queue depth per robot).

---

## Moderate Pitfalls

### Pitfall 11: MuJoCo Has No Detection Ground Truth — Fake mAP Is Worse Than No mAP

**What goes wrong:**
Temptation: report `mAP` on the Metrics panel to "measure detector quality." MuJoCo scenes have no COCO-labeled ground truth — you'd compute mAP against pseudo-labels derived from... the same detector. This is circular and gives meaningless 100% scores.

Real metrics possible in sim without labels: object permanence (same chair detected across frames → count vs. noise), 3D consistency (3D box location stable within ±0.1m as the robot moves), detection-to-SLAM-cloud association (box contains points of the expected extent), per-class count against known scene contents (if the scene has 4 chairs and detector reports 40, something is broken).

**Why it happens:**
"mAP" is the standard metric in detection papers. The panel needs a number. Teams wire up `torchmetrics.MeanAveragePrecision` against weak pseudo-labels.

**How to avoid:**
- Report the honest metrics: `detections_per_sec`, `confidence_mean`, `confidence_std`, `unique_class_count`, `3d_center_jitter_m` (stddev of a persistent object's detected 3D center across 30 frames).
- If scenes need ground truth, extract it from MuJoCo: query the body positions of known furniture XML bodies (MuJoCo `mj_name2id` + `data.xpos`). This gives 3D center ground truth for free. Compute `center_error_m` = L2 distance between detected 3D center and known body position.
- For OBB orientation eval, compute yaw error against MuJoCo body quat. This IS computable in sim — do it.
- Forbid "mAP" in the UI unless a labeled eval set is committed alongside the scene.

**Warning signs:**
- "mAP: 100%" displayed.
- Metric doesn't change when you make the detector worse on purpose.
- The metric's upstream computation pulls labels from the detector itself.

**Phase to address:** Phase 5 — eval & metrics (ground truth extractor from MuJoCo scene XML).

---

### Pitfall 12: No Frame-to-Frame Association → Every Frame Is a New Object

**What goes wrong:**
Detector publishes detections per frame, no identity. The Three.js layer adds a new 3D box mesh for every frame's detections. A chair detected 100 times becomes 100 overlapping boxes, each slightly different. Visually a "flicker." Memory-wise, slow leak. Metrically, "unique class count = 4000" instead of 4.

**Why it happens:**
v2 SLAM has a similar concept (keyframes + pose graph) but detection doesn't. Adding association is a whole sub-problem (tracker — ByteTrack, SORT, IoU-greedy).

**How to avoid:**
- For v3.0 MVP, a cheap per-robot 3D association is sufficient: if a new detection's 3D center is within 0.3m of a previous detection of the same class within the last 2 seconds, treat as the same track. Assign a stable `track_id`.
- Publish `track_id` in the wire payload. Frontend indexes Three.js meshes by `track_id` — updates in place instead of creating new.
- For v3.0, don't ship a full Kalman tracker. Rolling IoU-3D + class-match is enough and doesn't drift like IoU-2D does under camera motion.
- Track freshness: if a `track_id` hasn't been confirmed in 5 seconds, the frontend removes its mesh.

**Warning signs:**
- Three.js scene has thousands of OBB meshes after 30 seconds.
- FPS in the viewer drops over time even though the scene is stable.
- Detection count metric climbs monotonically.

**Phase to address:** Phase 4 — 3D OBB regression (cheap 3D IoU tracker); Phase 6 — frontend mesh lifecycle.

---

### Pitfall 13: WebSocket Payload at 10Hz with JSON Floats Blows the Wire Budget

**What goes wrong:**
Each OBB = center(3) + size(3) + orientation(4) + bbox2d(4) + score(1) + class(str) + track_id(int) + robot_id(str) + pose(16) + timestamp(1). JSON-serialized with default float precision, ~400 bytes/detection. At 20 detections/frame × N=2 robots × 10 Hz = 160KB/s. Doable but painful, and the browser's JSON.parse + React re-render under Zustand at 10Hz adds frame drops on lower-end laptops.

v2.0 already has a `stats` WS stream + SLAM cloud stream; adding a 10Hz detection stream on top without care blows the main-loop budget.

**Why it happens:**
Default `json.dumps(dict, ...)` does not strip precision. Float64 `0.3` serializes to `"0.30000000000000004"` (17 chars) instead of `0.3` (3 chars) when numpy values leak.

**How to avoid:**
- Round before serialize: center to 3 decimal places (mm), size to 3, orientation to 4 (quaternion components rarely need more), score to 3.
- Send detections at 2-5 Hz, not 10 Hz — they're detector-limited anyway. Match the detector's actual rate; don't poll faster.
- Use the existing WS framing (v2.0 has `stats` / `slam_metrics` / etc.) — add one message type `detections` with `{robot_id, timestamp, detections: [...]}` at detector rate.
- If payload grows: move to binary (msgpack — already used in v2.0 for ZMQ subprocess bridge; reuse). Floats become 8 bytes each. 10x smaller. Document the switch trigger in `ARCHITECTURE.md`.
- Frontend: use Zustand's shallow equality + a separate store slice for detections so React doesn't re-render unrelated panels.

**Warning signs:**
- Browser devtools Network tab shows >100KB/s on the WS.
- React Profiler shows `MetricsPanel` or `ViewerCanvas` re-rendering on every detection update.
- Backpressure: `send_json` latency >50ms.

**Phase to address:** Phase 5 — transport layer (WS message type + rate limit); Phase 7 — performance tuning if payload grows.

---

### Pitfall 14: Three.js OBB Disposal — GPU Buffer Leak on Mesh Replacement

**What goes wrong:**
Every frame, the "detections" layer clears old OBB meshes and creates new ones (naive React-in-Three.js pattern). Three.js does NOT garbage-collect `BufferGeometry` and `Material` — they live on the GPU until explicitly `.dispose()`-d. After 5 minutes of 10Hz updates: GPU memory exhausted, tab crashes, or (on integrated GPUs) the entire browser slows down because WebGL falls back to software.

The v2.0 `VoxelManager` (Three.js `InstancedMesh`) already handles this correctly. Detection OBBs need the same pattern.

**Why it happens:**
React's reconciliation disposes JSX elements but not their WebGL resources. `react-three-fiber` disposes reasonably, but only if the mesh was declared declaratively — imperative `scene.add(mesh)` leaks.

**How to avoid:**
- Use `InstancedMesh` for OBBs: one mesh, N instances, updated by matrix per track. Max instance count = expected tracks (~100 is generous). Update matrices per frame via `.setMatrixAt(i, matrix4); instancedMesh.instanceMatrix.needsUpdate = true`.
- Wrap in a v2.0-style manager class: `OBBManager` with `update(detectionsByTrackId)` method. Mirror `VoxelManager` structure.
- On unmount: explicit `geometry.dispose()`, `material.dispose()`. Add a `useEffect` cleanup.
- Labels (billboarded text) are a separate leak vector: use `troika-three-text` which handles disposal, or a 2D overlay layer with CSS `position: absolute` + world-to-screen projection (cheaper, no GPU text leaks, and scales better with label count).
- Add a dev-mode memory counter: `renderer.info.memory.geometries` printed every 10s. If it grows monotonically, there's a leak.

**Warning signs:**
- Browser tab RAM climbs for a static scene.
- `renderer.info.memory.geometries` keeps growing.
- Labels rendered with `TextGeometry` (expensive) instead of canvas/SDF text.

**Phase to address:** Phase 6 — frontend integration (OBBManager mirrors VoxelManager).

---

### Pitfall 15: React Flow Port Type for OBB-Carrying Edge Confuses the Pipeline Validator

**What goes wrong:**
v2.0's pipeline editor has 7 port data types (per `PROJECT.md` and `pipelineStore.ts`). v3.0 adds new node types: `DetectorNode` (RGB+Depth → Detections2D), `OBBRegressor` (Detections2D + Depth + Pose → OBBs3D). If the new port types are added ad-hoc (e.g., string literal `"detections_2d"` sprinkled across the TypeScript), Kahn's-algorithm validator (mentioned in the v2.0 milestone accomplishments) will accept invalid pipelines because it can't distinguish "bbox list with class id" from "bbox list with class name."

**Why it happens:**
Port types grow from 7 to 9 without a centralized definition. The TypeScript enum and the Python schema drift.

**How to avoid:**
- Single source of truth for port types. Either: (a) Python Pydantic models auto-generate TypeScript via `datamodel-code-generator`, or (b) hand-maintained `src/pipeline/port_types.py` + `frontend/src/pipeline/portTypes.ts` with an integration test that asserts equality.
- New v3.0 port types: `Detections2D` (list of 2D bboxes + scores + classes), `DetectionsWithPose` (adds capture_pose + timestamp), `OBBs3D` (list of OrientedBBox3D), `DetectorConfig` (model name + params). Name them, register them, stop.
- The validator should reject `DetectorConfig` connected to `Depth` (type mismatch). Test this.
- `NodeCatalog` categorization: add "Perception" category. Don't hide detection under "SLAM" or "Processing."

**Warning signs:**
- A new node type requires 3+ TypeScript file edits (enum, catalog, validator, renderer). Centralize instead.
- A pipeline validates but crashes at runtime because a node got the wrong input shape.
- String-literal port types in code review.

**Phase to address:** Phase 6 — pipeline editor nodes (add Perception category + port types before node implementations).

---

### Pitfall 16: Yank the YOLO Path Too Early → No Working Baseline During BoxeR Debugging

**What goes wrong:**
Eager refactor deletes the existing `ObjectDetector` (v1 YOLO) the moment the new `DetectorProtocol` is in place. BoxeR has a 3-day integration bug (Pitfall 1/2/6/7 surface in sequence). During those 3 days nobody can demo, test, or benchmark. The merge window slips.

This is the same lesson as v2.0 Pitfall 5 (don't break ICP during abstraction). Restate for v3.0: the working YOLO path is the only known-good detector. Preserve it.

**Why it happens:**
"Clean refactor" aesthetic, plus PR hygiene (big refactor + remove-old-code in one diff looks cleaner).

**How to avoid:**
- Step 1: Introduce `DetectorProtocol`. Wrap existing YOLO as `YOLODetectorBackend` literally delegating to the existing `ObjectDetector` class. Do NOT touch `ObjectDetector` itself.
- Step 2: Add BoxeR backend alongside. Toggle via config/UI.
- Step 3: Run both in CI on fixtures. Metrics side-by-side.
- Step 4: Only after BoxeR is green for a full day in real runs, consider if removing YOLO makes sense. Answer: probably not — YOLO is a valuable low-resource fallback. Keep both.
- Same as v2.0: `icp_backend.py` wrapped the existing SLAMPipeline rather than rewriting. Repeat this recipe.
- UI picker shows BOTH backends with capability badges. Default stays YOLO until BoxeR passes acceptance.

**Warning signs:**
- PR deletes `src/perception/detector.py` in the same commit as adding BoxeR.
- Nobody can demo during the BoxeR integration week.
- "Revert the whole branch" is the only recovery option after a bug.

**Phase to address:** Phase 2 — Detector API (wrap YOLO as the first backend, don't rewrite); Phase 3 — BoxeR backend (additive).

---

### Pitfall 17: Multi-Robot Detection Payload — robot_id Off-by-One / String vs. Int

**What goes wrong:**
v1.0/v2.0 codebase uses `robot_id` as string (`"robot_a"`, `"robot_b"` per detector.py:60 example). Pipeline editor nodes might pass robot index as int. When a detection with `robot_id: "robot_a"` arrives at a pipeline node expecting int `0`, the routing silently fails or associates detections to the wrong robot.

In `get_all_detections()` (detector.py:139) the dict is keyed by string. In frontend `robotStore.ts`, robots may be indexed by array position. In WS `stats` payload they're keyed by string. The three MUST agree.

**Why it happens:**
No formal type for `RobotId`. Each layer picks a representation.

**How to avoid:**
- `RobotId = NewType("RobotId", str)` in Python. `type RobotId = string` in TS. Pydantic model in the wire payload.
- All detection payloads use string ID. Pipeline nodes receive string. Frontend stores map `Record<RobotId, ...>`.
- Integration test: submit detection for `robot_a`, assert it appears in `robotStore.robots["robot_a"].detections`, not `[0]`.
- Defensive runtime check: on WS receipt, if `robot_id` isn't in `robotStore.robots`, log and drop (not silently ignore).

**Warning signs:**
- Robot A's chair detection appears on Robot B's camera feed overlay.
- Detections "vanish" when N_robots changes.
- `TypeError: string indices must be integers` in pipeline execution.

**Phase to address:** Phase 2 — Detector API (formalize `RobotId` type); Phase 5 — transport (Pydantic wire types).

---

### Pitfall 18: Restart-Overlay Flow Doesn't Cover Mid-Session Model Unload

**What goes wrong:**
v2.0 added a `RestartOverlay` component (see v2.0 MILESTONES.md). It's tied to SLAM backend switching. For detectors, pre-session selection works for YOLO↔BoxeR (restart the whole detection subprocess). BUT a subtler case: the user changes BoxeR's `confidence_threshold` param (live, via debounced WS like v2.0 SLAM params). No restart needed. But if the user changes the `model_variant` param (`boxer-resnet50` → `boxer-swin`), a weight reload IS needed — not a full subprocess restart, but not "live" either. There's no v2.0 precedent for "mid-backend-config-change that needs a warmup but not a restart."

**Why it happens:**
SLAM parameters are mostly numeric thresholds → schema-driven sliders work. Detector parameters include model selection → needs different UX.

**How to avoid:**
- Classify each parameter in the schema: `live` (no reload, debounced send), `reload` (triggers `backend.reload(new_params)` on the server which keeps the subprocess alive but re-instantiates the model; triggers a smaller "reloading model..." overlay with spinner, not a full restart overlay), `restart` (requires subprocess restart, triggers full v2.0 restart flow).
- Add a `reload(new_params)` method to the detector protocol that may or may not be supported (`CAPABILITIES["supports_reload"]`).
- Frontend: parameter inspector reads the classification and shows appropriate UX. A `reload` param click shows a `ConfirmModal` because reloads are disruptive.
- During reload, the detector publishes a `detector_status: "reloading"` WS event so the frontend can dim detection overlays.

**Warning signs:**
- User changes confidence and the whole subprocess restarts.
- User changes model variant and nothing happens (silent failure to reload).
- Detections from the OLD model appear AFTER a model variant change.

**Phase to address:** Phase 6 — frontend UX (parameter classification + reload flow).

---

## Minor Pitfalls

### Pitfall 19: `torch.set_num_threads(2)` at Module Scope Poisons All Importers

**What goes wrong:**
`src/perception/detector.py:25` sets thread count at import time. Any code that imports this file (tests, CLI tools, the pipeline editor that wants to list available detectors) inherits the global setting. A benchmark script that wants 8 threads silently gets 2.

**How to avoid:**
Move thread config into the detector's constructor, not module scope. Or, as per Pitfall 2, move it into `_thread_config.py` set once at process start with explicit budgets.

**Phase to address:** Phase 2 — Detector API (clean module scope).

---

### Pitfall 20: HuggingFace Hub Download on First Run in CI/Sandbox

**What goes wrong:**
First CI run hits `huggingface.co` to fetch model weights. If the CI sandbox is network-restricted (common), it fails with a cryptic `ConnectionError` buried inside `_load_from_pretrained`.

**How to avoid:**
- Commit a `models/` directory (gitignored) + a `scripts/fetch_models.py` that's run once in setup. CI runs the script in a non-restricted step, caches the result.
- Use `local_files_only=True` after the first load. Model load errors become informative: "run `make download-models` first."
- For tiny integration tests, use an `auto`-style mock or a tiny surrogate model (e.g., `hf-internal-testing/tiny-detr`) so tests run offline.

**Phase to address:** Phase 3 — BoxeR backend (offline-capable loader); Phase 7 — CI.

---

### Pitfall 21: FOV Hardcoded to 70° in Projection Code

**What goes wrong:**
`detector.py:225` hardcodes `fov_rad = math.radians(70.0)`. MuJoCo scenes may configure different FoVs. When the scene FoV is 60° and the projector thinks 70°, 3D positions are scaled by `tan(30)/tan(35) ≈ 0.82` — every position is 18% too close on X/Y.

**How to avoid:** Read `CameraIntrinsics` from `SensorFrame`. Delete the hardcode. Covered by Pitfall 3 consolidation.

**Phase to address:** Phase 2/4 (geometry consolidation).

---

### Pitfall 22: `INDOOR_CLASSES` Filter Hides Real Misses

**What goes wrong:**
`detector.py:64-72` filters detections to a hardcoded COCO class subset. A user adds a new object to the scene (e.g., a "dog" at class 16) — detector finds it but the filter drops it. User reports "detector can't find the dog"; the real issue is the filter.

**How to avoid:**
- Move class filter to a runtime parameter, not a class constant.
- Surface "classes considered" in the parameter panel (multi-select).
- Log at DEBUG: "filtered {n_raw - n_kept} detections by class filter."
- BoxeR / Grounding DINO / OWL-ViT use different class sets (BoxeR is COCO; Grounding DINO is open-vocabulary by prompt). The class filter concept is backend-specific — put it in the backend adapter, not the generic protocol.

**Phase to address:** Phase 2 — Detector API (class set per backend, not global).

---

### Pitfall 23: 10Hz Metrics Flood on `confidence_stats`

**What goes wrong:**
MetricsPanel at 10Hz with per-class confidence stats (mean, std, min, max, percentiles × 80 classes × 2 robots) produces a wire payload larger than the detections themselves.

**How to avoid:**
- Roll up to aggregate stats: `{mean_conf, std_conf, n_detections, top3_classes}`. Detail on demand via REST.
- Metric history (v2.0 pattern: `metric_history` WS payload) — downsample to 1 Hz for detection metrics unless the user opens the detailed panel.

**Phase to address:** Phase 5 — metrics (rollup + on-demand detail).

---

### Pitfall 24: Subprocess Bridge Serializing OBB Rotation Matrices via msgpack

**What goes wrong:**
v2.0's `SubprocessSLAMBridge` uses msgpack+numpy multipart. Numpy arrays round-trip fine. But a dataclass containing a 3x3 rotation matrix inside a list of OBBs may serialize to a nested structure that msgpack can't handle without a custom encoder, or that loses ndarray type identity.

**How to avoid:**
- Canonicalize the wire-internal format between detector subprocess and main: flat numpy arrays only. `obbs_centers: (N,3) float32`, `obbs_sizes: (N,3) float32`, `obbs_quats: (N,4) float32`, `classes: (N,) int32`, `scores: (N,) float32`. No nested dicts.
- Reconstruct into `OrientedBBox3D` objects on the main side.
- Matches v2.0's pattern for SLAM clouds (flat arrays, not nested).

**Phase to address:** Phase 5 — transport (subprocess wire format).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep median-depth 2D-center 3D projection, call it "3D detection" | Ship fast; already works | OBB regression requires geometric 3D anyway; rebuild later | Acceptable as YOLO fallback; NEVER represent as "real 3D detection" in docs or UI |
| Skip `warmup()` for YOLO (small model) | Saves 30 LOC | Inconsistent protocol; Big backends definitely need it | Never — protocol must be uniform or it's not a protocol |
| Hardcode FoV 70° | Less plumbing | Silent 18% position error on non-default scenes | Never — read from intrinsics |
| Share torch model across robots via threading | "Simpler" | GIL + compute serialization; per-robot latency doesn't improve | Acceptable for MVP if per-robot latency budget is 2-4s; use batching for tighter budgets |
| Skip tracker, dedupe visually | No tracker code | Metric meaningless; 3D mesh leak | Acceptable for first demo; add cheap 3D IoU tracker before milestone exit |
| Hardcode INDOOR_CLASSES | Works on current scene | Breaks on new scenes; hides real miss modes | Acceptable as default value; NOT as hardcoded constant |
| Put detector warmup in main server startup | Simple | Blocks server boot by 30s | Acceptable if a clear "loading..." message is shown; do async warmup in background and gate UI instead |
| Reuse v2.0 ZMQ bridge for BoxeR subprocess | v2.0 invested in this | None — right choice | Always acceptable |
| JSON wire format at 2 Hz | Easy to debug | Costly if detection rate increases | Acceptable at <5 Hz; migrate to msgpack above |
| Single shared detector for all N robots | v2.0 pattern | Fairness (round-robin), not throughput | Acceptable for N ≤ 4; batch across robots above |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| HuggingFace Transformers | `from_pretrained(id)` without `revision=` pin | Pin commit SHA via `revision=`; check Context7 for the current facebook/BoxeR repo path at integration time |
| HuggingFace `AutoProcessor` | Using image at non-standard size → silent resize | Resize in the backend with a known interpolation; log the processor's actual output shape once |
| Torch on CPU | Leaving `requires_grad=True` + no `torch.inference_mode()` | Freeze params + `inference_mode()` wrapper in `_detect()` |
| Torch thread config | Setting `torch.set_num_threads` after torch is used | Set env vars before imports; set torch settings before first forward pass |
| PyTorch MKL/oneDNN | Ignoring `OMP_NUM_THREADS` | Set explicitly in subprocess env |
| MuJoCo camera intrinsics | Assuming FoV=70 | Read from MuJoCo XML camera spec via `mj.mjv_defaultCamera` / `model.cam_fovy`; pass as `CameraIntrinsics` |
| Open3D PointCloud → numpy for detection | Creating PointCloud objects per detection | Work on raw numpy arrays; only create Open3D objects for visualization |
| Open3D Oriented Bounding Box | Using `compute_mean_and_covariance` on sky-leaking points | Filter outliers first; cluster; fit on dominant cluster |
| scipy Rotation | Forgetting `scalar_first=False` in quaternion (default) | Document quaternion order `[qx, qy, qz, qw]` everywhere |
| msgpack + numpy (existing v2.0 wire) | Serializing dataclass of dataclasses | Flat arrays per OBB field; reconstruct on other side |
| FastAPI WebSocket | `send_json` without async flow control | Backpressure: check WS state; drop detection frames if client isn't keeping up |
| React Flow port types | String-literal compare | Enum + exhaustive switch in validator |
| Three.js mesh lifecycle | `scene.add` without tracking | `InstancedMesh` + track-indexed; explicit dispose on unmount |
| react-three-fiber | Declarative meshes per detection | `<Instances>` with instanced rendering |
| Zustand store update per detection | Full store rewrite → all components re-render | Per-robot slice + shallow selector |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No model warmup | First detection 10-30s late; then fine | Warmup before reporting ready | Immediately on first run |
| Per-robot model instances | RSS × N_robots; no throughput gain | Shared model, batched inference | N_robots ≥ 2 |
| Sequential per-robot detection | per-robot FPS = total_FPS / N | Batch across robots in one forward | N_robots ≥ 2 |
| JSON floats at full precision | WS payload 2-3x expected | Round to 3-4 decimal places before serialize | Detection rate ≥ 5 Hz |
| Three.js mesh per detection per frame | GPU memory climbs; viewer slows | InstancedMesh + track-indexed updates | Session > 2 minutes |
| Gradient tracking on CPU | 2-3x slower; RSS climbs | `inference_mode()` + freeze params | Immediately, but especially after 1000 frames |
| Tokenizer rebuild per prompt (Grounding DINO) | Large overhead per prompt change | Cache tokenized prompt; only re-tokenize on text change | Prompts changing per-frame |
| Re-encode every detection into OBB mesh each frame | FPS drops over time | Only update matrices (setMatrixAt); geometry stays | Session > 1 minute |
| 10 Hz MetricsPanel updates | React re-render storm | Throttle to 1-2 Hz; separate Zustand slice | Multiple subscribers |
| `np.median` on 50k pixels per bbox | Detection dominated by numpy cost, not model | Subsample ROI to max 10k pixels; still robust | Large bboxes, 640×480+ |

---

## Security Mistakes

(This is a localhost dev simulation, so these are mostly hygiene concerns rather than adversarial security.)

| Mistake | Risk | Prevention |
|---------|------|------------|
| Auto-download model weights with no integrity check | Supply-chain: swapped weights → wrong detections | Pin `revision=` SHA; HuggingFace validates file hashes when revision is pinned |
| WS accepts arbitrary class filter strings from frontend | Pipeline eval() / param injection if a backend blindly passes to model | Schema-validate params server-side; never pass frontend strings directly to model calls |
| Subprocess bridge reads msgpack from network | If bridge were exposed beyond localhost, msgpack deserialization can construct arbitrary objects (with `raw=False`) | Keep ZMQ bound to `127.0.0.1`; use `strict_map_key=True` on msgpack unpacker |
| Model weights stored with loose filesystem perms | Writable weights could be tampered by other local processes | `models/` set readonly after fetch |
| Text prompts (Grounding DINO) accepted from frontend | Unbounded prompt length → resource exhaustion | Length-cap on server; reject prompts > 200 chars |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Detector: BoxeR (loading...)" that never changes | User assumes crash | Progress indicator with warmup stages: "downloading weights" / "warmup" / "ready"; time-since-started readout |
| Silently swapping to YOLO fallback | User thinks BoxeR worked | Toast on fallback + persistent badge in picker showing active backend |
| 3D box labels floating 30cm above objects | User thinks detector is wrong | Fix projection (Pitfall 3/4). If it's truly uncertainty, render confidence as size halo, not as offset |
| OBB flickers 30x/s as association fails | Viewer feels broken | Cheap 3D IoU tracker (Pitfall 12); labels hold for 1-2s after last detection |
| Parameter slider restarts detector on every move | Session disrupted | Debounce (v2.0 pattern); reload vs. live classification (Pitfall 18) |
| Switching detector mid-run without warning | Detections vanish | Pre-session selection via picker (reuse v2.0 pattern); restart overlay confirms |
| "mAP: 100%" on synthetic pseudo-labels | User trusts fake metric | Honest metrics only (Pitfall 11); "mAP" only appears when a labeled scene is loaded |
| Box + label + text + pose arrow all at once | Viewer cluttered | Layer toggles: boxes / labels / track IDs / confidence. Default: boxes + class labels only |
| No way to see the raw 2D bbox | Can't debug 3D projection | Camera feed overlay with 2D bbox drawn; toggle-able |

---

## "Looks Done But Isn't" Checklist

- [ ] **BoxeR backend "integrated":** Often missing warmup call, `.eval()` mode, `inference_mode()` wrapper, revision-pinned weights — verify `test_backend_regression` passes 3 fixed-image snapshots AND RSS is stable over 100 inferences.
- [ ] **Detector API "swappable":** Often missing `capture_pose` + `capture_timestamp` on the result — verify a 0.5 FPS backend + moving robot places the 3D box at the CAPTURE position, not current.
- [ ] **3D OBB "regressed":** Often just 2D bbox projected via median depth + axis-aligned box in world — verify rotation is actually used (rotate the object in MuJoCo; OBB orientation follows).
- [ ] **Multi-robot detection "works":** Often shared model with unfair scheduling — verify per-robot FPS is symmetric across 60 seconds.
- [ ] **Pipeline editor node "added":** Often missing port-type validation — verify connecting `DetectorConfig` → `Depth` is REJECTED by the validator.
- [ ] **Frontend picker "restarts backend":** Often missing restart overlay tie-in — verify v2.0 `RestartOverlay` fires for backend-level changes; smaller reload overlay fires for model-variant changes.
- [ ] **Metrics panel "shows detector stats":** Often shows only fps — verify `detection_freshness`, `confidence_mean`, `3d_center_jitter` are all present.
- [ ] **WS payload "reasonable":** Often unrounded floats at 10Hz — verify payload size <20KB/s with 20 detections × 2 robots × 2Hz.
- [ ] **Three.js OBBs "render":** Often leak — verify `renderer.info.memory.geometries` is stable after 5 minutes of detection.
- [ ] **YOLO "still works":** After BoxeR integration — verify selecting YOLO in picker produces same v2.0 behavior (characterization test).
- [ ] **Registry "discoverable":** Often depends on import order — verify `python -c "from src.perception.registry import list_available_backends"` works before any backend is imported.
- [ ] **Thread config "tuned":** Often default — verify `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `torch.get_num_threads()` all match the allocated budget in the subprocess.
- [ ] **Graceful fallback "works":** Often broken after refactor — verify uninstalling `transformers` keeps YOLO working and shows a clean "BoxeR unavailable" badge, not a crash.
- [ ] **Sim-ground-truth eval "runs":** Often faked — verify MuJoCo body positions are extracted and `center_error_m` metric matches expectations (should be <0.1m for clearly-visible objects).

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Warmup missing, first-run stall (P1) | LOW | Add `warmup()` to protocol; each backend implements. Day-scale. |
| Thread pool collision (P2) | MEDIUM | Move detector to subprocess (reuse v2.0 `SubprocessSLAMBridge`). 2-3 days. |
| Frame convention drift (P3) | MEDIUM-HIGH | Consolidate into `geometry.py`; delete duplicates; add regression test. 3-5 days because it touches downstream consumers. |
| Median-depth OBB (P4) | HIGH | Rewrite OBB estimation with point-cloud PCA; per-class outlier rejection. Week-scale. |
| OBB parameterization drift (P5) | MEDIUM | Canonicalize wire format; refactor all producers + consumers. 2-3 days. |
| Gradient tracking (P6) | LOW | Audit each backend; wrap in `inference_mode()`; freeze. Hours. |
| Tokenizer/processor drift (P7) | LOW-MEDIUM | Pin revision; add regression test with fixed fixtures. 1 day. |
| Stale pose on slow detector (P8) | MEDIUM | Add `capture_pose` + `capture_timestamp` through WS + Zustand. 2 days; touches 5-6 files. |
| Registry circular import (P9) | MEDIUM | Refactor module layout: types → protocol → registry → backends. 1-2 days. |
| Per-robot throughput collapse (P10) | MEDIUM | Implement batched inference across robots. 2-3 days. |
| Fake mAP metric (P11) | LOW | Replace with honest metrics + MuJoCo GT extractor. 1-2 days. |
| No frame association (P12) | MEDIUM | Cheap 3D IoU tracker; Three.js InstancedMesh. 2-3 days. |
| WS payload bloat (P13) | LOW | Rate limit + round floats. Hours. |
| Three.js leak (P14) | MEDIUM | Rewrite OBB layer with InstancedMesh manager. 2 days. |
| Pipeline port types (P15) | LOW-MEDIUM | Add port-type test matrix; centralize types. 1-2 days. |
| YOLO yanked too early (P16) | HIGH | Restore from git; keep YOLO wrapped as backend. Hours to restore + days to re-validate. |
| robot_id confusion (P17) | LOW | Type alias + runtime check. Hours. |
| Reload vs restart UX (P18) | LOW | Parameter classification in schema. 1 day. |

---

## Pitfall-to-Phase Mapping

Assumes v3.0 roadmap phases along the lines of:
- **Phase 1:** Research & backend shortlist
- **Phase 2:** Detector API + Registry + YOLO-as-first-backend wrap
- **Phase 3:** BoxeR (or selected HF transformer) backend + subprocess isolation
- **Phase 4:** Real 3D OBB regression + unified geometry
- **Phase 5:** Transport, metrics, eval (incl. MuJoCo GT)
- **Phase 6:** Frontend integration (picker, parameter panel, Three.js OBB layer, pipeline-editor nodes)
- **Phase 7:** Stability testing, CI/regression, polish

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| P1 Warmup stall | Phase 2 (API), Phase 3 (impl), Phase 6 (UX) | `detector_first_inference_ms` metric logged; first frame arrives within warmup budget |
| P2 Thread collision | Phase 2, Phase 3 | Detector runs in subprocess; main-process CPU unaffected when detector active |
| P3 Frame convention drift | Phase 2, Phase 4 | Single `geometry.py`; `test_geometry_agrees_with_slam_cloud` passes |
| P4 Median-depth OBB | Phase 4 | OBBs orient correctly on rotated MuJoCo furniture; extent matches actual object size ±20% |
| P5 OBB parameterization | Phase 4, Phase 5 | `OBB.from_wire(obb.to_wire()) == obb` round-trip test; canonical `qw >= 0` |
| P6 Gradient tracking | Phase 3 | RSS stable over 100 inferences; `inference_mode()` asserted in each backend's tests |
| P7 Processor drift | Phase 1, Phase 3, Phase 7 | Pinned `revision=`; fixed-fixture regression test in CI |
| P8 Stale pose | Phase 2, Phase 4, Phase 6 | `capture_pose` + `capture_timestamp` in wire payload; 3D box attaches to capture-time position |
| P9 Registry imports | Phase 2 | `import src.perception.registry` without torch loaded; `test_registry_no_heavy_imports` |
| P10 Per-robot throughput | Phase 3, Phase 5 | Symmetric per-robot FPS over 60s; RSS does not scale with N_robots |
| P11 Fake mAP | Phase 5 | MuJoCo GT extractor implemented; `center_error_m` reported; mAP removed from UI |
| P12 No association | Phase 4, Phase 6 | `track_id` in payload; Three.js mesh count bounded |
| P13 WS payload | Phase 5 | Payload < 20KB/s with 2 robots × 2 Hz × 20 detections |
| P14 Three.js leak | Phase 6 | `renderer.info.memory.geometries` stable over 5 min |
| P15 Port types | Phase 6 | Validator rejects type-mismatched edges; port types centralized |
| P16 YOLO yanked | Phase 2 | YOLO backend present throughout v3.0; characterization test against v2.0 behavior |
| P17 robot_id confusion | Phase 2, Phase 5 | `RobotId` type; integration test across wire |
| P18 Reload vs restart | Phase 6 | Parameter classification honored; smooth variant swap |
| P19 Module-scope thread set | Phase 2 | `src/_thread_config.py` at process start; no thread calls at module scope |
| P20 HF Hub download in CI | Phase 3, Phase 7 | `scripts/fetch_models.py`; `local_files_only=True` in CI |
| P21 FOV hardcode | Phase 2/4 | `CameraIntrinsics` used everywhere; hardcode deleted |
| P22 INDOOR_CLASSES filter | Phase 2 | Class filter configurable per-backend via schema |
| P23 Metric flood | Phase 5 | Detection metrics ≤ 2 Hz unless panel expanded |
| P24 Subprocess OBB serialize | Phase 5 | Flat-array wire between subprocess and main; round-trip test |

---

## Sources

- **Existing codebase (HIGH confidence):**
  - `src/perception/detector.py` — current YOLO detector, sign-flip convention, thread config at module scope
  - `src/perception/detection_3d.py` — duplicate projection path with different sign-flip source
  - `src/slam/protocol.py` + `src/slam/registry.py` — v2.0 protocol pattern to mirror
  - `src/slam/backends/subprocess_bridge.py` — v2.0 ZMQ+msgpack bridge to reuse
  - `.planning/PROJECT.md` + `.planning/MILESTONES.md` — v2.0 accomplishments, current constraints
  - `.planning/milestones/v2.0-research/PITFALLS.md` — v2.0 coordinate-frame, abstraction-layer, refactor-without-breaking, parameter-schema-drift lessons that echo directly into v3.0
- **HuggingFace Transformers (HIGH via official docs):**
  - transformers model loading, `revision=` pinning, processor/tokenizer drift patterns
  - `AutoProcessor`, `AutoModelForObjectDetection` defaults
- **PyTorch CPU (HIGH):**
  - `torch.inference_mode()` vs. `torch.no_grad()` — inference_mode disables view tracking
  - `torch.set_num_threads()` / `set_num_interop_threads()` behavior; OMP/MKL interaction
- **Three.js / react-three-fiber (MEDIUM-HIGH):**
  - `InstancedMesh` pattern for large numbers of similar meshes
  - `BufferGeometry.dispose()` + `Material.dispose()` required for GPU cleanup
  - `renderer.info.memory` for leak detection
- **React Flow (MEDIUM):**
  - Typed ports, node validation patterns; v2.0 codebase uses Kahn's algorithm validator per MILESTONES.md
- **ZMQ + msgpack (HIGH, from v2.0 in-repo):**
  - v2.0 subprocess bridge uses PAIR + msgpack+numpy multipart; reuse for detector subprocess
- **MuJoCo (HIGH):**
  - Camera intrinsics via `model.cam_fovy`; body positions via `mj_name2id` + `data.xpos` for ground truth

**Note on verification:** HuggingFace transformer specifics (BoxeR repo path, current processor API shape, Grounding DINO / OWL-ViT CPU performance) should be re-verified via Context7 `resolve-library-id` → `query-docs` at Phase 1 research time (2026-04 is 6+ months past this agent's knowledge cutoff; the `facebook/BoxeR` repo status, whether DETA or Co-DETR have overtaken BoxeR on CPU efficiency, etc. are not assumed here — those are questions for the STACK.md research companion).

---

*Pitfalls research: 2026-04-13 — v3.0 Pluggable Perception & 3D Object Detection milestone*
