# Domain Pitfalls

**Domain:** Multi-robot 3D reconstruction in simulation (SimWorld + DimOS)
**Researched:** 2026-03-17
**Confidence:** MEDIUM-HIGH (DimOS internals verified from local docs; multi-robot SLAM pitfalls well-established in literature)

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: DimOS Fleet Mode Is Broadcast-Only

**What goes wrong:** Developers assume DimOS fleet mode (`Go2FleetConnection`, `unitree-go2-fleet` blueprint) means independent multi-robot control. In reality, fleet mode broadcasts the same commands to all robots simultaneously. Only the primary robot's sensors stream. There is no per-robot navigation, no per-robot SLAM, no independent goal assignment.

**Why it happens:** The `Go2FleetConnection` inherits from single-robot `GO2Connection`. Extra robot connections only receive broadcast `move()` commands. The architecture assumes a "swarm does the same thing" pattern, not "each robot does different things."

**Consequences:** If you build split-room exploration on top of fleet mode, Robot B just mirrors Robot A. All sensor data comes from Robot A only. The entire multi-robot architecture must be redesigned.

**Prevention:**
- Run two completely separate DimOS blueprint instances, one per robot
- Each instance gets its own SLAM pipeline, frontier explorer, and navigator
- Build a coordination layer via LCM inter-process messaging or a shared DimOS Module in a third process
- Do NOT use `Go2FleetConnection` for this project

**Detection:** Both robots move identically. Test with different goal positions for each robot in the very first iteration.

### Pitfall 2: Coordinate Frame Misalignment Between SLAM Instances

**What goes wrong:** Each robot's SLAM initializes its own "world" frame at startup, with the robot's initial position as origin. Robot A's (0,0,0) and Robot B's (0,0,0) are different physical locations. Point clouds from both robots cannot be merged naively.

**Why it happens:** All SLAM algorithms initialize coordinates relative to the starting pose. Without a shared global frame, maps exist in incompatible coordinate systems.

**Consequences:** Merged maps are garbage -- walls appear in wrong places, occupancy grids conflict. This is the most common failure mode in multi-robot SLAM projects.

**Prevention:**
- **Use SimWorld ground-truth poses** to compute `T_global_from_slamA` and `T_global_from_slamB` transforms. SimWorld knows exactly where both robots are in the UE5 scene. This is the simulation advantage -- use it.
- Apply transforms before any merge step
- Carry explicit `frame_id` metadata on every point cloud and occupancy grid
- Write a `transform_to_global()` utility early and use it consistently

**Detection:** Visualize both robots' maps in Rerun with ground-truth overlay. If walls don't align, frame transforms are wrong.

### Pitfall 3: SimWorld Gym Interface May Not Support Real-Time SLAM

**What goes wrong:** Developers assume the SimWorld gym interface provides continuous sensor streams like real hardware. Gym environments are step-based: `obs = env.step(action)`. If step rate is too low (e.g., 5 Hz because UE5 rendering is slow), SLAM algorithms that expect 10-30 Hz input cannot converge.

**Why it happens:** OpenAI gym was designed for RL training where step rate is controlled by the training loop, not for real-time robotics where sensors stream continuously.

**Consequences:** SLAM fails to track, produces massive drift, or crashes due to large inter-frame motion. The robot appears to "teleport" between observations.

**Prevention:**
- Investigate SimWorld's actual achievable step rate BEFORE choosing a SLAM algorithm. This is the Phase 1 go/no-go gate.
- Choose SLAM that works with discrete RGB-D frames at the available rate (RTAB-Map in RGB-D mode works at 5-15 Hz)
- If step rate is too low, consider: (a) reducing UE5 render quality, (b) using ground-truth odometry to interpolate between frames, (c) using a SLAM algorithm with motion prediction
- Avoid LiDAR SLAM (e.g., FastLIO2) that requires continuous high-frequency IMU data

**Detection:** If SLAM tracking is lost within 30 seconds, or odometry drifts more than 1m in a straight corridor, the step rate is insufficient.

### Pitfall 4: Map Merging by Naive Concatenation

**What goes wrong:** Teams concatenate point clouds from two robots without proper fusion. The merged map has duplicate surfaces, contradictory occupancy values, and phantom obstacles.

**Why it happens:** Even with correct frame alignment, two robots observe the same areas from different angles with different noise. Blind concatenation preserves all errors from both.

**Consequences:** Navigation on the merged map fails unpredictably. The robot drives into "free space" that is actually an obstacle in the other robot's map.

**Prevention:**
- Use voxel grid merge with conflict resolution (not concatenation):
  - Point clouds: merge into shared voxel grid, averaging positions/colors within each voxel
  - Occupancy grids: Bayesian log-odds update accumulating evidence from both robots
- Start with simple concatenation + voxel downsample for MVP, but plan proper fusion
- Validate: compare merged map against SimWorld ground truth geometry

**Detection:** If merged occupancy grid has more occupied cells than either local grid alone (double-counting), fusion is broken.

### Pitfall 5: SLAM Drift Without Loop Closure in Large Environments

**What goes wrong:** In SimWorld's procedural urban environments (potentially large), SLAM accumulates odometry drift. After 100+ meters, the map is distorted by meters. When the robot returns to a visited area, the same corridor appears twice.

**Why it happens:** All odometry-based SLAM drifts over time. Without loop closure detection, error grows unboundedly.

**Consequences:** Occupancy grid becomes useless for navigation. Paths that should connect don't. Multi-robot merging is even harder because local maps are internally inconsistent.

**Prevention:**
- Use RTAB-Map which has built-in visual loop closure (bag of words approach)
- In simulation, use ground-truth pose as a "perfect GPS" to periodically anchor SLAM estimates. This sidesteps loop closure entirely for the sim case.
- Split-room strategy naturally limits each robot's path length, reducing drift proportionally
- Set RTAB-Map loop closure parameters conservatively (detect loop closures frequently)

**Detection:** Compare SLAM trajectory against ground truth. If position error exceeds 2% of total distance traveled, drift correction is needed.

## Moderate Pitfalls

### Pitfall 6: Exploration Deadlocks in Split-Room Strategy

**What goes wrong:** Two robots with split regions deadlock when: (a) both converge on the same boundary, (b) one finishes its zone while the other is stuck, (c) frontier detection sees the other robot as an obstacle.

**Prevention:**
- Zone-based allocation with non-overlapping Voronoi regions
- Filter the other robot from the occupancy grid before frontier detection (use known pose to mask it)
- Deadlock detector: if no exploration progress for N consecutive steps, re-partition remaining unexplored space
- Timeout on individual frontier goals: if a goal is unreachable for M seconds, select next-best frontier

### Pitfall 7: GPU/CPU Resource Contention

**What goes wrong:** UE5 rendering + two SLAM instances + two navigation stacks + map merging exceeds available hardware. System runs at 2-3 FPS, SLAM tracking fails.

**Prevention:**
- Profile early: run SimWorld with two robots at target step rate BEFORE adding SLAM
- Reduce UE5 render quality (lower resolution, fewer effects -- visual fidelity doesn't matter for depth data)
- Coarser voxel sizes (0.2-0.3m instead of 0.1m) for initial maps
- Process every Nth frame for SLAM if needed (e.g., every 3rd frame)
- Async map merging in a separate process, not blocking SLAM
- Set DimOS `--n-workers` high enough for two robot stacks

**Detection:** Wall-clock time per gym step exceeding 200ms (5 FPS) means optimization is needed.

### Pitfall 8: DimOS Stream Name Collisions in Multi-Robot Setup

**What goes wrong:** Two robot pipelines with identically-named streams (e.g., both have `odom`, `point_cloud`, `occupancy_grid`) cause `autoconnect()` to either fail or silently cross-wire data.

**Prevention:**
- Primary recommendation: separate processes per robot (natural isolation)
- If in single process: use `.remappings()` with `robot_a/` and `robot_b/` prefixes
- Always carry `frame_id` and `robot_id` in message metadata
- Log stream wiring at blueprint build time; verify in unit tests

### Pitfall 9: Point Cloud Memory Growth Crashes Long Runs

**What goes wrong:** Point cloud accumulator grows monotonically as robots explore new areas. After 5-15 minutes in a large environment, RAM is exhausted.

**Prevention:**
- Aggressive voxel downsampling (0.2-0.3m for running accumulator)
- Spatial windowing: full resolution only within N meters of robot, coarser beyond
- Monitor RSS (Resident Set Size); trigger global downsample if exceeding threshold (e.g., 50M points)
- For the occupancy grid (the navigation deliverable), this is less of a concern since it has fixed resolution

### Pitfall 10: Simulation Time vs Wall Clock Desynchronization

**What goes wrong:** SimWorld runs at variable speed. DimOS modules use `time.monotonic()` for timing. SLAM expects wall-clock-rate data but receives it faster or slower. Motion estimation breaks.

**Prevention:**
- Use SimWorld's simulation timestamp as the authoritative clock for all SLAM and mapping
- Set timestamp fields on all DimOS messages from the gym observation's sim time
- Never use `time.time()` or `time.monotonic()` for SLAM-related timing

## Minor Pitfalls

### Pitfall 11: Occupancy Grid Origin Shifts During Exploration

**What goes wrong:** Grid bounds grow as the robot explores. Grid origin shifts, making old frontier coordinates invalid.

**Prevention:** Use fixed-origin grid covering expected exploration area from the start. Or track origin and transform old coordinates when grid is regenerated.

### Pitfall 12: DimOS Is Pre-Release Beta

**What goes wrong:** APIs change between versions. Modules have known issues. Documentation may not match behavior.

**Prevention:** Pin exact DimOS version. Write integration tests for every DimOS interaction. Maintain thin abstraction layer.

### Pitfall 13: RTAB-Map ROS 2 Bridge Overhead

**What goes wrong:** Running RTAB-Map as a ROS 2 node and bridging to DimOS via ROSTransport adds latency (serialization/deserialization at each boundary).

**Prevention:**
- Consider using RTAB-Map's C++ library directly via Python bindings (if available) instead of ROS 2 nodes
- If using ROS 2, minimize bridge crossings: do depth-to-pointcloud conversion on the ROS side
- Profile the bridge latency early. If it exceeds 50ms per message, optimize or remove the bridge

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: SimWorld Gym Bridge | Gym step rate too low for SLAM (P3) | Profile step rate first. Choose RGB-D SLAM that works at available rate. |
| Phase 1: SimWorld Gym Bridge | Sim time vs wall clock (P10) | Use sim timestamps exclusively. |
| Phase 2: Single-Robot SLAM | SLAM drift in large env (P5) | Use ground-truth pose anchoring. Choose RTAB-Map with loop closure. |
| Phase 2: Single-Robot SLAM | Memory growth from accumulation (P9) | Set voxel size limits early. Monitor RSS. |
| Phase 3: Two-Robot Setup | Fleet mode is broadcast-only (P1) | Separate processes per robot from day one. |
| Phase 3: Two-Robot Setup | Stream name collisions (P8) | Separate processes provide natural isolation. |
| Phase 4: Map Merging | Frame misalignment (P2) | Use known spawn transforms from SimWorld. |
| Phase 4: Map Merging | Naive concatenation (P4) | Implement voxel merge with conflict resolution. |
| Phase 5: Exploration | Deadlocks (P6) | Zone partitioning + deadlock detection + timeout. |
| Phase 5: Exploration | Resource contention (P7) | Profile system load. Reduce render quality. Coarser voxels. |
| All Phases | DimOS API instability (P12) | Pin version. Integration tests. Abstraction layer. |

## Sources

- DimOS documentation and codebase analysis (local: docs/, .planning/codebase/) -- HIGH confidence
- DimOS fleet mode limitations (local: docs/robots.md, docs/examples.md) -- HIGH confidence
- Multi-robot SLAM failure modes -- MEDIUM confidence (well-established in literature, training knowledge)
- RTAB-Map characteristics (v0.23.1, loop closure, multi-session) -- HIGH confidence (verified via WebFetch)
- SimWorld gym interface specifics -- LOW confidence (inferred from PROJECT.md, not independently verified)

---

*Pitfalls research: 2026-03-17*
