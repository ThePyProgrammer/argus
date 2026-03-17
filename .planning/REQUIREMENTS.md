# Requirements: Multi-Robot 3D Reconstruction (SimWorld)

**Defined:** 2026-03-17
**Core Value:** Two simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Simulation Bridge

- [ ] **SIM-01**: System connects to SimWorld-Robotics gym environment and manages lifecycle (start/stop/reset)
- [ ] **SIM-02**: System extracts depth and RGB sensor data per robot per gym step
- [ ] **SIM-03**: System dispatches independent movement commands to each of two Go2 robots
- [ ] **SIM-04**: System extracts ground-truth pose (position + orientation) per robot per step

### SLAM Pipeline

- [ ] **SLAM-01**: Each robot runs RTAB-Map RGB-D SLAM producing a local pose graph and map
- [ ] **SLAM-02**: Each robot's SLAM pipeline outputs a 3D point cloud of explored area
- [ ] **SLAM-03**: Each robot's SLAM pipeline outputs an OctoMap 3D occupancy grid for navigation
- [ ] **SLAM-04**: System compares SLAM pose estimates to ground-truth and reports drift metrics

### Autonomous Exploration

- [ ] **EXPL-01**: System detects frontier boundaries (unexplored regions adjacent to explored space)
- [ ] **EXPL-02**: Each robot autonomously selects frontier goals and navigates to them without human input
- [ ] **EXPL-03**: System tracks and reports exploration completeness (% of navigable area covered)

### Multi-Robot Coordination

- [ ] **COORD-01**: Two Go2 robots operate as separate DimOS blueprint instances with namespaced streams
- [ ] **COORD-02**: System partitions the environment into regions using Voronoi splitting, assigning each robot a coverage zone
- [ ] **COORD-03**: System dynamically re-partitions regions when one robot's assigned area is fully explored

### Map Merging

- [ ] **MERGE-01**: System aligns robot-local maps to a shared global frame using known spawn transforms
- [ ] **MERGE-02**: System fuses two 3D occupancy grids into a single unified navigation map via voxel merging
- [ ] **MERGE-03**: System merges point clouds from both robots into a unified 3D reconstruction
- [ ] **MERGE-04**: Map merging operates incrementally in real-time as robots explore (not batch post-processing)

### Visualization

- [ ] **VIZ-01**: System displays the merged 3D map in real-time via Rerun or RViz2
- [ ] **VIZ-02**: System overlays both robots' current positions and trajectories on the merged map
- [ ] **VIZ-03**: System displays a coverage heatmap showing explored vs unexplored regions

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Exploration

- **EXPL-04**: Information-gain weighted frontier selection (prioritize high-value frontiers)
- **EXPL-05**: Multi-robot collision avoidance during exploration

### Advanced Coordination

- **COORD-04**: DimOS LLM agent for high-level exploration coordination and strategy
- **COORD-05**: Inter-robot communication protocol for sharing map fragments

### Scene Complexity

- **SCENE-01**: Dynamic obstacle avoidance (pedestrians/vehicles in SimWorld)
- **SCENE-02**: Custom office-like UE5 scene for indoor simulation

### Map Quality

- **MERGE-05**: Conflict resolution for overlapping mapped regions
- **MERGE-06**: Merged map quality scoring against ground-truth reconstruction

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-world deployment | Simulation-only project; no hardware integration |
| Custom SLAM implementation | Use RTAB-Map; writing custom SLAM is months of work for worse results |
| Semantic mapping | Object recognition adds complexity without supporting core navigation goal |
| Realistic communication simulation | Simulating network latency/drops is unnecessary in same-host simulation |
| Custom UE5 scene creation | Use SimWorld's existing urban environments as stand-in |
| DimOS fleet mode | Research confirmed it's broadcast-only; separate instances required |
| Post-processing map refinement | Core value is real-time; offline refinement is v2+ |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIM-01 | Phase 1 | In Progress (test stub + API discovered) |
| SIM-02 | Phase 1 | In Progress (test stub + API discovered) |
| SIM-03 | Phase 1 | Pending |
| SIM-04 | Phase 1 | In Progress (test stub + API discovered) |
| SLAM-01 | Phase 1 | Pending |
| SLAM-02 | Phase 1 | Pending |
| SLAM-03 | Phase 1 | Pending |
| SLAM-04 | Phase 1 | Pending |
| EXPL-01 | Phase 2 | Pending |
| EXPL-02 | Phase 2 | Pending |
| EXPL-03 | Phase 2 | Pending |
| COORD-01 | Phase 3 | Pending |
| COORD-02 | Phase 3 | Pending |
| COORD-03 | Phase 3 | Pending |
| MERGE-01 | Phase 3 | Pending |
| MERGE-02 | Phase 3 | Pending |
| MERGE-03 | Phase 3 | Pending |
| MERGE-04 | Phase 3 | Pending |
| VIZ-01 | Phase 4 | Pending |
| VIZ-02 | Phase 4 | Pending |
| VIZ-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-03-17*
*Last updated: 2026-03-17 after roadmap creation*
