# Roadmap: v4.0 Benchmarkable Locomotion Environment

## Overview

v4.0 turns Argus locomotion into a research-grade comparison harness before adding more sophisticated controllers. The current system already has a deterministic analytical trot and MuJoCo position-servo simulation path; this milestone wraps that path in a Gymnasium-style environment, creates reproducible scenario/seed control, exposes a controller plugin seam, instruments locomotion metrics, and adds a repeatable CLI evaluation runner.

The journey is intentionally staged: (1) define the environment/scenario/action-mode contract, (2) route the existing analytical trot through a controller protocol while reserving future adapters, (3) collect locomotion metrics from MuJoCo state/contact data, (4) run reproducible controller × scenario × seed evaluations with exports and baseline regression tests, and (5) document the harness and comparison matrix. RL training, MPC/WBC, and hardware deployment are explicitly deferred.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: locomotion-env-contract** - Gymnasium-style `ArgusGo2Env`, scenario catalog, seeded reset determinism, and action-mode contract
- [ ] **Phase 2: controller-plugin-baseline** - Locomotion controller protocol/registry, analytical trot baseline adapter, future-controller placeholders, and bridge abstraction alignment
- [ ] **Phase 3: locomotion-metrics-instrumentation** - Command tracking, stability, action-quality, and terrain/contact metrics collected from simulation state
- [ ] **Phase 4: evaluation-runner-and-regression** - CLI scenario/seed matrix runner, JSONL/CSV/summary exports, reproducibility metadata, and analytical-baseline regression test
- [ ] **Phase 5: harness-docs-and-comparison-matrix** - Harness guide, observation/action/reward/metric documentation, controller-family support matrix, and research rationale link

## Phase Details

### Phase 1: locomotion-env-contract
**Goal**: Establish a stable Gymnasium-style benchmark boundary around the existing Go2 MuJoCo locomotion path, including named scenarios, deterministic resets, and action modes.
**Depends on**: Nothing (first phase)
**Requirements**: LOC-ENV-01, LOC-ENV-02, LOC-ENV-03, LOC-ENV-04
**Success Criteria** (what must be TRUE):
  1. `ArgusGo2Env.reset(seed=...)` and `ArgusGo2Env.step(action)` return the Gymnasium-style contract: observation, reward, terminated, truncated, and info.
  2. The named scenario catalog includes at least `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance`, each selectable without changing environment code.
  3. Reusing the same seed reproduces robot spawn pose, terrain parameters, command schedule, and disturbance timing; changing the seed changes randomized scenario elements where applicable.
  4. Action modes for velocity command, joint-position target, and residual-over-baseline control are selected through environment config while preserving one environment API.
  5. Existing non-Gym simulation/web paths still boot, so the benchmark wrapper does not break the C2 runtime.
**Plans**: TBD
**Research flag**: standard

### Phase 2: controller-plugin-baseline
**Goal**: Put locomotion controllers behind a common protocol so the analytical trot becomes the default comparator and future residual/direct/MPC/WBC controllers have explicit extension seams.
**Depends on**: Phase 1
**Requirements**: LOC-CTRL-01, LOC-CTRL-02, LOC-CTRL-03, LOC-CTRL-04
**Success Criteria** (what must be TRUE):
  1. A `LocomotionController`-style protocol maps environment observation plus command into the configured action/actuator output shape.
  2. The existing `TrotGaitController` is available as the default registered baseline controller and produces behavior-equivalent joint targets in the flat-ground smoke scenario.
  3. Placeholder adapters for residual policy, direct policy, MPC, and WBC can be registered/discovered without editing MuJoCo bridge internals; unavailable implementations fail explicitly at selection time, not mid-run.
  4. Single-robot and multi-robot bridge paths share the same controller/action abstraction where practical, with no duplicated evaluation-specific control loop.
  5. Controller selection metadata is emitted into environment/evaluation info so downstream metrics know which controller produced each action.
**Plans**: TBD
**Research flag**: standard

### Phase 3: locomotion-metrics-instrumentation
**Goal**: Make locomotion behavior measurable: command tracking, stability, action quality, and contact/terrain proxies are computed consistently across scenarios and controllers.
**Depends on**: Phase 2
**Requirements**: LOC-METRICS-01, LOC-METRICS-02, LOC-METRICS-03, LOC-METRICS-04
**Success Criteria** (what must be TRUE):
  1. Metric collection reports forward/lateral/yaw command tracking error over time using desired command and measured base motion.
  2. Stability metrics include fall rate, roll/pitch bounds, base-height deviation, and distance before failure with explicit termination thresholds.
  3. Control-quality metrics include action smoothness, joint-limit violations, energy/effort proxy, and actuator saturation or equivalent position-servo proxy.
  4. Terrain/contact metrics include foot slip, foot clearance, contact timing/duty factor, and per-scenario success rate.
  5. Per-step and per-episode metric values are available through `info` or a metrics collector without tying them to one specific controller implementation.
**Plans**: TBD
**Research flag**: standard

### Phase 4: evaluation-runner-and-regression
**Goal**: Provide a repeatable CLI benchmark runner that executes controllers across scenario/seed matrices and exports enough data to compare and reproduce runs.
**Depends on**: Phase 3
**Requirements**: LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-03, LOC-EVAL-04
**Success Criteria** (what must be TRUE):
  1. A CLI evaluation command runs one or more controllers across a named scenario matrix and fixed seed list.
  2. Each run exports JSONL/CSV plus a machine-readable summary with per-controller mean, standard deviation, and failure counts.
  3. Exported metadata includes git commit, controller id, scenario id, seed, environment config, action mode, and run timestamp.
  4. The aggregate comparison table can be generated from saved artifacts without re-running simulation.
  5. A regression test prevents the analytical trot baseline from silently degrading on the flat-ground smoke scenario.
**Plans**: TBD
**Research flag**: standard

### Phase 5: harness-docs-and-comparison-matrix
**Goal**: Document the benchmark harness and make the supported/deferred controller-family boundary explicit for future locomotion work.
**Depends on**: Phase 4
**Requirements**: LOC-REPORT-01, LOC-REPORT-02, LOC-REPORT-03
**Success Criteria** (what must be TRUE):
  1. A concise harness guide explains observation space, action modes, reward/metric definitions, scenario catalog, and CLI evaluation workflow.
  2. A controller-family matrix states what is supported now versus deferred for analytical gait, residual RL, direct RL, MPC, WBC, ROS/hardware, and perception-conditioned locomotion.
  3. The documentation links `outputs/locomotion-rd-systems.md` as the rationale for v4 scope and accurately summarizes the current Argus method as analytical trot + MuJoCo position actuators.
  4. A new developer can run the flat-ground analytical baseline smoke benchmark from the guide without reading the implementation first.
**Plans**: TBD
**Research flag**: light

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. locomotion-env-contract | 0/TBD | Not started | - |
| 2. controller-plugin-baseline | 0/TBD | Not started | - |
| 3. locomotion-metrics-instrumentation | 0/TBD | Not started | - |
| 4. evaluation-runner-and-regression | 0/TBD | Not started | - |
| 5. harness-docs-and-comparison-matrix | 0/TBD | Not started | - |

## Requirement Coverage

| Phase | Requirements |
|-------|--------------|
| Phase 1 | LOC-ENV-01, LOC-ENV-02, LOC-ENV-03, LOC-ENV-04 |
| Phase 2 | LOC-CTRL-01, LOC-CTRL-02, LOC-CTRL-03, LOC-CTRL-04 |
| Phase 3 | LOC-METRICS-01, LOC-METRICS-02, LOC-METRICS-03, LOC-METRICS-04 |
| Phase 4 | LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-03, LOC-EVAL-04 |
| Phase 5 | LOC-REPORT-01, LOC-REPORT-02, LOC-REPORT-03 |

**Coverage:** 20/20 active requirements mapped ✓
**Orphans:** none
**Duplicates:** none

## Next Step

Roadmap approved 2026-04-30. Start with `/gsd-plan-phase 1` for `locomotion-env-contract`.
