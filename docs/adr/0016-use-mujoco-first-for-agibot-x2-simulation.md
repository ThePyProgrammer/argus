# ADR-0016: Use MuJoCo First for AGIBOT X2 Simulation

| Field | Value |
|-------|-------|
| Status | Proposed |
| Date | 2026-04-30 |
| Category | Technology Choice |
| Deciders | Project maintainers |
| Consulted | AGIBOT X2 simulation adaptation design, AGIBOT X2 research report |
| Informed | Future Argus simulation contributors |
| Supersedes | None |
| Superseded by | None |
| Related | ADR-0002, ADR-0003, ADR-0012, ADR-0015 |

## Context

The first AGIBOT X2 milestone is simulation-only: spawn 2-5 X2 robots, run physics-based walking, and let Argus coordinate them through high-level velocity or waypoint commands. Real hardware, AimDK_X2, PC2 deployment, and Isaac Lab as the primary runtime are out of scope.

Argus already uses MuJoCo as the simulation boundary. The existing architecture depends on MuJoCo for robot state, rendering, ground-truth metrics, and local coordination. Public X2 assets found during research include MuJoCo XML/MJCF-like models in third-party repositories, while official AGIBOT simulation tooling is stronger around Genie Sim / Isaac workflows for G1/G2 rather than an official public X2 simulation stack.

The key force is not simulator ideology. The key force is getting a credible X2 swarm demo without rebuilding the runtime under our feet.

## Options Considered

1. **MuJoCo first** — reuse Argus's existing simulation boundary and load X2 through MJCF/XML assets.
2. **Isaac Lab first** — shift the first X2 milestone to Isaac Lab for humanoid/RL throughput and USD-native assets.
3. **Dual simulator first** — support MuJoCo and Isaac Lab from day one.
4. **Status quo / do nothing** — keep Argus Go2-only and defer X2.

## Decision

**In the context of** building the first AGIBOT X2 simulation-only swarm milestone, **facing** existing MuJoCo-centred Argus infrastructure and uncertain public X2 asset maturity, **we decided for** MuJoCo first **to achieve** the shortest credible path to physics-walking X2 swarm simulation, **accepting** that Isaac Lab integration may still be needed later for large-scale training.

## Rationale

MuJoCo first is the least disruptive path. Argus already has MuJoCo stepping, rendering, state extraction, and ground-truth metrics. ADR-0002 already put the project on this road. Do not change roads while also changing robot morphology, locomotion, and swarm behaviour. That is how you turn a milestone into a bonfire.

Isaac Lab is attractive for high-throughput RL and USD-native humanoid workflows. It is not the right first integration boundary because it would require a larger runtime redesign before proving X2 can work inside Argus at all.

Dual simulator support is the long-term grown-up answer, but doing it first is premature. First make one X2 walk under Argus orchestration. Then earn the second simulator.

## Consequences

### Positive

- Reuses Argus's accepted MuJoCo simulation boundary.
- Reduces first-milestone integration risk.
- Keeps existing ground-truth metric and browser streaming assumptions intact.
- Aligns with available public X2 MJCF/XML-style assets.
- Allows Go2 regression testing in the same runtime.

### Negative

- MuJoCo may be less convenient than Isaac Lab for large-scale humanoid RL training.
- Public X2 MuJoCo assets still require audit for physics fidelity, actuator mapping, and licensing.
- If the only usable X2 walking policy exists in Isaac Lab, policy transfer or a later simulator decision may be required.

### Neutral / Follow-up

- Isaac Lab remains a future option for training or high-throughput evaluation.
- The robot platform abstraction from ADR-0015 should avoid baking in assumptions that make a later Isaac adapter impossible.
- This ADR does not choose a specific X2 asset repository as canonical.

## References

- ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary
- ADR-0003: Use Ground-Truth World Poses to Remove Map Alignment as a Variable
- ADR-0012: Forbid Fake mAP and Use MuJoCo Ground-Truth Metrics
- ADR-0015: Introduce Robot Platform Abstraction
- `docs/superpowers/specs/2026-04-30-agibot-x2-adaptation-design.md`
- `outputs/agibot-x2-swarm.md`
