# Depth odometry correction

Revision `c493d6c` substantially reduces the reproduced drift. It does not make depth-only localization reliable in every direction. Final planar error remains 0.24 to 0.48 m on the three tested camera trajectories, so navigation validation is still required before allocator comparisons.

Follow-up: the [mounted-camera correction](exploration-body-origin-validation.md) identifies a further cause of that residual error. Defining unsupported motion at the calibrated body origin reduces robot A's final errors to 0.004 to 0.036 m on the same trajectories. The measurements below describe the earlier estimator.

## Diagnosis

Repeating each robot's initial image 30 times produces negligible drift. Controlled translation and rotation do not: the former point-to-point ICP accumulates 0.21 to 0.62 m position error in the analytical room tests. Matching nearby sampled points on broad surfaces can explain camera rotation as translation.

Point-to-plane alignment improves orientation, but a direct substitution still permits large position errors. Fixed-radius normal searches can lack enough neighbours at longer distances, edges can produce misleading surface normals, and nearly unconstrained motion directions can amplify small errors. A trial that rotated around the cloud centroid also introduced translation in wall-only views.

## Changes

- Estimate normals from 20 nearest neighbours. Registration uses locally planar samples, rejecting line-like neighbourhoods and samples whose smallest covariance eigenvalue exceeds 1% of the next. Mapping retains the prepared observation cloud, including non-planar obstacles.
- Solve point-to-plane increments about the camera origin. Truncated least squares suppresses singular directions below 1% of the largest singular value. A wall-only rotation regression checks that this does not invent sideways motion.
- Retain the accepted registration cloud in camera coordinates. Both sides use consistent preparation and the pipeline's projection configuration. The former target reconstruction used the mutable dashboard configuration even when the pipeline was explicitly pinned.
- Report measured fitness, residual, observable rank, and acceptance instead of constant fitness 1. Rejected or missing observations report lost tracking, preserve the last accepted reference and pose, and insert no unlocalized points. Live simulator poses are never used as a fallback.

Updates require fitness above 0.3, at least 100 correspondences, and rank at least three. An accepted rank-three to rank-five update is only partially constrained; `OK` does not certify six-axis pose accuracy. These conditioning rules are recorded by `odometry_rule: planar_surface_svd_v1`.

## Matched camera replay

Seed 101, robot A, original recorded trajectories. The diagnostic renders the static fixture from each saved camera pose, excluding robot geometry. Both estimators receive identical depth frames and the same initial pose. Later pose inputs are deliberately incorrect to expose accidental simulator assistance. The baseline is revision `2614319`.

| Layout | Last input time | Final planar error, old / new | Final orientation error, old / new |
| --- | --- | --- | --- |
| Branching corridor | 4.20 s | 0.260 / 0.241 m | 23.57 / 0.55 degrees |
| Cluttered room | 4.33 s | 2.159 / 0.477 m | 62.25 / 0.27 degrees |
| Connected rooms | 4.99 s | 2.833 / 0.348 m | 81.88 / 0.23 degrees |

Maximum planar errors fall from 0.789 to 0.249 m, 2.159 to 0.481 m, and 2.833 to 0.349 m respectively. Orientation here is the full rotation difference, not the yaw-only measure in the earlier navigation report.

No frames are rejected in these replays. Partially constrained updates occur in 239/420, 168/433, and 156/499 post-initialization frames respectively. The remaining drift is consistent with incomplete geometric constraints, but these counts do not attribute every residual error to that cause. A featureless plane without visible boundaries cannot reveal translation parallel to itself. Freezing an unsupported increment avoids numerical excursions; it cannot recover motion the image does not observe.

## Validation and limits

Thirteen new regressions cover analytical room motion, wall rotation, unobservable translation, surface preparation, missing correspondences, pinned projection axes, and rejection/recovery. The three motion cases fail before the correction and pass with maximum position error below 2 cm and rotation error below one degree. Tests deliberately poison all later ground-truth inputs.

The shared SLAM, metrics, exploration, coordination, bridge, locomotion, and multi-robot integration check passes 1,013 tests with 7 skips. The known Windows ZeroMQ IPC module is excluded. A subsequent three-case check verifies JSON serialization of tracking metrics.

This is one robot and one development seed per layout, using saved motion. It is not a new closed-loop exploration run, an independent holdout study, or validation of collision clearance. The next gate is handling partially observed motion with additional odometry constraints or an explicitly declared pose-assisted baseline, then rerunning navigation and inspecting the column collision. Future coverage results must identify this changed baseline.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run pytest tests/slam/test_icp_motion.py tests/slam/test_surface_odometry.py -q
uv run python scripts/diagnose_exploration_odometry.py --input outputs/exploration-planning/longer-validation/connected_rooms/diagnosis.json --robot robot_a --output outputs/exploration-planning/odometry-diagnosis/current-connected-a.json
```

The input comes from [the navigation diagnostic](exploration-longer-validation.md). The replay exports per-frame errors, registration quality, and input/source hashes. Local before/after files are `outputs/exploration-planning/odometry-diagnosis/baseline-<scenario>-a.json` and `final-<scenario>-a.json`; they are ignored by Git. Earlier candidate results are retained in that directory and are not final results.
