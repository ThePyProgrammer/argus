---
phase: 14-interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters
plan: 02
subsystem: api
tags: [fastapi, pipeline-builder, dag-validation, presets, node-catalog]

requires:
  - phase: 08-backend-abstraction-icp-wrap
    provides: SLAMRegistry and MergeRegistry for node catalog discovery
provides:
  - PipelineBuilder with DAG validation (cycle, unknown type, unconnected port detection)
  - NodeCatalog aggregating 9 static + registry-discovered SLAM/merge nodes
  - Pipeline REST API (apply, node-catalog, presets CRUD)
  - 3 built-in pipeline presets (Default ICP, PGO High Quality, Comparison Mode)
affects: [14-03, 14-04, 14-05, 14-06]

tech-stack:
  added: []
  patterns: [pipeline-builder-graph-validation, preset-json-storage, kahn-topological-sort]

key-files:
  created:
    - src/coordination/pipeline_builder.py
    - backend/web/pipeline_routes.py
    - data/presets/builtin/default_icp.json
    - data/presets/builtin/pgo_high_quality.json
    - data/presets/builtin/comparison_mode.json
    - tests/coordination/test_pipeline_builder.py
    - tests/web/test_pipeline_routes.py
  modified:
    - backend/web/server.py
    - src/coordination/merge_registry.py

key-decisions:
  - "Kahn's algorithm for topological sort / cycle detection in PipelineBuilder"
  - "param_scalar nodes override target params via edge targetHandle mapping"
  - "Preset storage uses flat JSON files in data/presets/{builtin,user}/"
  - "Pipeline routes at /api/pipeline/* prefix, separate from /api/slam/*"

patterns-established:
  - "Graph validation: Kahn's topo sort for DAG enforcement, prefix-based type dispatch"
  - "Preset CRUD: builtin read-only, user writable, filesystem-backed JSON"

requirements-completed: [P14-BUILDER, P14-ROUTES, P14-PRESETS]

duration: 5min
completed: 2026-03-23
---

# Phase 14 Plan 02: Backend Pipeline System Summary

**PipelineBuilder with DAG validation, NodeCatalog aggregating registries, REST API for apply/catalog/presets, and 3 built-in pipeline preset configs**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-23T15:30:45Z
- **Completed:** 2026-03-23T15:36:01Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- PipelineBuilder validates graph JSON: rejects cycles (Kahn's algorithm), unknown node types, unconnected required inputs, resolves param_scalar overrides
- NodeCatalog aggregates 9 static node types + dynamic SLAM/merge nodes from registries
- Pipeline REST API: POST /apply, GET /node-catalog, GET/POST/DELETE /presets with builtin/user separation
- Three built-in presets: Default ICP (linear pipeline), PGO High Quality (with filter), Comparison Mode (diamond with splitter/combiner)
- All 12 tests pass (6 builder + 6 routes)

## Task Commits

Each task was committed atomically:

1. **Task 1: PipelineBuilder, NodeCatalog, and unit tests** - `923e846` (test RED) -> `0097a05` (feat GREEN)
2. **Task 2: Pipeline REST routes, preset storage, wire into server** - `857b0bd` (test RED) -> `42bc410` (feat GREEN)

_TDD tasks have RED/GREEN commits._

## Files Created/Modified
- `src/coordination/pipeline_builder.py` - PipelineBuilder, PipelineConfig, NodeCatalog classes
- `backend/web/pipeline_routes.py` - Pipeline REST API (apply, catalog, presets CRUD)
- `backend/web/server.py` - Wired pipeline_router into create_app()
- `data/presets/builtin/default_icp.json` - Default ICP pipeline preset
- `data/presets/builtin/pgo_high_quality.json` - PGO High Quality with voxel filter
- `data/presets/builtin/comparison_mode.json` - Comparison mode with dual SLAM backends
- `tests/coordination/test_pipeline_builder.py` - 6 builder unit tests
- `tests/web/test_pipeline_routes.py` - 6 route integration tests
- `src/coordination/merge_registry.py` - Fixed dict-changed-during-iteration bug

## Decisions Made
- Kahn's algorithm for topological sort / cycle detection in PipelineBuilder
- param_scalar nodes override target params via edge targetHandle mapping
- Preset storage uses flat JSON files in data/presets/{builtin,user}/
- Pipeline routes at /api/pipeline/* prefix, separate from /api/slam/*

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed MergeRegistry.list_strategies() iteration bug**
- **Found during:** Task 1
- **Issue:** MergeRegistry.list_strategies() iterates cls._strategies.items() without list() wrapper, causing RuntimeError when _load_class triggers decorator registration
- **Fix:** Changed to list(cls._strategies.items()) matching SLAMRegistry pattern
- **Files modified:** src/coordination/merge_registry.py
- **Verification:** All merge registry tests still pass (12/12)
- **Committed in:** 0097a05

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Pre-existing bug fix necessary for PipelineBuilder to call list_strategies(). No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend pipeline infrastructure complete for frontend canvas (Plan 03) and node palette (Plan 04)
- NodeCatalog ready to serve GET /api/pipeline/node-catalog for drag-and-drop palette
- PipelineBuilder ready to validate and interpret graphs from POST /api/pipeline/apply
- Presets ready for preset selector UI

---
*Phase: 14-interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters*
*Completed: 2026-03-23*
