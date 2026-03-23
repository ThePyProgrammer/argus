---
phase: 07-cleanup-and-verification-gaps
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, test-fixes, mujoco, streaming-viz]

# Dependency graph
requires:
  - phase: 06-react-c2-web-interface
    provides: "WebStreamingViz and web test infrastructure"
  - phase: 05-locomotion-and-physics
    provides: "Go2 locomotion tests and model path references"
  - phase: 03-multi-robot-coordination
    provides: "MultiRobotConfig and multi-bridge tests"
provides:
  - "Clean non-integration test suite with correct assertions"
  - "pytest-asyncio for async web test support"
affects: [07-cleanup-and-verification-gaps]

# Tech tracking
tech-stack:
  added: [pytest-asyncio]
  patterns: [robot-tint-fallback-in-true-rgb-mode]

key-files:
  created: []
  modified:
    - tests/bridge/test_multi_bridge.py
    - tests/locomotion/test_locomotion.py
    - tests/web/test_streaming_viz.py
    - pyproject.toml

key-decisions:
  - "true_rgb color mode falls back to robot_tint when no per-point RGB data available -- test updated to match"
  - "pytest-asyncio added to dev dependencies (not web) since it is a test-time concern"

patterns-established:
  - "Model path resolution: use parent.parent.parent from test files to reach project root"

requirements-completed: [VIZ-01]

# Metrics
duration: 2min
completed: 2026-03-23
---

# Phase 07 Plan 01: Fix Stale Tests Summary

**Fixed 3 stale test assertions (sim_steps default, model path, true_rgb fallback) and added pytest-asyncio for async web tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-23T02:27:22Z
- **Completed:** 2026-03-23T02:29:44Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Corrected sim_steps_per_frame assertion from 10 to 5 matching actual MultiRobotConfig default
- Fixed GO2_XML path to resolve from project root (3 parent levels) instead of tests directory
- Updated true_rgb color mode test to expect robot_tint fallback colors [230, 159, 0] when no per-point RGB data exists
- Added pytest-asyncio to dev dependencies, enabling 2 async ConnectionManager tests to run without warnings

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix stale test assertions and missing model paths** - `d65f3bb` (fix)
2. **Task 2: Install pytest-asyncio and fix async test configuration** - `25d5c64` (chore)

## Files Created/Modified
- `tests/bridge/test_multi_bridge.py` - Fixed sim_steps_per_frame assertion (10 -> 5)
- `tests/locomotion/test_locomotion.py` - Fixed GO2_XML path (parent.parent -> parent.parent.parent)
- `tests/web/test_streaming_viz.py` - Fixed true_rgb test to expect robot_tint fallback colors
- `pyproject.toml` - Added pytest-asyncio>=0.23.0 to dev dependencies

## Decisions Made
- true_rgb color mode implementation falls back to robot_tint coloring when no SLAM point cloud RGB data is available in robot_data (no slam_cloud_pts/slam_cloud_rgb keys). Test updated to match this behavior rather than the original white placeholder expectation.
- pytest-asyncio placed in dev dependencies group alongside pytest and pytest-timeout.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing cv2 (opencv) import failures in TestCameraFrame tests -- opencv-python-headless is listed in main dependencies but not installed in test environment. Out of scope for this plan.
- Pre-existing httpx missing for test_web_server.py collection. Out of scope.
- Pre-existing stale mocks and changed defaults in coordination/exploration tests. Out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Target test files (bridge, locomotion, web streaming) pass all non-integration tests
- 161 tests collected with zero collection errors (excluding pre-existing httpx issue)
- Ready for plan 07-02 to address remaining test gaps

---
*Phase: 07-cleanup-and-verification-gaps*
*Completed: 2026-03-23*
