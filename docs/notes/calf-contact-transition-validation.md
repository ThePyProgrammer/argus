# Rear-calf contact during a turn-to-walk transition (Issue #2)

## Isolated cause

The [Issue #1 validation](contact-severity-validation.md) measures robot A's
rear-right calf-floor event at 3.294–3.314 s: 20 ms duration, 39.9585 N peak
normal force, 0.317094 N s impulse, and 0.82121 mm maximum penetration.

`scripts/diagnose_gait_replay.py` replays the saved commands through the actual
bridge and Go2 controller without SLAM, navigation, or rendering. The original
controller behavior reproduces every recorded body position exactly and gives
the same contact measurements. The replay exports phase, joint targets/angles,
body roll/pitch/yaw, collision-shape clearance, and physics-step contact records.

At 3.21 s the command changes from turning in place at -1 rad/s to walking at
0.77655 m/s with +0.18419 rad/s yaw. The gait remains mid-swing (phase changes
from 0.24 to 0.27). The right hip target jumps from +0.15 to -0.02763 radians
in one 0.01 s control interval. The yaw change also reverses the differential
stride contribution. During the following swing-to-stance transition, body
pitch reaches about -0.1555 radians and roll about +0.1119 radians; the bent
rear calf enters the floor. Raising a foot alone does not establish calf clearance.

A smaller single-robot fixture reproduces a calf strike with this sequence:

1. Turn at +1 rad/s for 0.27 s.
2. Idle for 0.01 s.
3. Turn at -1 rad/s for 0.08 s.
4. Walk at 0.78 m/s with +0.18 rad/s yaw.

The old behavior strikes at about 0.45 s. Limiting active yaw changes removes
the strike. In this reduced sequence the preceding constant turns and idle
produce the same targets, so the intervention first changes the final
turn-to-walk transition. This isolates a command-transition contribution; it
does not establish that body attitude or phase is irrelevant to other contacts.

## Correction

`GaitParams.command_yaw_acceleration=8.0` bounds changes in the yaw command used
inside the active gait, using simulation `dt`. At the benchmark cadence this
limits yaw changes to 0.08 rad/s per frame and the corresponding hip target
change to 0.012 radians. The same filtered yaw drives differential stride and
the existing turn-dependent thigh allowance.

The first moving command uses its requested yaw. An explicit idle command
immediately returns all legs to standing and clears phase and yaw history.
Passing through zero yaw while an active reversal is requested does not reset
phase. Constant-command walking and turning targets remain exactly equal to
the former controller. Translation is not rate-limited.

An initial candidate limited both translation and yaw. It removed the contact
but reduced one-second transition travel below 90% of the old result in several
cases and was rejected. The yaw-only correction retains at least 90% across
the eight paired transition cases, with more than 0.15 m travel during the final
one-second walking phase, body height above 0.2 m, and tilt below 0.3 radians.
No contact-force or severity thresholds were changed.

## Offline replay evidence

The full five-second saved command sequence has the following outcomes:

| Measurement | Original yaw changes | Bounded yaw changes |
| --- | --- | --- |
| Non-foot contact events | 1 calf-floor | 0 |
| A minimum leg clearance at recorded frame boundaries | -0.818 mm | +12.148 mm |
| A minimum body height | 0.21846 m | 0.22360 m |
| A body XY travel between saved replay frames | 0.74952 m | 0.78619 m |
| B body XY travel between saved replay frames | 0.79307 m | 0.80223 m |

Clearance uses exact support heights of the box/cylinder/capsule/sphere collision
primitives above the fixture floor's top plane, excluding visual geometry.
For a box floor this extends its top plane; it does not measure edge distance.
The fixture robots remain over the floor footprint. Contact counts and force
measurements use every physics step. Replay frame summaries use sensor cadence.
The changed replay's maximum body-position difference from the old recording
is 0.10270 m, so old coverage is not a result for this new motion.

The retained artifacts are
[original replay](../../outputs/exploration-planning/calf-contact/replay-final-before/replay.json)
and [corrected replay](../../outputs/exploration-planning/calf-contact/replay-final-after/replay.json).
The former sets yaw acceleration to a very large finite value to reproduce
instantaneous updates, verified by zero error against all saved body positions.
Both record the gait parameters and source hash. Earlier development replays,
including a diagnostic failure, are preserved separately; they are offline
replays and do not claim fresh exploration coverage.

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe scripts/diagnose_gait_replay.py outputs/exploration-planning/contact-severity-validation/connected-rooms-01/diagnosis.json --output outputs/exploration-planning/calf-contact/replay-final-after
```

Use a new output directory for each replay.

## Automated and live validation

The complete locomotion suite, Go2 platform tests, control tests, real episode
tests, and exploration video-replay tests pass **361 tests**. This includes
unchanged straight-walk and constant-turn progress checks, stop/restart and idle
checks, mirrored transition sequences, the legacy-contact reproduction, yaw
slew timing at three control cadences, exact constant-command target equality,
phase continuity through zero yaw, and primitive-clearance calculations.

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -m pytest tests/locomotion tests/bridge/platforms/test_go2_platform.py tests/control tests/exploration/test_evaluation_episode.py tests/exploration/test_exploration_video.py -q -p no:cacheprovider --basetemp outputs/exploration-planning/calf-contact/test-tmp-01
```

The suite ran outside the Windows sandbox's temporary-directory restriction.
Real episode tests still produce matching commands and body trajectories with
measurement collection enabled and disabled.

Fresh connected-room validation uses runtime `59184ef`, seed 101, a requested
5 s horizon, and one OpenMP thread:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/calf-contact/connected-rooms-01
```

The live attempt completed the full **5.00 s** horizon with **74.909693% coverage**,
**zero non-foot contacts**, **zero falls**, **zero recovery entries**, and **zero
failed planning attempts**. All recorded source hashes remained unchanged during
the run. Its 842.37 s wall duration includes the episode and measurement work;
it is not an isolated timing benchmark.

| Live measurement | Before (`contact-severity-validation/connected-rooms-01`) | Corrected (`calf-contact/connected-rooms-01`) |
| --- | --- | --- |
| Requested / actual end time | 5 / 5 s, horizon | 5 / 5 s, horizon |
| Coverage | 67.685129% | 74.909693% |
| Leg-floor episodes | 1 | 0 |
| Other non-foot contact episodes | 0 | 0 |
| Falls / recovery entries / failed planning attempts | 0 / 0 / 0 | 0 / 0 / 0 |
| Team body XY travel | 1.543071 m | 1.546105 m |

The corrected run retains 2,500 physics intervals and 14,873 raw contact-point
samples. All nine measured geometry-pair contact episodes are expected foot
support; one foot reenters after the documented clearance interval. Both the
detailed collector and the legacy sensor-frame counter report zero non-foot
contacts. The original calf strike has therefore been removed in both the
fixed-command reproduction and this fresh closed-loop case.

The [verified top-view video](../../outputs/exploration-planning/calf-contact/connected-rooms-01/top-view.mp4)
shows the new trajectory and its recorded coverage. The
[verification report](../../outputs/exploration-planning/calf-contact/connected-rooms-01/top-view.json)
checks all 501 replayed body samples with **zero position error**. The video has
351 frames and lasts 14.04 s, including half-speed playback and hold frames.
The [complete diagnostic JSON](../../outputs/exploration-planning/calf-contact/connected-rooms-01/diagnosis.json)
retains the new commands, trajectories, coverage, contact records, and planning
diagnostics. The [earlier video](../../outputs/exploration-planning/contact-severity-validation/connected-rooms-01/top-view.mp4)
and all unsuccessful development artifacts are retained.

Coverage is 7.224564 percentage points higher in this one seeded case, with
essentially unchanged travel. This is an observed outcome of the changed
closed-loop motion, not evidence of an allocator improvement or a general
coverage gain. Other seeds, layouts, and longer horizons remain unvalidated
for this correction.

## Scope

This correction does not check terrain, current body attitude, or full-leg
geometry online. Initial motion and explicit idle still use immediate targets.
Yaw limiting adds response delay and changes closed-loop trajectories. Coverage
and obstacle-clearance results must therefore come from new exploration runs.
The development defaults and these fixtures do not establish general collision
safety, long-horizon exploration, or robustness to arbitrary command sequences.
