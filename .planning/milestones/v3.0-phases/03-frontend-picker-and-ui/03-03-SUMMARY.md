---
phase: 03-frontend-picker-and-ui
plan: 03
subsystem: ui
tags: [frontend, react, typescript, ui-primitive, restart-overlay, discriminated-union]

# Dependency graph
requires:
  - phase: 03-frontend-picker-and-ui
    provides: "CapabilityBadge prop generalization (Plan 02) — sibling primitive refactor"
provides:
  - "RestartOverlay subsystem-aware signature: {subsystem: 'slam' | 'detector' | 'lifter', name: string}"
  - "SUBSYSTEM_LABEL map ('slam' -> 'SLAM', 'detector' -> 'detector', 'lifter' -> 'lifter')"
  - "Two SLAM call sites migrated (SceneViewer.tsx:399, pipeline/ApplyBar.tsx:168)"
  - "Foundation for D-12 stacked detector + lifter overlay mounts in Plan 10"
affects: [03-10, 03-frontend-picker-and-ui, detector-restart-overlay, lifter-restart-overlay, pipeline-editor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Discriminated-union prop for subsystem-keyed UI primitives (no string-typed back-compat shim)"
    - "In-place primitive extension over wrapper duplication (per D-11)"

key-files:
  created: []
  modified:
    - frontend/src/components/RestartOverlay.tsx
    - frontend/src/components/SceneViewer.tsx
    - frontend/src/components/pipeline/ApplyBar.tsx

key-decisions:
  - "Treat pipeline-apply as a SLAM restart (subsystem='slam') — pipeline flow restarts the coordinator, matching D-11 + Research Pitfall #3"
  - "No back-compat algorithmName prop — hard-cut migration in same commit set keeps tsc as the gate"
  - "No stacking/z-index logic in the primitive — Plan 10 stacks by mounting separate overlay instances (D-12)"

patterns-established:
  - "Subsystem discriminated-union: 'slam' | 'detector' | 'lifter' (mirrors crash_fallback subsystem discriminator on the WS layer)"
  - "Label map sits next to the type definition so adding a fourth subsystem is a 2-line change (union + map)"

requirements-completed:
  - DET-UI-04

# Metrics
duration: ~4min
completed: 2026-04-14
---

# Phase 3 Plan 03: Restart-overlay subsystem prop Summary

**RestartOverlay rewritten with discriminated-union {subsystem, name} prop (D-11) and both legacy SLAM call sites migrated; tsc clean and zero algorithmName references remain.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-14T07:26:25Z
- **Completed:** 2026-04-14T07:30:31Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- RestartOverlay primitive accepts `{subsystem: 'slam' | 'detector' | 'lifter', name: string}` and renders `Restarting {LABEL} with {name}...` with the SUBSYSTEM_LABEL lookup
- Overlay/spinner/text style objects preserved verbatim (zero visual regression for the SLAM path)
- SceneViewer.tsx:399 SLAM mount migrated to `subsystem="slam" name={activeDisplay}`
- pipeline/ApplyBar.tsx:168 pipeline-apply mount migrated to `subsystem="slam" name="pipeline configuration"` (correctly typed as a SLAM restart per D-11 + Research Pitfall #3)
- `cd frontend && npx tsc --noEmit` exits 0; `grep -rn algorithmName frontend/src` returns no matches

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite RestartOverlay with subsystem + name props** — `98cad7e` (feat)
2. **Task 2: Migrate 2 existing RestartOverlay call sites (SceneViewer + ApplyBar)** — `54c7fdb` (feat)

_All commits used `--no-verify` per parallel-executor convention._

## Files Created/Modified

- `frontend/src/components/RestartOverlay.tsx` — new prop signature + SUBSYSTEM_LABEL; removed `algorithmName`; styles preserved verbatim
- `frontend/src/components/SceneViewer.tsx` — line 399 migrated to `subsystem="slam" name={activeDisplay}`
- `frontend/src/components/pipeline/ApplyBar.tsx` — line 168 migrated to `subsystem="slam" name="pipeline configuration"`

## Decisions Made

- **Pipeline-apply mount uses `subsystem="slam"`** — D-11 + Research Pitfall #3 establish that pipeline-apply IS a SLAM restart (coordinator restart). Keeping the same subsystem keeps the user-facing message accurate (`Restarting SLAM with pipeline configuration...`).
- **Hard-cut migration (no back-compat shim)** — explicitly per the plan's `<action>`. Because both call sites and the primitive land in the same plan and the codebase has only the two legacy call sites, the back-compat prop would only delay tsc-driven cleanup elsewhere.
- **No stacking logic in the primitive** — Plan 10 mounts additional detector/lifter instances; each remains a single overlay element. Stacking is a parent-render concern, not a primitive concern.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed in the order and scope specified; verification (`npx tsc --noEmit`, grep checks) all passed on first run after the edits.

## Issues Encountered

- `npx tsc` initially failed because `frontend/node_modules/` was empty in the worktree. Resolved by running `npm install` (added 100 packages, 2s). This is a worktree-bootstrap nit, not a plan deviation — no source files were affected, no commit was needed.

## Threat Flags

None. The two threats in the plan's `<threat_model>` (T-03-06 React JSX escaping for `name`, T-03-07 TypeScript discriminated union for `subsystem`) are both mitigated as designed: React handles the JSX interpolation escaping by default, and `npx tsc --noEmit` exits 0 — proving the discriminated-union narrowing rejects out-of-band values at compile time. No new attack surface introduced.

## User Setup Required

None — primitive refactor + two in-tree call-site migrations.

## Next Phase Readiness

- **Plan 10 unblocked:** Plan 10 can mount additional `<RestartOverlay subsystem="detector" name={...} />` and `<RestartOverlay subsystem="lifter" name={...} />` instances inside SceneViewer (or wherever the detector store lives) without touching the primitive again. The signature contract is now stable.
- **Plan 11 (useWebSocket wiring) unaffected:** the `detector_restart_complete` handler will set `detectorStore.setRestarting(false)`, which controls whether the new detector overlay mounts — the primitive itself does not need any further changes.
- **No follow-up debt:** zero `algorithmName` references survive in `frontend/src`, so a future grep audit will not turn up legacy usage.

## Self-Check: PASSED

- Created files: none expected for this plan.
- Modified files (verified present on disk):
  - FOUND: frontend/src/components/RestartOverlay.tsx
  - FOUND: frontend/src/components/SceneViewer.tsx
  - FOUND: frontend/src/components/pipeline/ApplyBar.tsx
- Commits (verified via `git log --oneline`):
  - FOUND: 98cad7e (Task 1)
  - FOUND: 54c7fdb (Task 2)
- Verification gate: `cd frontend && npx tsc --noEmit` exited 0; `grep -rn algorithmName frontend/src` returned no matches.

---
*Phase: 03-frontend-picker-and-ui*
*Completed: 2026-04-14*
