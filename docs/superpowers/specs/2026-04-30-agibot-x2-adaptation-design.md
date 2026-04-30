# AGIBOT X2 Simulation Adaptation Design

Date: 2026-04-30
Status: Approved for specification; implementation not started
Scope: Argus support for AGIBOT X2 simulation only, with MuJoCo as the first backend

## Goal

Adapt Argus so it can run an AGIBOT X2 swarm simulation in MuJoCo. The first milestone is a physics-walking swarm demo: 2-5 X2 robots spawn in simulation, each runs a real walking controller or policy, and Argus coordinates them through high-level velocity or waypoint commands.

Hardware integration through AimDK_X2, ROS 2 on PC2, or real AGIBOT X2 Ultra robots is explicitly out of scope for this milestone.

## Architectural Direction

Argus currently concentrates too many robot-specific assumptions in the MuJoCo bridge. The existing bridge owns MuJoCo stepping, multi-robot orchestration, Go2 model assumptions, Go2 actuator and camera discovery, Go2 gait control, rendering, and sensor capture. That worked for a single platform. It will not survive humanoids without becoming a junk drawer with legs.

Introduce a robot platform layer below the existing coordinator and UI:

- `RobotPlatform`: interface for model assets, actuator mapping, sensor mapping, command modes, reset behavior, state extraction, footprint, and failure detection.
- `Go2Platform`: preserves current Unitree Go2 behavior behind the new interface.
- `AgibotX2Platform`: loads the X2 MuJoCo model, exposes X2 state and sensors, and delegates joint-level control to an X2 walking controller or policy.
- `MultiRobotBridge`: becomes platform-agnostic MuJoCo orchestration for stepping, spawning, rendering, and streaming.
- `Coordinator`: remains mostly platform-agnostic and consumes platform metadata such as footprint, max speed, command modes, and fall state.

## Locomotion Boundary

Argus should not implement a procedural humanoid gait for X2. The current Go2 trot controller pattern does not transfer to a high-DOF humanoid. The X2 platform should define a replaceable walking controller boundary:

### Inputs

- desired planar velocity;
- desired yaw rate;
- stand / stop command;
- reset / recover command.

### Outputs

- low-level MuJoCo actuator controls for the X2 joints.

### State

- base pose and velocity;
- joint positions and velocities;
- IMU-like orientation;
- contact state;
- fall flag and fall reason;
- command-tracking metrics;
- controller health.

The first implementation can wrap whichever X2 MuJoCo controller or policy is available from the chosen asset source. The boundary must make the controller replaceable so a better trained policy can be swapped in later without rewriting the bridge, coordinator, or UI.

The swarm layer must never command raw X2 joints. It sends goals, planar velocities, yaw rates, and stop/recover commands. Joint-level actuation belongs behind the X2 walking controller boundary.

## Swarm Demo Behaviour

The first demo should support:

- spawning 2-5 AGIBOT X2 robots in MuJoCo;
- assigning each robot a waypoint or formation slot;
- converting waypoint error into bounded velocity and yaw commands;
- running each robot's X2 walking controller under physics;
- detecting falls, collisions, and near misses;
- disabling or stopping failed robots without killing the whole simulation;
- streaming robot pose, state, camera/depth, and failure status to the UI.

This is not an RL training milestone. Training hooks can be designed later. The first problem is to make X2 walking and Argus swarm orchestration coexist without turning the bridge into a platform-specific hairball.

## Data Flow

```text
Frontend controls / waypoint goals
  -> FastAPI/WebSocket backend
  -> Coordinator
  -> MultiRobotBridge
  -> AgibotX2Platform
  -> X2 walking controller
  -> MuJoCo actuators
  -> simulated sensors/state
  -> WebSocket stream back to UI
```

The backend should add platform selection and platform metadata while preserving existing SLAM/perception pipeline APIs where possible.

## Backend and UI Changes

Backend additions:

- platform selection: `go2` or `agibot_x2`;
- platform metadata endpoint or stream payload fields;
- generic robot command API for velocity, yaw, stop, reset, and waypoint-level commands;
- X2 runtime state: standing, walking, fallen, recovering, disabled;
- command-tracking error and controller health;
- collision, contact, and fall summaries.

Frontend additions:

- robot cards show platform, X2 state, fall status, and controller health;
- control panel sends generic velocity/waypoint commands instead of Go2-shaped commands;
- scene viewer uses platform footprint/dimensions instead of Go2 assumptions;
- pipeline editor remains unchanged unless sensor schemas force a change.

Platform-specific details should stay out of the coordinator and UI wherever possible. They flow through metadata and state schemas. Otherwise every future robot becomes a frontend refactor, which is how projects punish themselves for past sins.

## Error Handling and Safety State

Treat physics failures as normal robot runtime state, not Python exceptions.

Each simulated X2 robot should expose:

- `standing | walking | fallen | recovering | disabled`;
- last command;
- command-tracking error;
- fall reason: base height, roll/pitch threshold, bad contact, actuator saturation, timeout, or controller invalid output;
- collision and near-miss summary;
- controller health: policy loaded, action shape valid, NaN/Inf guard status, actuator clamp count.

Error classes:

1. **Configuration errors**
   - Missing X2 MJCF.
   - Invalid actuator map.
   - Missing controller weights.
   - Sensor name mismatch.
   - These fail startup loudly.

2. **Runtime robot failures**
   - Fall.
   - Unstable contacts.
   - Controller saturation.
   - Waypoint timeout.
   - These disable or stop the affected robot while the simulation continues.

3. **Swarm-level failures**
   - Robot collision.
   - Deadlock.
   - Unreachable waypoint.
   - All robots disabled.
   - These surface in UI and scenario test logs.

## Testing Strategy

Minimum tests before calling the milestone complete:

- platform registry loads Go2 and X2 configs independently;
- existing Go2 simulation behaviour does not regress;
- X2 model asset path is validated at startup;
- X2 actuator and sensor mapping matches expected controller IO;
- one X2 can stand and walk under a smoke-test command;
- 2-5 X2 robots spawn with unique names, state, and command channels;
- waypoint-to-velocity command generation works without joint-level leakage;
- fall detection disables only the failed robot;
- collision/near-miss state appears in backend state;
- UI displays platform type and X2 runtime state.

## ADRs to File

The design is governed by three proposed ADRs:

1. `0015-introduce-robot-platform-abstraction.md`
   - Separate platform-specific robot assumptions from `MultiRobotBridge`.

2. `0016-use-mujoco-first-for-agibot-x2-simulation.md`
   - Target MuJoCo first because Argus already uses MuJoCo as its platform boundary.

3. `0017-treat-x2-locomotion-as-external-walking-policy-boundary.md`
   - Keep joint-level humanoid actuation behind a replaceable walking controller/policy boundary.

## Out of Scope

- Real AGIBOT X2 Ultra hardware.
- AimDK_X2 integration.
- PC2 deployment.
- Isaac Lab as the primary runtime.
- Training an X2 walking policy inside Argus.
- Raw-joint multi-agent RL.
- Manipulation and end-effector control beyond future metadata placeholders.

## Success Criteria

The milestone is complete when Argus can run a MuJoCo simulation with 2-5 AGIBOT X2 robots, each controlled by a physics-based walking controller/policy, and the existing Argus UI/coordinator can issue simple swarm-level waypoint or velocity commands while displaying robot pose, simulated sensors, runtime state, and failures.
