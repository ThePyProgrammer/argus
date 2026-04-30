# ADR-0019: Benchmark Locomotion Before Adding New Controller Families

| Field | Value |
|-------|-------|
| Status | Proposed |
| Date | 2026-04-30 |
| Category | Process / Workflow |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/research/SUMMARY.md`, `outputs/locomotion-rd-systems.md` |
| Informed | Simulation, locomotion, controller, metrics, evaluation, and future robot-platform contributors |
| Supersedes | None |
| Superseded by | None |
| Related | ADR-0002, ADR-0012, ADR-0017, ADR-0018 |

## Context

Argus currently has analytical Go2 locomotion, not a research-grade controller comparison stack. The existing path maps velocity commands to a deterministic trot and relies on MuJoCo position actuators. It is inspectable, integrated, and good enough to serve as a baseline.

The tempting move is to jump straight to something more impressive: residual RL, direct RL, MPC, WBC, ROS 2, or hardware-style adapters. That would be premature. The locomotion research summary is explicit: Argus is not currently an MPC, WBC, trajectory optimization, reinforcement learning, imitation learning, torque-control, ROS 2 deployment, or contact-aware locomotion planning system.

Controller claims need repeatable scenarios, deterministic seeds, command tracking, stability metrics, action-quality metrics, contact/terrain proxies, machine-readable exports, and a baseline regression test. Without those, adding a new controller family only creates a new way to fool ourselves. The universe has enough demos that walk once on flat ground and then pretend to be science.

## Options Considered

1. **Benchmark before controller sophistication** — build the harness, scenarios, metrics, controller seams, exports, and regression tests before adding RL/MPC/WBC/hardware-oriented controllers.
2. **Implement residual or direct RL immediately** — train or integrate learned policies before the evaluation harness exists.
3. **Implement MPC/WBC immediately** — add model-based control before the project has the required contact, state, torque-control, and dynamics infrastructure.
4. **Keep manually tuning the analytical trot** — improve the existing baseline without making comparisons reproducible.
5. **Status quo / do nothing** — leave locomotion as a working demo with no benchmark discipline.

## Decision

**In the context of** an Argus locomotion stack that has a working analytical Go2 baseline but no reproducible comparison harness, **facing** pressure to add more sophisticated controller families, **we decided to** benchmark locomotion before adding new controller families **to achieve** honest, scenario/seed/metric-backed controller comparisons, **accepting** slower visible progress on RL, MPC, WBC, ROS, and hardware-oriented control.

## Rationale

The analytical trot is valuable because it is deterministic, inspectable, and already wired into the simulator. That makes it a good comparator. Replacing it or burying it under a half-built learned/model-based controller before the benchmark exists would destroy the control condition.

Advanced locomotion work needs infrastructure Argus does not yet have. RL needs environment contracts, observations, rewards, resets, action modes, and run metadata. MPC and WBC need reliable state, contact, actuator assumptions, dynamics, and failure reporting. ROS/hardware needs a separate deployment architecture and safety boundary. Pretending those are just implementation details is how projects get a pile of impressive acronyms and no trustworthy results.

The right order is boring and correct: make the current baseline measurable, then compare new controllers against it. Architecture is often just refusing to skip the step that prevents future nonsense.

## Consequences

### Positive

- Future controller improvements must clear a repeatable baseline instead of winning a visual demo.
- The existing analytical trot remains a useful deterministic comparator.
- RL, MPC, WBC, ROS, and hardware work get clearer entry criteria.
- Evaluation and regression infrastructure becomes available before controller complexity increases.
- Scope stays aligned with the CPU-first MuJoCo simulation boundary.

### Negative

- v4.0 will not ship a new learned, MPC, WBC, ROS, or hardware controller.
- Some users may perceive the milestone as infrastructure-heavy because it deliberately prioritizes measurement over novelty.
- The team must maintain discipline when future controller work tries to sneak in before the harness is ready.

### Neutral / Follow-up

- Residual RL over the analytical trot baseline remains a plausible future milestone.
- Direct proprioceptive RL, MPC, WBC, ROS 2, hardware deployment, and perception-conditioned locomotion should each get their own scope and ADR treatment when they become active.
- ADR-0018 defines the harness mechanics this decision depends on.
- ADR-0017 remains relevant for external walking-policy boundaries on non-Go2 platforms.

## References

- ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary
- ADR-0012: Forbid Fake mAP and Use MuJoCo Ground-Truth Metrics
- ADR-0017: Treat X2 Locomotion as External Walking Policy Boundary
- ADR-0018: Use Reproducible Gymnasium-Style Locomotion Benchmark Harness
- `.planning/PROJECT.md` — v4.0 scope, out-of-scope items, and key decisions
- `.planning/ROADMAP.md` — v4.0 roadmap overview and phase ordering
- `.planning/REQUIREMENTS.md` — Future Requirements and Out of Scope sections
- `.planning/research/SUMMARY.md` — research findings and deferred implementation branches
- `outputs/locomotion-rd-systems.md` — locomotion control and tooling research basis
