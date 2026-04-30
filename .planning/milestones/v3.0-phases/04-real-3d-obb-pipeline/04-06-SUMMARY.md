---
phase: 04
plan: 06
subsystem: frontend
tags:
  - frontend
  - hotswap
  - ui
  - wave-4
dependency_graph:
  requires:
    - "04-05"  # backend /api/detectors/lifter-hotswap route
  provides:
    - "SC#5 UI wiring: lifter-switch dropdown POSTs to hot-swap route with no restart overlay"
  affects:
    - "frontend/src/components/DetectorSection.tsx"
tech_stack:
  added: []
  patterns:
    - "Fire-and-forget fetchDetectorState() post hot-swap to refresh active-lifter display (Pattern Template 5)"
    - "Hot-swap clears stagedLifterParams only on 200 OK; failed swaps preserve staged params for retry"
key_files:
  created: []
  modified:
    - frontend/src/components/DetectorSection.tsx
decisions:
  - "Kept restartSubsystem union type as 'detector' | 'lifter' | null — 'lifter' is dead-code at runtime after this plan but stays in the union to minimize Plan 06 blast radius (per Research Pattern Template 5 note)"
  - "No overlay on hot-swap failure — error banner only, matching synchronous UX"
metrics:
  duration_minutes: 5
  completed: 2026-04-14
  tasks_completed: 1
  files_changed: 1
  commits: 1
requirements:
  - DET-3D-01
---

# Phase 04 Plan 06: DetectorSection Lifter Hot-Swap Redirect — Summary

**One-liner:** Rewired `DetectorSection.tsx` lifter-switch flow from the deleted
`/lifter-select` restart-route onto Plan 05's synchronous
`POST /api/detectors/lifter-hotswap`, deleting `pollForLifterRestart` and all
lifter-path restart-overlay triggers while leaving the detector-switch flow
(D-02, still restarts) untouched.

## Objective Recap

Phase 4 Decision D-09 supersedes Phase 3's `/lifter-select` restart pattern
with an in-place hot-swap: the session stays running, the active lifter is
replaced under a pool lock, and the UI never sees a restart event for lifter
changes. Plan 05 delivered the backend route. This plan is the one-file
frontend rewire that makes the UI consume it.

## Deliverables

| Artifact | Change | Result |
|----------|--------|--------|
| `frontend/src/components/DetectorSection.tsx` | Modified | 14 insertions, 40 deletions; lifter flow no longer mounts restart overlay |

## Code Changes

### `frontend/src/components/DetectorSection.tsx`

**Deleted (40 lines):**
- `pollForLifterRestart(expectedLifter)` function (previously lines 45-69) — the
  synchronous hot-swap route makes polling meaningless.
- From `onConfirmLifterSwitch`:
  - `setRestarting(true)` and `setRestartSubsystem('lifter')` (no restart
    semantics on the lifter path anymore).
  - The matching `setRestarting(false)` / `setRestartSubsystem(null)` in the
    `!res.ok` and `catch` branches (none to clear because none were set).
  - The `pollForLifterRestart(pendingLifter)` call site.

**Added (14 lines):**
- Header docstring block updated to explain that only the detector path polls,
  citing Phase 4 D-09 for the lifter hot-swap contract.
- `onConfirmLifterSwitch` body rewritten to POST
  `/api/detectors/lifter-hotswap`, with a `fetchDetectorState()` call on 200 OK
  to refresh the active-lifter display via the existing store pipeline.
- `ConfirmModal` body copy for lifter-switch: replaced
  `"This will restart the current session."` with
  `"This is an instant swap (no restart)."`.

**Unchanged (preserved per plan):**
- `pollForDetectorRestart` + `onConfirmDetectorSwitch` + detector
  `ConfirmModal` copy — the detector switch still restarts per D-02.
- `onDetectorSelect`, `onLifterSelect` trigger callbacks.
- `restartSubsystem: 'detector' | 'lifter' | null` type union in
  `detectorStore.ts`: `'lifter'` is now dead at runtime but retained for
  type compatibility (Research Pattern Template 5 note).

## Acceptance Criteria

All plan-defined grep invariants pass:

| Invariant | Expected | Actual |
|-----------|----------|--------|
| `/api/detectors/lifter-hotswap` occurrences | 1 | 1 |
| `/api/detectors/lifter-select` occurrences | 0 | 0 |
| `pollForLifterRestart` occurrences | 0 | 0 |
| `setRestartSubsystem('lifter')` occurrences | 0 | 0 |
| `"This will restart the current session"` occurrences | 0 | 0 |
| `"instant swap (no restart)"` occurrences | 1 | 1 |
| `pollForDetectorRestart` occurrences (function + call) | >=2 | 2 |
| `/api/detectors/select` occurrences | 1 | 1 |
| `npx tsc --noEmit` exit status | 0 | 0 (0 `error TS` lines) |

## Verification

- **Typecheck:** `cd frontend && npx tsc --noEmit` → exit 0, 0 errors. Log
  captured at `/tmp/tsc_04_06.log` during execution.
- **Manual verification** (UI): deferred to Plan 07 MuJoCo integration per
  `04-VALIDATION.md` Manual-Only Verification row 1. Plan 07's integration
  test will script a lifter swap via the UI route and observe OBB rotation
  change to close SC#5 end-to-end.

## Deviations from Plan

None — plan executed exactly as written. Task 1's `action` block was applied
verbatim (3 targeted edits in `DetectorSection.tsx`: delete polling helper,
rewrite `onConfirmLifterSwitch`, update modal copy). No auto-fixes, no
architectural changes, no scope expansion.

**Note on missing tooling:** The worktree did not have `node_modules` installed
prior to verification, so `npx tsc` initially failed to resolve the local
TypeScript. Running `npm install --no-audit --no-fund` (163 packages, 2s)
before the typecheck is a workflow adjustment, not a code deviation — no file
outside the worktree's `frontend/node_modules/` cache changed. Tracked here
only for reproducibility (future agents in fresh worktrees should run
`npm install` in `frontend/` before `tsc --noEmit`).

## Threat Model Follow-Through

All four threats from the plan's register are covered by the executed code:

| Threat ID | Status |
|-----------|--------|
| T-04-25 (Tampering via removed /lifter-select) | Mitigated — grep invariant confirms `/lifter-select` absent from the component |
| T-04-26 (DoS via double-click) | Accepted — `confirmDisabled={switching}` still gates the modal button |
| T-04-27 (503 pool-not-ready) | Mitigated — error banner surfaces on `!res.ok` |
| T-04-28 (Stale stagedLifterParams after failed swap) | Mitigated — `clearStagedLifterParams()` runs only on the 200 OK branch |

No new security surface introduced; no threat flags.

## Known Stubs

None. The component is fully wired to both the detector-switch and
lifter-hot-swap backend routes; the detector store provides real data.

## Commits

| Hash | Message |
|------|---------|
| 8437b82 | feat(04-06): redirect lifter switch to /lifter-hotswap, drop restart path |

## Self-Check: PASSED

- `frontend/src/components/DetectorSection.tsx` exists and contains
  `/api/detectors/lifter-hotswap` (verified via grep above).
- Commit `8437b82` exists on `worktree-agent-aa1810b2`
  (`git log --oneline -1` confirms).
- No other files modified; `git status --short` is clean post-commit.
- `tsc --noEmit` exits 0 with 0 errors (captured above).
