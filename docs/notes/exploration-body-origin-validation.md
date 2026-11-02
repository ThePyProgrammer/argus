# Mounted-camera motion correction

Revision `4ebeb53` corrects false body translation during turns. On the same robot-A camera trajectories, final planar error falls from 0.24 to 0.48 m to 0.004 to 0.036 m. This addresses the residual error investigated after the [surface odometry correction](exploration-odometry-validation.md).

## Cause and correction

The Go2 camera sits 0.4 m ahead of the body and 0.05 m above it. Turning the body therefore moves the camera along an arc, even when the body stays in place. In a poorly constrained view, the previous solver kept unsupported camera translation at zero. Converting that camera estimate back to a body pose could then make the body appear to slide.

The solver now defines unsupported increments at the calibrated body origin. It accounts for the camera's offset when applying each rotation. This uses the fixed `body_from_camera` calibration, not a live simulator body pose. Fully observed translation remains estimable. Producers without mounting calibration retain the coincident camera/body convention.

The replay diagnostic now supplies and records the same fixed calibration as the bridge. Provenance identifies the correction as `body_origin_surface_svd_v2`.

## Matched replay results

Seed 101, saved trajectories, identical static scenes and initial pose seeds. Subsequent pose inputs remain deliberately incorrect to detect accidental simulator assistance.

| Layout, robot A | Previous final planar error | Corrected final planar error | Corrected maximum planar error |
| --- | --- | --- | --- |
| Branching corridor | 24.09 cm | 1.19 cm | 5.91 cm |
| Cluttered room | 47.74 cm | 0.43 cm | 5.34 cm |
| Connected rooms | 34.83 cm | 3.58 cm | 3.67 cm |

Final full-orientation errors are 0.54, 0.74, and 0.24 degrees respectively. All frames are accepted in these three replays.

| Additional robot-B replay | Final planar error | Maximum planar error | Rejected frames |
| --- | --- | --- | --- |
| Branching corridor | 7.99 cm | 8.05 cm | 0 |
| Cluttered room | 12.49 cm | 12.57 cm | 84 |
| Connected rooms | 1.51 cm | 1.51 cm | 0 |

The cluttered-room B trajectory retains a separate close-obstacle tracking failure. At its first rejection, 3.09 s, the camera is about 0.14 m from the column face. Fitness is 1 and rank is three, but the alignment does not meet the 100-correspondence acceptance requirement. The prior estimator also rejects 84 frames on this trajectory and finishes with 24.10 cm planar error. The correction therefore improves position without removing this failure. Final orientation error is about 18.8 degrees after tracking loss in both versions.

Follow-up: [bounded registration refinement](exploration-near-obstacle-validation.md) removes the sampling failure at 3.09 s without relaxing acceptance thresholds. The first rejection moves to 3.77 s, about 1.4 cm from the column, where the geometric rank is insufficient. The table above describes the earlier fixed-resolution estimator.

Saved-trajectory replay continues after rejection to expose failures. The real evaluator terminates on lost tracking; these replays do not imply that navigation deliberately continues with a lost pose.

## Fresh exploration check

A new two-robot `connected_rooms` episode, seed 101, reaches the five-second horizon with no contacts, falls, recovery entries, or tracking failures. This runs the actual controller, rendering, mapping, planning, and coverage collector with the corrected estimator.

| Robot | Final planar error | Maximum planar error | Final orientation error | Body travel |
| --- | --- | --- | --- | --- |
| A | 4.41 cm | 4.53 cm | 0.24 degrees | 1.19 m |
| B | 1.30 cm | 1.34 cm | 0.22 degrees | 1.13 m |

Pose comparisons use input times through 4.99 s. Coverage reaches 88.8%, with normalized AUC 0.7118; the configured 90% threshold is not reached. The episode and aligned pose histories are saved under `outputs/exploration-planning/body-origin-validation/connected_rooms/`. Concurrent processes make its wall time unsuitable for throughput comparisons.

This supports the correction on one fresh development run. Fresh corridor/cluttered-room checks, repeatability, near-obstacle tracking, and footprint clearance remain gates before the allocator study.

## Regression coverage

Four independent wall-rendering cases reproduce 8 to 12 cm of false body displacement before the correction. They cover both turn directions and two camera offsets, including a rotated camera-to-body frame. They now keep body position error below 1 cm and orientation error below one degree, with all later ground-truth inputs poisoned.

Four additional mounted-camera room cases check stationary, translating, rotating, and combined motion. Existing unmounted-camera cases remain unchanged. The shared SLAM, metrics, exploration, coordination, bridge, locomotion, and multi-robot integration suite passes 1,021 tests with 7 skips. The known Windows ZeroMQ IPC module is excluded.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run pytest tests/slam/test_icp_motion.py tests/slam/test_surface_odometry.py -q
uv run python scripts/diagnose_exploration_odometry.py --input outputs/exploration-planning/longer-validation/connected_rooms/diagnosis.json --robot robot_a --output outputs/exploration-planning/body-origin-validation/replays/current-connected-a.json
uv run python scripts/diagnose_exploration_contacts.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/body-origin-validation/connected-rooms-rerun
```

Local replay artifacts are under `outputs/exploration-planning/body-origin-validation/replays/`. They include mounting calibration, source/input hashes, pose errors, and registration quality. These generated files are ignored by Git. This is one development seed per layout, not a general localization or obstacle-clearance guarantee. Motion that is truly unobservable remains a limitation.
