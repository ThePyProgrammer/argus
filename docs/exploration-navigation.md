# Exploration navigation baseline

The shared navigation path now selects reachable frontier cells and separates floor observations before building the obstacle map. These corrections address the [first-scan failure](notes/exploration-first-scan-failure.md) and apply equally to interactive exploration and evaluation.

## Frontier targets

Cluster centroids remain useful for ranking regions. Navigation targets are actual free cells belonging to a cluster and reachable under the planner's existing inflation and eight-neighbor rules.

Clusters retain nearest, largest, or supplied bias scoring. Within a cluster, cells are ordered by distance from the current estimated position, then row and column. Other cells are tried before discarding a region. Occupied, inflated, and disconnected cells are excluded. Clearance caches are invalidated when grid contents change.

A scan replaces the current path. The new path is retained and executed on that frame, including the first scan at step 30. Previously, the periodic rescan branch immediately discarded it.

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

The relevant metrics, exploration, coordination, bridge, SLAM, and dashboard integration suites pass 704 tests with 7 skips. The existing subprocess SLAM test module is excluded because this Windows ZeroMQ build does not support IPC. Real episode tests preserve command and body-trajectory equality with measurement collection enabled and disabled.

With seed 101, all three layouts reach a 1-second smoke horizon with a goal assignment for each robot, zero planning failures, and zero falls. Each robot enters recovery once under the existing stuck detector. These short runs resolve the early failure; they do not establish sustained exploration, controller safety, or long-horizon repeatability. Recovery timing and longer navigation runs remain development checks before the comparison campaign.

Episode provenance records the exploration configuration, `reachable_frontier_member_v1`, and `per_observation_plane_v1`. Selection timing now includes reachable-cell filtering and candidate ranking, and excludes A* execution, mapping, and rendering.
