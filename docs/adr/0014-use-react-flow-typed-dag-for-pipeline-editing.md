# ADR-0014: Use React Flow Typed DAG for Pipeline Editing

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/research/FEATURES.md`, `frontend/package.json`, `README.md` |
| Informed | Frontend and pipeline contributors |
| Supersedes | Hardcoded perception/SLAM pipeline wiring as the only configuration surface |
| Superseded by |  |
| Related | ADR-0005, ADR-0006, ADR-0007 |

## Context

Argus exposes backend and perception composition as part of the research workflow. v2.0 introduced a React Flow pipeline editor with typed ports and validation. v3.0 extends that editor with detector, 3D lifter, tracker, and semantic-map concepts. Planning explicitly calls out typed `Detections2D` and `Detections3D` ports and per-edge validation.

## Options Considered

1. **React Flow typed DAG editor** — visual graph of nodes, ports, presets, validation, and backend-backed schemas.
2. **Static config files** — easier to version but less discoverable and less interactive.
3. **Backend-only imperative wiring** — keep all pipeline composition in Python.
4. **Status quo / do nothing** — expose only top-level controls and hardcoded runtime pipeline behavior.

## Decision

**In the context of** a browser-first research platform for pluggable perception and SLAM, **facing** the need to inspect and configure multi-stage pipelines, **we decided for** a React Flow typed DAG editor **to achieve** interactive composition and validation, **accepting** cross-language schema discipline between backend node definitions and frontend types.

## Rationale

Pipeline structure is part of the user-facing research surface. A typed DAG makes invalid connections visible before runtime and gives users an understandable representation of detector, lifter, tracker, map, and visualization stages.

## Consequences

### Positive

- Users can understand and configure pipeline composition visually.
- Typed ports prevent obvious class-of-data mistakes.
- Built-in presets can encode recommended pipelines while allowing controlled edits.

### Negative

- Frontend and backend node schemas must stay synchronized.
- Graph validation and serializer compatibility become core correctness concerns.

### Neutral / Follow-up

- Pipeline hot-apply should respect backend lifecycle constraints; not every change can be live.
- Perception node schemas should be driven from registries where possible.

## References

- `.planning/PROJECT.md` — React Flow for pipeline editor decision
- `.planning/REQUIREMENTS.md` — DET-PIPELINE requirements
- `.planning/research/FEATURES.md` — Pipeline editor table stakes and dependency ordering
- `frontend/package.json` — `@xyflow/react` dependency
- `README.md` — Pipeline Editor section
