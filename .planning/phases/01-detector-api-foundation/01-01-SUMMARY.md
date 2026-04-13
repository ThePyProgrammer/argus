---
phase: 01-detector-api-foundation
plan: 01
subsystem: infra
tags: [thread-config, torch, oneDNN, omp, mkl, openblas, perception, pytest-parametrize]

# Dependency graph
requires: []
provides:
  - "src/_thread_config.py — process-global env-var + torch thread budget setup"
  - "get_detector_thread_budget(num_robots) — Phase 2+ formula consumer"
  - "Grep-based invariant test that locks D-14 at CI"
affects: [02-detector-protocol-and-registry, 02-detector-worker-pool, 05-boxer-backend, 05-rt-detrv2-backend, 05-owlv2-backend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-scope side-effect import for process-global runtime config (mirrors src.slam.backends pattern)"
    - "Idempotent _CONFIGURED sentinel guard for repeat imports"
    - "Grep-based pytest invariant for forbidden-call-site enforcement"

key-files:
  created:
    - "src/_thread_config.py"
    - "tests/perception/__init__.py"
    - "tests/perception/test_thread_config.py"
  modified:
    - "src/main.py"
    - "src/perception/detector.py"

key-decisions:
  - "Default thread budget hardcoded to 2 (Phase 1 preserves pre-existing detector.py:25 setting)"
  - "_set_env_if_absent honors user-supplied OMP/MKL/OPENBLAS values (no clobber)"
  - "torch import wrapped in try/except ImportError so non-perception installs still work"
  - "torch.set_num_interop_threads(1) hardcoded (not budget-derived) per research P4"
  - "Grep test allows up to 4 leading spaces (covers module-scope try/if/else blocks)"

patterns-established:
  - "Process-global runtime config: src/_thread_config.py imported as first non-stdlib line in src/main.py (D-14)"
  - "Forbidden-call invariant test: parametrized over src/**/*.py, named exception per file"

requirements-completed: [DET-API-06]

# Metrics
duration: 3min
completed: 2026-04-13
---

# Phase 1 Plan 01: Thread Config Foundation Summary

**Process-global torch thread budget (OMP/MKL/OPENBLAS=2 + torch.set_num_threads(2) + torch.set_num_interop_threads(1)) consolidated into src/_thread_config.py imported first in main.py, with a parametrized grep invariant locking D-14 at CI.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-13T08:18:13Z
- **Completed:** 2026-04-13T08:21:00Z
- **Tasks:** 4
- **Files modified:** 5 (3 created, 2 edited)

## Accomplishments

- Created `src/_thread_config.py` — the single allowed module-scope torch.set_num_threads call site
- Inserted `import src._thread_config` as the first non-stdlib line of `src/main.py` (line 7), positioned before backend.web.server / src.slam.* / src.perception.* (all of which transitively import torch via ultralytics)
- Deleted line 25 (`torch.set_num_threads(2)`) from `src/perception/detector.py` — closes Pitfall P19
- Built grep-based invariant test (`tests/perception/test_thread_config.py`) that runs across 39 src/**/*.py files (38 PASSED, 1 SKIPPED for the allowed file) and will fail CI if any future commit re-introduces a module-scope `torch.set_num_threads` or `torch.set_num_interop_threads` call outside `_thread_config.py`
- Exposed `get_detector_thread_budget(num_robots)` API for Phase 2+ dynamic budget tuning per research Decision D formula `max(2, C // (2 + N_robots))`

## Task Commits

Each task was committed atomically (parallel-mode --no-verify):

1. **Task 1: Create src/_thread_config.py** — `22999fe` (feat)
2. **Task 2: Insert _thread_config import in src/main.py** — `f560476` (feat)
3. **Task 3: Delete torch.set_num_threads(2) from detector.py:25** — `96b8b10` (fix)
4. **Task 4: Grep-based thread-config invariant test** — `84d772d` (test)

Plan metadata commit follows separately.

## Files Created/Modified

- `src/_thread_config.py` — NEW. Sets OMP/MKL/OPENBLAS env vars + NNPACK_DISABLE/TORCH_CPP_LOG_LEVEL via `_set_env_if_absent` (respects user override), then `torch.set_num_threads(2)` + `torch.set_num_interop_threads(1)`. Idempotent via `_CONFIGURED` sentinel. Exposes `get_detector_thread_budget(num_robots)` for Phase 2+.
- `src/main.py` — MODIFIED. One line inserted at line 7: `import src._thread_config  # noqa: F401 -- sets OMP/MKL/torch threads before any torch import (D-14)`. Positioned after the `_os.environ` shim (lines 4-5) and before all `src.*` / `from backend.*` / `import torch` lines.
- `src/perception/detector.py` — MODIFIED. Line 25 (`torch.set_num_threads(2)  # limit CPU usage for background detection`) deleted. Surrounding `try/except ImportError` block, `import torch`, `from ultralytics import YOLO`, `YOLO_AVAILABLE`, and `class ObjectDetector` are unchanged.
- `tests/perception/__init__.py` — NEW. Empty file to make tests/perception a package.
- `tests/perception/test_thread_config.py` — NEW. Two tests: (1) parametrized over `src/**/*.py`, asserts no module-scope `torch.set_num_threads(` or `torch.set_num_interop_threads(` outside `_thread_config.py`; (2) sanity test asserting the allowed file actually contains both calls.

## Decisions Made

None beyond what the plan specified — plan executed exactly as written. Plan-level decisions (hardcoded budget=2, `_set_env_if_absent` semantics, `try/except ImportError` torch guard, grep approach with `\s{0,4}` leading-space tolerance) were all pre-decided in PLAN.md / CONTEXT.md D-14.

## Deviations from Plan

None - plan executed exactly as written.

The plan-level verification gate #2 (`uv run python -c "import src.main"`) required both `--extra perception` and `--extra web` (the default `uv run` install excludes optional extras). The plan implicitly assumed perception+web were installed; this is an environment quirk, not a deviation. With the correct extras the gate passes cleanly.

## Issues Encountered

- **uvicorn ModuleNotFoundError on `import src.main`:** First gate-2 attempt failed because `uv run python` (no extras) does not install the `web` extra (uvicorn/fastapi). Re-ran with `uv run --extra perception --extra web python -c "import src.main"` — passes. This is pre-existing environment configuration, not introduced by this plan.
- **Pre-existing SyntaxWarnings in third-party `evo` package:** `evo/core/transformations.py` emits `invalid escape sequence '\*'` warnings on import. Out of scope (Rule: pre-existing, not caused by this plan's changes).

## User Setup Required

None - no external service configuration required.

## Verification Gate Results

All five plan-level gates passed:

| Gate | Command | Result |
|------|---------|--------|
| 1 | `import src._thread_config; OMP=2; torch.get_num_threads()==2` | thread_config OK |
| 2 | `import src.main` (with perception+web extras) | src.main OK |
| 3 | `! grep torch.set_num_threads src/perception/detector.py` | no matches OK |
| 4 | `pytest tests/perception/test_thread_config.py -x` | 69 passed, 1 skipped |
| 5 | Idempotent: `import src._thread_config` twice | idempotent OK |

## Next Phase Readiness

- D-14 (thread config) Phase 1 scope is fully complete; remaining D-14 work: none.
- Plan 02 (DetectorProtocol + DetectorRegistry) can now safely add backend modules that transitively import torch — `_thread_config.py` will already have run by the time those modules load.
- Plan 04 (MedianDepthLifter) and Plan 05 (YOLOv11Backend behind protocol) can rely on `torch.set_num_threads(2)` being globally set without each backend re-applying it.
- The grep invariant test will fail CI loudly on any future commit that re-introduces a forbidden module-scope thread-config call, locking the contract for future BoxeR/RT-DETRv2/OWLv2 backends in Phase 5.

## Self-Check

Files created exist:
- `src/_thread_config.py` — FOUND
- `tests/perception/__init__.py` — FOUND
- `tests/perception/test_thread_config.py` — FOUND

Files modified retain expected content:
- `src/main.py:7` contains `import src._thread_config` — FOUND
- `src/perception/detector.py` no longer contains `torch.set_num_threads` — CONFIRMED (grep returns 0 matches)

Commits exist:
- `22999fe` (Task 1) — FOUND
- `f560476` (Task 2) — FOUND
- `96b8b10` (Task 3) — FOUND
- `84d772d` (Task 4) — FOUND

## Self-Check: PASSED

---
*Phase: 01-detector-api-foundation*
*Plan: 01*
*Completed: 2026-04-13*
