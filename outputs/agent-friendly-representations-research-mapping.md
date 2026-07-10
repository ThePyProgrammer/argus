# Mapping and Representation Literature

## Executive takeaways

- Agent-friendly swarm maps need more than a single occupancy grid. The literature converges on layered representations: metric geometry for collision checking, topology for routing and abstraction, semantics for task reasoning, and uncertainty/provenance for coordination under partial observability.
- Occupancy and metric maps remain the most robust substrate for navigation and exploration because they encode free/occupied/unknown space and support probabilistic fusion. Their weakness is that they are not intrinsically task-level: agents still need object, room, affordance, or connectivity abstractions.
- Multi-robot SLAM systems increasingly decouple local estimation from global/shared consistency. Centralized systems such as COVINS simplify global optimization but create server/bandwidth dependencies; decentralized systems such as Kimera-Multi and Swarm-SLAM reduce single points of failure but must explicitly manage inter-robot loop-closure validation, communication prioritization, and consistency.
- Scene graphs and semantic maps are the strongest candidates for agent-facing world models. 3D Dynamic Scene Graphs and Hydra show how objects, places, rooms, humans, and traversability can coexist in a hierarchical graph while preserving metric grounding.
- Communication constraints push swarm representations toward sparse, event-driven sharing: keyframes, descriptors, pose-graph constraints, frontier summaries, local submaps, object/place nodes, and uncertainty deltas instead of dense global maps.
- Dynamic environments remain under-solved. OctoMap explicitly supports probabilistic updates under sensor noise and environmental changes, and 3D Dynamic Scene Graphs include humans/moving agents, but long-term multi-robot consistency in nonstationary worlds is still a gap.
- Map fusion is not just geometric alignment. Occupancy-grid merging must solve unknown initial correspondences, map overlap, resolution differences, and fusion order; semantic and scene-graph fusion additionally need object identity, relation consistency, temporal validity, and conflict resolution.
- For Argus-style swarms, a practical representation stack would be: local probabilistic occupancy/ESDF maps; sparse pose graph and submap summaries for inter-robot exchange; topological place graph/frontier graph for coordination; semantic object/place/room graph for agent planning; uncertainty/provenance metadata on every shared assertion.

## Evidence table

| Claim | Source | Evidence | Relevance to agent-friendly swarm representations | Caveats |
|---|---|---|---|---|
| Probabilistic 3D occupancy maps are a strong low-level substrate for uncertain navigation. | Hornung et al., OctoMap (2013) | OctoMap is a 3D occupancy-grid mapping framework based on octrees, updates cells probabilistically, handles sensor noise and dynamic changes, and stores maps compactly. | Gives robots a compact, mergeable estimate of free/occupied/unknown volume for collision checking and exploration. | Occupancy alone lacks objects, goals, affordances, and high-level relations. Dynamic support is update-level, not full semantic temporal reasoning. |
| Occupancy-grid map merging remains useful but depends on correspondence, overlap, resolution, and feature quality. | Sunil et al., Feature-Based Occupancy Map-Merging (2023) | Uses KAZE keypoints, SIFT descriptors, MSAC/RANSAC-style outlier rejection, and Bayesian grid fusion; tested on real 2D LiDAR Qcars data and six-map hierarchical fusion. | Shows a concrete path for fusing local robot maps when initial relative poses are unknown. | KAZE is slow; SIFT rotation recovery can vary; randomized MSAC creates run-to-run variation; enough overlap/features are still needed. |
| Cooperative exploration needs localization, relative pose estimation, map merging, task allocation, and communication as one coupled system. | Wang et al., Multi-Robot System for Cooperative Exploration Survey (2025) | Survey organizes cooperative exploration modules around localization/mapping, global/relative pose estimation, multi-robot map merging, task assignment, motion planning, and limited communication. | Supports a layered architecture where representation, planning, and communication policies are co-designed rather than bolted together. | Survey-level evidence; detailed claims depend on the individual systems reviewed. |
| Dense metric-semantic maps can be built in fully distributed multi-robot SLAM. | Tian et al., Kimera-Multi (2021) | Fully distributed peer-to-peer system; rejects incorrect inter- and intra-robot loop closures; builds globally consistent metric-semantic 3D mesh with face annotations; communication-parsimonious. | Direct evidence that swarm maps can combine metric geometry, semantics, and distributed estimation. | Assumes visual-inertial sensing and loop-closure opportunities; dense semantic meshes may be expensive for large swarms. |
| Sparse decentralized SLAM explicitly addresses scalability and bandwidth by prioritizing inter-robot loop closures. | Lajoie and Beltrame, Swarm-SLAM (2023) | Open-source sparse decentralized C-SLAM for lidar, stereo, RGB-D, and inertial sensing; loop-closure prioritization reduces communication and accelerates convergence; evaluated on five datasets and a three-robot real experiment. | Suggests that agent-friendly shared maps should exchange the most informative constraints, not full raw maps. | Validation scale is modest relative to very large swarms; sparse SLAM gives structure, not full semantic task context by itself. |
| Centralized collaborative SLAM can scale to many agents but creates an architectural dependency on a server back end. | Schmuck et al., COVINS (2021) | Each agent runs onboard visual-inertial odometry and shares map data with a COVINS server, which performs global optimization, redundant-data removal, and collaborative estimation; reported with more than 10 agents and a 12-agent mission. | Useful baseline for global consistency and bandwidth/data-reduction design. | Central server is a bottleneck/single point of failure in degraded communication or adversarial settings. |
| 3D scene graphs unify metric, semantic, topological, and dynamic world state in a robot-actionable structure. | Rosinol et al., 3D Dynamic Scene Graphs (2020) | Represents entities and relations in layered graph form; includes places, structures, rooms, objects, robots, and humans; targets planning, decision-making, HRI, long-term autonomy, and scene prediction. | Strong template for an agent-facing world model that exposes objects/places/relations while staying grounded in SLAM geometry. | Validation emphasized photorealistic simulation; multi-robot fusion and large-scale distributed consistency are not the central contribution. |
| Online 3D scene-graph construction can maintain geometry, topology, rooms, loop closures, and graph optimization as the robot explores. | Hughes et al., Hydra (2022) | Real-time system builds 3D scene graphs from sensor data; maintains local ESDF, extracts topological places, segments rooms, detects loop closures, and optimizes graph layers with embedded deformation. | Demonstrates how a robot can continuously transform sensor data into a hierarchy useful for navigation and reasoning. | Primarily single-robot online perception; distributed multi-robot graph fusion remains additional work. |
| Building-scale 3D scene graphs provide object-room-camera relationships that are more queryable than raw 3D reconstructions. | Armeni et al., 3D Scene Graph (2019) | Proposes a 3D graph for entire buildings with objects, rooms, cameras, and relationships; uses multi-view consistency and building-scale structure. | Reinforces the value of relational map APIs for agents: queries over rooms, objects, viewpoints, containment, and adjacency. | Semi-automatic/offline pipeline; not designed as a real-time multi-robot SLAM system. |
| Semantic mapping surveys show that semantics are essential but heterogeneous: object maps, place labels, ontologies, metric-semantic maps, and topological-semantic maps differ in purpose. | Kostavelis and Gasteratos, Semantic Mapping Survey (2015) | Reviews semantic mapping for mobile robotics and representation types connecting geometric maps with object/place concepts. | Helps separate map layers by consumer: controllers need geometry; planners need topology; task agents need semantic entities and relations. | Older than target window but foundational; predates many deep-learning and scene-graph systems. |
| Multi-robot map fusion under partial observability should preserve uncertainty and provenance, not just a fused best estimate. | Kimera-Multi; Swarm-SLAM; OctoMap; cooperative exploration survey | These sources emphasize probabilistic updates, incorrect loop-closure rejection, sparse loop-closure prioritization, peer-to-peer or constrained communication, and incomplete unknown-environment exploration. | Agent decisions need confidence, source robot, timestamp, and conflict state to avoid over-trusting stale or contradictory maps. | Few systems expose uncertainty/provenance as a first-class agent API; often it remains internal to SLAM/fusion. |
| Topological/place abstractions reduce communication and planning burden while retaining navigational structure. | Hydra; 3D Dynamic Scene Graphs; cooperative exploration survey | Hydra extracts a topological map of places from ESDF and segments rooms; 3D Dynamic Scene Graphs model topology at multiple abstraction levels; exploration surveys emphasize task allocation and planning over partial maps. | Swarms can coordinate over frontiers, rooms, doors, corridors, and graph cutsets instead of dense grids. | Topological extraction can be brittle in open, cluttered, or changing environments; semantics and topology may disagree. |

## Detailed findings

### 1. Occupancy, metric, and ESDF maps: reliable local grounding

Occupancy grids remain the canonical representation for mobile robot navigation because they explicitly separate occupied, free, and unknown space. OctoMap extends this to 3D with an octree, making probabilistic volumetric mapping compact enough for robots. Its key contribution for swarms is not semantic richness, but reliable uncertainty-aware geometry. This matters because every higher-level representation eventually needs metric grounding for collision checks, frontier detection, sensor planning, and safety constraints.

The core limitation is abstraction. A cell grid cannot naturally express "the doorway to the kitchen is blocked by a person," "robot B already searched the storage room," or "this object is likely a charging station." It can encode local evidence for those claims, but not the relational claim itself. For agent-friendly representations, occupancy maps should be treated as a substrate rather than the whole world model.

ESDFs, as used in Hydra, are a useful intermediate: they support motion planning and distance queries while enabling extraction of places and topological structure. This suggests an implementation pattern for swarms: keep high-bandwidth ESDF/occupancy maps local, then share lower-bandwidth derived artifacts such as frontiers, place nodes, traversability summaries, and submap descriptors.

### 2. Map fusion: alignment, uncertainty, and conflict handling

Feature-based occupancy map merging demonstrates that even the apparently simple problem of fusing 2D occupancy grids involves hard correspondence questions. When robots start with unknown relative poses, systems must estimate transformations from partial overlapping maps. Sunil et al. use image-like feature extraction over occupancy grids, outlier rejection, and Bayesian fusion. The evidence is useful because it surfaces practical constraints: feature sparsity, low overlap, different grid resolutions, runtime costs, and randomness.

For swarms, this argues against treating "merge maps" as a primitive black box. A robust agent-facing map should expose whether a region is locally observed, transformed from another robot's frame, fused under uncertain alignment, or contradicted by another source. Without provenance, downstream agents may interpret a stitched map as ground truth.

### 3. Multi-robot SLAM architectures: centralized, decentralized, and hybrid tradeoffs

COVINS is a centralized collaborative visual-inertial SLAM system: each robot estimates locally and transmits map information to a server that performs global optimization and removes redundant data. This is attractive when communication to a base station is reliable and global consistency is more important than graceful degradation. It also provides a useful baseline for data reduction: agents need not share raw sensor streams if compact map/keyframe products suffice.

Kimera-Multi and Swarm-SLAM represent the decentralized direction. Kimera-Multi builds dense metric-semantic maps with peer-to-peer communication and robust loop-closure rejection. Swarm-SLAM emphasizes sparse decentralized SLAM, sensor flexibility, and inter-robot loop-closure prioritization to reduce communication and accelerate convergence. These systems point toward a swarm representation pattern: each robot owns a local map and shares only selected constraints, descriptors, and semantic/geometric summaries needed to improve common situational awareness.

The architectural implication is that agent-friendly maps should be separable into local truth, shared hypotheses, and globally optimized consensus. A planner should be able to ask: "What do I know locally? What did my peers report? What constraints support the merged frame? What is stale or uncertain?"

### 4. Semantic maps and scene graphs: strongest interface for agents

Semantic mapping connects geometry to meaningful entities. The older semantic mapping survey by Kostavelis and Gasteratos is still useful because it highlights representation heterogeneity: object-level maps, metric-semantic maps, topological-semantic maps, and ontology-like symbolic maps solve different problems.

Scene graphs go further by making relations first-class. Armeni et al. propose a building-scale 3D scene graph linking objects, rooms, cameras, and relationships. 3D Dynamic Scene Graphs bring this into robotics by layering places, structures, rooms, objects, humans, robots, and temporal/spatial relations. Hydra then shows an online robotic pipeline that builds a layered 3D scene graph from sensor data, including ESDF geometry, place topology, room segmentation, loop closure, and graph optimization.

For agents, these graph representations are far more queryable than raw maps. They support questions such as:

- Which unexplored rooms are adjacent to this corridor?
- Which robot last observed the blocked doorway?
- What objects are likely in this room?
- Which routes remain traversable under current uncertainty?
- Which semantic claims conflict with recent observations?

The remaining gap is distributed graph fusion. Single-robot scene graphs are already compelling; multi-robot, communication-constrained, uncertainty-aware scene-graph merging is less mature than pose-graph or occupancy-grid fusion.

### 5. Topological abstractions: essential for coordination

Topological maps compress navigation into places and connections. Hydra extracts a topological map of places from ESDFs and segments those places into rooms. 3D Dynamic Scene Graphs represent topology across abstraction levels. Multi-robot exploration surveys emphasize that robots coordinate under partial observability through task assignment, goal selection, and motion planning; these are naturally graph-level operations.

For swarms, topology is the representation layer most directly aligned with coordination. Robots can exchange "frontier node F is assigned to robot 3," "corridor edge E is blocked," or "room R is searched" instead of dense maps. Topology also provides a natural substrate for decentralized task allocation and communication scheduling.

However, topology can hide important metric constraints. A graph edge may exist but be too narrow, blocked, risky, or dynamically occupied. Agent-friendly topological maps should therefore carry metric affordances: traversability, clearance, distance/cost, confidence, last observed time, and semantic labels.

### 6. Uncertainty, partial observability, and dynamics

All swarm mapping is partial and stale by default. Occupancy mapping handles uncertainty probabilistically at the cell/voxel level. SLAM systems handle uncertainty through pose graphs, loop closures, and robust rejection of bad constraints. Exploration surveys frame unknown environments as inherently partial-observable and communication-limited. Scene graphs add semantic and relational uncertainty, but the literature less consistently exposes that uncertainty to downstream agents.

Dynamic environments intensify the problem. OctoMap can update probabilities as observations change, and 3D Dynamic Scene Graphs model humans and moving agents. But there is still a representation gap between "a cell probability changed" and "this hallway is temporarily blocked by a moving human; wait or reroute." Agent-facing maps should explicitly model temporal validity, moving entities, stale evidence, and persistence assumptions.

### 7. Communication constraints and map products

The most relevant multi-robot systems point away from dense all-to-all map sharing. COVINS shares map information with a central server and removes redundant data. Kimera-Multi is parsimonious with communication and peer-to-peer. Swarm-SLAM explicitly prioritizes inter-robot loop closures to reduce communication.

This suggests a hierarchy of shareable products:

1. Very sparse: robot pose/status, frontier claims, task assignments.
2. Sparse SLAM: keyframes, descriptors, selected loop-closure candidates, pose-graph constraints.
3. Local submaps: occupancy/ESDF tiles, compressed map patches, local semantic detections.
4. Semantic/topological summaries: place nodes, doors, rooms, object nodes, traversability edges.
5. Dense shared products: metric-semantic mesh or global occupancy map when bandwidth allows.

An agent-friendly swarm should degrade gracefully down this hierarchy as communication worsens.

## Contradictions / gaps

- Dense semantic maps versus sparse communication: Agent reasoning benefits from rich scene graphs and metric-semantic meshes, but swarm communication benefits from sparse loop closures and summaries. The literature has good examples of both, but fewer mature systems that optimize both simultaneously.
- Centralized consistency versus decentralized resilience: COVINS-style centralized optimization gives clean global maps; Swarm-SLAM and Kimera-Multi prioritize decentralized operation. The right representation may need both: local-first maps with opportunistic global consensus.
- Occupancy uncertainty is mature; semantic uncertainty is less exposed. Probabilistic occupancy grids and robust pose-graph methods explicitly manage uncertainty, but object/room/relation confidence, provenance, and temporal decay are often not first-class APIs.
- Dynamic environments are represented unevenly. 3D Dynamic Scene Graphs include moving agents, and OctoMap supports updates under environmental change, but long-horizon multi-robot map consistency with moving objects, changing traversability, and stale peer reports is still weak.
- Scene-graph fusion is underdeveloped compared with pose-graph fusion. Multi-robot systems robustly reject bad loop closures, but equivalent distributed mechanisms for object identity, room identity, semantic contradictions, and relation conflicts are less standardized.
- Topological maps help planning but can lose safety-critical metric detail. A swarm world model needs both graph-level abstraction and metric affordances on edges/nodes.
- Evaluation scales remain limited. Several systems report strong dataset results or small-team real-world experiments, but very large heterogeneous swarms under intermittent communication remain less validated.
- Agent-facing APIs are rarely the evaluation target. Papers optimize mapping accuracy, SLAM consistency, runtime, or communication, but less often measure how well downstream autonomous agents can query, plan, negotiate, and recover from wrong map beliefs.

## Source list

1. Armin Hornung, Kai M. Wurm, Maren Bennewitz, Cyrill Stachniss, Wolfram Burgard. "OctoMap: An Efficient Probabilistic 3D Mapping Framework Based on Octrees." Autonomous Robots, 2013. DOI: https://doi.org/10.1007/s10514-012-9321-0. Project: https://octomap.github.io/
2. Sooraj Sunil, Saeed Mozaffari, Rajmeet Singh, Behnam Shahrrava, Shahpour Alirezaee. "Feature-Based Occupancy Map-Merging for Collaborative SLAM." Sensors, 2023. DOI: https://doi.org/10.3390/s23063114. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC10055820/
3. Chuqi Wang, Chao Yu, Xin Xu, Yuman Gao, Xinyi Yang, Wenhao Tang, Shu'ang Yu, Yinuo Chen, Feng Gao, ZhuoZhu Jian, Xinlei Chen, Fei Gao, Boyu Zhou, Yu Wang. "Multi-Robot System for Cooperative Exploration in Unknown Environments: A Survey." arXiv, 2025. https://arxiv.org/abs/2503.07278
4. Yulun Tian, Yun Chang, Fernando Herrera Arias, Carlos Nieto-Granda, Jonathan P. How, Luca Carlone. "Kimera-Multi: Robust, Distributed, Dense Metric-Semantic SLAM for Multi-Robot Systems." arXiv, 2021. https://arxiv.org/abs/2106.14386
5. Pierre-Yves Lajoie, Giovanni Beltrame. "Swarm-SLAM: Sparse Decentralized Collaborative Simultaneous Localization and Mapping Framework for Multi-Robot Systems." arXiv, 2023. https://arxiv.org/abs/2301.06230
6. Patrik Schmuck, Thomas Ziegler, Marco Karrer, Jonathan Perraudin, Margarita Chli. "COVINS: Visual-Inertial SLAM for Centralized Collaboration." arXiv, 2021. https://arxiv.org/abs/2108.05756
7. Antoni Rosinol, Arjun Gupta, Marcus Abate, Jingnan Shi, Luca Carlone. "3D Dynamic Scene Graphs: Actionable Spatial Perception with Places, Objects, and Humans." arXiv, 2020. https://arxiv.org/abs/2002.06289
8. Nathan Hughes, Yun Chang, Luca Carlone. "Hydra: A Real-time Spatial Perception System for 3D Scene Graph Construction and Optimization." arXiv, 2022. https://arxiv.org/abs/2201.13360
9. Iro Armeni, Zhi-Yang He, JunYoung Gwak, Amir R. Zamir, Martin Fischer, Jitendra Malik, Silvio Savarese. "3D Scene Graph: A Structure for Unified Semantics, 3D Space, and Camera." arXiv, 2019. https://arxiv.org/abs/1910.02527
10. Ioannis Kostavelis, Antonios Gasteratos. "Semantic Mapping for Mobile Robotics Tasks: A Survey." Robotics and Autonomous Systems, 2015. DOI: https://doi.org/10.1016/j.robot.2015.06.006
11. Hugh Durrant-Whyte, Tim Bailey. "Simultaneous Localization and Mapping: Part I." IEEE Robotics & Automation Magazine, 2006. DOI: https://doi.org/10.1109/MRA.2006.1638022
12. Tim Bailey, Hugh Durrant-Whyte. "Simultaneous Localization and Mapping (SLAM): Part II." IEEE Robotics & Automation Magazine, 2006. DOI: https://doi.org/10.1109/MRA.2006.1678144
