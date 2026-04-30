# ADR-0018: Use Reproducible Gymnasium-Style Locomotion Benchmark Harness

| Field | Value |
|-------|-------|
| Status | Proposed |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/research/SUMMARY.md`, `outputs/locomotion-rd-systems.md` |
| Informed | Simulation, locomotion, controller, metrics, and evaluation contributors |
| Supersedes | None |
| Superseded by | None |
| Related | ADR-0002, ADR-0003, ADR-0006, ADR-0012, ADR-0019 |

## Context

Argus already has a working Go2 locomotion path: high-level velocity commands feed an analytical Raibert-style trot controller, which outputs 12 Unitree Go2 joint-position targets tracked by MuJoCo position actuators. That is useful. It is not yet a benchmark.

The v4.0 planning work makes locomotion comparison a first-class goal. Future controller families — residual policies, direct policies, MPC, WBC, and hardware-oriented adapters — need a shared boundary for reset, step, action shape, observation, metrics, and reproducibility. Without that boundary, every controller comparison becomes a bespoke script with just enough differences to make the numbers untrustworthy. That is how benchmarks rot.

The approved v4.0 roadmap requires:

- a Gymnasium-style `ArgusGo2Env` with `reset(seed=...)` and `step(action)` semantics;
- named scenarios including `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance`;
- deterministic seeded resets for spawn pose, terrain parameters, command schedule, and disturbances;
- action modes for velocity command, joint-position target, and residual-over-baseline control;
- a locomotion controller protocol/registry with analytical trot as the default baseline;
- machine-readable JSONL/CSV/summary exports and reproducibility metadata;
- a baseline regression test for the analytical trot.

## Options Considered

1. **Reproducible Gymnasium-style benchmark harness** — wrap the existing MuJoCo/Go2 locomotion path in `ArgusGo2Env`, expose scenario and seed control, route controllers through a protocol/registry seam, and export benchmark artifacts.
2. **Custom Argus-only evaluator API** — create project-specific reset/run/evaluate functions without following the Gymnasium environment contract.
3. **Controller-specific benchmark scripts** — let each controller family own its own runner, metrics, and export format.
4. **Visual demo only / status quo** — keep the current simulation path and judge locomotion quality by watching the browser or ad hoc logs.

## Decision

**In the context of** a MuJoCo-first robot simulation platform that needs comparable locomotion results, **facing** existing analytical Go2 locomotion with no stable benchmark boundary, **we decided for** a reproducible Gymnasium-style locomotion benchmark harness with named scenarios, deterministic seeds, controller protocol/registry seams, and machine-readable exports **to achieve** repeatable controller evaluation and future learning compatibility, **accepting** the extra discipline required to make reset determinism, action modes, and metrics stable contracts.

## Rationale

Gymnasium-style `reset` and `step` semantics are the least surprising boundary for locomotion evaluation and future learning workflows. Reinforcement learning libraries already understand this shape, regression tests can exercise the same API, and controller comparison can use one runner instead of a drawer full of snowflake scripts.

The controller protocol/registry belongs in this ADR because it is part of the benchmark boundary. Controllers are what the harness compares. Splitting the controller seam into a separate ADR right now would create paperwork, not clarity. ADR-0006 already records the general protocol/registry pattern; this ADR applies that habit to locomotion without pretending the pattern is new.

The scenario, seed, export, and metadata requirements are not garnish. They are the difference between a benchmark and a nice video. Same seed should mean same spawn pose, terrain parameters, command schedule, and disturbance timing. If that is not true, the result is not reproducible; it is a physics-flavored anecdote.

## Consequences

### Positive

- Evaluation, regression tests, and future learning workflows share one environment API.
- Controller families can be compared through one controller/action seam instead of bespoke runners.
- The analytical trot becomes a registered deterministic baseline rather than hidden bridge behavior.
- Scenario and seed metadata make benchmark runs reproducible and reviewable.
- JSONL/CSV/summary exports allow offline aggregate comparison without rerunning simulation.

### Negative

- Reset determinism is now an architectural contract, not a best-effort convenience.
- The environment API can ossify too early if observation and action shapes are designed lazily.
- Controller registry imports must stay lightweight; loading future ML policies just to list controllers would repeat old dependency mistakes.
- Multi-robot and single-robot bridge paths may need refactoring before they share the controller/action seam cleanly.

### Neutral / Follow-up

- Initial support is simulation-only and Go2-focused.
- RL training, MPC, WBC, ROS 2, and hardware adapters remain separate future decisions.
- Metrics should be available per step and per episode, but final metric definitions can evolve during implementation.
- The frontend does not need a benchmark visualization overhaul for this ADR to hold.

## References

- ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary
- ADR-0003: Use Ground-Truth World Poses to Remove Map Alignment as a Variable
- ADR-0006: Use Protocol and Registry Pattern for Pluggable Backends
- ADR-0012: Forbid Fake mAP and Use MuJoCo Ground-Truth Metrics
- `.planning/PROJECT.md` — v4.0 active requirements, constraints, and key decisions
- `.planning/ROADMAP.md` — Phase 1, Phase 2, Phase 3, and Phase 4 scope
- `.planning/REQUIREMENTS.md` — LOC-ENV, LOC-CTRL, LOC-METRICS, and LOC-EVAL requirements
- `.planning/research/SUMMARY.md` — research-derived v4 scope
- `outputs/locomotion-rd-systems.md` — locomotion control and tooling research basis
