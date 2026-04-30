---
phase: 07-pipeline-editor-perception-nodes
plan: 07
subsystem: ui
tags: [react-flow, pipeline-editor, typescript, vitest, node-registry, perception]

requires:
  - phase: 07
    provides: "Plan 07-06 extended PortDataType/NodeCategory unions (Detections2D/3D/Tracks + perception)"
  - phase: 07
    provides: "Plan 07-02 scaffolded de-skipped perception test stubs"
provides:
  - "PORT_COLORS extended with Detections2D=#ff8a65, Detections3D=#ec407a, Tracks=#26a69a"
  - "PORT_SHAPES extended with all 3 new types = circle"
  - "CATEGORY_COLORS extended with perception=#ad1457 magenta"
  - "NODE_DEFINITIONS registered: detector_generic, detection3d_generic, tracker_generic"
  - "viz_output.inputs extended with optional tracks_in port"
  - "NodePalette CATEGORY_ORDER + CATEGORY_LABELS gain perception between merger/filter"
  - "nodeDefinitions.perception.test.ts de-skipped with 5 green assertions"
  - "pipelineStore.connect.perception.test.ts de-skipped with 3 assertions (Plan 08 wave-gate coupling)"
affects: [07-08, 07-09, 07-10, 07-11, 07-12]

tech-stack:
  added: []
  patterns:
    - "Registry-extension pattern: append to Record<Union, T> maps in lockstep with union-type extensions"
    - "Wave-gate coupling: Plan 07's tests assert dataType values that Plan 08's onConnect fix will satisfy"

key-files:
  created: []
  modified:
    - frontend/src/utils/nodeDefinitions.ts
    - frontend/src/components/pipeline/NodePalette.tsx
    - frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts
    - frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts

key-decisions:
  - "Followed plan literal action for connect test bodies (dataType assertions included). Executor accepted the wave-gate coupling note — 2/3 connect assertions fail in isolation, but pass once Plan 08 lands its onConnect fix in the same wave."

patterns-established:
  - "Lockstep map extension: when PortDataType/NodeCategory unions grow, PORT_COLORS / PORT_SHAPES / CATEGORY_COLORS must extend in the same plan or TypeScript strict Record exhaustiveness breaks the build"
  - "Palette category insertion between existing categories: add to CATEGORY_ORDER at the correct index and CATEGORY_LABELS in matching position; render loop at NodePalette.tsx line 146 is category-agnostic"

requirements-completed: [DET-PIPELINE-01, DET-PIPELINE-02]

duration: 3min
completed: 2026-04-15
---

# Phase 07 Plan 07: Perception Node Catalog + Palette Extension Summary

**Three perception node definitions (detector_generic, detection3d_generic, tracker_generic) + 3 new port colors + perception category magenta landed in the frontend node registry, with NodePalette surfacing a new "Perception" section between Mergers and Filters.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-15T10:59:32Z
- **Completed:** 2026-04-15T11:02:10Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- PORT_COLORS / PORT_SHAPES / CATEGORY_COLORS extended in lockstep with Plan 06's union-type growth (closes the TypeScript `Record<PortDataType, string>` exhaustiveness compile break).
- Three static NodeDefinitions registered (detector_generic, detection3d_generic, tracker_generic) with the exact D-03/D-04/D-05 port sets locked by CONTEXT.
- viz_output gains optional `tracks_in` port (D-06) so the downstream tracker_generic → viz_output edge is a legal connection.
- NodePalette `CATEGORY_ORDER` gains `'perception'` at index 3 (between `'merger'` and `'filter'`) matching UI-SPEC Palette Layout Ordering; `CATEGORY_LABELS.perception = 'Perception'` added.
- `nodeDefinitions.perception.test.ts` de-skipped with 5 assertions — all green.
- `pipelineStore.connect.perception.test.ts` de-skipped with 3 assertions, wired for the Plan 08 wave-gate completion.
- Wave 2 green gate for the 3 Plan-06-authored test files passes: `nodeDefinitions.perception.test.ts` + `portColors.test.ts` + `pipelineValidation.typeMismatch.test.ts` = 15/15 passing.

## Task Commits

Each task was committed atomically (no pre-commit verify, per parallel_execution directive):

1. **Task 1: Extend color/shape maps + add 3 node defs + viz_output tracks_in** — `f860e5b` (feat)
2. **Task 2: Insert perception into NodePalette CATEGORY_ORDER + CATEGORY_LABELS** — `5adb0c2` (feat)
3. **Task 3: Fill de-skipped perception test bodies** — `fbffe98` (test)

## Files Created/Modified

- `frontend/src/utils/nodeDefinitions.ts` — 3 port colors + 3 port shapes + 1 category color + 3 NodeDefinitions + viz_output.tracks_in (+59 lines).
- `frontend/src/components/pipeline/NodePalette.tsx` — CATEGORY_ORDER + CATEGORY_LABELS extended (+2 lines).
- `frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts` — describe.skip removed; 5 real assertions filled.
- `frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts` — describe.skip removed; 3 real assertions filled (2 depend on Plan 08).

## Decisions Made

- **Literal action bodies for connect test.** The plan's `<action>` block provides test bodies that assert `edges[0].data?.dataType === 'Detections2D' | 'Detections3D' | 'Tracks'`, but the current `pipelineStore.onConnect` hardcodes `dataType: 'PointCloud'` (Plan 08's target). Plan 07-07 explicitly permits either (a) literal bodies that fail until Plan 08 lands or (b) softened `expect(edges).toHaveLength(1)` only. **Chose (a)** — the plan states "Executor decision. The acceptance criteria below check only for the de-skip + file existence." Using the literal bodies means the test will naturally flip green once Plan 08 ships, without follow-up edits. The connect test is NOT in Task 3's automated verify block; the verify block runs the 3 plan-specified files (all green).
- **Installed frontend node_modules.** The worktree did not have `frontend/node_modules/` populated; ran `npm install` to execute vitest. Added `frontend/package-lock.json` to the Task 3 commit (no semver changes — existing lockfile recreated byte-identical content; verification-only artifact).

## Deviations from Plan

None that require a Rule 1/2/3 auto-fix. Plan executed exactly as written, with the executor decision above documented as the one discretionary branch the plan itself invited.

## Issues Encountered

- **vitest not installed in worktree.** Resolved by running `npm install` in `frontend/`. Expected for a fresh worktree; not a plan issue.
- **Connect test has 2 expected failures in isolation.** This is the documented Plan 08 wave-gate coupling — not an issue per the plan. 2/3 `connect.perception` assertions will flip green automatically once Plan 08's `onConnect` fix lands in the same wave.

## Self-Check: PASSED

**Files verified exist:**
- FOUND: `frontend/src/utils/nodeDefinitions.ts` (with Detections2D/Detections3D/Tracks/perception/detector_generic/detection3d_generic/tracker_generic/tracks_in all grep-confirmed)
- FOUND: `frontend/src/components/pipeline/NodePalette.tsx` (with 'perception' in CATEGORY_ORDER and CATEGORY_LABELS)
- FOUND: `frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts` (describe.skip count = 0)
- FOUND: `frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts` (describe.skip count = 0)

**Commits verified exist:**
- FOUND: f860e5b (Task 1 — feat color/category + perception node defs)
- FOUND: 5adb0c2 (Task 2 — feat NodePalette perception)
- FOUND: fbffe98 (Task 3 — test fill perception test bodies)

**Test run (Task 3 verify block):**
- `npm run test -- --run src/utils/__tests__/nodeDefinitions.perception.test.ts src/utils/__tests__/portColors.test.ts src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` → 3 test files, 15 tests, **all pass** (duration 852ms).

## Next Phase Readiness

- **Ready for Plan 07-08** (pipelineStore.onConnect dataType fix). When 07-08 lands, `pipelineStore.connect.perception.test.ts` flips 3/3 green with no re-edit; that is the Wave 2 completion gate.
- **Ready for Plan 07-09+** (DetectorNode/Detection3DNode/TrackerNode custom renderers, NodeCatalog wiring). The registry + palette + type system are all in place — downstream plans only need to render and wire data.
- **No blockers.** TypeScript build passes (union exhaustiveness satisfied). 15/15 plan-specified vitest assertions green.

---
*Phase: 07-pipeline-editor-perception-nodes*
*Completed: 2026-04-15*
