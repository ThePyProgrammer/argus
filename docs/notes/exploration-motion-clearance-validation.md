# Execution clearance development — Issue #4

November 14, 2026. This is a development guard, not a general collision-safety
certificate. Live results and the remaining acceptance work are recorded below.

## Runtime changes

All `ExplorationLoop.step_once` proposals pass through `MotionClearanceGuard`:
bootstrap, normal waypoints, pure turns, reverse recovery, and idle. The guard
uses estimated body poses, observed occupancy, and static model calibration.
Simulator world poses and reference obstacles are not runtime guard inputs.

The Go2 bridge derives a **0.658494 m** containing sphere from fixed collision
geometry, allowing every hip, thigh, and knee rotation and every body attitude.
Unsupported geometry/layout changes fail calibration. This replaces the runtime
assumption that knees remain in Issue #3's narrower certified interval; it does
not assume that physically unstable joint configurations are safe to execute.
Planning and execution share the maximum of that sphere, configured body radius,
and camera offset plus stand-off, then add the existing margin and raster term.
The resulting radius is **0.779205 m** on the default 0.10 m grid.

Recent estimated poses supply planar velocity and yaw rate. Prediction includes
a 0.30 s command horizon, 0.10 s reaction interval, 1 m/s² modeled braking,
0.05 m/s growing drift allowance, and the default gait's 8 rad/s² active-yaw
slew. Both delayed and immediate translation responses are checked. These are
development assumptions, not a proven enclosure of all physical trajectories.
Commands are tried at full, half, and quarter scale, otherwise stopped. Even an
idle proposal checks residual motion. A rejected stopping tail is explicitly
reported: sending zero cannot undo momentum or an already-invalid clearance.

Stale observations/poses, missing calibration, tracking loss, excessive estimated
motion, and lateral command requests stop motion. Predicted center travel through
unknown cells is rejected. Footprint space outside that center route is checked
against known obstacles only; unseen obstacles and map/pose errors remain limits.
The planner still allows unknown cells with a penalty, so repeated rejected
routes remain an integration concern for #5. Rejection clears the route and
cancels blind recovery; it does not implement bounded recovery retries.

Command records include each robot's reason, scale, radius, stopping status, and
local clearance diagnostic. `clearance_m` is slack against nearby occupied-cell
centers after allowances, not ground-truth camera clearance; null means no nearby
obstacle was measured or the decision ended before that check.

The physical reverse fixture also exposed a gait bug: stride used unsigned speed,
so negative forward velocity produced a forward stride. Stride now preserves the
longitudinal sign. Episode provenance records this separately from the yaw fix.

## Tests

The affected suite passed **775 tests with seven skips**:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -m pytest tests/exploration tests/control tests/coordination tests/bridge tests/locomotion/test_gait_controller.py tests/locomotion/test_gait_clearance.py tests/locomotion/test_gait_transitions.py -q -p no:cacheprovider --basetemp outputs/exploration-planning/motion-clearance/test-tmp-02
```

The first broad invocation had 49 setup errors because its temporary-directory
parent did not exist, plus three incomplete bridge fixtures. The parent and
fixtures were corrected; the complete rerun above passed. Older proposal-level
exploration tests isolate the guard; the separate integration fixtures exercise
the actual guard at every command branch.

Unit fixtures cover forward/reverse walls at both grid resolutions, turns,
diagonal crossings, residual drift while idle, unknown routes, stale/missing
inputs, yaw reversal, and default stopping prediction. Integration tests exercise
the real guard for bootstrap, waypoint, and recovery proposals, with poisoned
ground-truth poses and independently guarded teammates.

Two three-second MuJoCo unit fixtures use an explicitly perfect pose/map oracle
to isolate physical forward/reverse behavior. They require actual displacement
in the requested direction, camera stand-off of at least 0.15 m, no sampled wall
contact, and body height above 0.20 m. These are unit physics checks, not live
exploration attempts or evidence that estimated maps are accurate.

## Live validation

Both seed-101 attempts used runtime **`1646b07`**, one OpenMP thread, and unchanged
source hashes. They ran concurrently, so wall durations are not performance
benchmarks. Each retained diagnostics and a verified video with recorded coverage.

| Attempt | Actual/requested duration | Coverage, initial → final | Team travel | Minimum sampled camera stand-off | Non-foot contacts |
| --- | --- | --- | --- | --- | --- |
| [Clutter video](../../outputs/exploration-planning/motion-clearance/cluttered-room-01/top-view.mp4) | 10.00/10.00 s | 14.6569% → 36.7320% | 1.1814 m | A: 0.35785 m; B: 0.33057 m | One rear-calf/floor event |
| [Connected-room video](../../outputs/exploration-planning/motion-clearance/connected-rooms-01/top-view.mp4) | 5.00/5.00 s | 58.2179% → 76.5202% | 1.5087 m | A: 1.54279 m; B: 0.71093 m | One rear-calf/floor event |

Both terminated at the horizon with zero falls, recovery entries, and failed A*
planning attempts. Detailed physics-step measurements report zero robot-obstacle
or robot-robot contacts. The legacy contact counter reports one "robot_obstacle"
episode in each run because it groups non-foot floor contact into that category;
the detailed classification above identifies the actual event. These runs are
**not contact-free**. Neither reaches the 90% coverage threshold.

Video replay verifies **1001 clutter states** and **501 connected-room states**,
both with zero body-position error. Verification reports are beside each video.
Clearance summaries are retained as `clearance-summary.json` in each attempt.
The offline comparator reconstructs camera pose from saved true body poses and
the fixed mount. Distances are camera-point XY distances to static rectangular
obstacles and walls at saved pre-decision sensor times, excluding other robots
and the final post-command state. They are not continuous-time or whole-body
distance certificates. Peak planar body-pose errors over those samples were
2.848/0.495 mm for clutter A/B and 2.516/1.428 mm for connected rooms A/B.

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/motion-clearance/cluttered-room-01
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/motion-clearance/connected-rooms-01
```

These are reproduction records; reruns must use new output directories.

## Remaining failures and issue status

**Issue #4 remains open.** The historical 12.9 cm camera proximity was not repeated
in this clutter attempt, but the guard's stopping model and gait interaction are
not validated as a general physical bound. Clutter A had 41 and B 756 decisions
where even the modeled stopping tail was rejected. B's final slack was -10.06 mm
against the conservative map envelope. Zero commands do not prove that the robot
remained inside that envelope. A larger geometry radius alone cannot establish
a dynamics guarantee.

Clutter also exposes **#5** directly: A's last nonzero command was at 5.01 s and
B's at 2.41 s, although the episode continues to 10 s. Both terminal maps still
have reachable frontier cells. There were **1278 candidate-selection calls**,
zero failed A* attempts, and repeated execution rejections. Replanning can thus
find nominal routes while execution remains blocked. This requires explicit
blocked/replanning states, bounded retries, and checked recovery; reaching the
horizon while stopped is not successful exploration. No clearance bypass or
blind reverse was enabled.

The new command sequences also expose a **gait restart regression**:

| Attempt, robot A rear-right calf | Contact interval | Duration | Peak normal force | Normal impulse | Maximum penetration | Existing severity policy |
| --- | --- | --- | --- | --- | --- | --- |
| Clutter | 2.786–2.868 s | 82 ms | 76.304 N | 4.03644 N s | 1.436 mm | forceful_contact |
| Connected rooms | 3.754–3.762 s | 8 ms | 48.869 N | 0.33706 N s | 0.154 mm | unclassified_contact |

Full offline command replays in `clutter-replay-01` and `connected-replay-01`
exactly reproduce all body positions and these contact measurements. The contacts
occur after short idle/restart transitions into a turn, which reset active yaw
history. Halving active yaw acceleration from 8 to 4 rad/s² in separate offline
replays (`clutter-yaw4-01`, `connected-yaw4-01`) does **not** remove either contact;
the runtime default remains unchanged. This disproves that simple tuning as a
fix, without establishing a complete causal explanation. Changed-controller
replays claim no new exploration coverage. The original Issue #2 fixture remains
fixed; that narrow correction did not guarantee every restart sequence.

Next acceptance work for #4 is to isolate restart dynamics in a reduced physics
fixture, establish the stopping/drift model's physical limits, and rerun live
validation after correction. #5 owns bounded recovery and replanning behavior;
#6 still owns pose/floor/map error budgets and the broader multi-layout, multi-seed,
longer-horizon matrix. This pair of runs does not close any of those issues.
