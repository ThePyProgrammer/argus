---
phase: 07
plan: 06
subsystem: frontend-pipeline-editor
tags: [types, validation, ports, tdd, wave-2]
requires:
  - "Plan 07-02 (Wave 0 stubs: de-skipped test file scaffolds)"
provides:
  - "PortDataType union extended with Detections2D | Detections3D | Tracks"
  - "NodeCategory union extended with perception"
  - "findPortTypeMismatches(nodes, edges): ValidationError[] — per-edge type-mismatch validator"
  - "validateGraph hooks findPortTypeMismatches BEFORE findUnconnectedPorts (D-09 order)"
affects:
  - "frontend/src/utils/nodeDefinitions.ts (Record<PortDataType,string> exhaustiveness — REQUIRES Plan 07-07 to land map entries)"
  - "frontend/src/stores/pipelineStore.ts (PortDataType inference in onConnect — Plan 07-09 consumes new union values)"
tech-stack:
  added: []
  patterns:
    - "String-literal union extension preserving strict TS exhaustiveness"
    - "Clone findUnconnectedPorts traversal shape for findPortTypeMismatches"
    - "Error ordering: mismatch before structural (D-09 actionability policy)"
key-files:
  created: []
  modified:
    - frontend/src/utils/pipelineTypes.ts
    - frontend/src/utils/pipelineValidation.ts
    - frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts
    - frontend/src/utils/__tests__/portColors.test.ts
decisions:
  - "Preserve Record<PortDataType,string> strict typing: Plan 07-07 MUST co-land map entries before the wave-2 gate checks typecheck. This intentional compile-coupling is documented in the plan."
  - "Default dataType fallback in mkEdge test helper is 'PointCloud' (matches current pipelineStore.ts:101 bug) — the helper is only used for synthesizing test edges; the field's value is irrelevant to the type-mismatch validator (which reads port.dataType on the node, not edge.data.dataType)."
  - "Test bodies reference detector_generic / tracker_generic node definitions that Plan 07-07 adds. Tests at rest (Plan 06 standalone) will fail to import buildNodeData('detector_generic'); that's the wave-2 gate the plan designs for."
metrics:
  duration: "36min"
  completed: "2026-04-15T10:57:13Z"
  tasks: 2
  files: 4
  commits:
    - "e3fb5b2 feat(07-06): extend PortDataType + NodeCategory unions"
    - "cb0fced feat(07-06): add findPortTypeMismatches + hook into validateGraph"
---

# Phase 7 Plan 06: PortDataType + NodeCategory Extension + findPortTypeMismatches Summary

Extended the frontend type system with three new PortDataType values (Detections2D, Detections3D, Tracks) and one new NodeCategory (perception), plus the per-edge type-mismatch validator that DET-PIPELINE-03 SC#2 calls for. Both test files (pipelineValidation.typeMismatch + portColors) de-skipped with full assertion bodies, ready for the Wave 2 gate that runs after Plan 07-07 lands the PORT_COLORS / PORT_SHAPES / CATEGORY_COLORS / detector_generic / tracker_generic map extensions.

## Objective

Unblock Plan 07-07 (node definitions) by providing the string-literal union extensions it indexes, AND unblock SC#2 (connecting PointCloud to Detections2D shows an error) by shipping findPortTypeMismatches. Both deliverables are pre-requisites of the wave-2 perception-node palette surface.

## What Was Built

### Task 1 — PortDataType + NodeCategory extensions (commit e3fb5b2)

**File:** `frontend/src/utils/pipelineTypes.ts`

Extended the PortDataType union from 7 literal members to 10, adding:
- `'Detections2D'` — Phase 7 DET-PIPELINE-02 coral #ff8a65
- `'Detections3D'` — Phase 7 DET-PIPELINE-02 pink #ec407a
- `'Tracks'` — Phase 7 DET-PIPELINE-02 teal #26a69a

Extended the NodeCategory union from 7 literal members to 8, adding:
- `'perception'` — Phase 7 DET-PIPELINE-01 magenta #ad1457

Inline comments pin each new member to its source CONTEXT decision so future readers can trace the provenance without grepping the plan.

### Task 2 — findPortTypeMismatches + validateGraph hook (commit cb0fced)

**File:** `frontend/src/utils/pipelineValidation.ts`

Added `findPortTypeMismatches(nodes, edges): ValidationError[]`:
- Builds an id → node Map for O(1) lookup.
- For each edge, resolves source node + output PortDef (via `sourceHandle`) and target node + input PortDef (via `targetHandle`).
- Skips (no error) when either node or port cannot be resolved — defensive against malformed graph state.
- Emits a ValidationError with CONTEXT D-09 literal format when `srcPort.dataType !== tgtPort.dataType`:
  ```
  Edge from {srcLabel}.{srcPortLabel} ({srcType}) to {tgtLabel}.{tgtPortLabel} ({tgtType}) has mismatched types
  ```
- Error carries `nodeId: edge.target` so the React Flow error overlay highlights the receiver node.

Modified `validateGraph` to hook `findPortTypeMismatches` BEFORE `findUnconnectedPorts`:
- Final order: cycles → type mismatches → unconnected ports → missing output.
- D-09 rationale: type errors are more actionable (user sees the specific mismatched edge, not a generic "required input missing").

**Test files de-skipped:**

`frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` — 5 tests:
1. Matching Image → Image returns no errors.
2. PointCloud → Image mismatch detected, message references both types.
3. Detections2D → Detections3D mismatch detected (requires Plan 07-07 for node defs).
4. Literal D-09 message format — full string equality assertion.
5. validateGraph ordering — mismatch index < unconnected index.

`frontend/src/utils/__tests__/portColors.test.ts` — 5 tests:
1. PORT_COLORS.Detections2D === '#ff8a65'
2. PORT_COLORS.Detections3D === '#ec407a'
3. PORT_COLORS.Tracks === '#26a69a'
4. PORT_SHAPES.Detections2D/3D/Tracks === 'circle'
5. CATEGORY_COLORS.perception === '#ad1457'

Both files' `describe.skip(...)` wrappers flipped to `describe(...)`; 0 remaining skips in either file.

## Verification

- `grep -c "'Detections2D'\|'Detections3D'\|'Tracks'" frontend/src/utils/pipelineTypes.ts` → 3 ✓
- `grep -c "'perception'" frontend/src/utils/pipelineTypes.ts` → 1 ✓
- `grep -c "export function findPortTypeMismatches" frontend/src/utils/pipelineValidation.ts` → 1 ✓
- `grep -c "has mismatched types" frontend/src/utils/pipelineValidation.ts` → 1 ✓
- `grep -n "findPortTypeMismatches" frontend/src/utils/pipelineValidation.ts` → 2 hits (line 90 def, line 139 validateGraph hook) ✓
- findPortTypeMismatches hook (line 139) appears BEFORE findUnconnectedPorts call (line 142) BEFORE findMissingOutput (line 145) ✓
- `grep -c "describe.skip"` on both test files → 0 ✓

**Typecheck:** Deferred to wave-2 gate. Frontend node_modules not installed in this worktree so `tsc --noEmit` cannot run locally; the plan's `<verify>` block documents that standalone Plan 06 sampling will fail typecheck (by design — Plan 07-07 must co-land PORT_COLORS / NODE_DEFINITIONS entries before `Record<PortDataType, string>` exhaustiveness holds). The wave-2 checker runs typecheck + vitest after both plans land.

## Deviations from Plan

### Auto-fixed Issues

None.

### Plan-Text Divergences

**Test case 4 ("emits mismatch error in CONTEXT D-09 literal format") — cleaner expected-string construction.**

- **Found during:** Task 2 test authoring.
- **Issue:** The plan's inlined test body reads `srcNode.data.label`.PointCloud (PointCloud) — hardcoding the port label as "PointCloud" while simultaneously commenting that it comes from the `slam_generic.cloud_out` port whose actual label is `"PointCloud"` (confirmed in nodeDefinitions.ts:73). The plan also contained draft scratchpad ("Actually depth_out IS Image ... Instead use slam cloud → detector image") that was not intended to ship.
- **Fix:** Compute expected string via the actual PortDef lookups (`slam.data.outputs.find(p => p.id === 'cloud_out')`) rather than hardcoded literals, so the test remains correct if the label text ever changes in nodeDefinitions.ts. Same behavioral intent; less brittle test code.
- **Files modified:** `frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts`
- **Commit:** cb0fced (tracked as part of Task 2)

No other divergences from the plan.

## Known Stubs

None. No placeholder UI, no hardcoded empty renders, no TODO markers in shipped code. The `describe.skip → describe` transition removes the existing scaffold stubs.

## Deferred Issues

None. All acceptance criteria of Plan 07-06 satisfied; the typecheck + vitest green state is the wave-2 gate responsibility (Plan 07-07 co-commits nodeDefinitions extensions).

## Wave-Level Coupling (Plan 07-07 dependency)

This plan's test files import `buildNodeData('detector_generic')` and `buildNodeData('tracker_generic')` — node definitions that land in Plan 07-07. Plan 07-06 standalone typecheck and vitest runs will fail on:
- `portColors.test.ts`: missing `PORT_COLORS.Detections2D / Detections3D / Tracks` and `CATEGORY_COLORS.perception` keys.
- `pipelineValidation.typeMismatch.test.ts`: missing `NODE_DEFINITIONS.detector_generic / tracker_generic`.
- `nodeDefinitions.ts`: `Record<PortDataType, string>` exhaustiveness failure once this plan's union extension lands.

These failures are the intentional wave-2 coupling. The wave-2 checker runs typecheck + vitest AFTER both Plan 07-06 and Plan 07-07 land; both must be green at that checkpoint.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced in this plan. Threat model T-07-15 (malformed sourceHandle/targetHandle) is mitigated by the `continue` guards in findPortTypeMismatches (lines `if (!src || !tgt) continue` and `if (!srcPort || !tgtPort) continue`).

## Self-Check: PASSED

- FOUND: frontend/src/utils/pipelineTypes.ts
- FOUND: frontend/src/utils/pipelineValidation.ts
- FOUND: frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts
- FOUND: frontend/src/utils/__tests__/portColors.test.ts
- FOUND commit: e3fb5b2 (feat(07-06): extend PortDataType + NodeCategory unions)
- FOUND commit: cb0fced (feat(07-06): add findPortTypeMismatches + hook into validateGraph)
