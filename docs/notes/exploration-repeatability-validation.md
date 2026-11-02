# Longer exploration and trace repeatability

Development validation increases the requested horizon from five to ten simulated seconds for the three seed-101 layouts. A second corridor process disables measurement collection to test whether observation changes commands or body motion.

## Conditions

Runtime source is unchanged from `fd3a73e`, which includes the close-range registration correction. Commit `c2bfe9a` adds only a trace comparator, tests, and documentation. The four run manifests contain identical hashes for every Python file under `src/`, identical dependency versions, and `OMP_NUM_THREADS=1`.

Environment: Windows, Python 3.12.16, MuJoCo 3.6.0, Open3D 0.19.0, NumPy 2.4.3, and SciPy 1.17.1. Cross-platform exact equality is not claimed.

Each run uses two Go2 robots, the existing `legacy_voronoi` policy, ICP mapping, a 0.01 s sensor interval, and the same seed-101 spawn sample for its layout. No control parameter changes were made during validation. Runs share the machine, so wall times are not throughput benchmarks.

Artifacts are under `outputs/exploration-planning/repeatability-validation/`. Each case has a local `run.json`; collected cases export `diagnosis.json`, and the collector-off case exports `episode.json`. These development artifacts are ignored by Git. They do not implement the planned batch runner or its resume contract.

## Results

All three measured runs end with `all_unreachable` before the ten-second horizon. Each has zero recorded contacts, falls, recovery entries, and tracking failures. All remain valid evaluation outcomes. The AUC holds final coverage through ten seconds under the existing absorbing-termination rule; no further sensor observations are counted after termination.

| Layout | Active duration | Final coverage | Ten-second AUC | Time to 90% |
| --- | --- | --- | --- | --- |
| Branching corridor | 8.32 s | 96.0% | 0.8171 | 5.81 s |
| Connected rooms | 6.80 s | 96.3% | 0.8308 | 5.41 s |
| Cluttered room | 7.37 s | 86.9% | 0.6625 | Not reached |

| Layout | Maximum planar error A / B | Final planar error A / B |
| --- | --- | --- |
| Branching corridor | 5.42 / 10.51 cm | 5.42 / 10.07 cm |
| Connected rooms | 4.53 / 1.39 cm | 3.85 / 1.33 cm |
| Cluttered room | 6.54 / 8.75 cm | 5.37 / 8.72 cm |

Pose comparisons use matching SLAM input times through each terminal decision. Contact measurements retain their sensor-cadence limitation. These runs do not demonstrate uninterrupted ten-second navigation or complete coverage. The cluttered-room case exhausts reachable frontiers below the coverage target and remains an unresolved navigation gate.

Each layout exactly reproduces its earlier five-second command, body-position, and coverage histories: 500 command samples and 501 position/coverage samples. The earlier connected-room reference predates registration refinement, so that prefix match establishes unchanged behavior on this trajectory rather than a same-revision repeat.

The full corridor comparison passes exact numeric equality with collection enabled and disabled: 833 command records, 833 body-position samples, identical provenance and runtime events, and the same `all_unreachable` outcome at 8.32 s. The command history includes the terminal decision, which does not advance physics. The report is saved as `comparison.json` in the artifact directory.

All four processes completed with runtime source hashes unchanged from their start manifests. This establishes collector neutrality for the complete corridor trajectory through termination. Full measured repeats of the other two layouts and successful ten-second navigation remain unverified.

## Runtime bottleneck

A 15-second, 20 Hz sample of the collected corridor process captured 299 stacks without errors. Of these, 269 (90.0%) were inside `OctoMapBuilder.get_occupied_voxels`. This function rebuilds an Open3D voxel grid from all accumulated scan points on every call. Planning, voxel-count checks, reporting, and repartitioning call it repeatedly.

The raw sample is saved as `corridor-profile.txt` in the artifact directory. This is a local bottleneck diagnosis, not a campaign throughput estimate. Sampling read the running process without changing its control code. A fresh process with the same environment reported one thread in both NumPy and SciPy BLAS libraries.

Cache the occupied-voxel result until the next insertion or reset, verify identical outputs and traces, then measure isolated runtime before scaling the study. Bounding accumulated map storage is a separate change that needs its own behavior checks.

## Comparison contract

The [trace comparator](../../scripts/compare_exploration_traces.py) checks exact numeric equality of commands, body positions, runtime events, outcome, sensor cadence, settling duration, and provenance. It excludes wall time, memory, and measurement outputs. A matching algorithm failure is still a failure; equality describes repeatability only.

Ten focused tests cover tiny numerical changes, differing seeds, missing history tails, malformed exports, and matching algorithm failures. Full runtime regression results remain those of the [preceding correction](exploration-near-obstacle-validation.md), since runtime code is unchanged.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/diagnose_exploration_contacts.py --scenario branching_corridor --seed 101 --horizon 10 --output outputs/exploration-planning/repeatability-rerun/corridor-collected
uv run python scripts/run_exploration_smoke.py --scenario branching_corridor --seed 101 --horizon 10 --no-collect --output outputs/exploration-planning/repeatability-rerun/corridor-uncollected/episode.json
uv run python scripts/compare_exploration_traces.py outputs/exploration-planning/repeatability-rerun/corridor-collected/diagnosis.json outputs/exploration-planning/repeatability-rerun/corridor-uncollected/episode.json --output outputs/exploration-planning/repeatability-rerun/comparison.json
```

Use the same runtime revision and environment for both runs. Repeat the first command with `connected_rooms` and `cluttered_room`, using separate output directories, for the other layout checks. The local validation wrapper additionally records source hashes and progress; the commands above use the same episode and diagnostic functions.

One seed per layout cannot establish general navigation reliability. Next remove repeated voxel-query work while preserving traces, then diagnose the cluttered-room frontier exhaustion. Additional development seeds, longer horizons, and footprint-clearance validation remain before allocation comparisons. The planner's 15 cm hard obstacle margin remains a known limitation.
