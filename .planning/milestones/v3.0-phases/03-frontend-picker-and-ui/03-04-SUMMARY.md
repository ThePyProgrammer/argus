---
phase: 03
plan: 04
subsystem: frontend-state
tags:
  - frontend
  - zustand
  - detector-store
  - rest-fetch
requirements:
  - DET-UI-06
provides:
  - useDetectorStore
  - fetchDetectorState
  - DetectorBackend
  - LifterBackend
requires:
  - zustand@5
affects:
  - Plan 03-07 (DetectorDropdown consumer)
  - Plan 03-08 (DetectorParameterPanel consumer)
  - Plan 03-10 (RestartOverlay subsystem; useWebSocket wiring)
  - Plan 03-11 (Vitest structural-equivalence test)
tech_stack:
  added: []
  patterns:
    - flat-zustand-store
    - parallel-rest-fetch
    - slamStore-mirror
key_files:
  created:
    - frontend/src/stores/detectorStore.ts
  modified: []
decisions:
  - "Implemented D-02 verbatim: 8 SLAM-mirror state fields + 5 lifter additions; 9 SLAM-mirror setters + 5 lifter setters."
  - "DetectorBackend.capabilities typed as Record<string, string|number|boolean> (NOT Record<string, boolean>) because detector capabilities are heterogeneous (framework=string, cpu_latency_hint_ms=number, outputs_3d_natively=boolean)."
  - "Defaults pinned to canonical truth sources: activeBackend='yolov11' / activeDisplay='YOLOv11-nano' (server.py:62 app.state); activeLifter='median_depth' / activeLifterDisplay='Median Depth (legacy)' (Detection3DRegistry + MedianDepthLifter registration)."
  - "fetchDetectorState parallel-fetches all 4 detector REST endpoints; single try/catch around all four with one generic error message (T-03-09 mitigation; T-03-10 accept)."
metrics:
  duration_min: 4
  tasks_completed: 1
  files_created: 1
  files_modified: 0
  completed: 2026-04-14
---

# Phase 3 Plan 04: Detector Store Summary

Zustand store mirroring slamStore.ts shape with 5+5 lifter extensions and parallel REST hydration across 4 detector endpoints, ready for Wave 2 UI consumers.

## What Was Built

`frontend/src/stores/detectorStore.ts` (149 lines) — a structural clone of `frontend/src/stores/slamStore.ts` (88 lines) with the D-02 lifter extensions baked in. The store is the single source of truth that downstream UI components (DetectorDropdown, DetectorParameterPanel, DetectorSection, LifterDropdown, RestartOverlay) will read from in Wave 2.

### State Surface

**Detector state (mirrors `useSlamStore`):**

| Field | Type | Default |
|-------|------|---------|
| `backends` | `DetectorBackend[]` | `[]` |
| `activeBackend` | `string` | `'yolov11'` |
| `activeDisplay` | `string` | `'YOLOv11-nano'` |
| `activeParameters` | `Record<string, unknown>` | `{}` |
| `stagedParams` | `Record<string, unknown>` | `{}` |
| `isRestarting` | `boolean` | `false` |
| `error` | `string \| null` | `null` |
| `crashMessage` | `string \| null` | `null` |

**Lifter state (D-02 additions, no SLAM equivalent):**

| Field | Type | Default |
|-------|------|---------|
| `lifters` | `LifterBackend[]` | `[]` |
| `activeLifter` | `string` | `'median_depth'` |
| `activeLifterDisplay` | `string` | `'Median Depth (legacy)'` |
| `activeLifterParameters` | `Record<string, unknown>` | `{}` |
| `stagedLifterParams` | `Record<string, unknown>` | `{}` |

### Setter Surface

**Detector setters (mirrors `useSlamStore`):**

`setBackends`, `setActive(name, display, parameters)`, `setRestarting`, `stageParam(key, value)`, `clearStagedParams`, `setError`, `updateActiveParam(key, value)`, `setCrashMessage`, `clearCrashMessage` — 9 setters total, signature-identical to the SLAM equivalents.

**Lifter setters (D-02 additions):**

`setLifters`, `setActiveLifter(name, display, parameters)`, `stageLifterParam(key, value)`, `clearStagedLifterParams`, `updateActiveLifterParam(key, value)` — 5 setters total, naming convention follows the `*Lifter*` infix pattern locked in plan/context.

### `fetchDetectorState`

Parallel-fetches all 4 detector REST endpoints via `Promise.all`, then dispatches each response through its setter. Single `try/catch` wraps the whole block; any rejection (network or parse) sets `error: 'Failed to load detector backends. Check that the server is running.'`.

| Endpoint | Response Shape | Dispatched Via |
|----------|----------------|----------------|
| `GET /api/detectors/backends` | `{backends: DetectorBackend[]}` | `setBackends(data.backends)` |
| `GET /api/detectors/active` | `{backend, display, parameters}` | `setActive(data.backend, data.display, data.parameters)` |
| `GET /api/detectors/lifters` | `{lifters: LifterBackend[]}` | `setLifters(data.lifters)` |
| `GET /api/detectors/active-lifter` | `{lifter, display, parameters}` | `setActiveLifter(data.lifter, data.display, data.parameters)` |

The `/lifters` and `/active-lifter` endpoints will be added in Plan 03-05 (parallel wave). Until that plan ships, the two lifter fetches will 404 and `setError` will trip — acceptable because no UI consumer mounts in Wave 1.

## Type Decisions

- **`DetectorBackend.capabilities: Record<string, string | number | boolean>`** — detector capabilities are heterogeneous (`framework: string`, `cpu_latency_hint_ms: number`, `outputs_3d_natively: boolean`, `license: string`). The slamStore template uses `Record<string, boolean>` which would fail tsc when these heterogeneous values arrive over the wire. This is the only intentional type divergence from slamStore.
- **`LifterBackend` reuses `DetectorBackend['parameter_schema']`** — lifters have the same `live_tunable` parameter shape as detectors (per D-02 + D-09 restart semantics).
- **`parameter_schema.properties.*.default: number | boolean | string`** — extends slamStore's `number | boolean` to include `string` defaults (e.g., enum-style detector params expected in future BoxeR / OWLv2 backends per Phase 5 deferred ideas).

## Verification

```bash
cd frontend && npx tsc --noEmit
```

Exits 0. (Required `npm install` first because the worktree had no `node_modules`; that was a one-time bootstrap and `package-lock.json` was reverted to avoid an unrelated naming churn — the lockfile only flipped the project name `c2-frontend` ↔ `argus-frontend`, which is unrelated to this plan and belongs in a separate cleanup.)

## Plan 11 Lock

Plan 03-11 will add `frontend/src/stores/__tests__/detectorStore.shape.test.ts` (D-03) — a Vitest structural-equivalence test that asserts:

- `Object.keys(useDetectorStore.getState())` ⊇ `Object.keys(useSlamStore.getState())`
- The 10 lifter additions (5 fields + 5 setters) are present by name
- Setter signature parity (e.g., `setActive(name, display, parameters)` matches `setActiveLifter(name, display, parameters)`)

Until Plan 11 lands, the only shape lock is the TypeScript compile-time check (`tsc --noEmit`).

## Deviations from Plan

None — plan executed exactly as written.

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/stores/detectorStore.ts` | 149 | Zustand store + REST fetcher (this plan) |
| `frontend/src/stores/slamStore.ts` | 88 | Template (read-only reference) |

## Threat Surface Notes

- **T-03-08 (Tampering)** — accept. REST payloads are server-authored (Pydantic-validated on writes; registry-authored on reads); React JSX auto-escapes any rendered string.
- **T-03-09 (DoS)** — mitigated. `try/catch` around all 4 parallel fetches catches network and parse errors and surfaces a single user-facing error message.
- **T-03-10 (Info Disclosure)** — accept. Error text is generic ("Failed to load detector backends. Check that the server is running.") with no stack trace or internal detail.

No new threat surface beyond what was modelled in the plan.

## Commits

- `52b2bfb` — feat(03-04): add detectorStore mirroring slamStore + lifter extensions

## Self-Check: PASSED

- FOUND: `frontend/src/stores/detectorStore.ts` (149 lines, all 10 D-02 names + 9 SLAM-mirror setters + 4 REST endpoints + correct defaults)
- FOUND: commit `52b2bfb` in `git log --oneline`
- VERIFIED: `cd frontend && npx tsc --noEmit` exits 0
