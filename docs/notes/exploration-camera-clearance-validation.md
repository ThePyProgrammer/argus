# Camera clearance and route following

Follow-up: [floor history](exploration-floor-history-validation.md) and [camera calibration](exploration-camera-calibration-validation.md) address two mapping issues. Their videos and results retain the unsuccessful attempts. Floor reacquisition under pose drift and execution-time clearance remain unresolved.

The preceding cluttered-room run lost tracking at 9.07 s with robot A's camera 2.16 cm from a column. Its 110 matched points had observable rank two, below the unchanged minimum of three. The camera sits 40 cm ahead of the body, while the former hard planning radius was only 15 cm.

## Correction

The [navigation contract](../exploration-navigation.md#body-and-camera-clearance) now combines the configured Go2 footprint, fixed camera offset, camera stand-off, and raster allowance. Frontier reachability and A* share this envelope. Diagonal moves cannot cut blocked corners, and smoothing cannot cross the exclusion area. These changes are in `c7940d7`.

The first live attempt exposed a separate execution problem: the follower still walked forward during large heading corrections, including turns toward targets behind the robot. It could leave its cleared route and enter the inflated area. Both cluttered-room starts eventually had no passable neighbors, despite retaining hundreds of frontier cells.

Exploration now requests an in-place turn when heading error exceeds 0.25 radians, about 14 degrees. Forward travel resumes after alignment; small steering corrections still allow translation. Explicit exploration waypoint targets use the same rule. The generic waypoint follower keeps its existing default unless the caller enables the heading threshold. This change is in `421b3d6`; provenance records `path_following: align_heading_before_translation_v1`.

The initial envelope reserved the half-diagonal of both occupied and traversed cells. Revision `f02c130` checks continuous segment-to-obstacle distances directly and retains only the occupied-cell allowance. At 0.1 m resolution, the resulting radius is 0.674 m instead of 0.745 m. The physical footprint, camera stand-off, and 5 cm planning margin are unchanged. This matters when new observations place the current start inside inflation: the earlier envelope could also block every adjacent escape cell. The existing single-step escape exception still applies; this is not a general recovery planner.

## Planning-only attempt

All cases use seed 101, two Go2 robots, the existing allocator, and unchanged measurement and tracking thresholds.

| Layout | End time / outcome | Coverage | Contacts |
| --- | --- | --- | --- |
| Branching corridor | 5.00 s, horizon | 73.5% | 2 calf-floor episodes |
| Connected rooms | 4.51 s, all unreachable | 75.5% | 0 |
| Cluttered room | 4.90 s, all unreachable | 31.9% | 0 |

These attempts have no tracking rejection or fall, but the early stops are not successful exploration. Minimum measured camera clearance in the cluttered room is 35.8 cm for A and 17.4 cm for B. The original close-range rejection did not recur before termination; this does not establish sustained tracking. The follower still defeated route clearance.

Adding the heading gate alone retained tracking but stopped cluttered-room exploration at 2.88 s with 32.2% coverage and connected-room exploration at 2.25 s with 66.7%. The corridor reached five seconds with 61.8%. These `*-heading` attempts still used the larger raster allowance. At the cluttered-room terminal state, the smaller allowance restores 108 reachable frontier cells for A and 49 for B. This is an offline planning check, not a live success claim. A's nearest mapped obstacles were floor-height points; B's were the column. Old floor misclassification remains a mapping limitation that a clearance rule cannot repair.

## Final live checks

These cases use the complete correction through `f02c130`. Every recorded source hash matches that checked-out runtime, and sources remained unchanged during each run.

| Layout | Requested horizon | End time / outcome | Coverage | Contacts / falls / tracking rejections |
| --- | --- | --- | --- | --- |
| Branching corridor | 5 s | 5.00 s, horizon | 73.4% | 0 / 0 / 0 |
| Connected rooms | 5 s | 2.32 s, all unreachable | 77.0% | 0 / 0 / 0 |
| Cluttered room | 10 s | 5.54 s, all unreachable | 37.7% | 0 / 0 / 0 |

In the cluttered room, minimum camera clearance is 67.2 cm for A and 31.1 cm for B. Maximum planar pose errors are 0.9 cm and 9.9 cm respectively. The dangerous close approach is absent from this trace, but the run ends before the old 9.07 s failure. Successful ten-second exploration remains unvalidated. The earlier baseline reached 64.0% coverage before losing tracking, so the new result is not a coverage improvement.

Both cluttered-room robots finish with free start cells but no passable neighbors under inflation. A's nearest mapped obstacle is a floor-height voxel about 31 cm away; B's is a column voxel about 53 cm away. In connected rooms, both starts are blocked by floor-height voxels about 47 to 49 cm away. These are terminal-map diagnostics, not inputs to control.

Remaining work is to correct persistent floor misclassification and handle new obstacles or route departures before the current pose becomes trapped inside the planning envelope. Turning before translation reduces one cause of departure; it is not a continuous motion-clearance guard or a general escape policy. Even the corridor's terminal map has inflated starts, so reaching its five-second horizon does not establish longer-run navigation. Keep the study gate open and repeat live validation after those corrections.

## Regression checks

The final navigation, control, coordination, and selected multi-robot integration suites pass 489 tests with four skips. Tests cover calibrated camera envelopes, cached clearance updates, inflated goals, diagonal corner blocking, smoothing fallback, between-waypoint clearance, turn-before-translation, route replacement, and collector attachment.

## Reproduction and scope

Artifacts are under `outputs/exploration-planning/camera-clearance-validation/`. The `*-planner` and `*-heading` directories retain intermediate attempts. The complete correction is in `cluttered-room-final`, `corridor-final`, and `connected-rooms-final`. Each run records source hashes, dependency versions, commands, body trajectories, registration quality, coverage, contacts, and terminal planning state. Runs started before their final commits; the per-file source hashes identify the tested implementation. Concurrent run wall times are not throughput measurements.

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/diagnose_exploration_floor.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/camera-clearance-rerun/cluttered-room
```

Camera clearance is measured after the run by transforming fixed mounting calibration with recorded simulator body poses and checking XY distance to fixture obstacles and boundaries. This diagnostic does not feed navigation. Coverage uses the same fixed reference area as before, including any areas the conservative planner cannot reach. A configured footprint, estimated map, and heading gate do not establish collision safety or localization accuracy for arbitrary scenes, poses, or horizons.
