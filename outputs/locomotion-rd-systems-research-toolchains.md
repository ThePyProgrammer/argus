# Locomotion R&D Systems and Toolchains for Humanoid and Robot Dog Control

**Task:** T3 from `/home/prannayag/pragnition/robotics/argus/outputs/.plans/locomotion-rd-systems.md`
**Scope:** Development infrastructure only: simulators, model formats, middleware, optimization/control libraries, training stacks, evaluation/benchmarking, deployment pipelines. Algorithms are mentioned only where they explain toolchain support.
**Date:** 2026-04-30

## Executive takeaways

1. **The current legged-locomotion R&D split is roughly: MuJoCo for precise, scriptable, lightweight dynamics and benchmarking; Isaac Lab/Isaac Sim for GPU-heavy RL, large asset pipelines, sensors, and sim-to-real workflows; Gazebo/ROS 2/ros2_control for system integration and deployment-like testing; RaiSim for fast contact-rich legged simulation in some academic stacks; Genesis is emerging but should be treated as exploratory until the project needs its specific capabilities.** Evidence: sources [1], [2], [3], [4], [5], [7], [8], [9].
2. **Model-format choice is architectural, not cosmetic.** MJCF is native and richer for MuJoCo; URDF is common in ROS and supported/imported by several tools; USD is the native backbone of Isaac Sim; SDF is central in Gazebo. Conversion works, but high-fidelity actuator, contact, sensor, and material semantics frequently need tool-specific tuning. Evidence: [1], [6], [7], [8], [9], [10], [11].
3. **Modern RL locomotion stacks are converging around vectorized/GPU simulators plus PPO-style libraries and experiment tracking.** legged_gym used Isaac Gym plus `rsl_rl` and is now effectively superseded by Isaac Lab; Isaac Lab integrates `rsl_rl`, `rl_games`, `skrl`, and Stable-Baselines3; MuJoCo MJX/MuJoCo Playground offers JAX/GPU/Warp paths. Evidence: [2], [4], [12], [13], [14], [15], [16], [17], [18].
4. **Classical/model-based control infrastructure remains a separate stack:** Pinocchio for rigid-body dynamics, Crocoddyl for contact-rich trajectory optimization/DDP, Drake for model-based design/verification, CasADi/acados for nonlinear optimization/MPC and embedded solver generation. These are tools to build controllers and planners, not turnkey locomotion products. Evidence: [19], [20], [21], [22], [23].
5. **Argus currently sits in the lightweight MuJoCo + MJCF + analytical position-control lane.** It loads a Unitree Go2 MJCF model, patches torque motors to MuJoCo position actuators, computes a Raibert-style analytical trot from velocity commands, writes 12 joint-position targets to `data.ctrl`, steps MuJoCo, and renders RGB/depth/IMU/ground-truth pose. Evidence: repo sources [R1], [R2], [R3], plus MuJoCo API/model docs [1], [6], [24], [25].

## Numbered sources

### Simulator and model-format sources

[1] MuJoCo overview — https://mujoco.readthedocs.io/en/stable/overview.html
[2] Isaac Lab installation/overview docs — https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html
[3] Gazebo Sim getting started docs — https://gazebosim.org/docs/jetty/get_started/
[4] Genesis overview docs — https://genesis-world.readthedocs.io/en/latest/user_guide/overview/what_is_genesis.html
[5] RaiSim / RSS paper fetch result — https://raisim.com and https://www.roboticsproceedings.org/rss15/p48.pdf
[6] MuJoCo modeling docs — https://mujoco.readthedocs.io/en/stable/modeling.html
[7] ROS 2 URDF tutorial — https://docs.ros.org/en/rolling/Tutorials/Intermediate/URDF/URDF-Main.html
[8] OpenUSD introduction — https://openusd.org/26.05/
[9] Isaac Sim docs index/importer/USD references — https://docs.isaacsim.omniverse.nvidia.com/latest/index.html, https://docs.nvidia.com/isaac-sim/importer_exporter/importers_exporters.html, https://docs.nvidia.com/isaac-sim/omniverse_usd/open_usd.html, https://docs.nvidia.com/isaac-sim/assets/usd_assets_robots.html
[10] MuJoCo XML actuator position reference — https://mujoco.readthedocs.io/en/stable/XMLreference.html#actuator-position
[11] MuJoCo API types reference — https://mujoco.readthedocs.io/en/stable/APIreference/APItypes.html

### Middleware, training, and benchmarking sources

[12] ros2_control getting started — https://control.ros.org/rolling/doc/getting_started/getting_started.html
[13] ros2_control package docs fetch result — https://docs.ros.org/en/jazzy/p/index.html
[14] legged_gym project site and paper — https://leggedrobotics.github.io/legged_gym/ and https://arxiv.org/abs/2109.11978
[15] legged_gym GitHub README — https://github.com/leggedrobotics/legged_gym
[16] rsl_rl GitHub README — https://github.com/leggedrobotics/rsl_rl
[17] Humanoid-Gym GitHub README — https://github.com/roboterax/humanoid-gym
[18] Isaac Lab environments/RL docs fetch results — https://github.com/isaac-sim/IsaacLab/blob/main/docs/source/overview/environments.rst and https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/index.html
[19] MuJoCo MJX docs — https://mujoco.readthedocs.io/en/stable/mjx.html
[20] MuJoCo Playground GitHub README — https://github.com/google-deepmind/mujoco_playground
[21] Stable-Baselines3 docs — https://stable-baselines3.readthedocs.io/
[22] Gymnasium Env API — https://gymnasium.farama.org/api/env/
[23] RLlib docs — https://docs.ray.io/en/latest/rllib/
[24] Weights & Biases experiment tracking — https://wandb.ai/site/experiment-tracking/

### Optimization/control infrastructure sources

[25] Pinocchio GitHub README — https://github.com/stack-of-tasks/pinocchio
[26] Crocoddyl GitHub README — https://github.com/loco-3d/crocoddyl
[27] Drake homepage — https://drake.mit.edu
[28] CasADi homepage — https://web.casadi.org/
[29] acados docs — https://docs.acados.org/

### Argus repository sources read directly

[R1] `/home/prannayag/pragnition/robotics/argus/pyproject.toml`
[R2] `/home/prannayag/pragnition/robotics/argus/src/bridge/sim_bridge.py`
[R3] `/home/prannayag/pragnition/robotics/argus/src/locomotion/xml_patcher.py`
[R4] `/home/prannayag/pragnition/robotics/argus/src/locomotion/gait_controller.py`

## Evidence table

| Claim | Evidence | Confidence |
|---|---|---:|
| MuJoCo is a general-purpose physics engine aimed at fast, accurate articulated-system simulation for robotics/ML, with Python bindings over the C API. | MuJoCo overview and Python docs: [1], [24]. | High |
| MuJoCo’s native XML model format is MJCF; it can also load URDF, but URDF is more limited than MJCF. | MuJoCo modeling docs: [6]. | High |
| MuJoCo supports `MjModel.from_xml_string`, `MjData`, and `mj_step`; this matches Argus’s current simulation bridge style. | MuJoCo Python docs [24]; Argus bridge [R2]. | High |
| MuJoCo position actuators are a documented actuator shortcut with servo gains such as `kp`/`kv`; Argus patches Go2 `<motor>` actuators into `<position>` actuators. | MuJoCo XML reference [10]; Argus XML patcher [R3]. | High |
| Isaac Lab is built on Isaac Sim and targets robotics RL/imitation learning workflows, with high workstation requirements and NVIDIA GPU assumptions. | Isaac Lab install docs [2]. | High |
| Isaac Lab includes locomotion environments and integrates RL libraries including `rl_games`, `rsl_rl`, `skrl`, and `sb3`. | Isaac Lab environments/RL docs [18]. | Medium-High |
| Isaac Sim uses USD as its core/unifying data format and supports robot asset import from URDF and MJCF. | Isaac Sim docs fetch result [9]; OpenUSD intro [8]. | High |
| Gazebo Sim is a 3D robotics simulator with SDF-centered worlds and ROS-facing workflows. | Gazebo docs [3]. | High |
| ROS 2 URDF docs present URDF as the XML robot geometry/organization format in ROS. | ROS 2 URDF tutorial [7]. | High |
| ros2_control provides a controller-manager/resource-manager/hardware-abstraction framework for real robot control in ROS 2. | ros2_control docs [12], [13]. | High |
| legged_gym is an Isaac Gym locomotion setup for legged robots; its README says support is limited and work moved toward Isaac Lab after Isaac Gym to Isaac Sim transition. | legged_gym site/README [14], [15]. | High |
| legged_gym reports fast GPU-parallel training and sim-to-real transfer to ANYmal; use this as historical evidence for the toolchain style, not as a universal benchmark. | legged_gym project/paper [14]. | Medium-High |
| rsl_rl is a compact GPU-accelerated robotics RL library with PPO and student-teacher distillation, used by Isaac Lab and Legged Gym. | rsl_rl README [16]. | High |
| Humanoid-Gym is an Isaac Gym humanoid locomotion RL framework with MuJoCo sim-to-sim validation/export paths and reported RobotEra XBot validation. | Humanoid-Gym README [17]. | Medium-High |
| MuJoCo MJX supports JAX/XLA accelerator execution, batch dimensions, `vmap`/`jit`, and humanoid/quadruped locomotion tutorial material; it has feature/performance caveats. | MJX docs [19]. | High |
| MuJoCo Playground is a DeepMind robot-learning suite using MuJoCo MJX, with quadruped/biped locomotion tasks and CLI PPO training paths. | MuJoCo Playground README [20]. | High |
| Stable-Baselines3 is a PyTorch RL algorithm library with PPO/SAC/TD3/etc.; it is useful for Gym-style pipelines but not documented here as a legged-robot-specific massive-GPU simulator stack. | SB3 docs [21]. | High for feature list; Medium for robotics suitability comparison. |
| Gymnasium provides the standard `reset`/`step` Env API, action/observation spaces, terminated/truncated separation, and `info` for metrics/debugging. | Gymnasium Env API [22]. | High |
| RLlib is relevant when distributed, multi-agent, offline, or externally connected simulator training becomes important. | RLlib docs [23]. | High |
| W&B is relevant for RL training operations because it logs metrics, configs, artifacts/checkpoints, git state, and supports run comparison. | W&B docs [24]. | High |
| Pinocchio provides rigid-body dynamics, kinematics, derivatives, and supports URDF/SDF/MJCF/SRDF; it is suited for control/optimization/planning infrastructure. | Pinocchio README [25]. | High |
| Crocoddyl is an optimal-control/DDP library for robot control under contact sequences and relies on Pinocchio. | Crocoddyl README [26]. | High |
| Drake is a C++/Python toolbox for model-based design, verification, multibody dynamics, mathematical programming, and contact/friction simulation. | Drake homepage [27]. | High |
| CasADi and acados fit nonlinear optimization/MPC workflows; acados emphasizes embedded fast solvers and code generation. | CasADi [28], acados [29]. | High |
| Argus currently depends on `mujoco>=3.0.0` and has no ROS 2, Isaac, Pinocchio, Crocoddyl, Drake, rsl_rl, or Gymnasium dependency in `pyproject.toml`. | Argus `pyproject.toml` [R1]. | High |
| Argus current locomotion path is velocity command → analytical trot gait → 12 joint position targets → MuJoCo `data.ctrl` → `mj_step`. | Argus bridge/gait/XML patcher [R2], [R3], [R4]. | High |

## Categories

### 1. Simulators

#### MuJoCo

**Best fit:** Lightweight research simulator, model-level debugging, deterministic-ish scriptable experiments, contact-rich articulated simulation, Python-first control loops, and MJCF model control.
**Evidence:** MuJoCo is documented as a fast/accurate articulated-system physics engine with C/Python APIs, `MjModel`/`MjData`, Python bindings, offscreen rendering, and support for parallel sampling through multiple `mjData` instances [1], [24]. MJCF is native and URDF import exists but is more limited [6]. MJX provides JAX/XLA/GPU-accelerated batched simulation and tutorial material for humanoid/quadruped locomotion, but with limitations around unsupported features, single-scene speed, contacts/meshes, and MJX-Warp autodiff [19].

**Locomotion R&D role:**
- Rapid controller iteration: analytical gait, IK, MPC loop prototypes, policy rollouts.
- Asset control: MJCF exposes MuJoCo-specific actuator/contact/tendon/sensor semantics better than URDF.
- Evaluation: easier to create repeatable scripted benchmarks and log state trajectories.
- Training: MJX/MuJoCo Playground can move MuJoCo into GPU RL territory, but this is a different architecture from the classic Python `mj_step` loop.

**Pitfalls:**
- URDF import is not equivalent to MJCF-native modeling [6].
- Converting torque motors to position actuators changes the control problem: the controller is then commanding servo targets, not direct torque.
- MJX support is not full MuJoCo feature parity; models with many contacts or meshes can degrade performance [19].

#### Isaac Gym / Isaac Lab / Isaac Sim

**Best fit:** GPU-parallel RL, large-scale domain randomization, sensor/asset-rich embodied AI, and sim-to-real-oriented training pipelines.
**Evidence:** Isaac Lab is built on Isaac Sim, requires Isaac Sim first, and its docs emphasize robotics RL/imitation learning, environments, sensors, controllers, training, and inference [2]. Isaac Lab environment docs include locomotion and integrations for `rl_games`, `rsl_rl`, `skrl`, and `sb3` [18]. Isaac Sim uses USD as the core/unifying data format and imports URDF/MJCF robot assets [9].

**Locomotion R&D role:**
- Preferred when the research objective is learning locomotion policies at scale.
- Better fit than plain MuJoCo when the experiment needs thousands of environments, GPU physics/rendering, procedural scenes, or Isaac-native assets.
- Stronger bridge to NVIDIA robotics ecosystem and Omniverse/USD pipelines.

**Pitfalls:**
- Heavier machine requirements: Isaac Lab docs list Ubuntu 22.04/Windows 11, 32+ GB RAM, 16+ GB VRAM, and NVIDIA driver constraints [2].
- Isaac Gym-era repos such as legged_gym are historically important but not the future-proof base; legged_gym README says support is limited and migration moved toward Isaac Lab [15].
- USD/Isaac asset fidelity may diverge from MJCF; conversion requires validation of joint limits, actuation, contacts, sensors, and inertias.

#### RaiSim

**Best fit:** Fast rigid-body/contact simulation in academic legged robotics pipelines, especially where prior RaiSim assets/environments exist.
**Evidence:** The RSS paper/source fetch describes RaiSim as a robotics/robot-learning physics engine for rigid-body dynamics with strong contact handling and faster-than-real-time use in legged robotics [5].

**Locomotion R&D role:**
- Useful for contact-rich robot-learning experiments and repeated rollouts.
- Less central than MuJoCo/Isaac for Argus because Argus already has MuJoCo assets and Python simulation bridge.

**Pitfalls:**
- Ecosystem gravity for new legged RL work has shifted heavily toward Isaac Lab and MuJoCo MJX/MuJoCo Playground; choose RaiSim only for a concrete reason such as existing benchmark compatibility or known model support.

#### Gazebo Sim

**Best fit:** ROS-facing robot integration, SDF worlds, sensor/system simulation, and deployment-like middleware testing.
**Evidence:** Gazebo Sim docs describe a 3D robotics simulator, SDF examples/worlds, server/GUI modes, and ROS/Gazebo installation guidance [3].

**Locomotion R&D role:**
- More useful for integration tests and ROS 2 stacks than for fast policy training.
- Good candidate once Argus has ROS 2 nodes, hardware abstractions, or deployment orchestration to test.

**Pitfalls:**
- Do not treat Gazebo as a drop-in replacement for Isaac/MuJoCo RL training throughput.
- SDF/URDF/Gazebo plugins introduce another model semantics layer.

#### Genesis

**Best fit:** Exploratory emerging simulator/data-generation platform.
**Evidence:** Genesis docs describe a robotics/embodied AI/physical AI platform with a universal physics engine, rendering, and generative data engine [4]. The fetched overview did not provide enough detail on locomotion benchmarks, model formats, differentiability, or deployment maturity.

**Locomotion R&D role:**
- Watchlist/experimental, not the primary recommended Argus migration path today.

**Pitfalls:**
- Treat claims as lower confidence until validated on Argus-like quadruped locomotion, assets, and training workloads.

### 2. Model formats and asset pipelines

| Format | Primary ecosystem | Strengths | Weak spots / migration notes | Evidence |
|---|---|---|---|---|
| MJCF | MuJoCo | Rich MuJoCo-native modeling; actuators, contacts, tendons, sensors, compiler conveniences; current Argus Go2 models are MJCF. | Less native to ROS deployment; conversion to URDF/USD needs validation. | [6], [10], [R2], [R3] |
| URDF | ROS 2, ros2_control, broad robotics interchange | Common robot structure/geometry format in ROS; imported by MuJoCo/Isaac; useful for robot_state_publisher/tf/control stacks. | Limited for full physics/contact/control semantics; MuJoCo docs explicitly call URDF more limited than MJCF. | [6], [7], [9], [12] |
| USD | Isaac Sim / Omniverse | Native/unifying scene and asset format in Isaac Sim; strong scene composition, layering, asset assembly. | Not a rigging/control format by itself; robot dynamics/import details need Isaac-specific validation. | [8], [9] |
| SDF | Gazebo Sim | World/scene format for Gazebo; good for simulation worlds, sensors, plugins. | Different semantics from MJCF/URDF; not Argus-native today. | [3] |
| MJB | MuJoCo compiled binary | Faster standalone load of compiled MuJoCo models. | Less editable/human-readable; not the source-of-truth model. | [6] |

**Practical rule:** keep a canonical source model per simulator instead of assuming perfect round-trip conversion. For Argus today, that canonical source is MJCF. If Argus adds ROS 2/ros2_control, a URDF/xacro model becomes necessary. If Argus adds Isaac Lab, USD becomes the runtime asset backbone even if import starts from MJCF/URDF.

### 3. Control middleware and deployment infrastructure

#### ROS 2

The accessible ROS 2 concept fetch failed on one URL, but the ROS/URDF and ros2_control docs were accessible. For this task’s toolchain scope, the relevant verified facts are:
- URDF is the XML robot-description format used in ROS tutorials for robot geometry and organization [7].
- ros2_control is the ROS 2 robot-control framework for real-time robot control and hardware integration [12], [13].

#### ros2_control

**Best fit:** Moving from simulator-only control loops to hardware-like control interfaces.
**Evidence:** ros2_control docs describe a controller manager that loads/activates/deactivates controllers, a resource manager that abstracts hardware components/plugins and read/write communication, and controller plugins that use state feedback to compute command outputs. Robot bringup uses controller YAML, `<ros2_control>` tags in URDF/xacro, and launch files [12].

**Locomotion R&D role:**
- Defines a seam between high-level policy/controller and low-level actuator interfaces.
- Lets the same controller architecture target simulation and hardware adapters.
- Works naturally with joint trajectory, forward command, differential drive, and custom controllers [13].

**Pitfalls:**
- Adding ros2_control is not just adding a Python dependency. It requires URDF/xacro with `<ros2_control>` tags, controller configs, hardware-interface plugins, launch files, and timing/real-time discipline [12].
- It does not solve locomotion by itself; it standardizes the control plumbing.

### 4. Optimization and model-based-control libraries

| Library | Toolchain role | Best use in locomotion R&D | Evidence |
|---|---|---|---|
| Pinocchio | Rigid-body dynamics, kinematics, analytical derivatives, contact/closed-loop support; C++ with Python interface. | Dynamics engine for whole-body control, trajectory optimization, inverse dynamics, centroidal dynamics, and model-based planners. | [25] |
| Crocoddyl | Contact-sequence optimal control / DDP-style solvers; uses Pinocchio. | Trajectory optimization, MPC-style prototyping, multi-contact locomotion motion generation. | [26] |
| Drake | Model-based design/verification, multibody dynamics, mathematical programming, contact/friction simulation. | Verification, optimization-heavy controllers, planning/control prototyping, formal-ish analysis. | [27] |
| CasADi | Symbolic/algorithmic differentiation and nonlinear optimization; standalone C export. | NMPC/trajectory optimization prototyping, gradients/Jacobians/Hessians. | [28] |
| acados | Fast embedded OCP/MPC/MHE solvers with code generation. | Real-time MPC on embedded or near-real-time platforms once model/control formulation is settled. | [29] |

**Practical rule:** Pinocchio/Crocoddyl/CasADi/acados/Drake are not substitutes for MuJoCo or Isaac. They usually sit beside a simulator: the simulator supplies rollouts/sensors/contact validation; the optimization library supplies dynamics derivatives, trajectories, feedback gains, or real-time MPC solvers.

### 5. Training stacks

#### legged_gym

**Status:** historically important, not the safest new foundation.
**Evidence:** legged_gym is an Isaac Gym environment suite for legged robots, with ANYmal and other robots; the project reports GPU-parallel fast training and sim-to-real transfer to ANYmal [14]. The GitHub README says work moved to Isaac Lab after Isaac Gym to Isaac Sim, and the repo now receives limited updates/support [15].

**Use when:** reproducing older papers, comparing against existing legged_gym baselines, or porting an older Isaac Gym stack.

**Do not use as the primary greenfield path** unless compatibility with an existing legged_gym baseline is the research requirement.

#### Isaac Lab + rsl_rl / rl_games / skrl / sb3

**Status:** current NVIDIA-centered robot-learning stack.
**Evidence:** Isaac Lab docs list locomotion environments, manager/direct workflows, play/inference variants, and RL integrations with `rl_games`, `rsl_rl`, `skrl`, and `sb3` [18]. `rsl_rl` is a compact GPU-accelerated robotics RL library with PPO and student-teacher distillation, used by Isaac Lab and Legged Gym [16].

**Use when:** training quadruped/humanoid policies at scale, domain randomization, sim-to-real prep, GPU-rich experiments, or Isaac/Omniverse assets are central.

#### Humanoid-Gym

**Status:** useful reference for humanoid-specific Isaac Gym-style workflows, not directly a robot-dog stack.
**Evidence:** Humanoid-Gym is an RL framework for humanoid locomotion, uses Isaac Gym for training, exports policies, and validates via MuJoCo sim-to-sim with real-world RobotEra XBot examples claimed in the README [17].

**Use when:** studying humanoid training/deployment workflow patterns, policy export, and sim-to-sim validation.

#### MuJoCo MJX + MuJoCo Playground

**Status:** promising MuJoCo-native GPU RL path.
**Evidence:** MJX gives JAX/XLA accelerator execution, batched `mjx.Model`/`mjx.Data`, `vmap`/`jit`, and tutorial material for humanoid/quadruped locomotion [19]. MuJoCo Playground is a DeepMind suite for GPU-accelerated robot learning and sim-to-real transfer using MuJoCo MJX, with quadruped/biped locomotion tasks and PPO CLI training examples [20].

**Use when:** Argus wants to stay in MuJoCo/MJCF while adding high-throughput learning. This is likely the lowest model-format disruption route compared with Isaac Lab, but it may still require adapting Argus’s model/control to MJX-supported features.

#### Stable-Baselines3, Gymnasium, RLlib

**SB3:** PyTorch implementations of common RL algorithms including PPO/SAC/TD3; useful for standard Gym-style experiments, smaller CPU/vectorized runs, baselines, and education [21].
**Gymnasium:** de facto Env API standard: `reset` returns observation/info; `step` returns observation, reward, terminated, truncated, info; spaces define action/observation validity; `info` can carry metrics/debug data [22].
**RLlib:** distributed/multi-agent/offline/externally connected simulator stack, useful when training moves beyond single-process/single-workstation pipelines [23].

**Practical rule:** expose Argus locomotion tasks through a Gymnasium-compatible environment before committing to a learning library. That keeps SB3, RLlib, rsl_rl wrappers, and custom evaluators reachable.

### 6. Evaluation, benchmarking, and experiment operations

A credible locomotion R&D pipeline needs more than a simulator. It needs repeatable evaluation and failure analysis:

| Layer | Standard tool/pattern | Why it matters | Evidence |
|---|---|---|---|
| Env API | Gymnasium `reset`/`step`, spaces, terminated/truncated, `info` metrics | Lets training/evaluation code share a consistent contract. | [22] |
| Run tracking | W&B or equivalent | Logs reward curves, stability metrics, configs, checkpoints/artifacts, git state, comparisons. | [24] |
| Baseline libraries | SB3 / rsl_rl / RLlib depending on scale | Avoids hand-rolling PPO/SAC/distributed training. | [16], [18], [21], [23] |
| Simulator seed/config management | Explicit simulator seeds, domain-randomization configs, model hashes | Needed for reproducibility and regression detection. | Inferred from Env API/experiment tracking docs [22], [24]; implementation-specific. |
| Locomotion metrics | distance traveled, commanded-vs-actual velocity, energy/torque proxy, falls, foot clearance/contact timing, orientation stability, recovery time | Converts “it walks” demos into comparable R&D data. | Metric list is an engineering synthesis; verify per final benchmark definition. |
| Sim-to-sim validation | Train in one sim, test in another, e.g. Humanoid-Gym Isaac Gym training then MuJoCo validation | Catches overfitting to one simulator’s contact/actuation quirks. | [17] |
| Sim-to-real readiness | Domain randomization, actuator/sensor latency/noise, hardware interface, policy export | Required before hardware transfer; tooling supports it but does not guarantee it. | [14], [16], [18], [20] |

## Practical comparison

| Toolchain | Primary value | Locomotion maturity | Setup burden | Model format center | Best Argus use | Main risk |
|---|---|---:|---:|---|---|---|
| Current Argus MuJoCo Python loop | Simple, inspectable, lightweight simulation and perception integration. | Medium for scripted quadruped gait; low for advanced locomotion research. | Low | MJCF | Keep as baseline and evaluation harness. | Position-servo analytical gait hides torque/contact-control problems. |
| MuJoCo + Gymnasium + SB3 | Standard RL baselines with modest integration cost. | Medium for simple tasks; lower throughput than GPU-native stacks. | Low-Medium | MJCF/Gym Env | First learning baseline/prototyping step. | May bottleneck on CPU/Python stepping; SB3 not legged-specific. |
| MuJoCo MJX + MuJoCo Playground | MuJoCo-native high-throughput GPU RL. | Medium-High and improving. | Medium | MJCF/MJX-supported subset | Best “stay in MuJoCo but learn policies” path. | MJX feature limitations and model adaptation work. |
| Isaac Lab + rsl_rl/skrl/rl_games | Current large-scale robot-learning stack. | High for locomotion training workflows. | High | USD runtime, imports URDF/MJCF | Best serious RL/sim-to-real path if NVIDIA GPU resources are available. | Heavy dependency stack, asset conversion, GPU/driver constraints. |
| Gazebo + ROS 2 + ros2_control | Deployment-like integration and hardware abstraction. | High for robotics integration, not high-throughput training. | High | URDF/xacro + SDF | Best path toward hardware/controller architecture. | Does not solve gait/RL; introduces ROS complexity. |
| Pinocchio + Crocoddyl | Model-based dynamics/trajectory optimization. | High for model-based control research infrastructure. | Medium-High | URDF/SDF/MJCF support through Pinocchio | Add WBC/MPC/trajectory-optimization research path. | Requires strong dynamics/control formulation; not turnkey. |
| Drake | Optimization, verification, multibody modeling. | Medium for locomotion stack integration; high for model-based analysis. | Medium-High | Drake parser ecosystem | Use for verification/planning experiments, not first Argus upgrade. | Integration overhead relative to current MuJoCo loop. |
| CasADi + acados | NMPC/OCP prototyping and embedded solver generation. | High for MPC infrastructure if model is formulated. | Medium-High | Problem formulation, not robot asset format | Later MPC path after dynamics abstraction exists. | Premature until Argus defines state/control/constraints rigorously. |
| RaiSim | Fast contact simulation in some legged-learning stacks. | Medium-High historically/academically. | Medium | RaiSim assets | Only if reproducing RaiSim-based work. | Less aligned with current Argus assets and newer ecosystem center. |
| Genesis | Emerging embodied-AI simulator/data-generation platform. | Unknown for Argus-like locomotion from checked docs. | Unknown | Not established from fetched docs | Watchlist only. | Maturity/benchmark uncertainty. |

## Where Argus currently sits

### Current Argus stack observed in repository

- `pyproject.toml` declares `mujoco>=3.0.0`, Open3D, Rerun, evo, NumPy/SciPy/OpenCV, ZMQ/msgpack, and optional perception/web/dev dependencies. It does **not** declare Isaac, ROS 2, ros2_control, Pinocchio, Crocoddyl, Drake, CasADi, acados, rsl_rl, Gymnasium, RLlib, or Stable-Baselines3 [R1].
- `src/bridge/sim_bridge.py` loads a Unitree Go2 model from `models/unitree_go2`, patches it, constructs `mujoco.MjModel.from_xml_string(...)` and `mujoco.MjData(...)`, then advances with `mujoco.mj_step(...)` [R2].
- The bridge returns RGB/depth via MuJoCo rendering, IMU readings when sensors exist, and ground-truth camera pose from MuJoCo state [R2].
- `src/locomotion/xml_patcher.py` converts upstream Go2 MJCF `<motor>` actuators into MuJoCo `<position>` actuators with `kp`/`kv`, removes `ctrlrange`, adds a floor/light/camera/visual depth settings, and does not modify the source XML on disk [R3]. MuJoCo documents position actuators with `kp`/`kv` servo-tuning fields [10].
- `src/locomotion/gait_controller.py` implements a Raibert-style analytical trot that maps `(vx, vy, omega, dt)` to 12 joint position targets, using diagonal leg pairs FL+RR and FR+RL and differential stride for turning [R4].
- `MuJoCoBridge.step()` either accepts an explicit 12-element action or calls `_velocity_to_ctrl()`, writes the result to `self._data.ctrl[:]`, steps physics for `sim_steps_per_frame`, and captures a sensor frame [R2].

### Position in the landscape

Argus is currently a **MuJoCo/MJCF scripted quadruped simulation harness**, not an RL training stack, not a ROS deployment stack, and not a model-based whole-body-control stack. Its strengths are low setup burden, code clarity, direct access to MuJoCo state/rendering, and suitability for perception/exploration pipeline experiments. Its limitations for locomotion R&D are that locomotion is hard-coded as a position-servo trot, there is no standard RL environment API, no policy-training pipeline, no model-based dynamics/optimization layer, no hardware abstraction, and no formal locomotion benchmark suite beyond existing tests.

## Migration / upgrade implications for Argus

### Upgrade path A: Formalize current MuJoCo locomotion as a benchmarkable Gymnasium environment

**What changes:**
- Add an `ArgusGo2Env` or similar Gymnasium-compatible environment around `MuJoCoBridge`.
- Define observation space, action space, reward/metric outputs, termination/truncation, seeds, and reset options using Gymnasium semantics [22].
- Preserve current analytical trot as a baseline controller and/or action wrapper.
- Add evaluation metrics: commanded-vs-actual velocity, fall rate, distance, body orientation stability, contact timing proxy, energy/actuation proxy, stuck detection, and sim wall-clock speed.

**Why first:**
- Lowest disruption.
- Creates a shared contract for SB3/RLlib/custom evaluation/MuJoCo Playground-style wrappers.
- Makes Argus results comparable before introducing heavier infrastructure.

**Risks:**
- If action remains joint positions through MuJoCo position actuators, learned/control results are not equivalent to torque-control locomotion.
- Python stepping may not support high-throughput RL.

**Research value:** Medium.
**Implementation complexity:** Low-Medium.
**System risk:** Low.

### Upgrade path B: MuJoCo MJX / MuJoCo Playground learning path

**What changes:**
- Port or adapt the Go2 MJCF and task definition to MJX-compatible features.
- Use MuJoCo Playground patterns for PPO training and batched GPU rollouts [19], [20].
- Keep Argus classic MuJoCo bridge as validation/evaluation/sensor pipeline, while training may run in a separate MJX-compatible environment.

**Why:**
- Keeps MuJoCo/MJCF as the center of gravity.
- Avoids immediate USD/Isaac migration.
- Gives a credible high-throughput learning path for quadruped control.

**Risks:**
- MJX does not support every MuJoCo feature; MJX-JAX can be slower for single scenes and degrade with many contacts/mesh collisions; MJX-Warp lacks automatic differentiation per docs [19].
- Requires separating training-time environment from Argus’s current sensor/perception bridge.

**Research value:** High.
**Implementation complexity:** Medium.
**System risk:** Medium.

### Upgrade path C: Isaac Lab training stack

**What changes:**
- Convert/import Go2 assets into Isaac Sim/USD pipeline; validate inertias, joint axes, actuator behavior, contacts, sensors, and control rates [9].
- Build Isaac Lab locomotion task configs and train with `rsl_rl`, `rl_games`, `skrl`, or `sb3` [16], [18].
- Add experiment tracking and policy export/inference validation.

**Why:**
- Best aligned with current NVIDIA-centered legged RL ecosystem.
- Mature workflows for large-scale training, domain randomization, and sim-to-real-style policy development.

**Risks:**
- Heavy GPU/driver/Isaac requirements [2].
- Asset/control semantics change from MuJoCo MJCF to Isaac/USD.
- Could pull Argus away from its current perception/exploration priorities.

**Research value:** Very High for RL locomotion.
**Implementation complexity:** High.
**System risk:** High.

### Upgrade path D: ROS 2 + ros2_control deployment architecture

**What changes:**
- Create URDF/xacro for Go2 with `<ros2_control>` tags [12].
- Add controller YAML, controller-manager launch, hardware/sim interface plugins, and ROS 2 message/action boundaries.
- Treat Argus high-level navigation/exploration outputs as commands to a controller stack rather than direct MuJoCo writes.

**Why:**
- Necessary if Argus is moving toward hardware realism, modular robot middleware, multi-process deployment, or compatibility with external ROS tooling.

**Risks:**
- Does not improve locomotion quality by itself.
- Requires a real-time/timing/control-interface discipline not present in the current simple Python bridge.

**Research value:** Medium-High for deployment architecture.
**Implementation complexity:** High.
**System risk:** Medium-High.

### Upgrade path E: Model-based dynamics/optimization layer

**What changes:**
- Add Pinocchio model loading/dynamics and optionally Crocoddyl, CasADi, acados, or Drake for trajectory optimization/MPC/WBC research [25], [26], [27], [28], [29].
- Define state/control vectors, contact schedule representation, constraints, cost terms, and simulation validation against MuJoCo.

**Why:**
- Enables research beyond hand-coded gait: inverse dynamics, whole-body control, trajectory optimization, MPC, contact-planning experiments.

**Risks:**
- Large conceptual jump; requires controller math and model consistency.
- Needs careful mapping between MuJoCo MJCF actuation/contact and the optimization model.

**Research value:** High for model-based locomotion.
**Implementation complexity:** High.
**System risk:** Medium.

## Recommendations for Argus sequencing

1. **Do not start by replacing MuJoCo.** Argus already has working MJCF assets and a clear MuJoCo bridge [R1], [R2]. Keep it as the baseline simulator/evaluation harness.
2. **First add a benchmark/environment boundary.** A Gymnasium-style wrapper plus metrics makes every later path easier: SB3 baseline, MJX port, Isaac comparison, or model-based controller evaluation [22].
3. **Keep the analytical trot as a baseline, not the endpoint.** It is useful as a deterministic smoke-test controller, but it should be measured against learned/model-based alternatives once the evaluation harness exists [R4].
4. **If the next goal is learning:** choose MuJoCo MJX/MuJoCo Playground first if staying close to Argus assets matters; choose Isaac Lab if GPU-scale sim-to-real locomotion is the primary research deliverable and hardware requirements are acceptable [18], [19], [20].
5. **If the next goal is deployment architecture:** add ROS 2/ros2_control only after defining which controller abstraction Argus needs, because ros2_control standardizes plumbing but does not provide locomotion intelligence [12], [13].
6. **If the next goal is advanced model-based control:** add Pinocchio first, then Crocoddyl/CasADi/acados depending on whether the chosen control formulation is DDP/contact trajectory optimization or NMPC/OCP [25], [26], [28], [29].

## Gaps and caveats

- The ROS 2 general concepts page fetch failed for one URL, so this report relies on accessible ROS URDF and ros2_control docs for ROS-related claims [7], [12], [13].
- The RaiSim official site fetch was limited; evidence comes from the accessible RSS paper fetch and should be strengthened if RaiSim becomes a serious candidate [5].
- Genesis documentation fetched was high-level; no detailed locomotion benchmark/toolchain recommendation should be made from it yet [4].
- This report did not benchmark runtime speed on the local machine. Throughput claims are sourced from docs/papers/project pages, not reproduced locally.
- This report intentionally does not deeply survey locomotion algorithms; it maps the infrastructure those algorithms commonly require.
