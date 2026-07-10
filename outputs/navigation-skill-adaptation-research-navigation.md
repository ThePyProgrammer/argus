# Navigation and Exploration Strategy Adaptation for Robots

## Executive Summary

The most actionable literature for an Argus gated online exploration skill selector is not broad hierarchical reinforcement learning, but a narrower line of systems that make **explicit choices among frontiers, planners, parameter sets, modes, arms, or robot-team tasks**. Classic frontier exploration already frames exploration as repeated high-level goal selection [S1]. Coordinated and market-based multi-robot exploration extend this to team allocation by scoring expected information or reconnaissance value against travel/coordination cost [S2, S3]. These methods support a first Argus implementation in which high-level skills expose expected gain, cost, risk, and applicability signals, while a selector chooses and sequences them under promotion/fallback gates.

Recent navigation adaptation systems are closer to the desired Argus shape than end-to-end learned exploration policies. APPLD and APPLI learn or select planner parameter sets from demonstrations/interventions while retaining the existing navigation stack [S4, S5]. Hybrid Classical/RL Local Planner switches between a classical planner and an RL planner using a meta-reasoning policy, with reported live-robot gains and explicit planner trade-offs [S6]. Learned planner-selection work and DRL control-switching papers indicate a growing direction of treating local planners as selectable skills rather than replacing the whole stack [S7, S8]. This literature favors **constrained adaptation over wholesale policy learning** for early systems.

Bandit and active-inference papers provide a useful formal model for online high-level choice under uncertainty. The most directly relevant exploration paper models autonomous robotic exploration as a contextual multi-armed bandit over candidate survey sites, using context and changing preferences to adapt selection [S9, S10]. Case-based navigation papers show an older but still useful pattern: retrieve similar prior situations and adapt reactive-control parameters or paths [S11, S12]. For Argus, the combined recommendation is: start with auditable skill-level meta-control using contextual scoring, memory/case retrieval, and fallback guards; log enough context/action/outcome data to later train contextual bandits, offline policy selectors, or options-style RL.

## Scope and Acceptance

This research file covers T3 only: adaptive navigation and exploration strategy selection systems. It intentionally avoids broad HRL foundations and generic evaluation methodology except when tied to a concrete system. Sources were accepted when they were primary papers, reputable surveys, or direct publisher/arXiv pages and when their contribution mapped to one of the requested angles: frontier/exploration strategy adaptation, learned meta-control, contextual bandits, case/memory-based navigation, planner/skill selection, or multi-robot exploration.

## Evidence Table

| Theme | Source(s) | Selection/adaptation object | Evidence type | What it contributes for Argus | Caveats |
|---|---|---|---|---|---|
| Frontier exploration as strategy selection | Yamauchi 1997 [S1] | Next frontier/goal | Classic primary paper | Exploration can be represented as repeated high-level goal choice at known/unknown boundaries | Greedy frontier choice; limited uncertainty, long-horizon, and multi-robot handling |
| Coordinated multi-robot exploration | Burgard et al. 2005 [S2] | Robot-to-target/frontier assignment | Primary paper | Scores travel cost against information gain for team exploration; relevant to multi-robot skill allocation | Requires reliable map/pose assumptions; not a learned selector |
| Market-based multi-robot coordination | Zlot & Stentz 2006 [S3] | Task/subtask allocation through auctions | Primary paper | Shows how high-level exploration/recon tasks can be decomposed, bid on, and allocated across robots | Depends on task decomposition and bidding design; local/myopic cost estimates can matter |
| Adaptive planner parameter learning from demonstration | APPLD [S4] | Planner parameter settings | Primary paper; arXiv/RAL/IROS | Learns navigation-stack tuning from human demonstration without replacing low-level control | Demonstration quality and coverage constrain generalization |
| Adaptive planner parameter learning from interventions | APPLI [S5] | Multiple planner parameter presets | Primary paper; arXiv/ICRA | Uses intervention data and confidence-based preset choice; strong precedent for gated adaptation | Still parameter adaptation, not exploration-skill sequencing |
| Hybrid meta-control between planners | Sharma et al. 2024 [S6] | Classical vs RL local planner | Primary paper; arXiv | Direct example of planner-as-skill switching based on surroundings; reports 26% navigation-time improvement | Limited public detail in fetched abstract; ground-robot local navigation, not exploration |
| ML local planner selection | Öner & Sezer 2025 [S7] | Local planner choice | Recent primary paper/publisher listing | Shows planner selection is becoming an explicit supervised/ML robotics problem | Details require full article access; recent result needs replication scrutiny |
| DRL control switch across navigation planners | Linh et al. 2022 [S8] | Control/planner switching | Primary IEEE listing | Supports hybrid classical/RL control switching rather than monolithic learned navigation | Limited details available from search result; likely local navigation focus |
| Contextual bandit exploration | Wakayama et al. 2024 [S9] | Candidate survey site/arm | Primary arXiv paper | Formalizes exploration choice as contextual bandit; supports preference-aware online adaptation | Demonstrated in simulated mineral survey setting, not indoor multi-robot workbench |
| Active-inference bandit with dynamic preferences | Wakayama et al. 2025 [S10] | Candidate survey/action under changing preferences | Primary IEEE/TRO listing | Shows online preference shifts can be handled at decision layer | Domain is autonomous survey/site selection, not full robot navigation |
| Case-based reactive navigation | Ram & Santamaría 1997 [S11] | Reactive control parameters retrieved/adapted from cases | Primary IEEE listing | Precedent for memory-backed online parameter/control selection | Older robotics assumptions; may not match modern SLAM/local planners |
| Case-based global navigation | Aha, Breslow & Muñoz-Avila 2001 [S12] | Retrieved navigation cases/plans | Primary journal article | Supports storing prior navigation situations and reusing/adapting them for dynamic environments | Older CBR methods; source access is partially gated |
| Multi-strategy CBR + RL navigation | Ram, Arkin, Moorman & Clark 1997 [S13] | Reactive control strategy/parameters and learned improvement | Primary technical report/publication record | Directly combines case-based selection and RL for self-improving reactive navigation | Older system; not necessarily validated at modern scale |
| Learned exploration/exploitation mode shift | Wasserman et al. 2023/2024 [S14] | Exploration vs exploitation module | Primary arXiv/RAL listing | Modular policy-level switching; useful pattern for “explore until signal, then exploit” | Semantic embodied navigation, not generic mapping/exploration |
| Curriculum RL for exploration and mapping | Li, Xin & Li 2023 [S15] | Learned exploration policy | Primary arXiv paper | Shows end-to-end learned exploration remains active and can use local/global map abstractions | More relevant as future path than near-term gated selector |
| Autonomous exploration planners | Selin et al. 2019 [S16] | Next-best-view / gain-estimate reuse | Primary IEEE listing | Information-gain and cost scoring patterns useful as skill utility features | Planner-specific; not necessarily an online meta-selector |
| Surveys on multi-robot exploration | Sharma & Tiwari 2016; Hu & Pei 2024 [S17, S18] | Surveyed frontier/coordination methods | Survey/review | Establishes frontier, coordination, and task-allocation families as mainstream | Surveys vary in rigor; use for orientation, not critical claims alone |

## Key Findings

### 1. Frontier exploration already provides the base abstraction: choose high-level exploration goals, not motor actions

Yamauchi’s frontier-based exploration selects goals on the boundary between known and unknown map regions [S1]. The important design lesson is not the specific frontier detector; it is the abstraction boundary. Exploration progress can be advanced by choosing among **candidate high-level targets** with predicted information gain and navigation cost, while leaving local control to the robot stack [S1].

For Argus, this supports representing each exploration skill as a producer of candidate actions such as “go to frontier cluster,” “revisit high-uncertainty cell,” “fan out to under-covered region,” or “return/connectivity repair.” The selector need not initially learn low-level control. It can rank skill proposals using shared features: estimated information gain, travel cost, blockage risk, map uncertainty, robot health, communication/connectivity risk, and recent failure history.

### 2. Multi-robot exploration literature favors utility/cost allocation, auctions, and explicit decomposition

Burgard et al. coordinate multiple robots by weighing utility/information gain against cost when assigning robots to exploration targets [S2]. Zlot and Stentz generalize market-based coordination to complex tasks using task trees, auctions, and bidding at multiple abstraction levels; their area reconnaissance example is close to multi-robot exploration and surveillance [S3]. Surveys confirm that frontier-based and coordinated allocation strategies are central families in multi-robot exploration [S17, S18].

The practical implication is that Argus should avoid a single global “best frontier” policy for multi-robot settings. It should expose team-level constraints and utilities: duplicate-coverage penalties, separation/connectivity constraints, robot-specific cost-to-target, expected marginal map gain, and whether a skill consumes one robot or coordinates several. A gated selector can start with deterministic or bandit-style scoring but should keep the action interface allocation-aware.

### 3. Planner parameter adaptation is a strong near-term analogue for exploration-skill tuning

APPLD learns planner parameters from human demonstration so a robot can adapt an existing navigation stack in complex environments [S4]. APPLI learns multiple parameter presets from human interventions and chooses among them with confidence during deployment [S5]. These systems are not exploration strategy selectors, but they are highly relevant because they keep the trusted navigation stack and adapt at a higher level: parameter sets, not raw actions.

For Argus, this argues for tuning skill parameters before training full RL policies. Examples: frontier-cluster radius, information-gain weight, risk penalty, minimum commitment time, revisit threshold, multi-robot dispersion weight, and fallback threshold. The APPLI pattern is especially useful: collect “intervention-like” events such as stalls, repeated failed frontiers, near-collisions, no-map-growth windows, or connectivity violations, then learn which skill preset would have avoided the issue [S5].

### 4. Planner/skill switching is an emerging robotics pattern

Hybrid Classical/RL Local Planner switches between a classical velocity-space planner and an RL planner using a simple meta-reasoning policy; the fetched abstract reports better live-robot performance than either planner alone and a 26% navigation-time improvement [S6]. Local planner selection using machine learning [S7] and DRL-based control switching across navigation planners [S8] further indicate that treating planners as selectable modules is a live research direction.

The central contradiction is also useful: classical planners tend to be smoother and more predictable, while learned planners may handle dynamic obstacles better but can be less smooth or harder to audit [S6]. Argus should therefore include explicit planner/skill capability metadata and guardrails rather than assuming a learned selector always improves performance. A selector should know when a skill is eligible, when it is disallowed, and when a fallback must override it.

### 5. Contextual bandits fit first-version online exploration skill selection better than full RL

Wakayama et al. model autonomous robotic exploration as a contextual multi-armed bandit over candidate survey sites, using hyperspectral context and preference/outcome models to adapt choices [S9]. The follow-on active-inference bandit work emphasizes dynamic preferences [S10]. Although the application is mineral survey site selection rather than indoor mapping, the mathematical fit is strong: choose one high-level arm now, observe delayed/noisy outcome, update future choice.

For Argus, contextual bandits are a reasonable intermediate between hand-coded scoring and full options learning. Context can include map frontier statistics, robot pose/health, inter-robot distance/connectivity, recent skill outcomes, environment morphology, and simulation scenario tags. Arms can be skill templates or skill-parameter presets. Reward can be a bounded multi-objective score: map gain, time cost, safety events, recovery events, duplicate coverage, and communication penalties. The bandit should be constrained by gates, because pure reward maximization can choose unsafe or thrashing actions.

### 6. Case-based and memory-based navigation supports retrieval-augmented skill selection

Older case-based navigation work directly addressed online selection and adaptation of reactive robotic control parameters [S11], global navigation in dynamic environments using stored cases [S12], and multi-strategy self-improving reactive control combining case-based reasoning and reinforcement learning [S13]. These papers predate modern deep learning stacks, but their architecture is surprisingly aligned with Argus: store context, retrieve similar cases, adapt a prior successful behavior, and update the case base after outcomes.

For Argus, memory should not merely be a log archive. It can become a retrieval feature for the selector: “in prior maps with narrow corridors and repeated frontier failures, dispersion skill outperformed nearest-frontier skill,” or “when comms dropped below threshold, regroup/connectivity repair dominated continued exploration.” This can be implemented before RL by indexing scenario/context/outcome tuples and using them to bias or veto skill choices.

### 7. Learned exploration policies are useful as a future path, but not the safest v1 selector

XGX for semantic embodied navigation explicitly combines exploration and exploitation modules, switching into exploitation when the goal becomes visible and using exploitation to teacher-force exploration [S14]. Curriculum RL for autonomous exploration and mapping uses local egocentric and global map abstractions to train an exploration policy [S15]. These systems show that learned exploration is viable and that modular switching can matter, but they are less immediately suitable for Argus’s first gated online skill selector than planner/parameter/bandit systems.

The reason is scope and observability. End-to-end or policy-heavy exploration papers often optimize a specific embodied-navigation benchmark or mapping setup. Argus needs a simulation-first workbench where the selector’s decisions remain explainable, reversible, and comparable across many robot/team configurations. Learned policies should be a later consumer of the same logs and skill API.

## Contradictions and Limitations

1. **Learning improves adaptation, but can reduce auditability.** Hybrid planner switching reports gains from combining classical and RL planners, but also notes different qualitative strengths: classical planning is smoother/path-tracking oriented, RL handles dynamic obstacles better but is less smooth [S6]. Argus should treat learned skills as conditional tools, not universal replacements.

2. **Bandit framing is compelling but domain transfer is incomplete.** Contextual bandit exploration papers are directly about autonomous robotic exploration choice, but the fetched primary example is mineral survey site selection with hyperspectral context, not indoor multi-robot map expansion [S9, S10]. The formalism transfers better than the empirical claims.

3. **Frontier and utility methods are mature but often myopic.** Frontier and next-best-view planners score immediate map gain/cost and can perform well, but greedy target selection can miss long-horizon structure, and utility estimates can be noisy or stale [S1, S16]. A selector should include commitment windows and replan/fallback logic to prevent oscillation.

4. **Case-based navigation is architecturally relevant but old.** CBR papers map well to memory-backed skill selection, yet many were built for older sensors, maps, and reactive controllers [S11-S13]. Use the pattern, not the exact implementation.

5. **Multi-robot allocation mechanisms assume decomposable tasks and comparable bids.** Market-based coordination works best when tasks can be decomposed and robots can estimate local costs well [S3]. Argus should record where bids were wrong, not just which task was assigned.

6. **Recent planner-selection papers are promising but not all details were accessible.** Some relevant recent work was identified through publisher/search pages only [S7, S8]. Treat these as directionally useful until full papers are reviewed.

## Concrete Implications for the Argus Design Spec

### A. Represent skills as high-level selectable arms with typed proposals

Each exploration skill should expose a typed proposal, not just an opaque command:

- skill ID and version;
- candidate target(s) or allocation(s);
- predicted information gain;
- travel/time cost;
- risk/safety estimate;
- expected communication/connectivity impact;
- applicability predicate;
- tunable parameter set;
- minimum commitment and cancellation conditions.

This follows frontier/next-best-view scoring [S1, S16], multi-robot utility allocation [S2, S3], and planner-switching systems [S6-S8].

### B. Start with gated scoring plus contextual logging, then graduate to contextual bandits

A defensible staged path is:

1. **Hand-coded gated selector:** hard eligibility gates, weighted utility score, fallback rules.
2. **Case/memory-biased selector:** retrieve similar scenario/outcome records and adjust scores [S11-S13].
3. **Contextual bandit selector:** learn skill/preset choice from logged context/action/outcome tuples [S9, S10].
4. **Options/RL path:** train policies or option models after the skill API and reward logs stabilize.

This avoids prematurely replacing navigation with opaque low-level RL while preserving a future learning path.

### C. Include intervention-style events as first-class training signals

APPLI shows the value of learning from interventions rather than requiring full demonstrations [S5]. Argus should log events that act like interventions:

- no frontier reached within timeout;
- map gain below threshold for N seconds;
- repeated frontier invalidation;
- collision/near-collision or local planner recovery;
- comms/connectivity violation;
- robot stuck/spinning;
- excessive duplicate coverage;
- human or scripted oracle override in simulation.

These events can supervise future skill-preset selection or provide negative reward for bandit/RL training.

### D. Use memory retrieval before full model learning

Case-based navigation suggests a lightweight memory system can be useful before a learned policy is mature [S11-S13]. Store scenario features, selected skill, parameters, outcome metrics, and failure signatures. Retrieval can support:

- score priors for similar map morphology;
- vetoes for skills known to fail in similar contexts;
- fallback recommendations;
- simulation curriculum generation from repeated failure clusters.

### E. Make multi-robot allocation a native action type

Multi-robot exploration papers allocate robots to targets or tasks, not merely choose one global strategy [S2, S3]. Argus should support skills that output team-level assignments:

- one robot to nearest frontier, another to high-uncertainty region;
- split team subject to max separation;
- regroup/connectivity-repair action;
- auction-style per-robot bid table;
- explicit duplicate-coverage penalty.

### F. Add anti-thrashing and safety gates

The literature’s myopic-selection problem implies specific guardrails:

- minimum dwell/commitment time per selected skill unless safety triggers;
- hysteresis before switching between similar skills;
- cooldown after a skill fails;
- fallback to conservative frontier or recovery behavior;
- hard gates for unsafe planner modes, low battery, comms loss, or map uncertainty;
- audit log with “why selected” and “why rejected” fields.

### G. Define rewards as bounded multi-objective outcomes

For bandit/RL readiness, each skill execution should produce a bounded outcome vector rather than one opaque scalar:

- explored area / map entropy reduction;
- unique frontier reduction;
- time and path length;
- safety/recovery penalties;
- duplicate coverage;
- communication/connectivity penalties;
- terminal success/failure;
- human/scripted override indicator.

The scalar score can be a configurable projection of this vector, enabling preference changes like those emphasized by active-inference bandit work [S9, S10].

## Source List

[S1] Brian Yamauchi, “A Frontier-Based Approach for Autonomous Exploration,” IEEE CIRA, 1997. URL: https://ieeexplore.ieee.org/abstract/document/613851/ ; PDF: http://www.robotfrontier.com/papers/cira97.pdf

[S2] Wolfram Burgard, Mark Moors, Cyrill Stachniss, Frank E. Schneider, “Coordinated Multi-Robot Exploration,” IEEE Transactions on Robotics, 2005. URL: https://ieeexplore.ieee.org/abstract/document/1435481/

[S3] Robert Zlot and Anthony Stentz, “Market-Based Multirobot Coordination for Complex Tasks,” International Journal of Robotics Research, 25(1):73–101, 2006. DOI: 10.1177/0278364906061160. URL: https://journals.sagepub.com/doi/abs/10.1177/0278364906061160

[S4] Xuesu Xiao, Bo Liu, Garrett Warnell, Jonathan Fink, Peter Stone, “APPLD: Adaptive Planner Parameter Learning from Demonstration,” IEEE Robotics and Automation Letters / IROS, 2020. arXiv:2004.00116. DOI: 10.48550/arXiv.2004.00116. URL: https://arxiv.org/abs/2004.00116

[S5] Zizhao Wang, Xuesu Xiao, Bo Liu, Garrett Warnell, Peter Stone, “APPLI: Adaptive Planner Parameter Learning from Interventions,” ICRA, 2021. arXiv:2011.00400. DOI: 10.48550/arXiv.2011.00400. URL: https://arxiv.org/abs/2011.00400

[S6] Vishnu D. Sharma, Jeongran Lee, Matthew Andrews, Ilija Hadžić, “Hybrid Classical/RL Local Planner for Ground Robot Navigation,” arXiv, 2024. arXiv:2410.03066. DOI: 10.48550/arXiv.2410.03066. URL: https://arxiv.org/abs/2410.03066

[S7] H. K. Öner and V. Sezer, “Local Planner Selection for Autonomous Robots Using Machine Learning,” International Journal of Intelligent Robotics and Applications, 2025. DOI: 10.1007/s41315-024-00387-2. URL: https://link.springer.com/article/10.1007/s41315-024-00387-2

[S8] K. U. Linh, J. Cox, T. Buiyan, “All-in-One: A DRL-Based Control Switch Combining State-of-the-Art Navigation Planners,” IEEE conference paper, 2022. URL: https://ieeexplore.ieee.org/abstract/document/9811797/

[S9] Shohei Wakayama, Alberto Candela, Paul Hayne, Nisar Ahmed, “Active Inference in Contextual Multi-Armed Bandits for Autonomous Robotic Exploration,” arXiv, 2024/2025. arXiv:2408.04119. DOI: 10.48550/arXiv.2408.04119. URL: https://arxiv.org/abs/2408.04119

[S10] Shohei Wakayama, Alberto Candela, Paul Hayne, Nisar Ahmed, “Active Inference for Bandit-Based Autonomous Robotic Exploration with Dynamic Preferences,” IEEE/TRO listing, 2025. DOI noted from arXiv page: 10.1109/TRO.2025.3577041. URL: https://ieeexplore.ieee.org/abstract/document/11025188/

[S11] Ashwin Ram and Juan Carlos Santamaría, “Case-Based Reactive Navigation: A Method for On-Line Selection and Adaptation of Reactive Robotic Control Parameters,” IEEE conference paper, 1997. URL: https://ieeexplore.ieee.org/abstract/document/584946/

[S12] David W. Aha, Leonard A. Breslow, Héctor Muñoz-Avila, “Conversational Case-Based Reasoning,” Applied Intelligence, 2001, includes related case-based planning/navigation work; global navigation result identified as “Global Navigation in Dynamic Environments Using Case-Based Reasoning.” DOI: 10.1023/A:1020979520454. URL: https://link.springer.com/article/10.1023/A:1020979520454

[S13] Ashwin Ram, Ronald C. Arkin, Kenneth Moorman, Robin J. Clark, “Case-Based Reactive Navigation: A Case-Based Method for On-Line Selection and Adaptation of Reactive Robotic Control Parameters” / related multistrategy CBR+RL navigation publications, Georgia Tech repository record. URL: https://repository.gatech.edu/entities/publication/56f3946e-2002-4ce0-93c4-71fc58f3ad44

[S14] Justin Wasserman, Girish Chowdhary, Abhinav Gupta, Unnat Jain, “Exploitation-Guided Exploration for Semantic Embodied Navigation,” arXiv, 2023; IEEE Robotics and Automation Letters listing, 2024. arXiv:2311.03357. DOI: 10.48550/arXiv.2311.03357. URL: https://arxiv.org/abs/2311.03357

[S15] Zhi Li, Jinghao Xin, Ning Li, “Autonomous Exploration and Mapping for Mobile Robots via Cumulative Curriculum Reinforcement Learning,” arXiv, 2023. arXiv:2302.13025. DOI: 10.48550/arXiv.2302.13025. URL: https://arxiv.org/abs/2302.13025

[S16] M. Selin, M. Tiger, D. Duberg, F. Heintz, “Efficient Autonomous Exploration Planning of Large-Scale 3-D Environments,” IEEE Robotics and Automation Letters / ICRA listing, 2019. URL: https://ieeexplore.ieee.org/abstract/document/8633925/

[S17] S. Sharma and R. Tiwari, “A Survey on Multi Robots Area Exploration Techniques and Algorithms,” 2016 International Conference listing. URL: https://ieeexplore.ieee.org/abstract/document/7514570/

[S18] X. Hu and H. Pei, “A Review of Coordinated Multi-Robot Exploration,” Journal of Physics: Conference Series, 2024. DOI: 10.1088/1742-6596/2798/1/012037. URL: https://iopscience.iop.org/article/10.1088/1742-6596/2798/1/012037/meta

## Notes on Source Quality

- Strongest direct evidence for Argus v1 design: [S1-S6], [S9], [S11-S13].
- Best multi-robot evidence: [S2], [S3], [S17], [S18].
- Best future-path evidence for learned exploration: [S14], [S15].
- Sources [S7], [S8], and [S16] were accepted as relevant but should be re-read from full PDFs before making strong quantitative claims beyond their abstracts/listings.
