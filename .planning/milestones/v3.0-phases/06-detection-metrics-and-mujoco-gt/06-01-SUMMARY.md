---
phase: 06-detection-metrics-and-mujoco-gt
plan: 01
subsystem: infra
tags: [pyproject, dependencies, pyyaml, perception-extra]

# Dependency graph
requires: []
provides:
  - Explicit PyYAML>=6.0 declaration in [project.optional-dependencies].perception
  - Officially-declared import path for yaml.safe_load in downstream perception code
affects:
  - 06-05 (MuJoCoGTExtractor — uses yaml.safe_load on scene GT YAML)
  - any future perception-extra consumer importing yaml

# Tech tracking
tech-stack:
  added:
    - PyYAML>=6.0 (promoted from implicit system install to explicit perception extra)
  patterns:
    - "All runtime yaml.safe_load call sites must be backed by an explicit manifest declaration (no relying on transitive/system installs)"

key-files:
  created: []
  modified:
    - pyproject.toml (append single entry to perception extra, no reorder, no touch to dependencies)

key-decisions:
  - "Declare PyYAML under the perception extra (not base dependencies) because yaml is only needed by the perception subsystem (MuJoCoGTExtractor scene GT mapping)."
  - "Append at end of list, preserving trailing-comma style and existing entry order."

patterns-established:
  - "Manifest-first: before any new runtime import is landed in src/, it must appear in pyproject.toml (prevents 'works on my machine' breakage for devs installing only declared extras)."

requirements-completed: [DET-METRICS-02]

# Metrics
duration: 2min
completed: 2026-04-15
---

# Phase 6 Plan 1: PyYAML Declaration Summary

**PyYAML>=6.0 declared in `pyproject.toml` `[project.optional-dependencies].perception` so downstream Plan 05 (`MuJoCoGTExtractor`) can rely on `import yaml` being an officially-declared dependency rather than a system-install coincidence.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-15T07:41:30Z
- **Completed:** 2026-04-15T07:43:29Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `"PyYAML>=6.0"` as the 7th entry of the `perception` optional-dependencies list.
- Verified `pyproject.toml` still parses cleanly via `tomllib.load`.
- Verified `dependencies` list (base) is unchanged — no scope leakage.

## Task Commits

1. **Task 1: Add PyYAML to perception extra** — `af7ca10` (chore)

## Files Created/Modified

- `pyproject.toml` — Append `"PyYAML>=6.0",` to the `perception` optional-dependencies list (single-line addition, no reorder).

## Decisions Made

- Placed under `perception` extra rather than base `dependencies`: yaml is only consumed by the perception subsystem (MuJoCoGTExtractor scene GT mapping in Plan 05); base-install users who never touch perception do not need the dep.
- Pin `>=6.0` (not a hard equality): PyYAML 6.x is API-stable for `safe_load`; avoids churn from minor bumps.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Verification Evidence

```
$ grep -c 'PyYAML>=6.0' pyproject.toml
1

$ python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb'));
             assert d['project']['optional-dependencies']['perception'][-1] == 'PyYAML>=6.0';
             print('perception length:', len(d['project']['optional-dependencies']['perception']));
             print('dependencies length:', len(d['project']['dependencies']))"
perception length: 7
dependencies length: 9
```

- `perception` grew 6 → 7 (expected).
- `dependencies` length stable at 9 (unchanged).
- `PyYAML>=6.0` is the final entry (matches success-criteria assertion in PLAN.md).
- `git diff` confirmed: single-line addition, no other sections touched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 05 (`MuJoCoGTExtractor`) can now safely `import yaml` under the perception extra.
- No blockers introduced.

## Self-Check: PASSED

- `pyproject.toml` modification present: FOUND (contains `PyYAML>=6.0`, tomllib-valid)
- Task 1 commit `af7ca10`: FOUND in `git log`
- No stub patterns introduced (no UI-rendering or placeholder code in scope)
- No new threat surface introduced (build-manifest edit only; threat register T-6-01 confirms N/A, T-6-04 transferred to Plan 05)

---
*Phase: 06-detection-metrics-and-mujoco-gt*
*Completed: 2026-04-15*
