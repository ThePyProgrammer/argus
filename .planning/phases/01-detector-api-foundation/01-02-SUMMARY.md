---
phase: 01-detector-api-foundation
plan: 02
subsystem: perception
tags: [protocol, runtime-checkable, dataclass, torch-mixin, types, perception, contracts]

requires:
  - phase: 01-detector-api-foundation
    provides: tests/perception/__init__.py (Plan 01-01, parallel wave 1)
provides:
  - DetectorProtocol (@runtime_checkable, 5 methods + classmethod available)
  - Detection3DProtocol (@runtime_checkable, lift with required slam_cloud)
  - TorchBackendMixin (eval+freeze enforcement, _inference contextmanager)
  - Detection2D, Detections2D, OrientedBox3D (Phase 1 skeleton), Detections3D
  - DetectorInput enum (RGB_ONLY, RGBD, RGB_TEXT_PROMPT)
affects: [01-03-registry, 01-04-median-depth-lifter, 01-05-yolov11-backend, 02-detector-worker, 04-point-cluster-lifter]

tech-stack:
  added: [typing.Protocol with runtime_checkable, contextlib.contextmanager for inference guard]
  patterns:
    - "Module-order layering (types -> protocol -> registry -> backends) per Pitfall P9"
    - "Lazy torch import inside method bodies to keep Protocol module torch-free"
    - "Mandatory CAPABILITIES key list documented in Protocol docstring; enforcement deferred to registry"
    - "Mixin-based eval+inference_mode discipline (compile-time-hard-to-forget)"
    - "available() classmethod probe for backend availability + install hint"

key-files:
  created:
    - src/perception/types.py
    - src/perception/protocol.py
    - tests/perception/test_protocol_contracts.py
  modified: []

key-decisions:
  - "DetectorInput as enum.Enum (not Literal string) for type-safe registration-time capability checks"
  - "OrientedBox3D ships skeleton-only in Phase 1; to_wire/from_wire/__eq__ tolerance deferred to Phase 2 wire-format work"
  - "TorchBackendMixin uses lazy torch import inside __init__ method body to keep src.perception.protocol torch-free at module scope (Pitfall P9)"
  - "_inference exposed as contextmanager (not decorator) so backends can scope guard precisely around forward pass"
  - "TypeError raised eagerly when subclass forgets to set self.model before super().__init__() (fail fast)"

patterns-established:
  - "Lazy heavy-dep import: torch/transformers/ultralytics imported inside method bodies, never at module scope, in foundational layers (types.py, protocol.py)"
  - "Snapshot-diff invariant test: import module, assert delta to sys.modules excludes torch/ultralytics/transformers/onnxruntime"
  - "Frozen dataclass field-order locking: contract test asserts exact ordered field name list to prevent silent reordering"
  - "Protocol surface locking: contract test asserts public method set is EXACTLY the locked set, rejecting accidental additions"

requirements-completed: [DET-API-01, DET-API-03]

duration: 5min
completed: 2026-04-13
---

# Phase 1 Plan 02: Protocol & Types Foundation Summary

**DetectorProtocol + Detection3DProtocol locked as @runtime_checkable Protocols with 5-method surface (process_frame, reset, warmup, get_metrics, apply_params, available), TorchBackendMixin enforcing eval+inference_mode discipline, and frozen dataclass types (Detection2D, OrientedBox3D skeleton, DetectorInput enum) — all torch-free at module scope per Pitfall P9.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-13T08:19:02Z
- **Completed:** 2026-04-13T08:23:41Z (approx)
- **Tasks:** 3
- **Files created:** 3
- **Files modified:** 0

## Accomplishments

- `src/perception/types.py` (114 lines): `DetectorInput` enum + 4 frozen dataclasses (`Detection2D`, `Detections2D`, `OrientedBox3D` skeleton, `Detections3D`) — zero heavy-dep imports
- `src/perception/protocol.py` (206 lines): `DetectorProtocol`, `Detection3DProtocol` (both `@runtime_checkable`), `TorchBackendMixin` with `_inference()` contextmanager — torch imported lazily inside method bodies only
- `tests/perception/test_protocol_contracts.py` (269 lines): 18 contract tests covering Protocol method-set lock, dataclass field order, runtime_checkable isinstance check via stub, `slam_cloud` annotation invariant, `TorchBackendMixin` eval+freeze enforcement, no-heavy-imports invariant, and `to_wire`/`from_wire` absence (Phase 2 scope)
- All 18 contract tests pass under `uv run pytest`

## Task Commits

Each task was committed atomically (parallel-wave executor, --no-verify):

1. **Task 1: src/perception/types.py** — `51a9d86` (feat)
2. **Task 2: src/perception/protocol.py** — `0fb9d43` (feat)
3. **Task 3: tests/perception/test_protocol_contracts.py** — `70cc5b4` (test)

## Files Created/Modified

- `src/perception/types.py` — Frozen dataclasses + DetectorInput enum, the bottom of the perception module stack (P9 layer 1)
- `src/perception/protocol.py` — Detector + lifter protocols and TorchBackendMixin (P9 layer 2). DetectorInput re-exported for registry convenience.
- `tests/perception/test_protocol_contracts.py` — 18-test contract suite locking the Phase 1 surface so Plans 03/04/05 cannot drift

## Decisions Made

- **DetectorInput is `enum.Enum`** (CONTEXT.md "Claude's Discretion" resolved). Picked over `Literal` so the registry in Plan 03 can validate `CAPABILITIES["input_type"]` via `isinstance(..., DetectorInput)` rather than fragile string comparison.
- **`OrientedBox3D` is skeleton-only.** Fields and conventions documented (xyzw quaternion, world-frame meters, local-axis half-extents) but `to_wire()` / `from_wire()` / quaternion-hemisphere canonicalization (`qw >= 0`) deferred to Phase 2 (DET-3D-03/04). The contract test asserts these methods are absent — it would fail loudly if Phase 2 work leaked into Phase 1.
- **Lazy torch import inside `TorchBackendMixin.__init__`** (not module scope). Caching `self._torch = torch` after the lazy import keeps `_inference()` cheap. Importing `src.perception.protocol` does not pull torch into `sys.modules` — verified by the no-heavy-imports test.
- **`_inference` as `contextlib.contextmanager`, not decorator.** Backends call `with self._inference(): forward()` and can keep post-processing (NMS, metric updates) outside the guard. Matches CONTEXT.md "Specifics" section.
- **Eager `TypeError` on missing `self.model`.** `TorchBackendMixin.__init__` checks `hasattr(self, "model")` and raises with a clear message naming the contract violation (D-08). Fails fast at construction rather than silently producing a broken backend.
- **`isinstance(stub, DetectorProtocol)` smoke test.** The success-criteria explicitly required runtime-checkable verification via stub — the test constructs `YoloTestStub` with all five methods + `available()` classmethod + `CAPABILITIES`/`PARAMETER_SCHEMA` class attrs and asserts `isinstance(stub, DetectorProtocol)`.
- **`slam_cloud` annotation invariant test.** Per success-criteria, added `test_detection_3d_protocol_slam_cloud_annotation_optional` which asserts the annotation string contains both "ndarray" and "none" (case-insensitive). Locks D-04 contract beyond just parameter name presence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed `perception` extra (torch + ultralytics + transformers)**
- **Found during:** Task 2 verification (TorchBackendMixin runtime check)
- **Issue:** `uv run python` failed with `ModuleNotFoundError: No module named 'torch'` when the verification script attempted to construct a `FakeBackend(TorchBackendMixin)` — the lazy torch import inside `__init__` requires torch to be resolvable at call time.
- **Fix:** Ran `uv sync --extra perception --extra dev` to install `torch>=2.10.0`, `transformers>=5.3.0`, `ultralytics>=8.4.24` and pytest-* test-runner deps.
- **Files modified:** none (lockfile only — `uv.lock` updated implicitly)
- **Verification:** Verification script passes; pytest runs all 18 contract tests.
- **Committed in:** N/A (env-only change, no source modification)

**2. [Rule 1 - Bug] Verification script's `hasattr` check on Protocol class attributes was wrong**
- **Found during:** Task 2 verification
- **Issue:** The verify block in the plan asserted `hasattr(DetectorProtocol, 'CAPABILITIES')` but Protocol class-level annotations without default values do NOT create class attributes (this is standard Python `typing.Protocol` semantics, mirrored in SLAMProtocol). The same `hasattr` would fail against the existing `src.slam.protocol.SLAMProtocol`.
- **Fix:** Adjusted the verification logic to check `'CAPABILITIES' in DetectorProtocol.__annotations__` for the class-attribute contract, while keeping `hasattr` for methods (which DO appear on the class). The actual contract test in Task 3 uses the correct semantics throughout.
- **Files modified:** none (test logic is correct in `test_protocol_contracts.py`; only the inline verify shell command was adjusted)
- **Verification:** All 18 contract tests pass.

**3. [Rule 2 - Missing critical functionality] Added 18th test for runtime_checkable stub isinstance check + 14th-15th tests for slam_cloud annotation lock**
- **Found during:** Task 3 authoring
- **Issue:** Plan listed 14 tests in acceptance criteria, but executor success-criteria explicitly demand: (a) `isinstance(yolo_test_stub, DetectorProtocol)` passes, and (b) slam_cloud annotation contains both 'None' AND 'ndarray' (case-insensitive). The plan's 14-test list covered runtime_checkable-via-`_is_runtime_protocol` and lift parameter names, but NOT the actual `isinstance` smoke check or annotation string check.
- **Fix:** Added `test_detector_protocol_runtime_checkable_with_stub` (constructs `YoloTestStub` with full mandatory CAPABILITIES dict + all 5 methods + classmethod and asserts isinstance) and `test_detection_3d_protocol_slam_cloud_annotation_optional` (asserts annotation string contains both 'none' and 'ndarray', case-insensitive). Total tests: 18 (4 over the planned 14, all covering executor success-criteria).
- **Files modified:** tests/perception/test_protocol_contracts.py
- **Verification:** All 18 tests pass; the new tests would fail loudly if a future change broke runtime_checkable or weakened the slam_cloud annotation.

---

**Total deviations:** 3 auto-fixed (1 blocking env, 1 verification-script bug, 1 critical-functionality completeness)
**Impact on plan:** No scope creep — all deviations either restored verifiability (env install) or strengthened test coverage to match executor success-criteria. Source files match the plan's `<action>` blocks verbatim.

## Issues Encountered

- The verify shell snippet shipped in the plan had an incorrect `hasattr` check for Protocol class attributes (see Deviation #2). Worked around by recognising that Protocol class-attr annotations live in `__annotations__`, mirrors existing `SLAMProtocol` semantics. No source-file change was required.

## Exposed Symbols for Downstream Plans

- **Plan 01-03 (registry):** `DetectorProtocol`, `Detection3DProtocol`, `DetectorInput`, `Detections2D`, `Detections3D` — registry validates `CAPABILITIES` keys + `input_type` enum at registration time.
- **Plan 01-05 (YOLOv11Backend):** `TorchBackendMixin`, `DetectorProtocol`, `Detection2D`, `Detections2D` — backend inherits the mixin, returns `Detections2D` from `process_frame`.
- **Plan 01-04 (MedianDepthLifter):** `Detection3DProtocol`, `OrientedBox3D`, `Detections3D` — lifter implements `lift(...)` returning a `Detections3D` of `OrientedBox3D` items with identity quaternion (axis-aligned skeleton, pre-Phase 4).

## Pitfalls Addressed

- **P1 (first-inference stall):** `warmup(dummy_frame: SensorFrame) -> None` is mandatory on `DetectorProtocol`. Docstring states "no-op warmup is a bug" — Plan 05's YOLOv11Backend will exercise the real inference path.
- **P5 (eval-mode blowup):** `TorchBackendMixin.__init__` calls `self.model.eval()` and `p.requires_grad_(False)` for every parameter; `_inference()` wraps `torch.inference_mode()`. Compile-time-hard-to-forget — backends that subclass the mixin cannot accidentally run in train mode or with autograd.
- **P9 (circular imports / heavy-dep leak):** Module-order layers 1 (`types.py`) and 2 (`protocol.py`) are torch-free at module scope. Verified by snapshot-diff `sys.modules` invariant test. Lazy torch import lives inside `TorchBackendMixin.__init__` only.

## Threat Flags

None — Phase 1 ships type/protocol contracts only; no network endpoints, no authentication paths, no file/IO surface, no schema changes at trust boundaries. Phase 2's REST `/api/detectors/*` endpoints will introduce auth surface for the first time.

## Next Phase Readiness

- Plan 01-03 can land registry on top of these protocols today (no blockers).
- Plan 01-04 (MedianDepthLifter) and Plan 01-05 (YOLOv11Backend) have their full base interface available.
- The contract tests will catch regressions in Plans 03/04/05 — any drift from the locked surface fails CI loudly.
- The `tests/perception/__init__.py` package marker is owned by Plan 01-01 (parallel wave 1); pytest collected the test file successfully without it (rootdir discovery), but the `__init__.py` will still land for consistency with `tests/slam/`.

## Self-Check: PASSED

- src/perception/types.py — FOUND
- src/perception/protocol.py — FOUND
- tests/perception/test_protocol_contracts.py — FOUND
- .planning/phases/01-detector-api-foundation/01-02-SUMMARY.md — FOUND
- Commit 51a9d86 (Task 1: types) — FOUND
- Commit 0fb9d43 (Task 2: protocol) — FOUND
- Commit 70cc5b4 (Task 3: contract tests) — FOUND
- 18/18 contract tests passing under `uv run pytest`

---
*Phase: 01-detector-api-foundation*
*Plan: 02*
*Completed: 2026-04-13*
