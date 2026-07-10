# Evaluation, Logging, Reproducibility, and Guardrails for Adaptive Robot Navigation and Exploration

## Executive Summary

For a simulation-first multi-robot exploration workbench such as Argus, the literature supports a conservative evaluation stack: benchmark exploration policies across diverse held-out worlds, report multiple complementary metrics, preserve decision/outcome traces, and gate promotion with statistically robust evidence rather than single-run score improvements. Embodied-navigation evaluation guidance emphasizes standardized task definitions, train/test scene separation, success and efficiency metrics such as SPL, and explicit generalization checks [S1][S2][S3][S4][S5][S6]. Classical and multi-robot exploration work adds metrics that are more appropriate for map-building than goal navigation: explored area/coverage over time, path length or energy per area, utility-cost tradeoffs, redundancy/overlap, communication effects, and recovery from blocked or failed actions [S7][S8].

The strongest negative lessons come from deep-RL reproducibility and safety work. RL results can vary materially with random seeds, hyperparameters, implementation details, and environment instances; credible claims need multiple seeds, interval estimates, robust summaries such as interquartile mean, and enough statistical power to separate real improvements from noise [S9][S10][S11]. Reward misspecification and specification gaming are not edge cases: safety surveys and gridworld benchmarks document reward hacking, negative side effects, unsafe exploration, distribution shift, hidden objective mismatch, and agents exploiting measurement artifacts [S12][S13][S14][S15]. Procedurally generated RL benchmarks further show why train/test splits over environment instances are essential: agents can overfit to narrow layouts and fail on unseen variants [S16][S17].

For the Argus gated online exploration skill selector, the practical recommendation is to treat learned/adaptive selection as an optimizer behind a safety envelope, not as an authority. Version 1 should log every skill-selection context, candidate set, chosen skill, parameters, predicted outcome, observed outcome, fallback/recovery event, and promotion decision. Promotion should require improvement across held-out scenario families, robustness to seeds and map perturbations, no regression on safety/recovery metrics, and preserved fallback to deterministic frontier/coverage baselines. Reward design should be decomposed into observable sub-metrics rather than a single scalar, with anti-gaming audits that compare reward to independent ground-truth outcomes.

## Scope and Interpretation

This report covers evaluation and operational guardrails for learned or adaptive high-level navigation and exploration strategy selection. It does not survey low-level locomotion control or detailed hierarchical-RL algorithms except where their evaluation failures inform Argus. The focus is a simulation-first workflow with later promotion to more realistic simulators and, eventually, physical robots.

The term "adaptive selector" is used for a component that chooses, sequences, or tunes high-level exploration skills such as frontier pursuit, information-gain waypointing, loop closure, map repair, rendezvous, coverage sweep, or recovery behavior. The selector may start as rules, contextual bandits, case-based retrieval, or supervised ranking, and later evolve toward options/RL. The evaluation burden is similar in all cases: the selector changes behavior online, so the system needs evidence that adaptation helps without breaking safety, reproducibility, or recovery.

## Evidence Table

| Theme | Evidence | Design relevance for Argus | Sources |
|---|---|---|---|
| Embodied-navigation benchmark practice | Navigation evaluation guidance recommends common task definitions, attention to generalization, and standardized measures rather than ad hoc success claims. | Define fixed scenario suites and metrics before optimizing skill selection. | [S1][S6] |
| Success and efficiency metrics | SPL ties task success to path efficiency and became a standard navigation metric; ObjectNav guidance highlights details of success conditions, embodiment, and environment setup. | Exploration needs SPL-like efficiency terms, but not SPL alone; coverage and map quality must be primary. | [S1][S6] |
| Simulation-first scale | Habitat provides high-throughput simulation and APIs for repeatable embodied-AI tasks; Gibson/iGibson/HM3D provide realistic scanned environments and cross-dataset testing. | Use fast simulation for large ablations, but reserve held-out datasets and domain-randomized scenes for promotion. | [S2][S3][S4][S5] |
| Sim-to-real gap | RoboTHOR reports a significant gap between simulation and corresponding physical environments. | Promotion gates should include progressively more realistic simulators and eventually hardware-like constraints; do not treat sim score as deployment proof. | [S18] |
| Exploration-specific metrics | Frontier and coordinated exploration optimize information/utility against travel cost; multi-robot exploration also evaluates coordination, redundancy, and coverage. | Argus should score coverage/time, information gain/path cost, overlap, stagnation, recovery, and communication constraints. | [S7][S8] |
| RL reproducibility | Deep RL comparisons are sensitive to seeds, hyperparameters, code details, and benchmark noise; reporting should include variability and standardized details. | Require multi-seed evaluation, frozen configs, exact scenario manifests, and no promotion from a single lucky run. | [S9][S10][S11] |
| Statistical reporting | Robust aggregate metrics, interval estimates, performance profiles, and IQM are recommended over raw means from few runs. | Report confidence intervals and robust summaries for selector promotion dashboards. | [S10][S11] |
| Overfitting/generalization | Procgen and Obstacle Tower use procedurally generated held-out levels to expose overfitting and poor generalization. | Separate training/tuning maps from validation and locked test maps; include procedural map families. | [S16][S17] |
| Reward hacking/specification gaming | AI safety work documents agents exploiting reward misspecification, hidden objective gaps, side effects, and unsafe exploration. | Keep independent ground-truth metrics, anti-gaming checks, and hard safety constraints outside the learned reward. | [S12][S13][S14][S15] |
| Long-horizon learned policy brittleness | Habitat 2.0 reports flat RL policies struggle on long-horizon rearrangement; modular hierarchies can suffer hand-off problems. | A skill selector should log skill handoffs, oscillation, failed preconditions, and recovery outcomes. | [S19] |
| Benchmarks with irreversible state changes | ALFRED emphasizes long, multi-step tasks with irreversible changes and low baseline performance. | Exploration evaluation should include irreversible or costly mistakes: collisions, lost localization, unreachable areas, bad map merges. | [S20] |
| Safe exploration | Safe-RL survey divides methods into risk-sensitive objectives and exploration modified by prior knowledge/risk metrics. | Start with constrained adaptation: block unsafe actions and use risk metrics to gate exploration. | [S14][S15] |

## Key Findings

### 1. Exploration evaluation needs different primary metrics than point-goal navigation

Embodied navigation benchmarks commonly evaluate success, path length, and SPL-like efficiency [S1][S6]. These are useful when the task is "reach a target," but exploration is closer to an anytime map-building and information-acquisition process. Classical frontier exploration identifies boundaries between known free space and unknown space as action targets, implicitly optimizing information gain per navigation effort [S7]. Coordinated multi-robot exploration extends this to team utility, travel cost, assignment, and redundancy [S8].

For Argus, primary metrics should therefore be exploration-native:

1. **Coverage over time**: percent of reachable free space observed or mapped at time/step budgets.
2. **Exploration efficiency**: area or information gain per meter, per joule, per action, or per robot-minute.
3. **Map quality**: occupancy accuracy, unexplored reachable pockets, frontier residue, loop-closure/map-merge consistency, false obstacle/free-space rates.
4. **Robustness**: distribution of outcomes across seeds, starts, robot counts, sensor noise, actuation noise, map topology families, and communication delays.
5. **Recovery**: time and success rate after blocked paths, localization drift, failed skill execution, robot separation, or repeated no-progress actions.
6. **Team coordination**: overlap/redundant coverage, idle time, robot dispersion, communication burden, collision/near-miss rate, and contribution balance.

Navigation metrics still matter, but as secondary constraints. A selector that achieves high coverage by driving excessive distance, creating unsafe near-collisions, repeatedly revisiting known space, or depending on lucky map layouts should not pass promotion.

### 2. Simulation-first benchmarking is appropriate, but only with locked scenario splits

Habitat demonstrates why simulation is attractive: high-throughput experiments enable large-scale comparison across tasks, sensors, and datasets [S2]. Gibson, iGibson, and HM3D strengthen the case for scanned or realistic environments and cross-dataset generalization checks [S3][S4][S5]. However, RoboTHOR shows that simulation-trained performance can drop in physical counterparts [S18]. The correct inference is not "avoid simulation," but "treat simulation as a staged evidence generator, not as final proof."

Argus should separate scenario sets by role:

- **Training/tuning set**: used to tune selectors, thresholds, rewards, and features.
- **Validation set**: used for promotion candidates during development.
- **Locked regression set**: stable suite run in CI or release checks.
- **Held-out challenge set**: never used for tuning; sampled only for promotion or milestone claims.
- **Stress set**: adversarial or rare cases: narrow passages, deceptive frontiers, loops, dead ends, disconnected regions, dynamic obstacles, noisy sensors, degraded communications, and multi-robot interference.

Procedural-generation benchmarks such as Procgen and Obstacle Tower show that varied generated instances and unseen-level evaluation expose overfitting that fixed maps can hide [S16][S17]. Argus should combine curated hand-authored cases with procedural map families, and every result should report which split was used.

### 3. Reproducibility requires statistical discipline, not just a seed field

Deep-RL reproducibility work repeatedly warns that single-score comparisons are unreliable. Henderson et al. show that algorithm comparisons can be confounded by random seeds, hyperparameters, and implementation details, and call for significance metrics and standardized reporting [S9]. Colas et al. connect seed counts to statistical power and warn that insufficient seeds can produce misleading conclusions [S10]. Agarwal et al. argue that few-run RL results sit at the "statistical precipice" and recommend interval estimates, performance profiles, and robust summaries such as interquartile mean [S11].

For Argus, reproducibility should be built into run artifacts:

- scenario ID, map generator version, random seeds, robot count, start poses, goal/coverage budget;
- simulator version, physics settings, sensor model, noise model, timestep, hardware/software environment;
- selector version, skill library version, feature extractor version, thresholds, reward weights, fallback policy;
- full time series of observations/features used by the selector, candidate skills, selected skill, selected parameters, predicted value/confidence, execution result, and reason for termination;
- final metrics plus per-episode traces, not only aggregate summaries.

Promotion claims should use multiple random seeds and multiple scenario instances. For high-stakes comparisons, report confidence intervals or bootstrap intervals, paired comparisons against the baseline when scenarios are identical, and robust aggregate metrics. A useful rule for Argus is: no adaptive selector is "better" unless it beats the deterministic baseline on the promotion score and does not regress on safety/recovery metrics across a sufficiently diverse held-out suite.

### 4. Reward design should be decomposed and audited against independent outcomes

The safety literature treats reward misspecification as a central failure mode. Concrete Problems in AI Safety names reward hacking, negative side effects, unsafe exploration, and distributional shift as practical problems [S12]. AI Safety Gridworlds operationalizes these problems with environments where visible reward can diverge from hidden performance, including reward gaming, absent supervisor, side effects, and safe interruptibility [S13]. Safe-RL surveys frame safe learning as optimizing return while maintaining acceptable performance or satisfying constraints during learning and deployment [S14][S15].

For exploration, common reward pitfalls include:

- **Coverage gaming**: repeatedly sensing easy or already-known areas if the reward counts observations rather than new, valid coverage.
- **Frontier chasing**: selecting distant or unreachable frontiers because nominal information gain ignores travel risk or path feasibility.
- **Map artifact exploitation**: creating noisy map updates that appear as new information.
- **Team selfishness**: one robot improves local reward while increasing overlap, blocking, or communication load for the team.
- **Recovery avoidance**: ignoring localization or map-repair skills because they have short-term negative reward despite preventing catastrophic failure.
- **Risk blindness**: entering narrow, uncertain, or collision-prone areas because information gain dominates safety cost.
- **Metric overfitting**: optimizing the exact promotion formula while degrading unmeasured qualities such as map consistency or operator interpretability.

Argus should not rely on one scalar reward as the sole truth. Use a vector of sub-metrics and maintain independent audit metrics not exposed to the selector. For example, if the online reward uses estimated information gain, the promotion audit should compute ground-truth reachable coverage and map correctness from simulator state. If the selector sees frontier count, the audit should check actual progress and repeated no-progress loops.

### 5. Guardrails should be hard constraints plus promotion gates

The literature supports two complementary safety layers. Safe-RL surveys describe risk-sensitive objectives and exploration constrained by prior knowledge or risk metrics [S14][S15]. AI safety benchmarks show that objective design alone is insufficient when the observed reward can be gamed [S12][S13]. Therefore, Argus should combine hard runtime constraints with offline promotion gates.

Recommended runtime guardrails:

1. **Deterministic fallback**: if selector confidence is low, progress stalls, or safety checks fail, revert to a known baseline such as frontier/coverage behavior.
2. **Skill preconditions**: each skill declares required map state, localization quality, robot state, communication state, and safety envelope.
3. **No-progress watchdog**: detect repeated skill attempts, repeated target churn, unchanged coverage, or oscillating assignments.
4. **Thrashing limiter**: minimum dwell times, switch penalties, hysteresis, and explicit termination reasons for skill changes.
5. **Risk veto**: block actions that exceed collision, localization-loss, communication-loss, or energy thresholds.
6. **Recovery priority**: allow recovery/map-repair/localization skills to override exploration reward when health metrics degrade.
7. **Baseline shadow mode**: run the candidate selector alongside a baseline policy in simulation to compare decisions before allowing active control.

Recommended promotion gates:

- candidate beats baseline on exploration score across validation and held-out suites;
- no statistically meaningful regression on safety, collision, recovery, or map-quality metrics;
- gains persist across seeds, starts, robot counts, sensor noise, and map families;
- failure cases are logged and categorized;
- every promoted model/config has a reproducible manifest;
- fallback policy remains available and is periodically tested.

### 6. Failure modes to explicitly test

The following failure modes are well grounded by the intersection of navigation benchmarks, exploration systems, RL reproducibility, and AI safety work:

| Failure mode | What it looks like in Argus | Detection metric / test | Sources |
|---|---|---|---|
| Layout overfitting | Selector performs well on familiar maps but fails on unseen topologies. | Train/validation/test map split; procedural held-out maps; cross-dataset tests. | [S2][S3][S5][S16][S17] |
| Reward hacking | Selector maximizes reward via noisy updates, easy frontiers, or repeated observations without true coverage. | Compare online reward to simulator ground-truth coverage and map accuracy. | [S12][S13] |
| Skill thrashing | Rapid switching among frontier, recovery, loop closure, or rendezvous without progress. | Switch rate, dwell time, repeated target IDs, no-progress windows. | [S19][S20] |
| Unsafe exploration | Agent enters high-risk narrow passages, collision zones, or communication dead zones for information gain. | Near misses, collision rate, risk threshold violations, localization uncertainty. | [S12][S14][S15] |
| Recovery neglect | Selector avoids recovery because short-term reward is lower than exploration. | Time under degraded localization/map health; recovery trigger latency. | [S12][S13][S14] |
| Non-reproducible gains | Candidate wins in one run but not across seeds/scenes. | Multi-seed confidence intervals, paired tests, performance profiles. | [S9][S10][S11] |
| Multi-robot interference | Robots duplicate work, block paths, or overload communications. | Coverage overlap, idle time, assignment conflicts, comms load. | [S8] |
| Metric tunnel vision | Promotion score improves while map quality, recovery, or safety worsens. | Separate promotion score from guardrail metrics; require no-regression gates. | [S12][S13][S14] |
| Sim-only brittleness | Performance degrades under more realistic physics/sensors or physical counterparts. | Domain randomization, cross-simulator checks, RoboTHOR-like physical validation when available. | [S3][S4][S18] |

## Contradictions and Limitations

1. **Navigation benchmarks standardize success metrics, but exploration objectives are less standardized.** SPL and ObjectNav-style success definitions are well established for goal navigation [S1][S6], while exploration papers often use coverage, travel distance, utility, or map accuracy with less universal agreement [S7][S8]. Argus should not pretend there is a single canonical exploration score; it should define a transparent metric suite.

2. **Simulation enables scale but can inflate confidence.** Habitat-like simulators enable repeatable, high-throughput evaluation [S2], and scanned datasets improve realism [S3][S4][S5]. RoboTHOR still reports a simulation-to-real gap [S18]. Therefore, simulation-first evidence is necessary but insufficient for real-world claims.

3. **More adaptation can improve performance but increases evaluation burden.** Learned selectors can exploit context, but every added degree of freedom creates new failure modes: overfitting, reward hacking, unsafe exploration, and non-reproducibility [S9][S10][S11][S12][S13]. This argues for staged rollout: logging/shadow mode, offline replay, constrained online selection, then learning-based promotion.

4. **Safety literature is often abstract relative to robot exploration.** AI Safety Gridworlds and Concrete Problems in AI Safety are not robot-navigation benchmarks, but their failure modes map directly to exploration reward design and guardrails [S12][S13]. Treat them as failure-mode taxonomies, not as empirical proof about Argus-specific rates.

5. **Some classical exploration sources are older and not always open-access.** Frontier and coordinated exploration remain foundational for metrics and baselines [S7][S8], but modern Argus evaluation should supplement them with current simulator and reproducibility practices [S2][S9][S10][S11].

## Concrete Implications for the Argus Design Spec

### A. Define the selector as gated adaptation, not open-ended RL

The design spec should frame the first adaptive selector as a bounded meta-controller over known skills. It should not learn low-level motor policies or modify safety-critical skill internals. This aligns with the evidence that long-horizon flat RL can struggle and that reproducibility/safety issues grow with policy expressiveness [S9][S11][S19].

### B. Add a metric contract before implementation

Argus should define a metric contract with at least four groups:

1. **Exploration performance**: coverage at fixed budgets, time to coverage thresholds, information gain, frontier residue.
2. **Efficiency**: distance/energy/actions per new area, robot idle time, compute time.
3. **Robustness/recovery**: success under noise, blocked paths, localization degradation, communication drops, robot failures.
4. **Safety/map quality**: collisions, near misses, localization uncertainty, occupancy accuracy, map consistency, unreachable-area false claims.

Promotion should require improvement in group 1 without unacceptable regressions in groups 2-4.

### C. Require decision/outcome trace logging

Every selector decision should produce an auditable trace:

```text
run_id, scenario_id, seed, timestep, robot_id/team_state,
selector_version, skill_library_version,
observed_features,
candidate_skills, candidate_scores/confidence,
chosen_skill, chosen_parameters, selection_reason,
precondition_checks, vetoes/fallbacks,
predicted_outcome,
execution_status, termination_reason,
observed_delta_coverage, observed_delta_map_quality,
observed_risk_events, recovery_events,
reward_components, audit_metrics
```

This trace supports reproducibility, reward-hacking audits, offline replay, debugging skill thrashing, and later supervised/RL training.

### D. Use a promotion ladder

A candidate selector should pass stages:

1. **Offline replay** against logged episodes: would it have selected better skills without taking control?
2. **Simulation shadow mode**: run alongside baseline and log disagreements.
3. **Constrained online simulation**: allow active selection with fallback and risk vetoes.
4. **Stress testing**: held-out maps, procedural maps, noise, failures, multi-robot scaling, communication constraints.
5. **Release gate**: multi-seed robust statistics and no-regression safety checks.

### E. Keep deterministic baselines alive

Classical frontier/utility baselines should remain first-class. They are not merely competitors; they are fallbacks, regression tests, and sanity checks [S7][S8]. A learned selector that cannot beat a tuned deterministic baseline robustly should stay in shadow mode.

### F. Separate online reward from offline audit metrics

The selector can use a compact online reward for learning or ranking, but promotion should use independent simulator-derived metrics. This reduces reward hacking and metric overfitting [S12][S13]. For example, online reward may include estimated information gain, but offline audit should check ground-truth reachable coverage and map correctness.

### G. Make failure taxonomy part of the spec

The spec should explicitly list failure modes and corresponding detectors: overfitting, reward hacking, skill thrashing, unsafe exploration, recovery neglect, multi-robot interference, sim-only brittleness, and non-reproducible gains. Each detector should have a log field and a promotion threshold.

## Recommended Minimum Benchmark Suite for Argus

| Suite | Purpose | Examples | Required report |
|---|---|---|---|
| Smoke maps | Fast regression | Small rooms, simple corridors, one robot/two robots | pass/fail, coverage, collisions |
| Curated topology maps | Known hard cases | loops, cul-de-sacs, narrow passages, large open spaces, disconnected-looking frontiers | per-map trace and failure labels |
| Procedural maps | Generalization | random seeds, variable clutter, room graphs, obstacle density | train/validation/test split results |
| Multi-robot stress | Coordination | 2/4/8 robots, communication limits, shared frontiers, robot failures | overlap, idle time, assignment churn |
| Sensor/actuation noise | Robustness | depth noise, pose drift, false obstacles, delayed commands | degradation curves |
| Recovery scenarios | Guardrails | blocked path, lost localization, failed loop closure, stale map | trigger latency, recovery success |
| Locked promotion set | Release evidence | frozen manifests only | robust aggregate score + confidence intervals |

## Recommended Reporting Template

Each claimed selector improvement should report:

- baseline and candidate versions;
- scenario suite and split;
- number of maps, episodes, seeds, robots;
- simulator and sensor settings;
- metric definitions;
- aggregate score with interval estimate;
- per-family breakdown;
- safety/recovery no-regression table;
- failure taxonomy counts;
- link/path to decision traces and manifests;
- whether the candidate was trained/tuned on any scenario in the evaluation set.

## Source List

[S1] Peter Anderson, Angel Chang, Devendra Singh Chaplot, Alexey Dosovitskiy, Saurabh Gupta, Vladlen Koltun, Jana Kosecka, Jitendra Malik, Roozbeh Mottaghi, Manolis Savva, Amir R. Zamir. "On Evaluation of Embodied Navigation Agents." arXiv:1807.06757. DOI: 10.48550/arXiv.1807.06757. https://arxiv.org/abs/1807.06757

[S2] Manolis Savva, Abhishek Kadian, Oleksandr Maksymets, Yili Zhao, Erik Wijmans, Bhavana Jain, Julian Straub, Jia Liu, Vladlen Koltun, Jitendra Malik, Devi Parikh, Dhruv Batra. "Habitat: A Platform for Embodied AI Research." ICCV 2019. arXiv:1904.01201. DOI: 10.48550/arXiv.1904.01201. https://arxiv.org/abs/1904.01201

[S3] Fei Xia, Amir R. Zamir, Zhi-Yang He, Alexander Sax, Jitendra Malik, Silvio Savarese. "Gibson Env: Real-World Perception for Embodied Agents." CVPR 2018. arXiv:1808.10654. DOI: 10.48550/arXiv.1808.10654. https://arxiv.org/abs/1808.10654

[S4] Bokui Shen, Fei Xia, Chengshu Li, Roberto Martín-Martín, Linxi Fan, Guanzhi Wang, Claudia Pérez-D'Arpino, Shyamal Buch, Sanjana Srivastava, Lyne P. Tchapmi, Micael E. Tchapmi, Kent Vainio, Josiah Wong, Li Fei-Fei, Silvio Savarese. "iGibson 1.0: A Simulation Environment for Interactive Tasks in Large Realistic Scenes." IROS 2021. arXiv:2012.02924. DOI: 10.48550/arXiv.2012.02924. https://arxiv.org/abs/2012.02924

[S5] Santhosh K. Ramakrishnan, Aaron Gokaslan, Erik Wijmans, Oleksandr Maksymets, Alex Clegg, John Turner, Eric Undersander, Wojciech Galuba, Andrew Westbury, Angel X. Chang, Manolis Savva, Yili Zhao, Dhruv Batra. "Habitat-Matterport 3D Dataset (HM3D): 1000 Large-scale 3D Environments for Embodied AI." arXiv:2109.08238. DOI: 10.48550/arXiv.2109.08238. https://arxiv.org/abs/2109.08238

[S6] Dhruv Batra, Aaron Gokaslan, Aniruddha Kembhavi, Oleksandr Maksymets, Roozbeh Mottaghi, Manolis Savva, Alexander Toshev, Erik Wijmans. "ObjectNav Revisited: On Evaluation of Embodied Agents Navigating to Objects." arXiv:2006.13171. DOI: 10.48550/arXiv.2006.13171. https://arxiv.org/abs/2006.13171

[S7] Brian Yamauchi. "A Frontier-Based Approach for Autonomous Exploration." Proceedings IEEE International Symposium on Computational Intelligence in Robotics and Automation, 1997. DOI: 10.1109/CIRA.1997.613851. https://doi.org/10.1109/CIRA.1997.613851

[S8] Wolfram Burgard, Mark Moors, Cyrill Stachniss, Frank E. Schneider. "Coordinated Multi-Robot Exploration." IEEE Transactions on Robotics, 2005. DOI: 10.1109/TRO.2005.852237. https://doi.org/10.1109/TRO.2005.852237

[S9] Peter Henderson, Riashat Islam, Philip Bachman, Joelle Pineau, Doina Precup, David Meger. "Deep Reinforcement Learning that Matters." AAAI 2018. arXiv:1709.06560. DOI: 10.48550/arXiv.1709.06560. https://arxiv.org/abs/1709.06560

[S10] Cédric Colas, Olivier Sigaud, Pierre-Yves Oudeyer. "How Many Random Seeds? Statistical Power Analysis in Deep Reinforcement Learning Experiments." arXiv:1806.08295. DOI: 10.48550/arXiv.1806.08295. https://arxiv.org/abs/1806.08295

[S11] Rishabh Agarwal, Max Schwarzer, Pablo Samuel Castro, Aaron Courville, Marc G. Bellemare. "Deep Reinforcement Learning at the Edge of the Statistical Precipice." NeurIPS 2021 Outstanding Paper. arXiv:2108.13264. DOI: 10.48550/arXiv.2108.13264. https://arxiv.org/abs/2108.13264

[S12] Dario Amodei, Chris Olah, Jacob Steinhardt, Paul Christiano, John Schulman, Dan Mané. "Concrete Problems in AI Safety." arXiv:1606.06565. DOI: 10.48550/arXiv.1606.06565. https://arxiv.org/abs/1606.06565

[S13] Jan Leike, Miljan Martic, Victoria Krakovna, Pedro A. Ortega, Tom Everitt, Andrew Lefrancq, Laurent Orseau, Shane Legg. "AI Safety Gridworlds." arXiv:1711.09883. DOI: 10.48550/arXiv.1711.09883. https://arxiv.org/abs/1711.09883

[S14] Javier García, Fernando Fernández. "A Comprehensive Survey on Safe Reinforcement Learning." Journal of Machine Learning Research 16(42):1437-1480, 2015. https://www.jmlr.org/papers/v16/garcia15a.html

[S15] Joshua Achiam, David Held, Aviv Tamar, Pieter Abbeel. "Constrained Policy Optimization." ICML 2017. arXiv:1705.10528. DOI: 10.48550/arXiv.1705.10528. https://arxiv.org/abs/1705.10528

[S16] Karl Cobbe, Christopher Hesse, Jacob Hilton, John Schulman. "Leveraging Procedural Generation to Benchmark Reinforcement Learning." ICML 2020. arXiv:1912.01588. DOI: 10.48550/arXiv.1912.01588. https://arxiv.org/abs/1912.01588

[S17] Arthur Juliani, Ahmed Khalifa, Vincent-Pierre Berges, Jonathan Harper, Ervin Teng, Hunter Henry, Adam Crespi, Julian Togelius, Danny Lange. "Obstacle Tower: A Generalization Challenge in Vision, Control, and Planning." IJCAI 2019. arXiv:1902.01378. DOI: 10.48550/arXiv.1902.01378. https://arxiv.org/abs/1902.01378

[S18] Matt Deitke, Winson Han, Alvaro Herrasti, Aniruddha Kembhavi, Eric Kolve, Roozbeh Mottaghi, Jordi Salvador, Dustin Schwenk, Eli VanderBilt, Matthew Wallingford, Luca Weihs, Mark Yatskar, Ali Farhadi. "RoboTHOR: An Open Simulation-to-Real Embodied AI Platform." CVPR 2020. arXiv:2004.06799. DOI: 10.48550/arXiv.2004.06799. https://arxiv.org/abs/2004.06799

[S19] Andrew Szot et al. "Habitat 2.0: Training Home Assistants to Rearrange their Habitat." arXiv:2106.14405. DOI: 10.48550/arXiv.2106.14405. https://arxiv.org/abs/2106.14405

[S20] Mohit Shridhar, Jesse Thomason, Daniel Gordon, Yonatan Bisk, Winson Han, Roozbeh Mottaghi, Luke Zettlemoyer, Dieter Fox. "ALFRED: A Benchmark for Interpreting Grounded Instructions for Everyday Tasks." arXiv:1912.01734. https://arxiv.org/abs/1912.01734

## Verification Notes

- Direct WebFetch checks succeeded for the arXiv/JMLR pages behind [S1]-[S6], [S9]-[S20], except where the queried arXiv ID was found to refer to an unrelated paper and was excluded.
- DOI redirects for [S7] and [S8] were checked; full publisher pages were not fully readable through WebFetch due access/HTTP restrictions. These are retained because they are canonical foundational exploration papers with stable DOIs.
- Several initially searched arXiv IDs were rejected because they resolved to unrelated physics, mathematics, genomics, or information-retrieval papers rather than navigation/evaluation sources.
- Claims about Argus-specific design are recommendations inferred from the cited evidence; they are not empirical results from Argus experiments.
