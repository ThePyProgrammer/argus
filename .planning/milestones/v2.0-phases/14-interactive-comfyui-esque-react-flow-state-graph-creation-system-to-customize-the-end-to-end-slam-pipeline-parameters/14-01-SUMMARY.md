---
phase: 14-interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters
plan: 01
subsystem: ui
tags: [react-flow, xyflow, zustand, typescript, pipeline-graph, node-editor]

requires:
  - phase: 09-frontend-slam-controls-live-tuning-ui
    provides: Zustand flat store pattern (slamStore, controlStore), ParameterPanel rendering
  - phase: 08-backend-abstraction-icp-wrap
    provides: SLAMRegistry, SLAMBackend parameter_schema shape
provides:
  - Pipeline type system (PortDataType, PortDef, PipelineNodeData, PipelineEdge, PipelineConfig, NodeDefinition)
  - Node definitions with 11 types across 7 categories (PORT_COLORS, PORT_SHAPES, CATEGORY_COLORS, NODE_DEFINITIONS, buildNodeData)
  - Graph validation (cycle detection via Kahn's algorithm, unconnected port detection, missing output check)
  - Graph serialization with parameter node override resolution
  - Zustand pipelineStore with React Flow integration (onNodesChange, onEdgesChange, onConnect)
affects: [14-02, 14-03, 14-04, 14-05, 14-06]

tech-stack:
  added: ["@xyflow/react"]
  patterns: ["React Flow external store pattern", "typed port system", "graph validation via topological sort"]

key-files:
  created:
    - frontend/src/utils/pipelineTypes.ts
    - frontend/src/utils/nodeDefinitions.ts
    - frontend/src/utils/pipelineValidation.ts
    - frontend/src/utils/pipelineSerializer.ts
    - frontend/src/stores/pipelineStore.ts
  modified:
    - frontend/package.json

key-decisions:
  - "Used type alias (not interface) for PipelineNodeData and PipelineEdgeData to satisfy React Flow's Record<string, unknown> generic constraint"
  - "Parameter node override resolution via edge traversal in serializer -- parameter nodes inject their value into connected target node params"

patterns-established:
  - "Pipeline type system: all node/edge/port types centralized in pipelineTypes.ts"
  - "Node definitions registry: NODE_DEFINITIONS + buildNodeData() factory for creating node instances"
  - "Graph validation pipeline: validateGraph() runs cycle, unconnected, and missing-output checks in order"

requirements-completed: [P14-TYPES, P14-STORE]

duration: 3min
completed: 2026-03-23
---

# Phase 14 Plan 01: Pipeline Type System and Store Summary

**Pipeline type system with 7 port data types, 11 node definitions across 7 categories, Kahn's algorithm graph validation, parameter-override-aware serializer, and Zustand pipelineStore with React Flow integration**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T15:30:48Z
- **Completed:** 2026-03-23T15:34:28Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Installed @xyflow/react and defined complete pipeline type system (PortDataType, PortDef, PipelineNodeData, PipelineEdge, PresetInfo, ValidationError, PipelineConfig, NodeDefinition)
- Created 11 node definitions covering sensors, SLAM, merger, filters, splitter/combiner, parameter, and output categories with typed ports and parameter schemas
- Implemented graph validation with Kahn's algorithm cycle detection, unconnected required port detection, and missing output node check
- Built pipelineSerializer with parameter node override resolution via edge traversal
- Created pipelineStore following existing Zustand flat store pattern with React Flow callbacks integration

## Task Commits

1. **Task 1: Install @xyflow/react and create pipeline type system + node definitions** - `5b21f4a` (feat)
2. **Task 2: Create pipelineValidation, pipelineSerializer, and pipelineStore** - `af054e6` (feat)

## Files Created/Modified
- `frontend/package.json` - Added @xyflow/react dependency
- `frontend/src/utils/pipelineTypes.ts` - All TypeScript types for pipeline nodes, edges, ports, presets, config
- `frontend/src/utils/nodeDefinitions.ts` - PORT_COLORS, PORT_SHAPES, CATEGORY_COLORS, NODE_DEFINITIONS (11 types), buildNodeData()
- `frontend/src/utils/pipelineValidation.ts` - detectCycles (Kahn's), findUnconnectedPorts, findMissingOutput, validateGraph
- `frontend/src/utils/pipelineSerializer.ts` - serializeGraph (with parameter node override resolution), deserializeGraph
- `frontend/src/stores/pipelineStore.ts` - Zustand store with React Flow integration, all actions per spec

## Decisions Made
- Used `type` alias instead of `interface` for PipelineNodeData and PipelineEdgeData because React Flow v12 generic constraints require `Record<string, unknown>` compatibility, which TypeScript interfaces don't satisfy due to missing index signatures
- Parameter node override resolution implemented in serializer (not store) -- the serializer traverses edges to find parameter category source nodes and injects their `value` into the target node's params keyed by targetHandle name

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed PipelineNodeData/PipelineEdgeData type constraint for React Flow**
- **Found during:** Task 1 (type system creation)
- **Issue:** React Flow's `Node<T>` and `Edge<T>` require `T extends Record<string, unknown>`, but TypeScript interfaces don't satisfy index signature constraints
- **Fix:** Changed `interface` to `type` alias for PipelineNodeData and PipelineEdgeData
- **Files modified:** frontend/src/utils/pipelineTypes.ts
- **Verification:** `npx tsc --noEmit` passes with no new errors
- **Committed in:** 5b21f4a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minimal -- type alias vs interface is functionally equivalent for consumers. No scope creep.

## Issues Encountered
None - pre-existing TypeScript errors in DetectionBoxes.ts, SceneViewer.tsx, and useWebSocket.ts are unrelated to this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 5 TypeScript utility files and store are ready for Plan 02 (PipelineNode component, PortHandle, EdgeAnimated)
- @xyflow/react installed and types verified
- pipelineStore actions ready for React Flow canvas integration

---
*Phase: 14-interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters*
*Completed: 2026-03-23*
