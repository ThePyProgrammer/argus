# ADR-0003: Use Ground-Truth World Poses to Remove Map Alignment as a Variable

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `README.md`, `.planning/PROJECT.md` |
| Informed | SLAM, exploration, and metrics contributors |
| Supersedes |  |
| Superseded by |  |
| Related | ADR-0002, ADR-0005, ADR-0013 |

## Context

Multi-robot mapping normally requires inter-robot loop closure, distributed pose graph optimization, and careful map alignment. Argus is explicitly simulation-first: MuJoCo exposes exact robot and camera poses. The README states that Argus uses ground-truth poses as a controlled variable so the project can focus on coordination, streaming, pluggability, and visualization rather than map registration.

## Options Considered

1. **Use MuJoCo ground-truth world poses** — seed or transform outputs into a shared world frame using simulation truth.
2. **Estimate all poses through SLAM only** — force every map merge to solve localization and alignment.
3. **Hybrid mode** — use ground truth for some components and estimated poses for others.
4. **Status quo / do nothing** — leave pose-source assumptions implicit.

## Decision

**In the context of** a simulation research platform for multi-robot perception orchestration, **facing** the complexity of map alignment and drift, **we decided for** using MuJoCo ground-truth world poses as the shared frame basis **to achieve** deterministic map fusion and reproducible evaluation, **accepting** that real localization robustness is not tested by default.

## Rationale

Ground-truth poses turn map fusion into a systems integration problem rather than a localization research problem. This makes other variables measurable: exploration strategy, backend behavior, detection latency, visualization bandwidth, and pipeline composition.

## Consequences

### Positive

- Multi-robot maps can be fused in a common world frame without solving inter-robot localization first.
- Detection metrics can compare 3D outputs against MuJoCo body positions.
- Coordinate-frame bugs become easier to isolate because a known world reference exists.

### Negative

- The baseline can overstate real-world readiness.
- Algorithms that depend on realistic localization uncertainty require separate validation.

### Neutral / Follow-up

- Future hardware or noisy-simulation work should introduce explicit pose-source modes.
- Metrics and docs should avoid implying that ground-truth-aided performance equals deployment performance.

## References

- `README.md` — When Robots Are Cheap, Coordination Is Everything
- `README.md` — On Ground Truth as a Research Accelerant
- `.planning/PROJECT.md` — Core value and constraints
