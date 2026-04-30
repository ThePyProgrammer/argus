# ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Technology Choice |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `README.md` |
| Informed | Robotics, perception, and frontend contributors |
| Supersedes |  |
| Superseded by |  |
| Related | ADR-0003, ADR-0004, ADR-0011 |

## Context

Argus is a simulation-first multi-robot perception system. The project explicitly excludes physical deployment and GPU-dependent backends in the current scope. Earlier planning records identify MuJoCo as the replacement for SimWorld because the available environment is CPU-only and MuJoCo provides metric depth, deterministic physics, and ground-truth poses.

## Options Considered

1. **MuJoCo CPU simulation** — use MuJoCo scenes, cameras, depth, body poses, and physics as the platform boundary.
2. **SimWorld / UE-style simulation** — use richer scenes and rendering at the cost of GPU and integration burden.
3. **Physical robot deployment** — optimize around hardware sensors, drift, networking, and safety constraints now.
4. **Status quo / do nothing** — leave platform assumptions implicit in code and planning docs.

## Decision

**In the context of** a CPU-only research platform focused on multi-robot coordination and perception integration, **facing** the need for deterministic simulation, metric depth, and rapid iteration, **we decided for** MuJoCo CPU simulation as the platform boundary **to achieve** reproducible experiments and accessible local development, **accepting** that real-world deployment concerns are out of scope.

## Rationale

MuJoCo gives Argus the data it needs: RGB, depth, world-frame body/camera poses, and controllable scene state. That supports the project's core research question: orchestrating and comparing multi-robot perception pipelines, not solving every hardware deployment variable at once.

## Consequences

### Positive

- Runs without NVIDIA GPU dependency.
- Provides ground-truth state for evaluation and architecture simplification.
- Keeps iteration speed high for backend, UI, and planning work.

### Negative

- Results do not automatically transfer to physical robots.
- Sensor noise, actuator uncertainty, network failures, and hardware safety remain unmodeled unless explicitly added later.

### Neutral / Follow-up

- GPU-dependent detector and SLAM backends remain future work.
- Real-world deployment should require new ADRs for sensor, localization, transport, and safety assumptions.

## References

- `.planning/PROJECT.md` — Key Decisions: MuJoCo over SimWorld
- `.planning/REQUIREMENTS.md` — Out of Scope: physical deployment, GPU-dependent detectors
- `README.md` — Philosophical Foundations: ground truth as research accelerant
