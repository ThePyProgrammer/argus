---
phase: 03
plan: 08
subsystem: frontend-picker-and-ui
tags:
  - frontend
  - parameter-panel
  - websocket-wiring
  - detector
requirements:
  - DET-UI-03
  - DET-UI-04
requires:
  - frontend/src/stores/detectorStore.ts (Plan 03-04)
  - frontend/src/components/ParameterPanel.tsx (SLAM clone template)
  - frontend/src/stores/controlStore.ts (sendRaw)
  - frontend/src/utils/debounce.ts
  - frontend/src/components/SliderField.tsx
provides:
  - DetectorParameterPanel component (debounced detector_param_update WS sender)
  - WS-driven restart-overlay dismissal via detector_restart_complete -> detectorStore.setRestarting(false)
affects:
  - Plan 10 DetectorSection (will mount DetectorParameterPanel + rely on WS-driven overlay dismissal with polling fallback)
tech-stack:
  added: []
  patterns:
    - "getState() inside debounce closure (fresh sendRaw reference across WS reconnects)"
    - "live_tunable split: debounced WS send vs stageParam"
    - "defensive narrow-cast for forward-compatible WS payload enrichment"
key-files:
  created:
    - frontend/src/components/DetectorParameterPanel.tsx
  modified:
    - frontend/src/hooks/useWebSocket.ts
decisions:
  - "DetectorParameterPanel is a verbatim clone of ParameterPanel with only store-binding + WS type string renamed (D-01 clone-and-rename strategy); no shared abstraction"
  - "detector_restart_complete handler now drives detectorStore.setRestarting(false) + fetchDetectorState(); polling fallback in Plan 10 becomes a genuine backup path"
  - "detector_param_ack stays log-only for Phase 3 — Phase 6 MetricsPanel will surface errors (per plan scope)"
metrics:
  tasks: 2
  files_changed: 2
  files_created: 1
  files_modified: 1
  completed: 2026-04-14
---

# Phase 3 Plan 08: DetectorParameterPanel + useWebSocket Wiring Summary

DetectorParameterPanel clones SLAM's ParameterPanel 1:1 with only the store binding and WS message type renamed; useWebSocket now drives detectorStore on `detector_restart_complete` instead of logging.

## Scope

Two small, surgical pieces of the detector control surface that don't need DetectorSection's wrapper:

1. `DetectorParameterPanel.tsx` — 109-line clone of `ParameterPanel.tsx` with exactly four renames applied. Same live_tunable split, same debounce closure, same SliderField + boolean toggle, same "No tunable parameters" fallback.

2. `useWebSocket.ts` — extend the one-case `detector_restart_complete` handler from log-only (Phase 2 scaffolding) to actually drive `useDetectorStore.getState().setRestarting(false) + fetchDetectorState()`. Defensive narrow-cast on the `lifter` payload field so Plan 06's enrichment doesn't require touching `messageTypes.ts` in this plan.

## What Shipped

### Task 1 — DetectorParameterPanel clone (commit `d984d1a`)

Copied `frontend/src/components/ParameterPanel.tsx` (109 lines) verbatim, then applied four whole-file renames:

| From | To |
|------|----|
| `from '../stores/slamStore'` | `from '../stores/detectorStore'` |
| `useSlamStore` | `useDetectorStore` |
| `'slam_param_update'` | `'detector_param_update'` |
| `ParameterPanel` (fn name + export) | `DetectorParameterPanel` |

Structural invariants preserved:

- `debouncedSendParam` defined at module top, fetching `useControlStore.getState().sendRaw` *inside* the closure (Research §Anti-Patterns — fresh reference across WS reconnects). Only the `type:` string changed.
- `handleParamChange(key, value, liveTunable)` always calls `updateActiveParam`, then branches: `liveTunable === true` → `debouncedSendParam`; else → `stageParam`.
- `humanize()`, SliderField rendering, boolean toggle, "No tunable parameters" empty-state fallback — all unchanged.
- Selectors wired to Plan 04's detectorStore: `backends`, `activeBackend`, `activeParameters` (all already present in that store).

File is exactly 109 lines (same as the SLAM template); tsc clean.

### Task 2 — useWebSocket detector_restart_complete wiring (commit `b7a26e6`)

Two edits:

1. Added import alongside SLAM equivalent:
   ```typescript
   import { useDetectorStore, fetchDetectorState } from '../stores/detectorStore';
   ```

2. Replaced the log-only handler at the `detector_restart_complete` case with:
   ```typescript
   case 'detector_restart_complete': {
     const payload = msg.payload as DetectorRestartCompletePayload;
     useDetectorStore.getState().setRestarting(false);
     fetchDetectorState();
     const lifter = (payload as DetectorRestartCompletePayload & { lifter?: string }).lifter;
     console.log(`[detector] restart complete: ${payload.backend}${lifter ? ' / lifter=' + lifter : ''}`);
     break;
   }
   ```

The `lifter` narrow-cast is defensive — Plan 06 enriches the backend payload to `{backend, lifter}`, but `messageTypes.ts::DetectorRestartCompletePayload` currently only has `backend`. The cast keeps this plan's diff minimal and leaves the message type update to Plan 10 if needed.

`detector_param_ack` handler left untouched (log-only) — Phase 6 MetricsPanel concern.

## Interaction With Other Plans

| Plan | Relationship |
|------|-------------|
| 03-04 | Consumer — this plan calls `setRestarting`, `updateActiveParam`, `stageParam`, `fetchDetectorState` on Plan 04's detectorStore |
| 03-06 | Backend counterpart — Plan 06 enriches the `detector_restart_complete` WS payload with `{backend, lifter}`; the narrow-cast here accepts that enrichment without requiring type changes |
| 03-10 | Consumer — Plan 10's DetectorSection mounts `<DetectorParameterPanel />`. Plan 10's polling-fallback becomes a genuine backup path (WS-driven dismissal is now primary) |

## Verification

```
cd frontend && npx tsc --noEmit
```

Exit code 0 after each task.

Acceptance criteria grep checks (Task 1):

- `export function DetectorParameterPanel` present
- `useDetectorStore` present, `useSlamStore` absent
- `'detector_param_update'` present, `'slam_param_update'` absent
- `debounce`, `SliderField`, `stageParam` all present

Acceptance criteria grep checks (Task 2):

- Exactly 1 import line for `{ useDetectorStore, fetchDetectorState }`
- `useDetectorStore.getState().setRestarting(false)` present
- `fetchDetectorState()` present
- `detector_restart_complete` case no longer log-only (3+ lines of wiring before the `console.log`)

## Deviations from Plan

None — both tasks executed exactly as written. No Rule 1/2/3 auto-fixes triggered; no architectural surprises.

Infrastructure note: The working tree was missing Plan 04's `detectorStore.ts` on arrival due to the soft-reset to `ebba012` (parallel-execution base). Checking the file back out from the base commit was pure environment setup, not a deviation from plan intent. `frontend/node_modules` was also absent; `npm install` was run before `tsc`.

## Authentication Gates

None — pure frontend typescript changes.

## Threat Flags

None — this plan only touches already-public WS message types (`detector_param_update` is Phase 2's existing backend route; `detector_restart_complete` is Phase 2's existing WS message). No new trust boundaries.

## Known Stubs

None. Both files wire to real, in-tree data sources:

- `DetectorParameterPanel` reads from `useDetectorStore` (populated by `fetchDetectorState()` on mount via DetectorSection in Plan 10).
- `useWebSocket` wires to the already-populated `useDetectorStore` state.

## Metrics

- **Tasks:** 2/2 completed
- **Files created:** 1 (`DetectorParameterPanel.tsx`, 109 lines)
- **Files modified:** 1 (`useWebSocket.ts`, +6/-2)
- **Commits:** `d984d1a`, `b7a26e6`
- **tsc:** clean at each task boundary

## Self-Check: PASSED

- `frontend/src/components/DetectorParameterPanel.tsx` — FOUND (109 lines)
- `frontend/src/hooks/useWebSocket.ts` — modified in place, grep checks pass
- Commit `d984d1a` — FOUND in git log
- Commit `b7a26e6` — FOUND in git log
- `cd frontend && npx tsc --noEmit` — exits 0
