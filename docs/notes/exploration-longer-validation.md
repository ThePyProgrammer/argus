# Five-second navigation validation

The corrected baseline is not ready for allocator comparisons. Two layouts stop early, a calf-floor contact returns after restarting, and substantial localization error remains even in the layout that reaches the horizon.

## Conditions

Revision `0bfa63d27466e2771047496bd6b0499b4e6eea31`, seed 101, two Go2 robots, five-second requested horizon, 100 Hz control/sensing, ICP and legacy Voronoi allocation. Camera/body conversion and bounded swing lift are enabled. Controller and planner settings were held fixed across layouts.

Each layout ran in a separate process with `OMP_NUM_THREADS=1`. Processes ran concurrently; wall time and allocator latency are not performance benchmarks. These are development runs, one seed per layout, not independent final-study samples.

## Outcomes

| Layout | Stop time | Outcome | Initial / final coverage | Travel A / B | Contact episodes |
| --- | --- | --- | --- | --- | --- |
| Branching corridor | 4.20 s | `all_unreachable` | 47.8% / 68.6% | 0.928 / 0.886 m | 1 calf-floor |
| Cluttered room | 4.33 s | `all_unreachable` | 14.7% / 49.0% | 0.958 / 0.802 m | 1 robot-column |
| Connected rooms | 5.00 s | `horizon` | 58.2% / 87.5% | 1.065 / 0.996 m | 0 |

All runs are valid measurements, with no falls, recovery entries, or reported runtime errors. Valid does not mean successful navigation. None reaches 90% coverage. Normalized five-second coverage AUC is 0.6190, 0.2652, and 0.7020 respectively; early stops retain attained coverage through the remaining horizon.

Corridor robot A now observes 785 eligible cells, up from zero initially. Movement eventually reveals floor behind the initial occlusion. Its earlier zero was not a permanently broken collector.

`all_unreachable` describes the robots' current planning maps, not the fixture's true reachability. Recorded A* failures are zero: candidate filtering can reject every destination before A* is called.

## Localization

Errors compare estimated body poses with simulator body poses at the same SLAM input time. Ground truth is used only for this diagnostic comparison, apart from the baseline's existing initial pose seed. Heading errors are wrapped absolute yaw differences.

| Layout | Robot | Maximum planar error | Final planar error | Final heading error |
| --- | --- | --- | --- | --- |
| Branching corridor | A | 0.789 m | 0.260 m | 15.1 degrees |
| Branching corridor | B | 0.631 m | 0.567 m | 20.3 degrees |
| Cluttered room | A | 2.159 m | 2.159 m | 62.1 degrees |
| Cluttered room | B | 0.639 m | 0.146 m | 3.8 degrees |
| Connected rooms | A | 2.833 m | 2.833 m | 82.5 degrees |
| Connected rooms | B | 0.575 m | 0.463 m | 41.9 degrees |

Final input times are 4.20, 4.33, and 4.99 seconds respectively. Both robots exceed 0.5 m planar error at some point in every layout. Fixed mount calibration removes the former frame mismatch; it cannot correct accumulated odometry error. These traces establish drift, but do not isolate its cause or prove that it caused every route loss or contact.

## Contact isolation

In the corridor, B receives zero velocity from 3.87 through 4.04 seconds, resumes at 4.05 with about 0.373 m/s forward velocity and 1 rad/s yaw, and its left rear calf touches the floor at 4.10. Replaying the recorded commands through the same two-robot physics scene, without rendering, SLAM, planning, or collectors, reproduces that contact at exactly 4.10 seconds. All 420 replayed body-position samples match the original trace exactly.

This is a reproducible controller failure under the recorded command sequence. Restart timing is a lead to investigate, not yet a proven cause. The existing two-second constant-command tests do not cover this transition.

In the cluttered room, B's base contacts `obstacle_column_1` at 3.96 seconds and its front-right foot contacts the same column at 3.98. Those two geometry pairs form one debounced contact episode. No non-foot floor contacts occur in this layout. The saved first route does not establish clearance for the later route at collision time.

The corridor's first 100 commands, 101 body-position samples, and first-second pose estimates exactly match the preceding one-second run. Physics replay and this matching prefix do not establish full closed-loop five-second repeatability.

## Next work

1. Reduce the recorded corridor command sequence to a restart regression, inspect joint-target transitions, and correct the calf strike while preserving forward progress.
2. Isolate ICP drift with stationary and known-motion camera sequences. Record registration quality and pose increments before changing the estimator or introducing a separately labeled pose-assisted diagnostic.
3. Capture the planning grid, route, and body footprint at the column collision. Assess the current 0.15 m inflation against the platform's 0.35 m footprint radius without assuming inflation alone caused the collision.
4. Repeat these development checks after corrections, then verify longer closed-loop repeatability before implementing the comparison campaign.

## Artifacts and reproduction

Local artifacts are under `outputs/exploration-planning/longer-validation/<scenario>/`: `run.json`, `diagnosis.json`, `summary.json`, initial camera arrays, and first-route grids. The corridor also has `physics-replay.json`. These generated files are ignored by Git; this note records the findings.

Run each scenario with the existing diagnostic, using a new output directory:

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/diagnose_exploration_contacts.py --scenario branching_corridor --seed 101 --horizon 5 --output outputs/exploration-planning/longer-validation-rerun/branching_corridor
```

Repeat with `cluttered_room` and `connected_rooms`. The diagnostic exports raw histories; the local summary and physics replay are analysis products, not additional outputs of this command. No runtime code changed during this validation. The preceding 975-passed, 7-skipped test result remains documented in the [contact diagnosis](exploration-contact-diagnosis.md); this follow-up adds simulation evidence, not another test-suite run.
