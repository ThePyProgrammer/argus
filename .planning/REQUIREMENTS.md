# Requirements: Multi-Robot 3D Reconstruction (SimWorld)

**Defined:** 2026-03-17
**Core Value:** Two simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Simulation Bridge

- [x] **SIM-01**: System connects to SimWorld-Robotics gym environment and manages lifecycle (start/stop/reset)
- [x] **SIM-02**: System extracts depth and RGB sensor data per robot per gym step
- [x] **SIM-03**: System dispatches independent movement commands to each of two Go2 robots
- [x] **SIM-04**: System extracts ground-truth pose (position + orientation) per robot per step

### SLAM Pipeline

- [x] **SLAM-01**: Each robot runs RTAB-Map RGB-D SLAM producing a local pose graph and map
- [x] **SLAM-02**: Each robot's SLAM pipeline outputs a 3D point cloud of explored area
- [x] **SLAM-03**: Each robot's SLAM pipeline outputs an OctoMap 3D occupancy grid for navigation
- [x] **SLAM-04**: System compares SLAM pose estimates to ground-truth and reports drift metrics

### Autonomous Exploration

- [x] **EXPL-01**: System detects frontier boundaries (unexplored regions adjacent to explored space)
- [x] **EXPL-02**: Each robot autonomously selects frontier goals and navigates to them without human input
- [x] **EXPL-03**: System tracks and reports exploration completeness (% of navigable area covered)

### Multi-Robot Coordination

- [x] **COORD-01**: Two Go2 robots operate as separate DimOS blueprint instances with namespaced streams
- [x] **COORD-02**: System partitions the environment into regions using Voronoi splitting, assigning each robot a coverage zone
- [x] **COORD-03**: System dynamically re-partitions regions when one robot's assigned area is fully explored

### Map Merging

- [x] **MERGE-01**: System aligns robot-local maps to a shared global frame using known spawn transforms
- [x] **MERGE-02**: System fuses two 3D occupancy grids into a single unified navigation map via voxel merging
- [x] **MERGE-03**: System merges point clouds from both robots into a unified 3D reconstruction
- [x] **MERGE-04**: Map merging operates incrementally in real-time as robots explore (not batch post-processing)

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
| SIM-01 | Phase 1 | Complete (01-02) |
| SIM-02 | Phase 1 | Complete (01-02) |
| SIM-03 | Phase 1 | Complete (01-02) |
| SIM-04 | Phase 1 | Complete (01-02) |
| SLAM-01 | Phase 1 | Complete |
| SLAM-02 | Phase 1 | Complete |
| SLAM-03 | Phase 1 | Complete |
| SLAM-04 | Phase 1 | Complete |
| EXPL-01 | Phase 2 | Complete (02-01) |
| EXPL-02 | Phase 2 | Complete (02-01) |
| EXPL-03 | Phase 2 | Complete |
| COORD-01 | Phase 3 | Complete (03-01) |
| COORD-02 | Phase 3 | Complete (03-01) |
| COORD-03 | Phase 3 | Complete (03-02) |
| MERGE-01 | Phase 3 | Complete (03-02) |
| MERGE-02 | Phase 3 | Complete (03-02) |
| MERGE-03 | Phase 3 | Complete (03-02) |
| MERGE-04 | Phase 3 | Complete |
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
