# Navigation Skill Adaptation Research Foundations

**Scope.** Foundations for skill/options and hierarchical reinforcement learning (HRL) relevant to a gated online exploration skill selector for Argus. This report emphasizes definitions, mechanisms, temporal abstraction, skill discovery, multi-level hierarchies, and HRL for navigation/exploration. It intentionally does **not** go deep on model-based skill planning; arXiv:2207.07560 is included only to position it.

## Executive Summary

Skill-based adaptation in robot navigation is best grounded in the options framework: an option is a temporally extended course of action with an initiation set, an internal policy, and a termination condition, turning flat MDP action selection into semi-MDP decision-making over variable-duration behaviors [S1]. For Argus, this maps cleanly to high-level exploration skills such as frontier pursuit, loop closure, information-gain sweep, rendezvous, relocalization, and stuck recovery. A gated selector can be treated as a conservative hand-engineered policy-over-options today, with a path toward learned option policies, learned termination, and eventually option discovery.

The HRL literature repeatedly supports three design principles. First, temporal abstraction is useful because it shortens effective horizons, improves credit assignment, and makes high-level decisions more interpretable [S1, S2, S3]. Second, hierarchy must preserve observability of the right state variables: options/subtasks work when initiation and termination predicates are tied to measurable progress and safety conditions, not just arbitrary action bundles [S1, S3, S4]. Third, autonomous skill discovery is promising but brittle; diversity-based or graph/Laplacian methods can produce reusable behaviors, but they often need careful state representations, coverage assumptions, and task alignment before they become reliable navigation skills [S9, S10, S11, S12].

For Argus, the near-term recommendation is **do not start with end-to-end HRL**. Build a typed skill interface whose metadata already looks like an option: preconditions/initiation set, tunable parameters, expected effects, termination criteria, failure modes, and telemetry. Use a gated selector that chooses and sequences these skills using explicit mission signals: map entropy reduction, frontier utility, coverage novelty, localization confidence, communication risk, collision/stuck signals, and inter-robot redundancy. That architecture captures the operational benefits of options while retaining debuggability. Future RL can then learn (1) option-selection priorities, (2) termination thresholds, (3) parameter tuning, and later (4) new skills or subgoals.

The user-referenced paper, **Skill-based Model-based Reinforcement Learning / SkiMo** (arXiv:2207.07560), belongs in this ecosystem because it plans over learned skills and is evaluated on long-horizon navigation/manipulation tasks [S15]. However, its core contribution is model-based skill-space planning, so it should be cited as future direction rather than the foundation for the current gated selector.

## Evidence Table

| Source | Mechanism / definition | Evidence type | Relevance to Argus skill selector | Cautions |
|---|---|---|---|---|
| [S1] Sutton, Precup & Singh 1999 | Options: initiation set, policy, termination; SMDP and intra-option learning | Foundational theory + experiments | Direct template for skill API and selector-as-policy-over-options | Assumes well-defined state/action abstractions; real robot signals may be partial/noisy |
| [S2] Barto & Mahadevan 2003 | HRL survey: temporal abstraction, decomposition, subgoals, reusable subtasks | Survey/tutorial | Taxonomy for choosing between options, MAXQ, feudal, subgoal methods | Older; predates deep RL and modern sim-scale robotics |
| [S3] Dietterich 2000 MAXQ | Hierarchical decomposition with value-function factorization and state abstraction | Algorithmic theory + experiments | Shows why skill/subtask boundaries should expose relevant state and hide irrelevant state | Requires designer-specified hierarchy; recursive optimality can differ from global optimality |
| [S4] Bacon, Harb & Precup 2017 | Option-Critic learns intra-option policies and terminations end-to-end | Deep RL algorithm | Future path for learning termination/selection instead of hand thresholds | Learned options can collapse or become hard to interpret without constraints |
| [S5] Kulkarni et al. 2016 h-DQN | Manager chooses intrinsic goals; controller learns goal achievement | Deep HRL experiments | Useful analogy for high-level exploration goals vs low-level navigation control | Demonstrated mostly in game-like settings; goal design still matters |
| [S6] Vezhnevets et al. 2017 FeUdal Networks | Manager emits latent goals; worker follows them over time | Deep HRL experiments | Supports separating strategic exploration intent from motor/navigation execution | Latent goals may be hard to audit in safety-critical robotics |
| [S7] Levy et al. 2019 HAC | Multi-level hierarchy trained with hindsight; assumes lower levels can solve subgoals | Deep HRL robotics/gridworld experiments | Relevant for future multi-level skill hierarchy: mission -> exploration skill -> waypoint/subgoal -> controller | Training stability remains difficult; depends on subgoal representation |
| [S8] Nachum et al. 2018 HIRO | Off-policy correction for hierarchical goal-conditioned policies | NeurIPS algorithm + continuous-control experiments | Relevant if Argus later learns high-level goals from replay in simulation | More about continuous control than explicit multi-robot exploration; needs lots of data |
| [S9] Machado, Bellemare & Bowling 2017 | Laplacian/eigenoption discovery from state-space graph structure | Option-discovery theory + experiments | Suggests graph/map structure can induce navigation options such as corridor/region traversal | Quality depends on learned graph/state representation and coverage |
| [S10] Florensa, Duan & Abbeel 2017 | Pretrain diverse stochastic skills, then learn high-level selector | Skill discovery + sparse-reward HRL | Matches Argus future: discover reusable exploration behaviors in simulation before online selection | Transfer from pretraining domain to mission domain may fail |
| [S11] Eysenbach et al. 2019 DIAYN | Unsupervised skill discovery by maximizing skill identifiability and entropy | Unsupervised RL experiments | Useful for discovering behavior repertoire without hand rewards | Diversity is not the same as mission utility; may produce irrelevant skills |
| [S12] Sharma et al. 2020 DADS | Skills optimized for predictable, distinct dynamics | Unsupervised skill discovery + planning demos | Useful idea for learning skills with predictable map/pose effects | Includes model-based planning emphasis; not a drop-in selector |
| [S13] Mirowski et al. 2017 | Deep RL navigation with auxiliary depth/loop-closure tasks | 3D maze navigation experiments | Loop-closure and depth/map auxiliary signals are good selector telemetry | Not an options/HRL method by itself |
| [S14] Mirowski et al. 2018 | City-scale visual navigation, landmarks, transfer across cities | Visual navigation experiments | Supports separating general navigation behavior from place-specific memory/context | Street-view setting differs from robot exploration |
| [S15] Shi, Lim & Lee 2022 SkiMo | Skill-based model-based RL; skill dynamics and skill-space planning | arXiv paper; long-horizon navigation/manipulation | Belongs as future path to skill-space prediction/planning | Model-based planning is central; keep out of current foundation depth |
| [S16] Sohn, Oh & Lee 2018 | HRL with subtask dependency graphs for zero-shot generalization | Graph/subtask HRL experiments | Useful if Argus encodes exploration tasks as dependency graph: localize before map merge, rendezvous before relay, etc. | Requires known or inferred subtask graph |
| [S17] Colas et al. 2019 CURIOUS | Intrinsically motivated modular goal generation and goal-conditioned learning | Autonomous goal/curriculum RL | Useful for adaptive exploration curricula in simulation | More goal-conditioned curriculum than classical options |

## Key Findings

### 1. Options give the cleanest formal vocabulary for Argus skills

The options framework defines a skill as a temporally extended action with three parts: an **initiation set** indicating when the option is available, an **option policy** describing behavior while active, and a **termination condition** that decides when control returns to the higher-level policy [S1]. This directly matches an engineering skill contract:

- **Initiation/preconditions:** e.g., a frontier-pursuit skill is available when frontiers exist, localization confidence is adequate, and the robot is not trapped.
- **Policy/behavior body:** e.g., choose frontier target, generate path, execute local planner, replan if blocked.
- **Termination:** e.g., frontier reached, information gain exhausted, timeout, progress stalls, safety violation, map merge required.

Because options induce a semi-Markov decision process, the high-level selector reasons at skill boundaries rather than every control step [S1]. For Argus, this reduces the action horizon and yields inspectable decisions: the selector can explain why it activated frontier pursuit, coverage sweep, relay positioning, or recovery.

### 2. Temporal abstraction is both a learning device and a systems design device

HRL literature frames temporal abstraction as a way to reduce long-horizon credit assignment and to reuse behavior modules [S1, S2]. In robotics, the same idea also improves integration: the skill selector does not need to know every local planner command, only whether the skill is making progress and when to stop. MAXQ further shows that hierarchy can factor value functions and enable state abstraction when subtasks ignore irrelevant variables [S3].

For Argus, this means each skill should publish a small, explicit state slice for selection:

- progress rate or estimated value-of-continuing;
- expected information gain or entropy reduction;
- risk/safety cost;
- localization confidence impact;
- communication/team coordination impact;
- termination/failure reason codes.

The selector should not consume raw simulator state indiscriminately. HRL works best when abstraction boundaries are deliberate [S2, S3].

### 3. Learned option termination is attractive, but hand-authored terminations are safer first

Option-Critic showed that intra-option policies and termination functions can be learned end-to-end with policy-gradient methods [S4]. That is a credible future path for Argus, especially for learning when to abandon a frontier, switch from exploration to loop closure, or trigger recovery.

However, learned terminations can become opaque or unstable. For a simulation-first multi-robot workbench, the first version should use explicit termination predicates and log them heavily. Later experiments can learn threshold adjustments or termination scoring while preserving hard safety overrides.

### 4. Multi-level hierarchies are relevant, but only if levels have distinct semantics

Deep HRL systems such as h-DQN, FeUdal Networks, HAC, and HIRO separate high-level goal/skill choice from lower-level control [S5, S6, S7, S8]. They differ in representation: discrete intrinsic goals, latent goals, hindsight-trained subgoals, or continuous goal vectors. The common useful pattern is not the specific neural architecture; it is the separation of decision timescales.

A practical Argus hierarchy should be semantic rather than arbitrary:

1. **Mission layer:** team-level objective, map coverage, communication constraints, shared exploration policy.
2. **Skill selector layer:** choose among exploration/recovery/coordination skills.
3. **Skill parameter layer:** set target frontier, sweep radius, rendezvous point, loop-closure candidate, risk tolerance.
4. **Navigation/control layer:** path planning, local avoidance, controller execution.

This hierarchy gives future HRL clear interfaces. Avoid adding extra hierarchy levels unless each level has a different decision timescale and observable outcome.

### 5. Skill discovery can help, but discovered skills need grounding in map/exploration utility

Unsupervised skill discovery methods learn diverse skills without task rewards. DIAYN maximizes distinguishability between skills [S11]; DADS learns skills with predictable and distinct dynamics [S12]; stochastic neural-network HRL pretrains diverse skills for later high-level selection [S10]. Graph/Laplacian methods discover options by finding meaningful directions in a state-transition graph [S9].

These are relevant to Argus because navigation and exploration naturally create graph structure: rooms, corridors, frontiers, bottlenecks, revisitation loops, map partitions, and communication relay regions. The strongest fit is probably not raw motor-skill discovery, but **map/topology-aware option discovery**:

- traverse bottleneck / doorway;
- move to frontier cluster;
- sweep unexplored room;
- return to high-confidence localization region;
- become relay between two robots;
- revisit loop-closure candidate;
- escape cul-de-sac or dynamic obstacle trap.

The limitation is that unsupervised diversity can optimize for behaviors that are visually or dynamically distinct but not useful for exploration [S11]. Argus should score discovered skills by downstream mission utility before admitting them to the online selector.

### 6. Navigation-specific RL evidence supports auxiliary signals and memory, not blind end-to-end selection

Deep RL navigation work shows that auxiliary objectives such as depth prediction and loop-closure classification can improve navigation learning in complex 3D environments [S13]. City-scale visual navigation work emphasizes landmarks, memory, and transfer between general navigation behavior and place-specific knowledge [S14]. These are not options-framework papers, but they identify useful telemetry for an exploration skill selector.

For Argus, selector inputs should include navigation-specific signals beyond reward:

- frontier count and frontier quality distribution;
- map entropy / occupancy uncertainty;
- novelty of reachable regions;
- loop-closure candidate quality;
- localization covariance / drift;
- path risk and blockage history;
- team redundancy and coverage overlap;
- communication graph robustness.

### 7. arXiv:2207.07560 belongs here, but as future trajectory

SkiMo learns a skill repertoire and a skill dynamics model, then plans in skill space for long-horizon tasks including navigation and manipulation [S15]. It is directly skill-based and hierarchical, but model-based planning is central. For this report’s scope, SkiMo should be cited to justify a future progression from gated skill selection toward learned skill dynamics and skill-space prediction. It should not dominate the current design because T2 covers model-based skill planning in depth.

## Contradictions and Limitations in the Literature

1. **Interpretability vs performance.** Hand-designed options are interpretable and safe, but may underperform learned options. Learned options can improve performance but often lose semantic clarity [S1, S4, S11]. Argus should preserve semantic skill names and hard constraints even if internal scoring becomes learned.

2. **Diversity vs usefulness.** Skill-discovery methods often optimize diversity, empowerment, or predictability rather than mission reward [S10, S11, S12]. A diverse behavior repertoire is not automatically an exploration strategy.

3. **Designer hierarchy vs learned hierarchy.** MAXQ-style approaches benefit from designer-provided decompositions [S3], while option-critic and unsupervised discovery aim to reduce manual design [S4, S11]. In a robotics workbench, fully learned hierarchy may be premature; a hybrid approach is more defensible.

4. **Simulation success vs real-world robustness.** Many HRL results are in games, gridworlds, MuJoCo-style continuous-control, or simplified navigation settings [S5, S6, S7, S8]. Argus is simulation-first, which is helpful, but if the workbench is meant to inform robotics, domain randomization, sensor noise, partial observability, and multi-robot communication failures must be built into evaluation.

5. **Single-agent assumptions.** Much of the canonical HRL/options literature is single-agent [S1-S12]. Argus is multi-robot. Team-level options need additional state: teammate intent, map merge status, communication topology, redundant coverage, and collision/interference risk.

6. **Termination is underappreciated.** Many practical failures in skill sequencing are termination failures: staying too long in a low-yield skill, switching too often, abandoning useful behavior too early, or oscillating between skills. Option theory gives termination a first-class role [S1], and Argus should too.

## Concrete Implications for the Argus Design Spec

### A. Define every exploration skill as an option-like contract

Each skill should declare:

- **Name and semantic purpose:** e.g., `frontier_pursuit`, `coverage_sweep`, `loop_closure`, `rendezvous_relay`, `relocalize`, `unstuck_recovery`.
- **Initiation set / preconditions:** state predicates that make the skill available.
- **Parameters:** target, radius, risk budget, timeout, information-gain threshold, teammate assignment, etc.
- **Expected effects:** map entropy reduction, pose-confidence improvement, communication improvement, escape progress.
- **Termination conditions:** success, no-progress, timeout, safety violation, better skill opportunity, team conflict, precondition invalidated.
- **Failure modes and cooldowns:** avoid immediate re-selection after repeated failure.
- **Telemetry:** progress, utility estimate, cost estimate, termination reason, and traces for offline learning.

This is directly grounded in the options framework [S1].

### B. Use a gated selector before learning a policy-over-options

The first online selector should be a conservative gated decision system:

1. Filter available skills by initiation set and safety constraints.
2. Score remaining skills by mission utility and risk.
3. Apply hysteresis/cooldowns to prevent oscillation.
4. Select skill and parameters.
5. Monitor termination and progress.
6. Log decision context for future supervised/RL training.

This gives the system an immediate policy-over-options while creating data for later option-critic, HIRO/HAC-style, or contextual-bandit/RL selectors [S4, S7, S8].

### C. Make termination a design object, not an afterthought

For each skill, distinguish:

- **success termination:** goal achieved;
- **failure termination:** blocked, unsafe, lost localization, communication lost;
- **economic termination:** marginal information gain too low;
- **coordination termination:** teammate already covers target or team objective changed;
- **exploration termination:** novelty exhausted or better frontier appears.

This follows the option definition and avoids brittle long-running behaviors [S1].

### D. Prefer parameterized skills over too many discrete skills

Rather than creating dozens of nearly identical options, define fewer parameterized skills. Example: `coverage_sweep(region, sweep_pattern, risk_budget)` is preferable to separate hardcoded skills for every sweep variant. This keeps the future action space manageable for policy-over-options learning and aligns with goal-conditioned HRL [S5, S7, S8, S17].

### E. Treat multi-robot coordination as high-level option context

The selector should consider teammate state before skill activation:

- Is another robot already heading to the same frontier cluster?
- Would moving here improve or break communication connectivity?
- Is this robot best suited for relay, exploration, recovery, or map-merge support?
- Does the team need diversity of exploration directions?

Canonical HRL is often single-agent, so Argus must extend the option state with team context rather than blindly importing algorithms [S1, S2].

### F. Build the data substrate for future RL now

Log every selector decision as a transition over skills:

- state summary at skill start;
- available skills and gates;
- selected skill and parameters;
- skill duration;
- termination reason;
- reward/proxy metrics: entropy reduction, area covered, collisions, localization drift, communication health, teammate interference;
- counterfactual candidates if available.

This creates the dataset needed for offline evaluation, contextual bandits, imitation of expert heuristics, or future HRL.

### G. Use simulation to evaluate skill-level generalization, not just path success

Argus should test the selector across map families and robot-team configurations:

- maze/corridor maps with bottlenecks for eigenoption-like traversal relevance [S9];
- open spaces where frontier pursuit may dominate;
- loop-rich maps where loop-closure timing matters [S13];
- communication-constrained maps requiring relay behavior;
- dynamic obstacle or blockage scenarios requiring recovery;
- multi-robot redundancy scenarios requiring anti-overlap coordination.

Metrics should include coverage efficiency, entropy reduction per meter/time, communication graph robustness, relocalization events, stuck recovery latency, skill-switch frequency, and avoidable overlap.

### H. Keep SkiMo as a future design waypoint

The design spec can mention a future path:

1. typed hand-authored options;
2. learned scoring/termination thresholds;
3. learned option-selection policy from logged simulation data;
4. discovered or refined options in simulation;
5. skill-level dynamics model and skill-space planning, as in SkiMo-like approaches [S15].

But model-based planning should stay outside the current selector foundation if T2 owns that depth.

## Numbered Source List

[S1] Richard S. Sutton, Doina Precup, Satinder Singh. “Between MDPs and semi-MDPs: A Framework for Temporal Abstraction in Reinforcement Learning.” *Artificial Intelligence*, 112(1-2), 1999, pp. 181-211. DOI: https://doi.org/10.1016/S0004-3702(99)00052-1

[S2] Andrew G. Barto, Sridhar Mahadevan. “Recent Advances in Hierarchical Reinforcement Learning.” *Discrete Event Dynamic Systems*, 13, 2003, pp. 41-77. DOI: https://doi.org/10.1023/A:1022140919877

[S3] Thomas G. Dietterich. “Hierarchical Reinforcement Learning with the MAXQ Value Function Decomposition.” *Journal of Artificial Intelligence Research*, 13, 2000, pp. 227-303. DOI: https://doi.org/10.1613/jair.639

[S4] Pierre-Luc Bacon, Jean Harb, Doina Precup. “The Option-Critic Architecture.” arXiv: https://arxiv.org/abs/1609.05140; AAAI 2017 proceedings: https://ojs.aaai.org/index.php/AAAI/article/view/10916

[S5] Tejas D. Kulkarni, Karthik R. Narasimhan, Ardavan Saeedi, Joshua B. Tenenbaum. “Hierarchical Deep Reinforcement Learning: Integrating Temporal Abstraction and Intrinsic Motivation.” arXiv: https://arxiv.org/abs/1604.06057

[S6] Alexander Sasha Vezhnevets, Simon Osindero, Tom Schaul, Nicolas Heess, Max Jaderberg, David Silver, Koray Kavukcuoglu. “FeUdal Networks for Hierarchical Reinforcement Learning.” arXiv: https://arxiv.org/abs/1703.01161; ICML 2017: https://proceedings.mlr.press/v70/vezhnevets17a.html

[S7] Andrew Levy, George Konidaris, Robert Platt, Kate Saenko. “Learning Multi-Level Hierarchies with Hindsight.” arXiv: https://arxiv.org/abs/1712.00948; ICLR 2019: https://openreview.net/forum?id=ryzECoAcY7

[S8] Ofir Nachum, Shixiang Gu, Honglak Lee, Sergey Levine. “Data-Efficient Hierarchical Reinforcement Learning.” NeurIPS 2018. arXiv: https://arxiv.org/abs/1805.08296; proceedings: https://proceedings.neurips.cc/paper/2018/hash/e6384711491713d29bc63fc5eeb5ba4f-Abstract.html

[S9] Marlos C. Machado, Marc G. Bellemare, Michael Bowling. “A Laplacian Framework for Option Discovery in Reinforcement Learning.” arXiv: https://arxiv.org/abs/1703.00956; ICML 2017: https://proceedings.mlr.press/v70/machado17a.html

[S10] Carlos Florensa, Yan Duan, Pieter Abbeel. “Stochastic Neural Networks for Hierarchical Reinforcement Learning.” arXiv: https://arxiv.org/abs/1704.03012; ICLR 2017: https://openreview.net/forum?id=B1oK8aoxe

[S11] Benjamin Eysenbach, Abhishek Gupta, Julian Ibarz, Sergey Levine. “Diversity is All You Need: Learning Skills without a Reward Function.” arXiv: https://arxiv.org/abs/1802.06070; ICLR 2019: https://openreview.net/forum?id=SJx63jRqFm

[S12] Archit Sharma, Shixiang Gu, Sergey Levine, Vikash Kumar, Karol Hausman. “Dynamics-Aware Unsupervised Discovery of Skills.” arXiv: https://arxiv.org/abs/1907.01657; ICLR 2020: https://openreview.net/forum?id=HJgLZR4KvH

[S13] Piotr Mirowski, Razvan Pascanu, Fabio Viola, Hubert Soyer, Andrew J. Ballard, Andrea Banino, Misha Denil, Ross Goroshin, Laurent Sifre, Koray Kavukcuoglu, Dharshan Kumaran, Raia Hadsell. “Learning to Navigate in Complex Environments.” arXiv: https://arxiv.org/abs/1611.03673; ICLR 2017: https://openreview.net/forum?id=SJMGPrcle

[S14] Piotr Mirowski, Matthew Koichi Grimes, Mateusz Malinowski, Karl Moritz Hermann, Keith Anderson, Denis Teplyashin, Karen Simonyan, Koray Kavukcuoglu, Andrew Zisserman, Raia Hadsell. “Learning to Navigate in Cities Without a Map.” arXiv: https://arxiv.org/abs/1804.00168

[S15] Lucy Xiaoyang Shi, Joseph J. Lim, Youngwoon Lee. “Skill-based Model-based Reinforcement Learning.” arXiv: https://arxiv.org/abs/2207.07560

[S16] Sungryull Sohn, Junhyuk Oh, Honglak Lee. “Hierarchical Reinforcement Learning for Zero-shot Generalization with Subtask Dependencies.” arXiv: https://arxiv.org/abs/1807.07665; NeurIPS 2018: https://proceedings.neurips.cc/paper/2018/hash/e6384711491713d29bc63fc5eeb5ba4f-Abstract.html may not be the correct proceedings page for this title; use arXiv as the stable identifier.

[S17] Cédric Colas, Pierre Fournier, Olivier Sigaud, Mohamed Chetouani, Pierre-Yves Oudeyer. “CURIOUS: Intrinsically Motivated Modular Multi-Goal Reinforcement Learning.” arXiv: https://arxiv.org/abs/1810.06284; ICML 2019: https://proceedings.mlr.press/v97/colas19a.html
