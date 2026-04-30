---
phase: 03
plan: 07
subsystem: frontend
tags:
  - frontend
  - ui-component
  - dropdown
dependency-graph:
  requires:
    - 03-02  # CapabilityBadge {label, value} signature
    - 03-04  # useDetectorStore + DetectorBackend / LifterBackend types
  provides:
    - DetectorDropdown component (DET-UI-01 option-row surface)
    - LifterDropdown component (DET-UI-02 base; Plan 10 owns visibility gate)
  affects:
    - frontend/src/components/DetectorDropdown.tsx (new)
    - frontend/src/components/LifterDropdown.tsx (new)
tech-stack:
  added: []
  patterns:
    - clone-and-rename (D-01) — no generic BackendDropdown<T> refactor
    - compile-time typed capability badge keys (Array<keyof Backend['capabilities']>)
key-files:
  created:
    - frontend/src/components/DetectorDropdown.tsx
    - frontend/src/components/LifterDropdown.tsx
  modified: []
decisions:
  - Re-used AlgorithmDropdown.tsx DOM + style objects verbatim (D-01 clone fidelity)
  - Declared BADGE_KEYS / LIFTER_BADGE_KEYS as module-level typed arrays so the TS compiler catches capability-key drift
  - Kept unavailable-backend rendering (opacity 0.4 + reason tooltip) identical across all three dropdowns
  - Badge divergence: Detector = framework/license/cpu_latency_hint_ms (D-06); Lifter = license/outputs_oriented (D-05-analogous)
  - Visibility gate kept OUT of LifterDropdown (owned by Plan 10 DetectorSection per D-07/D-08)
metrics:
  duration: "~1.5min"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  completed-date: 2026-04-14
---

# Phase 3 Plan 7: DetectorDropdown + LifterDropdown Summary

**One-liner:** Cloned AlgorithmDropdown into DetectorDropdown (3-key capability-badge pack: framework, license, cpu_latency_hint_ms) and LifterDropdown (2-key pack: license, outputs_oriented), both wired to the Wave 1 `useDetectorStore` with identical unavailable-backend greyed-tooltip behavior.

## Objective

Deliver DET-UI-01 option-row surface and DET-UI-02 lifter picker as two standalone components ready for Plan 10's DetectorSection mount. Strict clone-and-rename strategy (D-01) — no generic refactor, zero risk to existing SLAM UX.

## Clone Lineage

```
AlgorithmDropdown.tsx (149 lines, Wave 0 baseline)
    │
    ├── clone + rename slamStore → detectorStore
    │   + switch badge-row rendering from boolean-filter to 3-key typed pack
    │   → DetectorDropdown.tsx (154 lines)
    │
    └── (via Task 2)
        clone + rename DetectorDropdown → LifterDropdown
        + switch selectors to lifters/activeLifter/activeLifterDisplay
        + swap 3-key badge pack for 2-key (license, outputs_oriented)
        → LifterDropdown.tsx (155 lines)
```

Both files sit alongside `AlgorithmDropdown.tsx` in `frontend/src/components/` with no cross-imports — each is self-contained.

## Tasks Executed

### Task 1: DetectorDropdown
- **Commit:** `e7a2693`
- **File:** `frontend/src/components/DetectorDropdown.tsx` (154 lines)
- **Key changes vs template:**
  - `useSlamStore` → `useDetectorStore` (selectors: `backends`, `activeBackend`, `activeDisplay`)
  - Imported `DetectorBackend` type from `../stores/detectorStore` for badge-key typing
  - Replaced the boolean-filter capability rendering with a typed `BADGE_KEYS: Array<keyof DetectorBackend['capabilities']>` array: `['framework', 'license', 'cpu_latency_hint_ms']`
  - Badge row now always renders (the `CapabilityBadge` D-04 rules drop missing/`undefined`/`false` values), so we removed the `capabilities.length > 0` guard — still a no-op for backends lacking any of the three keys
  - Kept verbatim: trigger style, list style, click-outside / Escape handlers, active-highlight left-border, unavailable opacity/title tooltip
- **tsc:** clean (no new errors above baseline)

### Task 2: LifterDropdown
- **Commit:** `4a52fbc`
- **File:** `frontend/src/components/LifterDropdown.tsx` (155 lines)
- **Key changes vs Task 1 output:**
  - All `DetectorDropdown` names → `LifterDropdown`
  - Store selectors: `backends` → `lifters`, `activeBackend` → `activeLifter`, `activeDisplay` → `activeLifterDisplay`
  - Loop variable `backend` → `lifter`
  - Badge pack: `LIFTER_BADGE_KEYS: Array<keyof LifterBackend['capabilities']> = ['license', 'outputs_oriented']`
  - Empty-state copy: `'Loading backends...'` → `'Loading lifters...'`, `'No backends available'` → `'No lifters available'`
  - Imported `LifterBackend` type (not `DetectorBackend`) so TS enforces the lifter capability-key surface
- **Visibility gate NOT in this file** — Plan 10 wraps the consumer in `{activeBackendInfo?.capabilities?.outputs_3d_natively === false && <LifterDropdown onSelect={...} />}` per D-08; the component itself always renders when mounted
- **tsc:** clean

## Badge Key Divergence Rationale

| Dropdown | Badge Keys | Reason |
|----------|-----------|--------|
| DetectorDropdown | `framework`, `license`, `cpu_latency_hint_ms` | D-05/D-06 — identifies backend provenance (framework), IP/licensing implications (license), and performance expectation (latency hint) |
| LifterDropdown | `license`, `outputs_oriented` | D-05-analogous — lifter capabilities in `median_depth.py:117-122` are mostly functional flags (`requires_depth`, `requires_point_cloud`) that aren't useful on a compact pill; `outputs_oriented` is the one user-visible quality differentiator (true = Phase 4 PCA-OBB, false = MedianDepth flat quaternion), and `license` keeps parity with the detector row |

Neither set includes `outputs_3d_natively` (detector) — that key is FUNCTIONAL (drives LifterDropdown visibility), not rendered. Per D-05, this is a one-line change in each dropdown if the badge surface needs to expand.

## Deviations from Plan

None — both tasks executed exactly as specified. The only minor liberty: dropped the `capabilities.length > 0` conditional around the badge-row container because the CapabilityBadge D-04 rules (skip `false`/`null`/`undefined`) already no-op for missing keys, and a `display: flex` container with zero children renders zero height. This is consistent with the plan's note that "D-04 handles null/undefined safely (returns null) so this is safe even if a backend omits a key."

## Verification Results

```bash
$ cd frontend && npx tsc --noEmit
# exit 0 — clean
```

Acceptance criteria (all pass):

**Task 1 (DetectorDropdown):**
- `export function DetectorDropdown` present
- `useDetectorStore` imported (4 call sites: 3 selectors + 1 re-export of type)
- `from '../stores/detectorStore'` import present
- All three badge-key string literals present (`'framework'`, `'license'`, `'cpu_latency_hint_ms'`)
- Zero `useSlamStore` references (no leftover rename)

**Task 2 (LifterDropdown):**
- `export function LifterDropdown` present
- Store selectors `s.lifters`, `s.activeLifter`, `s.activeLifterDisplay` all present
- Both lifter badge-key literals present (`'license'`, `'outputs_oriented'`)
- Zero `DetectorDropdown` references (clean rename)

**Line-count thresholds:** DetectorDropdown 154 ≥ 130 ✓, LifterDropdown 155 ≥ 120 ✓.

## Threat Flags

No new trust boundaries introduced beyond those already documented in the plan's `<threat_model>`. Both T-03-18 (registry-authored text in JSX) and T-03-19 (install-hint tooltips) remain **accepted** — mitigation is "registry authors trusted + React auto-escapes JSX interpolation", no new surface added.

## Downstream Readiness

Plan 10 (DetectorSection) can now:
1. Import `{ DetectorDropdown }` from `./DetectorDropdown`
2. Import `{ LifterDropdown }` from `./LifterDropdown`
3. Wire `onSelect={handleDetectorSwitchRequest}` (triggers ConfirmModal → `/lifter-select` POST → restart flow per D-09)
4. Wrap LifterDropdown mount in the `outputs_3d_natively === false` conditional per D-08

No other files in the tree need to change before Plan 10 ships.

## Known Stubs

None — both components consume real store state (no hardcoded empty arrays, no placeholder text rendered as data). Empty-state copy ("Loading backends..." / "Loading lifters...") is a genuine loading UX branch, not a stub.

## Self-Check: PASSED

Files exist:
- `frontend/src/components/DetectorDropdown.tsx` ✓ (154 lines, ≥130 threshold)
- `frontend/src/components/LifterDropdown.tsx` ✓ (155 lines, ≥120 threshold)

Commits exist on branch `worktree-agent-a4deb802`:
- `e7a2693` feat(03-07): add DetectorDropdown with 3-key capability badges ✓
- `4a52fbc` feat(03-07): add LifterDropdown with license + outputs_oriented badges ✓

`cd frontend && npx tsc --noEmit` → exit 0 ✓
