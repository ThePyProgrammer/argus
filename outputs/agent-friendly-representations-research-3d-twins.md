# 3D Twins, Point Clouds, NeRFs, and Gaussian Splats

## Executive takeaways

1. Build 3D twins and related 3D maps because robots need a persistent spatial substrate that is richer than per-frame perception: localization, obstacle checking, collision prediction, reconstruction, human/operator visualization, fleet coordination, and simulation/replanning all consume scene state. Classical point-cloud, voxel, occupancy, TSDF/ESDF, and mesh maps remain the most directly useful for planning because they expose geometry, free/occupied space, distances, and collision surfaces in forms planners can query.
2. Neural representations such as NeRFs and 3D Gaussian splats are valuable because they preserve dense appearance and geometry, support novel-view rendering, and can fill gaps where raw point clouds or sparse maps are incomplete. In robotics literature they are mainly consumed by SLAM/tracking, localization, reconstruction, view synthesis, active perception, navigation/planning, interaction/manipulation, and scene-understanding modules. They are not usually direct action policies or symbolic task models.
3. Agent-readability is representation-dependent. Occupancy grids, ESDFs, meshes, and explicit Gaussian maps expose queryable state and are closer to agent-readable geometry. NeRFs are continuous implicit fields optimized for differentiable rendering; robots normally need derived abstractions such as depth, occupancy, signed distance, collision geometry, semantic labels, traversability, object handles, scene graphs, or planner cost maps. Gaussian splats sit between these extremes: explicit primitives are more inspectable than MLP weights, but downstream agents still usually require derived occupancy, surfaces, segmentation, semantics, uncertainty, or cost layers.
4. Multi-robot and swarm settings make the reason for 3D twins sharper: a shared twin can serve as a synchronized world model for task allocation, predictive collision checking, communication-aware navigation, operator awareness, and sim-to-real testing. The caveat is bandwidth and consistency: raw point clouds, dense meshes, NeRFs, and splat maps are too heavy to broadcast naively, so practical systems exchange submaps, compressed summaries, object/task states, occupancy layers, or planner-relevant deltas.
5. The strongest evidence is not that “agents read 3D twins directly,” but that many robotics modules read specific projections of them. The agent-facing interface is usually a derived API: nearest obstacle distance, free-space query, pose graph, semantic object list, traversability map, collision check, rendered view, or simulation state.

## Evidence table

| Claim | Source | Evidence | Downstream consumer | Agent-readability implication | Caveats |
|---|---|---|---|---|---|
| ESDF/TSDF maps are built because planners need fast distance-to-obstacle and collision information, not just visual reconstruction. | Oleynikova et al., “Voxblox: Incremental 3D Euclidean Signed Distance Fields for On-Board MAV Planning,” arXiv:1611.03631 | Voxblox incrementally builds ESDFs from TSDFs onboard and targets real-time MAV replanning; it explicitly connects ESDFs to a trajectory-optimization local planner and TSDFs to surface meshes. | Local trajectory optimization, collision avoidance, MAV replanning, operator/human mission planning via mesh outputs. | Highly agent-readable at the planning layer: ESDF queries directly answer “how far to collision?”; TSDF/mesh can be converted to surfaces. | Older than the requested NeRF/splat period, but foundational for why geometric 3D maps matter. |
| Probabilistic 3D occupancy maps are useful because robots need compact, updatable free/occupied-space estimates over unknown extents. | OctoMap project; Hornung et al., “OctoMap: An Efficient Probabilistic 3D Mapping Framework Based on Octrees,” Autonomous Robots 2013 | OctoMap describes full 3D occupancy grid mapping for robotics with probabilistic updates, dynamic extent, multi-resolution, and compact storage; ROS integration is explicitly supported. | Navigation, exploration, collision checking, mapping, ROS perception stacks. | Occupancy is relatively agent-readable because cells expose free/occupied/unknown state; higher-level agents still need traversability, costs, objects, or semantic annotations. | Occupancy maps do not preserve rich appearance or object semantics by themselves. |
| NeRFs are built as continuous scene representations for dense view synthesis and compact appearance/geometry modeling, but the original formulation is not a robotics control interface. | Mildenhall et al., “NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis,” ECCV 2020, arXiv:2003.08934 | NeRF maps 3D position and viewing direction to density/color and renders novel views from posed images. | Novel-view rendering, dense reconstruction, perception pre-processing. | Not directly agent-readable: an agent needs rendering, depth extraction, occupancy/SDF conversion, or task abstractions. | Original paper is computer-vision oriented, not a robotics pipeline. |
| Robotics NeRF surveys identify downstream consumers across perception, localization/navigation, SLAM, planning, interaction, and decision-making. | Ming et al., “Benchmarking Neural Radiance Fields for Autonomous Robots: An Overview,” arXiv:2405.05526 | Survey summary names perception, localization and navigation, decision-making, 3D reconstruction, segmentation, pose estimation, SLAM, navigation/planning, and interaction. | Robot perception, SLAM, localization, navigation/planning, interaction, decision-making. | NeRF is a substrate; agent-readable products are task outputs such as depth, segmentation, pose, cost, and planned actions. | Survey-level evidence; individual methods vary widely in real-time performance and robustness. |
| NeRF robotics literature treats NeRFs as promising due to continuous models and low memory, but deployability remains a challenge. | Wang et al., “NeRFs in Robotics: A Survey,” IJRR 2025 / arXiv:2405.01333 | Survey states NeRFs offer simplified mathematical models, low memory footprint, and continuous scene representations; it separates robotics applications from method improvements needed for deployment. | Perception and interaction tasks; method improvements for real robot deployment. | Continuous fields are compact but indirect; robots usually need query wrappers or derived representations. | Survey abstract does not establish that NeRFs are broadly deployed in production robots. |
| Neural implicit SLAM maps can support tracking and map updating, but the learned representation is scene-specific and not a symbolic world model. | Sucar et al., “iMAP: Implicit Mapping and Positioning in Real-Time,” arXiv:2103.12352 | iMAP uses one MLP as the sole scene representation for online RGB-D SLAM, supporting live tracking and global map updating. | Camera tracking/localization, dense mapping, online reconstruction. | Less directly agent-readable: useful for localization/reconstruction, but planners need extracted geometry/occupancy/SDF/mesh. | Real-time claims are tied to specific online optimization and RGB-D assumptions. |
| Scalable implicit SLAM improves dense reconstruction/tracking, but hierarchical neural encodings still need downstream extraction for planning or symbolic decisions. | Zhu et al., “NICE-SLAM: Neural Implicit Scalable Encoding for SLAM,” CVPR 2022 / arXiv:2112.12130 | NICE-SLAM adds hierarchical local information and geometric priors for scalable dense SLAM, reporting strong tracking and mapping. | Tracking, mapping, dense reconstruction. | More spatially structured than a single global MLP, but still not a direct agent command/state abstraction. | Focuses on SLAM quality rather than downstream robot autonomy interfaces. |
| 3D Gaussian Splatting is attractive for robotics because it is explicit and real-time renderable compared with implicit neural fields. | Kerbl et al., “3D Gaussian Splatting for Real-Time Radiance Field Rendering,” SIGGRAPH 2023 / arXiv:2308.04079 | Represents scenes as explicit anisotropic 3D Gaussians seeded from sparse points and optimized for real-time high-quality rendering. | View synthesis, reconstruction, visibility reasoning, map visualization; later robotics systems use it in SLAM. | More inspectable than opaque MLP weights; still needs conversion or augmentation for collision, semantics, and planning. | Original source is rendering-focused, not a robotics system. |
| Gaussian-splat SLAM systems consume splats for tracking, mapping, pose estimation, reconstruction, and novel-view synthesis. | Keetha et al., “SplaTAM: Splat, Track & Map 3D Gaussians for Dense RGB-D SLAM,” CVPR 2024 / arXiv:2312.02126 | SplaTAM uses explicit 3D Gaussian maps for online RGB-D SLAM, supporting tracking/localization, map construction, pose estimation, and novel-view synthesis. | Dense RGB-D SLAM, camera pose estimation, reconstruction, view synthesis. | Explicit Gaussian primitives make map state more inspectable and updatable, but agents still need task-level abstractions. | RGB-D setting; performance and robustness depend on sensor assumptions and scene conditions. |
| Other Gaussian-splat SLAM work emphasizes adaptive map growth/pruning, coarse-to-fine pose tracking, and dense reconstruction. | Yan et al., “GS-SLAM: Dense Visual SLAM with 3D Gaussian Splatting,” CVPR 2024 / arXiv:2311.11700 | GS-SLAM ties differentiable splatting to SLAM, adaptive Gaussian growth/pruning, coarse-to-fine pose tracking, and tests on Replica/TUM-RGBD. | Real-time dense SLAM, RGB-D mapping, camera pose tracking, scene reconstruction. | Agent can query/render/update a structured map more easily than with a pure implicit field; planning still needs collision/occupancy derivations. | Abstract-level evidence only here; author-reported benchmarks. |
| Compact Gaussian SLAM responds to a robotics constraint: redundant splats increase memory/storage and slow training. | Deng et al., “Compact 3D Gaussian Splatting For Dense Visual SLAM,” arXiv:2403.11247 | The paper targets fewer/smaller Gaussian ellipsoids with sliding-window masking, geometry codebook compression, and global BA; it identifies high memory/storage as a problem in prior 3DGS SLAM. | Dense visual SLAM, pose estimation, reconstruction, real-time rendering on resource-limited robots. | Compression makes splat maps more plausible for robot/fleet use, but compressed radiance primitives are still not planner semantics. | Later revisions extend beyond 2024; still a fast-moving area. |
| Robotics 3DGS surveys frame splats around scene understanding and interaction, with open challenges in adaptability and efficiency. | Zhu et al., “3D Gaussian Splatting in Robotics: A Survey,” arXiv:2410.12262 | Survey calls 3DGS an explicit representation using Gaussian primitives and differentiable rendering, promising due to real-time rendering and photorealism; groups work around scene understanding and interaction. | Scene understanding, interaction, mapping/SLAM-related robotics applications. | Explicit primitives improve inspectability, but “understanding” requires semantics/features beyond raw radiance splats. | Survey-level; field is young and terminology is still stabilizing. |
| Digital twins in multi-robot planning are used as predictive simulation/collision-checking substrates rather than direct policy brains. | Shaarawy et al., “Hybrid Task and Motion Planning with Reactive Collision Handling for Multi-Robot Disassembly of Complex Products,” arXiv:2509.21020 | The abstract says the safety layer uses predictive collision checking in a MoveIt/FCL digital twin plus reactive vision-based avoidance and replanning. | Multi-robot task-and-motion planning, collision checking, safety layer, EV battery disassembly. | Agent reads twin through collision-checking and planner APIs, not by consuming a raw mesh/point cloud directly. | Application-specific dual-agent disassembly; not a general swarm benchmark. |
| Multi-robot digital-twin systems use shared virtual environments for route planning, anomaly detection, and communication-aware coordination. | Yang et al., “Advancing Multi-Robot Networks via MLLM-Driven Sensing, Communication, and Computation,” arXiv:2604.00061 | Survey includes an end-to-end “digital-twin warehouse navigation” demo with predictive link context and discusses multi-robot sensing/communication/compute orchestration. | Fleet route planning, warehouse navigation, anomaly detection, communication/resource orchestration. | The twin is an orchestration context; agents need distilled route, link, anomaly, task, or resource signals. | 2026 survey/demo evidence; outside 2020-2026 preference but at edge of current-date corpus and not a single validated deployment. |
| Broad robotics representation surveys converge on a division of labor: sparse/geometric maps dominate localization/SLAM, dense/neural maps support navigation, manipulation, semantics, and richer interaction. | Deng et al., “What Is The Best 3D Scene Representation for Robotics? From Geometric to Foundation Models,” arXiv:2512.03422 | Survey covers point clouds, voxels, SDFs, scene graphs, NeRFs, 3DGS, and foundation models; organizes robot functions as perception, mapping, localization, navigation, manipulation. | Whole robotics stack: perception, mapping, localization, navigation, manipulation. | No single representation is universally agent-readable; systems layer abstractions and APIs over lower-level maps. | Survey abstract-level evidence; some listed 2025/2026 sources may be preprint-only. |

## Detailed findings

### 1. Why build 3D twins and 3D scene representations?

Robotics builds 3D twins, point-cloud maps, meshes, NeRFs, and Gaussian-splat maps for three overlapping reasons.

**First, robots need persistent geometry.** A robot cannot plan or coordinate solely from a camera frame; it needs a spatial memory of free space, obstacles, surfaces, and sometimes object geometry. Classical mapping systems solve this explicitly. OctoMap exposes probabilistic free/occupied/unknown space over an octree. Voxblox goes further for motion planning by converting TSDF observations into ESDFs, where each query can return distance to the nearest obstacle. Those are not just visual artifacts; they are data structures designed for collision checking and trajectory optimization.

**Second, robots need shared simulation and prediction.** A digital twin is valuable when the system must reason about actions before execution: collision prediction, task-and-motion planning, operator supervision, safety monitors, or fleet scheduling. In the multi-robot EV battery disassembly example, the MoveIt/FCL digital twin is consumed by a predictive collision-checking safety layer, while live vision handles reactive avoidance and replanning. In fleet/warehouse settings, a digital twin can act as the common world state for route planning, anomaly detection, communication-aware orchestration, and operator awareness.

**Third, newer neural and splat representations try to preserve appearance-rich, dense, continuous structure.** Point clouds and occupancy grids are planner-friendly but can be sparse, noisy, and semantically thin. NeRFs provide continuous density/color fields and high-quality novel views. 3D Gaussian splats preserve an explicit primitive set while enabling differentiable, real-time rendering. That makes them attractive for dense SLAM, active perception, teleoperation visualization, robot learning data generation, and scene-understanding pipelines.

### 2. Point clouds, voxels, meshes, TSDFs, and ESDFs

Point clouds are often the raw or intermediate output from LiDAR, RGB-D cameras, stereo, or multi-view reconstruction. They are useful for registration, scan matching, obstacle detection, and surface reconstruction, but a raw point cloud is rarely the final agent-facing state. It usually gets converted into:

- occupancy grids or octrees for free/occupied/unknown queries;
- TSDFs for surface fusion and mesh extraction;
- ESDFs for fast distance-to-obstacle queries;
- meshes for simulation, collision checking, visualization, or inspection;
- object-level or semantic maps for task planning.

The downstream consumer determines the useful abstraction. A trajectory optimizer wants ESDF gradients/costs. A collision checker wants mesh or primitive geometry. A global planner may want occupancy or traversability. A manipulation planner may want object poses, support surfaces, and collision volumes. A human operator may want a textured mesh or rendered twin. A symbolic task planner usually wants a distilled list of objects, rooms, affordances, constraints, and predicates rather than raw points.

For agent-readability, geometric maps are the strongest baseline. Occupancy, ESDF, and mesh queries can be wrapped as deterministic APIs. However, they still lack high-level semantics. An LLM-like planner, behavior tree, or task allocator will not typically reason over millions of points; it will consume derived facts such as “aisle A blocked,” “bin pose = X,” “nearest obstacle distance = 0.8 m,” or “frontier region unexplored.”

### 3. Digital twins in robotics and multi-robot pipelines

A robotics digital twin is best understood as a live or periodically synchronized model of the physical system plus environment, not merely a pretty 3D asset. It can include robot kinematics, collision geometry, sensors, maps, object states, task state, communications, and simulation dynamics.

Downstream consumers include:

- task-and-motion planners using the twin for feasibility and collision checks;
- safety monitors comparing predicted and observed state;
- multi-robot task allocators using shared world/task state;
- fleet managers and route planners using map plus communication context;
- simulation and synthetic-data tools;
- human operators using XR/visualization layers;
- anomaly detectors comparing expected and observed behavior.

The key implication is that the twin is normally consumed through service interfaces. A planner calls a collision checker or simulator; it does not “read” a mesh in a cognitively meaningful way. In multi-robot systems, the twin also mediates bandwidth: agents cannot always share raw dense maps, so they exchange submaps, compressed geometry, map deltas, object states, task state, or planner-relevant summaries.

### 4. NeRFs in robotics

NeRFs model scenes as continuous radiance/density fields and are strongest at novel-view synthesis and dense scene reconstruction. Robotics surveys now tie NeRFs to perception, localization/navigation, SLAM, pose estimation, segmentation, navigation/planning, interaction, and decision-making. SLAM-oriented methods such as iMAP and NICE-SLAM show how neural implicit maps can become the live map used by tracking and reconstruction loops.

The agent-readability problem is sharper for NeRFs than for occupancy or ESDF maps. A NeRF can render an image from a candidate pose, and derivative methods can extract depth, density, or occupancy-like signals. But the raw representation is an optimized neural field, not a task graph, object map, traversability map, or collision checker. Downstream robotics modules therefore usually need one of the following wrappers:

- render candidate views for active perception or view planning;
- extract depth/occupancy/SDF for collision checking;
- estimate camera pose by photometric/geometric alignment;
- attach semantic or language features to field samples;
- distill object-level maps, affordances, or scene graphs;
- compute uncertainty/information gain for exploration.

So NeRFs are useful as a dense perceptual substrate. They are not, by default, directly readable by symbolic agents or controllers.

### 5. 3D Gaussian splats in robotics

3D Gaussian Splatting represents a scene as explicit anisotropic Gaussian primitives with position, covariance, opacity, and appearance parameters. Compared with NeRFs, the representation is more inspectable: it is a set of spatial primitives rather than only neural weights. It also supports fast differentiable rendering, which makes it attractive for online SLAM and dense reconstruction.

Robotics-oriented 3DGS systems consume splats in familiar SLAM loops:

- initialize/update a map from RGB-D, monocular, or multi-sensor observations;
- track camera pose against rendered or projected splats;
- grow, prune, and optimize Gaussian primitives;
- render novel views for supervision and evaluation;
- reconstruct dense environments for visualization or downstream reasoning.

SplaTAM, GS-SLAM, and Compact 3D Gaussian Splatting for Dense Visual SLAM illustrate the direction: splats become the dense map used by tracking, mapping, pose estimation, reconstruction, and rendering. Compact 3DGS work also exposes a practical robotics constraint: dense splat maps can be memory-heavy, so compression and pruning matter before splats become good fleet or onboard representations.

Agent-readability is better than NeRF but still incomplete. A robot can inspect Gaussian centers/covariances and potentially derive visibility or occupancy; however, raw splats do not automatically encode traversability, rigid-object identity, affordances, or task predicates. For planning and multi-agent coordination, splat maps still need derived collision geometry, semantic segmentation, object tracks, free-space maps, and uncertainty layers.

### 6. What downstream modules consume these representations?

Across the sources, the consumers cluster into the following modules:

1. **Localization and tracking:** pose estimation against point-cloud maps, implicit neural maps, or splat maps.
2. **SLAM and mapping:** maintaining a persistent map while estimating trajectory.
3. **Collision checking and motion planning:** querying occupancy, meshes, ESDFs, or digital-twin collision geometry.
4. **Navigation and exploration:** using occupancy/traversability/frontier/cost layers derived from 3D maps.
5. **Manipulation and task-and-motion planning:** using object poses, meshes, collision volumes, and simulated task state.
6. **Scene understanding:** segmentation, object recognition, semantic features, language-aligned labels, affordances.
7. **View planning and active perception:** rendering candidate views or evaluating information gain in neural/splat/twin maps.
8. **Multi-robot coordination:** shared maps/twins for task allocation, route planning, conflict detection, and communication/resource orchestration.
9. **Human/operator interfaces:** visual twins, meshes, splat/NeRF renderings, XR overlays.
10. **Training/simulation:** synthetic data, sim-to-real evaluation, policy training, predictive safety checks.

The same low-level representation can feed multiple consumers, but usually only after conversion. A mesh may feed both visualization and collision checking. A NeRF may feed both pose tracking and view planning through rendered images/depth. A digital twin may feed both task allocation and safety checking through separate APIs.

### 7. Are these directly agent-readable?

A useful scale is:

- **Most directly agent-readable:** occupancy grids, ESDFs, object poses, collision APIs, planner cost maps, semantic maps, scene graphs, task-state databases. These expose discrete or queryable facts and costs.
- **Moderately readable:** meshes, point clouds, TSDFs, Gaussian splats. They are spatial and explicit, but agents typically need wrappers for nearest surfaces, collisions, free space, object segmentation, or semantics.
- **Least directly readable:** raw NeRF/implicit neural fields. They are powerful perceptual memories but require rendering, sampling, extraction, or learned query heads before a planner or high-level agent can use them.

The practical answer is therefore: build 3D representations as substrate, then derive agent-facing abstractions. A robot policy, swarm coordinator, or task planner rarely consumes a raw 3D twin. It consumes services backed by that twin: “is path collision-free?”, “where is object X?”, “what areas are unexplored?”, “what is the predicted link quality on route R?”, “what view should robot B take next?”, or “can arm 2 reach the bolt without colliding?”

## Contradictions / gaps

1. **Rendering quality vs. planning utility.** NeRF and 3DGS papers emphasize photorealistic rendering and reconstruction, while planners need conservative free-space, geometry, uncertainty, and dynamics. A high-quality rendering representation is not automatically a safe planning map.
2. **Explicit does not mean semantic.** Gaussian splats are more explicit than NeRFs, but raw splat primitives are not object identities or affordances. They still need segmentation/semantic layers for task agents.
3. **Digital twin definitions vary.** Some sources use “digital twin” for full synchronized cyber-physical systems; others use it for a simulation/collision-checking world model. This makes cross-paper comparison imprecise.
4. **Multi-robot evidence is thinner than single-robot SLAM evidence.** Dense 3D neural/splat mapping is active in single-robot SLAM, but robust shared NeRF/3DGS maps for swarms remain less mature, especially under bandwidth limits and dynamic scenes.
5. **Benchmarks often stop before downstream autonomy.** Many papers report reconstruction, PSNR/rendering, ATE, or mapping metrics. Fewer show end-to-end gains in task success, collision rate, exploration efficiency, or multi-robot throughput.
6. **Dynamic scenes remain hard.** Digital twins and robot maps must handle moving objects, changing workspaces, and non-rigid structure. Static reconstruction metrics understate this issue.
7. **Agent interfaces are under-specified.** Papers often say a representation supports “navigation,” “interaction,” or “decision-making,” but do not always specify the exact API between the 3D map and the planner/controller.

## Source list

1. Ben Mildenhall, Pratul P. Srinivasan, Matthew Tancik, Jonathan T. Barron, Ravi Ramamoorthi, Ren Ng. “NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis.” ECCV 2020. arXiv: https://arxiv.org/abs/2003.08934
2. Edgar Sucar, Shikun Liu, Joseph Ortiz, Andrew J. Davison. “iMAP: Implicit Mapping and Positioning in Real-Time.” ICCV 2021. arXiv: https://arxiv.org/abs/2103.12352
3. Zihan Zhu, Songyou Peng, Viktor Larsson, Weiwei Xu, Hujun Bao, Zhaopeng Cui, Martin R. Oswald, Marc Pollefeys. “NICE-SLAM: Neural Implicit Scalable Encoding for SLAM.” CVPR 2022. arXiv: https://arxiv.org/abs/2112.12130
4. Helen Oleynikova, Zachary Taylor, Marius Fehr, Roland Siegwart, Juan Nieto. “Voxblox: Incremental 3D Euclidean Signed Distance Fields for On-Board MAV Planning.” IROS 2017. arXiv: https://arxiv.org/abs/1611.03631
5. Armin Hornung, Kai M. Wurm, Maren Bennewitz, Cyrill Stachniss, Wolfram Burgard. “OctoMap: An Efficient Probabilistic 3D Mapping Framework Based on Octrees.” Autonomous Robots 2013. Project: https://octomap.github.io/ DOI: https://doi.org/10.1007/s10514-012-9321-0
6. Bernhard Kerbl, Georgios Kopanas, Thomas Leimkühler, George Drettakis. “3D Gaussian Splatting for Real-Time Radiance Field Rendering.” ACM Transactions on Graphics / SIGGRAPH 2023. arXiv: https://arxiv.org/abs/2308.04079
7. Nikhil Keetha, Jay Karhade, Krishna Murthy Jatavallabhula, Gengshan Yang, Sebastian Scherer, Deva Ramanan, Jonathon Luiten. “SplaTAM: Splat, Track & Map 3D Gaussians for Dense RGB-D SLAM.” CVPR 2024. arXiv: https://arxiv.org/abs/2312.02126
8. Chi Yan, Delin Qu, Dan Xu, Bin Zhao, Zhigang Wang, Dong Wang, Xuelong Li. “GS-SLAM: Dense Visual SLAM with 3D Gaussian Splatting.” CVPR 2024. arXiv: https://arxiv.org/abs/2311.11700
9. Tianchen Deng, Chang Nie, Shuhong Liu, Wenhua Wu, Jianfei Yang, Shenghai Yuan, Jiuming Liu, Danwei Wang, Hesheng Wang. “Compact 3D Gaussian Splatting For Dense Visual SLAM.” arXiv: https://arxiv.org/abs/2403.11247
10. Yuhang Ming, Xingrui Yang, Weihan Wang, Zheng Chen, Jinglun Feng, Yifan Xing, Guofeng Zhang. “Benchmarking Neural Radiance Fields for Autonomous Robots: An Overview.” arXiv: https://arxiv.org/abs/2405.05526
11. Guangming Wang, Lei Pan, Songyou Peng, Shaohui Liu, Chenfeng Xu, Yanzi Miao, Wei Zhan, Masayoshi Tomizuka, Marc Pollefeys, Hesheng Wang. “NeRFs in Robotics: A Survey.” IJRR 2025 / arXiv. https://arxiv.org/abs/2405.01333
12. Siting Zhu, Guangming Wang, Xin Kong, Dezhi Kong, Hesheng Wang. “3D Gaussian Splatting in Robotics: A Survey.” arXiv: https://arxiv.org/abs/2410.12262
13. Tianchen Deng et al. “What Is The Best 3D Scene Representation for Robotics? From Geometric to Foundation Models.” arXiv: https://arxiv.org/abs/2512.03422
14. Abdelaziz Shaarawy, Cansu Erdogan, Rustam Stolkin, Alireza Rastegarpanah. “Hybrid Task and Motion Planning with Reactive Collision Handling for Multi-Robot Disassembly of Complex Products: Application to EV Batteries.” arXiv: https://arxiv.org/abs/2509.21020
15. Hyun Jong Yang, Howon Lee, Kyuhong Shim, Jeongho Kwak, Hyunsoo Kim, Donghoon Kim, Khoa Anh Ngo, Sehyun Ryu, Jaehyun Choi, Youbin Kim, Chanjun Moon, Michael Ryoo, Byonghyo Shim. “Advancing Multi-Robot Networks via MLLM-Driven Sensing, Communication, and Computation: A Comprehensive Survey.” arXiv: https://arxiv.org/abs/2604.00061
