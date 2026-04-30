# T2 Research: Learning-Based Locomotion R&D Systems for Humanoids and Robot Dogs

**Task:** T2 from `outputs/.plans/locomotion-rd-systems.md`
**Topic:** Locomotion R&D systems for humanoid and robot dog control
**Scope boundary:** This file covers reinforcement learning, imitation learning, teacher-student / distillation, sim-to-real, domain randomization, residual / hybrid learning, real-world adaptation, and learned policies for legged locomotion. Classical WBC/MPC/trajectory optimization appears only as baseline context or as a scaffold around learned policies.

## 1. Numbered Sources

1. **Tan et al. (2018), “Sim-to-Real: Learning Agile Locomotion For Quadruped Robots.”** arXiv: https://arxiv.org/abs/1804.10332, DOI: https://doi.org/10.48550/arXiv.1804.10332. Quadruped RL with actuator/latency modeling, randomized training conditions, disturbances, and sim-to-real transfer.
2. **Xie et al. (2018), “Feedback Control For Cassie With Deep Reinforcement Learning.”** arXiv: https://arxiv.org/abs/1803.05580, DOI: https://doi.org/10.48550/arXiv.1803.05580. Cassie biped feedback walking policies learned by reference-motion mimicry, speed time-scaling, and policy interpolation.
3. **Hwangbo et al. (2019), “Learning agile and dynamic motor skills for legged robots.”** arXiv: https://arxiv.org/abs/1901.08652, DOI: https://doi.org/10.48550/arXiv.1901.08652. ANYmal neural policy trained in simulation and transferred to hardware for agile quadruped control.
4. **Lee et al. (2020), “Learning Quadrupedal Locomotion over Challenging Terrain.”** arXiv: https://arxiv.org/abs/2010.11251, Science Robotics DOI: https://doi.org/10.1126/scirobotics.abc5986. ANYmal proprioceptive RL with zero-shot transfer to mud, snow, rubble, vegetation, water, and natural settings.
5. **Siekmann et al. (2020/2021), “Sim-to-Real Learning of All Common Bipedal Gaits via Periodic Reward Composition.”** arXiv: https://arxiv.org/abs/2011.01387, DOI: https://doi.org/10.48550/arXiv.2011.01387. Cassie RL using periodic reward composition for standing, walking, hopping, running, skipping, and gait switching.
6. **Rudin et al. (2021/2022), “Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning.”** arXiv: https://arxiv.org/abs/2109.11978, DOI: https://doi.org/10.48550/arXiv.2109.11978. ANYmal policies trained on thousands of parallel simulated robots, with reported training times under 4 minutes for flat terrain and 20 minutes for uneven terrain.
7. **Kumar et al. (2021), “RMA: Rapid Motor Adaptation for Legged Robots.”** arXiv: https://arxiv.org/abs/2107.04034, DOI: https://doi.org/10.48550/arXiv.2107.04034. Unitree A1 base policy plus adaptation module trained in simulation and transferred without real fine-tuning across terrain/payload/wear changes.
8. **Miki et al. (2022), “Learning robust perceptive locomotion for quadrupedal robots in the wild.”** arXiv: https://arxiv.org/abs/2201.08117, DOI: https://doi.org/10.48550/arXiv.2201.08117. Quadruped perceptive locomotion with proprioceptive and exteroceptive fusion, tested in natural/urban settings including an hour-long Alpine hike.
9. **Margolis et al. (2022), “Rapid Locomotion via Reinforcement Learning.”** arXiv: https://arxiv.org/abs/2205.02824, DOI: https://doi.org/10.48550/arXiv.2205.02824. MIT Mini Cheetah RL policy with adaptive velocity-command curriculum and online system identification; reports up to 3.9 m/s on varied terrain.
10. **Margolis & Agrawal (2022), “Walk These Ways: Tuning Robot Control for Generalization with Multiplicity of Behavior.”** arXiv: https://arxiv.org/abs/2212.03238, DOI: https://doi.org/10.48550/arXiv.2212.03238. Learned controller exposes a structured family of behaviors for run-time tuning across new tasks/environments.
11. **Radosavovic et al. (2023), “Real-World Humanoid Locomotion with Reinforcement Learning.”** arXiv: https://arxiv.org/abs/2303.03381, DOI: https://doi.org/10.48550/arXiv.2303.03381. Humanoid causal-transformer policy using prior proprioceptive observations/actions, trained with large-scale randomized simulation and transferred zero-shot.
12. **Haarnoja et al. (2023/2024), “Learning Agile Soccer Skills for a Bipedal Robot with Deep Reinforcement Learning.”** arXiv: https://arxiv.org/abs/2304.13653, arXiv DOI: https://doi.org/10.48550/arXiv.2304.13653, Science Robotics DOI: https://doi.org/10.1126/scirobotics.adi8022. Miniature humanoid RL for falling recovery, walking, turning, kicking, and tactical play; reports large gains over scripted baseline.
13. **Gu et al. (2024), “Humanoid-Gym: Reinforcement Learning for Humanoid Robot with Zero-Shot Sim2Real Transfer.”** arXiv: https://arxiv.org/abs/2404.05695, DOI: https://doi.org/10.48550/arXiv.2404.05695. Isaac Gym-based humanoid RL framework for RobotEra XBot-S and XBot-L, with MuJoCo sim-to-sim validation and real-world verification.
14. **Fu et al. (2024), “HumanPlus: Humanoid Shadowing and Imitation from Humans.”** arXiv: https://arxiv.org/abs/2406.10454, DOI: https://doi.org/10.48550/arXiv.2406.10454. 33-DoF humanoid: RL low-level policy from human motion data, human shadowing, then supervised behavior cloning for autonomous skills.
15. **Radosavovic et al. (2024), “Learning Humanoid Locomotion over Challenging Terrain.”** arXiv: https://arxiv.org/abs/2410.03654, DOI: https://doi.org/10.48550/arXiv.2410.03654. Humanoid transformer locomotion policy trained from flat-ground sequence modeling then refined with RL on uneven terrain; reports Berkeley hiking trails and steep San Francisco streets.
16. **He et al. (2024/2025), “HOVER: Versatile Neural Whole-Body Controller for Humanoid Robots.”** arXiv: https://arxiv.org/abs/2410.21229, DOI: https://doi.org/10.48550/arXiv.2410.21229, project: https://hover-versatile-humanoid.github.io/. Multi-mode policy distillation for humanoid whole-body control across navigation, loco-manipulation, and manipulation modes.
17. **Shi et al. (2025), “Adversarial Locomotion and Motion Imitation for Humanoid Policy Learning.”** arXiv: https://arxiv.org/abs/2504.14305, DOI: https://doi.org/10.48550/arXiv.2504.14305. Unitree H1 humanoid policy learning combining locomotion and motion imitation via adversarial upper/lower-body control.
18. **Legged Robotics, `legged_gym` project page / GitHub.** https://github.com/leggedrobotics/legged_gym. Codebase associated with massively parallel Isaac Gym legged-locomotion RL, with examples including ANYmal C/B, A1, and Cassie.

## 2. Evidence Table

| # | System / paper | Robot class | Platform / robot | Learning family | Sim-to-real mechanism | Evidence reported | Relevance |
|---|---|---|---|---|---|---|---|
| 1 | Tan et al. 2018 | Quadruped | Research quadruped | Deep RL | Actuator/latency modeling, simulator calibration, randomization, disturbances | Trotting/galloping transferred to real robot | Early canonical quadruped sim-to-real RL recipe |
| 2 | Xie et al. 2018 | Biped / humanoid-like | Cassie | RL + imitation/reference tracking | Realistic simulator, delay handling, robust policy design | Uneven-ground blind walking and push robustness in paper claims | Early learned biped feedback controller |
| 3 | Hwangbo et al. 2019 | Quadruped | ANYmal | RL policy | Simulation training and hardware transfer | Better velocity tracking, faster running, fall recovery claims | ANYmal line became a major legged-RL reference |
| 4 | Lee et al. 2020 | Quadruped | ANYmal | Proprioceptive RL | Randomized simulation; zero-shot field deployment | Mud, snow, rubble, vegetation, water | Strong example that proprioception-only RL can generalize beyond lab floors |
| 5 | Siekmann et al. 2021 | Biped | Cassie | RL with periodic reward composition | Sim-to-real transfer | Standing, walking, hopping, running, skipping; gait switching | Shows learned gait families for underactuated biped |
| 6 | Rudin et al. 2021/2022 | Quadruped | ANYmal | Massively parallel RL | GPU-parallel simulation, terrain curriculum | Under-4-min flat / 20-min uneven training; real transfer | Defines modern high-throughput legged RL training style |
| 7 | RMA 2021 | Quadruped | Unitree A1 | RL + online adaptation | Base policy plus adaptation module, trained fully in sim | Rocky, slippery, deformable, grass, vegetation, stairs, sand | Canonical real-world adaptation architecture |
| 8 | Miki et al. 2022 | Quadruped | ANYmal-class quadruped | Perceptive RL | Exteroceptive/proprioceptive recurrent encoder | Natural/urban settings, hour-long Alpine hike | Shows perception-conditioned locomotion beyond proprioceptive reflexes |
| 9 | Rapid Locomotion 2022 | Quadruped | MIT Mini Cheetah | RL + online system ID | Adaptive curriculum, online system identification | Up to 3.9 m/s; grass/ice/gravel/disturbances | High-speed agility example |
| 10 | Walk These Ways 2022 | Quadruped | Legged robot | RL with multiplicity of behavior | Behavior-parameterized policy | Real-time switching; crouch/hop/run/stairs/shove/dance claims | Useful for Argus-style commandable gait families |
| 11 | Real-World Humanoid RL 2023 | Humanoid | Unnamed humanoid in abstract/page | Model-free RL + causal transformer | Randomized sim, zero-shot transfer, history-based adaptation | Outdoor terrain, external disturbance robustness | Important shift from quadrupeds to full humanoid RL |
| 12 | Agile Soccer 2023/2024 | Humanoid / biped | 20-actuator miniature humanoid | Deep RL | Dynamics randomization and perturbations, zero-shot transfer | 181% faster walking, 302% faster turning, 63% less stand-up time, 34% faster kicking vs scripted baseline | End-to-end skill stack, not just walking |
| 13 | Humanoid-Gym 2024 | Humanoid | RobotEra XBot-S/XBot-L | RL framework | Isaac Gym training, MuJoCo sim-to-sim bridge, zero-shot sim-to-real | Real-world verification on XBot-S/L | Toolchain and reproducibility example for humanoid RL |
| 14 | HumanPlus 2024 | Humanoid | 33-DoF, 180 cm humanoid | RL + human imitation + behavior cloning | Human motion data -> RL low-level control -> shadowing -> supervised task policy | 60-100% task success on manipulation-heavy humanoid tasks | Shows locomotion/control policy as foundation for whole-body autonomy |
| 15 | Challenging Terrain Humanoid 2024 | Humanoid | Real humanoid | Sequence modeling + RL refinement | Prior trajectory sequence model, uneven-terrain RL | 4+ miles of Berkeley trails; steep SF streets | Current exemplar of outdoor humanoid locomotion learning |
| 16 | HOVER 2024/2025 | Humanoid | Humanoid robots | Multi-mode policy distillation | Full-body kinematic motion imitation as shared abstraction | Seamless transitions among modes claimed | Distillation architecture for integrating locomotion and manipulation |
| 17 | Adversarial Humanoid Imitation 2025 | Humanoid | Unitree H1 | Adversarial locomotion + motion imitation | MuJoCo training/evaluation plus hardware | Robust locomotion and precise motion tracking claims | Recent H1 example connecting locomotion and whole-body motion imitation |
| 18 | legged_gym | Quadruped/biped | ANYmal, A1, Cassie examples | High-throughput RL tooling | Isaac Gym parallel simulation; deploy trained policies | Open-source project lineage | Practical R&D substrate for Argus-like experimentation |

## 3. Taxonomy of Learning-Based Legged Locomotion Systems

### 3.1 End-to-end proprioceptive RL policies

**Pattern:** Train a neural policy in simulation using observations such as base velocity estimates, IMU state, joint positions/velocities, command velocities, and recent action/state history. Deploy the policy as a high-rate joint target, joint torque, or PD target generator.

**Representative sources:** Tan 2018 [1], Hwangbo 2019 [3], Lee 2020 [4], Rudin 2021/2022 [6], Humanoid-Gym 2024 [13].

**What it buys:**
- High agility and robustness can emerge without hand-designed foothold or gait logic.
- The same training harness can optimize many reward variants quickly once the simulator/robot model is stable.
- Modern GPU-parallel simulators make training iteration times practical rather than academic.

**What it costs:**
- Reward design, observation design, actuator modeling, and domain randomization become the new control design problem.
- Policies can exploit simulator artifacts unless heavily randomized and validated.
- Debugging learned failure modes is harder than debugging an analytical gait generator.

### 3.2 RL with reference motions or periodic gait structure

**Pattern:** Instead of asking RL to discover all gait timing from scratch, provide reference trajectories, periodic reward terms, phase variables, or gait schedules. RL learns feedback stabilization and adaptation around this structure.

**Representative sources:** Xie 2018 Cassie [2], Siekmann 2021 Cassie [5], Walk These Ways 2022 [10].

**What it buys:**
- Faster convergence and more human-/animal-readable gait styles.
- Easier commandability: velocity command, gait phase, gait style, or behavior embedding can be explicit inputs.
- Better fit for projects migrating from analytical gaits, because the analytical controller can become a reference or teacher.

**What it costs:**
- The reference can cap exploration or encode bad assumptions.
- Phase variables and gait schedules can reduce robustness if the robot needs non-periodic recovery motions.

### 3.3 Teacher-student, privileged learning, and distillation

**Pattern:** Train a teacher policy with privileged simulator state, terrain maps, future information, or multiple specialized skills; distill into a deployable student using only onboard observations. Related variants distill multiple controllers into one mode-switching policy.

**Representative sources:** RMA uses a base policy plus adaptation module with privileged/simulated variability logic [7]; HOVER uses multi-mode policy distillation for humanoid whole-body control [16]; HumanPlus uses RL low-level control plus supervised imitation/behavior cloning stages [14].

**What it buys:**
- Lets training exploit information unavailable on the real robot while keeping the deployed policy realistic.
- Provides a structured path from many specialist controllers or human demonstrations to one runtime policy.
- Useful when Argus needs to preserve simple runtime inference but train with rich simulator labels.

**What it costs:**
- Requires careful separation between training-only observations and deployable observations.
- Dataset mismatch between teacher rollouts and student deployment can produce brittle behavior.
- Distillation adds a second optimization problem, so failure diagnosis spans teacher, student, and data coverage.

### 3.4 Online adaptation and system identification

**Pattern:** The policy infers hidden environment/robot parameters from recent observation-action history or an explicit adaptation module. These inferred latents condition the locomotion policy.

**Representative sources:** RMA 2021 [7], Rapid Locomotion 2022 [9], Real-World Humanoid RL 2023 [11], Challenging Terrain Humanoid 2024 [15].

**What it buys:**
- Robustness to payload changes, friction changes, deformable terrain, actuator wear, and modeling error.
- Real-world adaptation without explicit real-world fine-tuning.
- Strong fit for outdoor locomotion and cheap robot hardware where parameters drift.

**What it costs:**
- Adaptation can lag sudden contact changes.
- Bad state estimation can poison the adaptation latent.
- Needs validation over disturbances, terrain changes, and hardware faults, not just nominal walking.

### 3.5 Perceptive locomotion policies

**Pattern:** Combine proprioception with exteroception such as depth, height maps, terrain encoders, or visual features. The policy uses terrain information to adjust stepping, body posture, and gait.

**Representative sources:** Miki 2022 [8]; HOVER and HumanPlus are broader whole-body examples where perception and imitation feed task-level behavior [14,16].

**What it buys:**
- Necessary for stairs, obstacles, gaps, clutter, and anticipatory foothold selection.
- Moves beyond blind robustness to terrain-aware behavior.

**What it costs:**
- Requires perception pipeline, calibration, latency handling, and sim asset/terrain generation.
- Exteroceptive policies are more sensitive to sensor noise and occlusion than proprioception-only policies.
- Data distribution becomes a combined locomotion + perception problem.

### 3.6 Imitation learning and motion imitation for humanoids

**Pattern:** Learn low-level controllers or whole-body behaviors from motion capture, video-derived human motion, teleoperation, or demonstrations, often with RL for physical feasibility and supervised behavior cloning for high-level task policies.

**Representative sources:** HumanPlus 2024 [14], HOVER 2024/2025 [16], Adversarial Humanoid Imitation 2025 [17], Xie 2018 reference mimicry for Cassie [2].

**What it buys:**
- Natural-looking humanoid motion and richer whole-body skill repertoires.
- Efficient task acquisition when demonstrations are available.
- Useful bridge from locomotion-only control to loco-manipulation.

**What it costs:**
- Human motion retargeting to robot morphology is nontrivial.
- Demonstration coverage and embodiment mismatch can dominate performance.
- Pure imitation often needs RL or dynamics-aware filtering to become physically robust.

### 3.7 Residual / hybrid learning around classical controllers

**Pattern:** Keep an analytical gait, MPC, WBC, or PD controller as a baseline and learn a residual action, residual target, gait parameter correction, terrain-adaptation latent, or stabilizing term.

**Representative evidence in this pass:** The accessible sources above emphasize full learned policies, reference-conditioned RL, online adaptation, and distillation more than explicit residual RL. However, the taxonomy remains relevant for Argus because an analytical trot gait can be used as a prior, reference generator, safety fallback, or residual-learning baseline.

**What it buys:**
- Lower-risk migration path from an existing analytical controller.
- Residual policy can focus on errors the hand-designed gait cannot handle: slip, pushes, compliance mismatch, or rough terrain.
- Easier safety story because residual magnitudes can be bounded.

**What it costs:**
- The learned policy may inherit the baseline's limitations.
- Residual action spaces require careful scaling; too small cannot help, too large defeats the safety purpose.
- Requires deciding where residuals live: foot trajectory, joint position target, torque, body velocity command, or gait parameters.

## 4. Key Tradeoffs

| Decision axis | Option A | Option B | Tradeoff |
|---|---|---|---|
| Policy output | Joint position / PD targets | Joint torques | PD targets are easier to deploy and safer in many simulators; torque policies can be more expressive but are more sensitive to actuator modeling and control-loop fidelity. |
| Training observations | Proprioception only | Proprioception + exteroception | Proprioception-only systems are simpler and surprisingly robust; exteroception is needed for anticipatory obstacle/stair behavior but adds perception failure modes. |
| Adaptation | Static robust policy | Online adaptation/history-conditioned policy | Static policies are simpler; adaptation improves terrain/payload/wear robustness but introduces latency and hidden-state failure modes. |
| Learning style | From-scratch RL | Reference/imitation-conditioned RL | From-scratch can discover unconventional robust strategies; references/imitation improve sample efficiency and style/commandability. |
| Sim-to-real strategy | More accurate simulator | More randomized simulator | Model fidelity reduces nominal gap; randomization hardens policies to unknown errors. Strong systems usually use both actuator/system modeling and randomization. |
| Runtime architecture | Single monolithic policy | Hierarchical/distilled/multi-mode stack | Monolithic is simpler to run; hierarchical/distilled stacks are better for whole-body humanoid skill composition but harder to train/debug. |
| Safety path | Direct policy deployment | Learned policy behind constraints/fallbacks | Direct deployment is clean for research demos; fallback/residual designs are more practical for incremental Argus upgrades. |
| Research value | Analytical gait baseline + learned residual | Full RL locomotion stack | Residual path is lower complexity and more publishable as an incremental R&D scaffold; full RL is higher ceiling but demands more infrastructure. |

## 5. Representative Humanoid / Biped Examples

### 5.1 Cassie feedback walking with deep RL (Xie et al. 2018) [2]

Cassie is a biped rather than a full humanoid, but it is a central bridge between classic biped control and humanoid RL. The paper learns feedback walking controllers by imitating reference motion and reports robustness to sensory delay, uneven ground, and pelvis pushes. The policy-interpolation and time-scaling ideas are especially relevant for commandable gait variants.

**Argus relevance:** If Argus has an analytical gait phase variable, a Cassie-style approach suggests converting that into a reference-conditioned RL problem rather than discarding it immediately.

### 5.2 Cassie all-common-gaits via periodic reward composition (Siekmann et al. 2021) [5]

This work uses periodic reward composition to express biped gait families and demonstrates standing, walking, hopping, running, skipping, and gait transitions on Cassie. It is a clean example of using reward structure rather than explicit classical gait derivation to obtain multiple gaits.

**Argus relevance:** A robot-dog trot/walk/bound family could be parameterized similarly with periodic foot-contact or velocity terms, preserving commandability while moving control authority into RL.

### 5.3 Real-world humanoid locomotion with RL (Radosavovic et al. 2023) [11]

This system uses a causal transformer policy over recent proprioceptive observations/actions, trained with large-scale model-free RL in randomized simulation, then transferred zero-shot to a real humanoid. The key idea is in-context adaptation through history rather than a memoryless MLP.

**Argus relevance:** For a MuJoCo-based Argus stack, history-conditioned policies are a practical way to compensate for unmodeled contacts, latency, and actuator effects without requiring exteroception first.

### 5.4 Humanoid-Gym zero-shot sim-to-real framework (Gu et al. 2024) [13]

Humanoid-Gym packages humanoid RL around Isaac Gym, with a MuJoCo sim-to-sim bridge and real verification on RobotEra XBot-S/XBot-L. It is less a single control trick than a reproducible R&D scaffold.

**Argus relevance:** This is a strong example of a modern training toolchain pattern: high-throughput training simulator plus independent validation simulator. Argus already using MuJoCo can benefit from the “sim-to-sim before sim-to-real” mindset even before hardware exists.

### 5.5 HumanPlus humanoid shadowing and imitation (Fu et al. 2024) [14]

HumanPlus trains a low-level humanoid policy in simulation from human motion data, uses the real robot to shadow humans and collect whole-body data, then trains autonomous skills by supervised behavior cloning. The reported tasks extend beyond locomotion into whole-body behavior.

**Argus relevance:** For future humanoid Argus variants, locomotion policy should be viewed as a reusable low-level substrate under imitation- or task-learning layers.

### 5.6 Learning humanoid locomotion over challenging terrain (Radosavovic et al. 2024) [15]

This work combines flat-ground sequence-model training with RL refinement on uneven terrain and reports real outdoor deployment over Berkeley trails and steep San Francisco streets. It reflects the current trend: sequence models and RL are being merged for robust humanoid locomotion.

**Argus relevance:** A staged curriculum is better than immediately training on all terrain: first stable flat walking, then randomized terrain, then terrain-specific refinement.

### 5.7 HOVER and adversarial humanoid imitation (He et al. 2024/2025; Shi et al. 2025) [16,17]

HOVER frames whole-body humanoid control as multi-mode policy distillation; the adversarial H1 work combines locomotion and motion imitation. Both indicate that humanoid R&D is shifting from isolated walking policies toward unified motion-control substrates.

**Argus relevance:** If Argus’s long-term goal includes manipulation or humanoid morphology, separate one-off locomotion controllers should be avoided in favor of interfaces that can compose navigation, posture, and whole-body task modes.

## 6. Representative Quadruped / Robot Dog Examples

### 6.1 Sim-to-real quadruped RL (Tan et al. 2018) [1]

This is an early canonical robot-dog-style sim-to-real RL paper. It emphasizes that deployment success depends on actuator and latency modeling, simulator calibration, randomized training conditions, and disturbances, not only the RL algorithm.

**Argus relevance:** The first serious Argus RL upgrade should invest in actuator/latency/noise modeling and randomized initial states before optimizing exotic algorithms.

### 6.2 ANYmal agile skills (Hwangbo et al. 2019) [3]

Hwangbo et al. show simulation-trained neural locomotion policies transferred to ANYmal, with claims of better velocity tracking, faster running, and fall recovery. This helped establish learned policies as viable competitors to handcrafted controllers on real quadrupeds.

**Argus relevance:** Velocity-command tracking is a natural objective for Argus because the existing command interface appears to be velocity-command oriented.

### 6.3 ANYmal challenging terrain (Lee et al. 2020) [4]

Lee et al. demonstrate proprioceptive RL with zero-shot transfer to snow, mud, rubble, vegetation, water, and other natural terrain. The notable lesson is that exteroception is not always required for useful field robustness, provided the policy is trained with sufficient variation and proprioceptive feedback.

**Argus relevance:** Before building a vision/height-map stack, Argus can get meaningful research value from proprioception-only rough-terrain randomization.

### 6.4 Massively parallel RL / legged_gym (Rudin et al. 2021/2022; legged_gym) [6,18]

Rudin et al. and legged_gym define the high-throughput style: train thousands of robots in parallel on GPU, use terrain curricula, and iterate quickly. Reported training times are minutes rather than days for certain ANYmal settings.

**Argus relevance:** If Argus stays MuJoCo-only, training throughput may be lower than Isaac Gym-style setups. A planner should decide whether Argus needs Isaac Gym / Isaac Lab integration, a vectorized MuJoCo setup, or a smaller-scale learning baseline.

### 6.5 RMA: Rapid Motor Adaptation (Kumar et al. 2021) [7]

RMA uses a base policy and adaptation module trained entirely in simulation, then deploys to Unitree A1 without real-world fine-tuning. It targets terrain, payload, wear, and other hidden dynamics changes.

**Argus relevance:** This is the best model for “same command interface, more robust execution.” Argus can keep velocity commands and train a policy conditioned on a latent inferred from recent observations.

### 6.6 Perceptive locomotion in the wild (Miki et al. 2022) [8]

Miki et al. combine proprioceptive and exteroceptive inputs with a recurrent encoder and report long outdoor operation in challenging natural and urban terrain.

**Argus relevance:** This is a later-stage upgrade path after proprioceptive RL: add height/terrain perception once the base learned locomotion policy is stable.

### 6.7 Rapid Locomotion / Walk These Ways (Margolis et al. 2022) [9,10]

Rapid Locomotion emphasizes high-speed agility on MIT Mini Cheetah with online system ID and curriculum learning. Walk These Ways exposes a family of learned behaviors that can be switched at run time.

**Argus relevance:** These are especially aligned with an R&D simulator project: behavior multiplicity gives visible, testable capabilities beyond “walk forward,” while online ID addresses the sim-to-real gap conceptually even if Argus has no hardware yet.

## 7. Cross-Cutting Findings

1. **Modern legged RL is not just “run PPO.”** The repeatable systems combine reward shaping, observation design, actuator modeling, latency/noise modeling, randomized dynamics, terrain curricula, command curricula, and deployment constraints. Sources [1], [6], [7], [9], and [13] all point to the stack around RL as the real system.

2. **Quadruped learning is more mature than humanoid learning, but humanoids are catching up rapidly.** Quadruped sim-to-real examples are strong from 2018 onward [1,3,4,6,7,8,9,10]. Humanoid/biped examples expand from Cassie and miniature humanoids [2,5,12] to full humanoid outdoor locomotion, toolchains, and whole-body imitation by 2023-2025 [11,13,14,15,16,17].

3. **History and adaptation are now standard for hard real-world settings.** RMA [7], Rapid Locomotion [9], and the humanoid transformer policies [11,15] all use recent experience or adaptation to address hidden dynamics and terrain changes.

4. **Teacher-student/distillation is a scaling pattern, not just a trick.** It appears whenever training information is richer than runtime information, or whenever many specialist skills need to be compressed into one deployable controller [7,14,16].

5. **Sim-to-real success usually uses both gap reduction and robustness.** Actuator/latency modeling, simulator calibration, and sim-to-sim validation reduce the gap; randomization, disturbances, curricula, and adaptation make policies tolerate the remaining gap [1,6,7,9,13].

6. **Residual/hybrid learning is underrepresented in the top accessible exemplars from this pass, but highly relevant as an engineering migration path.** For Argus, a residual policy around the existing analytical gait is lower risk than immediately replacing the gait generator with a black-box policy.

## 8. Implications for Argus

The plan states Argus currently maps velocity command -> analytical trot gait -> joint position targets -> MuJoCo position actuators. Based on the learning-locomotion literature above, the practical upgrade path should be staged rather than jumping directly to full humanoid-grade RL.

### 8.1 Best near-term learning upgrade: command-conditioned learned gait stabilizer

Keep the velocity-command interface. Train a policy that outputs either:

- residual joint-position offsets on top of the analytical trot targets, or
- gait-parameter corrections such as step height, stance timing, foot placement offset, and body posture offset, or
- direct PD joint targets once residual control is validated.

**Why:** This preserves Argus’s current architecture while adding measurable learning value. It aligns with reference-conditioned RL patterns [2,5,10] and sim-to-real practices [1,6,7].

### 8.2 Build a legged-RL training harness before chasing algorithms

Minimum research harness:

- vectorized environments or batched rollouts;
- command randomization over linear/angular velocity;
- terrain randomization, friction randomization, mass/inertia randomization, actuator strength randomization, latency/noise injection;
- reward terms for command tracking, upright posture, energy/smoothness, foot slip, undesired contacts, joint-limit avoidance, and fall termination;
- evaluation suite with fixed seeds and terrain families.

**Why:** The cited systems succeed because of the whole pipeline, not because of one isolated policy architecture.

### 8.3 Use proprioception-only learning before perception

Start with IMU/base state estimates, joint states, previous actions, command velocity, and optionally gait phase. Add height maps or vision later.

**Why:** Lee et al. [4], RMA [7], and Rapid Locomotion [9] show high value from proprioception/adaptation alone. Perception adds calibration, latency, and data-distribution problems [8].

### 8.4 Add online adaptation as a second milestone

After a baseline learned controller works, add an adaptation latent inferred from recent observations/actions, following RMA-style thinking [7] or history-conditioned transformer/MLP policies [11,15].

**Why:** It directly targets the biggest sim-to-real and sim-to-sim gaps: friction, compliance, latency, mass variation, and actuator strength.

### 8.5 Consider sim-to-sim validation

If Argus remains MuJoCo-first, train in MuJoCo and validate in another engine only if toolchain resources permit. Alternatively, train in Isaac Gym/Lab and validate in MuJoCo, similar in spirit to Humanoid-Gym’s Isaac Gym plus MuJoCo bridge [13].

**Why:** Simulator overfitting is a real risk. Sim-to-sim failure is a cheap warning before hardware or high-stakes demos.

### 8.6 Avoid premature full humanoid imitation stack

HumanPlus, HOVER, and H1 adversarial imitation are important for the long-term humanoid roadmap [14,16,17], but they require datasets, retargeting, and whole-body task definitions. For a quadruped/robot-dog Argus phase, they are better treated as architectural inspiration than immediate implementation targets.

## 9. Recommended Argus Learning Roadmap

| Stage | Goal | Control output | Training style | Complexity | Research value | Main evidence |
|---|---|---|---|---|---|---|
| 0 | Preserve analytical baseline | Existing joint position targets | None | Low | Baseline comparator | Needed for ablation |
| 1 | Residual trot stabilizer | Residual joint-position offsets | Command-conditioned RL around analytical gait | Medium | High | Reference/residual migration inspired by [2,5,10] |
| 2 | Direct learned quadruped locomotion | PD joint targets | Proprioceptive RL with domain randomization | Medium-high | High | [1,3,4,6,18] |
| 3 | Robust/adaptive locomotion | PD targets + adaptation latent | RMA/history-conditioned policy | High | Very high | [7,9,11,15] |
| 4 | Perceptive rough-terrain locomotion | PD targets conditioned on terrain features | Exteroceptive RL / teacher-student | High | Very high, but infrastructure-heavy | [8] |
| 5 | Whole-body imitation / humanoid expansion | Whole-body policy | Motion imitation, distillation, behavior cloning | Very high | Strategic if humanoid direction matters | [14,16,17] |

## 10. Practical Evaluation Metrics for Argus

Use a fixed evaluation battery instead of relying on videos or single rollouts:

- command tracking error for forward/lateral/yaw velocity;
- fall rate over randomized seeds;
- distance traveled before failure;
- recovery from pushes and randomized initial perturbations;
- energy / action smoothness / joint-limit violations;
- foot slip and undesired contact rate;
- terrain success rate across flat, slopes, steps, rough heightfields, low friction, and compliance proxies;
- robustness to actuator strength, latency, mass, and friction randomization;
- sim-to-sim transfer score if a second simulator is available;
- ablation against the existing analytical trot controller.

## 11. What Not to Over-Claim

- Do not claim learned policies are universally better than WBC/MPC. The evidence supports high agility and robustness in many settings, but learned systems rely on substantial training infrastructure and careful validation.
- Do not claim sim-to-real is solved by domain randomization alone. The stronger examples combine randomization with actuator modeling, curricula, adaptation, and deployment engineering [1,6,7,9,13].
- Do not treat humanoid and quadruped difficulty as equivalent. Humanoids add higher center-of-mass instability, more degrees of freedom, richer contact modes, and often whole-body task requirements.
- Do not jump to perception before proprioceptive locomotion is strong. Perceptive locomotion is powerful but expands the failure surface.
- Do not evaluate only nominal flat walking. The literature’s meaningful claims are on rough terrain, pushes, speed, gait transitions, payload/terrain adaptation, or long outdoor traverses.

## 12. Gaps / Follow-Up Targets

- I found strong examples through 2025; I did not identify a reliable, source-verified 2026 locomotion-learning exemplar in this pass. Since today is 2026-04-30, a final report could optionally add a targeted 2026 citation sweep.
- Explicit residual-learning legged-locomotion papers were not prominent among the accessible top sources fetched here. If Argus prioritizes residual learning, do a focused follow-up on “residual RL + locomotion + quadruped/humanoid” and “learning residuals over MPC/WBC.”
- Some arXiv ID guesses returned unrelated papers; only the numbered relevant sources above should be used as evidence.
- Full methodology details for several sources require PDF-level reading beyond the abstract/page extraction used here; final claims about exact reward terms, network architectures, and randomization ranges should be checked in the PDFs before implementation.

## 13. Bottom Line

For Argus, the evidence points to a staged learning roadmap: keep the velocity-command interface, first add a residual or reference-conditioned RL controller around the analytical trot, then progress to direct proprioceptive RL with heavy domain randomization, then add online adaptation, and only later add exteroception or humanoid whole-body imitation. Quadruped robot-dog learning is mature enough to justify implementation now; humanoid learning is advancing quickly but requires substantially more infrastructure and data discipline.
