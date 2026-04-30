---
phase: 07
plan: 08
subsystem: frontend/pipeline-editor
tags: [det-pipeline-03, det-pipeline-05, bugfix, hot-apply, toast]
requires:
  - phase-07-plan-02 (perception node definitions + PortDataType extension)
  - phase-07-plan-06 (backend hot-apply response shape)
provides:
  - "Edge dataType resolution from source output port"
  - "Hot-apply success toast UI"
  - "Regression lockdown: pipelineStore.dataType.test.ts (5 green assertions)"
affects:
  - frontend/src/stores/pipelineStore.ts
  - frontend/src/utils/pipelineSerializer.ts
  - frontend/src/components/pipeline/ApplyBar.tsx
  - frontend/src/components/pipeline/PipelineNode.tsx
tech-stack:
  added: []
  patterns:
    - "Source-handle dataType inference (DET-PIPELINE-03 D-08)"
    - "Hot-apply branch on REST response status field (DET-PIPELINE-05 D-10)"
    - "React toast with useEffect cleanup + aria-live polite"
key-files:
  created:
    - path: (none — test file pre-existed as stub)
  modified:
    - path: frontend/src/stores/pipelineStore.ts
      change: "onConnect resolves edge dataType from source output port"
    - path: frontend/src/utils/pipelineSerializer.ts
      change: "deserializeGraph resolves edge dataType per edge from source output port"
    - path: frontend/src/components/pipeline/ApplyBar.tsx
      change: "handleConfirmApply branches on response.status; hot-apply toast renders inline"
    - path: frontend/src/components/pipeline/PipelineNode.tsx
      change: "CATEGORY_ICONS += perception (unblocks TS build after NodeCategory extension)"
    - path: frontend/src/stores/__tests__/pipelineStore.dataType.test.ts
      change: "5 live assertions replace describe.skip stubs"
decisions:
  - "Preserve defensive `?? 'PointCloud'` fallback in both onConnect + deserializeGraph — required for malformed-input safety (first test case exercises it)"
  - "Use magnifying glass \\u{1F50D} for perception category icon (UI-SPEC leaves category icon unlocked; matches detector semantics)"
  - "Hot-apply toast auto-dismiss = 3000ms flat (no 200ms fade animation implemented — UI-SPEC animation is aspirational; inline-style + no CSS-in-JS makes transition brittle. Unmount is immediate on timeout.)"
metrics:
  completed: 2026-04-15T11:08:58Z
  duration_minutes: ~3
  tasks_executed: 2
  commits: 3
---

# Phase 07 Plan 08: DataType Bugs + Hot-Apply Toast Summary

Fix the two hardcoded `dataType: 'PointCloud'` bugs (DET-PIPELINE-03) in pipelineStore.onConnect and pipelineSerializer.deserializeGraph by resolving dataType from the source node's output PortDef; extend ApplyBar to handle the new `{status: 'hot-applied'}` REST response branch with a success toast per UI-SPEC Hot-Apply Toast Pixel Spec.

## What Was Built

### Task 1 — dataType resolution from source output port

**pipelineStore.ts onConnect:** Replaced hardcoded `dataType: 'PointCloud' as const` with source-handle lookup:

```ts
const sourceNode = state.nodes.find((n) => n.id === connection.source);
const sourcePort = sourceNode?.data.outputs.find(
  (p) => p.id === connection.sourceHandle,
);
const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
```

**pipelineSerializer.ts deserializeGraph:** Same pattern applied per edge within the `config.edges.map`; `nodes` array is already constructed at that point, so each edge's dataType is resolved against the actual built node graph (not the backend's generic type string).

**Defensive fallback preserved:** `?? 'PointCloud'` remains. The falling-back test case (`nonexistent_handle`) passes by exercising this path.

### Task 2 — ApplyBar hot-apply branch + success toast

**Response branching in `handleConfirmApply`:**

```ts
.then((body) => {
  usePipelineStore.getState().markApplied();
  if (body && body.status === 'hot-applied') {
    usePipelineStore.getState().setIsApplying(false);
    const changed = Array.isArray(body.changed) ? (body.changed as string[]) : [];
    setHotToast({ visible: true, changed });
  }
  // status === 'restarting': isApplying cleared by useWebSocket slam_restart_complete handler
})
```

**Toast pixel spec (UI-SPEC locked):**

| Property | Value |
|----------|-------|
| Position | `absolute; bottom: 100%; left: 16px; margin-bottom: 4px; z-index: 50` |
| Width | `minWidth: 240, maxWidth: 480` |
| Background | `#1e3a2a` |
| Border | `1px solid #4caf50` |
| Padding | `8px 12px` |
| Body text | 11px / weight 600 / color `#a5d6a7` |
| Icon | `\u2713` check glyph, 12px, `#4caf50`, `marginRight: 6px` |
| Secondary line | 10px / weight 400 / color `#888`, only when `changed.length > 0` |
| Lifetime | 3000ms via `useEffect` + `setTimeout`; cleanup clears timeout on unmount |
| ARIA | `role="status" aria-live="polite"` |
| Dismissal | Click anywhere on toast sets `visible: false` |

**Literal copy:** `Pipeline updated in place` (UI-SPEC Copywriting Contract lock, exact string, appears exactly once).

## Threat Mitigations Applied

- **T-07-19 (malformed response body):** `body && body.status === 'hot-applied'` guard prevents NPE; unknown statuses fall through to the restart path (isApplying stays true until WS clears it — existing behavior).
- **T-07-20 (stale toast on unmount):** `useEffect` cleanup function clears the `setTimeout` handle; React unmount releases state before timer fires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking Issue] Add `perception` entry to CATEGORY_ICONS**
- **Found during:** Task 2 verification (`npm run build`)
- **Issue:** TS error `TS2741: Property 'perception' is missing in type ... but required in type 'Record<NodeCategory, string>'` at `PipelineNode.tsx:8`. Phase 7 NodeCategory union was extended to include `'perception'` (Plan 02 territory), but PipelineNode.tsx's `CATEGORY_ICONS` wasn't updated, so TS build fails.
- **Fix:** Added `perception: '\u{1F50D}'` (magnifying glass — matches detector semantics; UI-SPEC doesn't lock a category icon).
- **Files modified:** `frontend/src/components/pipeline/PipelineNode.tsx`
- **Commit:** 426f531

This was in-scope-adjacent — the plan's verification step (`npm run build green`) cannot pass without it, and the issue was directly surfaced by the plan's own acceptance criteria.

## Verification Results

- `npm run test -- --run src/stores/__tests__/pipelineStore.dataType.test.ts` → **5 passing** (Image, PointCloud, Detections2D, defensive fallback, deserialize).
- `npm run test -- --run` full suite → **29 passing, 7 skipped** (skipped are unrelated pre-existing Plan 07 WIP stubs).
- `npm run build` → green (TS + Vite bundle).
- Grep acceptance criteria:
  - `sourcePort?.dataType` in pipelineStore.ts: 1 hit ✓
  - `sourcePort?.dataType` in pipelineSerializer.ts: 1 hit ✓
  - `dataType: 'PointCloud' as const` in pipelineStore.ts: 0 hits ✓ (bug removed)
  - `dataType: 'PointCloud' as const` in pipelineSerializer.ts: 0 hits ✓ (bug removed)
  - `describe.skip` in dataType test: 0 hits ✓
  - `hot-applied` in ApplyBar.tsx: 1 hit ✓
  - `Pipeline updated in place` in ApplyBar.tsx: 1 hit ✓ (literal lock)
  - `setIsApplying(false)` in ApplyBar.tsx: 2 hits ✓ (hot-apply branch + error catch)
  - `#1e3a2a` in ApplyBar.tsx: 1 hit ✓
  - `#4caf50` in ApplyBar.tsx: 2 hits ✓
  - `role="status"` in ApplyBar.tsx: 1 hit ✓
  - `aria-live="polite"` in ApplyBar.tsx: 1 hit ✓

## Commits

| Commit  | Type    | Description                                                                       |
|---------|---------|-----------------------------------------------------------------------------------|
| e015d9e | test    | Add failing tests for edge dataType resolution (RED)                              |
| c704a45 | fix     | Resolve edge dataType from source output port in store + serializer (GREEN)       |
| 426f531 | feat    | ApplyBar handles hot-applied response with success toast + PipelineNode fix      |

## Requirements Completed

- **DET-PIPELINE-03** — SC#2 edge-type regression: hardcoded `PointCloud` on every new edge is fixed; Detections2D/Image edges now carry correct dataType, making port-type mismatch validation (added by Plan 07-03) functional.
- **DET-PIPELINE-05** — SC#4 hot-apply path: ApplyBar no longer shows RestartOverlay for `{status: 'hot-applied'}` responses; success toast renders per UI-SPEC.

## Known Stubs

None. All changes wire real state:
- `edge.data.dataType` is populated from live source PortDef lookup (not mock/empty).
- `hotToast.changed` receives the server's `changed` array verbatim; empty array naturally hides the secondary line.
- Success toast shows real `Pipeline updated in place` literal and the server-provided changed fields.

## Self-Check: PASSED

- FOUND: frontend/src/stores/pipelineStore.ts (edited)
- FOUND: frontend/src/utils/pipelineSerializer.ts (edited)
- FOUND: frontend/src/components/pipeline/ApplyBar.tsx (edited)
- FOUND: frontend/src/components/pipeline/PipelineNode.tsx (edited)
- FOUND: frontend/src/stores/__tests__/pipelineStore.dataType.test.ts (filled)
- FOUND: commit e015d9e (RED tests)
- FOUND: commit c704a45 (dataType fix)
- FOUND: commit 426f531 (ApplyBar + PipelineNode fix)
