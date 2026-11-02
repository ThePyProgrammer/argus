# Observed free space and supported floor planes

The planner now keeps unobserved cells unknown instead of growing free labels around walls and floor observations. Observed floor and the existing estimated-trajectory footprint supply free-space evidence. Occupied columns retain precedence.

The correction also addresses two problems exposed by the smaller, observation-based frontiers:

- Candidates already within the waypoint arrival radius are skipped.
- Smoothed paths retain the exact selected goal. Previously, an endpoint within 20 cm of the goal could be accepted even if smoothing moved it inside the arrival radius, completing the path immediately.

Navigation correction: `e9a2209`. Episode provenance records `planning_free_space: observed_floor_and_trajectory_v1`, `navigation_target_rule: reachable_unreached_frontier_member_v2`, and `planned_goal: preserve_exact_endpoint_v1`.

## Floor classification

Saved observations exposed a separate mapping error. Ranking floor hypotheses by apparent height could select a tilted plane through a wall/floor edge. That plane rejected genuine floor samples and sometimes removed raised obstacle points.

Revision `578618c` ranks eligible planes by residual-weighted support before hypothesis deduplication and refinement. Points close to the plane contribute more than points near the inlier cutoff. Height breaks ties. The calibration band, tilt limit, minimum support, spatial extent, and distance tolerance are unchanged. The filter still uses observed points and fixed calibration, without simulator geometry or live ground-truth poses.

The diagnostic in `957f618` uses simulator poses only after classification to label saved samples. Near-floor samples lie within 2 mm of the fixture's floor plane; raised samples exceed 4 cm. These are diagnostic bands, not new controller thresholds.

| Saved cluttered-room sample | Near-floor points | Missed before / after | Raised points removed before / after |
| --- | --- | --- | --- |
| A, 0.00 s | 292 | 236 / 0 | 16 / 0 |
| A, 0.52 s | 321 | 281 / 0 | 19 / 0 |
| B, 0.02 s | 188 | 143 / 0 | 56 / 0 |
| B, 0.06 s | 220 | 164 / 0 | 56 / 0 |

The saved corridor-B sample also improves from 165 missed near-floor points to zero, with raised-point removal falling from 52 to zero. Two corridor-A samples still reject all 295/296 near-floor points. This correction does not resolve every floor-filter rejection. Surfaces within the floor calibration/tolerance bands remain ambiguous.

## Development validation

Final runs keep seed 101, two Go2 robots, the existing allocation policy, sensing, locomotion, and coverage definitions. Runtime hashes remain unchanged throughout all three runs. They run concurrently, so wall times are not throughput measurements.

| Layout | Budget | End time / outcome | Coverage | Contact episodes |
| --- | --- | --- | --- | --- |
| Branching corridor | 5 s | 5.00 s, horizon | 88.9% | 2 |
| Connected rooms | 5 s | 5.00 s, horizon | 70.8% | 0 |
| Cluttered room | 10 s | 9.07 s, tracking failure | 64.0% | 2 |

No run records a fall or recovery entry. Both five-second cases retain tracking. Maximum planar pose errors are 5.3 cm in the corridor, 1.2 cm in connected rooms, and 14.6 cm in the cluttered room. The cluttered-room failure remains a valid algorithm outcome; its final coverage is held through the ten-second AUC horizon.

The corridor contacts are robot A's rear calves touching the floor at 0.37 and 0.60 s. The cluttered-room contacts are robot B's front-left foot against a column at 3.79 s and rear-left calf against the floor at 4.51 s. The earlier contact-free checks do not establish safety for these changed maneuver sequences.

At 9.07 s, robot A's camera is about 2.16 cm from `obstacle_column_3`. Registration still has 110 correspondences and fitness 1.0, but observable rank is two. It correctly rejects the frame with `insufficient_rank`; acceptance thresholds remain unchanged. This identifies camera stand-off as a concrete remaining constraint, alongside physical footprint clearance and gait transitions. The navigation gate remains unmet.

Intermediate attempts remain in the artifact directory. Removing free-space expansion alone reached ten seconds with only 16.6% coverage and repeated immediately completed goals. Adding unweighted floor support and candidate-distance filtering, before exact endpoint preservation, ended at 4.07 s with a tracking failure near a column. These are failed development attempts, not results of the final revision.

Regression checks cover unsupported free labels, occupied-cell precedence, retained frontiers in an enclosed observed patch, already-reached candidates, exact smoothed endpoints, and three rendered column-edge observations. The original real first-scan test still requires both robots to receive goals and preserve command/body traces with collection enabled and disabled; its assertions were not weakened. Long-run collector neutrality has not been re-established for this revision.

Final regression validation: 1,054 tests pass with seven skips across SLAM, metrics, exploration, coordination, bridge, locomotion, and selected multi-robot integration. The known Windows ZeroMQ IPC module is excluded.

## Artifacts and reproduction

Artifacts are under `outputs/exploration-planning/free-space-validation/`. Final cases are `cluttered-room-final`, `corridor-final`, and `connected-rooms-final`. Each records runtime source hashes. Diagnoses contain command/body histories, contact events, pose errors, terminal planning grids, and registration quality. Floor probes also save `floor.json` and selected observation arrays. `floor-reclassification.json` records the saved-sample comparison; the final cluttered-room case includes `terminal-clearance.json`.

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/diagnose_exploration_floor.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/free-space-rerun/cluttered-room
```

The [preceding voxel-cache validation](exploration-voxel-cache-validation.md) records the offline frontier diagnosis. Generated artifacts are ignored by Git. Sustained navigation, footprint/camera clearance, additional seeds, and longer-run repeatability remain evaluation gates.
