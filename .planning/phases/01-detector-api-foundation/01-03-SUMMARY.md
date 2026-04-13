---
phase: 01-detector-api-foundation
plan: 03
subsystem: perception
tags: [perception, registry, decorator, lazy-import, capabilities, plugin-architecture]

# Dependency graph
requires:
  - phase: 01-detector-api-foundation
    provides: "Plan 02 — DetectorProtocol, Detection3DProtocol, DetectorInput enum, Detections2D/3D dataclasses (registry consumes DetectorInput for type-checked capability validation)"
  - phase: 01-detector-api-foundation
    provides: "Plan 01 — _thread_config ordering (registry is layer 3 of the import hierarchy; stays torch-free so Plan 01's ordering invariants are preserved)"
provides:
  - "DetectorRegistry — 2D detector backend registry with mandatory CAPABILITIES-key enforcement (framework, license, cpu_latency_hint_ms, outputs_3d_natively, input_type)"
  - "Detection3DRegistry — separate 3D lifter registry with its own mandatory keys (requires_depth, requires_point_cloud, outputs_oriented, license)"
  - "@detector_backend / @detection_3d decorators — class-definition-time registration via __module__ + __qualname__ lazy class-path"
  - "list_backends() contract — calls backend.available() classmethod, surfaces (bool, reason) verbatim; never invents install-hint text"
  - "_clear() test helper on both registries for cross-test isolation"
affects:
  - "01-04 (MedianDepthLifter) — consumes @detection_3d decorator to register"
  - "01-05 (YOLOv11Backend + backends/__init__.py side-effect imports) — consumes @detector_backend and DetectorRegistry.create"
  - "02 (DetectorWorker + DetectorWorkerPool) — uses DetectorRegistry.create()/list_backends() to enumerate+spawn backends"
  - "02 (REST /api/detectors/*) — serializes list_backends() output to the frontend picker"
  - "05 (RT-DETRv2, OWLv2, BoxeR) — plug in via decorator; registry code does not change"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-registry separation (2D vs 3D) with identical shape but independent _backends dicts — research Decision A"
    - "Mandatory CAPABILITIES-key enforcement at register() time — fail loudly at import, not at first use"
    - "available() classmethod probe for install-hint reporting — replaces v2.0 ImportError swallowing"
    - "Lazy class-path loading via __module__ + __qualname__ — registry module stays torch/ultralytics/transformers-free at import (Pitfall P9)"
    - "Defensive probe handling — missing probe defaults to (True, None); probe exceptions are caught and reported as unavailable without crashing the registry"

key-files:
  created:
    - "src/perception/registry.py (307 lines) — DetectorRegistry + Detection3DRegistry + @detector_backend + @detection_3d + _validate_capabilities + _load_class + _probe_availability"
    - "tests/perception/test_registry.py (272 lines, 16 test cases) — contract tests for D-05, D-06, P9, research Decision A"
  modified: []

key-decisions:
  - "Default 2D detector name locked to 'yolov11' (CONTEXT.md D-07); default 3D lifter locked to 'median_depth' (CONTEXT.md D-13)."
  - "register() signature takes the klass in hand (not just class_path) so CAPABILITIES validation happens synchronously at decorator time. SLAMRegistry's signature is preserved elsewhere; this intentional divergence is why backends know instantly whether they violate D-06."
  - "_probe_availability tolerates three failure modes: missing available() classmethod (defaults to (True, None) for legacy/third-party backends), probe raises exception (registered as unavailable with exception surfaced, registry does not crash), probe returns malformed shape (same). This is forgiving by design — a buggy backend must not take down list_backends()."
  - "capabilities/parameter_schema in list_backends() are returned as dict(...) copies so callers can mutate freely without poisoning registry internal state."
  - "Pre-existing test_protocol_contracts torch-dependency failures logged to deferred-items.md — out of Plan 03 scope (caused by uv venv not pulling torch, not by registry code)."

patterns-established:
  - "D-06 enforcement pattern: _validate_capabilities(name, klass, required_keys, typed_keys, kind) is the single gatekeeper both registries funnel through. Future registries (e.g., tracker registry in v3.0+) reuse the same helper."
  - "Decorator-to-register shim: @detector_backend computes class_path as f'{klass.__module__}.{klass.__qualname__}' then delegates to Registry.register(name, display, class_path, klass). Every future backend registration follows this shape."
  - "Test isolation pattern: autouse fixture _clean_registries calls _clear() before AND after each test so leaked state never cascades."
  - "Importlib-based sys.modules[__name__].Foo = Foo trick for tests that need list_backends to actually resolve a locally-defined class without monkey-patching."

requirements-completed: [DET-API-02, DET-API-03]

# Metrics
duration: 3 min
completed: 2026-04-13
---

# Phase 1 Plan 3: Perception Registry Summary

**DetectorRegistry + Detection3DRegistry with mandatory CAPABILITIES-key enforcement, available() probe-based install hints, and lazy class-path loading — registry module stays torch-free at import time.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-13T09:49:52Z
- **Completed:** 2026-04-13T09:53:15Z
- **Tasks:** 2 (both `type=auto tdd=true`)
- **Files created:** 2 (`src/perception/registry.py`, `tests/perception/test_registry.py`)
- **Files modified:** 0
- **Tests added:** 16 (all passing)

## Accomplishments

- Two separate registries (`DetectorRegistry` default `yolov11`, `Detection3DRegistry` default `median_depth`) with independent `_backends` dicts — research Decision A locked.
- Mandatory CAPABILITIES-key enforcement at `register()` time: 2D backends must declare `framework`, `license`, `cpu_latency_hint_ms`, `outputs_3d_natively`, `input_type` (CONTEXT.md D-06); 3D lifters must declare `requires_depth`, `requires_point_cloud`, `outputs_oriented`, `license`. Missing any key raises `ValueError` with all missing keys listed in sorted order for determinism.
- `input_type` is strictly type-checked to be a `DetectorInput` enum member (not a raw string) — catches drift at registration rather than runtime.
- `list_backends()` calls each backend's `available()` classmethod per CONTEXT.md D-05. The registry surfaces the returned `(bool, str | None)` as `(available, reason)` verbatim — it never invents install-hint text. Tolerates three edge cases: missing probe (defaults to `(True, None)`), probe exception (caught, marked unavailable with exception surfaced, registry does not crash), malformed return shape (same).
- `@detector_backend(name, display)` and `@detection_3d(name, display)` decorators register at class-definition time via lazy `__module__ + __qualname__` class-path strings — no torch / ultralytics / transformers at registry module import (Pitfall P9 closed for perception layer 3).
- 16 contract tests covering: heavy-imports invariant, defaults, missing-dict, missing-key listing, wrong-type rejection, happy path, probe behavior (true/false/missing/exception), unloadable class path, decorator behavior, 2D/3D registry independence, unknown-name create rejection.

## Task Commits

1. **Task 1: `src/perception/registry.py`** — `6ad6dfd` (feat) — DetectorRegistry + Detection3DRegistry + @detector_backend + @detection_3d + `_validate_capabilities` + `_load_class` + `_probe_availability`.
2. **Task 2: `tests/perception/test_registry.py`** — `7dbba31` (test) — 16 contract tests covering D-05, D-06, P9, and research Decision A.

_Note: Plan authored with `tdd=true` but ordered implementation-first (Task 1 = code, Task 2 = tests). Task 1's `<verify>` block embedded inline behavioral assertions that provided the RED/GREEN discipline equivalent before Task 2's formalized pytest suite was committed._

## Files Created

- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a353671a/src/perception/registry.py` — 307 lines; `DetectorRegistry`, `Detection3DRegistry`, `detector_backend`, `detection_3d`, plus module-private helpers.
- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a353671a/tests/perception/test_registry.py` — 272 lines; 16 pytest cases with autouse `_clean_registries` fixture.
- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a353671a/.planning/phases/01-detector-api-foundation/deferred-items.md` — out-of-scope pre-existing failure log.

## Decisions Made

See frontmatter `key-decisions`. Headline: `register()` takes the klass (not just a class_path) so D-06 validation happens synchronously at decorator time; probe-failure handling is forgiving so a single buggy backend cannot brick `list_backends()`.

## Deviations from Plan

None — plan executed exactly as written. Every `<action>` block, `<behavior>` clause, `<acceptance_criteria>` check, and `<verify>` block passed on first run. No Rule 1/2/3/4 deviations triggered.

## Gate Status

| Gate | Status | Evidence |
| --- | --- | --- |
| `grep -c "class DetectorRegistry"` | PASS (1) | 1 |
| `grep -c "class Detection3DRegistry"` | PASS (1) | 1 |
| `grep -c "def detector_backend"` | PASS (1) | 1 |
| `grep -c "def detection_3d"` | PASS (1) | 1 |
| `grep -c "_DETECTOR_REQUIRED_KEYS"` | PASS (>=2) | 2 |
| `grep -c "input_type"` | PASS (>=2) | 3 |
| `grep -c "outputs_oriented"` | PASS (>=1) | 1 |
| `grep -c "^import torch"` | PASS (0) | 0 |
| `grep -c "^import ultralytics"` | PASS (0) | 0 |
| `grep -c "^import transformers"` | PASS (0) | 0 |
| Task 1 inline verify (`uv run python -c ...`) | PASS | exit 0, prints `OK: registry contracts` |
| `uv run pytest tests/perception/test_registry.py -x -v` | PASS | 16 passed |
| `uv run python -c "from src.perception.registry import ..."` | PASS | prints `registry OK` |
| Full perception suite (minus pre-existing torch-missing failures) | PASS | 88 passed, 1 skipped |

## Issues Encountered

- **Pre-existing failure (NOT caused by Plan 03):** `tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_enforces_eval_and_freeze` and `::test_torch_backend_mixin_inference_contextmanager` fail with `ModuleNotFoundError: No module named 'torch'` because the uv venv does not currently pull torch. Confirmed present on base commit `3558bdb` prior to any Plan 03 work. Logged to `.planning/phases/01-detector-api-foundation/deferred-items.md` per executor scope-boundary rule. Does NOT affect registry correctness — `src.perception.registry` imports only stdlib + `DetectorInput` and passes the heavy-imports invariant test.

## Worktree Base Reset

The worktree was initialized on commit `b6bb40f` but the expected base per orchestrator was `3558bdb` (Wave 1 merge-back that contains `_thread_config.py`, `types.py`, `protocol.py`, and Plan 02 tests). A hard reset to `3558bdb` brought the worktree in line with the expected Phase 1 Wave 2 starting state. No work was lost (the worktree had no in-progress commits). This is the known Windows-adjacent behavior called out in the executor workflow's `<worktree_branch_check>`.

## Authentication Gates

None — no external services, no auth, no network.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `DetectorRegistry` + `Detection3DRegistry` contracts are locked and tested. Plan 04 (`MedianDepthLifter`) can consume `@detection_3d` decorator directly. Plan 05 (`YOLOv11Backend` + `src/perception/backends/__init__.py` side-effect imports) can consume `@detector_backend` directly.
- Parallel Wave 2 plans in Phase 1 (none scheduled — 01-03 is the sole Wave 2 plan per the plan frontmatter) have no collision risk with this work.
- Deferred item (torch missing from uv venv) is non-blocking for Plan 04; Plan 05 will need torch installed for YOLOv11Backend instantiation — that's the natural point to address it.

## Self-Check

- [x] `src/perception/registry.py` exists on disk: `test -f` PASS.
- [x] `tests/perception/test_registry.py` exists on disk: `test -f` PASS.
- [x] Commit `6ad6dfd` present in `git log`: PASS.
- [x] Commit `7dbba31` present in `git log`: PASS.
- [x] 16 registry tests PASS under `uv run pytest`.
- [x] Registry module import leaks zero heavy deps (P9 invariant test PASS).
- [x] All acceptance_criteria grep checks PASS.

## Self-Check: PASSED

---
*Phase: 01-detector-api-foundation*
*Completed: 2026-04-13*
