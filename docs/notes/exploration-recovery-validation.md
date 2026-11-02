# Recovery validation

## Scope

Development checks for the recovery change in `8de4f22`. Two Go2 robots use the existing ICP/Voronoi baseline, seed 101, a 5-second horizon, and 0.01-second sensor intervals. Runs use Windows, MuJoCo 3.6, and `OMP_NUM_THREADS=1`.

This checks the [mobility recovery correction](../exploration-navigation.md#mobility-recovery), not an allocation improvement. The 726-test regression passes with 7 skips; the known Windows IPC test module is excluded. The real 0.35-second observer-invariance test passes without recovery. Long-horizon repeatability is still untested.

## Five-second development runs

All three runs reach the horizon with zero recovery entries, falls, failed A* attempts, or robot-robot contacts.

| Layout | Coverage | Team travel | Robot-obstacle contacts | Wall time |
| --- | --- | --- | --- | --- |
| Branching corridor | 61.4% | 2.89 m | 11 | 458 s |
| Cluttered room | 53.0% | 3.61 m | 2 | 628 s |
| Connected rooms | 77.3% | 3.65 m | 4 | 567 s |

Contact counts are debounced episodes, not contact frames. The planning-failure counter counts failed A* calls; a scan with no feasible candidates can fail without incrementing it. Coverage remains the independent visible-floor metric. Corridor robot A contributed zero measured floor cells despite moving, so team coverage alone obscures an important sensing limitation. These single-seed checks provide no method comparison or uncertainty estimate.

## Navigation issues exposed

The corridor reaches its horizon with no recovery entries or falls, but records 11 robot-obstacle contact episodes. This metric excludes expected foot-floor contact; it includes other robot-floor contacts. A completed episode is not collision-free exploration.

The saved corridor trace also shows a stale-path execution bug:

| Robot | Goal cleared, command stops | Forward command resumes without a goal |
| --- | --- | --- |
| A | 2.93 s | 2.95 s, 0.796 m/s |
| B | 3.69 s | 3.71 s, 0.800 m/s |

Code inspection explains the behavior: `_evaluate_frontiers` clears `_goal_id` on an unsuccessful scan but retains `_current_waypoint_runner`. `step_once` resets its local termination flag on the next frame. The coordinator stops the robot only on frames whose metrics report termination. A later frame can therefore execute the retained route. This is independent of the recovery timing correction; the trace does not prove it caused the recorded contacts.

Next, invalidate routes when planning loses a feasible goal and keep that robot idle until a successful rescan. Add a regression with one exhausted robot and one still exploring. Then inspect contact events against estimated poses, body trajectories, and planning clearance before expanding the evaluation matrix. Increasing the recovery timeout further would not address this failure.

## Runtime diagnostic

A separate 0.5-second corridor run under `cProfile` took 35.5 wall seconds. Pixel readback (`mjr_readPixels`) accounted for 12.4 seconds, ICP registration for 8.4 seconds, and scene rendering for 3.2 seconds. Floor classification took about 1.0 second. The profile is saved as `outputs/exploration-planning/recovery-validation/profile.pstats`.

These measurements include profiling overhead and concurrent development work. They identify costs to investigate, not isolated throughput estimates. Profile offscreen capture and ICP scheduling before budgeting the proposed 300-second campaign; any sensor or scheduling change must apply to every comparison method and pass the observation/command invariance checks again.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/run_exploration_smoke.py --scenario branching_corridor --seed 101 --horizon 5 --output outputs/exploration-planning/recovery-validation/branching_corridor.json
```

Repeat for `cluttered_room` and `connected_rooms`. The smoke export records command/body histories and reliability events. The original development traces under `outputs/exploration-planning/recovery-validation/*-seed-101-5s.json` also contain per-frame estimated positions and goal/recovery states captured by a local diagnostic driver. Generated traces are ignored by Git. They are development artifacts, not a frozen study manifest.
