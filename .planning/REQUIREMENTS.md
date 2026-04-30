# Requirements: v4.0 Benchmarkable Locomotion Environment

**Defined:** 2026-04-30
**Core Value:** Turn Argus locomotion from a hard-coded analytical gait demo into a repeatable benchmark harness where controller families can be compared across scenarios, seeds, and metrics.

---

## v4.0 Requirements

Each requirement maps to exactly one roadmap phase.

### LOC-ENV — Benchmark Environment Contract

- [x] **LOC-ENV-01**: Developer can run a Gymnasium-style `ArgusGo2Env` wrapper with `reset(seed=...)` and `step(action)` returning observation, reward, terminated, truncated, and info. Validated in Phase 1.
- [x] **LOC-ENV-02**: Developer can choose at least flat-ground, low-friction, slope, rough-heightfield, and push-disturbance scenarios from a named scenario catalog. Validated in Phase 1.
- [x] **LOC-ENV-03**: Developer can run deterministic seeded resets that reproduce robot spawn pose, terrain parameters, command schedule, and disturbance timing. Validated in Phase 1.
- [x] **LOC-ENV-04**: Developer can select action modes for velocity command, joint-position target, and residual-over-baseline control without changing the environment API. Validated in Phase 1.

### LOC-CTRL — Controller Comparison Seam

- [ ] **LOC-CTRL-01**: Developer can register locomotion controllers behind a common protocol that maps environment observation plus command into actuator/action output.
- [ ] **LOC-CTRL-02**: Existing analytical trot controller is exposed as the default baseline controller through the same protocol.
- [ ] **LOC-CTRL-03**: Developer can add placeholder adapters for residual policy, direct policy, and future MPC/WBC controllers without modifying the MuJoCo bridge internals.
- [ ] **LOC-CTRL-04**: Multi-robot and single-robot bridges share the same controller/action abstraction where practical, so comparison logic is not duplicated.

### LOC-METRICS — Locomotion Metrics

- [ ] **LOC-METRICS-01**: Evaluation captures command tracking error for forward velocity, lateral velocity, and yaw rate.
- [ ] **LOC-METRICS-02**: Evaluation captures stability metrics: fall rate, roll/pitch bounds, base height deviation, and distance before failure.
- [ ] **LOC-METRICS-03**: Evaluation captures control-quality metrics: action smoothness, joint-limit violations, energy/effort proxy, and actuator saturation.
- [ ] **LOC-METRICS-04**: Evaluation captures terrain/contact proxies: foot slip, foot clearance, contact timing/duty factor, and scenario success rate.
- [ ] **LOC-METRICS-05**: Metrics are exported as JSONL/CSV plus a machine-readable summary suitable for comparing controllers across seeds.

### LOC-EVAL — Repeatable Evaluation Runner

- [ ] **LOC-EVAL-01**: Developer can run a CLI evaluation command that executes a controller across a scenario matrix and fixed seed list.
- [ ] **LOC-EVAL-02**: Evaluation produces an aggregate comparison table with per-controller mean, standard deviation, and failure counts.
- [ ] **LOC-EVAL-03**: Evaluation stores enough metadata to reproduce a run: git commit, controller id, scenario id, seed, environment config, and action mode.
- [ ] **LOC-EVAL-04**: Evaluation includes regression tests that prevent the analytical trot baseline from silently degrading on the flat-ground smoke scenario.

### LOC-REPORT — Research Harness Documentation

- [ ] **LOC-REPORT-01**: Developer can read a concise harness guide explaining observation space, action modes, reward/metric definitions, and scenario catalog.
- [ ] **LOC-REPORT-02**: Developer can see an explicit comparison matrix explaining which controller families are supported now versus intentionally deferred.
- [ ] **LOC-REPORT-03**: Developer can use the final report from `outputs/locomotion-rd-systems.md` as the rationale link for milestone scope.

---

## Future Requirements (v5.0+)

- **LOC-RL-01**: Train a residual RL policy over the analytical trot baseline.
- **LOC-RL-02**: Train a direct proprioceptive RL policy producing PD joint targets.
- **LOC-MPC-01**: Add centroidal/convex MPC stance-force planning.
- **LOC-WBC-01**: Add whole-body control or inverse-dynamics QP layer.
- **LOC-ROS-01**: Add ROS 2 / ros2_control hardware-style deployment interface.
- **LOC-PERCEPT-01**: Add perception-conditioned locomotion over stairs/gaps/obstacles.

---

## Out of Scope

- **Training RL policies** — v4.0 builds the evaluation harness and action/controller seams first.
- **Implementing MPC/WBC** — current stack lacks the dynamics/contact/torque-control infrastructure for a safe implementation in this milestone.
- **Hardware deployment** — simulation-only until benchmark results justify a ROS/hardware architecture milestone.
- **Replacing the analytical trot** — it stays as the deterministic baseline comparator.
- **Frontend visualization overhaul** — CLI artifacts and documentation are sufficient for the benchmark milestone.

---

## Traceability

Each requirement maps to exactly one phase.

| Requirement | Phase |
|-------------|-------|
| LOC-ENV-01 | Phase 1 (locomotion-env-contract) |
| LOC-ENV-02 | Phase 1 (locomotion-env-contract) |
| LOC-ENV-03 | Phase 1 (locomotion-env-contract) |
| LOC-ENV-04 | Phase 1 (locomotion-env-contract) |
| LOC-CTRL-01 | Phase 2 (controller-plugin-baseline) |
| LOC-CTRL-02 | Phase 2 (controller-plugin-baseline) |
| LOC-CTRL-03 | Phase 2 (controller-plugin-baseline) |
| LOC-CTRL-04 | Phase 2 (controller-plugin-baseline) |
| LOC-METRICS-01 | Phase 3 (locomotion-metrics-instrumentation) |
| LOC-METRICS-02 | Phase 3 (locomotion-metrics-instrumentation) |
| LOC-METRICS-03 | Phase 3 (locomotion-metrics-instrumentation) |
| LOC-METRICS-04 | Phase 3 (locomotion-metrics-instrumentation) |
| LOC-METRICS-05 | Phase 4 (evaluation-runner-and-regression) |
| LOC-EVAL-01 | Phase 4 (evaluation-runner-and-regression) |
| LOC-EVAL-02 | Phase 4 (evaluation-runner-and-regression) |
| LOC-EVAL-03 | Phase 4 (evaluation-runner-and-regression) |
| LOC-EVAL-04 | Phase 4 (evaluation-runner-and-regression) |
| LOC-REPORT-01 | Phase 5 (harness-docs-and-comparison-matrix) |
| LOC-REPORT-02 | Phase 5 (harness-docs-and-comparison-matrix) |
| LOC-REPORT-03 | Phase 5 (harness-docs-and-comparison-matrix) |

**Coverage:** 20/20 active requirements mapped ✓
**Orphans:** none
**Duplicates:** none

---

*Defined: 2026-04-30 — pre-roadmap*
*Traceability filled: 2026-04-30 — 5 phases, 100% coverage*
