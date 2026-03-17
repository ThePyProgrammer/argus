# Feature Landscape

**Domain:** Multi-Robot Autonomous Exploration & 3D Reconstruction (Simulation)
**Researched:** 2026-03-17
**Confidence:** MEDIUM-HIGH (DimOS docs verified locally; domain knowledge well-established; SimWorld specifics LOW)

## Table Stakes

Features users expect. Missing = system does not function as a multi-robot 3D reconstruction pipeline.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Two Go2 robots spawn and operate in SimWorld** | Fundamental requirement -- multi-robot is the project's reason to exist | Medium | SimWorld gym supports multi-agent via `world_buffer.py`. DimOS fleet mode exists but is broadcast-only (see PITFALLS.md) -- use separate blueprint instances instead. |
| **SimWorld gym bridge as DimOS Module** | Everything flows from this. Without sensor data, no SLAM, no map, no exploration. | Medium | Custom `SimWorldGymConnection` Module that calls `env.step()` and publishes observations as typed DimOS streams (Image, DepthImage, Pose). |
| **Per-robot SLAM producing local 3D map** | Core SLAM is the atomic unit. No map merge without local maps. | High | RTAB-Map v0.23.1 consuming RGB-D data. One instance per robot. Produces registered point clouds and corrected poses. |
| **Odometry estimation** | SLAM needs pose input between frames. | Low | SimWorld gym likely provides ground-truth poses. Use directly for MVP; swap to visual odometry later for realism. |
| **Occupancy grid for navigation** | Robots cannot plan paths without knowing free/occupied space. | Medium | OctoMap v1.10.0 from RTAB-Map point clouds. 2D projection for frontier detection and path planning. |
| **Point cloud output** | Stated requirement for 3D reconstruction visualization. | Medium | RTAB-Map produces dense point clouds from RGB-D. Open3D for voxel downsampling and processing. |
| **Merged map from both robots** | Core value proposition: "two robots, one map." | High | RTAB-Map multi-session mode with inter-session loop closure. Known spawn transforms simplify alignment in simulation. |
| **Autonomous frontier-based exploration** | Robots must explore without human input. Frontier-based is the proven baseline. | High | Detect frontier cells (boundary between known-free and unknown) on the occupancy grid. Select nearest/largest frontier as navigation goal. Yamauchi 1997, well-understood. |
| **Path planning and obstacle avoidance** | Robots must navigate to goals without collisions. | Medium | DimOS already has `--planner-strategy` and obstacle avoidance (`--obstacle-avoidance true`). Extend for frontier goals. A* on occupancy grid for global, DWA/potential field for local. |
| **Split-room coverage strategy** | Stated requirement: robots divide the space and explore different areas. | Medium | Voronoi partitioning based on robot positions. Each robot targets frontiers only within its assigned region. |
| **Real-time incremental map updates** | Stated constraint: "map must build live, not post-processed." | Medium | Publish incremental map deltas (new voxels/points since last update). Avoid republishing entire accumulated map each frame. |
| **DimOS agent orchestration** | Project constraint: DimOS coordinates robots. | Medium | LangGraph agent with @skill-decorated exploration methods. Agent handles high-level task allocation. |

## Differentiators

Features that set the system apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **LLM-driven task reallocation** | If one robot finishes early or gets stuck, agent reassigns regions intelligently. | Low | DimOS agent already supports LangGraph + GPT-4o. Add exploration-aware system prompt and reallocation skills. |
| **Live Rerun 3D visualization** | Watch the map build in real-time from a browser. Compelling demo. | Low | DimOS already has `rerun_bridge()`. Add point cloud + occupancy + robot pose + frontier logging to Rerun. |
| **Dynamic re-partitioning** | Static region splits waste time if areas are asymmetric. Dynamic re-partition adapts. | Medium | Monitor frontier counts per partition. When one robot exhausts its region, reassign remaining frontiers. |
| **Exploration progress metrics** | Quantify "X% of environment explored." Know when to stop. | Low | Compare known-free volume vs total bounding box in OctoMap. SimWorld may provide ground truth for precise calculation. |
| **Frontier visualization** | Debug and demo: see where robots want to explore next in Rerun. | Low | Log frontier cells as colored points in Rerun. Color-code by assigned robot. |
| **Ground-truth comparison** | Automatically evaluate reconstruction quality vs SimWorld's known geometry. | Medium | Key advantage of simulation. Extract GT mesh from UE5, compute chamfer distance, completeness, accuracy. |
| **Mesh reconstruction** | Surface mesh from merged point cloud. Visually superior to raw points. | Medium | Poisson or marching cubes on final point cloud. Can run as periodic background process. |
| **Adaptive exploration speed** | Slow in complex areas (more features), fast in open areas. | Low | Modulate Go2 velocity based on frontier density or point cloud density. Simple heuristic. |
| **Inter-robot loop closure** | When Robot A visits Robot B's territory, detect and refine the joint map. | High | Requires cross-robot place recognition (DBoW2 or similar). Triggers joint pose graph optimization. Major accuracy improvement but significant complexity. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Custom SLAM algorithm** | SLAM is mature. Writing one wastes months and produces worse results than RTAB-Map. | Use RTAB-Map 0.23.1. Focus effort on multi-robot coordination, which is the novel part. |
| **Custom UE5 scene creation** | Out of scope per PROJECT.md. Massive effort, marginal value. | Use SimWorld's existing procedural urban environments. Different seeds for variety. |
| **Post-processing refinement** | Contradicts real-time requirement. Complexity without core value. | If map quality is poor, improve real-time pipeline (better SLAM params, denser keyframes). |
| **Semantic mapping** | Kimera-style semantic annotation is orthogonal to geometric reconstruction goal. | Output geometry only (occupancy grid + point cloud). Semantic layers can be added later. |
| **Vision-language navigation** | Different task per PROJECT.md (MMNav benchmark is separate). | Use frontier-based exploration, not language-guided navigation. |
| **Realistic communication model** | Simulating packet loss and bandwidth is a networking project, not a mapping project. | Use direct shared-memory communication. Add degradation layer later if needed. |
| **Hardware-realistic sensor noise** | Rabbit hole that does not help the core demo. Simulation-only project. | Use SimWorld sensor output as-is. Document sim-specific parameters for future retuning. |
| **3+ robot scaling** | Adds coordination complexity for no immediate value. Two robots demonstrate multi-robot sufficiently. | Design for extensibility (parameterize, don't hardcode "2") but only test/optimize for two. |
| **Traffic system integration** | Not relevant for indoor-like survey per PROJECT.md. | Ignore SimWorld's traffic features entirely. |

## Feature Dependencies

```
SimWorld Gym Bridge (Module)
  |
  +---> RGB Image Stream
  +---> Depth Image Stream  ----> Depth-to-PointCloud Processor
  +---> Ground Truth Pose Stream       |
  +---> Odometry Stream                v
           |                     SLAM Node (RTAB-Map per robot)
           |                        |
           |                        +---> Corrected Pose
           |                        +---> Registered Point Cloud
           |                                    |
           |                                    v
           |                             Local Map Builder
           |                                |          |
           |                                v          v
           |                         Occupancy Grid   Point Cloud Map
           |                                |
           |                                v
           |                         Frontier Detection
           |                                |
           v                                v
    Robot Navigation  <--------  Exploration Planner (assigns goals)
                                        ^
                                        |
                                 Map Merge Server
                                   ^          ^
                                   |          |
                            Robot A Map   Robot B Map

DimOS Agent (LangGraph) orchestrates:
  - Initial region assignment (split-room)
  - Dynamic re-partitioning (if implemented)
  - Exploration start/stop/status
```

## MVP Recommendation

**Phase 1 -- SimWorld Bridge (get sensor data flowing):**
1. SimWorld gym wrapper DimOS Module
2. Verify sensor data formats (RGB, depth, pose)
3. Single robot, raw sensor streaming + Rerun visualization
4. No SLAM yet -- just prove the bridge works

**Phase 2 -- Single-Robot SLAM (prove the pipeline):**
5. Depth-to-point-cloud processor
6. RTAB-Map integration (via ROS 2 bridge or Python bindings)
7. Occupancy grid generation (OctoMap)
8. Single robot mapping while manually driven

**Phase 3 -- Single-Robot Exploration (prove autonomy):**
9. Frontier detection on occupancy grid
10. Navigation goal selection
11. Full autonomous loop: explore -> detect frontier -> navigate -> repeat

**Phase 4 -- Second Robot (prove multi-agent):**
12. Duplicate pipeline with namespaced streams
13. Two independent SLAM instances
14. Frame alignment using known spawn transforms
15. Map merging (RTAB-Map multi-session or point cloud concatenation)

**Phase 5 -- Coordinated Exploration (the full system):**
16. Split-room region assignment
17. Per-robot frontier filtering (only frontiers in assigned region)
18. Unified merged map as output

**Phase 6 -- Polish:**
19. Full Rerun visualization dashboard
20. Performance tuning
21. DimOS agent integration for LLM-driven coordination (optional)
22. Ground-truth comparison metrics (optional)

**Defer indefinitely:**
- Inter-robot loop closure (only if merged map quality is visibly poor)
- Information-gain exploration (only if frontier-based takes too long)
- Mesh reconstruction (only if point cloud visualization is insufficient)
- Adaptive exploration speed (optimization, not core)

**Rationale:** Get one robot working end-to-end before adding multi-robot complexity. The SimWorld gym interface is the riskiest unknown and must be validated first. SLAM is the most technically complex single component and benefits from early development. Multi-robot aspects (Phases 4-5) are primarily integration work once single-robot is proven.

## Sources

- PROJECT.md requirements and constraints -- HIGH confidence
- DimOS documentation (fleet mode, agent skills, blueprints, navigation) -- HIGH confidence (verified from local docs/)
- RTAB-Map capabilities (v0.23.1, multi-session, ROS 2 Humble/Jazzy) -- HIGH confidence (verified via WebFetch)
- OctoMap capabilities (v1.10.0, octree occupancy) -- HIGH confidence (verified via WebFetch)
- Frontier-based exploration (Yamauchi 1997) -- HIGH confidence (established algorithm)
- SimWorld multi-agent gym API -- LOW confidence (inferred from PROJECT.md, not independently verified)

---

*Feature research: 2026-03-17*
