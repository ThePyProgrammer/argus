# Research Summary: Multi-Robot 3D Reconstruction (SimWorld)

**Domain:** Multi-robot autonomous exploration and 3D reconstruction in simulation
**Researched:** 2026-03-17
**Overall confidence:** MEDIUM

## Executive Summary

This project builds a multi-robot autonomous exploration and 3D reconstruction system where two simulated Unitree Go2 quadrupeds explore a SimWorld-Robotics (UE5) environment, each running independent SLAM, and merge their maps into a unified real-time 3D reconstruction. DimOS serves as the orchestration framework, providing module composition, typed pub/sub streams, and LLM-powered agent coordination.

The recommended stack centers on RTAB-Map v0.23.1 for per-robot visual SLAM (RGB-D), OctoMap v1.10.0 for 3D occupancy grid generation, and Open3D for point cloud processing. ROS 2 Humble serves as the SLAM computation backbone, with DimOS's built-in ROSTransport bridging data between the two frameworks. The architecture uses separate DimOS blueprint instances per robot (NOT fleet mode, which is broadcast-only) communicating via LCM inter-process messaging to a centralized map merge server and exploration coordinator.

The biggest technical risk is the SimWorld gym interface. Its exact observation space, multi-agent stepping semantics, and achievable frame rate are not documented in the project files and must be discovered empirically in Phase 1. The architecture is designed to isolate this risk -- the SimWorldGymBridge module is the only component touching the gym API, so downstream modules are insulated from API surprises. If SimWorld's step rate cannot support real-time SLAM, the entire approach needs revision.

Multi-robot SLAM is a well-studied domain. The key architectural insight is to avoid the complexity of true multi-robot SLAM (which requires inter-robot loop closure and distributed pose graph optimization) by exploiting simulation's advantage: known spawn positions provide the global frame transform for each robot's local map, making merging a straightforward coordinate transformation plus voxel fusion operation.

## Key Findings

**Stack:** DimOS 0.0.11 + RTAB-Map 0.23.1 (via ROS 2 Humble) + OctoMap 1.10.0 + Open3D 0.18+ + gymnasium for SimWorld bridge

**Architecture:** Two-instance DimOS architecture -- separate blueprint process per robot, LCM cross-process communication, centralized map merge + exploration coordination in a third process

**Critical pitfall:** DimOS fleet mode is broadcast-only (same commands to all robots, sensors from primary only). Must use separate blueprint instances for independent robot control.

**Exploration approach:** Frontier-based with Voronoi region splitting. Each robot targets frontiers only within its assigned partition. Re-partition when one robot's region is exhausted.

**Simulation advantage:** Known spawn transforms eliminate the need for ICP-based or feature-based map alignment. Ground-truth poses can anchor SLAM estimates to prevent drift.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **SimWorld Gym Bridge** - Resolve the biggest unknown first
   - Addresses: SimWorld gym connection, sensor data format discovery, achievable step rate
   - Avoids: Building downstream on unverified assumptions about data format
   - Risk: HIGH (SimWorld API is LOW confidence)

2. **Single-Robot SLAM Pipeline** - Core technical complexity
   - Addresses: Depth-to-pointcloud, RTAB-Map integration, occupancy grid (OctoMap), local map building
   - Avoids: Multi-robot complexity while validating fundamental pipeline
   - Risk: MEDIUM (RTAB-Map is proven; integration with SimWorld sensor format is the risk)

3. **Single-Robot Autonomous Exploration** - Prove the autonomy loop
   - Addresses: Frontier detection, navigation goal selection, autonomous explore-map-navigate cycle
   - Avoids: Multi-robot coordination (validate single-robot first)
   - Risk: LOW (frontier-based exploration is well-understood)

4. **Two-Robot Independent Operation** - Mechanical duplication + frame alignment
   - Addresses: Second robot instance, stream namespacing, frame alignment using spawn transforms
   - Avoids: Map merging yet (just verify two independent pipelines work)
   - Risk: MEDIUM (DimOS multi-process coordination is non-trivial)

5. **Map Merging + Coordinated Exploration** - The core deliverable
   - Addresses: Map merge server, voxel fusion, split-room region assignment, coordinated frontiers
   - Avoids: Complex inter-robot loop closure (use known transforms instead)
   - Risk: MEDIUM (map fusion quality; exploration deadlocks)

6. **Polish and Integration** - Visualization, performance, optional LLM agent
   - Addresses: Rerun dashboard, transport tuning, DimOS agent skills, ground-truth metrics
   - Avoids: Premature optimization in earlier phases
   - Risk: LOW (standard DimOS patterns)

**Phase ordering rationale:**
- Phase 1 resolves the riskiest unknown (SimWorld gym API) and determines feasibility
- SLAM (Phase 2) is isolated to single-robot to reduce debugging surface area
- Autonomous exploration (Phase 3) validates the full single-robot loop before adding multi-robot
- Two-robot (Phase 4) is primarily mechanical duplication once single-robot works
- Map merge + exploration coordination (Phase 5) is the final integration
- Polish (Phase 6) should not happen before correctness is established

**Research flags for phases:**
- Phase 1: NEEDS deeper research -- SimWorld gym API format is LOW confidence, must be investigated empirically
- Phase 2: NEEDS research -- SLAM algorithm selection depends on Phase 1 sensor findings; RTAB-Map ROS 2 bridge vs Python bindings decision
- Phase 3: Standard patterns, unlikely to need research
- Phase 4: May need research on DimOS multi-process LCM coordination patterns
- Phase 5: Standard map merge and frontier exploration patterns, may need research on OctoMap merging specifics
- Phase 6: Standard DimOS visualization patterns, unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | DimOS well-documented locally; RTAB-Map v0.23.1 verified; SLAM choice depends on SimWorld sensor format |
| Features | HIGH | Requirements clearly defined in PROJECT.md; feature dependencies straightforward |
| Architecture | HIGH | DimOS module/stream pattern maps directly to multi-robot SLAM; two-instance approach avoids fleet mode limitations |
| Pitfalls | MEDIUM-HIGH | Fleet mode broadcast limitation verified from docs; common multi-robot pitfalls well-known; SimWorld-specific risks need Phase 1 |

## Gaps to Address

- **SimWorld gym observation/action space format** -- must be discovered empirically in Phase 1. Cannot verify remotely.
- **Available sensors on simulated Go2 in SimWorld** -- LiDAR vs depth camera vs both determines SLAM algorithm choice
- **SimWorld multi-agent stepping semantics** -- synchronous (one `step()` advances all robots) vs independent stepping
- **RTAB-Map Python bindings quality** -- may need ROS 2 bridge instead of direct Python integration
- **DimOS multi-process LCM topic namespacing** -- fleet blueprint may have reusable patterns
- **OctoMap incremental update API** -- need to verify the OctoMap ROS 2 node supports incremental point cloud insertion (not full rebuild each frame)

---

*Research summary: 2026-03-17*
