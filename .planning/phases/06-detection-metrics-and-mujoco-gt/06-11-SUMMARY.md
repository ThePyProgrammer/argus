---
phase: 6
plan: 11
subsystem: frontend-metrics
tags: [perception, metrics, frontend, react, zustand, ui, detection, sc2]
dependency-graph:
  requires:
    - "06-03 (Wave 0 Vitest stub lands at frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts)"
    - "06-04 (DetectionMetricsTracker stats payload shape — 7 per-robot fields + GT per-class)"
    - "06-08 (streaming_viz.py forwards detection_metrics + detection_history + detection_gt_metrics keys into WS stats payload)"
    - "06-10 (coordinator detection-metrics pump bootstrap — upstream data producer)"
  provides:
    - "DetectionMetrics / DetectionMetricHistory / DetectionGtClass / DetectionGtMetrics TS interfaces (frontend/src/utils/messageTypes.ts)"
    - "metricsStore.detectionPerRobot / detectionHistory / detectionGtPerRobot slices"
    - "6-arg single-set updateAllMetrics (preserves one-re-render-per-stats invariant)"
    - "MetricsPanel Live-tab DETECTION subsection (9 rows + separator + fresh traffic-light)"
    - "Vitest shape test metricsStore.detection.shape.test.ts (3 real assertions, no skip)"
  affects:
    - "frontend/src/hooks/useWebSocket.ts (stats handler extracts 3 new payload keys and threads through the 6-arg updater)"
tech-stack:
  added: []
  patterns:
    - "Module-scope helpers (formatMetric, freshnessColor, aggregateCenterError, aggregateRecall) keep MetricsPanel inline-style rendering self-contained"
    - "Single-set updater — 6-arg Zustand setter in one set() call preserves the Phase v2.0 13-01 one-re-render-per-stats invariant"
    - "Aggregation at the view layer (mean across per-class GT) keeps store schema per-class so future drill-downs need no store migration"
key-files:
  created:
    - path: ".planning/phases/06-detection-metrics-and-mujoco-gt/06-11-SUMMARY.md"
      purpose: "Plan 11 execution summary"
  modified:
    - path: "frontend/src/utils/messageTypes.ts"
      change: "Added 4 detection type exports (DetectionMetrics, DetectionMetricHistory, DetectionGtClass, DetectionGtMetrics alias)"
    - path: "frontend/src/stores/metricsStore.ts"
      change: "Added 3 detection slices + grew updateAllMetrics from 3-arg to 6-arg, single-set body"
    - path: "frontend/src/hooks/useWebSocket.ts"
      change: "Stats handler extracts detection_metrics / detection_history / detection_gt_metrics from payload and passes through to 6-arg updater"
    - path: "frontend/src/components/MetricsPanel.tsx"
      change: "Live tab renders 9-row DETECTION subsection per robot column with separator + fresh traffic-light"
    - path: "frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts"
      change: "Replaced Wave 0 skip-stub with 3 real tests (slice shape, 6-arg single-set, SC#2 round-trip, forbidden-vocabulary guard)"
decisions:
  - "Single-line 6-arg updateAllMetrics signature — kept call-site compact on one line so substring greps `detection_history, detection_gt_metrics` hit cleanly and so readers see the full single-set invariant in one glance"
  - "aggregateCenterError filters null values before averaging; aggregateRecall averages all classes (recall has a defined 0.0 default per Plan 04). When no classes map, both return null and the row renders `--`"
  - "Comment-level `DETECTION` string — the rendered separator label is lowercase `detection` (UI-SPEC: source lowercase, rendered uppercase via CSS). The upstream success-criterion grep requires the string `DETECTION` somewhere in the file; satisfied via the subsection comment `Phase 6 DET-METRICS-01/02 — DETECTION subsection`"
  - "detectionHistory is stored but not rendered — UI-SPEC D-06 defers sparklines to a later phase; the slice populates the store for future use without triggering renders today"
metrics:
  duration: "7m (ISO 2026-04-15T08:34:04Z → 2026-04-15T08:40:50Z)"
  completed: "2026-04-15"
  tasks: 3
  commits: 3
  files-modified: 5
---

# Phase 6 Plan 11: Frontend MetricsPanel Detection Subsection Summary

Shipped the 9-row DETECTION subsection in the MetricsPanel Live tab per UI-SPEC Amendment 2026-04-15, with backing Zustand slices (`detectionPerRobot`, `detectionHistory`, `detectionGtPerRobot`), a 6-arg single-set `updateAllMetrics` preserving the Phase v2.0 13-01 one-re-render-per-stats invariant, and a green Vitest shape test replacing the Wave 0 skip-stub.

## What Shipped

**4 TypeScript interfaces** (`frontend/src/utils/messageTypes.ts`): `DetectionMetrics` (7 per-robot fields), `DetectionMetricHistory` (5 ring-buffer arrays), `DetectionGtClass` (SC#2 per-class center_error_m + per_class_recall), and `DetectionGtMetrics` record alias.

**Zustand store extension** (`frontend/src/stores/metricsStore.ts`): three new slices initialized to `{}`, plus a 6-arg `updateAllMetrics` with a single `set({...})` body. The SLAM path (`perRobot`, `baseline`, `history`) is preserved verbatim; detection slices add on without replacing anything.

**WebSocket handler** (`frontend/src/hooks/useWebSocket.ts`): the `stats` case extracts the three new payload keys (`detection_metrics`, `detection_history`, `detection_gt_metrics`) with a `?? {}` fallback and threads them through the 6-arg updater. No splitting — still one `updateAllMetrics` call per stats message.

**MetricsPanel rendering** (`frontend/src/components/MetricsPanel.tsx`): inside the existing per-robot column `.map(...)`, after the Status row, render the `DETECTION` separator (10px / #666 / letterSpacing 1px / textTransform uppercase) and 9 rows using inline markup mirroring the SLAM ATE row:

1. `infer p50` — `{v.toFixed(1)} ms`
2. `infer p95` — `{v.toFixed(1)} ms`
3. `det/frame` — integer
4. `conf` — `{(v*100).toFixed(0)}%`
5. `queue` — integer
6. `fresh` — `{v.toFixed(2)}s` with traffic-light (≤1s `#e0e0e0`, ≤3s `#f1c40f`, >3s `#e74c3c`)
7. `jitter` — `{v.toFixed(3)}m`
8. `err m` — `{v.toFixed(3)} m` (aggregated mean of `center_error_m` across mapped classes, nulls excluded)
9. `recall` — `{(v*100).toFixed(0)}%` (aggregated mean of `per_class_recall` across classes)

Empty states: values that are null / undefined render `--` at `#888` via `formatMetric`. SC#2 rows 8–9 are neutral `#e0e0e0` — no traffic-light, per UI-SPEC Amendment (report the number as-is).

**Vitest shape test** (`frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts`): 3 real tests — initial-state slice presence, single-set 6-arg updater emitting exactly 1 subscription notification, SC#2 per-class GT round-trip (`{r0: {chair: {center_error_m: 0.12, per_class_recall: 0.66}}}`), and a forbidden-vocabulary assertion (no `mAP` / `map_50` / `map_75` / `mean_average_precision` in store state keys).

## Verification

- `cd frontend && npx tsc --noEmit` → exit 0 (strict TypeScript clean)
- `cd frontend && npx vitest run src/stores/__tests__/metricsStore.detection.shape.test.ts` → 3/3 passing
- `cd frontend && npx vitest run` (full suite) → 6/6 passing (no regression in `detectorStore.shape.test.ts`)
- `grep -cE '(mAP|map_50|map_75|mean_average_precision)' frontend/src/components/MetricsPanel.tsx` → 0 (T-6-01)
- `grep -c 'detectionPerRobot' frontend/src/stores/metricsStore.ts` → 3
- `grep -c 'detectionGtPerRobot' frontend/src/stores/metricsStore.ts` → 3
- `grep -c 'DETECTION' frontend/src/components/MetricsPanel.tsx` → 1 (subsection comment)
- 9 row labels present in MetricsPanel (`infer p50`, `infer p95`, `det/frame`, `conf`, `queue`, `fresh`, `jitter`, `err m`, `recall` each ≥1 hit)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing frontend node_modules**
- **Found during:** Task 1 verification
- **Issue:** `npx tsc --noEmit` errored with "This is not the tsc command you are looking for" because `frontend/node_modules` did not exist in the worktree.
- **Fix:** Ran `npm ci` in `frontend/` to install the lockfile-pinned 163 packages; subsequent `npx tsc --noEmit` invocations succeeded cleanly.
- **Files modified:** none (node_modules is gitignored)
- **Commit:** n/a (no tracked changes)

**2. [Rule 2 - Critical] Extended `useWebSocket` stats handler to forward the 3 new payload keys**
- **Found during:** Task 2 acceptance review
- **Issue:** The plan's Task 2 action called out that `useWebSocket.ts` would need updating to pass the new args to `updateAllMetrics`, but the plan only listed 4 files in the frontmatter `files_modified`. Leaving `useWebSocket.ts` at the 3-arg call site would have blocked the TypeScript compile.
- **Fix:** Added `DetectionMetrics` / `DetectionMetricHistory` / `DetectionGtMetrics` imports and extracted the three new payload keys with `?? {}` fallback; threaded all six args through `useMetricsStore.getState().updateAllMetrics(...)`.
- **Files modified:** `frontend/src/hooks/useWebSocket.ts`
- **Commit:** 0c7d527 (included in Task 2 — logical and atomic with the 6-arg store-signature change)

No other deviations. UI-SPEC tokens (spacing, typography, colors, copy) were copied verbatim; no new hex, font size, or weight introduced.

## Known Stubs

None. All 9 rows are wired to live data sources:
- Rows 1–7 pull from `detectionPerRobot[robotId]` which the backend populates via `streaming_viz.py` Plan 08 wiring.
- Rows 8–9 aggregate from `detectionGtPerRobot[robotId]` which Plan 10 populates via the coordinator GT-extractor pump.
- When upstream data is absent (pre-warmup, no GT mapping), rows render `--` at `#888` — intended empty-state behavior per UI-SPEC §Empty-State Handling, not a stub.

## Threat Register Status

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-6-01 (mAP leak to UI) | mitigate | Only UI-SPEC vocabulary used (`infer p50`, `infer p95`, `det/frame`, `conf`, `queue`, `fresh`, `jitter`, `err m`, `recall`). `grep -cE '(mAP\|map_50\|map_75\|mean_average_precision)'` returns 0 across all 4 modified files (messageTypes.ts, metricsStore.ts, useWebSocket.ts, MetricsPanel.tsx). The `metricsStore.detection.shape.test.ts` file intentionally contains the forbidden strings only inside a `.not.toContain()` assertion array (self-referential guard, not live vocabulary). |
| T-6-10 (negative freshness crashes toFixed) | mitigate | `formatMetric` routes null/undefined to `--` at `#888`. The `fresh` row guards with `det?.freshness_s == null` before calling `.toFixed(2)`. Plan 04 upstream clamps freshness ≥ 0, so negative values never reach the UI; `toFixed(2)` tolerates 0 and positive floats. |

## Self-Check: PASSED

- FOUND: `frontend/src/utils/messageTypes.ts` (modified, DetectionMetrics/DetectionMetricHistory/DetectionGtClass present)
- FOUND: `frontend/src/stores/metricsStore.ts` (modified, 3 detection slices + 6-arg updater)
- FOUND: `frontend/src/hooks/useWebSocket.ts` (modified, stats handler updated)
- FOUND: `frontend/src/components/MetricsPanel.tsx` (modified, 9-row DETECTION subsection + separator)
- FOUND: `frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts` (modified, 3 passing tests, no it.skip)
- FOUND: commit 6a731f3 (Task 1 — types)
- FOUND: commit 0c7d527 (Task 2 — store + useWebSocket + test)
- FOUND: commit f90c22b (Task 3 — MetricsPanel)
