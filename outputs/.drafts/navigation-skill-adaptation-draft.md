# Skill-Based Adaptation of Navigation Strategies

## Executive Summary

The literature supports the Argus design direction: start with a **gated online selector over named navigation/exploration skills**, not end-to-end low-level motor-policy learning. The strongest foundations come from the options framework, which defines a skill-like option as a temporally extended action with an initiation set, internal policy, and termination condition [S1]. For Argus, this maps directly to exploration skills such as frontier pursuit, coverage sweep, recovery, robot deconfliction, relay/rendezvous, and viewpoint shift. The first implementation should preserve these semantics explicitly rather than hiding them inside an opaque policy.

The most important correction from the research is the positioning of the two user-referenced papers. **arXiv:2207.07560 is SkiMo, Skill-based Model-based Reinforcement Learning**, and it is central to the future path: learn skill dynamics/outcome models and plan in skill space [S5]. **arXiv:2411.02998 is FraCOs, Accelerating Task Generalisation with Multi-Level Skill Hierarchies**, and it is better treated as evidence for future multi-level hierarchy/generalization, not the primary near-term model for Argus [S6]. Near term, the stronger applied precedents are adaptive planner parameter learning, planner switching, contextual bandits, frontier/utility exploration, and reproducible embodied-navigation evaluation [S7][S8][S9][S10][S11][S12].

The design spec should be tightened in six ways: define every skill as an option-like contract; require typed skill proposals and bounded outcome vectors; add explicit termination taxonomy and anti-thrashing controls; add decision/outcome trace logging as a contract, not a nice-to-have; define a promotion ladder from offline replay to shadow mode to constrained online control; and split online reward from offline audit metrics to reduce reward hacking and non-reproducible claims [S13][S14][S15][S16][S17].

## 1. What the Literature Means by Skills for Navigation

The canonical vocabulary is the options framework: an option has an initiation set, a policy, and a termination condition; selecting among options turns primitive-step decision-making into semi-Markov decision-making over temporally extended actions [S1]. HRL surveys and MAXQ-style decompositions reinforce that useful hierarchies depend on well-chosen subtask boundaries and state abstractions, not arbitrary action bundles [S2][S3]. Option-Critic shows that selection and termination can later be learned end-to-end, but it also raises interpretability and stability concerns for operational robotics [S4].

For Argus, the key implication is simple: every exploration skill should look like an option even before it is learned. A `frontier_pursuit` skill should declare when it is applicable, what parameters it accepts, what behavior it delegates to existing planners/controllers, when it terminates, and which outcome fields prove whether it helped. This preserves debuggability while giving future RL a clean policy-over-options interface.

## 2. Why Gated Online Selection Is the Right Near-Term Design

Applied navigation literature favors constrained adaptation at the strategy/planner layer. APPLD adapts planner parameters from demonstrations while keeping the navigation stack intact [S7]. APPLI extends that idea by learning parameter presets from interventions and selecting them with confidence during deployment [S8]. Hybrid Classical/RL Local Planner treats planners as switchable modules and reports benefits from choosing between classical and RL local planning under a meta-controller [S9]. These systems are closer to the Argus v1 target than monolithic learned exploration policies because they adapt high-level choices without taking over low-level control.

Frontier exploration and multi-robot exploration provide the base structure: choose high-level exploration targets by balancing expected information gain against travel/coordination cost [S10][S11]. Market-based multi-robot coordination generalizes this into task decomposition, bidding, and allocation across robots [S12]. For Argus, the selector should not merely pick a global skill; some skills should emit team-level assignments or candidate allocations.

Contextual bandits and case-based navigation are the right intermediate learning tools. Active-inference contextual bandit work models autonomous robotic exploration as choosing among candidate survey arms under context and changing preferences [S13]. Older case-based navigation work supports retrieving similar prior situations and adapting control parameters or strategy choices [S18]. Together, they suggest a staged path: hand-authored gated scoring, then memory-biased scoring, then contextual bandits, then full options/RL.

## 3. Model-Based Skill Planning Is the Future Path, Not the First Step

SkiMo learns a skill repertoire and skill dynamics model, then plans in skill space for long-horizon tasks including navigation and manipulation [S5]. This is highly relevant to the future direction the user asked for: Argus logs should eventually train per-skill outcome models that predict map gain, frontier deltas, travel cost, failure probability, robot overlap, localization risk, and future affordances.

The skill-effect and TAMP literature strengthens this recommendation. Learned symbolic operators, neuro-symbolic skills, compositional skill models, and learned skill-effect models all show how completed executions can become precondition/effect, success-condition, feasibility, or sampler models for higher-level planning [S19][S20][S21]. For navigation/exploration, the equivalent is not predicting raw maps. It is predicting compact planning-relevant effects over map/topology/team features.

Deep affordance and visual-affordance work adds one more useful idea: plan not only by immediate reward, but by what future actions become possible [S22][S23]. Exploration skills often matter because they unlock future frontiers, better viewpoints, communication routes, loop-closure candidates, or safe staging positions. The Argus outcome schema should therefore include future affordance creation, not just immediate coverage gain.

## 4. Evaluation and Guardrails

Embodied-navigation evaluation literature warns against ad hoc success claims and encourages standardized tasks, train/test scene separation, success/efficiency metrics, and generalization checks [S14][S24]. Exploration needs different primary metrics than point-goal navigation: coverage over time, information gain per cost, map quality, recovery behavior, team overlap, idle time, and robustness across seeds/scenarios [S10][S11].

Deep-RL reproducibility work is directly relevant to promotion gates. Results are sensitive to seeds, implementation details, hyperparameters, and benchmark noise; credible claims need multi-seed evaluation, interval estimates, robust aggregate summaries, and enough statistical power [S15][S16][S25]. Procedural-generation benchmarks show why held-out map instances matter: agents can overfit to narrow layout distributions and fail on unseen worlds [S26].

Safety literature adds the failure taxonomy. Reward hacking, negative side effects, unsafe exploration, distribution shift, and objective mismatch are documented recurring problems [S17][S27]. For Argus, this means the online selector may use a compact reward or score, but promotion must audit independent simulator-ground-truth metrics. If the online reward uses estimated information gain, the audit should check true reachable coverage and map correctness from MuJoCo/world state.

## 5. Spec Review Refinements for Argus

### A. Define every skill as an option-like contract

Each skill should declare:

- stable id and version;
- semantic purpose;
- initiation/precondition predicates;
- parameter schema;
- typed proposal output;
- authority level;
- expected effects;
- termination conditions;
- failure modes and cooldown behavior;
- required telemetry fields.

This directly follows the options framework [S1] and keeps the selector compatible with later policy-over-options learning [S4][S5].

### B. Require typed skill proposals

A skill should not return an opaque command. It should return candidate proposals with:

- candidate target or robot allocation;
- predicted information/coverage gain;
- travel or time cost;
- safety/risk estimate;
- communication/connectivity impact;
- expected map/topology effect;
- minimum commitment window;
- cancellation/termination triggers.

This borrows from frontier utility and multi-robot allocation literature [S10][S11][S12].

### C. Make termination first-class

The spec should distinguish termination types:

- success termination;
- failure termination;
- economic termination when marginal gain is too low;
- coordination termination when another robot makes the action redundant;
- safety termination;
- precondition-invalidated termination;
- operator/scripted override.

Termination is part of the definition of an option, not bookkeeping [S1]. It is also where practical skill sequencing often fails.

### D. Add anti-thrashing and intervention-style events

The selector should include dwell times, hysteresis, switch penalties, failed-skill cooldowns, and no-progress watchdogs. It should log intervention-style events such as no map growth, repeated invalid frontiers, stuck/spinning, connectivity loss, near-collision, excessive duplicate coverage, or scripted oracle override. APPLI shows that interventions are useful learning signals for navigation-stack adaptation [S8].

### E. Use bounded outcome vectors, not one scalar score

Each outcome window should produce a bounded vector:

- coverage/map gain;
- entropy or frontier delta;
- path length/time/effort;
- safety events;
- recovery events;
- duplicate coverage;
- communication/connectivity change;
- map quality/audit metric;
- termination reason;
- override/fallback flag.

The balanced score can be a projection of this vector, but the vector must remain available for audit, debugging, and reward redesign. This reduces reward hacking risk [S17][S27].

### F. Add a promotion ladder

A candidate selector should pass:

1. offline replay over logged episodes;
2. shadow mode alongside baseline;
3. constrained online simulation with fallback/risk vetoes;
4. stress testing across held-out scenarios, procedural maps, noise, failures, and multi-robot settings;
5. release/promotion gate with robust statistics and no-regression safety checks.

This matches embodied-AI evaluation practice and RL reproducibility guidance [S14][S15][S16][S24].

### G. Keep deterministic baselines alive

Classical frontier/utility exploration should remain first-class as baseline, fallback, and regression oracle [S10][S11]. A learned selector that cannot robustly beat deterministic exploration across held-out seeds/scenarios should stay in shadow mode.

### H. Position full RL/options as a staged future path

The future path should be:

```mermaid
flowchart LR
  A[Typed hand-authored skills] --> B[Gated scoring selector]
  B --> C[Memory-biased selector]
  C --> D[Contextual bandit selector]
  D --> E[Learned skill outcome models]
  E --> F[Short-horizon skill-space planning]
  F --> G[Full HRL/options learner]
```

Caption: Recommended progression from auditable skill contracts to full HRL/options learning. The sequence is synthesized from options/HRL foundations [S1][S4], planner adaptation [S7][S8], contextual bandit exploration [S13], and SkiMo-style skill-space planning [S5].

FraCOs belongs at the far-right side of this path: multi-level hierarchy/generalization after the state/action/outcome contracts are stable [S6].

## 6. Claim Sweep and Verification Notes

Critical claims were cross-supported by at least two independent source families:

- Option-like contracts are grounded in options/HRL foundations [S1][S2][S3][S4].
- Gated high-level adaptation is grounded in planner-parameter adaptation, planner switching, frontier/multi-robot exploration, and contextual bandits [S7][S8][S9][S10][S11][S12][S13].
- Future model-based skill planning is grounded in SkiMo and learned skill-effect/TAMP literature [S5][S19][S20][S21].
- Promotion/evaluation recommendations are grounded in embodied navigation, RL reproducibility, procedural generation, and safety literature [S14][S15][S16][S17][S24][S25][S26][S27].

Verification caveats:

- Several publisher DOI pages redirect or restrict full content, but canonical titles and metadata were verified where possible.
- The Yamauchi frontier PDF URL found by a researcher did not verify cleanly through WebFetch; the final report relies on the canonical IEEE/DOI-style citation from researcher evidence rather than a stale PDF mirror.
- Quantitative claims from recent planner-switching papers should not be overused until full papers are re-read; this report treats them as directional precedent, not definitive proof for Argus.

## Open Questions

1. What exact `SkillState` abstraction will be sufficient for Argus without leaking raw map/planner internals into the learner?
2. How many scenarios/seeds should be required for promotion gates? The literature says multi-seed and held-out suites, but Argus needs a project-specific budget.
3. Should the first learner be pure gated scoring, memory-biased scoring, or a contextual bandit? The research supports this progression, but implementation cost differs.
4. Which audit metric should be hidden from the selector to detect reward hacking: ground-truth reachable coverage, map accuracy, or both?
5. How should multi-robot assignment proposals be represented so the selector can compare single-robot and team-level skills fairly?

## Source List

[S1] Richard S. Sutton, Doina Precup, Satinder Singh. “Between MDPs and semi-MDPs: A Framework for Temporal Abstraction in Reinforcement Learning.” Artificial Intelligence, 1999. https://doi.org/10.1016/S0004-3702(99)00052-1

[S2] Andrew G. Barto, Sridhar Mahadevan. “Recent Advances in Hierarchical Reinforcement Learning.” Discrete Event Dynamic Systems, 2003. https://doi.org/10.1023/A:1022140919877

[S3] Thomas G. Dietterich. “Hierarchical Reinforcement Learning with the MAXQ Value Function Decomposition.” JAIR, 2000. https://doi.org/10.1613/jair.639

[S4] Pierre-Luc Bacon, Jean Harb, Doina Precup. “The Option-Critic Architecture.” AAAI 2017. https://arxiv.org/abs/1609.05140

[S5] Lucy Xiaoyang Shi, Joseph J. Lim, Youngwoon Lee. “Skill-based Model-based Reinforcement Learning.” arXiv:2207.07560. https://arxiv.org/abs/2207.07560

[S6] Thomas P. Cannon, Özgür Şimşek. “Accelerating Task Generalisation with Multi-Level Skill Hierarchies.” arXiv:2411.02998. https://arxiv.org/abs/2411.02998

[S7] Xuesu Xiao, Bo Liu, Garrett Warnell, Jonathan Fink, Peter Stone. “APPLD: Adaptive Planner Parameter Learning from Demonstration.” arXiv:2004.00116. https://arxiv.org/abs/2004.00116

[S8] Zizhao Wang, Xuesu Xiao, Bo Liu, Garrett Warnell, Peter Stone. “APPLI: Adaptive Planner Parameter Learning From Interventions.” arXiv:2011.00400. https://arxiv.org/abs/2011.00400

[S9] Vishnu D. Sharma, Jeongran Lee, Matthew Andrews, Ilija Hadžić. “Hybrid Classical/RL Local Planner for Ground Robot Navigation.” arXiv:2410.03066. https://arxiv.org/abs/2410.03066

[S10] Brian Yamauchi. “A Frontier-Based Approach for Autonomous Exploration.” IEEE CIRA, 1997. https://doi.org/10.1109/CIRA.1997.613851

[S11] Wolfram Burgard, Mark Moors, Cyrill Stachniss, Frank E. Schneider. “Coordinated Multi-Robot Exploration.” IEEE Transactions on Robotics, 2005. https://doi.org/10.1109/TRO.2005.852237

[S12] Robert Zlot, Anthony Stentz. “Market-based Multirobot Coordination for Complex Tasks.” IJRR, 2006. https://doi.org/10.1177/0278364906061160

[S13] Shohei Wakayama, Alberto Candela, Paul Hayne, Nisar Ahmed. “Active Inference in Contextual Multi-Armed Bandits for Autonomous Robotic Exploration.” arXiv:2408.04119. https://arxiv.org/abs/2408.04119

[S14] Peter Anderson et al. “On Evaluation of Embodied Navigation Agents.” arXiv:1807.06757. https://arxiv.org/abs/1807.06757

[S15] Peter Henderson et al. “Deep Reinforcement Learning that Matters.” arXiv:1709.06560. https://arxiv.org/abs/1709.06560

[S16] Rishabh Agarwal et al. “Deep Reinforcement Learning at the Edge of the Statistical Precipice.” NeurIPS 2021. https://arxiv.org/abs/2108.13264

[S17] Dario Amodei et al. “Concrete Problems in AI Safety.” arXiv:1606.06565. https://arxiv.org/abs/1606.06565

[S18] Ashwin Ram, Juan Carlos Santamaría. “Case-Based Reactive Navigation: A Method for On-Line Selection and Adaptation of Reactive Robotic Control Parameters.” IEEE, 1997. https://ieeexplore.ieee.org/abstract/document/584946/

[S19] Tom Silver, Rohan Chitnis, Joshua Tenenbaum, Leslie Pack Kaelbling, Tomás Lozano-Pérez. “Learning Symbolic Operators for Task and Motion Planning.” arXiv:2103.00589. https://arxiv.org/abs/2103.00589

[S20] Tom Silver, Ashay Athalye, Joshua B. Tenenbaum, Tomás Lozano-Pérez, Leslie Pack Kaelbling. “Learning Neuro-Symbolic Skills for Bilevel Planning.” arXiv:2206.10680. https://arxiv.org/abs/2206.10680

[S21] Jacky Liang et al. “Search-Based Task Planning with Learned Skill Effect Models for Lifelong Robotic Manipulation.” arXiv:2109.08771. https://arxiv.org/abs/2109.08771

[S22] Danfei Xu et al. “Deep Affordance Foresight: Planning Through What Can Be Done in the Future.” arXiv:2011.08424. https://arxiv.org/abs/2011.08424

[S23] Alexander Khazatsky, Ashvin Nair, Daniel Jing, Sergey Levine. “What Can I Do Here? Learning New Skills by Imagining Visual Affordances.” arXiv:2106.00671. https://arxiv.org/abs/2106.00671

[S24] Manolis Savva et al. “Habitat: A Platform for Embodied AI Research.” ICCV 2019. https://arxiv.org/abs/1904.01201

[S25] Cédric Colas, Olivier Sigaud, Pierre-Yves Oudeyer. “How Many Random Seeds? Statistical Power Analysis in Deep Reinforcement Learning Experiments.” arXiv:1806.08295. https://arxiv.org/abs/1806.08295

[S26] Karl Cobbe et al. “Leveraging Procedural Generation to Benchmark Reinforcement Learning.” ICML 2020. https://arxiv.org/abs/1912.01588

[S27] Jan Leike et al. “AI Safety Gridworlds.” arXiv:1711.09883. https://arxiv.org/abs/1711.09883
