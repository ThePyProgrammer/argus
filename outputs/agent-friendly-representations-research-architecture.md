# End-to-End Architecture Patterns for Agent-Friendly Swarm Representations

## Executive takeaways

1. **The dominant pattern is not “one map,” but a typed, multi-layer world state with explicit ownership boundaries.** Recent system papers split the representation into metric/topological/semantic/resource layers: e.g., 3D Dynamic Scene Graphs (DSGs) expose places/objects/humans/rooms as graph nodes for planning; Open-RMF exposes facility resources such as doors, lifts, corridors, chargers, and schedules; uncertainty-aware team planners use dynamic topological graphs with risk-bearing edge weights.
2. **Agent-friendly representations need planner-facing abstractions plus control-facing grounding.** Perception outputs must be reduced to symbolic/topological resources, capabilities, preconditions, time windows, risk bounds, and executable behavior primitives. Behavior-tree MRTA work is a useful architectural bridge: tasks stay abstract while runtime allocation grounds them against robot-specific capabilities and preconditions.
3. **Swarm architectures must treat communication as an explicit architectural constraint, not a transport detail.** Decentralized belief-space work shows that inconsistent beliefs are normal under limited sharing, and coordination must include action-consistency checks or communication-triggering policies. Distributed MARL surveys similarly frame centralized-training/decentralized-execution (CTDE), communication learning, and partial observability as first-class design choices.
4. **Fleet-level safety and liveness usually appear as a resource/schedule layer above local navigation.** Open-RMF and time-ordered resource-sharing work model shared resources and temporal ordering constraints separately from robot autonomy. This pattern supports heterogeneous fleets because vendors keep local control while a coordination layer arbitrates conflicts.
5. **Centralized vs decentralized is best treated as a spectrum.** Practical systems often centralize scarce-resource arbitration, global task dispatch, or training while decentralizing execution, sensing, local avoidance, and low-level control. Fully centralized world models strain bandwidth and latency; fully decentralized systems face belief inconsistency, explainability, and safety assurance gaps.
6. **Human/agent supervision needs explainable swarm state, not raw telemetry.** Human-swarm interaction work argues that operators need interfaces to control and monitor swarm behavior and that explainability requirements are still underdeveloped. A representation suitable for autonomous agents is also useful for supervisors: tasks, intentions, commitments, confidence, conflicts, and why a robot or coalition was selected.
7. **The big gap is interface standardization across layers.** Papers increasingly define strong internal representations, but fewer specify stable schemas for perception-to-world-model updates, world-model-to-planner queries, planner-to-allocation bids, or allocation-to-control contracts. Open-RMF is the closest operational pattern for fleet interoperability, but it is focused on facility traffic/resources rather than a complete semantic belief model.

## Evidence table

| Claim | Source | Evidence | Architecture implication | Swarm-specific constraint | Caveats |
|---|---|---|---|---|---|
| 3D Dynamic Scene Graphs provide a planner-friendly bridge from perception to cognition by representing places, objects, humans, and spatial hierarchy as a graph. | Rosinol et al., 2020, *3D Dynamic Scene Graphs: Actionable Spatial Perception with Places, Objects, and Humans* | DSGs are described as “actionable spatial perception” supporting “planning and decision-making,” built from visual-inertial data plus object/human detection and pose estimation. | Use graph nodes/edges as the query interface for planning and decision-making instead of exposing raw point clouds or meshes. | Dynamic worlds and humans require spatio-temporal relations; graph updates must handle moving agents and stale information. | Evaluation described on the arXiv page is simulation-oriented; not a full multi-robot shared-map architecture. |
| Kimera shows an end-to-end metric-semantic pipeline that produces DSGs from SLAM and perception modules. | Rosinol et al., 2021, *Kimera: from SLAM to Spatial Perception with 3D Dynamic Scene Graphs* | Chains visual-inertial SLAM, metric-semantic 3D reconstruction, object localization, human pose/shape estimation, and scene parsing into a 3D DSG; claims real-time hierarchical semantic path planning. | Treat the world model as a continuously built product of perception, with typed abstractions for downstream planners. | Multi-robot extension needs map fusion, conflict resolution, and bandwidth-aware graph deltas rather than full scene replication. | Primarily a spatial perception system; task allocation and fleet coordination are outside scope. |
| Open-RMF demonstrates a practical fleet-interoperability pattern: facility/resource coordination above vendor-specific robot controllers. | Open-RMF documentation and project site | Describes a ROS 2 coordination layer/“traffic controller” for multiple fleets and shared resources including lifts, doors, corridors, chargers, network bandwidth, and human operators. | Put a resource/schedule/world-facility layer between task dispatch and local robot control; use adapters for robot fleets and infrastructure. | Heterogeneous robots, shared infrastructure, and human-populated facilities need conflict prevention and schedule negotiation. | Public overview pages do not fully specify the internal world-model schema or all adapter APIs. |
| Time-ordered resource sharing formalizes shared-resource conflicts as temporal constraints integrated with Open-RMF. | Chakravarty et al., 2024, *Time-Ordered Ad-hoc Resource Sharing for Independent Robotic Agents* | Encodes continuous-time resource ordering constraints in CNF/weighted-SAT; algorithms and test harness build on Open-RMF. | Represent scarce resources as time-indexed commitments that planners and dispatchers can solve over. | Latency and contention matter: shared doors, corridors, lifts, and chargers can become bottlenecks even when local navigation works. | Solver-driven approach suggests central arbitration; page excerpt does not deeply cover bandwidth or safety guarantees. |
| Decentralized belief-space planning must handle inconsistent local beliefs and limited data sharing explicitly. | Kundu et al., 2024/2025, *Action-Consistent Decentralized Belief Space Planning with Inconsistent Beliefs and Limited Data Sharing* | Targets robots that do not share identical beliefs; communication is constrained; action-consistency checks trigger exchange when needed. | World models should expose belief version/confidence and support “communicate when coordination would break,” not assume perfect shared state. | Partial observability, limited bandwidth, stale beliefs, and unsafe joint choices are core swarm constraints. | More a planning framework than a production fleet architecture; implementation complexity rises in high-dimensional spaces. |
| Dynamic topological graphs with uncertainty-bearing edge weights are a compact shared representation for heterogeneous team planning. | Duggan et al., 2023, *Uncertainty-Aware Planning for Heterogeneous Robot Teams using Dynamic Topological Graphs and Mixed-Integer Programming* | Models missions as topological graphs with state-dependent edge-weight distributions; uses MIP for long-horizon online replanning. | Expose topology, risk distributions, and robot capabilities to the task planner instead of dense maps. | Heterogeneous robots and imperfect information require risk-aware assignments and replanning. | Scenario-level evidence; risk behavior depends on model quality and tuning. |
| Distributed robot-team learning architectures commonly separate centralized learning/state aggregation from decentralized execution. | Wang et al., 2022, *Distributed Reinforcement Learning for Robot Teams: A Review* | Organizes field around CTDE, independent learners, centralized critics, value decomposition, and communication-based learning; highlights non-stationarity and partial observability. | If learning policies are used, the architecture should distinguish training-time global state from runtime local observations and messages. | Partial observability, communication constraints, and non-stationarity dominate decentralized policy performance. | Survey-level; does not prescribe concrete world-model schemas or task allocation APIs. |
| Behavior trees can serve as an action-grounding contract for heterogeneous MRTA. | Heppner et al., 2024, *Behavior Tree Capabilities for Dynamic Multi-Robot Task Allocation with Heterogeneous Robot Teams* | Uses reusable behavior-tree tasks, robot skill models in `ros_bt_py`, preconditions, utility scoring, and runtime auctions. | Put a capability/precondition layer between abstract tasks and robot-specific controllers; allocate missions by feasible grounded behaviors. | Heterogeneity and dynamic conditions make static assignments brittle; runtime utility/precondition checks block bad assignments. | Evidence shown is a simulated 3-robot mission; no full global semantic world model is described. |
| Market-based MRTA is an architectural pattern for decentralized or hybrid task allocation via bids, auctions, and utilities. | Manathara et al./Springer JIRS survey, 2023, *Market Approaches to the Multi-Robot Task Allocation Problem: A Survey* | Survey visible through scholar results as a market-approach MRTA survey; market methods use prices/bids/utilities to allocate work. | Define task allocation interfaces as bid requests over task state, robot capabilities, costs, risk, and commitments. | Bandwidth can be reduced by exchanging bids/valuations instead of full maps, but local valuations can be stale or strategically inconsistent. | Full page redirected through Springer identity; details here rely on visible bibliographic/search snippets and established survey topic. |
| MRTA systematic reviews show heterogeneity, uncertainty, and learning-based policies are now central rather than edge cases. | ACM Computing Surveys, 2024, *A Systematic Literature Review on Multi-Robot Task Allocation* | Search result identifies a 2024 ACM CSUR review covering heterogeneous systems and learning-based policies. | Architecture should expect multiple allocation backends and robot capability models, not a single static dispatcher. | Dynamic tasks, heterogeneous robots, and uncertain execution require feedback from control/execution back to allocation. | ACM page returned 403, so only bibliographic/search-visible evidence was available. |
| MRTA-Sim highlights the need to evaluate allocation, navigation, and control as a coupled stack in open-world environments. | Tuck et al., 2025, *MRTA-Sim: A Modular Simulator for Multi-Robot Allocation, Planning, and Control in Open-World Environments* | Sends allocation results into robot-specific navigation and centralized CBF-QP-style deconfliction; designed for complex indoor environments, interactions, human avoidance, and swappable modules. | Test interfaces end-to-end: allocation outputs must be executable by planners/controllers under physical constraints. | Local conflicts and tight spaces can invalidate abstract travel-time assumptions; humans and dynamic obstacles matter. | Simulator, not proof of field performance. |
| SPACE provides a modular testbed for decentralized MRTA with communication and behavior-tree integration. | Jang, 2024, *SPACE: A Python-based Simulator for Evaluating Decentralized Multi-Robot Task Allocation Algorithms* | Provides Python plug-ins for allocation, GUI behavior trees, inter-agent communication, and local task awareness. | Build allocation algorithms behind plug-in interfaces and evaluate communication assumptions explicitly. | Decentralization depends on local awareness and inter-agent messages; newly added tasks test adaptation. | Simulator only; large-scale real-world validation remains difficult. |
| Explainable swarm interfaces are necessary for safety-critical human/agent-in-the-loop supervision. | Naiseh, Soorati, and Ramchurn, 2023, *Outlining the design space of eXplainable swarm (xSwarm): experts perspective* | Frames HSI around humans needing to control and monitor swarms; explains that xSwarm is important for safety-critical applications and that requirements are underdefined. | Shared representations should include explainable task status, intent, rationale, confidence, and exception state for operators and supervising agents. | High robot counts make raw telemetry unusable; supervisors need abstraction and trust calibration. | Expert-perspective study with 26 experts; foundational requirements still immature. |

## Detailed findings

### 1. Perception-to-world-model interfaces: from raw sensing to typed, queryable state

The architecture trend is to prevent planners from depending on raw perception products. DSG and Kimera-style systems translate visual-inertial SLAM, semantic reconstruction, object detection, and human estimation into typed nodes and relations. This makes the representation more agent-friendly because cognition can ask questions such as “which room contains object X?”, “which places connect to this corridor?”, “where are humans likely to move?”, or “which route avoids occupied regions?” rather than process dense geometry.

For swarms, the key interface question is not just “what is the map?” but “what update is worth communicating?” A multi-robot DSG or semantic graph should support:

- **Delta updates** rather than full-state broadcasts.
- **Confidence and provenance** for each node/edge so agents can reason about stale or conflicting observations.
- **Local-to-global frame alignment** and conflict resolution.
- **Abstraction levels** so high-bandwidth local geometry stays local while task-relevant topology/semantics are shared.
- **Temporal validity** for dynamic humans, movable objects, blocked passages, and temporary hazards.

This directly addresses bandwidth, latency, and partial observability: a robot can share “corridor C blocked, confidence 0.8, observed 12 seconds ago” rather than raw sensor logs.

### 2. Shared world model: layered state rather than monolithic global truth

Across sources, the shared world model decomposes into layers:

- **Metric layer:** local maps, meshes, occupancy, robot poses, localization uncertainty.
- **Topological layer:** places, corridors, doors, rooms, connectivity, traversal costs.
- **Semantic layer:** objects, humans, task-relevant landmarks, affordances, zones.
- **Belief/risk layer:** probability distributions, confidence, stale-state markers, inconsistent local beliefs.
- **Resource/schedule layer:** doors, lifts, chargers, narrow passages, reserved time windows, right-of-way commitments.
- **Capability layer:** robot payload, sensors, locomotion type, battery, manipulation skills, behavior-tree actions, preconditions.
- **Intent/commitment layer:** assigned tasks, bids, trajectories, reservations, expected completion, failure states.

The architecture implication is that “world model” should be an API surface, not just a database. Different modules need different views: planners need topology/risk/capabilities; allocation needs tasks/costs/availability; traffic managers need resource reservations; controllers need local geometry and near-term constraints; human supervisors need summarized intent, exceptions, and rationale.

### 3. Cognition/planning interfaces: compact graphs and belief states

Uncertainty-aware planning work supports a compact interface: dynamic topological graphs with edge-weight distributions and robot/team constraints. This is more swarm-appropriate than requiring every planner to reason over dense maps. It also supports heterogeneous teams: different robots can have different traversal feasibility, risk, energy cost, or sensing value on the same graph edge.

Decentralized belief-space planning adds a crucial constraint: robots do not share one consistent belief. Architectures must therefore expose belief metadata and coordination checks. A planner should know whether another robot’s commitment was made under an outdated belief and whether a proposed joint action remains action-consistent. Communication becomes event-triggered: share data when inconsistency threatens coordination or safety, not continuously by default.

### 4. Task allocation interfaces: bids, utilities, capabilities, and commitments

MRTA sources converge on task allocation as a separate layer that consumes world/capability state and produces commitments. Market-based and auction-based approaches exchange bids or utilities; behavior-tree capability work grounds abstract tasks against robot skills and preconditions; Open-RMF-style task dispatch and traffic scheduling arbitrate shared resources.

A robust allocation interface should include:

- Task description: goal, location/region, deadlines, priority, dependencies.
- Required capabilities: sensors, payload, manipulator, locomotion, compute, endurance.
- Preconditions: access, safety state, object availability, environmental constraints.
- Cost/risk estimate: travel time, energy, uncertainty, congestion, opportunity cost.
- Commitment: selected robot/coalition, expected time window, reserved resources, fallback behavior.
- Feedback: started, blocked, replanned, completed, failed, confidence/diagnostics.

This representation is agent-friendly because it allows planners, learned policies, or human supervisors to inspect why an allocation is feasible or risky.

### 5. Control and action grounding: preserve local autonomy while sharing contracts

Open-RMF and behavior-tree MRTA both suggest that heterogeneous fleets work best when high-level coordination does not assume identical low-level controllers. The coordination layer issues tasks, constraints, or reservations; the robot adapter or behavior-tree executor grounds those into local navigation/manipulation behaviors.

The clean contract is:

- **Upward from control:** availability, pose/region, battery, capability status, estimated arrival, local blockage, failure reason.
- **Downward to control:** task goal, constraints, reserved route/resource windows, safety envelopes, behavior primitive/precondition set.
- **Sideways between peers or via coordinator:** commitments, right-of-way, conflict alerts, belief updates.

This keeps low-latency safety and obstacle avoidance local while preserving global coordination over scarce resources.

### 6. Centralized, decentralized, and hybrid coordination

The strongest architecture pattern is hybridization:

- **Centralized where global consistency matters:** shared-resource scheduling, facility infrastructure, global task queues, operator supervision, training-time aggregation.
- **Decentralized where latency, robustness, or bandwidth matters:** local sensing, collision avoidance, execution monitoring, peer-to-peer belief updates, local replanning.
- **CTDE where learning is used:** learn with global information or centralized critics, execute using local observations and bounded messages.

Pure centralization risks bandwidth saturation and single points of failure. Pure decentralization risks inconsistent beliefs, duplicate work, hidden conflicts, and poor explainability. Hybrid contracts let systems centralize commitments while decentralizing execution.

### 7. Safety and human/agent supervision

Safety appears architecturally in several layers:

- Resource reservations prevent door/lift/corridor conflicts.
- Topological risk models prevent routes through uncertain or dangerous regions.
- Belief consistency checks reduce unsafe joint actions under stale information.
- Behavior-tree preconditions block infeasible assignments.
- Local controllers enforce collision and dynamic constraints.
- Explainable swarm interfaces expose intent, confidence, exceptions, and rationale.

Human/agent-in-the-loop supervision should not consume raw robot telemetry. It should consume a summarized operational world model: active tasks, robot roles, conflicts, confidence, blocked resources, predicted failures, and suggested interventions.

## Architecture patterns observed

### Pattern A: Metric-semantic scene graph as cognitive substrate

**Flow:** sensors → SLAM/perception → semantic graph/DSG → planner queries → route/task decisions → local control.

**Best for:** indoor service robots, long-term autonomy, semantic navigation, human-aware planning.

**Interface shape:** graph nodes/edges with type, geometry, semantics, temporal state, confidence, provenance.

**Swarm adaptation:** share graph deltas and high-value semantic/topological changes; maintain local dense maps.

### Pattern B: Facility/resource scheduler above heterogeneous local autonomy

**Flow:** task request → fleet/task dispatcher → traffic/resource schedule → fleet adapters → robot controllers → status feedback.

**Best for:** hospitals, warehouses, campuses, buildings with doors/lifts/chargers and mixed vendors.

**Interface shape:** maps/facility resources, reservations, time windows, robot itinerary, adapter status.

**Swarm adaptation:** centralize scarce-resource arbitration; decentralize local execution.

### Pattern C: Belief-aware decentralized planning with communication triggers

**Flow:** local observations → local belief → joint-action consistency check → communicate if needed → decentralized plan/action.

**Best for:** bandwidth-limited teams, field robots, contested or infrastructure-poor environments.

**Interface shape:** belief summaries, uncertainty, action candidates, consistency predicates, communication events.

**Swarm adaptation:** avoid assuming a single global truth; design for stale and inconsistent local states.

### Pattern D: Topological-risk graph for long-horizon heterogeneous planning

**Flow:** world abstraction → dynamic topological graph with edge distributions → MIP/optimizer → team plan → replanning feedback.

**Best for:** large environments, heterogeneous platforms, risk-aware missions.

**Interface shape:** nodes/edges, traversal feasibility per robot, risk/cost distributions, mission constraints.

**Swarm adaptation:** compact enough for sharing; supports capability-specific costs and uncertainty.

### Pattern E: Market/auction allocation with capability and utility contracts

**Flow:** task announcement → robot/coalition bids → winner/coalition selection → commitment → execution feedback.

**Best for:** dynamic task streams, decentralized or hybrid teams, heterogeneous capabilities.

**Interface shape:** bids, utilities, costs, deadlines, capability constraints, commitments.

**Swarm adaptation:** reduces bandwidth relative to full-state sharing but needs safeguards for stale/strategic/incomplete valuations.

### Pattern F: Behavior-tree task grounding for heterogeneous robots

**Flow:** abstract mission BT → capability/precondition matching → runtime auction/selection → robot-specific BT execution → feedback.

**Best for:** reusable missions across robot types; systems needing explainable action decomposition.

**Interface shape:** behavior nodes, required capabilities, preconditions, utility score, executor status.

**Swarm adaptation:** prevents assignments that are semantically valid but physically infeasible for a given robot.

### Pattern G: Modular simulation/evaluation stack for allocation-planning-control coupling

**Flow:** scenario/world → MRTA module → navigation/planning module → deconfliction/control → metrics.

**Best for:** validating architecture assumptions before field deployment.

**Interface shape:** replaceable allocation/planner/controller components, task streams, communication models, execution metrics.

**Swarm adaptation:** tests whether abstract allocation survives real navigation constraints, congestion, humans, and dynamic tasks.

### Pattern H: Explainable operational state for supervisors and agent monitors

**Flow:** world/task/intent state → explanation summarizer → operator/agent interface → intervention or policy update.

**Best for:** safety-critical swarms, mixed human-autonomy operations.

**Interface shape:** intent, rationale, confidence, conflicts, exceptions, predicted outcomes, intervention options.

**Swarm adaptation:** essential when robot count exceeds what humans can monitor directly.

## Contradictions / gaps

1. **Shared global model vs local inconsistent beliefs.** System architectures often imply a shared world model, while decentralized belief-space research shows this is unrealistic under constrained communication. Practical architectures need explicit belief versioning and inconsistency handling.
2. **Semantic richness vs bandwidth/latency.** DSGs and semantic maps are agent-friendly, but sharing rich graphs across a swarm can overwhelm networks. The missing piece is standardized prioritization: what semantic deltas are worth broadcasting, to whom, and when?
3. **Planner abstraction vs controller feasibility.** MRTA and high-level planning can assume travel-time costs that fail in tight, dynamic spaces. MRTA-Sim highlights that allocation, navigation, and control must be evaluated together.
4. **Central safety guarantees vs decentralized robustness.** Central traffic/resource schedulers improve consistency but create bottlenecks and single points of failure. Decentralized policies improve resilience but are harder to certify and explain.
5. **Heterogeneity is widely acknowledged but inconsistently modeled.** Sources discuss heterogeneous teams, but capability schemas are not standardized. Behavior trees and capability models are promising, yet many planners still assume simplified robot capabilities.
6. **Human supervision requirements are underdefined.** xSwarm work shows the need for explainable swarm interfaces, but there is no mature consensus on what explanations, confidence summaries, or intervention primitives operators require.
7. **Digital-twin rhetoric exceeds operational evidence.** Robotics/fleet sources increasingly mention digital twins, but the stronger evidence in this set comes from facility/resource models and scene graphs rather than full closed-loop digital-twin operations.
8. **Few papers specify stable cross-layer APIs.** Most define algorithms or internal representations; fewer define reusable contracts for perception updates, planner queries, task bids, resource reservations, and execution feedback.

## Source list

1. Antoni Rosinol, Arjun Gupta, Marcus Abate, Jingnan Shi, Luca Carlone. **“3D Dynamic Scene Graphs: Actionable Spatial Perception with Places, Objects, and Humans.”** 2020. arXiv:2002.06289. https://arxiv.org/abs/2002.06289
2. Antoni Rosinol, Andrew Violette, Marcus Abate, Nathan Hughes, Yun Chang, Jingnan Shi, Arjun Gupta, Luca Carlone. **“Kimera: from SLAM to Spatial Perception with 3D Dynamic Scene Graphs.”** 2021. arXiv:2101.06894. https://arxiv.org/abs/2101.06894
3. Open Robotics / Open-RMF. **Open-RMF project site and ROS 2 Multirobot Book.** https://www.open-rmf.org/ and https://osrf.github.io/ros2multirobotbook/
4. Arjo Chakravarty, Michael X. Grey, M. A. Viraj J. Muthugala, Mohan Rajesh Elara. **“Time-Ordered Ad-hoc Resource Sharing for Independent Robotic Agents.”** 2024, IROS 2024. arXiv:2408.07942. https://arxiv.org/abs/2408.07942
5. Vaibhav Kundu, Nitay Rafaeli, Daniil Gulyaev, Vadim Indelman. **“Action-Consistent Decentralized Belief Space Planning with Inconsistent Beliefs and Limited Data Sharing: Framework and Simplification Algorithms with Formal Guarantees.”** 2024/2025. arXiv:2403.05962. https://arxiv.org/abs/2403.05962
6. Colton Duggan, Brandon Wolfe, Wilson Woosley, Marin Kobilarov, David Moore. **“Uncertainty-Aware Planning for Heterogeneous Robot Teams using Dynamic Topological Graphs and Mixed-Integer Programming.”** 2023. arXiv:2310.08396. https://arxiv.org/abs/2310.08396
7. Yu Wang, Mehul Damani, Puze Wang, Yuhong Cao, Guillaume Sartoretti. **“Distributed Reinforcement Learning for Robot Teams: A Review.”** 2022. arXiv:2204.03516. https://arxiv.org/abs/2204.03516
8. Robin Heppner, Janis Oberacker, Arne Roennau, Rüdiger Dillmann. **“Behavior Tree Capabilities for Dynamic Multi-Robot Task Allocation with Heterogeneous Robot Teams.”** 2024. arXiv:2402.02833. https://arxiv.org/abs/2402.02833
9. V. G. Manathara et al. **“Market Approaches to the Multi-Robot Task Allocation Problem: A Survey.”** *Journal of Intelligent & Robotic Systems*, 2023. DOI:10.1007/s10846-022-01803-0. https://doi.org/10.1007/s10846-022-01803-0
10. **“A Systematic Literature Review on Multi-Robot Task Allocation.”** *ACM Computing Surveys*, 2024. DOI:10.1145/3700591. https://dl.acm.org/doi/abs/10.1145/3700591
11. Victoria Marie Tuck et al. **“MRTA-Sim: A Modular Simulator for Multi-Robot Allocation, Planning, and Control in Open-World Environments.”** 2025. arXiv:2504.15418. https://arxiv.org/abs/2504.15418
12. Inmo Jang. **“SPACE: A Python-based Simulator for Evaluating Decentralized Multi-Robot Task Allocation Algorithms.”** 2024. arXiv:2409.04230. https://arxiv.org/abs/2409.04230
13. Omar Naiseh, Mohammad Davoudi Soorati, Sarvapali D. Ramchurn. **“Outlining the design space of eXplainable swarm (xSwarm): experts perspective.”** 2023. arXiv:2309.01269. https://arxiv.org/abs/2309.01269
