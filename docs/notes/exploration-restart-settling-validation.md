# Restart and stopping dynamics — Issue #4 follow-up

November 15, 2026. This follows the failed live attempts recorded in
[execution clearance validation](exploration-motion-clearance-validation.md).
The new behavior remains a development model, not a general hardware safety bound.

## Reduced restart failure and correction

The earlier clutter and connected-room command traces reproduce their rear-calf
floor contacts exactly in offline physics replay. A smaller fixture needs only
three commands: turn at -1 rad/s for 0.47 s, idle for 0.01 s, then turn at
+1 rad/s for 0.50 s. The previous gait records a **28 ms calf-floor contact**.
The idle requests standing, but ten milliseconds does not complete the physical
load transfer before another diagonal pair lifts.

Runtime **`5e98b65`** adds `GaitParams.restart_settle_s = 0.08`. An idle command
immediately requests the standing pose and clears phase/yaw history. A restart
waits for the remainder of an **80 ms standing-command interval**, including time
already spent idle. Repeated idle/restart requests count down the same interval.
Initial motion and uninterrupted commands have no added delay. This interval
does not assert that body motion has stopped or that a stable stance was sensed.

The gait and execution predictor share `filter_gait_command`, including the
active-yaw slew, explicit idle, and restart countdown. Prediction still includes
physical momentum while standing is commanded. Episode provenance records
`standing_pose_restart_settle_v2` and `observed_pose_swept_stop_restart_v2`.

The 80 ms interval removes the reduced contact and both full recorded contacts.
Mirrored restart fixtures cover two preceding turn durations and idle periods of
10, 30, 100, and 180 ms. They require no non-foot contact, body height above
0.20 m, tilt below 0.30 rad, and at least 90% of the previous gait's one-second
turning progress. The older turn-to-walk progress and clearance checks also pass.
The focused shared-state/gait suite passes **86 tests**.

The final affected suite, including settled-idle recognition below, passes
**900 tests with seven skips**:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -m pytest tests/exploration tests/control tests/coordination tests/bridge tests/locomotion/test_gait_controller.py tests/locomotion/test_gait_clearance.py tests/locomotion/test_gait_transitions.py tests/locomotion/test_locomotion.py -q -p no:cacheprovider --basetemp outputs/exploration-planning/motion-clearance/test-tmp-rest-state-01
```

An earlier broad run found four bridge fixtures that assumed an immediate
restart after one idle frame. Those now verify immediate standing, the full
80 ms interval, and then the first fresh gait targets. The final suite above
includes these fixtures and all 75 physical stopping cases.

This interval was selected using development fixtures. Simply retaining phase
removed the recorded contacts but regressed older turn-to-walk cases. Restarting
the opposite diagonal pair severely slowed one turn direction; choosing a pair
by turn direction also regressed clearance/progress. A 100 ms standing interval
removed contacts but failed one existing progress requirement. Those alternatives
were rejected without loosening the requirement. These checks do not establish
robustness across every gait phase, surface, robot model, or command sequence.

Final-revision offline replays are preserved in
`outputs/exploration-planning/motion-clearance/restart-final-clutter-01/` and
`restart-final-connected-01/`. Both have zero non-foot contacts. Body trajectories
change, so these replays do not claim the original exploration coverage. All
earlier unsuccessful probes and the original live videos remain preserved.

## Stopping-envelope diagnosis

The prior clutter run reveals a separate model error. After B's last moving
command at 2.41 s, its body moves approximately **7.1 cm** during the following
standing transition. The original predictor, initialized with the 100 ms
estimated velocity average, predicts approximately **2.9 cm** of translation
before its drift allowance. For A the corresponding distances are approximately
7.0 cm and 4.5 cm. Commanding zero does not instantly remove momentum, and changes
in leg posture can also move the body in a different direction.

Exact-pose unit physics fixtures isolate this from SLAM/map error. At the original
defaults, seven of nine initial forward/turn stopping cases leave the predicted
path plus its declared drift allowance. Extending reaction time and reducing
braking acceleration alone still fail several expanded reverse/turn cases.

Runtime **`b5d2b9b`** adds a one-second settling horizon with 0.20 m/s growing drift allowance. It
covers all **45 calibration cases** (five speeds, three yaw commands, three gait
phases), plus **30 cases at two additional gait phases**. Checks follow physical
motion for one second after the stop and compare it with the complete predicted
swept path, including its between-sample allowance. Exact poses are unit-test
oracles only; runtime continues to consume estimated poses. This is empirical
development calibration, not a universal dynamics guarantee.

The reaction interval remains 0.10 s and modeled braking remains 1 m/s². The
prediction now lasts at least `hold + motion_settling_s`, even after modeled
velocity has reached zero. This retains space for the standing posture change.
Episode provenance identifies `observed_pose_swept_stop_settling_v3`; the complete
configuration records the parameters. No world truth enters the runtime guard.

The original 1.1 m forward/reverse wall fixtures retain their camera-clearance,
contact, standing-height, and stopping-clearance checks, but the larger uncertainty
reserve no longer permits useful progress there. New 1.5 m wall fixtures must
also demonstrate correctly directed displacement. The 1.1 m outcomes are not
counted as navigation successes. This explicit tradeoff is preferable to assuming
that a braking-only tail bounds the measured posture motion.

## Live validation and acceptance

The [restart-only connected-room video](../../outputs/exploration-planning/motion-clearance/restart-connected-live-01/top-view.mp4)
at `5e98b65` isolates the gait correction; its stopping configuration still uses
the original defaults. Seed 101 reached **5.00/5.00 s**, **77.1523% coverage**,
and **1.37630 m team travel**, with zero non-foot contacts, falls, recovery entries,
or failed planning attempts. Minimum saved-sample static-obstacle camera stand-off
was **0.71833 m**. Both robots still issued nonzero commands near the horizon.
All 501 body states verify with zero replay error; source hashes were unchanged.
The nearby `clearance-summary.json` records the sampled-distance scope and guard
decisions. This run removes the connected-room restart contact observed at the
previous revision; it does not validate the new stopping parameters.

The combined-correction attempts at **`b5d2b9b`** also reached their requested
horizons, with unchanged source hashes:

| Attempt | Actual/requested duration | Coverage | Team travel | Minimum sampled camera stand-off | Non-foot contacts / falls |
| --- | --- | --- | --- | --- | --- |
| [Connected-room video](../../outputs/exploration-planning/motion-clearance/settling-connected-live-01/top-view.mp4) | 5.00/5.00 s | 77.1523% | 1.37630 m | 0.71833 m | 0 / 0 |
| [Clutter video](../../outputs/exploration-planning/motion-clearance/settling-clutter-live-01/top-view.mp4) | 10.00/10.00 s | 31.2745% | 0.46186 m | 0.57511 m | 0 / 0 |

The connected-room run exactly matches the restart-only run: **500 commands,
501 body states, and every coverage sample**. The comparison is retained in
`settling-connected-live-01/restart-comparison.json`. Video verification checks
501/1001 body states with zero error. Camera distances retain the sampled static
XY scope described in the earlier execution note; they are not continuous-time
or inter-robot clearance certificates. Neither run reaches 90% coverage.

Clutter exposes the cost of the larger reserve. A's last nonzero command is at
3.22 s; B receives no nonzero command. Both terminal maps still have reachable
frontier cells, with **1654 candidate-selection calls and zero failed A* attempts**.
This is blocked execution and repeated replanning, not exploration success.

The run also exposed a state error in the stopping check: B was stationary for
the entire episode yet all 999 post-initial decisions reserved space for a fresh
standing transition. Its final stopping slack was -1.19 mm against that reserve.
That conservative rejection does not mean the body or camera touched an obstacle.

## Recognizing a settled robot

Runtime **`233ba70`** distinguishes an idle robot that has completed the modeled
settling interval from a fresh stop. It requires at least one second of commanded
standing, estimated planar speed below 0.01 m/s, and estimated yaw rate below
0.10 rad/s. Invalid or stale observations reset this history. Even a settled idle
retains reaction/braking prediction for its measured velocity and a drift
allowance over that shorter tail.

**Every new movement still uses the full settling envelope.** The exemption only
avoids inventing a new posture transition for a robot that remains standing; it
does not shrink the calibrated body radius, permit motion through obstacles,
or turn an unsafe route into a valid one. Tests cover stale timestamps, renewed
momentum, and rejecting a new turn from an otherwise-clear settled idle state.
Provenance records `observed_pose_swept_stop_settled_idle_v4`.

The [final clutter video](../../outputs/exploration-planning/motion-clearance/rest-state-clutter-live-01/top-view.mp4)
at `233ba70` reaches **10.00/10.00 s**, **31.2745% coverage**, and **0.46186 m
team travel**, with zero non-foot contacts, falls, recovery entries, or failed
A* attempts. Minimum sampled camera stand-off is **0.57511 m** for A and
**0.61188 m** for B. Peak sampled planar pose errors are 4.247 mm and 0.065 mm.
The source hashes remain unchanged; video verification checks all **1001 body
states with zero position error**.

All **1000 executed commands, 1001 body states, and coverage samples exactly
match** the preceding clutter attempt. This comparison excludes the clearance
diagnostics and is saved in `rest-state-clutter-live-01/settling-comparison.json`.
B now reports 100 `stopping_obstacle_clearance` decisions during the initial
settling window, followed by 899 `obstacle_clearance` decisions for proposed
movement. The correction changes the diagnosis of rest, not permission to move.
A still receives 677 `obstacle_clearance` decisions and stops moving after
3.22 s. B still receives no nonzero command; candidate selection still runs
1654 times. Both maps finish with reachable frontier cells. These are execution
rejections, not failed A* searches or a completed exploration task.

Reproduction commands (always choose fresh output directories):

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/motion-clearance/rest-state-clutter-live-02
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/motion-clearance/rest-state-connected-live-01
```

## Issue scope and remaining behavior

This completes **#4's development execution-clearance scope**: every command
branch is guarded, the unrestricted geometry bound replaces the conditional
knee assumption, stale inputs have a stop policy, yaw/restart state is shared
with the controller, physical stopping fixtures cover the calibrated tail, and
fresh videos report clearance, contacts, duration, and progress. The final
connected-room evidence is at `b5d2b9b`; the final clutter evidence is at
`233ba70`. The later settled-idle exemption is exercised by clutter and unit
tests; connected rooms did not contain a prolonged idle period.

This does **not** resolve sustained exploration. The clutter guard eliminates
the recorded contact while reducing coverage from the earlier guard's 36.7320%
to 31.2745%. The larger reserve prevents motion in some spaces, including the
tighter wall fixtures. **#5 remains open** for bounded execution-rejection
replanning, verified recovery where possible, and explicit trapped outcomes
without stopping a productive teammate. Recovery must preserve the guard and
the physical geometry; repeated planning alone is not recovery.

**#6 remains open** for pose/map uncertainty and multiple seeds, all three
layouts, and longer horizons. The 75 physical stopping cases and seed-101 live
runs are empirical development evidence, not a general collision certificate.
Unknown obstacles, accumulated map error, and motion outside the tested dynamics
remain limitations. All failed traces, probes, and live videos are preserved.
