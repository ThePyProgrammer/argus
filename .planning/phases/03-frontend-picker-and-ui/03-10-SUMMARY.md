---
phase: 03
plan: 10
subsystem: frontend
tags:
  - frontend
  - detector-section
  - mount
  - stacked-overlays
requires:
  - 03-02  # CapabilityBadge + RestartOverlay prop extensions
  - 03-04  # detectorStore (Plan 04 Wave 1)
  - 03-07  # DetectorDropdown + LifterDropdown (Wave 2)
  - 03-08  # DetectorParameterPanel + WS restart wiring (Wave 2)
provides:
  - frontend/src/components/DetectorSection.tsx
  - detectorStore.restartSubsystem  # extended per D-12 (Plan 11 extras set includes this)
affects:
  - frontend/src/components/ControlPanel.tsx
  - frontend/src/components/SceneViewer.tsx
tech-stack:
  patterns:
    - "pollForRestart (SLAM-mirror): 500ms × 20 attempts with setError on timeout"
    - "ConfirmModal reuse with per-flow heading/body/labels (D-14)"
    - "D-08 strict `=== false` capability gate (accepts first-render flicker)"
key-files:
  created:
    - frontend/src/components/DetectorSection.tsx
  modified:
    - frontend/src/stores/detectorStore.ts
    - frontend/src/components/ControlPanel.tsx
    - frontend/src/components/SceneViewer.tsx
decisions:
  - "D-12 stacked overlay mounting code path implemented via detectorStore.restartSubsystem discriminator"
  - "WS detector_restart_complete path intentionally does NOT clear restartSubsystem — isRestarting=false already hides overlay; leaves one render of stale discriminator but no visible artifact"
  - "Lifter params UI lives inside LifterDropdown (Wave 2 Plan 07); DetectorParameterPanel is detector-only"
metrics:
  tasks: 3
  files_touched: 4
  completed: 2026-04-14
---

# Phase 03 Plan 10: DetectorSection Parent + ControlPanel Mount + Stacked RestartOverlays Summary

Wire the final user-facing integration for Phase 3 object-detection UI: a parent `DetectorSection` component that owns detector + lifter switch flows, mounted in `ControlPanel` after `AlgorithmSection`, with two new conditional `RestartOverlay` mounts in `SceneViewer` that stack alongside the existing SLAM overlay.

## What Shipped

### Task 1 — detectorStore extension (Plan 04 surface delta)

Added ONE new state field + ONE new setter to `detectorStore.ts`:

- `restartSubsystem: 'detector' | 'lifter' | null` — discriminates which overlay renders when `isRestarting` is true
- `setRestartSubsystem: (subsystem) => void` — setter

Default value: `null`. Non-breaking addition; Plan 11's structural-equivalence Vitest test expects this in the `extras` set alongside the 10 lifter additions (29 total `getState()` keys).

### Task 2 — DetectorSection.tsx (358 lines)

Created `frontend/src/components/DetectorSection.tsx` — exact parallel of `AlgorithmSection.tsx` (231 lines) with BOTH detector AND lifter switch flows in one component:

| Surface | Source | Notes |
|---------|--------|-------|
| Collapsible header "OBJECT DETECTION" | SLAM ALGORITHM style (12px bold #888, chevron) | — |
| `DetectorDropdown` | Plan 07 | `onSelect` opens ConfirmModal |
| Active capability badge row | D-05 keys: `framework`, `license`, `cpu_latency_hint_ms` | Uses extended `CapabilityBadge({label, value})` |
| `LifterDropdown` | Plan 07 | Conditional on `outputs_3d_natively === false` (D-08 strict) |
| Error banner with dismiss | Mirror SLAM | Dismiss sets `error: null` |
| `DetectorParameterPanel` | Plan 08 | Always mounted when section expanded |
| `ConfirmModal` detector switch | D-14 copy: "Switch detector to X? This will restart perception." | `Switch Detector` / `Keep Current` |
| `ConfirmModal` lifter switch | D-14 copy: "Switch lifter to X? This will restart the current session." | `Switch Lifter` / `Keep Current` |

Two local polling fallbacks (D-15):

- `pollForDetectorRestart(expectedBackend)` — 500ms × 20 attempts against `GET /api/detectors/active`
- `pollForLifterRestart(expectedLifter)` — same shape against `GET /api/detectors/active-lifter`

Both fallbacks clear `isRestarting` AND `restartSubsystem` on success or timeout; both set the same timeout error ("Restart timed out. Try again or refresh the page.").

Both `onConfirm*Switch` flows set `setRestarting(true)` + `setRestartSubsystem('detector' | 'lifter')` BEFORE the POST so the overlay mounts immediately, then clear staged params AFTER the POST succeeds.

### Task 3 — ControlPanel + SceneViewer integration

**ControlPanel.tsx** (2 lines added):

```tsx
import DetectorSection from './DetectorSection';   // + new import
// ...
<AlgorithmSection />
<DetectorSection />                                // + new mount
```

D-17 reconciliation: CONTEXT said "Sidebar mount"; `AlgorithmSection` actually lives in `ControlPanel.tsx:184`, so DetectorSection mounts adjacent there. No Sidebar.tsx change.

**SceneViewer.tsx** (import + 4 selectors + 2 new overlay mounts):

```tsx
import { useDetectorStore } from '../stores/detectorStore';
// ...
const detectorRestarting = useDetectorStore((s) => s.isRestarting);
const detectorDisplay = useDetectorStore((s) => s.activeDisplay);
const lifterDisplay = useDetectorStore((s) => s.activeLifterDisplay);
const restartSubsystem = useDetectorStore((s) => s.restartSubsystem);
// ...
{isRestarting && <RestartOverlay subsystem="slam" name={activeDisplay} />}
{detectorRestarting && restartSubsystem === 'detector' && (
  <RestartOverlay subsystem="detector" name={detectorDisplay} />
)}
{detectorRestarting && restartSubsystem === 'lifter' && (
  <RestartOverlay subsystem="lifter" name={lifterDisplay} />
)}
```

D-12 "stacked overlays for concurrent restarts" satisfied: three independent conditional mount sites; each produces its own `RestartOverlay` instance. SLAM + detector + lifter can all render concurrently (all absolute-positioned with the same z-index — D-12 defers pipeline-driven concurrent-restart polish to Phase 7). Detector and lifter are mutually exclusive via the single `restartSubsystem` discriminator during normal operation.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 4ad6948 | feat(03-10): add restartSubsystem to detectorStore for stacked overlays |
| 2 | 943932f | feat(03-10): create DetectorSection parent component |
| 3 | 246c5b6 | feat(03-10): mount DetectorSection + stacked RestartOverlays |

## Deviations from Plan

None — plan executed exactly as written. Only normalization: the DetectorSection file ended up at 358 lines (>240 minimum) because of expanded inline comments documenting each D-ID decision at the relevant code site.

## Known Tradeoffs

**WS `detector_restart_complete` path does not clear `restartSubsystem`:** `useWebSocket.ts` (Plan 08) calls `detectorStore.setRestarting(false)` on WS completion but does not touch `restartSubsystem`. Behavior analysis:

- `isRestarting === false` hides BOTH detector and lifter overlays in SceneViewer's conditional render (first boolean in the `&&` chain).
- `restartSubsystem` retains its last value ('detector' or 'lifter') until the next switch flow sets it.
- No user-visible artifact: the next restart's `setRestartSubsystem(...)` call overwrites it before the overlay re-mounts.
- Polling-fallback paths in DetectorSection DO clear it, so the timeout branch leaves a clean null state.

Accepted. If a future plan needs `restartSubsystem === null` as a post-restart invariant (e.g., for a reducer that cares about completion), wire the clear into `useWebSocket.ts`'s `detector_restart_complete` handler at that time.

## Verification

- `frontend/src/stores/detectorStore.ts`: `grep -c restartSubsystem` → 4 occurrences (state field, interface setter, default value, setter body).
- `frontend/src/components/DetectorSection.tsx`: 358 lines; contains OBJECT DETECTION, `outputs_3d_natively === false`, `pollForDetectorRestart`, `pollForLifterRestart`, `/api/detectors/select`, `/api/detectors/lifter-select`, `Switch Detector`, `Switch Lifter`, `DetectorParameterPanel`, `LifterDropdown`, `setRestartSubsystem` — all 11 required patterns.
- `frontend/src/components/ControlPanel.tsx`: 1× DetectorSection import, 1× `<DetectorSection />` mount.
- `frontend/src/components/SceneViewer.tsx`: detector import present, `restartSubsystem === 'detector'`, `restartSubsystem === 'lifter'`, both new `<RestartOverlay>` mounts.
- `cd frontend && npx tsc --noEmit`: exit 0.
- `cd frontend && npm run build`: exit 0 (246 modules transformed, 1024 kB bundle).

## Phase 3 Success Criteria Status (converged here)

Plan 10 is the Wave 3 integration plan — all 5 Phase 3 criteria funnel through DetectorSection:

| Criterion | Status |
|-----------|--------|
| Detector picker with capability badges | DetectorDropdown (Plan 07) mounted; D-05 badges rendered |
| Lifter dropdown hidden when native 3D | D-08 strict `=== false` gate in DetectorSection |
| Detector parameter panel with debounced WS sends | DetectorParameterPanel (Plan 08) mounted |
| Restart overlay dismisses on `detector_restart_complete` | Primary WS path (Plan 08); polling fallback here |
| RGB 2D bbox overlay per robot | Plan 09 (not this plan) — independent path in CameraFeed |

## Self-Check: PASSED

- [x] detectorStore.ts contains restartSubsystem (4 occurrences)
- [x] DetectorSection.tsx exists (358 lines, all patterns present)
- [x] ControlPanel.tsx imports + mounts DetectorSection
- [x] SceneViewer.tsx imports useDetectorStore + 2 new overlay mounts
- [x] `npx tsc --noEmit` exits 0
- [x] `npm run build` exits 0
- [x] Commits 4ad6948, 943932f, 246c5b6 present in git log
