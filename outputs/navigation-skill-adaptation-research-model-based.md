# Model-Based Skill Planning and Outcome Models for Navigation Skill Adaptation

## Executive Summary

Model-based skill planning is a strong literature fit for Argus's proposed gated online exploration skill selector. The most relevant thread treats high-level skills/options as temporally extended actions with learned outcome, transition, effect, or feasibility models, then plans/searches over skill sequences rather than primitive controls [S1][S2][S3][S4]. For Argus, this supports a staged design: begin with a gated heuristic selector over hand-authored exploration skills, log every skill attempt and completed outcome, then learn lightweight skill-effect models that can eventually support model-predictive skill sequencing.

SkiMo is directly relevant: it learns a skill repertoire and a skill dynamics model, then plans in skill space to extend planning horizons and improve sample efficiency in navigation and manipulation domains [S1]. arXiv:2207.07560 should be positioned as a core precedent rather than a contrast paper [S1]. The user-referenced arXiv:2411.02998, FraCOs, is relevant as a hierarchical option-discovery and transfer paper, but it is less directly relevant than SkiMo because it is not primarily a model-based skill planner and appears focused on hierarchical RL transfer/generalization rather than robot navigation or skill outcome models [S16].

A second important thread comes from robot planning and TAMP: learned symbolic operators, neuro-symbolic skills, learned skill-effect models, and compositional skill models show how completed executions can be converted into precondition/effect, success-condition, feasibility, and sampler models for higher-level planning [S5][S6][S7][S8]. These works are closer to Argus's near-term engineering path than end-to-end RL because Argus can record outcomes of exploration skills in simulation and learn models over semantic/map features before attempting full option learning.

A third thread comes from affordance and future-affordance models. Deep Affordance Foresight and VAL show that planning can use models of what actions/skills will become possible in the future, not just immediate success probabilities [S9][S10]. For exploration, this maps naturally to forecasting whether a skill will create new frontiers, improve connectivity, reduce localization risk, increase loop-closure opportunities, or unlock new skill affordances.

The concrete recommendation is to design Argus's selector around explicit skill contracts and outcome telemetry now: each skill should declare its applicability gates, tunable parameters, predicted outcome schema, failure modes, and post-execution outcome labels. This keeps the first implementation simple while preserving a clean path to learned skill dynamics, MPC over skills, and eventually options/RL.

## Evidence Table

| Theme | Source(s) | Evidence | Relevance to Argus | Confidence |
|---|---|---|---|---|
| Skill dynamics / SkiMo-like planning | [S1] | SkiMo learns a skill repertoire and a skill dynamics/outcome model, then plans in skill space; evaluated on navigation and manipulation tasks. | Directly supports learning outcome models for exploration skills and using them for longer-horizon skill sequencing. | High |
| Skill priors from offline data | [S2][S3] | SPiRL learns latent skill embeddings and priors from offline data; SkiLD reuses learned skills from demonstrations. | Supports learning a prior over exploration strategies from simulation logs before online adaptation. | Medium-high |
| Skill-space MPC / sequencing | [S4][S11][S12][S13] | Simulator Predictive Control searches over skill/task latents with MPC; locomotion work learns primitive-cycle dynamics and plans with MPC; MoPAC and switching pushing combine MPC with RL. | Argus can first run short-horizon receding-horizon search over hand-authored skill candidates before learning full policies. | Medium |
| Option/temporal-abstraction models | [S14][S15][S17][S18] | Temporally abstract partial models introduce option availability/affordances; reward-respecting subtasks align option models with planning; linear option models and temporally extended actions reduce planning burden. | Argus should model when exploration skills are available and what planning-relevant outcome they produce, not just score skills globally. | Medium-high |
| Learned symbolic/effect models | [S5][S6][S7][S8] | Operator-learning and neuro-symbolic skill work learns planning abstractions, symbolic operators, policies, samplers, constraints, and effects from experience/demonstrations. | Argus can learn compact transition/effect models over map/topological state, robot distribution, frontier statistics, and resource state. | High |
| Search-based skill-effect planning | [S7] | Search-based task planning uses learned high-level skill-effect models trained in simulation and iterative data generation; designed for lifelong robotic manipulation. | Strong template for simulation-first lifelong improvement of exploration skill models. | High |
| Affordance/outcome foresight | [S9][S10] | DAF models future action affordances; VAL uses generative visual outcome models to propose exploration targets and adapt skills. | Argus should predict future exploration affordances such as newly reachable frontiers or loop-closure candidates, not only immediate map gain. | Medium-high |
| Hierarchical navigation/subgoal planning | [S19] | Goal-conditioned offline RL with high-level subgoal planning is evaluated on long-horizon driving and robot navigation. | Useful contrast/bridge from skill selection to subgoal selection and full RL. | Medium |
| arXiv:2411.02998 | [S16] | FraCOs builds multi-level skill hierarchies for task generalization; relevant to transfer but not primarily a model-based robot planning method. | Include as contrast/future RL path, not as the main basis for current design. | Medium |

## Key Findings

1. **Skill-outcome models are the right abstraction layer for Argus.** SkiMo demonstrates the central pattern: learn reusable skills and a skill dynamics model, then plan over skills instead of primitive actions [S1]. For exploration, the analogous model should predict outcomes such as map gain, frontier creation/removal, localization confidence change, communication/connectivity impact, coverage overlap, time/energy cost, and failure probability.

2. **Planning needs feasibility/availability gates, not just utility scores.** Temporally Abstract Partial Models explicitly model option availability/affordances and the fact that options may only be valid in subsets of state space [S14]. This maps directly to exploration skills: frontier pursuit, loop closure, rendezvous, dispersion, coverage sweep, relocalization, and comms relay skills each have different state-dependent preconditions.

3. **A gated selector is literature-aligned if it logs outcomes for later model learning.** The TAMP/operator-learning literature shows that planners can benefit from learned symbolic operators, skill constraints, samplers, and effects [S5][S6][S8]. Argus can begin with hand-authored gates and later learn their boundaries from simulation outcomes.

4. **Completed task outcomes are useful training data for transition/effect models.** Search-based planning with learned skill-effect models trains high-level effect models in simulation and uses iterative data generation to focus learning on useful planning data [S7]. Argus should store every skill invocation as a transition tuple: pre-state abstraction, skill id, skill parameters, execution context, post-state abstraction, success/failure label, cost, and side effects.

5. **Affordance foresight is more relevant to exploration than immediate-success affordances alone.** Deep Affordance Foresight argues for planning through what actions will be afforded in the future [S9]. Exploration strategies often matter because they unlock future opportunities: new frontiers, better viewpoints, improved topology, or safer routes.

6. **Offline skill priors are useful, but should not replace model-based outcome reasoning.** SPiRL and SkiLD show value in learning reusable skill priors from offline experience or demonstrations [S2][S3]. For Argus, an offline prior over exploration skills can accelerate selection, but the selector still needs online evidence and outcome models because exploration maps, robot failures, and team configurations vary.

7. **MPC over skills is feasible but should be introduced after telemetry stabilizes.** Simulator Predictive Control, hierarchical locomotion MPC, and SkiMo all support receding-horizon planning over latent skills or primitives [S4][S11][S1]. However, Argus should avoid premature complex MPC until the skill outcome schema and state abstraction are reliable.

8. **arXiv:2207.07560 is central.** It is SkiMo itself and is directly relevant to skill dynamics/outcome models and planning in skill space [S1]. It should not be used merely as contrast.

9. **arXiv:2411.02998 belongs only as a secondary/future-path source.** FraCOs concerns multi-level skill hierarchies and transfer/generalization, which is relevant to eventual option learning, but it is not the strongest evidence for the current model-based selector design [S16].

## Contradictions and Limitations

1. **Model-based skill planning promises longer horizons, but model error remains a central risk.** SkiMo and skill-MPC papers motivate planning over abstract skills [S1][S4][S11], while MoPAC explicitly notes that dynamics-model errors can harm model-based RL and motivates hybrid MPC/RL to reduce model bias [S12]. Argus should treat learned outcome predictions as uncertain estimates, not authoritative commands.

2. **Skill priors can improve exploration but may bias against novel strategies.** SPiRL uses learned priors to guide downstream RL toward useful skills [S2], but exploration workbenches may need to deliberately try underrepresented or uncertain skills. Argus should include uncertainty bonuses or scheduled probing, especially in simulation.

3. **Symbolic/effect models scale planning but may be lossy.** Operator-learning work frames learned operators as compact, imperfect abstractions of transition dynamics [S5]. Argus should keep the learned model intentionally coarse and planning-relevant, while retaining raw logs for later re-labeling and richer models.

4. **Most directly relevant robot-skill papers are manipulation-heavy.** Learned skill-effect models, TAMP operators, DAF, and VAL are largely manipulation-oriented [S5][S6][S7][S8][S9][S10]. Their abstractions transfer well to navigation/exploration, but the metrics and state representations must be redesigned for multi-robot mapping.

5. **Few sources directly address multi-robot exploration skill selection.** The literature strongly supports model-based skill sequencing and outcome models, but direct evidence for multi-robot exploration skill selectors is thinner. This argues for a conservative gated design with simulation-first evaluation rather than immediate claims of general RL optimality.

6. **Deep hierarchical RL papers often optimize benchmark transfer rather than operational interpretability.** FraCOs and related option-discovery work are relevant to future autonomous option learning [S16][S20], but Argus needs explainable gates, safety constraints, and debuggable outcomes before opaque hierarchy learning.

## Concrete Implications for the Argus Design Spec

### 1. Define every exploration skill as a contract

Each high-level skill should have:

- **Applicability gates:** required map state, robot state, team state, localization state, and communication state.
- **Parameter schema:** target frontier, target region, rendezvous point, radius, time budget, risk tolerance, robot subset, etc.
- **Predicted outcome schema:** expected coverage gain, frontier delta, entropy reduction, travel cost, localization risk, connectivity change, collision/risk exposure, and probability of failure.
- **Termination conditions:** success, timeout, no-progress, blocked path, localization degradation, comms failure, map-staleness trigger.
- **Post-execution labels:** whether the intended effect occurred, what side effects occurred, and whether the skill created new affordances.

This mirrors the learned operator/skill-effect framing in TAMP and lifelong skill planning [S5][S6][S7][S8].

### 2. Start with gated online selection, but log data for learned models

The first Argus implementation can use explicit rules and scoring. However, each completed skill should be logged in a form suitable for model learning:

```text
(pre_state_abstraction, skill_id, skill_parameters, robot_subset, context,
 post_state_abstraction, success_label, cost_vector, side_effects, timestamp)
```

This directly supports later learning of skill-effect models like search-based skill planning [S7], option availability like partial option models [S14], and SkiMo-like skill dynamics [S1].

### 3. Use a compact planning state abstraction

Do not try to predict raw maps initially. Learn/predict over planning-relevant features:

- frontier count, frontier sizes, and frontier spatial distribution;
- explored-area and expected-information-gain summaries;
- topological graph connectivity and chokepoints;
- robot dispersion and assignment balance;
- localization confidence and loop-closure opportunities;
- communication graph health;
- battery/time budget/resource state;
- recent skill failures and stuck/blocked indicators.

This follows the lesson that symbolic operators and partial models are useful because they are lossy but planning-relevant abstractions [S5][S14].

### 4. Add uncertainty-aware scoring before full RL

Outcome models should produce uncertainty or confidence, not just point estimates. Use uncertainty to:

- suppress unsafe choices when uncertainty is high;
- prefer data collection in simulation;
- schedule occasional probing of under-sampled skills;
- detect out-of-distribution contexts;
- decide when to fall back to hand-authored gates.

This mitigates model-bias risks noted by model-based RL/MPC work [S12].

### 5. Treat future affordances as first-class outcomes

Exploration skill outcomes should include whether the skill creates future options, such as:

- new reachable frontiers;
- better viewpoints into occluded space;
- loop-closure candidates;
- restored or improved communication connectivity;
- safer routes through newly mapped topology;
- better robot staging for parallel exploration.

This is the navigation/exploration analogue of Deep Affordance Foresight and VAL [S9][S10].

### 6. Introduce model-predictive skill sequencing in phases

Recommended staged path:

1. **Phase A: gated selector.** Hand-authored gates plus heuristic utility score.
2. **Phase B: calibrated outcome predictors.** Learn per-skill success/cost/effect models from simulation logs.
3. **Phase C: one-step lookahead.** Choose skills by predicted immediate outcome and risk.
4. **Phase D: short-horizon receding-horizon skill planning.** Search over 2-4 skill sequences using learned outcome models, similar in spirit to skill-space planning/MPC [S1][S4][S11].
5. **Phase E: offline skill priors/options.** Learn skill priors or options from high-performing simulation traces [S2][S3][S16].
6. **Phase F: full RL/options learning.** Only after metrics, logs, and safety constraints are stable.

### 7. Keep arXiv:2411.02998 in the future-path section

FraCOs should be cited for future multi-level hierarchy learning and transfer [S16]. It should not drive the near-term design of the model-based selector because SkiMo, learned skill-effect models, partial option models, and TAMP operator learning are more directly aligned with Argus's immediate needs [S1][S7][S14][S5].

## Numbered Source List

[S1] Lucy Xiaoyang Shi, Joseph J. Lim, Youngwoon Lee. **Skill-based Model-based Reinforcement Learning**. arXiv:2207.07560. URL: https://arxiv.org/abs/2207.07560. Project page: https://clvrai.github.io/skimo/

[S2] Karl Pertsch, Youngwoon Lee, Joseph J. Lim. **Accelerating Reinforcement Learning with Learned Skill Priors**. arXiv:2010.11944. URL: https://arxiv.org/abs/2010.11944

[S3] Karl Pertsch, Youngwoon Lee, Yue Wu, Joseph J. Lim. **Demonstration-Guided Reinforcement Learning with Learned Skills**. arXiv:2107.10253. URL: https://arxiv.org/abs/2107.10253

[S4] Zhanpeng He, Ryan Julian, Eric Heiden, Hejia Zhang, Stefan Schaal, Joseph J. Lim, Gaurav Sukhatme, Karol Hausman. **Simulator Predictive Control: Using Learned Task Representations and MPC for Zero-Shot Generalization and Sequencing**. arXiv:1810.02422. URL: https://arxiv.org/abs/1810.02422

[S5] Tom Silver, Rohan Chitnis, Joshua Tenenbaum, Leslie Pack Kaelbling, Tomas Lozano-Perez. **Learning Symbolic Operators for Task and Motion Planning**. arXiv:2103.00589. URL: https://arxiv.org/abs/2103.00589

[S6] Tom Silver, Ashay Athalye, Joshua B. Tenenbaum, Tomas Lozano-Perez, Leslie Pack Kaelbling. **Learning Neuro-Symbolic Skills for Bilevel Planning**. arXiv:2206.10680. URL: https://arxiv.org/abs/2206.10680

[S7] Jacky Liang, Mohit Sharma, Alex LaGrassa, Shivam Vats, Saumya Saxena, Oliver Kroemer. **Search-Based Task Planning with Learned Skill Effect Models for Lifelong Robotic Manipulation**. arXiv:2109.08771; ICRA 2022. URL: https://arxiv.org/abs/2109.08771

[S8] Zi Wang, Caelan Reed Garrett, Leslie Pack Kaelbling, Tomás Lozano-Pérez. **Learning compositional models of robot skills for task and motion planning**. arXiv:2006.06444. URL: https://arxiv.org/abs/2006.06444

[S9] Danfei Xu, Ajay Mandlekar, Roberto Martín-Martín, Yuke Zhu, Silvio Savarese, Li Fei-Fei. **Deep Affordance Foresight: Planning Through What Can Be Done in the Future**. arXiv:2011.08424. URL: https://arxiv.org/abs/2011.08424

[S10] Alexander Khazatsky, Ashvin Nair, Daniel Jing, Sergey Levine. **What Can I Do Here? Learning New Skills by Imagining Visual Affordances**. arXiv:2106.00671. URL: https://arxiv.org/abs/2106.00671

[S11] Tianyu Li, Nathan Lambert, Roberto Calandra, Franziska Meier, Akshara Rai. **Learning Generalizable Locomotion Skills with Hierarchical Reinforcement Learning**. arXiv:1909.12324. URL: https://arxiv.org/abs/1909.12324

[S12] Andrew S. Morgan, Daljeet Nandha, Georgia Chalvatzaki, Carlo D'Eramo, Aaron M. Dollar, Jan Peters. **Model Predictive Actor-Critic: Accelerating Robot Skill Acquisition with Deep Reinforcement Learning**. arXiv:2103.13842. URL: https://arxiv.org/abs/2103.13842

[S13] Bo Zhang, Cong Huang, Haixu Zhang, Xiaoshan Bai. **Switching Pushing Skill Combined MPC and Deep Reinforcement Learning for Planar Non-prehensile Manipulation**. arXiv:2303.17379. URL: https://arxiv.org/abs/2303.17379

[S14] Khimya Khetarpal, Zafarali Ahmed, Gheorghe Comanici, Doina Precup. **Temporally Abstract Partial Models**. arXiv:2108.03213. URL: https://arxiv.org/abs/2108.03213

[S15] Richard S. Sutton, Marlos C. Machado, G. Zacharias Holland, David Szepesvari, Finbarr Timbers, Brian Tanner, Adam White. **Reward-Respecting Subtasks for Model-Based Reinforcement Learning**. arXiv:2202.03466. URL: https://arxiv.org/abs/2202.03466

[S16] Thomas P. Cannon, Özgür Şimşek. **Accelerating Task Generalisation with Multi-Level Skill Hierarchies**. arXiv:2411.02998. URL: https://arxiv.org/abs/2411.02998

[S17] Peeyush Kumar, Doina Precup. **Multi-Timescale, Gradient Descent, Temporal Difference Learning with Linear Options**. arXiv:1703.06471. URL: https://arxiv.org/abs/1703.06471

[S18] Palash Chatterjee, Roni Khardon. **Improving planning and MBRL with temporally-extended actions**. arXiv:2505.15754. URL: https://arxiv.org/abs/2505.15754

[S19] Jinning Li, Chen Tang, Masayoshi Tomizuka, Wei Zhan. **Hierarchical Planning Through Goal-Conditioned Offline Reinforcement Learning**. arXiv:2205.11790. URL: https://arxiv.org/abs/2205.11790

[S20] Benjamin Eysenbach, Abhishek Gupta, Julian Ibarz, Sergey Levine. **Diversity is All You Need: Learning Skills without a Reward Function**. arXiv:1802.06070. URL: https://arxiv.org/abs/1802.06070

[S21] Annie Xie, Avi Singh, Sergey Levine, Chelsea Finn. **Few-Shot Goal Inference for Visuomotor Learning and Planning**. arXiv:1810.00482. URL: https://arxiv.org/abs/1810.00482

## Accepted Source Count

21 accepted sources.
