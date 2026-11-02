# Exploration episodes

`ExplorationEpisode` runs one headless development episode through the same coordinator ticks as the dashboard. It currently supports the existing ICP/Voronoi control path on the three Go2 fixtures. The comparison methods, batch CLI, manifests, and resume support remain future work.

## Run a smoke case

```bash
uv run python scripts/run_exploration_smoke.py --scenario branching_corridor --seed 101 --horizon 0.35
```

The script prints a JSON result and closes all simulation resources. It opens no viewer and loads no optional detectors. Horizons must be positive multiples of the sensor interval, currently 0.01 simulated seconds. For repeatability checks on PowerShell, set `$env:OMP_NUM_THREADS = '1'` before launching Python. The validated environment uses MuJoCo 3.6 and one OpenMP thread; cross-platform bitwise equivalence is not claimed.

Save a longer development trace with:

```bash
uv run python scripts/run_exploration_smoke.py --scenario branching_corridor --seed 101 --horizon 5 --output outputs/exploration-planning/recovery-validation/branching_corridor.json
```

The saved JSON contains the result, commands, body trajectories, coverage history, episode events, and reliability events such as recovery entries and contacts. Repeat with `--no-collect` and a different output path to check that measurement attachment preserves `commands` and `trajectory`. These are development exports; batch manifests and resume are still unimplemented.

Compare two complete exports with:

```bash
uv run python scripts/compare_exploration_traces.py collected.json uncollected.json --output comparison.json
```

The comparator accepts smoke exports and contact diagnoses. It checks provenance, outcome, cadence, commands, body positions, and runtime events using exact numeric equality. It reports the first difference in each field and exits with status 1 on a mismatch or 2 for an unusable export. Timing, memory, coverage, and reliability measurements are excluded. Matching algorithm failures are reported as repeatable failures, not successful navigation. Keep the source revision, environment, and requested horizon fixed separately; this check does not establish those conditions from command equality.

The former `all_unreachable` failure at 0.29 simulated seconds is corrected. The [navigation baseline](exploration-navigation.md) now selects reachable frontier cells and separates observed floor before map accumulation. Recovery now measures commanded progress over simulated time. The [longer-run diagnostic](notes/exploration-recovery-validation.md) records development results, remaining contacts, and the stale-path failure now corrected by persistent route invalidation. These checks do not establish long-run exploration performance or compare allocation methods.

## Lifecycle

```python
from src.exploration.evaluation.episode import ExplorationEpisode

with ExplorationEpisode.from_scenario("connected_rooms", 101, horizon_s=1.0) as episode:
    while episode.inspect()["state"] == "running":
        episode.advance()
    result = episode.inspect()["result"]
    trace = episode.inspect(include_history=True)
```

`start` settles physics, creates collectors, and captures the initial measured state before autonomous commands. `advance` executes one coordinator decision and sensor interval. `inspect` returns detached data; full command, trajectory, event, and coverage histories are copied only when requested. `close` is idempotent. Episodes are single-use and finish automatically at the horizon or an absorbing termination.

The bridge clock is `completed_sensor_intervals * frame_dt`, with zero immediately after settling. The raw MuJoCo settling duration is recorded separately. The default 200 settling steps take 0.4 simulated seconds. Autonomous bootstrap movement is included in measurements. A forward pass after integration aligns camera transforms and contact samples with the recorded physics state.

The dashboard's `Coordinator.run` now delegates to `start`, `advance`, and `close`. Interactive pause, restart, partition, merge, and visualization behavior still uses that path. Evaluation enables absorbing termination explicitly; the dashboard retains its ongoing loop behavior.

## Reproducibility and information boundaries

- Spawn locations and headings come from the resolved fixture sample. The bridge applies those headings before settling.
- Recovery uses a separate generator per robot, seeded by `[episode_seed, 2, robot_index]`. Progress timeouts, reversing, and turning use captured simulation time in both evaluation and interactive exploration. See the [mobility recovery contract](exploration-navigation.md#mobility-recovery).
- Evaluation fixes the depth-to-cloud convention to MuJoCo's camera axes per backend instance. Dashboard configuration cannot change it, and evaluation does not change dashboard settings.
- Reference geometry enters only the measurement collector. Navigation receives the existing sensor frames and local maps. Map merging collects published outputs; it does not install a shared planning grid in each robot.
- The current baseline uses ground truth to initialize ICP's camera pose. Body travel is measured separately from MuJoCo body positions. Neither measurement implies localization independence.

## Outcomes and measurements

| Condition | Outcome |
| --- | --- |
| Horizon reached | Valid episode with final coverage and fixed-horizon AUC. |
| All active robots exhaust frontiers or reachable goals | Valid absorbing failure; retain observations through the horizon. |
| Caught exploration error or lost/changed SLAM backend | Explicit `algorithm_error`; stop before another physics interval. |
| Disabled robot | Stop its commands and observations permanently; its teammate continues. |
| All robots disabled | Valid `all_robots_failed` outcome. |
| Renderer, bridge, or unexpected runtime exception | Invalid infrastructure attempt; close resources and propagate the exception. |
| Early caller close or cleanup failure | Invalid attempt, with interruption or cleanup details. |

Go2 falls use the existing platform height threshold, below 0.16 m. A fall is counted but does not itself disable that controller. Recovery entries include both exploration stuck recovery and platform recovery states.

Contacts and body states are sampled at sensor cadence, currently every five physics steps. Brief contacts between samples can be missed. Planning attempts and selection latency are recorded at decision time; goal and recovery state transitions are sampled at the next sensor boundary. Selection timing includes reachable-cell filtering and candidate ranking, excluding A* execution, mapping, and rendering. Joint allocation will need its own timing boundary.

The result records total wall duration through measurement completion, measured-interval wall duration, real-time factor, sensor cadence, and the OS process RSS high-water mark. Memory scope is explicitly `process_lifetime`; it is not isolated episode memory when multiple episodes share a process. Batch process isolation belongs to the runner milestone.

The [measurement contract](exploration-measurements.md) defines visibility, AUC, overlap, event debounce, and failure scoring. `episode.coverage.write_observations(path)` exports first-observation arrays; `episode.reliability.events()` provides detailed reliability events. Persistent run directories and retry manifests are not implemented yet.

## Validation

Real offscreen tests compare commands, body trajectories, and coverage across repeated short episodes, intervening seeds, and collector attachment. A longer test passes the first frontier scan with successful goal assignments, with and without collection. Additional tests check fixture geometry after robot insertion, capture poses, heading application, owned recovery randomness, dashboard-setting isolation, disabled robots, backend loss, and cleanup after injected failures.

The [longer development checks](notes/exploration-repeatability-validation.md) reproduce the corridor's full command/body trace with collection enabled and disabled through its terminal decision at 8.32 s. All three layouts stop before the requested ten seconds because reachable frontiers are exhausted; the cluttered room remains below 90% coverage. These checks establish limited repeatability, not sustained ten-second navigation. Additional seeds, longer successful runs, the candidate methods, and the frozen study remain gates in the [execution plan](plans/exploration-evaluation.md).
