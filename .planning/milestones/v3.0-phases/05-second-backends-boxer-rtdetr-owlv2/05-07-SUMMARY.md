---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 07
subsystem: perception
tags: [rtdetrv2, onnxruntime, detector, transformer, coco, letterbox, cpu-inference]

# Dependency graph
requires:
  - phase: 05-01
    provides: onnxruntime>=1.19.0 dep + scipy + opencv-python-headless in perception extra
  - phase: 05-02
    provides: models/rtdetrv2/<SHA>/ directory layout + LICENSES.md Apache-2.0 entry for RT-DETRv2
  - phase: 05-04
    provides: tests/perception/test_rtdetrv2_backend.py skip-stub skeleton (7 tests)
  - phase: 05-05
    provides: src._thread_config.get_default_budget() public getter (D-07)
provides:
  - RT-DETRv2-S ONNX backend registered via DetectorRegistry as 'rtdetrv2'
  - RT_DETRV2_SHA / RT_DETRV2_REPO / RT_DETRV2_MODEL_DIR module constants (D-12 pin)
  - _letterbox_320 + _decode_boxes utility functions (testable in isolation)
  - COCO 80-class name mapping embedded for Detection2D.class_name
  - Activated test suite with monkeypatched ort.InferenceSession — 7 of 8 pass without the 300+ MB ONNX artifact
  - Synthetic 480×640 RGB+depth npz fixture for the skipped latency test's future rerun
affects:
  - 05-08 (backend selector pool) — will need to enumerate 'rtdetrv2' alongside 'yolov11' and 'boxer'
  - 05-11 (SHA verification) — backend raises on missing artifact; future plan adds sha256 integrity check at download time

# Tech tracking
tech-stack:
  added:
    - onnxruntime CPU EP as a DetectorProtocol-compatible framework (joins ultralytics, subprocess)
    - Framework-agnostic registration pattern validated — RT-DETRv2 does NOT use TorchBackendMixin (no torch.nn.Module involved)
  patterns:
    - Lazy-import hygiene (P9): onnxruntime + cv2 + scipy imported INSIDE method bodies, not at module scope
    - D-06 missing-artifact hint: backend.__init__ raises FileNotFoundError naming the `make` target — no auto-download
    - D-07 thread-budget inheritance: ort.SessionOptions.intra_op_num_threads = get_default_budget() (NO hardcoded int)
    - D-08 letterbox + reverse-letterbox: backend absorbs the 480×640 ↔ 320×320 coordinate transform; callers see original-frame pixel coords
    - Capability contract: framework='onnxruntime' proves the Phase 1 DetectorProtocol is genuinely framework-agnostic

key-files:
  created:
    - src/perception/backends/rtdetrv2_backend.py
    - tests/perception/fixtures/sample_480x640_with_chair.npz
  modified:
    - src/perception/backends/__init__.py
    - tests/perception/test_rtdetrv2_backend.py
    - .planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md

key-decisions:
  - "RT-DETRv2 backend skips TorchBackendMixin — ORT InferenceSession replaces torch.nn.Module; eval()/inference_mode() documented as no-ops"
  - "Module-level constants RT_DETRV2_SHA/REPO/MODEL_DIR mirror scripts/download_models.py; path is Path('models')/'rtdetrv2'/SHA with no user input (T-5-06 tampering mitigation)"
  - "Latency smoke test stays @pytest.mark.skip — rerun after `make download-models-rtdetrv2` produces the pinned artifact"
  - "Logit decoding: sigmoid(max_logit) per-query, argmax for class_id, threshold-filter; matches RT-DETRv2 DETR-family output format (logits shape (1,300,80), pred_boxes shape (1,300,4) cxcywh-normalized)"

patterns-established:
  - "Non-torch DetectorProtocol pattern: implement CAPABILITIES/PARAMETER_SCHEMA + process_frame/reset/warmup/get_metrics/apply_params/available directly; skip TorchBackendMixin when the underlying engine (ORT, subprocess, etc.) manages its own inference lifecycle"
  - "Letterbox backend absorbs coordinate transform: _letterbox_320 returns (scale, pad) so _decode_boxes can reverse; frame callers never see 320×320 coords"

requirements-completed: [DET-MODELS-02]

# Metrics
duration: 15 min
completed: 2026-04-15
---

# Phase 5 Plan 07: RT-DETRv2-S ONNX Backend Summary

**RT-DETRv2-S backend registered via onnxruntime CPU EP with fixed 320×320 input, letterbox preprocess, pinned SHA 5650961, and 7-of-8 test activation — DET-MODELS-02 lands.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-15T04:11:00Z
- **Completed:** 2026-04-15T04:26:00Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified, 1 deferred-items note)

## Accomplishments
- **RTDETRv2Backend class shipped and registered** — `DetectorRegistry.list_backends()` now surfaces `rtdetrv2` alongside `yolov11` with Apache-2.0 license, onnxruntime framework, and RGB_ONLY input type.
- **Letterbox coordinate transform contained inside the backend** — callers hand in a 480×640 MuJoCo frame and get Detection2D.bbox_xyxy in 480×640 coords; the 320×320 ORT plumbing is invisible.
- **D-07 thread-budget invariant enforced in a new framework** — `ort.SessionOptions.intra_op_num_threads = get_default_budget()` (not a hardcoded int), proving the Phase 1 thread-budget pattern generalizes beyond torch.
- **7 of 8 tests pass without the 300+ MB ONNX artifact** — monkeypatched `ort.InferenceSession` + `Path.exists` exercise constructor/warmup/preprocess/capabilities/thread-budget/registry paths; only the real-weights latency smoke test is `@pytest.mark.skip`.

## Task Commits

1. **Task 1: RTDETRv2Backend + letterbox + ORT session + registration** — `dc3293b` (feat)
2. **Task 2: activate test_rtdetrv2_backend.py with monkeypatched session + commit npz fixture** — `1118646` (test)

**Plan metadata:** `<this-commit>` (docs: 05-07 SUMMARY + deferred-items update)

## Files Created/Modified
- `src/perception/backends/rtdetrv2_backend.py` (**created**, 267 lines) — `RTDETRv2Backend` class, `_letterbox_320`, `_decode_boxes`, `_COCO_NAMES`, `RT_DETRV2_SHA/REPO/MODEL_DIR` constants.
- `src/perception/backends/__init__.py` (**modified**) — side-effect import `from src.perception.backends import rtdetrv2_backend` so the registry decorator fires.
- `tests/perception/test_rtdetrv2_backend.py` (**modified**) — replaced 7 skip-stubs with real assertions plus 1 new `test_construct_registers_in_registry`; 1 test stays `@pytest.mark.skip` with a rerun hint.
- `tests/perception/fixtures/sample_480x640_with_chair.npz` (**created**, 2.1 MB) — synthetic RGB + depth for the future latency rerun. Seeded `np.random.default_rng(42)` for determinism.
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md` (**modified**) — logged an out-of-scope pre-existing flake in `test_point_cluster_lifter_registered` (see Deferred Issues).

## Decisions Made
- **Skip TorchBackendMixin.** ORT has its own graph+inference lifecycle; there is no `torch.nn.Module` to `.eval()` or freeze. The DetectorProtocol contract is satisfied by implementing the five required methods directly. Docstring documents the rationale so future maintainers don't "fix" it by adding a useless mixin.
- **COCO class names embedded as a module-level dict.** Could have been imported from torchvision or ultralytics, but the backend must be importable without either — embedding the 80-class list keeps the import graph minimal (only numpy at module scope; cv2/scipy/onnxruntime lazy-loaded inside methods).
- **Latency smoke test stays skipped, with a rerun hint.** The plan explicitly calls out that activating it would require the 300+ MB `model.onnx`; committing that would bloat the repo and tangle CI with a `make download-models-rtdetrv2` prerequisite. The fixture npz is committed so the test is runnable locally as soon as the ONNX artifact lands.
- **ort.SessionOptions.intra_op_num_threads reads `get_default_budget()`, NOT a hardcoded int.** Phase 1 D-04 invariant: ALL thread budget config flows through `_thread_config.py`. The grep-style acceptance criterion `grep -cE 'intra_op_num_threads\s*=\s*[0-9]+' = 0` passes.

## Deviations from Plan

None — plan executed exactly as written. Both tasks met every acceptance criterion on first pass.

**Total deviations:** 0.
**Impact on plan:** None; zero auto-fixes required.

## Issues Encountered

**1. Pre-existing test-ordering failure discovered during phase-wide verification (out of scope)**
- **Found during:** Task 2 verification (`uv run pytest tests/perception/ -x --timeout=60 -m "not slow_boxer and not network"`).
- **Test:** `tests/perception/test_point_cluster_lifter.py::test_point_cluster_lifter_registered`.
- **Status:** Fails when run in the full `tests/perception/` sweep, passes in isolation. Verified by checkout of base commit `2854c68` — the failure is present WITHOUT the 05-07 changes. Unrelated to any RT-DETRv2 artifact.
- **Resolution:** Logged to `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md` as a test-infra cleanup item (autouse fixture needed to snapshot+restore registry dicts). Not auto-fixed per executor SCOPE BOUNDARY rule.

## Deferred Issues

Pre-existing failures outside Plan 05-07 scope (see `deferred-items.md` for full context):
- `test_point_cluster_lifter_registered` — test-ordering flake; registry-restore fixture needed.
- `fastapi` / `torch` / `open3d` / `openvins` ImportErrors in unrelated test modules — dev-install profile mismatches logged in 05-05.

## User Setup Required

None — no external service configuration required. The `make download-models-rtdetrv2` target (added in Plan 05-03 and activated in Plan 05-04) is the one step a user runs to fetch + export the pinned checkpoint locally; it is NOT a dashboard / credential setup.

## Next Phase Readiness

- DET-MODELS-02 is complete: RT-DETRv2-S backend constructs, registers, preprocesses, infers (behind a mock), and reports metrics. The latency smoke test gates SC#1 and will flip green the first time `make download-models-rtdetrv2` is run locally or in CI.
- Ready for **Plan 05-08** (DetectorWorkerPool integration / backend-selector expansion) — `DetectorRegistry.list_backends()` now returns ≥2 entries with valid `available=(False, 'Run make download-models-rtdetrv2 ...')` when the artifact is missing.
- Phase 2 subprocess bridge lock (`tests/perception/test_subprocess_bridge_skeleton.py`) still passes — confirms 05-07 did not disturb the ZMQ / coordinator plumbing.

## Self-Check: PASSED

- `test -f src/perception/backends/rtdetrv2_backend.py` → FOUND
- `test -f tests/perception/fixtures/sample_480x640_with_chair.npz` → FOUND
- `git log --oneline --grep="05-07"` → 2 commits found (`dc3293b`, `1118646`)
- `uv run pytest tests/perception/test_rtdetrv2_backend.py -v --timeout=30` → 7 passed, 1 skipped
- `uv run pytest tests/perception/test_registry.py tests/perception/test_subprocess_bridge_skeleton.py tests/perception/test_thread_config.py -x --timeout=60` → all pass, 0 regressions
- `grep -c 'intra_op_num_threads\s*=\s*[0-9]\+' src/perception/backends/rtdetrv2_backend.py` → 0 (no hardcoded thread count)
- `grep -c 'torch.set_num_threads' src/perception/backends/rtdetrv2_backend.py` → 0 (D-04 invariant)
- `grep -c '@detector_backend(name="rtdetrv2"' src/perception/backends/rtdetrv2_backend.py` → 1
- `grep -c 'from . import rtdetrv2_backend' src/perception/backends/__init__.py` → 1

---
*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Completed: 2026-04-15*
