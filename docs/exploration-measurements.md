# Exploration measurements

The evaluation collectors measure visible reachable floor, body travel, and reliability events. They consume captured data and never supply reference geometry to the planner. Existing dashboard progress fields retain their current meaning.

The collectors are wired into [headless development episodes](exploration-episodes.md). The batch `eval-exploration` command is not available yet.

## Floor visibility

[CoverageCollector](../src/metrics/exploration_coverage.py) uses the fixed [reference area](exploration-reference.md). Each reference cell contributes its floor center point.

`DepthObservation.from_frame(frame, intrinsics)` copies depth, calibration, capture time, and the camera-to-world transform into immutable storage. Moving the simulator or reusing a frame buffer cannot change an earlier observation. Legacy colorized depth is rejected.

MuJoCo cameras look along negative Z, with positive X right and positive Y up. Images use downward rows, integer pixel-center coordinates `(column, row)`, and centered principal points at `((width - 1) / 2, (height - 1) / 2)`. This convention matches Open3D depth unprojection. Depth is distance along the camera axis in meters, not Euclidean ray length. MuJoCo 3.6 already returns metric depth; the bridges preserve sub-meter readings and replace invalid, far-plane, and over-20-meter readings with zero.

`floor-depth-support-v2` uses these integer centers. Version 1 used half-integer centers with principal points larger by 0.5. Shifting both preserves the physical coverage rays and four-pixel support rule, apart from boundary rounding. SLAM previously combined integer centers with those larger principal points, creating a half-pixel bias. Episode provenance now records `camera_calibration: integer_pixel_centers_v2`. Old calibration values must be converted before using them with v2; changing only the principal point in the old collector is incorrect. New navigation traces can differ, so cross-revision coverage differences are not allocator effects.

A floor point counts only when:

1. It lies in front of the camera, within the sensing range, and inside the image.
2. All four surrounding pixel centers have valid depth.
3. Each depth agrees with the expected floor intersection along that pixel's ray.

Defaults are 0.01 to 20 meters and tolerance `0.005 m + 0.001 * expected_depth`. Comparing at each pixel center avoids errors from the floor's depth gradient in oblique views. Requiring four supporting pixels conservatively rejects silhouettes and the outer half-pixel border. Walls, overhangs, and other robots occlude floor through their rendered depth. Hidden collision geometry is never queried for visibility.

This is a finite-resolution visibility metric. Subpixel occluders and surfaces within the depth tolerance can be indistinguishable from the floor. It does not measure reconstruction completeness or prove that navigation classified a cell as free. Sensor resolution and tolerances must be frozen before the study.

## Time and failure handling

The caller supplies `start_sim_time` after settling and before autonomous motion. Frame times must use that same clock. The collector subtracts the origin, rejects backward or out-of-horizon samples, and rejects repeated frames for a robot at the same timestamp. Horizon roundoff within one nanosecond is snapped to the configured endpoint. Each batch is validated before its measurements are applied. The episode lifecycle establishes this boundary around bridge boot and exploration bootstrap.

Per-robot first-observation times define cumulative sets. Repeated stationary frames add no area. Team coverage counts their union; overlap counts cells seen by at least two robots divided by the union. For the primary two-robot study this is intersection over union. Empty observations give overlap zero and `zero_observation: true`.

Coverage is held constant between sensor captures. Its normalized AUC is computed exactly from first-observation times:

```text
team_first[cell] = min(first_seen[robot, cell])
AUC = sum(max(0, T - team_first[cell])) / (T * reference_cell_count)
```

Unseen cells have infinite first-observation time and contribute zero. A capture at `T` can improve final coverage but contributes no AUC. Threshold time is the first capture reaching the configured fraction, initially 90%; failure produces null threshold time and a capped score of `T`.

`stop_robot` freezes one robot's measurements while its teammate can continue. `finalize` accepts horizon completion or an explicit algorithm termination: no frontiers, all unreachable, all robots failed, or algorithm error. Early termination holds the last observation set through `T`. No-frontier status does not imply complete coverage. Finalization rejects subsequent measurements. Infrastructure failures belong in the future runner's invalid-attempt records.

`write_observations(path)` saves robot IDs, the reference mask, and per-robot first-observation times in NPZ without pickle. Outside-reference and unseen cells contain infinity. Final summaries include the metric version, reference hash, configuration, frame counts, and termination reason. The runner will save summaries and fixed-cadence snapshots alongside these arrays.

## Reliability

[ReliabilityCollector](../src/metrics/exploration_metrics.py) receives body states at increasing simulation times. It uses body XY displacement between samples, excluding the initial position and vertical motion. The caller must sample consistently; discrete distances can miss motion between samples.

| Measurement | Counting rule |
| --- | --- |
| Contact episodes | Actual MuJoCo contacts at distance zero or below, grouped by robot/object or unordered robot pair. Multiple contact points count once. |
| Expected ground contact | Explicit foot-floor pairs are excluded. Body-floor contact remains a measured event. Self-contact and environment-only contact are excluded. |
| Contact debounce | A new episode requires at least 0.2 simulated seconds of sampled absence. Brief gaps remain one episode. Sparse samples of sustained contact remain one episode. |
| Falls and recoveries | Count entry into each boolean state, including a failed state at the first measured sample. Sustained states count once. |
| Goal assignments | Count each changed non-null goal. A switch requires both old and new goals to be non-null; resuming from idle is an assignment. |
| Planning failures | Explicit unsuccessful attempts, deduplicated by robot and attempt ID. Repeated status polling cannot inflate counts. |
| Allocator latency | Caller-supplied measured milliseconds per invocation, summarized by mean and p95. |

`ContactClassifier` takes explicit robot geom ownership, foot geoms, and floor geoms from the compiled scene. Obstacle bodies group composite geoms; separate world geoms retain distinct identities. Proximity warnings are not contact measurements. Debouncing starts at the first sample reporting absence, so event counts depend on the declared contact sampling cadence.

The collector returns detached event records and summaries. The episode runtime supplies wall time, process memory, real-time factor, state classification, and event sampling. Development smoke results exist; no comparative benchmark has been run.

## Validation

```bash
uv run pytest tests/metrics/test_exploration_coverage.py tests/metrics/test_exploration_metrics.py tests/bridge/test_metric_depth.py
```

Tests use real offscreen MuJoCo renders for close and oblique floor views, wall occlusion, and robot occlusion. Analytical timelines verify union, overlap, AUC, threshold timing, and absorbing failures. Real MuJoCo contacts verify foot exclusions, body-floor contact, and robot-robot contact. Other tests cover immutable captures, input rejection, and event transitions. Development episode tests verify command-trace invariance with and without collection; longer successful runs remain a gate in the [execution plan](plans/exploration-evaluation.md).
