# ADR-0015: Introduce Robot Platform Abstraction

| Field | Value |
|-------|-------|
| Status | Proposed |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | AGIBOT X2 simulation adaptation design, AGIBOT X2 research report |
| Informed | Future Argus robot-platform contributors |
| Supersedes | None |
| Superseded by | None |
| Related | ADR-0002, ADR-0004, ADR-0006 |

## Context

Argus currently uses MuJoCo as the simulation platform boundary and has a working local coordination architecture. Good. The problem is that the bridge layer has accumulated platform-specific assumptions for the Unitree Go2: model structure, actuator names, camera discovery, gait control, reset behaviour, and state extraction are all effectively wired into the bridge.

That is tolerable for one quadruped. It is the wrong shape for adding AGIBOT X2, a humanoid with different assets, actuator topology, sensors, footprint, failure modes, and locomotion control. If we add X2 by sprinkling `if robot_type == "x2"` through the bridge, we will get a demo and a maintenance bill. The bill always arrives.

Argus already uses protocol/registry patterns for pluggable backends in perception and SLAM. The robot layer should follow the same architectural habit instead of pretending robots are just different XML files.

## Options Considered

1. **Introduce a robot platform abstraction** — define a platform boundary for model assets, actuator mapping, sensor mapping, command modes, reset/state extraction, footprint, and failure detection.
2. **Fork the existing bridge for X2** — create a parallel X2 bridge with copied MuJoCo stepping/rendering logic and X2-specific control.
3. **Patch the existing bridge with conditionals** — keep one bridge file and branch on robot type throughout the code.
4. **Status quo / do nothing** — keep Argus Go2-only.

## Decision

**In the context of** adapting Argus from a Go2-only simulator to an AGIBOT X2-capable simulation workbench, **facing** platform-specific assumptions embedded in the bridge, **we decided for** introducing a robot platform abstraction **to achieve** platform-specific isolation while preserving shared MuJoCo orchestration, **accepting** a modest abstraction cost before the X2 demo exists.

## Rationale

The bridge should orchestrate simulation. It should not know every robot's joint taxonomy, camera naming scheme, fall definition, and locomotion interface. That is platform code.

A `RobotPlatform` boundary lets Argus preserve shared behaviour:

- MuJoCo stepping;
- multi-robot spawning;
- rendering and sensor streaming;
- coordinator integration;
- UI/backend data flow.

It also isolates robot-specific behaviour:

- model asset selection;
- actuator and sensor mappings;
- command modes;
- reset behaviour;
- robot dimensions and footprint;
- fall/collision state;
- controller health.

This aligns with ADR-0006's protocol/registry pattern. Consistency matters. It is boring. Boring is good architecture.

## Consequences

### Positive

- AGIBOT X2 can be added without contaminating Go2 bridge logic.
- Existing Go2 behaviour can be wrapped as `Go2Platform` and regression-tested.
- Future platforms have a clear integration point.
- Coordinator and UI can consume platform metadata instead of platform conditionals.
- Testing can isolate platform mapping failures from MuJoCo orchestration failures.

### Negative

- The first implementation must refactor bridge boundaries before visible X2 progress appears.
- The abstraction can be overdesigned if it tries to anticipate every future robot. Do not do that. Support Go2 and X2, then generalize only where both need it.
- Existing code that assumes Go2 actuator/camera names will need to move or be wrapped.

### Neutral / Follow-up

- The abstraction should initially support simulation only.
- Hardware adapters such as AimDK_X2 should be a later ADR, not smuggled into this one.
- The platform interface should be small enough to test directly.

## References

- ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary
- ADR-0004: Use In-Process Transport for Local Coordination
- ADR-0006: Use Protocol and Registry Pattern for Pluggable Backends
- `docs/superpowers/specs/2026-04-30-agibot-x2-adaptation-design.md`
- `outputs/agibot-x2-swarm.md`
