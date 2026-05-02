# Roadmap: v4.0 Benchmarkable Locomotion Environment

## Overview

v4.0 turns Argus locomotion into a research-grade comparison harness before adding more sophisticated controllers. The current system already has a deterministic analytical trot and MuJoCo position-servo simulation path; this milestone wraps that path in a Gymnasium-style environment, creates reproducible scenario/seed control, exposes a controller plugin seam, instruments locomotion metrics, and adds a repeatable CLI evaluation runner.

The journey is intentionally staged: (1) define the environment/scenario/action-mode contract, (2) route the existing analytical trot through a controller protocol while reserving future adapters, (3) collect locomotion metrics from MuJoCo state/contact data, (4) run reproducible controller × scenario × seed evaluations with exports and baseline regression tests, and (5) document the harness and comparison matrix. RL training, MPC/WBC, and hardware deployment are explicitly deferred.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: locomotion-env-contract** - Gymnasium-style `ArgusGo2Env`, scenario catalog, seeded reset determinism, and action-mode contract — completed 2026-04-30
- [x] **Phase 2: controller-plugin-baseline** - Locomotion controller protocol/registry, analytical trot baseline adapter, future-controller placeholders, and bridge abstraction alignment — completed 2026-04-30
- [x] **Phase 3: locomotion-metrics-instrumentation** - Command tracking, stability, action-quality, and terrain/contact metrics collected from simulation state — completed 2026-04-30
- [x] **Phase 4: evaluation-runner-and-regression** - CLI scenario/seed matrix runner, JSONL/CSV/summary exports, reproducibility metadata, and analytical-baseline regression test — completed 2026-05-01
- [x] **Phase 5: harness-docs-and-comparison-matrix** - Harness guide, observation/action/reward/metric documentation, controller-family support matrix, and research rationale link — completed 2026-05-01
- [x] **Phase 6: repair-evaluation-runner-semantics** - Gap closure for scenario command selection, real distance export flattening, and baseline regression threshold semantics — completed 2026-05-01
- [x] **Phase 7: align-evaluation-action-mode-contract** - Gap closure for CLI action-mode support/rejection behavior and reproducible action-mode metadata — completed 2026-05-02
- [ ] **Phase 8: locomotion-controller-seam-cleanup** - Cleanup for multi-robot controller seam consistency and future-controller action-mode metadata — planned
- [ ] **Phase 9: milestone-closeout-hygiene** - Cleanup for validation metadata and pre-close artifact audit items before formal v4.0 archive — planned

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
**Plans**: 5 plans
Plans:

**Wave 1**
- [x] 01-01-PLAN.md — Add Gymnasium dependency, `ArgusGo2Env` contract, observation helpers, and LOC-ENV-01 tests.

**Wave 2 *(blocked on Wave 1 completion)***
- [x] 01-02-PLAN.md — Add named scenario catalog and deterministic reset metadata for LOC-ENV-02/03.
- [x] 01-03-PLAN.md — Add action-mode spaces and safe decoding helpers for LOC-ENV-04.

**Wave 3 *(blocked on Wave 2 completion)***
- [x] 01-04-PLAN.md — Wire scenario/action helpers into the environment API.

**Wave 4 *(blocked on Wave 3 completion)***
- [x] 01-05-PLAN.md — Add scenario MJCF generation, MuJoCo reset lifecycle, and bridge regression verification.

Cross-cutting constraints:
- Preserve the existing non-Gym simulation/web paths while adding the benchmark wrapper.
- Keep reset/step metadata reproducible: seed, scenario id, sampled parameters, command schedule, disturbance schedule, and action mode.
- Validate actions/scenario inputs before mutating MuJoCo state.

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
**Plans**: 6 plans
Plans:

**Wave 1**
- [x] 02-01-PLAN.md — Add locomotion controller protocol, registry, analytical baseline adapter, unavailable future-controller placeholders, and Wave 0 protocol/registry tests.

**Wave 2 *(blocked on Wave 1 completion)***
- [x] 02-02-PLAN.md — Add shared controller dispatch and validated control-target application helpers with fake-data tests.

**Wave 3 *(blocked on Wave 2 completion)***
- [x] 02-03-PLAN.md — Wire `ArgusGo2Env` to registered controller selection and reset/step metadata attribution.
- [x] 02-04-PLAN.md — Refactor `MuJoCoBridge` internals to use the registered analytical controller seam while preserving `SensorFrame` returns.
- [x] 02-05-PLAN.md — Refactor `MultiRobotBridge` internals to use per-robot registered analytical controllers while preserving `dict[str, SensorFrame]` returns.

**Wave 4 *(blocked on Wave 3 completion)***
- [x] 02-06-PLAN.md — Run final Phase 2 test hardening and cross-plan coverage assertions for decisions, requirements, threats, and deferred boundaries.

Cross-cutting constraints:
- Implement all locked decisions D-01 through D-15 from `02-CONTEXT.md` exactly; do not implement deferred RL/direct/MPC/WBC/ROS/hardware/frontend selection work.
- Validate controller ids and controller outputs before any MuJoCo `data.ctrl` mutation.
- Preserve existing bridge public lifecycles and return contracts.
- Emit controller metadata sufficient for downstream metrics/evaluation attribution.

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
**Plans**: 5 plans
Plans:

**Wave 1**
- [x] 03-01-PLAN.md — Add core locomotion metrics collector for command tracking, stability, and action-quality metrics.

**Wave 2 *(blocked on Wave 1 completion)***
- [x] 03-02-PLAN.md — Add strict Go2 foot mapping and contact/terrain proxy metrics.

**Wave 3 *(blocked on Wave 2 completion)***
- [x] 03-03-PLAN.md — Wire metrics collector into `ArgusGo2Env` reset/step, nested info payloads, and failure termination.

**Wave 4 *(blocked on Wave 3 completion)***
- [x] 03-04-PLAN.md — Harden Phase 3 validation coverage and run Nyquist quick/full checks.

**Wave 5 *(gap closure; blocked on Wave 4 completion)***
- [x] 03-05-PLAN.md — Gate progress-stall termination on non-trivial desired translational commands and add zero-command standing regressions.

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
**Plans**: 4 plans
Plans:

**Wave 1**
- [x] 04-01-PLAN.md — Add evaluation matrix contracts, fail-fast validation, and fake-env runner loop.

**Wave 2 *(blocked on Wave 1 completion)***
- [x] 04-02-PLAN.md — Add JSONL/CSV/manifest/summary/Markdown exports and offline comparison regeneration.

**Wave 3 *(blocked on Wave 2 completion)***
- [x] 04-03-PLAN.md — Wire `argus eval-locomotion` CLI subcommand and saved-run regeneration mode.

**Wave 4 *(blocked on Wave 3 completion)***
- [x] 04-04-PLAN.md — Add analytical flat-ground fixed-seed baseline regression gate.

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
**Plans**: 2 plans
Plans:

**Wave 1**
- [x] 05-01-PLAN.md — Create the canonical harness guide, README command card, hard-boundary controller-family matrix, and Markdown content guards.

**Wave 2 *(gap closure; blocked on Wave 1 completion)***
- [x] 05-02-PLAN.md — Align residual-policy placeholder action-mode metadata with the documented residual_baseline seam and add drift guards.

**Research flag**: light

### Phase 6: repair-evaluation-runner-semantics
**Goal**: Close milestone audit gaps in real evaluation semantics so scenario command schedules, exported distance metrics, and analytical baseline thresholds measure actual locomotion behavior.
**Depends on**: Phase 5
**Requirements**: LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04
**Gap Closure:** Closes command-schedule, distance-export, and baseline-regression gaps from `.planning/v4.0-MILESTONE-AUDIT.md`.
**Success Criteria** (what must be TRUE):
  1. Evaluation selects the command active at the current simulation time/current command instead of always using the first scenario command.
  2. `ArgusGo2Env` and/or evaluation info exposes enough current-command state for actions and exported command fields to match the running scenario.
  3. Real evaluation artifacts read `distance_xy_m` from the stability episode summary and preserve nonzero distance in CSV, summary, comparison, and threshold paths.
  4. Regression coverage proves nonzero scheduled commands drive real/fake evaluation actions and baseline checks cannot pass as stationary standing tests.
**Plans**: 3 plans
Plans:

**Wave 1**
- [x] 06-01-PLAN.md — Emit and consume active `current_command` for evaluation actions and command export fields.

**Wave 2 *(blocked on Wave 1 completion)***
- [x] 06-02-PLAN.md — Flatten `distance_xy_m` from stability summaries and preserve it through artifacts and comparison output.

**Wave 3 *(blocked on Wave 2 completion)***
- [x] 06-03-PLAN.md — Add stationary-controller baseline rejection and update Phase 6 Nyquist validation evidence.

**Research flag**: standard

### Phase 7: align-evaluation-action-mode-contract
**Goal**: Close milestone audit gaps in CLI action-mode behavior so evaluation either emits valid actions for each supported mode or rejects unsupported modes before misleading runs/artifacts are produced.
**Depends on**: Phase 6
**Requirements**: LOC-ENV-04, LOC-EVAL-03
**Gap Closure:** Closes CLI action-mode contract and metadata gaps from `.planning/v4.0-MILESTONE-AUDIT.md`.
**Success Criteria** (what must be TRUE):
  1. The evaluation runner contract for non-default action modes is explicit and enforced before environment stepping.
  2. `velocity_command`, `joint_position`, and `residual_baseline` CLI paths either generate actions matching their env action spaces or fail fast with actionable errors.
  3. Exported metadata records only action modes that were actually used for completed runs.
  4. CLI help/docs match the implemented evaluation action-mode contract.
**Plans**: 3 plans
Plans:

**Wave 1**
- [x] 07-01-PLAN.md — Add test-first evaluator action-mode validation, unsupported-mode rejection before side effects, and completed-run metadata guards.
- [x] 07-02-PLAN.md — Update eval-locomotion help and benchmark docs to distinguish evaluator-runnable modes from env-supported seams.

**Wave 2 *(gap closure; blocked on Wave 1 completion)***
- [x] 07-03-PLAN.md — Preserve matrix-config scalar values unless CLI overrides are explicit, add CLI no-artifact regressions, and clean action-mode docs markup.

**Research flag**: light

### Phase 8: locomotion-controller-seam-cleanup
**Goal**: Resolve the v4.0 audit tech debt around multi-robot controller seam consistency and future-controller action-mode metadata.
**Depends on**: Phase 7
**Requirements**: LOC-CTRL-04, LOC-CTRL-03, LOC-REPORT-02
**Gap Closure:** Closes tech-debt items from `.planning/v4.0-MILESTONE-AUDIT.md` for multi-robot controller abstraction and WBC placeholder metadata.
**Success Criteria** (what must be TRUE):
  1. MultiRobotBridge either uses the shared controller registry/dispatch seam equivalently to the single bridge or documents/tests a deliberate platform-runtime boundary.
  2. Controller output validation and indexed control application remain covered for multi-robot bridge behavior.
  3. WBC placeholder capability metadata no longer implies a runnable v4.0 env action mode that does not exist, or docs explicitly mark the future action contract as undefined/deferred.
  4. Controller-family docs and registry tests agree on placeholder action-mode vocabulary.
**Plans**: 2 plans
Plans:

**Wave 1**
- [x] 08-01-PLAN.md — Make the multi-robot platform-runtime boundary explicit and replace direct indexed control writes with shared pre-mutation validation.
- [x] 08-02-PLAN.md — Replace misleading WBC placeholder action-mode vocabulary with explicit deferred contract metadata and docs guards.

**Research flag**: light

### Phase 9: milestone-closeout-hygiene
**Goal**: Clean up milestone governance metadata and open pre-close artifacts so `/gsd-complete-milestone` can run without acknowledged deferred items.
**Depends on**: Phase 8
**Requirements**: LOC-ENV-01, LOC-CTRL-01, LOC-METRICS-01, LOC-EVAL-01
**Gap Closure:** Closes v4.0 audit validation/Nyquist metadata debt and the open artifact audit items blocking milestone closeout.
**Success Criteria** (what must be TRUE):
  1. Phase 1, 2, 3, and 6 validation files accurately reflect current verification status, Wave 0 state, and Nyquist compliance.
  2. Open debug sessions `point-cloud-below-ground`, `point-cloud-rotation`, and `voxel-becomes-pointcloud-closeup` are resolved, closed, or explicitly moved out of the v4.0 closeout path.
  3. Incomplete quick-task artifact records are repaired, closed, or explicitly moved out of the v4.0 closeout path.
  4. `gsd-sdk query audit-open` returns no open items that block milestone closure.
**Plans**: 0 plans
Plans:

- [ ] Plan with `/gsd-plan-phase 9`.

**Research flag**: light

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. locomotion-env-contract | 5/5 | Complete | 2026-04-30 |
| 2. controller-plugin-baseline | 6/6 | Complete | 2026-04-30 |
| 3. locomotion-metrics-instrumentation | 5/5 | Complete | 2026-04-30 |
| 4. evaluation-runner-and-regression | 4/4 | Complete | 2026-05-01 |
| 5. harness-docs-and-comparison-matrix | 2/2 | Complete | 2026-05-01 |
| 6. repair-evaluation-runner-semantics | 5/5 | Complete | 2026-05-01 |
| 7. align-evaluation-action-mode-contract | 3/3 | Complete | 2026-05-02 |
| 8. locomotion-controller-seam-cleanup | 0/2 | Planned | - |
| 9. milestone-closeout-hygiene | 0/0 | Planned | - |

## Requirement Coverage

| Phase | Requirements |
|-------|--------------|
| Phase 1 | LOC-ENV-01, LOC-ENV-02, LOC-ENV-03 |
| Phase 2 | LOC-CTRL-01, LOC-CTRL-02, LOC-CTRL-03, LOC-CTRL-04 |
| Phase 3 | LOC-METRICS-01, LOC-METRICS-02, LOC-METRICS-03, LOC-METRICS-04 |
| Phase 4 | — superseded by gap closure phases for LOC-METRICS-05 and LOC-EVAL-01..04 |
| Phase 5 | LOC-REPORT-01, LOC-REPORT-02, LOC-REPORT-03 |
| Phase 6 | LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04 |
| Phase 7 | LOC-ENV-04, LOC-EVAL-03 |
| Phase 8 | LOC-CTRL-04, LOC-CTRL-03, LOC-REPORT-02 |
| Phase 9 | LOC-ENV-01, LOC-CTRL-01, LOC-METRICS-01, LOC-EVAL-01 |

**Coverage:** 20/20 active requirements mapped ✓
**Orphans:** none
**Duplicates:** cleanup phases intentionally reference already satisfied requirements to close audit tech debt.

## Next Step

Run `/gsd-execute-phase 8` to execute the controller seam cleanup phase before formal v4.0 closure.
