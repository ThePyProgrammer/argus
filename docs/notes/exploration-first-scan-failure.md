# First-scan planning failure

Diagnosed November 1, 2026 on `branching_corridor`, seed 101, with the development baseline through commit `6723ced`. The episode stops at 0.29 simulated seconds with `all_unreachable`.

## Findings

The goal selector uses a frontier cluster's geometric centroid as its navigation target. A connected frontier can surround occupied space, so its centroid need not be a frontier cell or a navigable point. Both selected centroids are occupied in the captured planning grids.

| At the first planning scan | Robot A | Robot B |
| --- | --- | --- |
| Frontier clusters | 1 | 1 |
| Cells in selected cluster | 94 | 312 |
| Reachable cells in that cluster under current A* rules | 94 | 312 |
| Selected centroid is a frontier cell | No | No |
| Selected centroid occupancy | Occupied | Occupied |
| Passable neighbors at start | 8 | 8 |
| Path to an actual frontier cell | Found, 6 waypoints | Found, 6 waypoints |

The alternative paths use the same saved grid, start, obstacle inflation, and A* implementation. Only the target changes. This establishes a target-selection failure; it does not establish physical navigation success.

The failure chain is:

1. [FrontierDetector](../../src/exploration/frontier_detector.py) averages cluster coordinates to obtain a geometric centroid.
2. [GoalSelector](../../src/exploration/goal_selector.py) returns that centroid directly.
3. [PathPlanner](../../src/exploration/path_planner.py) rejects the occupied goal before searching.
4. [ExplorationLoop](../../src/exploration/exploration_loop.py) discards the entire cluster after that one rejection.
5. [Coordinator](../../src/coordination/coordinator.py) reports `all_unreachable` when both loops terminate.

Thus, the reported outcome means both representative targets failed, not that the actual frontier cells were unreachable. Neither start is trapped by inflation in this case.

## Floor contamination

The [occupancy projection](../../src/exploration/occupancy_grid.py) removes one dominant height bin only when it contains more than 30% of voxels. Neither map meets that condition:

| Height-filter input | Robot A | Robot B |
| --- | --- | --- |
| Voxels | 288 | 10,846 |
| Largest height-bin count | 69 | 1,856 |
| Largest bin fraction | 23.96% | 17.11% |
| Heights contributing to selected goal column | -0.048, +0.052 m | -0.106, -0.006 m |

These near-floor and below-floor voxels remain eligible to mark cells occupied. Robot B's target `(1.977, 0.100)` passes the independent reference-clearance check, despite being occupied in its planning grid. Robot A's target fails reference clearance and must not be assumed physically safe after filtering.

The captured maps confirm that the floor-filter gate stays off. This diagnosis does not isolate all causes of the reconstructed height spread, such as pose error or voxelization. It also does not validate the inferred free space around mapped obstacles.

## Reproduce

```bash
uv run python scripts/diagnose_exploration_planning.py --scenario branching_corridor --seed 101
uv run pytest tests/exploration/test_planning_diagnosis.py
```

For the validated Windows configuration, set `$env:OMP_NUM_THREADS = '1'` before launching Python. The script records inputs and returns each original planner result unchanged. Alternative targets are tested only after the episode closes.

Generated files go under `outputs/exploration-planning/branching_corridor-seed-101/`: an episode summary and per-attempt JSON, NPZ arrays, and SVG overlays. The arrays include the planning grid, costmap, frontier masks, source voxels, original target, and alternative path. They are ignored by Git. A small independent ring-frontier test reproduces the invalid-centroid assumption without simulation.

## Next correction

Select a validated cell within each frontier cluster, accounting for planner clearance and reachability. Retain the cluster while alternative cells remain untested. Preserve the geometric centroid for descriptive statistics and any cluster scoring that needs it.

Then replace the single-bin floor heuristic with a validated floor/obstacle separation rule based on observations. Test low obstacles and pose error as well as flat floors. Keep evaluation reference geometry out of navigation. Both corrections must apply to every allocator baseline before the comparative study.
