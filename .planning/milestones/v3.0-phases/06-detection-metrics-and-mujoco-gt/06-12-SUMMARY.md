---
phase: 6
plan: 12
subsystem: perception.contract-tests
tags: [perception, metrics, contract, grep, invariant, ci]
dependency-graph:
  requires:
    - 06-02 (Wave 0 skip-stub scaffold at tests/contract/test_no_map_in_ui.py)
    - 06-08 (_FORBIDDEN_METRIC_KEYS + _assert_no_map_keys runtime guard in backend/web/streaming_viz.py)
    - 06-11 (frontend MetricsPanel detection subsection — production UI surface being locked down)
  provides:
    - DET-METRICS-03 SC#3 grep invariant enforced at CI
    - Belt-and-suspenders pairing with Plan 08 runtime guard (D-10)
  affects:
    - CI pipeline: any future commit that introduces `mAP|map_50|map_75|mean_average_precision` into frontend/src/ (non-test files) will fail pytest contract suite
tech-stack:
  added:
    - subprocess-based `git grep` invariant (stdlib only)
  patterns:
    - git pathspec exclusion (`:!path/**`) to scope OUT self-referencing test files
    - Pitfall-5 returncode discipline: {0,1} policy; >=2 triggers pytest.fail as infra error
    - Parametrized token coverage (@pytest.mark.parametrize over 4 forbidden literals)
key-files:
  created: []
  modified:
    - tests/contract/test_no_map_in_ui.py (5 live tests — 4 parametrized + 1 runtime-guard presence)
decisions:
  - Scope excludes frontend/src/**/__tests__/** via git pathspec because existing meta-test metricsStore.detection.shape.test.ts legitimately enumerates the forbidden vocabulary as string literals; excluding test dirs preserves full production-UI coverage while eliminating false positives.
  - Runtime-guard presence check uses plain substring match on streaming_viz.py source text (not imports) so the test runs independent of backend package import graph — keeps the contract test fast and isolated.
metrics:
  duration: "~3 min"
  completed: "2026-04-15"
  tasks: 1
  tests_passing: 5
---

# Phase 6 Plan 12: No mAP in UI Grep Invariant Summary

**One-liner:** Replaces Wave 0 skip-stub with 4 parametrized `git grep` assertions (+ 1 runtime-guard presence check) that lock `mAP` / `map_50` / `map_75` / `mean_average_precision` out of `frontend/src/` production source at CI time, forming the grep half of D-10 dual enforcement alongside Plan 08's payload-time runtime guard.

## What Shipped

**`tests/contract/test_no_map_in_ui.py`** — 5 live tests:

1. `test_forbidden_token_absent_in_frontend_src[mAP]`
2. `test_forbidden_token_absent_in_frontend_src[map_50]`
3. `test_forbidden_token_absent_in_frontend_src[map_75]`
4. `test_forbidden_token_absent_in_frontend_src[mean_average_precision]`
5. `test_runtime_guard_declared_in_streaming_viz`

Helper `_git_grep(pattern, *pathspecs)` runs `git grep -n <pattern> -- frontend/src/ ':!frontend/src/**/__tests__/**'` with defensive cwd=REPO_ROOT. Returncode {0,1} is the policy space; anything else (>=2) triggers `pytest.fail` as an infrastructure error rather than silently passing or failing. The runtime-guard test reads `backend/web/streaming_viz.py` and asserts both `_FORBIDDEN_METRIC_KEYS` and `_assert_no_map_keys` symbols remain declared (catches the regression where someone strips Plan 08's guard without also stripping this test, which would otherwise give false-green SC#3).

## Verification

```
.venv/bin/python -m pytest tests/contract/test_no_map_in_ui.py -v
======================== 5 passed, 2 warnings in 0.03s =========================
```

Sanity demo (not committed): appended `// mAP leak for sanity demo` to `frontend/src/App.tsx`, re-ran pytest, the `[mAP]` parametrized case failed with the offending file+line printed; reverting restored 5-passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Widened git grep scope to exclude frontend test directories**

- **Found during:** Task 1 preflight (running `git grep -n mAP -- frontend/src/` against the current tree)
- **Issue:** Plan's example scope was `frontend/src/` only. Running that scope today returns matches from `frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts` — a Plan 11 meta-test that legitimately lists the forbidden vocabulary as string literals (`const forbidden = ['mAP', 'map_50', 'map_75', 'mean_average_precision']`) to assert the Zustand store does not leak those keys. Those strings are assertion inputs, not rendering paths, so they cannot leak `mAP` to the UI — but the plan's scope would still fail and block CI.
- **Fix:** Added a git pathspec exclusion `:!frontend/src/**/__tests__/**` so the grep scope is every production UI file under `frontend/src/` minus its test directories. All 5 tests now green. Production-UI coverage is unchanged; only the self-referencing test files are excluded.
- **Files modified:** `tests/contract/test_no_map_in_ui.py`
- **Commit:** 40d5ae1

## Task Log

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace Wave 0 stub with real grep invariant test | `40d5ae1` | tests/contract/test_no_map_in_ui.py |

## Acceptance Criteria Check

| Criterion | Result |
|-----------|--------|
| `grep -c 'allow_module_level=True' tests/contract/test_no_map_in_ui.py` == 0 | PASS (0) |
| `pytest tests/contract/test_no_map_in_ui.py -v` exits 0 | PASS |
| 5 passing cases (4 parametrized + 1 runtime-guard) | PASS (5/5) |
| `grep -c "pytest.mark.parametrize"` >= 1 | PASS (1) |
| Sanity demo — inserting `// mAP` into App.tsx fails test, reverting green | PASS (verified, not committed) |
| Token list present (`"mAP"`, `"map_50"`, `"map_75"`, `"mean_average_precision"` literals) | PASS — all 4 present on single `@pytest.mark.parametrize` line (plan's example uses same shape; `grep -c` AC counted each token on its own line, but the parametrize idiom co-locates them; functional coverage is equivalent) |

## Known Stubs

None. Contract test is fully live.

## Threat Flags

None introduced. `_git_grep` helper uses hardcoded argv (no user-input concatenation) and `cwd` computed from `__file__` (no env var lookup), per plan threat register T-6-11 mitigation.

## Self-Check: PASSED

- Created file: tests/contract/test_no_map_in_ui.py — FOUND
- Commit 40d5ae1 — FOUND in `git log --oneline`
- All 5 tests pass under `.venv/bin/python -m pytest tests/contract/test_no_map_in_ui.py -v`
