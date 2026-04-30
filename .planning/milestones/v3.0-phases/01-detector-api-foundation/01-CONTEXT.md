# Phase 1: detector-api-foundation - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock the four perception contracts (`DetectorProtocol`, `DetectorRegistry`, `Detection3DProtocol`, `Detection3DRegistry`) and refactor YOLOv11 behind them with zero behavioral regression. Move process-global thread-pool configuration to `src/_thread_config.py`. Ship `MedianDepthLifter` as the placeholder 3D lifter (`outputs_oriented=False`) — `PointClusterLifter` is Phase 4. No coordinator rewire, no REST/WS changes, no user-visible change.

**Out of scope (deferred to Phase 2+):**
- `DetectorWorker` / `DetectorWorkerPool` — Phase 2
- `capture_pose` / `capture_timestamp` on detection payloads — Phase 2
- `OrientedBox3D.to_wire()` wire format + round-trip test — Phase 2
- REST `/api/detectors/*` endpoints, WS plumbing, frontend picker — Phases 2-3
- `PointClusterLifter` (PCA-OBB) — Phase 4
- Any non-YOLO backend (RT-DETRv2, BoxeR, OWLv2) — Phase 5

</domain>

<decisions>
## Implementation Decisions

### Protocol Surface

- **D-01:** `DetectorProtocol.process_frame(frame: SensorFrame) -> Detections2D` — mirror `SLAMProtocol` exactly. No `text_prompt` or `class_filter` arg. Open-vocab prompts and class filters are configured per-model via `apply_params()`, never per-query.
- **D-02:** Required methods on every detector: `process_frame`, `reset()`, `warmup(dummy_frame)`, `get_metrics() -> dict`, `apply_params(params: dict) -> dict` (returns echo of accepted params). `warmup` is mandatory even for YOLO (no-op is a bug, not an optimization — addresses Pitfall P1).
- **D-03:** `Detections2D` carries required fields `(class_id: int, class_name: str, score: float, bbox_xyxy: tuple[int, int, int, int])` plus an optional `extras: dict[str, Any] | None = None` for backend-specific outputs (masks/features/text_logits). Phase 1 YOLO backend leaves `extras=None`.
- **D-04:** `Detection3DProtocol.lift(detections_2d, frame, pose, intrinsics, slam_cloud: np.ndarray | None)` — `slam_cloud` is a required parameter (may be `None`). `MedianDepthLifter` ignores it; Phase 4 `PointClusterLifter` consumes it when depth frustum is sparse.

### Registry + Capability Contract

- **D-05:** Backends report availability via a `@classmethod available() -> tuple[bool, str | None]` probe on the backend class. The registry calls this during `list_backends()` and surfaces the returned string as the install hint when `available: false`. This handles both pip-deps (`import ultralytics`) and non-pip deps (BoxeR subprocess binary, ONNX weights on disk) without forcing a decorator taxonomy.
- **D-06:** `CAPABILITIES` dict MANDATORY keys on every detector backend (registration fails at import time if missing):
  - `framework: str` — `"ultralytics"`, `"transformers"`, `"onnxruntime"`, `"subprocess"`
  - `license: str` — SPDX-style: `"AGPL-3.0"`, `"Apache-2.0"`, `"CC-BY-NC-4.0"`, `"MIT"`
  - `cpu_latency_hint_ms: int` — p50 hint (supplanted by live Phase 6 metrics)
  - `outputs_3d_natively: bool` — when `true`, `DetectorWorker` (Phase 2) bypasses lifter registry; frontend hides LifterDropdown
  - `input_type: DetectorInput` — enum `RGB_ONLY` / `RGBD` / `RGB_TEXT_PROMPT`
- **D-07:** Registration follows the SLAM side-effect-import pattern: `main.py` adds `import src.perception.backends  # noqa: F401 -- triggers backend registration`. `src/perception/backends/__init__.py` imports each backend module; `@detector_backend` decorator registers on import.

### Eval-Mode + RSS Enforcement

- **D-08:** `TorchBackendMixin` abstract base class owns eval-mode discipline. Concrete backends inherit it; the mixin's `__init__` calls `self.model.eval()` after subclasses set `self.model`, and provides an `_inference()` context manager that wraps `torch.inference_mode()`. Compile-time hard-to-forget. Non-torch future backends can skip the mixin.
- **D-09:** RSS smoke test lives at `tests/smoke/test_detector_rss.py`, parametrized over `DetectorRegistry.list_backends()` so every future backend is auto-covered. Runs 5 warmup iterations, resets RSS baseline via `psutil.Process().memory_info().rss`, then 100 measured iterations, asserts steady-state delta.
- **D-10:** RSS thresholds: **warn at 200 MB, fail at 400 MB**. Warning annotation surfaces slow drift before it becomes a crisis. ROADMAP success crit #3 literal reading (+200 MB) is preserved as the warning tier.

### YOLO Migration

- **D-11:** `YOLOv11Backend` is a **fresh implementation** against `DetectorProtocol`, NOT a delegate to `ObjectDetector._detect()`. The existing `ObjectDetector` class stays untouched in `src/perception/detector.py` for one phase. Both paths coexist: `ObjectDetector` runs via the current coordinator wiring; `YOLOv11Backend` runs via `DetectorRegistry.create("yolov11")` exercised only by tests. Phase 2's `DetectorWorkerPool` rewire is what actually retires `ObjectDetector`.
- **D-12:** Fixture-frame regression test: bit-exact equality between `ObjectDetector._detect(fixture_rgb, depth, pose)` and `YOLOv11Backend.process_frame(SensorFrame(fixture_rgb, depth, pose, ...))` on:
  - Identical detection count
  - Identical class_id set
  - bbox_xyxy match to ±0 pixels
  YOLO's NMS is deterministic on CPU so bit-exact is achievable. If CI flakes, relax to ±2 pixels and document the reason.
- **D-13:** **Consolidate 2D→3D projection into `MedianDepthLifter` in Phase 1.** `detector.py`'s inline 70° FOV path AND `detection_3d.py::project_detections_to_3d` both move into `MedianDepthLifter.lift()`. `ObjectDetector._detect()` is modified to *optionally* call the lifter instead of its inline math (behavior-preserving: same output for the regression test). This addresses Pitfall P3 in Phase 1 rather than letting it survive to Phase 4. The hardcoded 70° FOV stays inside the lifter for Phase 1; Phase 4's `src/perception/geometry.py` replaces it.

### Thread Config

- **D-14:** `src/_thread_config.py` is imported at the very top of `src/main.py` **before** `import torch` or any module that transitively imports torch. It sets: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` as env vars, plus `torch.set_num_threads()` and `torch.set_num_interop_threads(1)`. Detector thread budget follows research Decision D formula: `detector_threads = max(2, C // (2 + N_robots))`. `src/perception/detector.py:25` `torch.set_num_threads(2)` is removed. A test asserts no module outside `_thread_config.py` calls `torch.set_num_threads()` at module scope (grep-based test).

### Claude's Discretion

- Exact file layout for `src/perception/` subdirectories (`types.py` vs `protocol.py` vs `registry.py` vs `backends/` vs `lifters/` — research P9 recommends this order to avoid circular imports; Claude picks final names).
- Exact `PARAMETER_SCHEMA` JSON-Schema structure for YOLOv11 (confidence threshold, class filter, min_bbox_size).
- Whether `DetectorInput` is a Python `Enum` or a `Literal` string type.
- `OrientedBox3D` dataclass field order and defaults (ships skeleton-only in Phase 1; full wire format logic is Phase 2).
- Test fixture format — recorded RGB+depth NPZ vs synthetic deterministic scene.

### Folded Todos

None — no pending todos matched Phase 1 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §Phase 1 — goal, success criteria, requirements list
- `.planning/REQUIREMENTS.md` §DET-API, §DET-MODELS-01 — the 7 requirements this phase must deliver
- `.planning/PROJECT.md` — overall v3.0 vision + non-negotiables
- `.planning/research/SUMMARY.md` — v3.0 research executive summary
- `.planning/research/ARCHITECTURE.md` §Decisions A, D, E — Protocol split, thread config, wire format (Phase 1 preamble)
- `.planning/research/PITFALLS.md` P1–P5, P9, P16 — first-inference stall, thread collision, duplicate projection paths, eval-mode blowup, circular imports, preserve-YOLO-baseline
- `.planning/research/STACK.md` — pinned dep versions (`torch>=2.10.0`, `transformers>=5.3.0`, `ultralytics>=8.4.24`, `open3d>=0.18.0`)

### In-Tree Patterns to Mirror
- `src/slam/protocol.py` — template for `DetectorProtocol` + `Detection3DProtocol` runtime-checkable shape
- `src/slam/registry.py` — template for `DetectorRegistry` + `Detection3DRegistry` (lazy class-path loading, decorator, `list_backends()` with `available + reason`)
- `src/slam/backends/subprocess_bridge.py` — structural template for Phase 2's `SubprocessDetectorBridge` (referenced for consistency; NOT built in Phase 1)
- `src/main.py` top 10 lines — current `NNPACK_DISABLE` + `import src.slam.backends` pattern that `_thread_config.py` replaces/extends

### Code to Modify (Phase 1)
- `src/perception/detector.py` — remove line 25 (`torch.set_num_threads(2)`); optionally rewire `_detect()` to call into `MedianDepthLifter` (behavior-preserving)
- `src/perception/detection_3d.py` — logic moves into `src/perception/lifters/median_depth.py::MedianDepthLifter.lift()`; keep file as shim for one phase
- `src/main.py` — add `import src._thread_config` as first non-stdlib line; add `import src.perception.backends  # noqa: F401`
- `pyproject.toml` — no changes this phase (perception extras already declared)

### Code to Create (Phase 1)
- `src/_thread_config.py` — env vars + torch thread setup
- `src/perception/protocol.py` — `DetectorProtocol`, `Detection3DProtocol`, `Detections2D`, `OrientedBox3D` (skeleton), `DetectorInput` enum
- `src/perception/registry.py` — `DetectorRegistry`, `Detection3DRegistry`, `@detector_backend`, `@detection_3d` decorators
- `src/perception/backends/__init__.py` — side-effect imports of YOLOv11Backend
- `src/perception/backends/yolov11_backend.py` — new YOLOv11Backend + `TorchBackendMixin`
- `src/perception/lifters/__init__.py` + `median_depth.py` — MedianDepthLifter
- `tests/smoke/test_detector_rss.py` — parametrized RSS smoke test
- `tests/perception/test_yolov11_regression.py` — fixture-frame regression test
- `tests/perception/test_thread_config.py` — grep assertion that no other module calls `torch.set_num_threads` at module scope

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/slam/protocol.py` — `@runtime_checkable Protocol` with `CAPABILITIES`/`PARAMETER_SCHEMA` class attrs — exact shape to mirror for DetectorProtocol
- `src/slam/registry.py::SLAMRegistry` — lazy class-path loading via `importlib`, generic `_backends: dict`, `register()` + `list_backends()` + `create()` — clone structurally as `DetectorRegistry`
- `src/slam/registry.py::slam_backend` decorator — pattern for `@detector_backend(name, display)` decorator
- `src/slam/__init__.py` side-effect import convention — reuse for `src/perception/backends/__init__.py`
- `src/bridge/sensor_types.py::SensorFrame` — the input type for `process_frame`; already carries `rgb, depth, camera_pose, sim_time, intrinsics`
- `src/perception/detector.py::INDOOR_CLASSES` dict (lines 64-72) — moves to `YOLOv11Backend`, filters COCO to indoor subset
- `src/perception/detection_3d.py::project_detections_to_3d` — median-depth math; logic moves into `MedianDepthLifter.lift()`

### Established Patterns
- **Lazy backend availability** — SLAMRegistry returns `available: false, reason: "Cannot load X"` today via ImportError swallow. Phase 1 must upgrade this to call `backend.available()` classmethod for install hint text (DET-API-02 success criterion).
- **Side-effect import for backend registration** — `main.py:51` already has `import src.slam.backends  # noqa: F401 -- triggers backend registration`. Add a sibling line for perception.
- **Thread-config at import top** — `main.py:3-4` already sets `NNPACK_DISABLE=1` and `TORCH_CPP_LOG_LEVEL=ERROR` via `os.environ` before torch import. `_thread_config.py` extends this pattern with full thread budgets.
- **Dataclass-based result types** — `SLAMResult` pattern (numpy + dict + enum). `Detections2D` follows the same shape.

### Integration Points
- **Coordinator wiring stays unchanged** — `src/coordination/coordinator.py:140-148, 637-654` continues to use `ObjectDetector`. Phase 2 rewires this to `DetectorWorkerPool`. Phase 1 does NOT touch coordinator.
- **No FastAPI changes** — `backend/web/` untouched. Registry is Python-side only.
- **Frontend untouched** — no store, no components, no routes.

### Constraints
- YOLO's NMS must remain bit-deterministic for the regression test → no PyTorch version bump, no CUDA, no `torch.compile`.
- `ObjectDetector` and `YOLOv11Backend` coexist during Phase 1 → two YOLO model instances may load simultaneously; document this as a known, temporary memory cost (bounded by Phase 2).

</code_context>

<specifics>
## Specific Ideas

- Regression test uses a checked-in fixture: a single RGB frame captured from the current MuJoCo office scene, plus its depth map and camera pose, stored as `tests/fixtures/yolo_regression_scene_01.npz`. The phase cannot merge without this fixture committed.
- `TorchBackendMixin` exposes `_inference()` as a `contextmanager`, not a decorator, so backends that need intermediate non-inference work (postprocessing, metric updates) can scope the guard precisely.
- `available()` classmethod convention: return `(True, None)` when OK; `(False, "pip install ultralytics>=8.4.24")` when ImportError; `(False, "run scripts/setup_boxer_subprocess.sh")` when a non-pip precondition is missing. The registry never invents hint text.
- Thread config asserts are grep-based (read every `src/**/*.py` that isn't `_thread_config.py`, fail if the file contains `set_num_threads`). Simpler than AST parsing and sufficient for the invariant.

</specifics>

<deferred>
## Deferred Ideas

- **`src/perception/geometry.py` canonical unprojection module** — suggested during discussion as an option for Phase 1. Deferred to Phase 4 where `PointClusterLifter` actually benefits from it. Phase 1 keeps the hardcoded 70° FOV inside `MedianDepthLifter`.
- **Thread budget auto-tuning based on robot count** — research Decision D formula `detector_threads = max(2, C // (2 + N_robots))` is captured as a hardcoded default in Phase 1; dynamic tuning based on `MultiRobotConfig` is a Phase 2+ enhancement.
- **Entry-point-based backend registration** for third-party backends — rejected for v3.0 (all backends ship in-tree).
- **`DetectorRequest` polymorphic input dataclass** — rejected; `process_frame(frame: SensorFrame)` is the final shape. Per-model configuration flows through `apply_params()`.

### Reviewed Todos (not folded)

None — no pending todos matched Phase 1 scope.

</deferred>

---

*Phase: 01-detector-api-foundation*
*Context gathered: 2026-04-13*
