# Research Plan: Locomotion R&D systems for humanoid and robot dog control

## Questions
1. What are the major families of locomotion control systems used in current humanoid and quadruped research and development?
2. How do classical/analytical controllers, whole-body control, MPC, trajectory optimization, reinforcement learning, imitation learning, sim-to-real pipelines, and hybrid stacks differ in assumptions, data needs, compute cost, robustness, and deployability?
3. What development systems and toolchains are commonly used for locomotion R&D: simulators, model formats, policy training stacks, optimization frameworks, hardware abstraction layers, and evaluation pipelines?
4. What are representative examples from humanoid and quadruped systems, especially robot dogs, and what evidence supports their performance or limitations?
5. How does Argus's current method map into this landscape: velocity command -> analytical trot gait -> joint position targets -> MuJoCo position actuators?
6. What upgrade paths are plausible for Argus, and what tradeoffs would each introduce for research value, implementation complexity, and system risk?

## Strategy
- Use 4 parallel researcher tracks because this is a broad, multi-domain survey spanning robotics control theory, learning-based locomotion, practical R&D toolchains, and Argus-specific comparison.
- Researcher T1: Classical and model-based locomotion systems for quadrupeds/humanoids: analytical gaits, inverse kinematics, whole-body control, MPC, trajectory optimization.
- Researcher T2: Learning-based locomotion systems: RL, imitation learning, teacher-student/distillation, sim-to-real, domain randomization, real-world adaptation.
- Researcher T3: R&D infrastructure: MuJoCo, Isaac Gym/Lab, RaiSim, Genesis/ManiSkill if relevant, ROS 2/control, Pinocchio/Crocoddyl, policy deployment, benchmarks and metrics.
- Researcher T4: Argus code comparison: read current repo implementation and map it against the above methods, including exact files/classes and architectural seams for upgrade paths.
- Actual rounds: 1 broad parallel round. No follow-up round required; gaps were acceptable and final report labels weaker areas.

## Acceptance Criteria
- [x] All key questions answered with >=2 independent sources where claims are critical.
- [x] At least 3 humanoid examples and 3 quadruped/robot-dog examples covered.
- [x] Both non-learning and learning-based locomotion families are compared.
- [x] R&D systems/toolchains are mapped separately from control algorithms.
- [x] Argus's current implementation is grounded in direct code references.
- [x] Contradictions or contested claims are identified and addressed.
- [x] No single-source claims on critical findings.
- [x] Upgrade paths for Argus are ranked by implementation complexity and research value.

## Task Ledger
| ID | Owner | Task | Status | Output |
|---|---|---|---|---|
| T1 | researcher | Survey classical/model-based locomotion methods for humanoids and quadrupeds | done | outputs/locomotion-rd-systems-research-classical.md |
| T2 | researcher | Survey learning-based locomotion methods and sim-to-real pipelines | done | outputs/locomotion-rd-systems-research-learning.md |
| T3 | researcher | Survey locomotion R&D toolchains, simulators, middleware, and evaluation systems | done | outputs/locomotion-rd-systems-research-toolchains.md |
| T4 | researcher | Map Argus current locomotion implementation to method families and extension seams | done | outputs/locomotion-rd-systems-research-argus.md |
| T5 | lead | Evaluate round 1, identify gaps, and decide whether follow-up is needed | done | No follow-up required; citation verification narrowed final source set |
| T6 | lead | Write draft research brief with claim sweep | in_progress | outputs/.drafts/locomotion-rd-systems-draft.md |
| T7 | lead | Verify citations and produce final report/provenance | in_progress | outputs/locomotion-rd-systems.md; outputs/locomotion-rd-systems.provenance.md |

## Verification Log
| Item | Method | Status | Evidence |
|---|---|---|---|
| Argus locomotion pipeline description | Direct code read and cross-reference | pass | T4 output; `src/locomotion/gait_controller.py`; `src/locomotion/gait_params.py`; `src/locomotion/xml_patcher.py`; `src/bridge/multi_bridge.py`; `src/control/waypoint_runner.py` |
| Analytical gait vs MPC/RL classification | Cross-source comparison | pass | T1/T2/T4 outputs |
| Claims about whole-body control/MPC use in humanoids/quadrupeds | Source cross-read plus DOI redirect checks | pass with notes | T1 output; DOI redirects verified; some IEEE/Springer pages blocked direct content fetch |
| Claims about RL/sim-to-real methods | arXiv/source page verification | pass | Tan 2018, Hwangbo 2019, Lee 2020, Rudin 2021, RMA 2021, Miki 2022, Xie 2018, Siekmann 2020/2021, Humanoid-Gym 2024, HumanPlus 2024, Radosavovic 2024 |
| Toolchain landscape | Docs/project page verification | pass | MuJoCo docs, MJX docs, MuJoCo Playground, Isaac Lab, legged_gym, Gymnasium, Free Gait, OCS2 |
| Upgrade-path complexity ranking | Lead synthesis grounded in code + literature | pass | Final report section 8 |
| Final URLs live | WebFetch verification | pass with notes | Most open URLs verified; publisher DOI redirects live but some final pages blocked by 418/303 |

## Decision Log
- 2026-04-30: Scope includes both control algorithms and R&D systems/toolchains because the user asked for “research and development systems,” not just control theory.
- 2026-04-30: Argus comparison will be code-grounded rather than inferred from prior conversation; T4 must read repo files directly.
- 2026-04-30: One broad round was sufficient; source coverage included classical, learning, toolchain, and code mapping dimensions.
- 2026-04-30: Final report uses publisher-gated DOI sources sparingly and leans on accessible arXiv/docs/code sources for claims requiring direct verification.
