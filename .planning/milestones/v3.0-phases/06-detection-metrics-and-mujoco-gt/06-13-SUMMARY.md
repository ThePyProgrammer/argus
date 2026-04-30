---
phase: 6
plan: 13
subsystem: perception
tags: [perception, metrics, rss, memory, parametrize, backends, smoke-test]
requires:
  - DET-METRICS-05
  - CONTEXT D-15 (parametrize shape)
  - CONTEXT D-16 (CI fast tier filter)
  - RESEARCH Pitfall 7 (measurement ordering)
  - RESEARCH F4 (OWLv2 supersession)
  - src.perception.registry.DetectorRegistry.create
  - src.perception.backends.{yolov11_backend,rtdetrv2_backend,boxer_backend}
  - psutil>=7.0
  - pytest-timeout
  - pytest marker "slow_boxer" declared in pytest.ini
provides:
  - tests/integration/test_rss_smoke_backends.py (parametrized RSS smoke, 3 backends)
affects:
  - CI fast tier: `pytest -m "not slow_boxer"` now exercises yolov11 RSS cap on every run
  - CI nightly tier: `pytest -m slow_boxer` exercises BoxeR RSS cap when venv provisioned
  - tests/smoke/test_detector_rss.py is now a superseded legacy (YOLOv11-only); follow-up cleanup will remove it
tech-stack:
  added: []
  patterns:
    - pytest.mark.parametrize + pytest.param(marks=[...]) for per-case skipif + slow_boxer layering
    - honest-skip over pytest.fail on missing model artifacts (CI green on fresh clone)
    - Pitfall 7 RSS probe ordering: warmup → gc → rss_before → N inferences → gc → rss_after
    - try/finally backend.close() cleanup for subprocess-isolated BoxeR
key-files:
  created: []
  modified:
    - tests/integration/test_rss_smoke_backends.py  # Wave 0 stub → real parametrized test
decisions:
  - "OWLv2 absence documented in module docstring citing Phase 5 D-10 + RESEARCH F4 — ROADMAP SC#5 said 4 backends, reality is 3"
  - "Module-scope side-effect import `src.perception.backends` to trigger @detector_backend registration before parametrize resolves"
  - "Fixture falls back to synthetic RGBD when tests/fixtures/yolo_regression_scene_01.npz absent — smoke test stays runnable on a fresh clone"
  - "200 MB cap literal (200 * 1024 * 1024), not 400 MB fail threshold from legacy Phase 1 smoke — CONTEXT D-15 locks 200 MB as the single assert bound"
  - "Module-scope fixture (`scope=\"module\"`) for fixture_frame to avoid 480×640 RGBD re-allocation per parametrize case"
metrics:
  duration: "~6 min"
  completed: "2026-04-15"
  tasks: 1
  files_modified: 1
  commits: 1
---

# Phase 6 Plan 13: Parametrized RSS Smoke Across Backends Summary

DET-METRICS-05 SC#5 enforcement: parametrized RSS smoke test at
`tests/integration/test_rss_smoke_backends.py` covering YOLOv11 (always),
RT-DETRv2 (honest-skip on missing ONNX), BoxeR (opt-in via `slow_boxer`
marker + honest-skip on missing venv); 100 inferences post-warmup, 200 MB
growth cap per backend; OWLv2 intentionally absent per Phase 5 D-10.

## One-liner

Replaced Wave 0 skip-stub with a 3-backend parametrized pytest smoke that
asserts RSS growth ≤ 200 MB over 100 inferences, with honest-skip on
missing artifacts and a `slow_boxer` opt-in gate for the subprocess-isolated
BoxeR case.

## What Shipped

**`tests/integration/test_rss_smoke_backends.py`** (replacement, 164 insertions / 9 deletions)

- Parametrize spec (verbatim from CONTEXT D-15):
  - `"yolov11"` — always runs
  - `pytest.param("rtdetrv2", marks=pytest.mark.skipif(not _rtdetrv2_artifact_present(), reason="run `make download-models-rtdetrv2`"))`
  - `pytest.param("boxer", marks=[pytest.mark.slow_boxer, pytest.mark.skipif(not _boxer_ready(), reason="run `bash scripts/setup_boxer_subprocess.sh`")])`
- Artifact presence probes:
  - `_rtdetrv2_artifact_present()` → `(models/rtdetrv2).glob("*/model.onnx")` truthy
  - `_boxer_ready()` → `subprocess_venvs/boxer/.ready` exists
- RSS probe ordering (Pitfall 7):
  1. `DetectorRegistry.create(backend_id)`
  2. `backend.warmup(fixture_frame)`
  3. `gc.collect()`
  4. `process.memory_info().rss` → `rss_before`
  5. `for _ in range(100): backend.process_frame(fixture_frame)`
  6. `gc.collect()`
  7. `process.memory_info().rss` → `rss_after`
  8. `assert (rss_after - rss_before) < 200 * 1024 * 1024`
- Cleanup: `try/finally` calls `backend.close()` if present (BoxeR subprocess reaping)
- Fixture: module-scope `fixture_frame` reusing `tests/fixtures/yolo_regression_scene_01.npz`
  when available, synthetic 480×640 RGBD fallback otherwise
- Module-level `import src.perception.backends` to trigger
  `@detector_backend` side-effect registration before parametrize resolves

## OWLv2 Absence (Documented)

Module docstring cites the supersession:

> "OWLv2 is INTENTIONALLY absent. ROADMAP Phase 6 SC#5 lists 'YOLOv11,
> RT-DETRv2, OWLv2, BoxeR' but Phase 5 D-10 (2026-04-15) dropped OWLv2
> from the pluggable pipeline — see RESEARCH F4."

Grep verification: `F4|D-10` matches ≥ 1 in the module.

## Verification Output

```
$ pytest tests/integration/test_rss_smoke_backends.py --collect-only -q -m ""
tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[yolov11]
tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[rtdetrv2]
tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[boxer]
3 tests collected

$ pytest tests/integration/test_rss_smoke_backends.py -m "not slow_boxer" -v --timeout=300
tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[yolov11] PASSED [ 50%]
tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[rtdetrv2] SKIPPED [100%]
=========== 1 passed, 1 skipped, 1 deselected, 2 warnings in 20.63s ============
```

- yolov11 case: PASSED within 200 MB cap
- rtdetrv2 case: SKIPPED with honest-skip reason ("RT-DETRv2 ONNX model
  missing; run `make download-models-rtdetrv2`") — artifact absent on
  this worktree, expected behavior per D-15
- boxer case: DESELECTED by `not slow_boxer` marker filter — expected
  CI fast-tier behavior per D-16

## Acceptance Criteria Checklist

- [x] `grep -c 'allow_module_level=True'` = 0 (stub eliminated)
- [x] `grep -c 'parametrize'` = 4 (docstring + decorator + 2 incidental)
- [x] `grep -cE '"yolov11"|"rtdetrv2"|"boxer"'` = 5 (each id appears once in parametrize + docstring mentions)
- [x] `grep -c 'slow_boxer'` = 2 (docstring mention + marker use)
- [x] `grep -c 'gc.collect'` = 4 (docstring explanations + 2 real calls)
- [x] `grep -c '200 \* 1024 \* 1024'` = 1 (the `RSS_GROWTH_CAP_BYTES` literal)
- [x] `grep -c 'F4\|D-10'` = 3 (OWLv2 supersession cited)
- [x] `pytest --collect-only -m ""` lists 3 parametrized cases
- [x] `pytest -m "not slow_boxer"` exits 0 (1 passed, 1 skipped, 1 deselected)
- [x] No OWLv2 entry in parametrize list (zero `"owlv2"` backend id)

## Deviations from Plan

**None substantive.** Plan executed as written with two minor refinements:

1. **Synthetic-frame fallback** — the PLAN action block suggested importing
   `build_fixture_frame()` from `tests.smoke.test_detector_rss`, but that
   file does not export such a function. I inlined the equivalent fixture
   construction and added a synthetic-frame fallback so the smoke stays
   runnable on fresh clones without the `.npz` artifact. Matches the
   PLAN's stated "if not exported, extract fixture-construction lines
   directly" fallback path. Not tracked as a Rule-N deviation because it
   is the PLAN's own branch.
2. **Seed literal fix** — transient authoring typo `0xA12U` flagged as
   `SyntaxError: invalid hexadecimal literal` during first pytest
   collection; corrected inline to `0xA12` before the final commit.
   Pre-commit internal fix; not a Rule-N deviation.

No authentication gates encountered. No architectural escalations.

## Known Stubs

None. Every parametrized case either runs the real 100-inference loop or
honest-skips with an actionable remediation hint. No hardcoded empty
placeholder values flow to any consumer.

## Threat Flags

None. This plan only adds a test module; no new network surface, auth
paths, or filesystem-write behavior are introduced. T-6-12 (DoS via BoxeR
subprocess hang) is mitigated as specified — `try/finally` reaps the
subprocess via `backend.close()`, and the `slow_boxer` tier is expected
to run with `--timeout=900` in nightly CI per Phase 5 precedent.

## Commits

- `1a01734` test(06-13): parametrized RSS smoke over yolov11/rtdetrv2/boxer

## Self-Check: PASSED

- FOUND: tests/integration/test_rss_smoke_backends.py (modified, 164 insertions)
- FOUND: commit 1a01734 in git log
- VERIFIED: pytest collection shows 3 parametrized cases
- VERIFIED: pytest `-m "not slow_boxer"` exits 0 (yolov11 pass, rtdetrv2 skip, boxer deselect)
- VERIFIED: all 10 success-criteria grep checks pass
