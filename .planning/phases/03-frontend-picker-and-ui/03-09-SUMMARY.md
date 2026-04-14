---
phase: 03
plan: 09
subsystem: frontend
tags:
  - frontend
  - camera-feed
  - bbox-overlay
  - det-ui-05
requirements:
  - DET-UI-05
dependency-graph:
  requires:
    - Phase 02 Plan 02-11 (CameraFeed 2D bbox scaffolding, `bbox_xyxy` consumption)
    - frontend/src/utils/palette.ts (OKABE_ITO_RGB export)
  provides:
    - Per-class coloured 2D bbox overlay in CameraFeed (DET-UI-05 polish)
  affects:
    - frontend/src/components/CameraFeed.tsx
tech-stack:
  added: []
  patterns:
    - "class_id → palette index via `(class_id ?? 0) % OKABE_ITO_RGB.length`"
    - "CSS color string synthesized from RGB tuple via `rgb(r,g,b)`"
key-files:
  created: []
  modified:
    - frontend/src/components/CameraFeed.tsx
decisions:
  - "Index OKABE_ITO_RGB (RGB tuples) and synthesize a CSS rgb(r,g,b) string inside DetectionOverlay rather than switching to OKABE_ITO (hex); keeps must_haves contains='OKABE_ITO_RGB' literal match while yielding the same visible colors."
  - "Mark the now-unused `color` prop of DetectionOverlay as `_color` (destructuring rename) instead of removing it, preserving the existing props interface for any future robot-color-fallback feature and avoiding TS6133 under strict unused-locals."
  - "Guard negative class_id via a ternary inside the index expression (T-03-23 mitigation): `(det.class_id ?? 0) >= 0 ? (det.class_id ?? 0) % OKABE_ITO_RGB.length : 0`. JS `%` returns negative for negative dividends, which would yield `undefined` on array lookup and crash; COCO class_ids are non-negative, but the mitigation is free."
  - "Score tooltip upgraded from 1 → 2 decimal places to satisfy must_haves (`class_name + percentage to 2 decimal places`)."
  - "Add `textShadow: '0 1px 2px rgba(0,0,0,0.9)'` to the non-hover label for readability on bright RGB frames; leave the existing `rgba(0,0,0,0.75)` solid backdrop untouched per D-16."
metrics:
  duration_min: ~3
  completed_date: 2026-04-14
  tasks_completed: 1
  files_modified: 1
---

# Phase 03 Plan 09: CameraFeed per-class OKABE_ITO palette polish — Summary

Per-class 2D bbox overlay colours in `CameraFeed.tsx` via `OKABE_ITO_RGB[(det.class_id ?? 0) % OKABE_ITO_RGB.length]`, label text-shadow for readability on bright RGB frames, 2-decimal score tooltip — DET-UI-05 polish on top of the Phase 2 scaffolding. No new files, no schema changes, `tsc --noEmit` clean.

## What Changed

`frontend/src/components/CameraFeed.tsx` (+17 / −9):

- Import extended to pull `OKABE_ITO_RGB` alongside `robotColor`.
- Inside `DetectionOverlay`'s `.map((det, i) => …)` loop, a `classColor` local is derived via the guarded palette lookup and synthesized into a CSS `rgb(r,g,b)` string. COCO class indices are non-negative; the ternary still prevents an `undefined`-index crash for any weird server payload.
- Every reference to the single per-robot `color` inside the box rendering was replaced with `classColor`:
  - Box border (`2px solid classColor` / `#fff` on hover)
  - Box shadow glow (hover-only)
  - Label badge background (`classColor` on hover, `rgba(0,0,0,0.75)` otherwise — **unchanged backdrop**)
  - Label badge text colour (`classColor` on non-hover, `#000` on hover)
  - Hover tooltip border
  - Hover tooltip `class_name` strong colour
- `textShadow: '0 1px 2px rgba(0,0,0,0.9)'` added to the non-hover label text (belt-and-braces readability alongside the existing opaque backdrop).
- Score tooltip bumped from `.toFixed(1)` to `.toFixed(2)`.
- The `color` prop on `DetectionOverlay` is no longer referenced internally; destructured as `color: _color` to silence TS6133 under strict unused-locals without changing the component's props interface.

## Must-Haves Audit

| Truth | Verified |
|-------|----------|
| CameraFeed 2D bbox overlay colours each box by `det.class_id % OKABE_ITO_RGB.length` (not by robot color) | ✓ `OKABE_ITO_RGB[(det.class_id ?? 0) % OKABE_ITO_RGB.length]` at line 39–41 |
| Label backdrop readable on light and dark RGB frames (semi-opaque background with contrast text) | ✓ `rgba(0,0,0,0.75)` backdrop retained + added `textShadow` for extra contrast |
| Score tooltip renders class_name + percentage to 2 decimal places | ✓ `(det.score * 100).toFixed(2)` (bumped from `.toFixed(1)`) |
| Items without `bbox_xyxy` skip 2D overlay (graceful-degradation preserved) | ✓ `if (!det.bbox_xyxy || det.bbox_xyxy.length < 4) return null;` unchanged |
| `cd frontend && npx tsc --noEmit` exits 0 | ✓ clean |

## Acceptance Criteria Audit

| Criterion | Result |
|-----------|--------|
| `grep -q "import { robotColor, OKABE_ITO_RGB } from '../utils/palette'"` | ✓ line 3 |
| `grep -q "OKABE_ITO_RGB\[(det.class_id"` | ✓ line 39 matches |
| `grep -q "classColor"` | ✓ 8 occurrences |
| `if (!det.bbox_xyxy` guard present | ✓ line 33 |
| `cd frontend && npx tsc --noEmit` exits 0 | ✓ |

## Deviations from Plan

None behaviourally. Two minor adjustments that do not change the plan's intent:

1. **Index expression shape.** Plan suggested:
   ```ts
   const classColor = OKABE_ITO_RGB[(det.class_id ?? 0) % OKABE_ITO_RGB.length];
   ```
   which would type-error because `OKABE_ITO_RGB` is declared in `palette.ts` as `[number, number, number][]` — a tuple of RGB triples, not a string array. The plan's prose does describe the palette as "8 distinct colors," and the acceptance-criteria regex only requires `OKABE_ITO_RGB\[(det.class_id…`. Kept the literal `OKABE_ITO_RGB[(det.class_id…]` pattern (regex-compliant), destructured the tuple into `[cr, cg, cb]`, then synthesized `rgb(${cr}, ${cg}, ${cb})` — same visible palette, zero risk of switching to `OKABE_ITO` (hex). Documented here rather than as a Rule-3 deviation because both code and intent match the plan.
2. **Negative-class_id guard.** Plan's threat register (T-03-23) says `((x % n) + n) % n` is an acceptable mitigation and that the server-side class_id is non-negative (so "just document" is also acceptable). Implemented a ternary short-circuit rather than the double-mod trick because it reads more naturally in the array-index position and still satisfies the regex; identical behavior for any non-negative input.

## Authentication Gates

None encountered.

## Known Stubs

None. The overlay already renders live data from `robotStore.detections_3d.items`. Single-class scenes (e.g., all `person` detections) will now render all boxes in the same palette colour — **this is correct behaviour** per D-16 (palette keyed by class_id); a visual test with multiple COCO classes (person + chair + table, etc.) is the relevant manual-verify path.

## Deferred Issues

None. No pre-existing warnings in `CameraFeed.tsx` were touched; scope stayed within the DetectionOverlay function body.

## Threat Flags

None. No new network, auth, file-access, or schema surface introduced. The DOM still renders `det.class_name` via JSX (React auto-escapes) — T-03-24 acceptance unchanged.

## Manual Verification (deferred to 03-VALIDATION.md)

The per-class-colour visual outcome requires a live session with multiple detected classes in one frame (e.g., COCO `person` + `chair` + `dining table`) to confirm each draws its distinct OKABE_ITO hue. `tsc --noEmit` is the only automated gate per the plan's `<verification>` block. Logged under the Manual-Only verification table of `03-VALIDATION.md`.

## Commits

| Task | Commit | Summary |
|------|--------|---------|
| 1 — Per-class coloring + label backdrop polish | `23bdcbf` | `feat(03-09): per-class OKABE_ITO palette + label backdrop polish in CameraFeed` |

## Self-Check: PASSED

- Files modified: `frontend/src/components/CameraFeed.tsx` — FOUND (229 lines, > 220 min).
- Commit `23bdcbf` — FOUND in `git log`.
- `npx tsc --noEmit` — exits 0.
- `grep -q "OKABE_ITO_RGB"` — matches (3 hits).
- `grep -q "classColor"` — matches (8 hits).
- `grep -q "if (!det.bbox_xyxy"` — matches.
