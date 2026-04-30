# Argus Locomotion Mapping

## Current pipeline diagram

```text
Web UI / CLI / autonomous exploration
  -> command representation: (linear_vel=[vx, vy], angular_vel=wz)
  -> waypoint/frontier/random/teleop controller
  -> MultiRobotBridge.set_velocity(robot_id, linear, angular)
     or MuJoCoBridge.set_velocity(linear, angular)
  -> TrotGaitController.compute(vx, vy, omega, dt)
  -> 12 joint position targets in Go2 actuator order
  -> patched MuJoCo position actuators with PD gains
  -> MuJoCo mj_step over sim_steps_per_frame
  -> SensorFrame: RGB, depth, camera GT pose, optional IMU
  -> SLAM / OctoMap / exploration / coordination / web streaming
```

## Evidence table

| Area | Current implementation | Code references |
|---|---|---|
| Command representation | Locomotion command is not a force/torque/action-space object; it is `linear: np.ndarray([vx, vy])` plus scalar `angular`. | `src/bridge/sim_bridge.py:187-207`; `src/bridge/multi_bridge.py:277-285,447-463`; `src/control/teleop.py:66-99` |
| CLI modes | Main supports `teleop`, `waypoint`, `random`, `explore`, `multi`, and default `web`. | `src/main.py:69-77,160-185,715-775` |
| Web control flow | WebSocket receives `{type:"command", payload}` and dispatches to coordinator. UI emits stop/start/pause/resume/speed/restart/send_to. | `backend/web/server.py:118-124,211-247`; `frontend/src/hooks/useWebSocket.ts:41-55`; `frontend/src/components/ControlPanel.tsx:38-56,208-299`; `frontend/src/components/SceneViewer.tsx:270-305` |
| Autonomous flow | Frontier loop returns velocity commands; it does not directly command joints. Stuck recovery also emits velocity commands. | `src/exploration/exploration_loop.py:417-491`; recovery at `50-107`; run loop at `493-520` |
| Waypoint controller | Pure-pursuit/lookahead proportional steering; output is forward linear speed scaled by heading error plus angular velocity. | `src/control/waypoint_runner.py:65-141` |
| Gait controller | Raibert-style analytical trot, diagonal pair alternation, velocity clamp, phase clock, differential stride for turning, produces 12 joint position targets. | `src/locomotion/gait_controller.py:1-11,19-41,55-86,88-154` |
| Gait parameters | Hard-coded dataclass parameters: frequency 3 Hz, swing height 0.15, stride length 0.4, max speed 1.0 m/s, standing pose `(0, 0.9, -1.8)`. | `src/locomotion/gait_params.py:7-42` |
| Actuator model | Upstream Go2 torque `<motor>` actuators are converted in memory to MuJoCo `<position>` actuators with `kp/kv`; original XML is not modified. | `src/locomotion/xml_patcher.py:1-8,14-20,23-62,65-138` |
| Go2 MJCF source | MJCF contains freejoint, named joints, motor actuators, and home qpos. | `models/unitree_go2/go2.xml:67,80-175,188-200,208-209` |
| Single-robot MuJoCo bridge | Loads patched XML from `go2.xml`, sets standing qpos, settles, converts buffered velocity through gait, writes `data.ctrl`, steps physics, returns rendered camera frame and GT pose. | `src/bridge/sim_bridge.py:64-132,134-172,187-207,213-256` |
| Multi-robot MuJoCo bridge | Duplicates robot models, discovers per-robot qpos/control/camera indices, stores per-robot velocity buffers and gait controllers, writes per-robot controls each step. | `src/bridge/multi_bridge.py:31-65,83-181,204-285,447-463` |
| Multi-robot scene generation | Builds N prefixed Go2 instances, patches actuators to position mode, adds cameras, floor/office scene, per-robot actuators. | `src/bridge/scene_builder.py:46-166,186-308` |
| Parameters | Simulation and exploration knobs are dataclasses/CLI args, not live locomotion tuning. | `src/bridge/env_config.py:10-27`; `src/bridge/multi_robot_config.py:11-38`; `src/exploration/config.py:11-43`; `src/main.py:79-147` |
| Coordination interaction | Coordination affects high-level target selection and velocity commands, not gait phase, contacts, balance, or robot-robot locomotion dynamics. | `src/coordination/coordinator.py:477-580,609-643`; `src/coordination/robot_instance.py:41-126` |

## Classification vs locomotion method families

Argus currently implements a classical analytical velocity-to-gait stack:

```text
high-level planner/control -> body velocity command -> analytical trot gait -> joint position targets -> MuJoCo position servos
```

It is not currently MPC, WBC, RL, imitation learning, trajectory optimization, or ROS2/hardware deployment. The closest family is a Raibert-style/open-loop analytical quadruped gait with proportional waypoint navigation. Balance is emergent from MuJoCo position servos and gait heuristics, not from centroidal dynamics, contact optimization, inverse dynamics, torque control, or learned feedback.

## Extension seams

| Upgrade | Main seam | Required changes |
|---|---|---|
| MPC | Replace or wrap `_velocity_to_ctrl()` and `TrotGaitController.compute()` with an optimizer that consumes robot state, desired velocity/trajectory, contacts, and dynamics. | Need state extraction from MuJoCo qpos/qvel, contact schedule/state, dynamics model, foot locations, torque/force limits; likely abandon pure position-target interface or add low-level tracking. |
| WBC | Add whole-body state estimator and inverse dynamics/QP layer below high-level commands. | Need body pose/velocity, joint states, contacts, mass matrix/Jacobians, torque actuators or torque interface; current position actuator patch is a mismatch. |
| RL policy | Add policy inference seam at `MuJoCoBridge.step(action)` or `_velocity_to_ctrl()`. | Need observation vector builder, action scaling, checkpoint loading, frame stacking/history, policy rate, sim normalization, domain randomization if training. Current `step(action)` already accepts 12 joint position targets in single-robot bridge, but multi-robot bridge lacks comparable direct action API. |
| ROS2/hardware | Replace `MuJoCoBridge`/`MultiRobotBridge` with hardware/ROS2 bridge satisfying a command and sensor protocol. | Need ROS2 topics/services/actions, real joint state feedback, command safety, watchdogs, Unitree SDK or ros2_control adapter, time synchronization, calibration, fall detection, emergency stop. |
| Better analytical gait | Keep command representation and add gait plugin abstraction. | Extract a `LocomotionController` protocol; expose gait params live; add per-robot params; use body yaw/velocity feedback; add foot trajectory IK rather than direct heuristic joint-angle offsets. |

## Risk and complexity notes

Low complexity:
- Expose/tune `GaitParams` through config or UI.
- Add a locomotion-controller registry beside the existing SLAM/perception registry pattern.
- Add direct-action support to `MultiRobotBridge` matching single-robot `MuJoCoBridge.step(action)`.

Medium complexity:
- RL inference for joint-position policies in MuJoCo, if trained policy already exists.
- Footstep/IK analytical controller with feedback stabilization.
- ROS2 simulation bridge without hardware.

High complexity:
- MPC or WBC, because current stack lacks contact-aware dynamics/control abstractions and uses position servos rather than torque/force control.
- Hardware deployment, because current safety, timing, actuator semantics, estimation, and fall handling are simulation-oriented.
