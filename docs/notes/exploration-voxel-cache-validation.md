# Occupied-voxel caching and frontier diagnosis

`OctoMapBuilder` now voxelizes accumulated scans once between insertions. Repeated planning, counting, and reporting queries reuse that result. Insertion and reset invalidate it; public array queries return copies so callers cannot change cached geometry.

Runtime correction: `023e39f`. Terminal planning diagnostics: `75039dc`.

The full accumulated cloud, voxel origin, discretization, and point ordering are preserved. This removes redundant computation without changing map semantics. Accumulated scan storage remains unbounded.

## Validation

The SLAM, exploration, coordination, and selected multi-robot integration suites pass 534 tests with four skips. The known Windows ZeroMQ IPC module is excluded. A separate focused run passes nine cache/planning-diagnostic tests, overlapping the main suite and including two newly added terminal-diagnostic tests.

Cache checks compare exact voxel arrays against full Open3D rebuilds at three resolutions while scan bounds change. They also verify one voxelization per insertion, invalidation on reset, and protection from caller mutation. Terminal diagnostics distinguish missing frontiers, filtered small clusters, blocked starts, and reachable frontier cells.

The seed-101 cluttered-room rerun exactly reproduces the pre-cache result: `all_unreachable` at 7.37 s, 86.9% coverage, and zero recorded contacts, falls, or tracking failures. All 738 command records and 738 body-position samples match. Coverage histories/results, pose-error histories, and reliability events also match exactly. Runtime source hashes remain unchanged throughout the run.

### Query workload

A paired synthetic workload inserts 60 scans of 1,000 points each, then makes three array queries and three count queries per scan. Old and new implementations alternate execution order, use the same seeded scans, and produce exactly equal voxel arrays after every insertion. Three repetitions give:

| Implementation | Total query/insert time |
| --- | --- |
| Pre-cache revision `d303ee9` | 10.20-10.77 s |
| Cached implementation | 1.73-1.82 s |

This workload is 5.89-5.98 times faster. It measures repeated voxel queries, not whole-episode throughput. No evaluation or test processes ran concurrently with this workload. The live rerun took about 482 wall seconds; its predecessor shared the machine with other episodes, so those wall times do not establish a controlled episode speedup.

## Frontier exhaustion

Both robots stop with frontier cells still present, but outside their reachable components. Their start cells are free. Cluster filtering retains those frontiers, and none of the retained frontier cells is itself excluded by hard inflation.

| Robot | Retained frontier cells | Reachable frontier cells | Cells in reachable component |
| --- | --- | --- | --- |
| A | 728 | 0 | 193 |
| B | 752 | 0 | 230 |

The projection currently grows free labels by about 0.5 m around occupied and free cells. This can label unobserved floor as free, removing the boundary that frontier detection needs.

An offline counterfactual reconstructs both terminal grids exactly from the saved obstacle voxels, observed floor, and estimated body histories. Removing only that free-space expansion restores 46 reachable frontier cells for A and 49 for B. The existing A* planner finds a path to the nearest restored candidate for each robot. No reference mask supplies planning free space or targets.

This isolates a harmful map-labeling rule on the saved states. It does not establish a successful live correction: the reachable components remain 193 and 230 cells. There is also substantial low-height occupancy inside the fixture's reference-clear area: 2,219 voxels for A and 2,964 for B lie within 15 cm of floor height. Their insertion source needs diagnosis before treating the map as reliable. All recorded camera heights stay within the floor filter's 28-36 cm calibration band, so a simple camera-height excursion does not explain these samples.

Next validate an observation-based free-space rule in live navigation and trace low-height obstacle insertion. Preserve obstacle clearance and the independent coverage definition. Further seeds and sustained longer runs still precede allocator comparisons.

## Artifacts

Development artifacts are under `outputs/exploration-planning/voxel-cache-validation/`. The collected case includes source hashes, a full episode export, and per-robot terminal grids in `*-final-planning/frontiers.npz`, with JSON summaries alongside them. `comparison.json` records trace equality, `query-benchmark.json` records paired timings, and `frontier-counterfactual.json` records the offline map comparison. `floor-diagnostic.json` records the height and occupancy checks.

Terminal snapshots contain the observed obstacle voxels, observed floor points, costmap, frontier mask, and reachable mask. They are computed after the terminal control decision. Simulator reference geometry never enters planning.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/diagnose_exploration_contacts.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/voxel-cache-rerun/cluttered-room
uv run python scripts/compare_exploration_traces.py outputs/exploration-planning/repeatability-validation/cluttered-room-collected/diagnosis.json outputs/exploration-planning/voxel-cache-rerun/cluttered-room/diagnosis.json
```

See the [preceding validation](exploration-repeatability-validation.md) for the original traces and their limits. Generated artifacts are ignored by Git.
