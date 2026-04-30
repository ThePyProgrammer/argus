# ADR-0017: Treat X2 Locomotion as External Walking Policy Boundary

| Field | Value |
|-------|-------|
| Status | Proposed |
| Date | 2026-04-30 |
| Category | API Design |
| Deciders | Project maintainers |
| Consulted | AGIBOT X2 simulation adaptation design, AGIBOT X2 research report |
| Informed | Future Argus control and simulation contributors |
| Supersedes | None |
| Superseded by | None |
| Related | ADR-0002, ADR-0015, ADR-0016 |

## Context

The first AGIBOT X2 simulation milestone requires physics walking. That does not mean Argus should invent a humanoid gait controller.

Argus currently contains Go2 locomotion logic that is appropriate for a quadruped demo. AGIBOT X2 is a high-DOF humanoid. Stable walking depends on whole-body dynamics, contacts, actuator limits, latency, falls, recovery, and policy/controller assumptions. Pretending this is just another hand-written gait is how you get a robot-shaped screensaver faceplanting in MuJoCo.

The swarm coordinator should reason about goals, waypoints, velocity commands, formation slots, and robot health. It should not command raw X2 joints. Joint-level actuation belongs behind a walking controller or learned policy boundary.

## Options Considered

1. **External walking policy boundary** — Argus sends high-level velocity, yaw, stand, stop, and recover commands; a replaceable X2 controller/policy outputs MuJoCo actuator controls.
2. **Procedural humanoid gait inside Argus** — implement a hand-authored X2 gait similar in spirit to the Go2 trot controller.
3. **Raw-joint swarm control** — let the swarm layer or coordinator output joint targets/actions directly.
4. **Status quo / do nothing** — do not support X2 physics walking.

## Decision

**In the context of** adding AGIBOT X2 physics walking to an Argus swarm simulation, **facing** humanoid locomotion complexity and a coordinator that should stay platform-level, **we decided for** an external walking policy boundary **to achieve** replaceable X2 locomotion without leaking joint-level control into swarm logic, **accepting** dependency on a working X2 controller or policy.

## Rationale

Argus should orchestrate and visualize swarm behaviour. It should not become a humanoid locomotion research project before it can spawn an X2.

The X2 platform exposes a small command interface:

- desired planar velocity;
- desired yaw rate;
- stand/stop;
- reset/recover.

The walking controller consumes robot state and produces MuJoCo actuator controls. It also reports health:

- policy loaded;
- action shape valid;
- NaN/Inf guard state;
- actuator clamp count;
- command tracking error;
- fall state.

This keeps the first milestone honest. If the walking policy is bad, the robot falls and the simulator reports that. If the coordinator is bad, robots collide or deadlock. Those failures are different. They need different fixes. Blurring them together is not engineering; it is soup.

## Consequences

### Positive

- Swarm logic stays at the goal/velocity level.
- X2 locomotion can be swapped as better policies/controllers become available.
- Fall and controller-health reporting become explicit simulation state.
- The bridge can test controller IO separately from coordinator behaviour.
- Avoids copying the Go2 procedural gait pattern into a humanoid where it does not belong.

### Negative

- The first X2 demo depends on obtaining or training a working MuJoCo-compatible X2 walking policy/controller.
- Controller integration requires strict actuator ordering, observation shape, and model-version checks.
- Debugging may require tooling around policy outputs, contact state, and actuator clamps.

### Neutral / Follow-up

- Training a walking policy inside Argus is out of scope for this ADR.
- Isaac Lab policy training/import remains possible later.
- Hardware/AimDK command mapping should be a separate ADR when real robots enter scope.

## References

- ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary
- ADR-0015: Introduce Robot Platform Abstraction
- ADR-0016: Use MuJoCo First for AGIBOT X2 Simulation
- `docs/superpowers/specs/2026-04-30-agibot-x2-adaptation-design.md`
- `outputs/agibot-x2-swarm.md`
