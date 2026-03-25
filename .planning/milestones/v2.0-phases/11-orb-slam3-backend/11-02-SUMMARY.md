---
phase: 11-orb-slam3-backend
plan: 02
subsystem: slam, frontend, simulation
tags: [mujoco, orbslam3, three.js, tracking-status, textures]

requires:
  - phase: 11-01
    provides: ORB-SLAM3 backend implementation with SLAMProtocol
  - phase: 08-backend-abstraction-icp-wrap
    provides: SLAMProtocol, SLAMResult, TrackingStatus enum

provides:
  - Textured MuJoCo walls for ORB feature extraction in flat scenes
  - Tracking status color visualization on robot markers (green/red/yellow)
  - tracking_status field in Coordinator.get_robot_status() API
  - Full data pipeline: ExplorationLoop -> Coordinator -> StreamingViz -> WebSocket -> RobotMarker

affects: [12-openvins-backend, 13-svo-pro-backend]

tech-stack:
  added: []
  patterns:
    - "Tracking status stored on ExplorationLoop, propagated through RobotVizData to frontend"
    - "STATUS_COLORS constant in RobotMarker.ts for SLAM state visualization"

key-files:
  created: []
  modified:
    - src/bridge/scene_builder.py
    - models/unitree_go2/scene.xml
    - src/exploration/exploration_loop.py
    - src/coordination/coordinator.py
    - backend/web/streaming_viz.py
    - frontend/src/components/RobotMarker.ts
    - frontend/src/components/SceneViewer.tsx
    - frontend/src/stores/robotStore.ts
    - frontend/src/hooks/useWebSocket.ts
    - frontend/src/utils/messageTypes.ts

key-decisions:
  - "Store last_tracking_status on ExplorationLoop (closest to SLAMResult) rather than on RobotInstance"
  - "Propagate tracking_status via pose_update WS message (piggyback on existing frequent updates)"
  - "Use getattr with default 'ok' for backward compat with ICP backend (always returns OK)"

patterns-established:
  - "Tracking status propagation: ExplorationLoop.last_tracking_status -> RobotVizData -> pose_update WS -> RobotMarker color"

requirements-completed: [BACK-01, BACK-02]

duration: 7min
completed: 2026-03-23
---

# Phase 11 Plan 02: ORB-SLAM3 Scene Textures and Tracking Status Visualization

**Textured MuJoCo walls for ORB feature extraction plus robot marker color changes based on SLAM tracking status (green=OK, red=LOST, yellow=INITIALIZING/RELOCALIZING)**

## Performance

- **Duration:** ~70 min (includes post-checkpoint ORB-SLAM3 fixes)
- **Started:** 2026-03-23T07:33:27Z
- **Completed:** 2026-03-23T16:39:01Z
- **Tasks:** 3 of 3 (including human-verify checkpoint — approved by user)
- **Files modified:** 12

## Accomplishments
- Added checker and gradient wall textures to both flat scene (build_two_robot_scene) and single-robot scene (scene.xml)
- 4 boundary walls (north/south/east/west) provide visual features for ORB-SLAM3 feature extraction
- Full tracking status pipeline from SLAM backend through to frontend robot marker colors
- Robot markers change color in real-time: green (OK), red (LOST), yellow (INITIALIZING/RELOCALIZING)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add MuJoCo scene textures for ORB feature extraction** - `4d91670` (feat)
2. **Task 2: Frontend tracking status colors + coordinator wiring** - `76041c3` (feat)
3. **Task 3: End-to-end verification** - checkpoint approved by user
   - Post-checkpoint fix: `c67bc55` — Added Camera.bf and ThDepth to ORB-SLAM3 YAML config, fixed unavailable test
   - Post-checkpoint fix: `0ced1bf` — Inverted T_cw coordinate transform, seeded ground truth offset, INITIALIZING status before first track

**Plan metadata:** `0e23669` (docs: complete plan — updated post-checkpoint)

## Files Created/Modified
- `src/bridge/scene_builder.py` - Added wall_checker/wall_gradient textures and 4 boundary walls to flat scene
- `models/unitree_go2/scene.xml` - Added same textures and walls to single-robot scene
- `src/exploration/exploration_loop.py` - Store last_tracking_status from SLAMResult on each frame
- `src/coordination/coordinator.py` - Added tracking_status to get_robot_status() and RobotVizData
- `backend/web/streaming_viz.py` - Include tracking_status in pose_update WebSocket message
- `frontend/src/components/RobotMarker.ts` - STATUS_COLORS constant and trackingStatus-based coloring
- `frontend/src/components/SceneViewer.tsx` - Pass trackingStatus to updateRobot()
- `frontend/src/stores/robotStore.ts` - Added trackingStatus field to RobotInfo
- `frontend/src/hooks/useWebSocket.ts` - Pass tracking_status from pose_update to store
- `frontend/src/utils/messageTypes.ts` - Added tracking_status to PoseUpdatePayload

## Decisions Made
- Store last_tracking_status on ExplorationLoop rather than RobotInstance -- ExplorationLoop is closest to SLAMResult and already processes frames
- Propagate via pose_update WS message rather than a separate message -- reduces overhead, tracking status changes at the same cadence as poses
- Use getattr with default "ok" for backward compatibility -- ICP backend always returns OK status

## Deviations from Plan

### Auto-fixed Issues (Post-Checkpoint)

**1. [Rule 1 - Bug] Missing required ORB-SLAM3 RGBD YAML fields**
- **Found during:** Task 3 (end-to-end verification — after human checkpoint)
- **Issue:** ORB-SLAM3 RGBD mode requires Camera.bf (baseline×focal) and ThDepth (depth threshold) in the YAML config. These were absent, causing initialization failure.
- **Fix:** Added Camera.bf and ThDepth fields to the YAML config builder. Also fixed the `_AVAILABLE=False` test which wasn't properly blocking re-import.
- **Files modified:** `src/slam/backends/orbslam3_backend.py`, `tests/slam/test_orbslam3_backend.py`
- **Committed in:** `c67bc55`

**2. [Rule 1 - Bug] Incorrect ORB-SLAM3 coordinate transform and initialization behavior**
- **Found during:** Task 3 (end-to-end verification — after human checkpoint)
- **Issue:** ORB-SLAM3 returns T_cw (camera-in-world inverse) but code was treating it as T_wc directly. Map was also misaligned because no ground truth offset was seeded. Robots appeared at origin during initialization phase (LOST status was incorrect).
- **Fix:** Invert T_cw to T_wc before frame conversion. Seed ground truth offset from first frame so map aligns with MuJoCo world. Return INITIALIZING status (not LOST) before first successful track. Use ground truth pose during initialization so robots remain visible.
- **Files modified:** `src/slam/backends/orbslam3_backend.py`
- **Committed in:** `0ced1bf`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs discovered during human verification)
**Impact on plan:** Both fixes necessary for correct ORB-SLAM3 operation. No scope creep.

## Issues Encountered
- 2 pre-existing test failures found (test_default_values: stuck_threshold_steps config drift, test_path_through_gap: path planner edge case). Neither related to this plan's changes. All 126 SLAM/bridge/coordination tests pass.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ORB-SLAM3 backend fully integrated and human-verified ("ok looks about right")
- Textured scenes, tracking status visualization, and coordinate frame transform all correct
- Pre-existing test failures (stuck_threshold_steps config drift, path planner edge case) unrelated to this plan — should be addressed in a maintenance pass
- Phase 11 complete — ready for Phase 12 (OpenVINS + SVO Pro Backends)

---
*Phase: 11-orb-slam3-backend*
*Completed: 2026-03-23*
