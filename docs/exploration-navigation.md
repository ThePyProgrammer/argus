# Exploration navigation baseline

The shared navigation path now selects reachable frontier cells and separates floor observations before building the obstacle map. These corrections address the [first-scan failure](notes/exploration-first-scan-failure.md) and apply equally to interactive exploration and evaluation.

## Frontier targets

Cluster centroids remain useful for ranking regions. Navigation targets are actual free cells belonging to a cluster and reachable under the planner's existing inflation and eight-neighbor rules.

Clusters retain nearest, largest, or supplied bias scoring. Within a cluster, cells are ordered by distance from the current estimated position, then row and column. Other cells are tried before discarding a region. Occupied, inflated, and disconnected cells are excluded. Clearance caches are invalidated when grid contents change.

A scan clears the old route and goal before planning. A successful scan installs a new path and executes it on that frame, including the first scan at step 30. An unsuccessful scan leaves a persistent idle state, including frames without rescans. Initial forward movement is allowed only before the first scan; it cannot resume as a fallback after losing a route.

No frontiers, no feasible candidates, failed A* attempts, and scan exceptions all prevent stale-route execution. An idle robot keeps sensing and can resume after a successful rescan or an explicit waypoint command. Its teammate can continue exploring. Recovery cannot turn idle planning failure into movement. Episode provenance records `route_lifecycle: invalidate_on_rescan_v1`.

## Camera and body frames

Navigation converts the SLAM camera estimate to a body estimate using fixed mounting calibration. Planning starts, waypoint steering, progress detection, free-space trajectories, and Voronoi allocation use that body estimate. Floor classification and obstacle insertion keep the camera origin. The [contact diagnosis](notes/exploration-contact-diagnosis.md) explains the former 90-degree steering mismatch, the gait-clearance correction, and remaining limits.

The ICP backend now uses [constrained surface odometry](notes/exploration-odometry-validation.md). It suppresses poorly observed motion directions and reports actual registration quality. Rejected observations hold the last accepted pose/reference and do not enter the map. The initial pose remains simulator-assisted; subsequent updates use depth only. Partially constrained updates can still accumulate position error, so acceptance is not a guarantee of accurate localization.

## Floor observations

[FloorFilter](../src/exploration/floor_filter.py) classifies each SLAM frame before its points enter the accumulated obstacle cloud. This avoids treating floor points spread across height bins by pose error and voxelization as obstacles.

The filter estimates local surface normals, considers approximately horizontal planes at the calibrated camera-to-floor distance, and requires at least 40 supporting points with extent in two directions. It prefers the lowest supported plane within the calibration band. Point ordering and candidate ordering are deterministic; it uses no global random state or reference geometry.

| Default | Value |
| --- | --- |
| Upright Go2 camera-to-floor distance | 0.32 m |
| Height tolerance | 0.04 m |
| Plane inlier distance | 0.015 m |
| Maximum tilt relative to estimated world up | 25 degrees |
| Minimum secondary-axis RMS spread | 0.08 m |

Only plane inliers are removed. When no supported plane matches the calibration, points remain obstacle observations. `ExplorationConfig.ground_filter=False` bypasses separation. The camera-height calibration must be adapted for another platform or stance; this is a flat-floor Go2 baseline, not a general terrain classifier. Very shallow surfaces within the inlier tolerance are unresolved, and a broad raised surface within the calibration band can be ambiguous when the actual floor is hidden.

Observed floor cells supply free-space evidence to the planning grid. Occupied columns always take precedence, including low obstacles above observed floor. The grid uses one world-to-cell convention for insertion and querying. Coordination and navigation consume the same floor/obstacle projection. Existing inferred-free-space dilation remains a baseline limitation.

Floor observations never define measured coverage. The independent depth-based collector and fixed reference area retain their existing definitions.

## Validation and remaining work

Tests cover occupied ring centroids, alternative cells within one cluster, inflated and disconnected targets, stable ordering, and retained replanned paths. Floor tests cover rigid pose shifts/tilts, wall-dominated scans, missing floor, raised surfaces, low obstacles, and a rendered 6 cm box.

The relevant metrics, exploration, coordination, bridge, SLAM, locomotion, and dashboard integration suites pass 975 tests with 7 skips. The existing subprocess SLAM test module is excluded because this Windows ZeroMQ build does not support IPC. Real episode tests preserve command and body-trajectory equality with measurement collection enabled and disabled.

The original one-second checks resolved the first-scan failure but triggered recovery on every robot. The simulated-time correction below removes that false trigger. The [longer-run diagnostic](notes/exploration-recovery-validation.md) records subsequent contacts and the stale-path failure corrected above. Sustained exploration, controller safety, and long-horizon repeatability remain gates before the comparison campaign.

The [five-second follow-up](notes/exploration-longer-validation.md) tests the camera/body and swing-lift corrections across all three layouts. Two runs stop early; a calf-floor strike returns after restarting, and another robot hits a column. All layouts show more than 0.5 m peak planar pose error for both robots. The subsequent [idle/restart correction](notes/exploration-restart-validation.md) removes the reproduced floor strike in physics replay: idle commands now return all legs to standing and reset the gait phase. Localization, obstacle clearance, and a fresh full closed-loop validation remain unresolved.

Episode provenance records the exploration configuration, `reachable_frontier_member_v1`, and `per_observation_plane_v1`. Selection timing now includes reachable-cell filtering and candidate ranking, and excludes A* execution, mapping, and rendering.

## Mobility recovery

The former detector required 5 cm of movement on every frame. At the evaluation sensor rate of 100 Hz, that implies 5 m/s, far above the configured walking speed. It therefore triggered after 30 frames even while the robots were moving.

Recovery now requires two simulated seconds without 5 cm of net planar displacement while translation is commanded. Pure rotation commands instead require 0.1 radians of yaw progress. Idle commands reset the window. Vertical gait motion and small back-and-forth movement do not count as progress. Turning while walking still requires translation, so spinning against an obstacle cannot continually reset the timeout.

Both interactive exploration and evaluation use increasing sensor timestamps. Recovery reverses for 0.25 simulated seconds, then commands a 135-degree turn at up to 1.5 rad/s. The final command is bounded by the remaining duration or angle. Recovery clears the old route, suspends progress detection, and forces a rescan when complete. A new progress window prevents immediate retriggering.

Configuration uses `stuck_timeout_s`, `stuck_distance_m`, `stuck_angle_rad`, and `recovery_reverse_duration_s`. The old `stuck_threshold_steps` field is removed. Episode provenance identifies this behavior as `commanded_progress_sim_time_v1`.

These checks use estimated motion, not physical contact or goal progress. Pose drift can hide a blockage; movement without useful exploration can satisfy the mobility threshold. The two-second window is a development default, not a tuned safety guarantee.
