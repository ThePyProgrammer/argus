---
phase: 06-detection-metrics-and-mujoco-gt
plan: 02
subsystem: testing
tags: [pytest, skip-stub, scaffolding, wave-0, perception, metrics]

requires:
  - phase: 06
    provides: 06-VALIDATION.md Wave 0 requirements, 06-RESEARCH.md F5 (tests/contract missing), 06-CONTEXT.md D-10/D-14/D-15
provides:
  - "tests/metrics/ package (NEW) with 2 skip-stubs for DET-METRICS-01/02"
  - "tests/contract/ package (NEW) with 2 skip-stubs for DET-METRICS-03"
  - "3 additional skip-stubs under tests/integration/ and tests/ for DET-METRICS-03/04/05"
  - "collect-passes-but-skips state per Nyquist validation protocol"
affects:
  - "06-04 (Wave 1: DetectionMetricsTracker) — replaces tests/metrics/test_detection_metrics_tracker.py"
  - "06-05 (Wave 1: MuJoCoGTExtractor) — replaces tests/metrics/test_mujoco_gt.py"
  - "06-08 (Wave 2: payload runtime guard) — replaces tests/contract/test_no_map_in_payload.py"
  - "06-09 (Wave 2: export round-trip) — replaces tests/integration/test_detections_export.py"
  - "06-10 (Wave 3: CLI reservation) — replaces tests/test_main_args.py"
  - "06-12 (Wave 5: grep invariant) — replaces tests/contract/test_no_map_in_ui.py"
  - "06-13 (Wave 5: RSS smoke) — replaces tests/integration/test_rss_smoke_backends.py"

tech-stack:
  added: []
  patterns:
    - "skip-stub pattern: module-level pytest.skip(..., allow_module_level=True) naming target requirement + replacing plan"
    - "Phase 5 Plan 04 stub shape reused (docstring -> import pytest -> pytest.skip)"

key-files:
  created:
    - tests/metrics/__init__.py
    - tests/metrics/test_detection_metrics_tracker.py
    - tests/metrics/test_mujoco_gt.py
    - tests/contract/__init__.py
    - tests/contract/test_no_map_in_ui.py
    - tests/contract/test_no_map_in_payload.py
    - tests/integration/test_detections_export.py
    - tests/integration/test_rss_smoke_backends.py
    - tests/test_main_args.py
  modified: []

key-decisions:
  - "Reused Phase 5 Plan 04 canonical stub shape verbatim — docstring then import pytest then pytest.skip(allow_module_level=True)"
  - "Created tests/contract/ as a brand-new pytest package (previously absent per RESEARCH F5)"
  - "Left tests/integration/__init__.py untouched (already exists)"

patterns-established:
  - "Wave 0 scaffold: every Phase 6 test file lands as skip-stub before any implementation plan executes"
  - "Stub docstrings cite the replacing plan number + wave so downstream planners can find the target"

requirements-completed: [DET-METRICS-01, DET-METRICS-02, DET-METRICS-03, DET-METRICS-04, DET-METRICS-05]

duration: ~5min
completed: 2026-04-15
---

# Phase 06 Plan 02: Wave 0 Skip-Stub Scaffolding Summary

**9 Wave-0 scaffold files (2 package markers + 7 skip-stubs) landed so pytest collection flows even before DetectionMetricsTracker / MuJoCoGTExtractor / export / RSS implementations exist.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-15T~15:40Z
- **Completed:** 2026-04-15T~15:45Z
- **Tasks:** 3/3
- **Files created:** 9

## Accomplishments

- Established `tests/metrics/` as a fresh pytest package with DET-METRICS-01/02 skip-stubs
- Established `tests/contract/` as a brand-new pytest package (RESEARCH F5 identified this as missing) with both DET-METRICS-03 guards (grep invariant + payload runtime guard)
- Added 3 more stubs — `tests/integration/test_detections_export.py` (DET-METRICS-04), `tests/integration/test_rss_smoke_backends.py` (DET-METRICS-05), `tests/test_main_args.py` (DET-METRICS-03 CLI reservation) — without perturbing existing `tests/integration/__init__.py`
- Every stub names its target requirement ID and the plan number that will replace it in later waves, so downstream plans have unambiguous flip points

## Task Commits

1. **Task 1: tests/metrics/ package + 2 skip-stubs** — `77dd2f6` (test)
2. **Task 2: tests/contract/ package + 2 skip-stubs (NEW dir per F5)** — `14fa1d9` (test)
3. **Task 3: integration + main-args skip-stubs** — `ff4a282` (test)

## Files Created/Modified

- `tests/metrics/__init__.py` — 0-byte package marker (new package)
- `tests/metrics/test_detection_metrics_tracker.py` — DET-METRICS-01 skip-stub, replaced by 06-04
- `tests/metrics/test_mujoco_gt.py` — DET-METRICS-02 skip-stub, replaced by 06-05
- `tests/contract/__init__.py` — 0-byte package marker (NEW directory per RESEARCH F5)
- `tests/contract/test_no_map_in_ui.py` — DET-METRICS-03 grep invariant stub, replaced by 06-12
- `tests/contract/test_no_map_in_payload.py` — DET-METRICS-03 payload runtime guard stub, replaced by 06-08
- `tests/integration/test_detections_export.py` — DET-METRICS-04 export round-trip stub, replaced by 06-09
- `tests/integration/test_rss_smoke_backends.py` — DET-METRICS-05 parametrized RSS smoke stub (OWLv2 absent per Phase 5 D-10 / RESEARCH F4), replaced by 06-13
- `tests/test_main_args.py` — DET-METRICS-03 CLI reservation stub, replaced by 06-10

## Decisions Made

- Followed Phase 5 Plan 04 canonical stub body verbatim (docstring → `import pytest` → `pytest.skip(..., allow_module_level=True)`), so the scaffold matches existing precedent at `tests/integration/test_detector_crash_fallback.py`.
- Created `tests/contract/` as a brand-new pytest package — RESEARCH §F5 flagged it as missing and the plan said to create it.
- Did NOT recreate `tests/integration/__init__.py` — already present, per plan instructions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan verification statement expects "9 skipped" but only 7 test stubs exist**
- **Found during:** Overall verification
- **Issue:** The plan's `<verification>` section says `pytest tests/metrics tests/contract tests/integration/test_detections_export.py tests/integration/test_rss_smoke_backends.py tests/test_main_args.py -q` should show "9 `skipped` entries". Actual count is 7 — the plan conflated the total file count (9: 7 test modules + 2 `__init__.py`) with the skip count. `__init__.py` files are package markers and do not trigger pytest skips.
- **Fix:** No code change. All 7 stubs skip correctly at module level; this is the expected healthy state. Per-task acceptance criteria (all explicit counts of `skipped`, `allow_module_level=True`, requirement-ID grep matches) all pass.
- **Files modified:** None (documentation-only clarification)
- **Verification:** `pytest tests/metrics tests/contract tests/integration/test_detections_export.py tests/integration/test_rss_smoke_backends.py tests/test_main_args.py -q` → `7 skipped` (one per test module). Individual task-level counts match exactly (`tests/metrics/` → 2 skipped, `tests/contract/` → 2 skipped, three integration/main-args stubs → 3 skipped).
- **Committed in:** N/A (plan-text mismatch; no code affected)

---

**Total deviations:** 1 documentation clarification (no code deviation)
**Impact on plan:** Zero. All 9 expected files exist with the correct contents. The plan author's count of "9 skipped" appears to have over-counted by 2 (the `__init__.py` package markers). The underlying intent — every Phase 6 test file collectable-but-skipped — is satisfied.

## Issues Encountered

- **Pre-existing pytest collection errors (17) in `tests/perception/` and `tests/slam/`** — unrelated to this plan, confirmed pre-existing via `git stash` baseline check. Logged to `.planning/phases/06-detection-metrics-and-mujoco-gt/deferred-items.md`. Out of scope per SCOPE BOUNDARY rule.

## Self-Check: PASSED

All 9 files confirmed on disk:
- `tests/metrics/__init__.py` — FOUND (0 bytes)
- `tests/metrics/test_detection_metrics_tracker.py` — FOUND
- `tests/metrics/test_mujoco_gt.py` — FOUND
- `tests/contract/__init__.py` — FOUND (0 bytes)
- `tests/contract/test_no_map_in_ui.py` — FOUND
- `tests/contract/test_no_map_in_payload.py` — FOUND
- `tests/integration/test_detections_export.py` — FOUND
- `tests/integration/test_rss_smoke_backends.py` — FOUND
- `tests/test_main_args.py` — FOUND

All 3 task commits present on branch:
- `77dd2f6` — FOUND
- `14fa1d9` — FOUND
- `ff4a282` — FOUND

## Next Phase Readiness

- Wave 1 plans (06-04 MetricsTracker, 06-05 MuJoCoGTExtractor) can start immediately — their target test modules exist as flip-points.
- Wave 2 plans (06-08 payload guard, 06-09 export round-trip) have target test modules ready.
- Wave 3 plan (06-10 CLI reservation) has its target test module ready.
- Wave 5 plans (06-12 grep invariant, 06-13 RSS smoke) have their target test modules ready.
- No blockers introduced by this plan.

---
*Phase: 06-detection-metrics-and-mujoco-gt*
*Completed: 2026-04-15*
