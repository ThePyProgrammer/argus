# Phase 5: Robot Locomotion Fix - Research

**Researched:** 2026-03-18
**Domain:** Quadruped locomotion control in MuJoCo (Unitree Go2)
**Confidence:** HIGH

## Summary

The robots cannot move because of a fundamental actuator mismatch: the Go2 MJCF model uses **torque-mode motor actuators** (MuJoCo default `<motor>` with no gainprm/biasprm overrides), but the current `_velocity_to_ctrl()` writes **joint angle positions** (0.8, -1.5 rad) directly to `ctrl[]`. MuJoCo interprets these as ~1 Nm torque commands -- far too weak to move a 6.9 kg quadruped against gravity and friction. The sinusoidal oscillation adds at most 0.3 Nm variation, which produces jitter but zero net ground reaction force.

The fix has two options: (A) convert actuators to position-controlled servos (add `gainprm` and `biasprm` to the MJCF) so the existing ctrl-as-position pattern works, then implement a proper analytical trot gait; or (B) keep torque actuators and implement a PD controller in Python that computes torques from position errors. Option A is simpler and more robust. A pre-trained RL policy is the ideal long-term solution but requires heavy dependencies (PyTorch/ONNX, IsaacGym-trained weights) that are disproportionate for this project's needs.

**Primary recommendation:** Convert Go2 actuators to position-controlled mode in the MJCF, then implement a Raibert-style analytical trot gait with proper swing/stance phases, foot clearance, and body velocity coupling. This is a self-contained fix with no new dependencies.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Replace the crude sinusoidal gait with a pre-trained RL locomotion policy for Go2
- Fallback if no good RL policy exists: improved analytical gait with proper ground contact timing, body lean, and foot clearance (NOT direct body force)
- Fix applies to BOTH `MuJoCoBridge._velocity_to_ctrl()` and `MultiRobotBridge._velocity_to_ctrl()` -- they share the same pattern
- On stuck detection (position unchanged for N steps): turn in place 90 degrees, then retry navigation
- No hard limit on retries per frontier goal -- keep retrying with turn recovery
- Support omnidirectional movement: forward, backward, lateral strafe, and rotation
- Linear scaling: higher velocity command = faster gait + longer stride, capped at maximum safe speed
- The RL policy (or fallback gait) must accept (vx, vy, angular) as input and produce joint targets

### Claude's Discretion
- Specific RL policy selection (source, format, how to load)
- Integration details (ONNX, TorchScript, raw numpy weights, etc.)
- Gait parameter tuning if using analytical fallback
- Maximum safe speed cap value
- Turn-in-place implementation details (duration, angle)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

## Root Cause Analysis

### Why the Current Gait Fails

**The critical bug:** `go2.xml` defines actuators as:
```xml
<motor class="abduction" name="FL_hip" joint="FL_hip_joint"/>
```

With no `gainprm`, `biasprm`, or `gaintype` overrides, MuJoCo defaults to:
- `gaintype=0` (fixed gain = 1.0)
- `biastype=0` (no bias)
- This means `ctrl[i]` is applied as **raw torque in Nm**

But `_velocity_to_ctrl()` writes joint position values like `_STANDING_QPOS = [0.0, 0.8, -1.5, ...]` to `ctrl[]`. MuJoCo reads 0.8 as "apply 0.8 Nm torque", not "move joint to 0.8 radians." The Go2 weighs 6.9 kg and needs ~20+ Nm at the knee to stand. The sinusoidal gait adds 0.3 Nm oscillation -- 100x too weak.

**Evidence:** `ctrlrange` confirms torque limits: hips at +/-23.7 Nm, knees at +/-45.43 Nm. The `keyframe` home pose uses `ctrl="0 0.9 -1.8 ..."` which are also torque values (not positions) -- they happen to numerically match standing angles but are actually the torques that roughly hold the standing pose statically.

### The Fix: Position-Controlled Actuators

Convert `<motor>` to position servos by adding PD gains:

```xml
<default class="go2">
  <!-- Replace motor defaults with position actuators -->
  <position kp="40" kv="2" ctrlrange="-1.0472 1.0472"/>  <!-- per-class override -->
</default>
```

Or equivalently, modify actuators to `<position>` type. Then `ctrl[i] = desired_angle` works correctly.

## Standard Stack

### Core (No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| MuJoCo | >=2.2.2 | Physics sim | Already in project |
| NumPy | existing | Gait computation | Already in project |

### RL Policy Option (NOT RECOMMENDED for this project)

| Library | Version | Purpose | Why Not |
|---------|---------|---------|---------|
| unitree_rl_gym | latest | Training Go2 policies | Requires IsaacGym, PyTorch, GPU training |
| unitree_rl_mjlab | latest | MuJoCo-based RL | Requires full RL stack (Brax/PPO) |
| ONNX Runtime | 1.x | Running exported policies | Extra dependency, needs trained weights |

**Recommendation:** Use the analytical fallback path. The RL policy route requires training infrastructure (IsaacGym or MJX + Brax), produces PyTorch checkpoint files that need export, and adds PyTorch/ONNX as runtime dependencies. For a SLAM/exploration project, this is massive dependency bloat for what is fundamentally a "make the legs move" problem.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Analytical trot gait | Pre-trained RL policy | RL is more robust on rough terrain but requires PyTorch/ONNX + trained weights + Go2-specific checkpoint; analytical is zero-dependency and sufficient for flat ground |
| Position actuators in MJCF | PD controller in Python | MJCF position actuators are simpler, more stable at high sim rates; Python PD loop risks instability if dt varies |
| Raibert heuristic foot placement | Fixed-trajectory swing | Raibert adapts to velocity commands naturally; fixed trajectory needs separate speed parameterization |

## Architecture Patterns

### Recommended Approach: MJCF Position Actuators + Analytical Trot

#### Step 1: Fix the Actuator Model

Modify `go2.xml` (or a wrapper XML) to use position-controlled actuators:

```xml
<!-- Option A: Change <motor> to <position> with PD gains -->
<actuator>
  <position name="FL_hip" joint="FL_hip_joint" kp="40" kv="2" ctrlrange="-1.0472 1.0472"/>
  <position name="FL_thigh" joint="FL_thigh_joint" kp="40" kv="2" ctrlrange="-1.5708 3.4907"/>
  <position name="FL_calf" joint="FL_calf_joint" kp="60" kv="3" ctrlrange="-2.7227 -0.83776"/>
  <!-- ... repeat for all 12 joints ... -->
</actuator>
```

**Key gains (from community Go2 controllers):**
- Hip (abduction): kp=40, kv=2
- Thigh (hip joint): kp=40, kv=2
- Calf (knee): kp=60, kv=3 (higher because knee bears more load)

**Important:** Do NOT modify the upstream `go2.xml` from mujoco_menagerie. Instead, create a `go2_position.xml` that includes `go2.xml` but overrides the actuator section, or create a wrapper `scene_position.xml`.

#### Step 2: Implement Trot Gait Controller

```
src/
  locomotion/
    __init__.py
    gait_controller.py    # TrotGaitController class
    gait_params.py        # Dataclass with tunable params
```

#### Step 3: Integrate as Drop-In Replacement

Both `MuJoCoBridge._velocity_to_ctrl()` and `MultiRobotBridge._velocity_to_ctrl()` call the same `TrotGaitController.compute(vx, vy, omega, t) -> np.ndarray(12)`.

#### Step 4: Add Stuck Recovery to ExplorationLoop

Extend the existing stuck detection in `exploration_loop.py` lines 129-144 with a physical recovery action (turn 90 degrees).

### Pattern: Trot Gait with Swing/Stance Phases

**What:** A trot gait alternates diagonal leg pairs. Each leg follows a swing phase (foot in air, moving forward) and stance phase (foot on ground, pushing back). The key insight the current code misses is that **stance legs must push backward relative to the body to propel it forward**, while swing legs lift and reposition.

**Gait cycle (trot):**
```
Phase 0.0 - 0.5: FR+RL in stance (pushing), FL+RR in swing (lifting)
Phase 0.5 - 1.0: FL+RR in stance (pushing), FR+RL in swing (lifting)
```

**Joint targets during stance:**
- Hip: slight backward sweep (pushes body forward)
- Thigh: load-bearing angle (support body weight)
- Calf: load-bearing angle (support body weight)

**Joint targets during swing:**
- Hip: forward sweep (reposition foot ahead)
- Thigh: lift up (foot clearance)
- Calf: tuck in then extend (foot clearance, then ground contact)

**Velocity coupling:**
- `vx` (forward): scales hip sweep amplitude and gait frequency
- `vy` (lateral): adds hip abduction offset to shift body sideways
- `omega` (yaw): differential left/right hip sweep (one side steps further)

### Pattern: Raibert-Style Foot Placement

**What:** For each swing leg, the touchdown target is computed as:
```
x_foot = x_hip + v * T_stance/2 + k_p * (v - v_desired)
```
Where `v` is current body velocity, `T_stance` is stance duration, and `k_p` is a feedback gain. This naturally adapts stride length to velocity commands.

**When to use:** When you need velocity-responsive locomotion without RL.

### Anti-Patterns to Avoid

- **Applying position values as torques:** The entire current bug. Always verify actuator type matches control signal semantics.
- **Symmetric sinusoidal oscillation:** Sin waves on thigh joints produce equal push in both directions per cycle = zero net force. Real gaits are asymmetric: slow stance push, fast swing recovery.
- **No foot clearance in swing:** Without lifting feet above ground, legs drag and create friction that fights forward motion.
- **Modifying upstream mujoco_menagerie files:** Create wrapper XMLs instead to allow updating the upstream model.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Full RL locomotion policy | Custom PPO training loop | Pre-trained checkpoint from unitree_rl_gym (if going RL route) | Months of tuning, GPU training, reward shaping |
| Inverse kinematics solver | Custom IK for 3-DOF legs | Geometric IK (2-link planar + hip rotation) | Go2 legs are simple enough for closed-form IK |
| Contact force estimation | Custom contact detector | `mj_contactForce()` or foot sensor data | MuJoCo provides this natively |
| Quaternion math | Custom rotation utilities | Existing `_quat_to_rotation_matrix()` + `np.arctan2` for yaw | Already implemented in both bridges |

**Key insight:** The locomotion fix is a well-understood analytical problem for flat-ground trotting. The novel/complex parts (RL policies, terrain adaptation) are unnecessary for this project's SLAM exploration use case.

## Common Pitfalls

### Pitfall 1: Actuator Type Mismatch (THE CURRENT BUG)
**What goes wrong:** Writing position targets to torque actuators produces near-zero movement.
**Why it happens:** MuJoCo `<motor>` defaults to torque mode. Code assumes position mode.
**How to avoid:** Either change actuators to `<position>` type, or implement explicit PD controller.
**Warning signs:** Robot vibrates/jiggles but doesn't translate. `data.qpos` barely changes over steps.

### Pitfall 2: Unstable PD Gains
**What goes wrong:** Robot oscillates wildly or explodes when position gains are too high.
**Why it happens:** kp too high relative to simulation timestep and joint damping.
**How to avoid:** Start with conservative gains (kp=20-40 for Go2), increase gradually. Ensure kv provides adequate damping (kv = 0.05*kp is a good starting ratio).
**Warning signs:** Joint velocities spike to >100 rad/s, robot flies off screen.

### Pitfall 3: Standing Pose Mismatch After Actuator Change
**What goes wrong:** Robot collapses on start because standing pose doesn't match new actuator mode.
**Why it happens:** The `_STANDING_QPOS` values (0.0, 0.8, -1.5) are correct joint angles for standing, but the keyframe ctrl values (0, 0.9, -1.8) were torques. With position actuators, ctrl should match desired joint angles.
**How to avoid:** Use the keyframe `qpos` values (0, 0.9, -1.8) as the standing pose for position actuators. Note: current code uses (0, 0.8, -1.5) which differs from the keyframe -- verify which is correct empirically.
**Warning signs:** Robot sinks into ground or legs splay on boot.

### Pitfall 4: Gait Frequency vs. Frame Rate Aliasing
**What goes wrong:** Gait appears jerky or robot walks in place.
**Why it happens:** At 5 Hz frame rate (10 physics steps * 0.002s), a 4 Hz gait has only 1.25 frames per cycle. The gait controller undersamps its own trajectory.
**How to avoid:** Lower gait frequency to 1-2 Hz (each cycle spans 2.5-5 frames), or increase sim_steps_per_frame. The gait generates joint targets that MuJoCo interpolates between physics steps.
**Warning signs:** Robot's legs seem to teleport between positions rather than smoothly cycling.

### Pitfall 5: Stuck Recovery Oscillation
**What goes wrong:** Robot turns 90 degrees, walks into same obstacle, gets stuck again, turns 90 degrees, repeat.
**Why it happens:** Deterministic 90-degree turn may face another wall in enclosed spaces.
**How to avoid:** Randomize turn direction (left/right), and consider alternating 90/180 degree turns. The exploration loop's frontier re-scan after unstuck should pick a new goal direction.
**Warning signs:** Robot traces a square pattern in corners.

## Code Examples

### Example 1: Position Actuator XML (go2_position.xml)

```xml
<!-- Source: MuJoCo docs on position actuators + Go2 joint limits from go2.xml -->
<mujoco model="go2 position-controlled">
  <include file="go2.xml"/>

  <!-- Override actuators from go2.xml with position-controlled versions -->
  <!-- NOTE: MuJoCo does not support partial override of <actuator> from included files.
       The actuator section in go2.xml must be removed or this file must be
       a complete standalone that doesn't include go2.xml's actuator block.
       Approach: create a modified copy or use XML string manipulation at load time. -->
</mujoco>
```

**Practical approach:** Since MuJoCo `<include>` doesn't support selective override of actuator blocks, the cleanest solution is to programmatically modify the XML at load time in the bridge code:

```python
# Source: MuJoCo documentation on actuator types
import xml.etree.ElementTree as ET

def patch_actuators_to_position(xml_path: str) -> str:
    """Convert torque motors to position actuators in Go2 MJCF."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    actuator_elem = root.find("actuator")
    if actuator_elem is None:
        return ET.tostring(root, encoding="unicode")

    # PD gains per joint type
    GAINS = {
        "abduction": {"kp": "40", "kv": "2"},
        "hip": {"kp": "40", "kv": "2"},
        "knee": {"kp": "60", "kv": "3"},
    }

    for motor in list(actuator_elem):
        joint_class = motor.get("class", "")
        gains = GAINS.get(joint_class, GAINS["hip"])

        # Convert <motor> to <position>
        motor.tag = "position"
        motor.set("kp", gains["kp"])
        motor.set("kv", gains["kv"])
        # ctrlrange becomes joint position range (not torque range)
        # Remove torque ctrlrange -- position actuator will use joint limits
        if "ctrlrange" in motor.attrib:
            del motor.attrib["ctrlrange"]

    return ET.tostring(root, encoding="unicode")
```

### Example 2: Analytical Trot Gait Controller

```python
# Source: Raibert heuristic + standard quadruped gait literature
import numpy as np
from dataclasses import dataclass

@dataclass
class GaitParams:
    """Tunable gait parameters."""
    frequency: float = 2.0          # gait cycles per second
    stance_height: float = -0.25    # target foot height relative to hip (negative = below)
    swing_height: float = 0.06      # foot lift during swing phase
    stride_length: float = 0.15     # max forward stride per step at full speed
    lateral_stride: float = 0.08    # max lateral stride per step at full speed
    max_speed: float = 1.0          # m/s velocity cap
    # Standing joint angles (from go2.xml keyframe)
    standing_hip: float = 0.0
    standing_thigh: float = 0.9
    standing_calf: float = -1.8

class TrotGaitController:
    """Velocity-commanded trot gait for Unitree Go2.

    Produces 12 joint position targets given (vx, vy, omega) velocity command.
    Designed for position-controlled actuators.
    """

    # Leg indices: [hip, thigh, calf] for each leg
    # Order matches go2.xml actuator order: FL, FR, RL, RR
    # Diagonal pairs for trot: (FL, RR) and (FR, RL)
    PAIR_A = [0, 3]  # FL, RR -- in phase
    PAIR_B = [1, 2]  # FR, RL -- anti-phase

    def __init__(self, params: GaitParams | None = None):
        self._params = params or GaitParams()
        self._phase = 0.0  # 0.0 to 1.0

    def compute(
        self, vx: float, vy: float, omega: float, dt: float,
    ) -> np.ndarray:
        """Compute 12 joint position targets for one timestep.

        Args:
            vx: Forward velocity command (m/s, positive = forward).
            vy: Lateral velocity command (m/s, positive = left).
            omega: Yaw rate command (rad/s, positive = turn left).
            dt: Time since last call (seconds).

        Returns:
            (12,) array of joint position targets in actuator order.
        """
        p = self._params

        # Clamp speed
        speed = min(np.sqrt(vx**2 + vy**2), p.max_speed)

        # Advance gait phase (only when moving)
        if speed > 0.01 or abs(omega) > 0.01:
            self._phase = (self._phase + p.frequency * dt) % 1.0

        ctrl = np.zeros(12)

        for leg_idx in range(4):
            # Determine phase offset for this leg
            if leg_idx in self.PAIR_A:
                leg_phase = self._phase
            else:
                leg_phase = (self._phase + 0.5) % 1.0

            # Compute joint targets
            hip, thigh, calf = self._leg_targets(
                leg_idx, leg_phase, vx, vy, omega, speed,
            )

            base = leg_idx * 3
            ctrl[base] = hip
            ctrl[base + 1] = thigh
            ctrl[base + 2] = calf

        return ctrl

    def _leg_targets(
        self, leg_idx: int, phase: float,
        vx: float, vy: float, omega: float, speed: float,
    ) -> tuple[float, float, float]:
        """Compute hip, thigh, calf targets for one leg."""
        p = self._params
        is_swing = phase < 0.5  # first half = swing, second half = stance

        # Velocity scaling factor (0 to 1)
        v_scale = min(speed / p.max_speed, 1.0) if p.max_speed > 0 else 0.0

        # Hip abduction: lateral movement + turning differential
        is_left = leg_idx in [0, 2]  # FL=0, RL=2 are left legs
        is_front = leg_idx in [0, 1]  # FL=0, FR=1 are front legs

        hip = p.standing_hip
        # Lateral velocity -> hip abduction
        hip += 0.1 * vy * (1.0 if is_left else -1.0)
        # Turning -> differential abduction
        hip += 0.05 * omega * (1.0 if is_left else -1.0)

        if is_swing:
            # SWING: lift foot and move forward
            swing_progress = phase / 0.5  # 0 to 1 within swing

            # Thigh: lift during mid-swing (parabolic)
            lift = p.swing_height * 4.0 * swing_progress * (1.0 - swing_progress)
            thigh = p.standing_thigh - lift * 2.0  # less flexion = higher foot

            # Calf: tuck then extend
            calf = p.standing_calf + lift * 1.5

            # Forward stride: move foot forward during swing
            stride_offset = p.stride_length * v_scale * (swing_progress - 0.5)
            thigh += stride_offset * 0.5

        else:
            # STANCE: foot on ground, push backward
            stance_progress = (phase - 0.5) / 0.5  # 0 to 1 within stance

            thigh = p.standing_thigh
            calf = p.standing_calf

            # Push backward: hip sweeps from front to back during stance
            push_offset = p.stride_length * v_scale * (0.5 - stance_progress)
            thigh += push_offset * 0.3

        return hip, thigh, calf
```

### Example 3: Stuck Recovery (Turn-in-Place)

```python
# In exploration_loop.py, after stuck detection
class StuckRecovery:
    """Turn-in-place recovery when robot is stuck."""

    def __init__(self, turn_angle: float = np.pi / 2, angular_speed: float = 1.0):
        self._turn_angle = turn_angle
        self._angular_speed = angular_speed
        self._remaining = 0.0
        self._active = False

    def trigger(self):
        """Start a turn recovery."""
        # Randomize direction
        direction = 1.0 if np.random.random() > 0.5 else -1.0
        self._remaining = self._turn_angle * direction
        self._active = True

    def step(self, dt: float) -> tuple[np.ndarray, float] | None:
        """Get recovery velocity command, or None if not active."""
        if not self._active:
            return None

        turn = np.sign(self._remaining) * self._angular_speed
        self._remaining -= turn * dt

        if abs(self._remaining) < 0.1:
            self._active = False
            return None

        return np.zeros(2), turn

    @property
    def is_active(self) -> bool:
        return self._active
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sinusoidal joint oscillation | RL policies (IsaacGym/MJX trained) | 2023-2024 | Human-level agility, sim-to-real transfer |
| Torque actuators + manual PD | Position actuators in MJCF | MuJoCo 2.3+ | Cleaner separation of control and physics |
| Fixed gait tables | Raibert heuristic + MPC | Mature technique | Velocity-adaptive stride, robust on flat ground |

**For this project:** RL policies are state-of-the-art but overkill. Raibert-style analytical gait on position actuators is the sweet spot -- well-understood, zero dependencies, sufficient for flat-ground SLAM exploration.

## Open Questions

1. **Exact PD gains for position actuators**
   - What we know: Community Go2 controllers use kp=20-80, kv=1-5 range. The `go2.xml` has joint damping=2 and armature=0.01.
   - What's unclear: Optimal gains depend on sim timestep and desired stiffness. Need empirical tuning.
   - Recommendation: Start with kp=40/kv=2 for hips/thighs, kp=60/kv=3 for knees. Tune based on standing stability test.

2. **Standing pose values**
   - What we know: Code uses `_STANDING_QPOS = [0, 0.8, -1.5]` but keyframe uses `[0, 0.9, -1.8]`.
   - What's unclear: Which produces more stable standing.
   - Recommendation: Use keyframe values (0, 0.9, -1.8) as they are from the mujoco_menagerie authors.

3. **XML modification approach**
   - What we know: MuJoCo `<include>` doesn't support selective section override. Cannot override just `<actuator>` from an included file.
   - What's unclear: Whether to modify go2.xml directly, create a Python XML patcher, or maintain a separate copy.
   - Recommendation: Python XML patcher at load time in the bridge. Keeps upstream model untouched, applies to both single and multi-robot scenes.

4. **Multi-robot scene XML patching**
   - What we know: `scene_builder.py` already does XML string manipulation to prefix names for two robots.
   - What's unclear: Whether the actuator patching should happen before or after scene building.
   - Recommendation: Patch actuators in the source go2.xml before scene builder processes it, so prefixed actuators inherit the position type.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pytest.ini |
| Quick run command | `pytest tests/test_sim_bridge.py tests/test_multi_bridge.py tests/test_exploration_loop.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map

This phase has no formal requirement IDs. Tests map to functional behaviors:

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| Position actuator XML patching produces valid model | unit | `pytest tests/test_locomotion.py::test_patch_actuators -x` | No -- Wave 0 |
| TrotGaitController.compute() returns 12 joint targets within limits | unit | `pytest tests/test_locomotion.py::test_gait_output_shape_and_limits -x` | No -- Wave 0 |
| Robot translates >0.5m in 100 steps with forward velocity command | unit (mock-free MuJoCo) | `pytest tests/test_locomotion.py::test_robot_moves_forward -x` | No -- Wave 0 |
| Robot turns >45deg in 50 steps with angular command | unit | `pytest tests/test_locomotion.py::test_robot_turns -x` | No -- Wave 0 |
| Stuck recovery triggers turn-in-place action | unit | `pytest tests/test_exploration_loop.py::test_stuck_recovery -x` | No -- extend existing |
| Both bridges produce identical gait output for same input | unit | `pytest tests/test_locomotion.py::test_bridge_gait_parity -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_locomotion.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_locomotion.py` -- covers gait controller, XML patching, movement verification
- [ ] `src/locomotion/__init__.py` -- new module
- [ ] Extend `tests/test_exploration_loop.py` with stuck recovery test

## Sources

### Primary (HIGH confidence)
- `models/unitree_go2/go2.xml` -- Actuator definitions, joint limits, body masses (direct inspection)
- `src/bridge/sim_bridge.py` -- Current `_velocity_to_ctrl()` implementation (direct inspection)
- `src/bridge/multi_bridge.py` -- Multi-robot variant (direct inspection)
- MuJoCo documentation on actuator types: `<motor>` defaults to torque, `<position>` uses PD control

### Secondary (MEDIUM confidence)
- [unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) -- Official Unitree RL training repo, confirmed no pre-trained checkpoints for direct download
- [go2-convex-mpc](https://github.com/elijah-waichong-chan/go2-convex-mpc) -- Convex MPC with Raibert foot placement for Go2 in MuJoCo
- [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) -- Official simulator (no policies included, low-level only)
- [mujoco_playground](https://github.com/google-deepmind/mujoco_playground) -- DeepMind's locomotion environments (Go2 supported but requires full framework)

### Tertiary (LOW confidence)
- PD gain values (kp=40-60, kv=2-3): derived from multiple community implementations, not from official Unitree source. Needs empirical validation.

## Metadata

**Confidence breakdown:**
- Root cause analysis: HIGH -- direct code inspection confirms actuator type mismatch
- Actuator fix approach: HIGH -- MuJoCo position actuator semantics are well-documented
- Gait controller design: MEDIUM -- standard approach but specific parameters need tuning
- PD gains: LOW -- community-derived values, need empirical validation
- Stuck recovery: HIGH -- straightforward extension of existing detection logic

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain, no fast-moving dependencies)
