# Phase 5: Robot Locomotion Fix - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix robot locomotion so Go2 robots actually translate when given velocity commands in MuJoCo. The current sinusoidal gait controller oscillates legs but doesn't produce enough ground reaction force to move the robot base. Both single-robot and multi-robot modes are affected.

This phase does NOT add new exploration or coordination features -- it fixes the physical movement layer that all upstream features depend on.

</domain>

<decisions>
## Implementation Decisions

### Locomotion Approach
- Replace the crude sinusoidal gait with a pre-trained RL locomotion policy for Go2
- Research should find a suitable pre-trained policy (e.g., from mujoco_menagerie examples, Unitree's published policies, or community Go2 MuJoCo policies)
- Fallback if no good RL policy exists: improved analytical gait with proper ground contact timing, body lean, and foot clearance (NOT direct body force)
- Fix applies to BOTH `MuJoCoBridge._velocity_to_ctrl()` and `MultiRobotBridge._velocity_to_ctrl()` -- they share the same pattern

### Stuck Recovery Behavior
- On stuck detection (position unchanged for N steps): turn in place 90 degrees, then retry navigation
- No hard limit on retries per frontier goal -- keep retrying with turn recovery
- Current stuck detection threshold (20 steps) and rescan behavior remain -- this phase adds physical recovery action on top

### Velocity-to-Action Mapping
- Support omnidirectional movement: forward, backward, lateral strafe, and rotation
- Linear scaling: higher velocity command = faster gait + longer stride, capped at maximum safe speed
- The RL policy (or fallback gait) must accept (vx, vy, angular) as input and produce joint targets

### Claude's Discretion
- Specific RL policy selection (source, format, how to load)
- Integration details (ONNX, TorchScript, raw numpy weights, etc.)
- Gait parameter tuning if using analytical fallback
- Maximum safe speed cap value
- Turn-in-place implementation details (duration, angle)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current locomotion code (to be replaced)
- `src/bridge/sim_bridge.py` lines 151-187 -- `MuJoCoBridge._velocity_to_ctrl()` (single-robot sinusoidal gait)
- `src/bridge/multi_bridge.py` lines 291-329 -- `MultiRobotBridge._velocity_to_ctrl()` (multi-robot copy)

### Stuck detection (to be extended with recovery)
- `src/exploration/exploration_loop.py` lines 126-144 -- stuck detection logic (stuck_counter, force_rescan, waypoint_runner reset)

### MuJoCo model
- `models/unitree_go2/go2.xml` -- Go2 MJCF model with joint limits, actuator ranges, default classes
- `models/unitree_go2/README.md` -- Model derivation notes, MJX variant info

### Prior context
- `.planning/phases/03-multi-robot-coordination-and-map-merging/03-CONTEXT.md` -- Phase 3 decisions (where stuck problem was first observed)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_STANDING_QPOS` (both bridges): base standing joint positions for 12 actuators -- RL policy output should be additive to or replace these
- `_ACTUATOR_NAMES` (multi_bridge.py): actuator naming convention for mj_name2id discovery
- Stuck detection in ExplorationLoop: already detects position stagnation, just needs physical recovery action added

### Established Patterns
- `_velocity_to_ctrl()` takes buffered (linear, angular) and returns 12-element joint position target array
- Controllers (teleop, waypoint, random, explore) all produce (linear_vel, angular_vel) tuples
- Both bridges use the same interface -- fix one, copy pattern to the other

### Integration Points
- `_velocity_to_ctrl()` is called every `step()` in both bridges -- drop-in replacement
- `ExplorationLoop.step_once()` returns velocity commands -- no change needed there
- `WaypointRunner.get_velocity()` returns (linear, angular) -- no change needed
- The RL policy must run fast enough to not bottleneck the sim step loop (~5-10 Hz)

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. The key constraint is that the solution must be a drop-in replacement for `_velocity_to_ctrl()` so all existing control modes benefit automatically.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 05-make-sure-the-robots-do-not-get-stuck-at-one-place-without-being-able-to-move-off*
*Context gathered: 2026-03-18*
