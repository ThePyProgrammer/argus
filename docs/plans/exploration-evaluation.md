# Multi-robot exploration evaluation: execution plan

Status: implementation started. Created November 1, 2026.

The CLI commands, module names, method IDs, and artifacts below are proposed contracts unless explicitly described as existing. This document does not claim that the evaluator or any experimental results already exist.

### Implementation progress

Phase A (PR 1) is implemented: [fixture contracts](../../src/exploration/evaluation/scenarios.py), [three static layouts](../../data/benchmarks/exploration/README.md), deterministic spawn samples, analytical reference masks, and [ADR-0020](../adr/0020-evaluate-exploration-against-fixed-reference-area.md). The 262 exploration tests pass, including area calculations at two resolutions, compiled-geometry agreement, spawn validation, and initial Go2 camera ray checks.

PR 2 is implemented: the [compiled-geometry reference extractor](../../src/metrics/exploration_reference.py) supports static boxes at arbitrary rotations, fixed bounds, footprint/height clearance, and connected components with swept-clearance checks. It matches the analytical fixture masks at both validated resolutions. The [reference-area guide](../exploration-reference.md) covers diagnostic SVG/JSON/NPZ exports and rejected spawn markers.

Validation: 44 reference-extractor tests and 324 tests across the metrics and exploration suites pass. All three diagnostic exports were generated and checked.

PR 3 collectors are implemented: [camera-based coverage](../../src/metrics/exploration_coverage.py), first-observation exports, fixed-horizon AUC and overlap, body travel, contact episodes, recovery/fall transitions, planning failures, goal changes, and allocator latency. The [measurement contract](../exploration-measurements.md) defines depth tolerances, pixel support, event debounce, and failure scoring. A shared bridge fix preserves MuJoCo's metric depth for sub-meter views and invalidates readings beyond the sensing range.

Validation for PR 3: 59 collector tests and 6 depth regression tests were added. The metrics/exploration suites pass 383 tests; the bridge suite passes 121 with 3 skips. Rendered fixtures cover sub-meter and oblique floor views, wall occlusion, and robot occlusion.

PR 4's development lifecycle is implemented: [ExplorationEpisode](../../src/exploration/evaluation/episode.py) shares coordinator start/advance/close operations with the dashboard, applies resolved fixture spawns, owns recovery streams, and wires the collectors at the post-settling boundary. The [episode guide](../exploration-episodes.md) covers the smoke script, failure outcomes, timing, and process-memory scope. Repeatability tests compare real command and body traces with and without collection, including the first frontier scan.

Validation for PR 4: 695 tests pass across the runtime, metrics, SLAM, dashboard integration, and worker checks, with 7 skips. Nine existing subprocess SLAM tests fail because this Windows ZeroMQ build reports no IPC support. Those backend files are unchanged. Real episode tests include 17 cases; the two-episode planning test has a scoped 120-second timeout for offscreen rendering.

The [first-scan failure](../notes/exploration-first-scan-failure.md) is corrected in the [shared navigation baseline](../exploration-navigation.md). Targets are reachable frontier cells, newly planned paths survive the scan frame, and observed floor is separated before obstacle-map accumulation. Recovery now measures commanded progress over simulated time instead of requiring 5 cm per sensor frame. The [longer-run diagnostic](../notes/exploration-recovery-validation.md) records the resulting smoke checks, contacts, and a stale-path failure. Route invalidation now keeps an exhausted robot idle until a new route is installed; regression tests cover one idle robot alongside an active teammate. The [contact diagnosis](../notes/exploration-contact-diagnosis.md) now separates calf-floor strikes from wall collisions, corrects camera/body navigation frames and swing clearance, and explains initial zero coverage through wall occlusion. Establish longer-run stability and repeatability before comparing methods. PR 5's batch CLI, persistent manifests, and resume support remain unimplemented.

Current development gate: [observed free space, weighted floor support, and exact path goals](../notes/exploration-free-space-correction.md) are implemented and pass 1,054 regression tests with seven skips. Seed-101 corridor and connected-room checks reach five seconds with 88.9% and 70.8% coverage. The cluttered room reaches 9.07 s and 64.0% coverage before tracking fails with the camera about 2.2 cm from a column. Corridor and cluttered-room runs each record two contact episodes; none records a fall. Next address camera/footprint clearance and gait transitions, then repeat the live validation. Additional seeds, sustained longer runs, isolated episode timing, and long-run collector neutrality remain before allocator comparisons. Earlier [repeatability](../notes/exploration-repeatability-validation.md) and [voxel-cache performance](../notes/exploration-voxel-cache-validation.md) results describe their recorded revisions.

## 1. Result to produce

Build a reproducible study answering:

> Under fixed sensing, mapping, and locomotion conditions, does joint frontier assignment improve two-robot exploration over independent and Voronoi-biased goal selection?

Deliver a tested evaluator, three allocation methods, a frozen experiment matrix, downloadable results, a technical report, and a short visual demonstration. A positive result should quantify an improvement with uncertainty and account for failures. A negative result should explain where the method fails and provide a reusable benchmark.

The engineering contribution is the reproducible system and its evaluation. Joint frontier allocation is an established approach; implementing it does not by itself establish algorithmic novelty.

### Scope

| Included in the first study | Deferred until the study is complete |
| --- | --- |
| Two Go2 robots, one shared MuJoCo simulation | Larger teams, mixed robot platforms, hardware |
| Three bounded, static indoor layouts | Moving obstacles, terrain variation, procedural scene families |
| Existing ICP mapping and `icp_union` merge baseline | Comparisons between SLAM or detection backends |
| Independent, Voronoi, and joint allocation | Learned policies and skill-selection experiments |
| Simulator-assisted pose reference, disclosed in results | Pose noise, localization robustness, communication restrictions |
| CLI evaluation, analysis scripts, compact report | General dataset platform, full episode replay, broad dashboard redesign |

Disable optional detectors, VLMs, and exploration skill learning for the primary campaign. Keep the same robot controller, sensor configuration, map construction, recovery behavior, and information availability across methods.

## 2. Existing code and gaps

| Existing component | Reuse | Required work |
| --- | --- | --- |
| [Locomotion evaluator](../../src/locomotion/evaluation.py) | Matrix validation, manifests, CSV/JSONL output, summary regeneration pattern | Implement a separate exploration evaluator; avoid a general experiment framework in the first PR. |
| [Coordinator](../../src/coordination/coordinator.py) | Shared simulation, map publication, per-robot control | Expose an episode lifecycle and a common decision snapshot. Current goal selection occurs sequentially inside robot steps. |
| [Exploration loop](../../src/exploration/exploration_loop.py) | Frontier discovery, path following, recovery | Separate candidate preparation from allocation and execution while preserving existing behavior. |
| [Voronoi partitioner](../../src/coordination/voronoi_partitioner.py) | Existing two-robot baseline | Add an explicit method adapter and deterministic tie handling. Do not imply general team-size support. |
| [Coverage tracker](../../src/exploration/coverage_tracker.py) | Legacy progress diagnostics | Frontier exhaustion and bounding-box occupancy are not observed-area coverage. Add an independent measurement path. |
| [Occupancy projection](../../src/exploration/occupancy_grid.py) | Existing planner input | Its inferred free cells and trajectory stamping must not define measured coverage. |
| [Scene library](../../src/bridge/scene_library.py) | Asset loading and scene conventions | Preview bounds and clearance approximations are not a validated coverage oracle. Define explicit benchmark bounds and collision geometry. |
| [Multi-robot bridge](../../src/bridge/multi_bridge.py) | Physics, cameras, platform status | Capture sensor timestamps, reset state, expose simulation time, and guarantee cleanup. |
| [Local transport](../../src/coordination/transport.py) | Existing map callbacks | Prevent callbacks and state from leaking between episodes. |

Map merging currently collects outputs; it should not be assumed to populate every robot's planning grid. Trace and document the actual information flow before defining the benchmark. A new shared planning map would be a separate experimental intervention.

## 3. Measurement contract

### Fixed reference area

For each layout, create a finite 2D evaluation grid from the compiled collision geometry. Use a declared robot footprint and body-clearance envelope to identify navigable cells. Restrict the denominator to a preselected connected free-space component. Every accepted spawn pair must lie inside that same component.

Call the resulting cell set `R`. It is fixed before any method runs. Store its bounds, origin, resolution, clearance assumptions, scene hash, generator version, mask hash, and area in square meters. Never shrink `R` because a method failed to reach a region.

Begin with static primitive geometry whose free area can be independently checked. Proposed layout IDs are `branching_corridor`, `connected_rooms`, and `cluttered_room`. Store their MJCF and metadata under `data/benchmarks/exploration/`. They are new fixtures, not existing scene-library IDs. Existing office or restaurant scenes can become follow-up cases after their geometry and moving props are handled explicitly.

Proposed initial evaluation resolution is 0.10 m. Check sensitivity at 0.05 m on development fixtures before freezing it. Use one validated footprint across methods and record that this is an approximation to Go2's traversability, not a proof of dynamic reachability.

### Observed area

For each sensor frame, project fixed floor sample points into the camera using the capture-time camera transform and intrinsics. Count a sample only when it is within the image and sensing range, has valid depth, and the projected depth agrees with the visible floor surface within a documented tolerance. Occluders, including the other robot, must prevent observation. Use the correct camera depth convention; Euclidean ray length and camera-axis depth are not interchangeable.

This defines **visible reachable floor coverage**. It is not complete 3D reconstruction quality or a guarantee that the planner marked each cell free. Keep those distinctions in plots and reports.

Let `O_i(t)` be the cumulative reference cells observed by robot `i` by simulation time `t`:

```text
C(t) = |R intersect union_i O_i(t)| / |R|
AUC = integral from 0 to T of C(t) dt / T
overlap(t) = |O_1(t) intersect O_2(t)| / |O_1(t) union O_2(t)|
```

An empty observation union gives overlap zero with an explicit zero-observation flag. Record coverage at a fixed simulation-time cadence and integrate with the same documented rule for every run. Keep per-robot observation masks so overlap can be regenerated without rerunning physics.

The evaluation oracle must not provide reference free-space masks, hidden geometry, or coverage gradients to allocation or navigation. Existing pose assistance remains part of the simulation baseline and must be disclosed. Verify that attaching the measurement collector leaves command traces unchanged.

### Endpoints and failure treatment

| Metric | Definition and use |
| --- | --- |
| Primary: normalized coverage AUC | Measures how quickly area is observed over a fixed horizon, including runs that never reach a threshold. |
| Final coverage | Observed fraction at horizon `T`; report per scene and across scenes. |
| Threshold success | Whether coverage reaches 90% by `T`. Validate threshold feasibility during development, then freeze it. |
| Time to threshold | First simulated time reaching 90%; null if never reached. Always accompany it with success rate. |
| Capped time score | Threshold time on success, otherwise `T`. Label this an evaluation penalty, not an observed completion time. |
| Total travel | Sum of ground-truth body XY path lengths across both robots, excluding initial settling. |
| Duplicate observation | Cross-robot cumulative overlap at `T`, plus its time series. It describes redundancy, not necessarily wasted work. |
| Safety and reliability | Falls, robot-obstacle and robot-robot contact episodes, recovery entries, failed planning, and goal switches. Exclude expected foot-floor contacts. |
| Cost | Wall time, peak memory, real-time factor, allocator latency, and sensor frames processed. Report hardware and thread settings. |

Continue each valid episode to the same horizon for AUC, even after crossing 90%. If an algorithm exhausts frontiers or a robot fails, use a documented absorbing termination: retain the last observation set through `T`, prohibit new measurements after termination, and record the reason. If only one robot fails, stop the failed robot and allow the survivor to continue under the same rule for all methods.

Algorithm failures remain in the results. Infrastructure failures, such as renderer initialization failure or process termination, remain in the manifest as invalid attempts. Retry them with identical inputs and a linked attempt ID. Never silently remove or replace a difficult seed.

## 4. Experimental methods and controls

### Common decision input

At each allocation event, snapshot all robots before assigning any new goals. Use deterministic robot order and a versioned candidate catalog with world-frame IDs. Resolve matching local frontier clusters by a fixed spatial rule and test ambiguous cases.

Keep each robot's local map and feasible targets as the source of its candidates. Joint allocation may compare those candidate sets, but may not use remote-only targets or a hidden map unavailable to the baselines. All methods receive the same input schema; their selection rules decide what information to use.

A joint decision must not update another robot's sensors or map midway through allocation. Reserve active goals until completion, invalidation, or a common switching rule. Trigger allocation on the union of rescan/invalidation events; candidates from non-rescanning robots retain their recorded age. Apply the same scheduling rules to every method.

### Methods

| Proposed ID | Rule |
| --- | --- |
| `independent_nearest` | Each robot selects its nearest feasible local frontier with no cross-robot exclusion. |
| `voronoi_bias` | Existing region multiplier and nearest-frontier preference, retaining current repartition behavior. |
| `joint_assignment` | Select a pair of feasible targets using estimated information gain, path cost, switching cost, and overlap between predicted observation regions. |

For joint assignment, start with exhaustive pair enumeration for two robots. Use a bounded candidate list, initially at most 20 per robot, plus an idle option. All methods use the same candidate-generation and truncation rules. Record truncation frequency and perform a development check with a larger cap.

```text
pair utility = sum_i(alpha * estimated_gain_i
                     - beta * path_cost_i
                     - gamma * switch_cost_i)
               - lambda * predicted_overlap
```

Estimate gain from unknown cells in each robot's observed planning grid, never from `R`. Use A* path length for travel cost; unreachable targets are infeasible. Normalize terms with fixed, documented scales. For the main joint method, forbid assigning the same canonical frontier to both robots. Distinct frontiers can still have overlapping predicted views, which the overlap term addresses. Choose ties deterministically and define idle/recovery behavior when no valid pair exists.

Two ablations are required: `joint_no_deconfliction` removes both the same-target constraint and overlap penalty; `joint_no_gain` sets `alpha` to zero while retaining deconfliction. Use identical infrastructure and candidate generation. Describe these interventions precisely in the report.

Before comparing results, characterize any changes introduced by the common scheduling adapter relative to the original coordinator. Fix regressions for all methods before freezing the study. Do not call an adapted baseline behaviorally identical without evidence.

## 5. Implementation phases and acceptance gates

Each numbered PR below should be independently reviewable. Estimates are focused engineering days for one contributor, exclude unattended runs, and should be revised after the first end-to-end episode.

| Phase | PRs | Estimate | Exit gate |
| --- | --- | --- | --- |
| A. Study contract and fixtures | 1 | 2-3 days | Versioned measurement specification and three bounded layouts with validated spawn pools. |
| B. Coverage measurement | 2-3 | 4-6 days | Independent analytical tests and rendered sensor checks pass; no oracle information reaches planning. |
| C. Episode lifecycle and evaluator | 4-5 | 4-6 days | One baseline episode and a resumable matrix produce complete artifacts. |
| D. Allocation comparison | 6-7 | 4-6 days | Baselines, candidate, and ablations run through the same decision interface. |
| E. Pilot and protocol freeze | 8 | 2-3 days | Runtime budget, repeatability, parameter choices, and final matrix are fixed. |
| F. Evaluation and analysis | 9 | 2-4 days plus compute | Complete attempt accounting, paired comparisons, uncertainty, and regenerated figures. |
| G. Report and demonstration | 10 | 2-3 days | Reproducible report, video, and concise project summary. |

Budget roughly 20-31 focused working days. The critical path is reference geometry, coverage correctness, lifecycle extraction, common allocation inputs, pilot, frozen campaign, and report. Larger teams and new policy families are not prerequisites.

### PR 1: Define study and benchmark scenes

- [x] Add an ADR defining evaluation-only geometry, the observed-floor metric, fixed horizon, and supported assumptions. Recorded in ADR-0020.
- [x] Add the three bounded static MJCF fixtures, source/license metadata, analytic floor masks, and clear spawn pools with heading samples.
- [x] Add a typed scenario contract in `src/exploration/evaluation/scenarios.py`.
- [x] Validate door clearance, connected components, non-overlapping spawns, and initial camera visibility with compiled-geometry ray checks. All geometry is static; rendered depth validation belongs to PR 3.
- [x] Record proposed defaults: two Go2 robots, 320x240 sensors, 0.10 m evaluation and map grids, existing ICP backend, `icp_union`, no optional inference, and zero visualization delay. `StudyDefaults` makes these explicit; applying them to the runtime belongs to PR 4.

**Gate:** Independently hand-check free area and obstacle boundaries on small analytical fixtures. Invalid spawns or empty denominators fail before constructing the runtime.

### PR 2: Implement the reference mask

- [x] Add `src/metrics/exploration_reference.py` for compiled collision geometry, footprint/height clearance, fixed bounds, connected-component selection, and hashes. Supported geometry is explicit; arbitrary meshes and other collider families remain unsupported.
- [x] Use actual collision transforms, including rotated and tilted boxes. Verify against independent analytical fixtures and MuJoCo box contact calculations; do not reuse preview AABBs.
- [x] Store diagnostic SVG overlays, mask arrays, metadata, and rejected spawn locations through `scripts/inspect_exploration_reference.py`.

**Gate:** Rotated obstacles, narrow doors, disconnected rooms, boundary cells, and translation/rotation transforms have independently derived expected outcomes. Refining grid resolution does not produce unexplained area changes.

### PR 3: Implement coverage and reliability collectors

- [x] Add `src/metrics/exploration_coverage.py` and `exploration_metrics.py` for sensor visibility, observation masks, AUC, travel, events, and allocator timing. Runtime wall time and memory measurement belong to PR 4.
- [x] Keep legacy progress metrics available under clearly distinct names. Do not silently change the meaning of existing dashboard fields.
- [x] Snapshot capture-time camera transforms and simulator time; accept an explicit post-settling `t=0` and reject samples outside the measured interval. Establishing this boundary before autonomous bootstrap motion is part of PR 4 integration.
- [x] Define collision event debouncing and recovery-entry counting so sustained contact is not counted once per frame.

**Gate:** A stationary camera cannot gain coverage from repeated frames; two identical views do not double team coverage; a wall occludes floor behind it; invalid depth adds nothing; no-frontier status does not imply 100% coverage. Test the unprojection/projection convention with rendered fixtures.

### PR 4: Extract a deterministic episode lifecycle

- [x] Introduce `ExplorationEpisode` in `src/exploration/evaluation/episode.py` with start, advance, inspect, and close operations. Reuse the coordinator's control path rather than copying its loop.
- [x] Capture observations and commands at explicit frame boundaries and allow measurement collection to attach without influencing decisions.
- [x] Establish the collectors' post-settling clock origin before autonomous bootstrap motion. Wire body states, geom ownership, contact cadence, planning events, goal-selection latency, wall time, and process RSS high-water mark into measurements. Per-episode memory isolation and the joint allocator timing boundary remain future work.
- [x] Use simulation-time recovery intervals and named random streams on the benchmark path. Resolve spawns and headings explicitly; isolate depth-to-cloud settings from the dashboard.
- [x] Close the bridge, renderers, subscribers, and workers in `finally` paths. Preserve the dashboard's existing start/stop behavior.
- [x] Make caught exploration errors, disabled robots, and unexpected backend fallback explicit episode events and outcomes.

**Gate:** Same inputs on the same supported environment reproduce spawn state and decision traces within declared numerical tolerances. Running an episode alone or after another episode gives equivalent results. Evaluation collectors do not alter commands.

Development gate passes for short episodes and successful first-scan planning, with MuJoCo 3.6 and one OpenMP thread. Longer successful episodes must pass the same checks before the study.

### PR 5: Add `eval-exploration` and artifacts

- [ ] Add proposed `src/exploration/evaluation/config.py`, `runner.py`, and `exports.py`; connect the command through [src/main.py](../../src/main.py).
- [ ] Validate the entire matrix before writing output: method availability, scene hashes, horizon, seed ranges, robot count, output location, and maximum episode count.
- [ ] Write append-safe per-episode artifacts and atomically finalize completion records. Support resume by configuration hash and episode key.
- [ ] Add summary regeneration from saved records, without simulator construction or model downloads.
- [ ] Start with sequential execution. Use isolated processes for concurrent episodes only after cleanup and resource limits are measured. Disable the browser during batch runs; retain offscreen rendering for depth sensing.

**Gate:** A small matrix completes, interrupted output resumes without duplicate completed episodes, conflicting configurations fail, and regenerated summaries match original summaries. CLI help requires no optional detector setup.

### PR 6: Expose allocation inputs and baseline adapters

- [ ] Add proposed `src/coordination/allocation.py` for candidate snapshots, assignments, and method discovery.
- [ ] Split frontier preparation, allocation, and path execution in the exploration loop only as far as the shared decision point requires.
- [ ] Implement independent and Voronoi adapters, preserving feasible-target fallback, ongoing-goal handling, and recovery rules.
- [ ] Capture before/after baseline traces and explain intentional scheduling differences. Keep legacy web behavior unchanged unless a shared bug fix is required.

**Gate:** Robot iteration order does not change an allocation snapshot. Both methods handle zero, one, and multiple reachable frontiers. Any shared fixes are applied and evaluated before candidate tuning.

### PR 7: Implement joint assignment and ablations

- [ ] Add proposed `src/coordination/allocators/` implementations with deterministic tie breaking, explicit infeasibility, bounded enumeration, and recorded parameters.
- [ ] Store candidate scores, chosen assignments, path costs, predicted gain/overlap, target changes, and allocator latency in decision traces.
- [ ] Implement the two ablations as explicit method configurations, not separate copies of the runtime.

**Gate:** Synthetic cases cover duplicate targets, asymmetric path cost, overlapping views, one idle robot, invalidated goals, and no feasible pair. Oracle-only changes cannot change allocation. A larger candidate cap does not conceal a material truncation effect.

### PR 8: Pilot, tune, and freeze

- [ ] Run the pilot matrix below. Confirm visibility coverage is attainable and identify whether mapping or locomotion failures dominate.
- [ ] Choose horizon, threshold, event tolerances, gain radius, candidate cap, and method parameters using development data only.
- [ ] Give parameterized methods the same declared tuning budget. Log all configurations and pilot attempts; do not tune just the candidate while leaving an arbitrarily weak baseline.
- [ ] Freeze code revision, dependency lock, scenario/reference hashes, methods, seeds, endpoints, aggregation rules, and numerical tolerances in a study manifest.
- [ ] Register a runtime and disk budget from measured pilot throughput before starting the final campaign.

**Gate:** Final seeds have not been used for parameter selection. Sensor, geometry, and lifecycle tests pass. If basic exploration fails across methods, fix shared infrastructure and repeat the pilot before scaling runs.

### PR 9: Execute and analyze

- [ ] Run all frozen primary and ablation episodes; record every attempted cell and infrastructure retry.
- [ ] Add proposed `scripts/analyze_exploration.py` to verify completeness and compatibility, compute paired effects, and generate standalone SVG/PNG figures and CSV tables.
- [ ] Diagnose failures using traces and observation overlays; do not change primary-run parameters after inspecting final results.
- [ ] If a correctness bug is discovered, invalidate affected results with a reason, revise the study version, and rerun all affected methods rather than only the candidate.

**Gate:** Every planned episode has a valid result or a documented unresolved infrastructure failure. Incomplete pairs are identified, and a headline comparison is withheld if missingness could bias the conclusion.

### PR 10: Publish the local result package

- [ ] Write `docs/reports/exploration-evaluation.md` with question, methods, assumptions, experiment matrix, uncertainty, ablations, failure cases, limitations, and reproduction commands.
- [ ] Provide coverage curves, per-scene paired-effect plots, success/failure tables, overlap/travel summaries, and allocator cost.
- [ ] Select video episodes by a declared rule, such as the median primary-effect pair plus one failure, rather than the best candidate run.
- [ ] Add a small saved-run comparison view only if it can directly consume the finalized artifact schema. Static plots and the report are sufficient for this milestone.
- [ ] Update the README with measured outcomes and a link to the report. Keep all performance claims qualified as simulation results.

**Gate:** A fresh checkout can run a smoke case and regenerate the report figures from retained artifacts. The resume bullet can be traced to a specific table and manifest.

## 6. Experiment matrix and compute budget

Seeds control sampled spawn pairs/headings and named recovery streams. Repeating an unchanged deterministic scene under meaningless seed labels does not create independent evidence. Store the resolved initial state for each seed; use identical resolved states across methods.

| Stage | Matrix | Episodes | Purpose |
| --- | --- | --- | --- |
| Pilot | 3 primary methods x 3 layouts x seeds 101, 102, 103 | 27 | Validate runtime, metrics, and choose parameters. Additional tuning runs must be logged separately. |
| Repeatability | Rerun seed 101 for each primary method/layout | 9 additional | Compare against pilot traces; not independent statistical samples. |
| Primary study | 3 methods x 3 layouts x seeds 1001-1010 | 90 | Fixed comparison on unseen initial conditions. |
| Ablations | 2 ablations x 3 layouts x seeds 1001-1010 | 60 | Explain which candidate terms affect results. |
| Optional scaling reference | 1 independent robot x 3 layouts x seeds 1001-1010 | 30 | Context for team benefit; a separate question from the fixed-team comparison. |

The planned core is 186 episodes including pilot and repeatability, before extra tuning or infrastructure retries. It contains 150 final evaluation episodes. Ten seeds per layout are an initial design, not a guarantee of statistical precision.

Use pilot variability to select a fixed final sample size before inspecting final results. If ten seeds are inadequate, expand the primary and ablation matrices together to seeds 1001-1030: 450 final episodes and 486 including the listed pilot/repeatability runs. Do not add seeds selectively until a favorable result appears. Three layouts support claims about those layouts, not broad scene generalization.

Start development with a proposed 300 simulated-second horizon. Freeze or revise it using pilot feasibility and throughput. Record actual physics and sensor step durations; progress and recovery now use captured simulation time.

```text
serial wall hours = sum of episode wall seconds / 3600
estimated remaining hours = remaining episodes * pilot wall-time estimate / 3600
storage estimate = episodes * measured bytes per episode
```

For illustration only, at 10 wall minutes per episode, 186 episodes require 31 serial hours, or about 37 hours with a 20% reserve. This is not a measured Argus runtime. Estimate both a typical and a conservative completion budget from pilot median and tail latency. Add workers only after measuring renderer compatibility, peak memory, and throughput under contention.

Pair execution order within each scene/seed block and randomize method order with a recorded scheduling seed. Report simulation-time behavior separately from wall-clock cost; frozen-step simulation does not establish a real-time deployment deadline guarantee.

## 7. Artifacts and proposed commands

Store full generated output outside version control under `outputs/exploration-evals/<study-id>/`. Commit configs, tests, small reference fixtures, and compact report figures. Add narrowly scoped ignore rules for generated run payloads during implementation.

```text
manifest.json                  Study protocol, matrix, code/environment provenance
attempts.jsonl                 Every start, completion, failure, and retry
episodes.csv                   One resolved result per matrix cell, with attempt reference
summary.json                   Aggregate metrics, paired effects, confidence intervals
comparison.md                  Generated tables and failure accounting
episodes/<episode-id>/
  config.json                  Resolved configuration and initial state
  steps.jsonl                  Simulation time, coverage, trajectory and runtime metrics
  decisions.jsonl              Candidate scores and selected targets
  events.jsonl                 Falls, contacts, recovery, fallback, and termination
  observations.npz             Per-robot first-observation times on the reference grid
  trajectory.npz               Body poses and optional replay state
  result.json                  Final metrics and completion status
figures/                       SVG/PNG outputs generated from saved data
```

The manifest includes schema/metric versions, git commit and dirty-state indicator, dependency versions/lock hash, OS/CPU, renderer, thread settings, robot/scene/reference hashes, pose assumptions, all seeds, sensor cadence, planning parameters, and artifact checksums. Refuse publication-mode runs from an unrecorded dirty tree. Store a patch or require a clean revision.

Episode identity is derived from study configuration, method, layout, and seed. Retries receive distinct attempt IDs. Summary generation must never mix different metric versions or silently choose the best attempt. Use the first valid completed attempt according to the frozen retry policy.

Proposed commands, to be implemented in PR 5:

```bash
uv run argus eval-exploration --method independent_nearest --scenario connected_rooms --seed 101
uv run argus eval-exploration --matrix-config configs/evaluation/exploration/pilot.json
uv run argus eval-exploration --matrix-config configs/evaluation/exploration/study-v1.json
uv run argus eval-exploration --resume outputs/exploration-evals/<study-id>
uv run argus eval-exploration --from-run-dir outputs/exploration-evals/<study-id>
uv run python scripts/analyze_exploration.py --run-dir outputs/exploration-evals/<study-id>
```

## 8. Analysis and claim rules

The primary comparison is `joint_assignment` versus `voronoi_bias` on normalized coverage AUC. Independent selection and the two ablations provide contextual and mechanism comparisons. Declare this ordering before final evaluation.

Compute candidate-minus-baseline differences within each layout/seed pair. Report per-layout means, medians, spread, success rates, and paired-effect intervals. For the combined result, weight the three fixed layouts equally and bootstrap paired seeds within each layout. Use a recorded bootstrap seed and 10,000 resamples. The resulting interval describes variation over initial conditions in these fixed layouts; it does not establish generalization to unseen layouts. Repeated frames are not independent samples.

Report AUC improvement in percentage points, alongside raw values. Report percentage reductions in completion time only with the exact denominator, success rates, and failure policy. Do not report successful-runs-only completion times as the primary performance result. Keep safety events and compute cost visible even when coverage improves.

Before freezing, choose a practical improvement threshold. A proposed engineering target is at least 0.05 absolute normalized-AUC gain with no material regression in threshold success or safety. Define the allowed regression margins numerically in the study manifest using application needs, not final outcomes. This target is not a promised result. Statistical uncertainty, practical magnitude, and safety behavior must all be discussed.

Separate tuning and test seeds to reduce selection bias, following the experimental guidance in [Eimer et al., 2023](https://proceedings.mlr.press/v202/eimer23a.html). Careful baseline construction and reporting of performance variability are also central to [Patterson et al., 2024](https://www.jmlr.org/papers/v25/23-0183.html). Applying those practices to this non-learning allocation study is a design choice; neither paper validates the proposed allocator or sample size.

## 9. Validation and stop conditions

| Risk | Required check or response |
| --- | --- |
| Incorrect denominator or visibility | Analytical geometry and rendered occlusion fixtures must agree before performance runs. |
| Reference data reaches the planner | Typed observer boundary plus a command-trace invariance test. |
| Candidate gets extra information | Audit local-map membership, remote-target access, candidate ages, and scheduling across methods. |
| Refactor changes the baseline | Before/after trace comparisons; shared fixes and documented deviations before protocol freeze. |
| Mapping or locomotion dominates failures | Diagnose on development seeds. Fix shared issues or narrow the question; do not attribute those failures to allocation alone. |
| Nondeterminism or episode leakage | Repeated isolated runs, reversed execution order, and cleanup tests with injected exceptions. |
| Unrealistically optimistic timing | Separate simulated-time results from wall time and report allocator latency/resource consumption. |
| Candidate has no measurable advantage | Publish the measured tradeoff or negative result. Do not replace the primary endpoint after seeing results. |
| Rendered scenes are too expensive | Reduce concurrency first; change sensor settings only during development and apply them equally. |
| Timeout and crash records disappear | Completeness check against the frozen matrix; retries remain linked and visible. |

Add meaningful tests under `tests/exploration/`, `tests/coordination/`, `tests/metrics/`, and `tests/integration/`. Prioritize geometry truth, paired initial states, goal assignment edge cases, observation-only behavior, artifacts/resume, and existing control behavior. Run focused tests per PR, then the existing relevant exploration/coordination/bridge suites at the lifecycle and allocation gates. Execute the full applicable suite once before freezing the campaign and after any shared runtime fix.

## 10. Completion checklist and follow-up

- [ ] Coverage has an independent reference and a documented physical interpretation.
- [ ] Two baselines, the candidate, and both ablations use the same runtime and information rules.
- [ ] Every final episode is accounted for, including failures and retries.
- [ ] Paired results, uncertainty, per-layout behavior, safety, and compute cost are reported.
- [ ] Figures regenerate from saved artifacts, and a smoke run works from a documented environment.
- [ ] Report and video identify representative behavior and failure modes.
- [ ] README and resume claims cite measured tables and explicitly state simulation scope.

Possible resume wording after measurement:

> Built a reproducible two-robot exploration benchmark across 150 evaluation episodes and three MuJoCo layouts; implemented joint frontier allocation with [measured AUC effect], [threshold success], and [travel/cost tradeoff] relative to Voronoi coordination.

Fill placeholders from the report, or describe the benchmark and findings without an improvement claim. If the core study succeeds, the next independent study should introduce delayed or intermittent map exchange. Validate the baseline first, then change one assumption at a time.
