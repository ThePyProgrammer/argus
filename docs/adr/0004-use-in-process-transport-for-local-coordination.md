# ADR-0004: Use In-Process Transport for Local Coordination

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Integration Strategy |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `README.md` |
| Informed | Backend and coordination contributors |
| Supersedes | DimOS pLCM transport for local Argus coordination |
| Superseded by |  |
| Related | ADR-0002, ADR-0005, ADR-0008 |

## Context

The project initially inherited DimOS-oriented transport concepts. Current planning records say the DimOS dependency was replaced with in-process transport because all simulated robots, the coordinator, and the web server run locally in one Python process. README prose still contains some stale DimOS framing, so the decision needs to be explicit.

## Options Considered

1. **In-process callback transport** — use direct local callbacks and shared process state for robot/coordinator messages.
2. **DimOS pLCM / LCM transport** — serialize messages through local pub/sub even when all components are in one process.
3. **Network service split** — separate robots, coordinator, and visualization into independent services.
4. **Status quo / do nothing** — leave transport assumptions split across stale and current docs.

## Decision

**In the context of** a local MuJoCo simulation where all core components run in one process, **facing** unnecessary serialization and IPC overhead, **we decided for** in-process transport for local coordination **to achieve** lower latency and fewer dependencies, **accepting** that distributed deployment is not the default architecture.

## Rationale

A function call is the right transport when sender and receiver are in the same Python process and share trust, lifecycle, and deployment boundaries. Heavy or crash-prone model backends still use subprocess isolation where the failure-domain boundary matters.

## Consequences

### Positive

- Eliminates serialization overhead for local robot/coordinator communication.
- Simplifies debugging because messages remain ordinary Python objects.
- Avoids depending on DimOS pLCM behavior for the current scope.

### Negative

- The architecture is less ready for multi-host deployment.
- Components are more tightly coupled to a single-process lifecycle.

### Neutral / Follow-up

- README DimOS references should be treated as stale unless verified against current code.
- If Argus becomes distributed, a new ADR should define service boundaries and transport contracts.

## References

- `.planning/PROJECT.md` — Key Decisions: In-process transport over dimos pLCM
- `.planning/REQUIREMENTS.md` — Out of Scope: DimOS dependency replaced with in-process transport
- `README.md` — Coordination Layer: In-Process Transport
