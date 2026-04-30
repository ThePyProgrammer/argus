# Swarm-Control and Simulation-Training Methods for Multiple Humanoid Robots

**Task ID:** T4  
**Role:** researcher-methods  
**Accessed date for all cited web sources:** 2026-04-30  
**Scope note:** This report focuses on general methods for controlling and training a swarm or fleet of humanoid robots in simulation. It intentionally avoids platform-specific AGIBOT X2 specifications or assets except as contextual motivation. The relevant hard problem is not “make one humanoid walk”; it is “make several high-DOF, contact-rich, dynamically unstable bodies coordinate safely under partial observability, delays, imperfect communications, and imperfect simulators.”

## Executive methodological position

For multiple humanoid robots, use a **layered architecture** rather than a monolithic swarm policy:

1. **Single-robot locomotion/whole-body controller:** train or adapt robust humanoid locomotion in simulation with heavy dynamics randomization, actuator/latency modeling, contact randomization, and privileged-state critics where allowed. Humanoid sim-to-real papers show zero-shot or near-zero-shot transfer is possible, but only with aggressive robustness engineering and history-based policies [13][14][16].
2. **Multi-agent coordination layer:** use centralized training / decentralized execution (CTDE) for formation, task allocation, spacing, communication policy, and cooperative objectives [1][2][3][4][5][6]. Do not let this layer command raw joints directly at first; it should output goals, velocity limits, formation slots, or task assignments to lower-level controllers.
3. **Safety shield and traffic rules:** use deterministic collision-avoidance and reachability-style checks around learned policies. ORCA-style reciprocal avoidance and learned no-communication collision avoidance are useful, but neither is a complete safety case for humanoids with nontrivial footprints, falling dynamics, or contacts [9][10].
4. **Deployment envelope:** start with small teams, static scenes, low speeds, and conservative separation distances. Expand through curriculum and adversarial scenario generation only after the lower-level controller survives perturbations, terrain changes, and sensor/latency corruption.

## 1. Numbered source list

1. **Lowe et al. (2017), “Multi-Agent Actor-Critic for Mixed Cooperative-Competitive Environments.”** URL: https://arxiv.org/abs/1706.02275. Centralized critic with decentralized actors; canonical CTDE-style multi-agent actor-critic.
2. **Sunehag et al. (2017), “Value-Decomposition Networks For Cooperative Multi-Agent Learning.”** URL: https://arxiv.org/abs/1706.05296. Factorizes team value into per-agent utilities for cooperative MARL.
3. **Rashid et al. (2018), “QMIX: Monotonic Value Function Factorisation for Deep Multi-Agent Reinforcement Learning.”** URL: https://arxiv.org/abs/1803.11485. Monotonic mixing network for CTDE-compatible decentralized greedy execution.
4. **Yu et al. (2021/2022), “The Surprising Effectiveness of PPO in Cooperative, Multi-Agent Games.”** URL: https://arxiv.org/abs/2103.01955. MAPPO-style PPO baseline evidence for cooperative MARL.
5. **OroojlooyJadid and Hajinezhad (2019), “A Review of Cooperative Multi-Agent Deep Reinforcement Learning.”** URL: https://arxiv.org/abs/1908.03963. Survey of independent learners, centralized critics, value factorization, consensus, and communication learning.
6. **Foerster et al. (2016), “Learning to Communicate with Deep Multi-Agent Reinforcement Learning.”** URL: https://arxiv.org/abs/1605.06676. RIAL/DIAL communication learning; explicitly targets centralized learning with decentralized execution.
7. **Sukhbaatar, Szlam, and Fergus (2016), “Learning Multiagent Communication with Backpropagation.”** URL: https://arxiv.org/abs/1605.07736. CommNet and learned continuous communication among cooperative agents.
8. **Gerkey and Matarić (2004), “A Formal Analysis and Taxonomy of Task Allocation in Multi-Robot Systems.”** URL: https://www.cs.cmu.edu/~gerkey/research/final_papers/mrta-taxonomy.pdf. Formal MRTA taxonomy for assigning tasks across robot teams.
9. **van den Berg et al. (2011), “Optimal Reciprocal Collision Avoidance.”** URL: https://gamma-web.iacs.umd.edu/ORCA/. Reciprocal velocity-obstacle collision avoidance without communication.
10. **Chen et al. (2016), “Decentralized Non-communicating Multiagent Collision Avoidance with Deep Reinforcement Learning.”** URL: https://arxiv.org/abs/1611.04201. Learned decentralized collision avoidance from local state and nearby agents.
11. **Tobin et al. (2017), “Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World.”** URL: https://arxiv.org/abs/1703.06907. Domain randomization as a sim-to-real transfer strategy.
12. **Tan et al. (2018), “Sim-to-Real: Learning Agile Locomotion For Quadruped Robots.”** URL: https://arxiv.org/abs/1804.10332. System identification, actuator modeling, latency modeling, environment randomization, and compact observations for legged sim-to-real.
13. **Lee et al. (2020), “Learning Quadrupedal Locomotion over Challenging Terrain.”** URL: https://arxiv.org/abs/2010.11251. Robust proprioceptive RL locomotion with zero-shot transfer across difficult outdoor terrain.
14. **Rudin et al. (2021), “Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning.”** URL: https://arxiv.org/abs/2109.11978. Massively parallel legged RL with curriculum and hardware transfer.
15. **Makoviychuk et al. (2021), “Isaac Gym: High Performance GPU-Based Physics Simulation For Robot Learning.”** URL: https://arxiv.org/abs/2108.10470. GPU-resident physics and policy training for large-scale RL.
16. **Radosavovic et al. (2023), “Real-World Humanoid Locomotion with Reinforcement Learning.”** URL: https://arxiv.org/abs/2303.03381. Causal transformer humanoid locomotion trained in randomized simulation and deployed zero-shot.
17. **Li et al. (2024), “Reinforcement Learning for Versatile, Dynamic, and Robust Bipedal Locomotion Control.”** URL: https://arxiv.org/abs/2401.16889. Dual-history architecture and task randomization for human-sized bipedal locomotion.
18. **Radosavovic et al. (2024), “Humanoid Locomotion as Next Token Prediction.”** URL: https://arxiv.org/abs/2402.19469. Autoregressive sensorimotor sequence modeling for humanoid locomotion, including simulated and real data sources.
19. **Hansen et al. (2024), “Hierarchical World Models as Visual Whole-Body Humanoid Controllers.”** URL: https://arxiv.org/abs/2405.18418. Hierarchical world-model controller for a 56-DoF humanoid in simulation.
20. **MuJoCo project page.** URL: https://mujoco.org/. Contact-rich physics simulator for robotics, biomechanics, optimal control, system identification, and mechanism design.
21. **legged_gym project page.** URL: https://leggedrobotics.github.io/legged_gym/. Massively parallel legged robot policy training with curriculum on GPU simulation.

## 2. Method matrix

| Method family | Applicability to humanoid swarm | Requirements | Risks / caveats | Recommendation |
|---|---|---|---|---|
| Independent RL per robot | Baseline for simple local behaviors; useful for ablations | Per-robot observations, local rewards, shared policy optional | Non-stationarity, poor credit assignment, emergent crowding, hard-to-debug failures [5] | Use only as a baseline, not the primary swarm-control strategy. |
| CTDE actor-critic, e.g. MADDPG/MAPPO | Strong fit for training decentralized policies with centralized state during simulation [1][4] | Centralized simulator state, synchronized rollouts, stable reward design, careful normalization | Overfits to simulator observability; brittle if execution observations differ from training | Use for formation keeping, local coordination, communication gating, and role policies. |
| Value decomposition, VDN/QMIX | Fit for cooperative team objectives with decentralized greedy action selection [2][3] | Shared reward, team-level state during training, monotonicity assumptions for QMIX | Monotonic factorization may misrepresent tasks where one robot must sacrifice locally for global benefit [3] | Use when objectives are additive-ish: coverage, transport subtasks, patrol, area search. Avoid for tightly coupled whole-body manipulation unless validated. |
| Learned communication, DIAL/CommNet-style | Useful when robots need latent intent sharing, formation negotiation, or congestion avoidance [6][7] | Differentiable communication during training, explicit bandwidth/dropout/noise model | Sim-learned messages may exploit unrealistic channels; communication collapse under packet loss | Train with bandwidth limits, dropout, latency, message corruption, and no-comm fallback. |
| Classical MRTA / auction / market allocation | Good for task assignment above motion-control layer [8] | Task models, costs, capabilities, deadlines, replanning triggers | Poor if task costs ignore locomotion risk, congestion, battery, or human proximity | Use as supervisory allocator; feed assignments to learned or model-predictive local controllers. |
| Formation control | Useful for processions, coverage, queueing, escort, and synchronized movement | Relative localization, formation graph, collision constraints, leader/follower or consensus design | Humanoid dynamics make tight formations dangerous; falls create dynamic obstacles | Keep formation commands as soft constraints with safety override and large separation margins. |
| ORCA / reciprocal velocity obstacles | Fast local collision avoidance without communication [9] | Approximate robot footprints, velocities, preferred velocities, reciprocal compliance | Assumes agents follow reciprocal rules; does not reason about humanoid falls, footstep timing, kinodynamic limits | Use as a safety-filter candidate for low-speed planar navigation, not as a whole safety proof. |
| Learned no-communication collision avoidance | Useful for local crowd negotiation under partial observation [10] | Local neighbor states, robust perception, diverse crowd scenarios | Hard to guarantee; may exploit simulator artifacts; poor OOD behavior | Combine with deterministic shields and evaluate against adversarial crossing, bottleneck, and occlusion scenarios. |
| Hierarchical control | Very strong fit: swarm policy outputs goals/slots; locomotion policy handles body control | Stable low-level controller, command interface, safety monitor | Interface mismatch: high-level policy may command infeasible accelerations/turns | Recommended default architecture. Decouple whole-body stability from multi-agent coordination. |
| Massive parallel RL simulation | Essential for sample-hungry legged control and multi-agent curriculum [14][15][21] | GPU simulation, vectorized environments, reset logic, reproducible seeds | Simulator throughput can hide bad physics; scale produces false confidence | Use for exploration and robustness sweeps, but verify with higher-fidelity and hardware-in-loop tests. |
| Domain randomization | Essential for sim-to-real perception/dynamics robustness [11][12][16] | Distributions over mass, friction, latency, sensor noise, terrain, contacts, visuals | Too broad slows learning; too narrow overfits; wrong distributions create fake robustness | Start from identified parameter ranges, expand by failure-driven randomization. |
| System identification and actuator modeling | Critical for humanoids/legged robots [12][20] | Torque/position-control model, latency, saturation, gear friction, compliance, battery effects | Wrong actuator model is a silent transfer killer | Treat as a first-class workstream, not a footnote. Maintain measured actuator latency and saturation tests. |
| Curriculum learning | Useful for both locomotion and swarm complexity [14][21] | Progress metrics, automatic difficulty adjustment, failure taxonomy | Curriculum can overfit to staged tasks and fail when stages combine | Use staged progression: solo stability → pairs → small groups → occlusion/bottlenecks → communication loss. |
| Sequence/history policies | Useful for partial observability, latency, unobserved terrain/contact state [16][17][18] | Recurrent/transformer policy or stacked history, diverse temporal corruptions | More data-hungry; can memorize simulator timing artifacts | Use for humanoid low-level policies and possibly swarm intent prediction, with randomized delays. |
| World-model or hierarchical visual controllers | Promising for complex whole-body tasks [19] | Large-scale simulation, visual observations, model learning, reward design | Simulation-only evidence may not transfer; world models can hallucinate dynamics | Research track only until validated with conservative hardware tests. |

## 3. Simulation-training checklist

### 3.1 Environment and simulator setup

- [ ] Choose at least two simulator fidelity levels: a fast GPU RL simulator for large rollouts [15][21] and a higher-fidelity/contact-debug simulator such as MuJoCo or equivalent for spot checks [20].
- [ ] Define robot abstraction layers: joint-level/whole-body controller, velocity/pose command interface, swarm coordination layer, safety shield.
- [ ] Model contact surfaces: friction, restitution, compliance, slopes, steps, seams, deformability approximations, wet/slippery surfaces.
- [ ] Model humanoid footprint and fall envelope, not just a circular disk. A standing humanoid, walking humanoid, and falling humanoid occupy different safety volumes.
- [ ] Include environment layouts that produce real coordination stress: corridors, bottlenecks, crossings, doorway queues, dynamic obstacles, uneven terrain, occlusions.

### 3.2 Actuator, sensing, and latency modeling

- [ ] Identify actuator control mode and simulate saturation, torque/current limits, backlash, gearbox friction, thermal derating, compliance, and command clipping [12].
- [ ] Randomize actuation latency, observation latency, dropped control frames, clock skew, and asynchronous policy updates [12][16][17].
- [ ] Randomize IMU bias/noise, joint encoder noise, foot/contact sensor false positives, depth/LiDAR/RGB dropout, and inter-robot pose-estimation error.
- [ ] Validate that trained policies still work when proprioception is delayed, stale, or partially corrupted; humanoid policies often rely heavily on temporal history [16][17][18].

### 3.3 Policy architecture

- [ ] Train low-level humanoid locomotion separately before swarm coordination. Do not begin with end-to-end multi-humanoid raw-joint MARL unless the purpose is a research ablation.
- [ ] Use a command-conditioned locomotion policy: desired velocity, heading, stop/stand, sidestep, yield, and emergency crouch/brace if supported.
- [ ] Use CTDE for swarm policy training: centralized critic or value decomposition sees full simulator state; deployed actors see only local robot observations and permitted messages [1][2][3][4].
- [ ] Include explicit no-communication and degraded-communication modes [6][7].
- [ ] Put a safety filter between high-level commands and locomotion policy: velocity bounds, acceleration bounds, minimum separation, keep-out zones, and emergency stop.

### 3.4 Reward and task design

- [ ] Separate rewards by layer: locomotion stability, command tracking, energy/contact smoothness, formation/task progress, collision penalties, communication cost, and human/asset safety.
- [ ] Penalize near misses, not only collisions. Humanoids need extra buffer because slips and falls are not instantaneous point-mass events.
- [ ] Penalize excessive communication and require policies to solve simplified tasks under zero communication [6][7].
- [ ] Use team rewards for global objectives but preserve per-agent diagnostic metrics to detect lazy-agent behavior and credit-assignment failures [2][5].
- [ ] Include “do nothing safely” and “yield” as valuable behaviors. Swarm policies that always chase progress create pileups.

### 3.5 Curriculum

Recommended curriculum:

1. **Solo stability:** flat ground, command tracking, stops, turns, perturbations.
2. **Solo robustness:** slopes, friction variation, latency/noise, push recovery, terrain transitions.
3. **Pairwise interaction:** crossing paths, leader/follower, reciprocal yielding, stop-and-go.
4. **Small group:** 3–5 robots, formation slots, task allocation, bottlenecks.
5. **Communication stress:** packet loss, delay, bandwidth limits, wrong/missing messages.
6. **Dense swarm:** congestion, occlusion, dynamic obstacles, failures/falls.
7. **Adversarial evaluation:** worst-case spawn positions, moving obstacles, sensor dropouts, actuator degradation.
8. **Hardware-in-loop / shadow deployment:** real timing, real perception, policy outputs monitored but initially not executed.

This progression follows the same principle that made massively parallel legged training useful: use cheap simulation for breadth, but promote difficulty only when measured competencies are stable [14][21].

### 3.6 Domain randomization and system identification

- [ ] Start from system identification, then randomize around identified parameters; do not randomly spray distributions and hope reality is inside them [12].
- [ ] Randomize mass/inertia by body segment, joint friction/damping, actuator strength, latency, ground friction, restitution, terrain heightfields, sensor noise, and robot-to-robot calibration offsets.
- [ ] Randomize communication bandwidth, latency, packet drops, message ordering, and neighbor-list errors [6][7].
- [ ] Use visual randomization if perception policies consume RGB/depth; domain randomization has precedent for visual sim-to-real [11].
- [ ] Track randomization coverage per evaluation run. If a policy passes “randomized eval” but only saw easy friction/latency samples, the result is bookkeeping theater.

### 3.7 Evaluation protocol

- [ ] Report per-agent and team metrics: success, time, energy, falls, collisions, near misses, deadlocks, communication usage, minimum separation, recovery time, and policy interventions.
- [ ] Evaluate across seeds. MARL results are seed-sensitive; single-seed victories are suspicious.
- [ ] Hold out environment layouts and swarm sizes; test extrapolation from N robots to N+M robots.
- [ ] Evaluate with disabled communication, delayed communication, and adversarially corrupted messages.
- [ ] Stress-test failed robot behavior: one robot stops, falls, drifts, sends stale messages, or ignores reciprocal avoidance.
- [ ] Run ablations: no CTDE, no communication, no safety shield, no domain randomization, no curriculum, no actuator randomization.
- [ ] Do not accept simulator-only “success” for deployment. Gate promotion through progressively realistic timing and hardware tests.

## 4. Swarm deployment risk register

| ID | Risk | Likelihood | Impact | Why it matters | Mitigation | Evidence / source anchors |
|---|---:|---:|---|---|---|---|
| R1 | Sim-to-real gap in humanoid contact dynamics | High | High | Humanoid balance depends on contacts, friction, latency, and actuator response. | System ID, actuator/latency modeling, contact randomization, staged hardware tests. | Legged sim-to-real methods emphasize actuator and latency modeling [12]; humanoid sim-to-real needs randomized environments/history policies [16][17]. |
| R2 | Learned swarm policy commands infeasible motion | Medium | High | High-level MARL may output turns/accelerations the humanoid cannot execute safely. | Hierarchical command interface, acceleration clamps, safety shield, feasibility critic. | CTDE helps coordination but does not enforce kinodynamics by itself [1][4]. |
| R3 | Collision avoidance treats humanoids as point/circle agents | High | High | Humanoids have limbs, changing support polygons, and fall envelopes. | Use enlarged dynamic safety volumes, footstep-aware buffers, deterministic override. | ORCA is velocity-obstacle based and useful but abstract [9]. |
| R4 | Communication policy overfits to perfect simulator networking | High | Medium | Real wireless links have delay, loss, contention, and stale state. | Train with packet loss, latency, bandwidth constraints, no-comm fallback. | Learned communication is powerful but channel assumptions matter [6][7]. |
| R5 | Lazy-agent or role-collapse behavior | Medium | Medium | Some robots may stop contributing while team reward remains acceptable. | Per-agent diagnostics, role randomization, value decomposition ablations. | VDN work explicitly discusses lazy-agent issues [2]. |
| R6 | Dense crowd deadlock | Medium | High | Robots block each other in bottlenecks or doorways. | Curriculum with bottlenecks, yielding reward, MRTA congestion costs, ORCA-like fallback. | MRTA should account for task/cost structure [8]; collision avoidance alone is insufficient [9][10]. |
| R7 | Fall cascade | Medium | High | One falling robot becomes a dynamic obstacle and can trigger others to collide/fall. | Large spacing, fallen-robot detection, stop/yield policy, recovery zoning. | General gap: most MARL/collision papers do not model humanoid falls [1][9][10]. |
| R8 | Reward hacking in simulation | High | Medium | Policies exploit simulator artifacts, contact bugs, or unrealistic communication. | Multiple simulators/fidelity levels, randomization, contact audits, video review. | Massive simulation is efficient but not proof of physical validity [15][21]. |
| R9 | Scaling failure from small teams to larger swarms | Medium | Medium | Pairwise policies may fail under congestion and many-neighbor partial observability. | Train/evaluate at variable team sizes, use permutation-invariant encoders, graph/message limits. | Cooperative MARL surveys highlight coordination and non-stationarity challenges [5]. |
| R10 | Human safety and mixed traffic | Medium | High | Humanoids near humans need conservative margins and interpretable yielding. | Keep-out zones, speed limits, certified E-stop, human-aware evaluation scenarios. | Learned collision avoidance is not a safety certification [10]. |
| R11 | Perception OOD under lighting/occlusion | Medium | High | Swarm coordination often depends on detecting neighbors and obstacles. | Sensor redundancy, visual randomization, occlusion curriculum, fallback to proprioceptive/local rules. | Domain randomization helps but depends on coverage [11]. |
| R12 | Evaluation optimism from cherry-picked seeds/scenarios | High | Medium | MARL and locomotion results can vary dramatically. | Multi-seed confidence intervals, held-out maps, adversarial tests, failure report. | MAPPO-style results are implementation/hyperparameter sensitive [4]. |

## 5. Contradictions and gaps

1. **CTDE promises decentralized execution, but training often uses privileged information.** Centralized critics/value functions can stabilize learning [1][2][3][4], yet the deployed robot only has local observations and lossy messages. If training-state leakage is not controlled, policies appear robust in simulation and fail on hardware.

2. **Value factorization is elegant but may be too restrictive for humanoid teams.** VDN and QMIX are attractive for cooperative tasks [2][3], but humanoid swarm tasks can require non-monotonic tradeoffs: one robot waits, detours, or blocks temporarily so another can pass. QMIX’s monotonicity is useful engineering discipline, not universal truth.

3. **Learned communication improves coordination but creates a new sim-to-real gap.** DIAL and CommNet show that communication protocols can be learned [6][7]. The catch is obvious and often under-modeled: real communication has bandwidth, delay, dropouts, interference, and stale world models. Learned protocols must be trained under those constraints.

4. **Collision-avoidance literature often abstracts away the thing that makes humanoids dangerous: falling.** ORCA and learned decentralized collision avoidance are relevant [9][10], but humanoid robots are not holonomic discs. Footstep timing, arm swing, balance recovery, slips, and falls need explicit modeling or conservative safety buffers.

5. **Legged sim-to-real evidence is strong but not automatically swarm evidence.** Quadruped and humanoid locomotion papers show robust transfer with system identification, randomization, history policies, and curricula [12][13][14][16][17]. They do not prove that multiple humanoids can safely coordinate in dense, communication-constrained scenes.

6. **Massively parallel simulation can make bad assumptions look statistically convincing.** Isaac Gym/legged_gym-style throughput is valuable [15][21], but high rollout counts do not repair wrong contact physics, missing actuator saturation, or unrealistic network assumptions.

7. **Whole-body humanoid learning is moving fast, but many results are still single-agent or simulation-heavy.** Recent humanoid methods based on causal transformers, next-token prediction, dual-history policies, and hierarchical world models are promising [16][17][18][19]. The gap is validated multi-humanoid, real-world, contact-rich coordination.

8. **Task allocation and motion planning are often treated separately, but humanoid costs couple them.** MRTA abstractions are useful [8], but task cost must include locomotion risk, congestion, terrain, battery/thermal state, fall risk, and communication quality.

## 6. Methodological recommendations

### 6.1 Preferred architecture

Use this stack:

```text
Mission/task layer
  -> MRTA / planner / auction / scheduler
      -> CTDE-trained swarm coordination policy
          -> safety shield / collision and feasibility filter
              -> command-conditioned humanoid locomotion policy
                  -> whole-body controller / actuator interface
```

Rationale:

- CTDE and value decomposition are appropriate for learning coordination under centralized simulation supervision [1][2][3][4].
- MRTA gives interpretable task ownership and replanning hooks [8].
- A deterministic shield compensates for the lack of formal guarantees in learned collision avoidance [9][10].
- Humanoid locomotion policies need specialized sim-to-real treatment and should not be entangled prematurely with swarm reward learning [12][16][17].

### 6.2 Training strategy

- Train **single-humanoid locomotion** first using randomized dynamics, latency, terrain, and perturbations [12][16][17].
- Freeze or slowly fine-tune the locomotion policy while training the **swarm coordination layer**. Let the swarm policy command velocity/pose/slot goals, not torques.
- Use **MAPPO/MADDPG-style centralized critics** for continuous coordination and **VDN/QMIX-style baselines** for cooperative discrete/subtask decisions [1][2][3][4].
- Train communication policies with strict bandwidth, packet loss, latency, and no-communication ablations [6][7].
- Use curriculum from 1 robot to 2, 3–5, then denser groups. Include bottlenecks and failed robots early enough that the policy cannot learn a fantasy world.

### 6.3 Evaluation strategy

Minimum credible evaluation table:

| Category | Required tests |
|---|---|
| Locomotion transfer | Flat, slopes, low/high friction, payload variation, perturbations, latency injection |
| Pair interaction | Head-on passing, crossing, leader stop, one robot yields, one robot fails |
| Small swarm | Formation change, bottleneck, task allocation under congestion, communication loss |
| Dense swarm | Variable N, occlusion, dynamic obstacles, near-miss statistics |
| Robustness | Held-out maps, held-out randomization ranges, multi-seed, adversarial starts |
| Safety | E-stop latency, shield interventions, minimum separation, fall isolation |
| Sim-to-real gates | Shadow mode, hardware-in-loop timing, single robot, pair, then group |

### 6.4 What not to do

- Do not train an end-to-end raw-joint MARL policy for all humanoids as the main path. It is possible as a paper, not as a sane deployment plan.
- Do not assume ORCA or learned local avoidance is enough. Humanoid falls, limb motion, and kinodynamic limits violate the clean assumptions [9][10].
- Do not report only team success. Report per-agent failures, lazy-agent behavior, near misses, and shield interventions [2][5].
- Do not use perfect communication in training unless deployment has perfect communication, which it will not.
- Do not trust one simulator. Use fast simulation for training and slower/higher-fidelity simulation for contact and failure audits [15][20][21].

## 7. Bottom-line caveats for AGIBOT X2-style humanoid swarms

- The platform being humanoid changes the safety margin. A wheeled swarm can often be modeled as discs; humanoids need body-volume, limb, support, and fall modeling.
- The first deployable “swarm” behavior should likely be conservative: spacing, queueing, formation slots, and task allocation. Dense agile crowd motion should be treated as later-stage research.
- The simulation program should be judged by failure discovery, not just training reward. A simulator that never produces falls, foot slips, packet loss, or deadlocks is not a simulator; it is a wish generator.
- The recommended research path is layered, CTDE-trained, safety-shielded, communication-stressed, and evaluated with hostile scenarios before any multi-humanoid hardware trial.
