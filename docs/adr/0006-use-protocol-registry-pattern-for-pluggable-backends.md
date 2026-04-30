# ADR-0006: Use Protocol and Registry Pattern for Pluggable Backends

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/FEATURES.md`, `README.md` |
| Informed | SLAM, perception, pipeline, and UI contributors |
| Supersedes | Hardcoded backend selection paths |
| Superseded by |  |
| Related | ADR-0007, ADR-0008, ADR-0014 |

## Context

Argus is a research platform for comparing algorithms. v2.0 introduced pluggable SLAM backends through runtime-checkable Protocols and registries. v3.0 repeats the pattern for perception: `DetectorProtocol`, `Detection3DProtocol`, and registries with capability and parameter schemas. README and planning docs describe pluggability as a core research methodology, not just a convenience.

## Options Considered

1. **Runtime-checkable Protocol + Registry** — backends implement contracts and register with metadata, capabilities, and parameters.
2. **Factory functions / switch statements** — centralize selection logic in one file.
3. **Configuration-only plugin list** — describe backends in config and trust imports at runtime.
4. **Status quo / do nothing** — keep hardcoded ICP/YOLO-style paths.

## Decision

**In the context of** a system built to compare SLAM, detection, lifting, tracking, and merge strategies, **facing** backend churn and optional dependencies, **we decided for** runtime-checkable Protocols plus registries **to achieve** lazy discovery, contract validation, schema-driven UI, and backend comparison, **accepting** the discipline required to keep contracts small and stable.

## Rationale

Protocol/Registry keeps backend definition, metadata, and availability close to the implementation while giving the rest of the system a stable surface. It also lets the frontend consume backend capabilities and parameter schemas without hardcoding every algorithm.

## Consequences

### Positive

- New backends can be added without editing central switch statements.
- Missing optional dependencies can surface as unavailable backends instead of import-time crashes.
- UI controls and pipeline nodes can be driven from backend metadata.

### Negative

- Registry import order and heavy dependency imports must be controlled carefully.
- Protocols can become bloated if they try to cover every future backend shape.

### Neutral / Follow-up

- Backends that produce 3D natively should advertise capabilities rather than forcing all detectors into one shape.
- Registry imports should stay lightweight and should not import torch, transformers, or model weights just to list options.

## References

- `.planning/PROJECT.md` — Generic SLAM API and v3.0 detector API decisions
- `.planning/research/ARCHITECTURE.md` — DetectorProtocol and Detection3DProtocol design
- `.planning/research/FEATURES.md` — v2.0 pattern to mirror
- `README.md` — On Pluggability as a Research Methodology
