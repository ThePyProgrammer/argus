# Classical and Model-Based Locomotion R&D Systems for Humanoids and Robot Dogs

**Task:** T1 from `/home/prannayag/pragnition/robotics/argus/outputs/.plans/locomotion-rd-systems.md`
**Scope:** Non-learning/classical/model-based locomotion only: analytical gaits, CPGs, inverse kinematics, whole-body control, MPC, trajectory optimization, centroidal dynamics, contact planning. RL/imitation/sim-to-real are mentioned only as contrast.
**Date:** 2026-04-30

## 1. Numbered sources

1. **Kajita et al., "Biped walking pattern generation by using preview control of zero-moment point," ICRA 2003.** DOI: `10.1109/ROBOT.2003.1241826`; URL: https://doi.org/10.1109/ROBOT.2003.1241826. Crossref/WebFetch verified title, authors, venue, DOI. This is the canonical ZMP preview-control paper for humanoid walking pattern generation.
2. **Pratt et al., "Capture Point: A Step toward Humanoid Push Recovery," Humanoids 2006.** DOI: `10.1109/ICHR.2006.321385`; URL: https://doi.org/10.1109/ICHR.2006.321385. Crossref verified metadata. Introduces capture point-style reasoning for push recovery and step placement.
3. **Stephens and Atkeson, humanoid push recovery / balance control work, Autonomous Robots 2012.** URL attempted via CMU Robotics Institute redirects; source metadata could not be fetched reliably in this session. Included as a low-confidence pointer only because the CMU RI-hosted PDF URL returned 404 after redirect.
4. **Herzog et al., "Momentum control with hierarchical inverse dynamics on a torque-controlled humanoid," Autonomous Robots 2016.** DOI: `10.1007/s10514-015-9476-6`; URL: https://doi.org/10.1007/s10514-015-9476-6. Crossref verified title, authors, venue, DOI. Representative humanoid whole-body inverse dynamics / momentum-control stack.
5. **Kuindersma et al., "Optimization-based locomotion planning, estimation, and control design for the Atlas humanoid robot," Autonomous Robots 2016.** DOI: `10.1007/s10514-015-9479-3`; URL: https://doi.org/10.1007/s10514-015-9479-3. WebFetch verified title, authors, journal, publication year, DOI. Representative Atlas optimization-based locomotion stack.
6. **Ponton et al., "A convex model of humanoid momentum dynamics for multi-contact motion generation," Humanoids 2016.** DOI: `10.1109/HUMANOIDS.2016.7803371`; URL: https://doi.org/10.1109/HUMANOIDS.2016.7803371. Crossref verified metadata. Representative centroidal/momentum convexification for multi-contact humanoid planning.
7. **Ijspeert, "Central pattern generators for locomotion control in animals and robots: A review," Neural Networks 2008.** DOI: `10.1016/j.neunet.2008.03.014`; URL: https://doi.org/10.1016/j.neunet.2008.03.014. Crossref/Semantic Scholar verified title, venue, year, DOI. CPG review relevant to rhythmic gait generation.
8. **Raibert, "Legged Robots That Balance," MIT Press 1986.** URL: https://mitpress.mit.edu/9780262181174/legged-robots-that-balance/. Classic source for simple dynamic legged locomotion decomposition: hopping/running balance, foot placement, and body attitude control. Metadata not tool-verified in this session; included as assumed/classic background.
9. **Fankhauser et al., "Free Gait — An architecture for the versatile control of legged robots," Humanoids 2016.** DOI: `10.1109/HUMANOIDS.2016.7803401`; URL: https://doi.org/10.1109/HUMANOIDS.2016.7803401; code/docs: https://github.com/leggedrobotics/free_gait. Crossref and GitHub README verified. Architecture provides whole-body abstraction layer, task-space commands for leg/base motion, joint/Cartesian leg motion, targets/trajectories, feedback whole-body control, ROS/C++/Python/YAML use.
10. **Bellicoso et al., "Dynamic locomotion and whole-body control for quadrupedal robots," IROS 2017.** DOI: `10.1109/IROS.2017.8206174`; URL: https://doi.org/10.1109/IROS.2017.8206174. Crossref verified metadata. Representative ANYmal-era dynamic locomotion with whole-body control.
11. **Neunert et al., "Whole-Body Nonlinear Model Predictive Control Through Contacts for Quadrupeds," IEEE RA-L 2018.** DOI: `10.1109/LRA.2018.2800124`; URL: https://doi.org/10.1109/LRA.2018.2800124. Crossref verified metadata. Representative full-body nonlinear MPC through contacts for quadrupeds.
12. **Winkler et al., "Gait and Trajectory Optimization for Legged Systems Through Phase-Based End-Effector Parameterization," IEEE RA-L 2018.** DOI: `10.1109/LRA.2018.2798285`; URL: https://doi.org/10.1109/LRA.2018.2798285. Crossref verified metadata. Representative trajectory optimization formulation for legged systems.
13. **Di Carlo et al., "Dynamic Locomotion in the MIT Cheetah 3 Through Convex Model-Predictive Control," IROS 2018.** DOI: `10.1109/IROS.2018.8594448`; URL: https://doi.org/10.1109/IROS.2018.8594448. WebFetch verified title, authors, year, DOI, venue. Representative convex MPC robot-dog/quadruped controller.
14. **Kim et al., "Highly Dynamic Quadruped Locomotion via Whole-Body Impulse Control and Model Predictive Control," arXiv 2019.** URL: https://arxiv.org/abs/1909.06586. WebFetch verified title, authors, year, platform, approach, and top-speed claim. Combines MPC force targets with whole-body impulse/control on Mini Cheetah; evaluated on six gaits and reports 3.7 m/s.
15. **Patel et al., "Contact-Implicit Trajectory Optimization Using Orthogonal Collocation," IEEE RA-L 2019.** DOI: `10.1109/LRA.2019.2900840`; URL: https://doi.org/10.1109/LRA.2019.2900840. Crossref/WebFetch verified title, authors, year, venue, DOI. Generic intermittent-contact trajectory optimization method, relevant to locomotion planning because it avoids requiring a fixed contact schedule.
16. **Grandia et al., "Perceptive Locomotion Through Nonlinear Model-Predictive Control," IEEE T-RO 2023.** DOI: `10.1109/TRO.2023.3275384`; arXiv URL: https://arxiv.org/abs/2208.08373; DOI URL: https://doi.org/10.1109/TRO.2023.3275384. Crossref/Semantic Scholar/WebFetch verified. ANYmal stack integrating terrain perception, foothold feasibility constraints, multiple-shooting nonlinear MPC, real-time iteration, and hardware validation over gaps/slopes/stepping stones.
17. **OCS2 official project / README.** URL: https://github.com/leggedrobotics/ocs2 and docs https://leggedrobotics.github.io/ocs2/. WebFetch verified README claims: C++ toolbox for optimal control of switched systems, real-time MPC focus, solvers including SLQ, iLQR, SQP, SLP, IPM, ROS integration, Pinocchio helpers, and legged robot examples.
18. **Free Gait official GitHub README.** URL: https://github.com/leggedrobotics/free_gait. WebFetch verified architecture details; also tied to Source 9 paper.

## 2. Evidence table

| Source | Robot class | Method family | Evidence / contribution | Confidence |
|---|---:|---|---|---|
| 1 Kajita ZMP preview | Humanoid | Analytical reduced-order planning/control | ZMP preview control generates biped walking patterns from a linear inverted-pendulum-style model and desired ZMP behavior. | High for metadata; medium for method summary because full paper content was not fetched. |
| 2 Pratt capture point | Humanoid | Analytical balance / step placement | Capture point formalizes where the robot must step to stop divergent CoM motion, useful for push recovery. | High for metadata; medium for method summary. |
| 4 Herzog momentum inverse dynamics | Humanoid | Whole-body control, hierarchical inverse dynamics | Uses momentum control and hierarchical inverse dynamics on torque-controlled humanoid; representative task-priority WBC. | High for metadata; medium for detailed internals. |
| 5 Kuindersma Atlas | Humanoid | Optimization-based planning, estimation, control | Full Atlas humanoid locomotion stack using optimization-based planning/control design. | High for metadata; medium for details. |
| 6 Ponton convex momentum | Humanoid | Centroidal dynamics / convex optimization | Convex model of humanoid momentum dynamics for multi-contact motion generation. | High for metadata; medium for details. |
| 7 Ijspeert CPG review | Both | CPG rhythmic control | CPGs are a standard biologically inspired rhythmic gait-generation family. | High for metadata; medium for claims. |
| 9 Free Gait | Quadruped | Whole-body abstraction / gait architecture | Official README says it provides a whole-body abstraction layer, task-space leg/base commands, joint/Cartesian leg motions, trajectories, and feedback WBC. | High. |
| 10 Bellicoso dynamic locomotion | Quadruped | Whole-body control | Representative quadruped dynamic locomotion and WBC on ANYmal lineage. | High for metadata; medium for details. |
| 11 Neunert whole-body NMPC | Quadruped | Full-body NMPC through contacts | RA-L paper specifically targets whole-body nonlinear MPC through contacts. | High for metadata; medium for details. |
| 12 Winkler phase-based TO | Both/legged | Trajectory optimization | Phase-based end-effector parameterization for gait and trajectory optimization. | High for metadata; medium for details. |
| 13 Di Carlo Cheetah 3 | Quadruped | Convex MPC | Convex MPC for dynamic locomotion on MIT Cheetah 3. | High. |
| 14 Kim Mini Cheetah | Quadruped | MPC + whole-body impulse/control | WebFetch summary: MPC plans long-horizon force targets; whole-body layer outputs torque/position/velocity commands; Mini Cheetah reached 3.7 m/s. | High for fetched abstract-level claims. |
| 15 Patel contact-implicit TO | General legged/contact robots | Contact-implicit trajectory optimization | Orthogonal collocation method for dynamic robots with intermittent contact, avoiding preset contact schedules. | High. |
| 16 Grandia perceptive NMPC | Quadruped | Perceptive nonlinear MPC + contact planning | Integrates perception, foothold feasibility constraints, nonlinear MPC, and ANYmal hardware validation over rough terrain. | High. |
| 17 OCS2 | Both/toolchain | Optimal control/MPC tooling | Official README/docs list real-time MPC focus, SLQ/iLQR/SQP/SLP/IPM, ROS integration, Pinocchio helpers, legged examples. | High. |

## 3. Taxonomy of non-learning locomotion control systems

### 3.1 Analytical gait generators and inverse kinematics

**What they are:** Hand-designed gait phase machines produce desired foot trajectories and body motion; inverse kinematics maps desired foot poses to joint angles; lower-level position or impedance control tracks the targets.

**Typical architecture:**

`velocity command -> gait scheduler/phase oscillator -> foot swing/stance trajectories -> body pose target -> IK -> joint position/velocity/torque targets -> actuator controller`

**Strengths:** Simple, interpretable, low compute, good for simulation bring-up and educational R&D. Works well when terrain is flat and contact timing is known.

**Weaknesses:** Limited disturbance rejection, poor contact-force reasoning, brittle under terrain variation unless augmented with state estimation, foothold adaptation, force control, and recovery logic. If implemented with pure position actuators, contact impulses and foot slip are hidden rather than regulated.

**Representative sources:** Source 1 for analytical humanoid walking pattern generation; Source 8 for classic dynamic legged control decomposition; Source 9 for a more general command/action architecture.

### 3.2 Central Pattern Generators (CPGs)

**What they are:** Coupled oscillators generate rhythmic gait phases and can transition between periodic patterns. They are classical/non-learning in the sense that oscillator structure and coupling are engineered, though CPGs can be combined with adaptation or learning.

**Strengths:** Natural fit for rhythmic quadruped gaits such as walk, trot, pace, bound; supports smooth phase relationships and gait transitions.

**Weaknesses:** A CPG alone is only a timing/trajectory primitive. It does not solve contact wrench feasibility, centroidal balance, foothold reachability, or whole-body dynamics. Serious robot-dog systems typically embed rhythmic patterns inside WBC/MPC/foothold planning rather than treating the oscillator as the full controller.

**Representative source:** Source 7.

### 3.3 Reduced-order humanoid balance: ZMP, LIPM, capture point

**What they are:** Simplified center-of-mass models, usually linear inverted pendulum variants, enforce support-region and zero-moment constraints to plan stable biped walking. Capture-point methods reason about recoverability and step placement.

**Strengths:** Computationally light, historically successful for humanoid walking, mathematically interpretable, good for quasi-flat terrain and moderate motions.

**Weaknesses:** Reduced-order assumptions can break under highly dynamic, multi-contact, non-coplanar, or force-limited tasks. Full-body feasibility still needs IK/WBC and contact constraints.

**Representative sources:** Source 1 (ZMP preview), Source 2 (capture point), Source 6 (convex momentum/multi-contact motion generation).

### 3.4 Whole-Body Control (WBC) / inverse dynamics

**What it is:** A lower-to-mid-level controller solves constrained inverse dynamics or quadratic programs to satisfy task priorities: contact constraints, friction cones, base/momentum objectives, swing-foot tracking, posture regularization, torque limits, and joint limits.

**Typical architecture:**

`state estimate + contacts + desired body/foot tasks -> WBC QP / hierarchical inverse dynamics -> joint torques or impedance targets`

**Strengths:** Coordinates all joints and contacts; supports torque-controlled platforms; cleanly handles multiple tasks and constraints; natural bridge between high-level planners and low-level actuators.

**Weaknesses:** Requires accurate dynamics, state estimation, contact state, friction assumptions, and a torque/impedance control interface. With only position actuators, a true inverse-dynamics WBC cannot be expressed directly.

**Representative sources:** Source 4 for humanoid momentum/hierarchical inverse dynamics; Source 10 for quadruped dynamic locomotion and WBC; Source 14 for MPC force targets translated by whole-body impulse/control.

### 3.5 Model Predictive Control (MPC)

**What it is:** Receding-horizon optimization predicts future robot or centroidal dynamics and solves for state/control/contact-force trajectories. The controller repeatedly replans as new state estimates arrive.

**Common variants:**

- **Convex/reduced-order MPC:** Often optimizes centroidal dynamics or ground reaction forces with convex approximations. Fast and deployable; Source 13 is the canonical MIT Cheetah 3 example.
- **Whole-body nonlinear MPC:** Optimizes full-body or richer dynamics through contact. More expressive but computationally harder; Source 11 and Source 16 are representative.
- **Perceptive MPC:** Adds terrain maps and foothold feasibility constraints; Source 16 integrates stepability, plane fitting, signed-distance fields, and local convex foothold constraints.

**Strengths:** Handles future contact-force planning, constraints, and disturbance rejection better than open-loop gaits. Good research-value upgrade path for robot-dog systems.

**Weaknesses:** Solver complexity, model mismatch, contact-mode assumptions, tuning burden, and dependency on state estimation/terrain perception. Convex MPC often needs a predefined gait/contact schedule; contact-implicit variants can avoid this but become harder optimization problems.

**Representative sources:** Sources 11, 13, 14, 16, 17.

### 3.6 Trajectory optimization and contact planning

**What it is:** Offline or online optimization over robot trajectories, contact sequences, footholds, timings, and forces. Can be contact-scheduled, phase-based, or contact-implicit.

**Strengths:** Excellent for generating feasible motions, testing limits, and building libraries or references for a WBC/MPC stack. Contact-implicit formulations can discover contact timings rather than requiring them.

**Weaknesses:** Often slower and more numerically fragile than simple MPC; contact-implicit optimization is especially hard because complementarity/contact events create non-smoothness or stiff constraints.

**Representative sources:** Source 12 for phase-based end-effector parameterization; Source 15 for contact-implicit orthogonal collocation; Source 5 for Atlas optimization-based planning/control.

### 3.7 Centroidal dynamics and momentum planning

**What it is:** Models the robot as total mass, center of mass, angular momentum, and contact wrenches. It is a middle ground between point-mass LIPM and full rigid-body dynamics.

**Strengths:** Captures physically important balance/contact-force behavior at lower dimension than full-body models. Common in both humanoid multi-contact and quadruped MPC.

**Weaknesses:** Needs a downstream whole-body layer to realize centroidal plans with real joints and contacts. Feasible centroidal forces do not guarantee joint-level feasibility.

**Representative sources:** Sources 4, 6, 11, 13, 16.

## 4. Key tradeoffs

| Design choice | Advantage | Cost / risk | Best use |
|---|---|---|---|
| Analytical gait + IK | Lowest complexity; easy to inspect; deterministic; enough for flat-ground demo. | Weak force/contact reasoning; brittle under pushes, slopes, bad footholds; limited research novelty. | Initial simulator locomotion; baseline controller; regression tests. |
| CPG timing + IK/impedance | Smooth rhythmic gaits and transitions; compact gait representation. | CPG is not a balance/contact controller by itself. | Quadruped gait phase generation feeding WBC/MPC. |
| ZMP/LIPM/capture-point | Mature humanoid reduced-order balance; efficient. | Assumes simplified dynamics/support geometry; needs whole-body realization. | Humanoid walking and push-recovery baselines. |
| WBC inverse dynamics | Coordinates full robot and constraints; strong lower-level abstraction. | Needs torque/impedance control, dynamics model, contact estimator, QP stack. | Upgrading from position-only IK to physically meaningful contact control. |
| Convex MPC | Real-time, deployable, strong contact-force planning for quadrupeds. | Simplified dynamics and usually fixed gait/contact schedule. | Robot dog trot/walk/bound over uneven but not extreme terrain. |
| Whole-body nonlinear MPC | More expressive, can optimize richer robot behavior. | Higher compute and tuning complexity. | Research-grade quadruped/humanoid control where solver/toolchain investment is acceptable. |
| Trajectory optimization | Finds feasible motions and contact schedules; useful for planning and references. | May be offline or fragile; contact-implicit versions are numerically hard. | Generating motion libraries, validating dynamic feasibility, planner references. |
| Perceptive MPC/contact planning | Explicit terrain/foothold reasoning. | Requires mapping/perception pipeline and terrain uncertainty handling. | Rough terrain robot-dog locomotion. |

## 5. Representative humanoid examples

### 5.1 ZMP preview-control humanoid walking (Kajita et al.)

Kajita et al. are the canonical representative for analytical humanoid walking pattern generation using ZMP preview control (Source 1). This family plans a center-of-mass trajectory so that the zero moment point stays within the support region. The planner then needs IK/WBC to realize the motion on the full humanoid.

**Why it matters:** It is the historical baseline for stable humanoid walking. For Argus-like R&D, it demonstrates the value of reduced-order analytical models: simple enough to implement, but still tied to physical balance constraints.

### 5.2 Capture point / push recovery (Pratt et al.)

Capture point methods treat biped balance as a recoverability problem: given the current CoM state, where must the foot be placed to arrest divergent motion (Source 2). This is not a full locomotion stack, but it is an important primitive for step adjustment and disturbance rejection.

**Why it matters:** It shows how classical controllers can add recovery behavior without RL. A robot dog analogue is foothold replanning based on predicted base motion and support feasibility.

### 5.3 Momentum control and hierarchical inverse dynamics (Herzog et al.)

Herzog et al. represent torque-controlled humanoid WBC using momentum control and hierarchical inverse dynamics (Source 4). The core idea is to make balance/momentum objectives and contact constraints first-class tasks, rather than only tracking joint angles.

**Why it matters:** It is the humanoid counterpart to quadruped WBC: a planner emits body/foot/momentum targets, and inverse dynamics converts those into feasible joint torques subject to contacts and limits.

### 5.4 Atlas optimization-based locomotion stack (Kuindersma et al.)

Kuindersma et al. document an optimization-based locomotion, estimation, and control design stack for the Atlas humanoid robot (Source 5). This is representative of complete humanoid systems where planning, estimation, and controller design are co-developed.

**Why it matters:** It is a warning against thinking of locomotion as only a gait generator. High-performance classical humanoid walking needs state estimation, contact reasoning, planner/controller separation, and verification in the loop.

### 5.5 Convex/centroidal multi-contact humanoid planning (Ponton et al.)

Ponton et al. provide a convex model of humanoid momentum dynamics for multi-contact motion generation (Source 6). This sits between simple ZMP walking and full-body nonlinear optimization.

**Why it matters:** Humanoids benefit from centroidal abstractions because arms, feet, and environment contacts can all affect momentum. The same architectural idea maps to quadrupeds as centroidal MPC with multiple foot contacts.

## 6. Representative quadruped / robot-dog examples

### 6.1 Free Gait architecture

Free Gait provides an architecture and whole-body abstraction layer for legged robots (Sources 9 and 18). The official README states that it supports task-space leg and base commands, leg motion in joint and Cartesian space, targets and trajectories, position/velocity/force/torque goals, feedback whole-body control, ROS/C++/Python/YAML, and use cases from teleoperation to autonomous footstep planning.

**Why it matters:** Free Gait is directly relevant to Argus because it looks like the next abstraction above a hand-coded trot: represent actions as base/leg trajectories and feed them into a consistent whole-body layer.

### 6.2 ANYmal dynamic locomotion and WBC

Bellicoso et al. are a representative ANYmal quadruped WBC source (Source 10). The core pattern is to combine high-level gait/trajectory commands with a whole-body controller that respects contacts and robot dynamics.

**Why it matters:** It is a mature classical stack pattern for robot dogs: gait schedule plus body/foot objectives plus WBC, not just IK.

### 6.3 Whole-body nonlinear MPC through contacts

Neunert et al. represent a more aggressive model-based direction: whole-body nonlinear MPC through contacts for quadrupeds (Source 11). Instead of only optimizing centroidal forces, the controller reasons through richer robot/contact dynamics.

**Why it matters:** This is high research value but high implementation complexity. It likely requires a dedicated optimal-control toolchain such as OCS2 and reliable dynamics derivatives.

### 6.4 MIT Cheetah 3 convex MPC

Di Carlo et al. are the representative robot-dog/quadruped convex MPC example (Source 13). The stack uses a reduced-order model predictive controller for dynamic locomotion on MIT Cheetah 3.

**Why it matters:** This is one of the clearest upgrade models for a simulator robot dog: keep a prescribed gait/contact schedule, but replace pure kinematic stance handling with MPC-computed ground reaction forces and a lower-level torque/impedance controller.

### 6.5 Mini Cheetah MPC + whole-body impulse/control

Kim et al. combine MPC force planning with whole-body impulse/control on Mini Cheetah (Source 14). WebFetch extracted that MPC plans long-horizon force targets, the whole-body layer translates them into torque/position/velocity commands, and the system was tested with six gaits, outdoors/treadmill, reaching 3.7 m/s.

**Why it matters:** This is a strong classical/model-based contrast to RL: fast dynamic behavior is possible with engineered MPC/WBC stacks, provided the hardware/control interface supports it.

### 6.6 Perceptive nonlinear MPC for ANYmal

Grandia et al. integrate terrain perception, foothold feasibility, and nonlinear MPC for ANYmal (Source 16). WebFetch verified the stack uses stepability checks, plane fitting, signed-distance fields, local convex foothold constraints, multiple shooting, real-time iteration, and filter-based line search, with hardware validation over gaps, slopes, and stepping stones.

**Why it matters:** This is the model-based rough-terrain endgame: perception is not an add-on; it changes the optimization constraints.

## 7. Implications for Argus

The T4 researcher owns direct code mapping, so this section avoids making unverified claims about current files beyond the plan statement: the plan says Argus currently maps `velocity command -> analytical trot gait -> joint position targets -> MuJoCo position actuators`.

### 7.1 Classification of the current Argus approach

Based on the plan description, Argus is currently in the **analytical gait + IK/position-control** family. That is a valid baseline, but it sits at the low-complexity/low-robustness end of the taxonomy.

**What Argus likely gets right:**

- Interpretable gait timing and foot trajectories.
- Low implementation and compute cost.
- Easy debugging in MuJoCo.
- Good baseline for flat-ground commanded-velocity locomotion.

**What it likely lacks relative to classical research systems:**

- Explicit ground-reaction-force planning.
- Contact wrench/friction constraints.
- Centroidal momentum regulation.
- Whole-body inverse dynamics or QP task arbitration.
- Predictive foothold/contact planning.
- Push recovery or capture/recoverability logic.
- Terrain perception and foothold feasibility constraints.

### 7.2 Recommended classical upgrade ladder

1. **Make the current analytical trot a clean baseline, not the final architecture.** Preserve it as the simplest reproducible controller and regression target.
2. **Add contact-state and metrics instrumentation before adding smarter control.** Measure foot slip, duty factor, base roll/pitch, CoM height, tracking error, contact impulses, and falls. Without this, MPC/WBC improvements are impossible to evaluate.
3. **Introduce a Free Gait-style action abstraction.** Separate commands like base motion, leg swing trajectories, stance behavior, and gait schedule. This prepares the codebase for WBC/MPC without immediately implementing a solver.
4. **Add impedance/force-aware stance control if MuJoCo actuator setup allows it.** A pure position actuator pipeline hides contact-force regulation; WBC/MPC needs torque or at least impedance-style interfaces.
5. **Implement centroidal/convex MPC before full-body NMPC.** For a robot dog, the MIT Cheetah 3 / Mini Cheetah pattern is the most plausible research-value jump: keep gait schedule fixed, compute stance foot forces over a horizon, then map forces to joint torques or impedance targets.
6. **Only pursue full-body nonlinear MPC or contact-implicit trajectory optimization after dynamics/control infrastructure exists.** These are research-grade and solver-heavy; they should not be the first upgrade from analytical trot.
7. **For humanoid expansion, start with LIPM/ZMP/capture-point before whole-body humanoid MPC.** Humanoid balance has a mature reduced-order ladder analogous to quadruped centroidal MPC.

### 7.3 Best-fit near-term Argus research question

A strong near-term classical/model-based research direction is:

> How much robustness does Argus gain by moving from analytical trot + joint-position tracking to analytical trot + centroidal/convex MPC stance-force planning + impedance/torque realization?

This is better scoped than jumping directly to RL or full-body nonlinear MPC. It also creates a clean classical baseline against which the learning-focused researcher can later compare RL/imitation methods.

## 8. Contrast with learning-based locomotion, intentionally brief

Classical/model-based stacks encode physics, contacts, constraints, and tasks explicitly. They usually need less training data and are easier to diagnose, but they require modeling effort, solver tuning, and reliable state/contact estimation.

RL/imitation stacks can learn robust behaviors and exploit simulator scale, but their details are intentionally out of scope for this T1 output. For synthesis, compare them only at the architecture boundary: learning policies often replace or augment the gait planner, foothold selector, or low-level controller; they do not eliminate the need for simulation, metrics, actuator modeling, safety checks, and deployment interfaces.

## 9. Gaps and confidence notes

- IEEE/Springer pages often blocked direct abstract extraction, so several paper details are metadata-verified but method summaries rely on title-level knowledge plus robotics background. The evidence table marks those as medium confidence.
- Crossref verified metadata for the main canonical sources; WebFetch verified stronger content claims for OCS2, Free Gait, Mini Cheetah, and Perceptive NMPC.
- Source 3 was not reliable enough for strong claims and should not be used in the final report unless re-verified.
- No RL/imitation/sim-to-real details are included by design.

## 10. Practical source short list for the lead synthesis

If the final brief can only cite a compact set, use these:

1. Kajita ZMP preview control for classical humanoid walking.
2. Pratt capture point for humanoid push recovery.
3. Herzog momentum/hierarchical inverse dynamics for humanoid WBC.
4. Kuindersma Atlas for full humanoid optimization-based stack.
5. Free Gait for legged robot control architecture.
6. Di Carlo MIT Cheetah 3 for convex MPC quadruped locomotion.
7. Kim Mini Cheetah for MPC + whole-body impulse/control.
8. Grandia ANYmal for perceptive nonlinear MPC.
9. OCS2 for optimal-control/MPC tooling.
10. Patel contact-implicit trajectory optimization for contact planning.
