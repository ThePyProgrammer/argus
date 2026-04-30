---
phase: 07
plan: 02
subsystem: frontend-tests-scaffold
tags: [vitest, scaffolding, wave-0, perception, pipeline-editor, skip-stubs]
status: complete
requirements: [DET-PIPELINE-01, DET-PIPELINE-02, DET-PIPELINE-03]
wave: 0
depends_on: []
dependency_graph:
  requires:
    - vitest@^4.1.4 (already in frontend/package.json devDependencies)
    - frontend/vitest.config.ts (existing test runner config)
  provides:
    - skip-stub: Plan 07-06 → frontend/src/utils/__tests__/portColors.test.ts (DET-PIPELINE-02)
    - skip-stub: Plan 07-06 → frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts (DET-PIPELINE-03 SC#2)
    - skip-stub: Plan 07-07 → frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts (DET-PIPELINE-01 SC#1)
    - skip-stub: Plan 07-07 → frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts (DET-PIPELINE-01 catalog)
    - skip-stub: Plan 07-08 → frontend/src/stores/__tests__/pipelineStore.dataType.test.ts (DET-PIPELINE-03 SC#2 regression)
    - skip-stub: Plan 07-12 → frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx (D-02 hot-swap UI)
  affects:
    - frontend/vitest.config.ts (extended include glob to .tsx; backwards-compatible)
tech-stack:
  added: []
  patterns:
    - "describe.skip-wrapped vitest stub: file collects + skips cleanly until Wave 2 plan flips .skip → describe and fills assertions"
    - "Top-of-file JSDoc states target Plan + requirement so Wave 2 sampler can grep"
key-files:
  created:
    - frontend/src/stores/__tests__/pipelineStore.dataType.test.ts
    - frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts
    - frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts
    - frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts
    - frontend/src/utils/__tests__/portColors.test.ts
    - frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx
  modified:
    - frontend/vitest.config.ts (Rule 3 deviation: extended include glob to {ts,tsx})
decisions:
  - "Used describe.skip wrapping outer block (rather than per-it.skip) — matches plan template; Wave 2 deletes single token to enable suite."
  - "Every it() body uses expect(false).toBe(true) inside describe.skip — guarantees no accidental passing if .skip is removed without filling in real assertions."
  - "Vitest include glob extended to .tsx (Rule 3 blocking-fix) — D-02 NodeInspector dropdown stub is .tsx because it will import the React component in Plan 07-12; without this extension, vitest silently dropped the file from collection."
metrics:
  duration_minutes: 4
  tasks_completed: 1
  tasks_total: 1
  files_created: 6
  files_modified: 1
  commits: 1
  completed_date: "2026-04-15"
commit_hashes:
  - d52a5b4
---

# Phase 07 Plan 02: Frontend Vitest Skip-Stubs Summary

Six vitest skip-stub files seeded under frontend/src/{stores,utils,components/pipeline}/__tests__/ so Wave 2 perception plans (07-06, 07-07, 07-08, 07-12) inherit ready-to-flip TDD scaffolding.

## What Shipped

Wave 0 frontend half. Six vitest test files land with `describe.skip(...)` wrappers and `expect(false).toBe(true)` placeholders inside each `it()` body:

| # | File | Target Plan | Requirement / Reference |
|---|------|-------------|--------------------------|
| 1 | `frontend/src/stores/__tests__/pipelineStore.dataType.test.ts` | 07-08 | DET-PIPELINE-03 SC#2 (edge dataType bug at pipelineStore.ts:101 + pipelineSerializer.ts:112) |
| 2 | `frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts` | 07-07 | DET-PIPELINE-01 SC#1 (drag+connect across the new perception nodes) |
| 3 | `frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` | 07-06 | DET-PIPELINE-03 SC#2 (`findPortTypeMismatches` + D-09 message format) |
| 4 | `frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts` | 07-07 | DET-PIPELINE-01 catalog (CONTEXT D-03/D-04/D-05/D-06 port sets) |
| 5 | `frontend/src/utils/__tests__/portColors.test.ts` | 07-06 | DET-PIPELINE-02 (UI-SPEC color/shape hex literals) |
| 6 | `frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx` | 07-12 | D-02 hot-swap UI flow (Phase 7 revision iter 1) |

The glob in `frontend/vitest.config.ts` was extended from `*.test.ts` to `*.test.{ts,tsx}` to pick up the `.tsx` stub.

## Verification Run

```
$ cd frontend && npm run test -- --run
 Test Files  2 passed | 6 skipped (8)
      Tests  6 passed | 30 skipped (36)
```

All 6 new files registered, 30 stub assertions skipped, zero failures, zero errors. Existing 2 test files (detectorStore.shape, metricsStore.detection.shape) remain green.

## Acceptance Criteria

- [x] All 6 files exist
- [x] `grep -rc 'describe.skip' frontend/src/stores/__tests__/pipelineStore.dataType.test.ts` → 2 (≥ 1)
- [x] `grep -rc 'describe.skip' frontend/src/utils/__tests__/` → 3 across 3 files (≥ 3 total)
- [x] `grep -rc 'describe.skip' frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx` → 1 (≥ 1)
- [x] `cd frontend && npm run test -- --run` exits 0 with all 6 new files reporting skipped
- [x] No `expect(true).toBe(true)` placeholder — every it() body uses `expect(false).toBe(true)` inside `describe.skip` so accidental flip→pass is impossible
- [x] No production source files modified (only `vitest.config.ts` glob extension — Rule 3)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Vitest include glob did not match `.tsx`**

- **Found during:** Task 1 verify (initial vitest run reported 5/6 files collected — the .tsx was silently dropped).
- **Issue:** `frontend/vitest.config.ts` had `include: ['src/**/__tests__/**/*.test.ts', 'src/**/*.test.ts']` (no .tsx). The plan’s 6th stub is `.tsx` (it will render a React component in Plan 07-12), so vitest never picked it up. The verify command listed the file explicitly but vitest filters explicit args against the include glob.
- **Fix:** Extended both glob entries to `*.test.{ts,tsx}`. Backwards-compatible: every existing `.test.ts` still matches.
- **Files modified:** `frontend/vitest.config.ts`
- **Commit:** d52a5b4

**2. [Rule 3 - Blocking] frontend/node_modules absent in fresh worktree**

- **Found during:** Task 1 verify (`vitest: command not found`).
- **Issue:** Git worktrees do not share `node_modules`; this worktree was newly cut and had no install.
- **Fix:** Ran `npm install` in `frontend/` (163 packages added). Generated `node_modules/` is gitignored — nothing to commit.
- **Files modified:** none
- **Commit:** n/a

No architectural changes (Rule 4) needed. No bugs (Rule 1) or missing critical code (Rule 2) found in scope.

## Authentication Gates

None.

## Decisions Made

- **`describe.skip` wrapping over `it.skip` per `it()`** — matches the plan’s literal template. Wave 2 plans delete a single `.skip` token to enable an entire suite, then fill in real assertions to replace `expect(false).toBe(true)`.
- **`expect(false).toBe(true)` placeholder** — guarantees a failing assertion if a Wave 2 contributor removes `.skip` without writing the real test. This is the inverse of the common `expect(true).toBe(true)` no-op trap.
- **Vitest glob extension is backwards-compatible** — `*.test.{ts,tsx}` is a strict superset of `*.test.ts`, so existing tests keep matching exactly as before.

## Threat Flags

None — only test scaffolding under `__tests__/` directories. No new network endpoints, no auth paths, no schema or serialization changes. The vitest config change is dev-only.

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: frontend/src/stores/__tests__/pipelineStore.dataType.test.ts
- FOUND: frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts
- FOUND: frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts
- FOUND: frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts
- FOUND: frontend/src/utils/__tests__/portColors.test.ts
- FOUND: frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx

**Commits verified:**
- FOUND: d52a5b4 (test(07-02): add 6 vitest skip-stubs for Wave 2 perception sampling)
