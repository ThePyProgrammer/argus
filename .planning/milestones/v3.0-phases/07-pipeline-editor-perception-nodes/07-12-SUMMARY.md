---
phase: 07
plan: 12
subsystem: frontend-pipeline-editor
tags: [frontend, pipeline-editor, perception, hot-swap, D-02, SC#4]
requires:
  - frontend/src/stores/pipelineStore.ts (pre-existing updateNodeParam + selectNode)
  - frontend/src/components/pipeline/NodeInspector.tsx (pre-existing registry label)
  - frontend/src/App.tsx (pre-existing /api/pipeline/node-catalog fetch)
  - frontend/src/utils/nodeDefinitions.ts (Plan 07-XX perception node defs landed in Wave 2)
provides:
  - pipelineStore.availableRegistryNodes: RegistryNode[] state (single source of truth)
  - pipelineStore.setAvailableRegistryNodes(nodes) action
  - pipelineStore.updateNodeParam('backend', ...) hot-swap branch (D-02 contract)
  - NodeInspector backend <select> dropdown for perception nodes (SC#4 UI surface)
  - shared RegistryNode interface in frontend/src/utils/pipelineTypes.ts
affects:
  - frontend/src/App.tsx (fetch now also writes to store)
  - frontend/src/components/pipeline/NodePalette.tsx (import lifted type; no behavior change)
tech-stack:
  added:
    - "@testing-library/react@^16.0.0 (devDep; JSX rendering under jsdom for NodeInspector integration tests)"
    - "@testing-library/dom@^10.0.0 (devDep; peer of @testing-library/react)"
  patterns:
    - "Zustand getState() fire-and-forget write from event handler (existing NodePalette pattern)"
    - "Schema-default extraction: paramValues reset from parameterSchema.properties[k].default"
    - "Prefix-based category/type filtering in JSX (no new util module required)"
key-files:
  created:
    - frontend/src/stores/__tests__/pipelineStore.backendHotSwap.test.ts
  modified:
    - frontend/src/utils/pipelineTypes.ts
    - frontend/src/stores/pipelineStore.ts
    - frontend/src/App.tsx
    - frontend/src/components/pipeline/NodePalette.tsx
    - frontend/src/components/pipeline/NodeInspector.tsx
    - frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "RegistryNode shape lifted to pipelineTypes.ts (single source of truth; eliminates duplicate interface in App.tsx + NodePalette)"
  - "Hot-swap defensive fallback: when availableRegistryNodes has no match, updateNodeParam('backend') falls through to legacy paramValues[key]=value write (no crash, surfaces as HTTP 422 from PipelineBuilder on apply — per threat T-07-22 disposition)"
  - "paramValues reset uses schema-default extraction (not empty-object) — only schema-typed defaults populate; keys without `default` are omitted (tests lock the contract)"
  - "NodeInspector dropdown gating uses explicit nodeType whitelist (3 perception types) rather than category check — future perception node types MUST be added here (documented as a Wave 4 follow-up if more perception kinds land)"
metrics:
  duration: ~15min
  completed: 2026-04-15
  tasks_completed: 2
  test_count_delta: "+5 store tests + 7 previously-skipped Inspector tests flipped green = +12 assertions"
  total_tests_passing: "41/41 frontend vitest suite (0 skipped, 0 failing)"
---

# Phase 7 Plan 12: D-02 NodeInspector Backend Hot-Swap Dropdown Summary

## One-Liner
Added the user-facing backend hot-swap <select> dropdown to NodeInspector for the 3 perception node types, lifted RegistryNode catalog into pipelineStore, and extended updateNodeParam('backend', ...) to mutate registryName + replace parameterSchema + reset paramValues per D-02 — closing the SC#4 end-to-end exercisability gap that Plans 04/08/09 left open.

## What Changed

### Store layer (Task 1)
- `frontend/src/utils/pipelineTypes.ts` — exported new shared `RegistryNode` interface (lifted from App.tsx's inline declaration).
- `frontend/src/stores/pipelineStore.ts` — added `availableRegistryNodes: RegistryNode[]` state + `setAvailableRegistryNodes` action; rewrote `updateNodeParam` to special-case `key === 'backend'`:
  1. Resolve `baseKind = nodeType.replace(/_generic$/, '')` (e.g. `detector_generic` → `detector`).
  2. Look up `${baseKind}_${newRegistryName}` in `availableRegistryNodes`.
  3. If found: set `data.registryName = newRegistryName`, replace `data.parameterSchema`, and build `paramValues` from the schema's `properties[k].default` values.
  4. If not found: fall through to the legacy `paramValues[key] = value` write (defensive — no partial-state crash; downstream `/api/pipeline/apply` will surface HTTP 422 via PipelineBuilder).
- `frontend/src/App.tsx` — removed the inline `RegistryNode` interface, imported the shared one from `pipelineTypes`, and extended the `/api/pipeline/node-catalog` fetch to also populate the store via `usePipelineStore.getState().setAvailableRegistryNodes(regNodes)`.
- `frontend/src/components/pipeline/NodePalette.tsx` — removed the inline `RegistryNode` interface, imported the shared one.

### UI layer (Task 2)
- `frontend/src/components/pipeline/NodeInspector.tsx` — added a store subscription to `availableRegistryNodes`; rendered a new `<select aria-label="Backend">` immediately BELOW the existing "Backend: {registryName}" static label, gated to the 3 perception node types (`detector_generic`, `detection3d_generic`, `tracker_generic`). Dropdown options are filtered by `category === 'perception' AND type.startsWith(${baseKind}_)`; `onChange` dispatches `updateNodeParam(selectedNodeId, 'backend', e.target.value)` which triggers the Task 1 hot-swap branch.

### Test layer
- `frontend/src/stores/__tests__/pipelineStore.backendHotSwap.test.ts` (new, 5 tests) — covers default-empty, `setAvailableRegistryNodes` write, hot-swap success path, defensive fallback path, and legacy non-`backend` key path.
- `frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx` — promoted from `describe.skip` (Plan 07-02 stub) to 7 real assertions covering render gating across 3 perception types + 1 non-perception negative, options prefix-filtering, change-handler spy, and full hot-swap side-effects.

## Commits (in order)
- `c203d39` test(07-12): add failing tests for availableRegistryNodes + backend hot-swap
- `591f068` feat(07-12): lift RegistryNode + availableRegistryNodes store + backend hot-swap (D-02)
- `4c0f6ae` test(07-12): promote NodeInspector.backendDropdown from skip-stub to 7 real assertions
- `ef3ea86` feat(07-12): add backend hot-swap <select> dropdown to NodeInspector (D-02)

## Verification
- `cd frontend && npx tsc -p tsconfig.json --noEmit` → exit 0 (clean).
- `cd frontend && npm run test -- --run` → **41/41 passing, 0 skipped, 0 failing** (was 34 passing + 7 skipped in Plan 07-12 stubs pre-merge).
- `cd frontend && npm run build` → exit 0; Vite production bundle succeeds.
- Store tests (5/5 green): default-empty, setter write, hot-swap success, defensive fallback, legacy-key passthrough.
- Inspector tests (7/7 green): detector_generic render, detection3d_generic render, tracker_generic render, slam_generic negative, options prefix filter, updateNodeParam spy, full hot-swap mutation.

## Deviations from Plan

**None — plan executed exactly as written.**

Task action blocks were followed verbatim for both store + UI changes. No architectural Rule-4 decisions triggered. No Rule-1/2/3 auto-fixes required (no pre-existing bugs discovered in the touched files).

### Dependency install note (not a deviation — plan anticipated this)
The plan explicitly called out: "If `@testing-library/react` is missing from `frontend/package.json`, install it". I verified it was missing, then installed `@testing-library/react@^16.0.0` + `@testing-library/dom@^10.0.0` as devDeps. Both landed in the Task 2 RED commit (`4c0f6ae`) alongside the promoted test file.

## Requirements Closed

- **DET-PIPELINE-01** — perception nodes have a live-editable backend surface in the UI (D-02 contract).
- **DET-PIPELINE-05** — hot-swap path exercisable end-to-end from the Inspector, not just from raw /api/pipeline/apply payloads (SC#4 rubric requirement).

## Threat Surface Closure
No new threats introduced. Plan's threat register remained accurate:

- **T-07-22** (Tampering — unknown registry name) — mitigated as planned via defensive fallback in `updateNodeParam('backend')`.
- **T-07-23** (Tampering — malformed parameterSchema) — mitigated via `match.parameterSchema?.properties ?? {}` defensive read.
- **T-07-24** (Information Disclosure — catalog contents) — accepted (already public via NodePalette).
- **T-07-25** (DoS — rapid dropdown changes) — mitigated via cached-catalog read (no re-fetch on change; Zustand setState is synchronous and React-batched).

## Known Stubs
None — all UI surfaces wired to real store data. No placeholder text, no `=[]`/`={}` flowing to render paths.

## Self-Check: PASSED

**Files verified:**
- FOUND: frontend/src/stores/__tests__/pipelineStore.backendHotSwap.test.ts
- FOUND: frontend/src/utils/pipelineTypes.ts (modified)
- FOUND: frontend/src/stores/pipelineStore.ts (modified)
- FOUND: frontend/src/App.tsx (modified)
- FOUND: frontend/src/components/pipeline/NodePalette.tsx (modified)
- FOUND: frontend/src/components/pipeline/NodeInspector.tsx (modified)
- FOUND: frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx (modified)

**Commits verified present in git log:**
- FOUND: c203d39
- FOUND: 591f068
- FOUND: 4c0f6ae
- FOUND: ef3ea86

**Key acceptance greps:**
- `grep "export interface RegistryNode" frontend/src/utils/pipelineTypes.ts` → 1 hit
- `grep "availableRegistryNodes" frontend/src/stores/pipelineStore.ts` → 4 hits
- `grep "setAvailableRegistryNodes" frontend/src/stores/pipelineStore.ts` → 2 hits
- `grep "key === 'backend'" frontend/src/stores/pipelineStore.ts` → 1 hit
- `grep "setAvailableRegistryNodes" frontend/src/App.tsx` → 1 hit
- `grep "interface RegistryNode" frontend/src/App.tsx` → 0 hits (lifted)
- `grep "interface RegistryNode" frontend/src/components/pipeline/NodePalette.tsx` → 0 hits (lifted)
- `grep 'aria-label="Backend"' frontend/src/components/pipeline/NodeInspector.tsx` → 1 hit
- `grep "describe.skip" frontend/src/components/pipeline/__tests__/NodeInspector.backendDropdown.test.tsx` → 0 hits
- Full frontend vitest suite: 41/41 green, 0 skipped, 0 failing.
- TSC + Vite build both exit 0.
