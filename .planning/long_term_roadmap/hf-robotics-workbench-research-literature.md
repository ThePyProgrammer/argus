# HuggingFace/PyTorch for Robotics: Literature and Benchmark Survey (2020–2026)

## Scope

This report surveys research literature, benchmarks, datasets, and reusable software primitives relevant to a “HuggingFace/PyTorch for Robotics” thesis: robot foundation models, open robot datasets, cross-embodiment learning, imitation/RL benchmarks, embodied AI evaluation, robot data/evaluation standardization, and reusable research primitives. Emphasis is on 2020–2026, with a few pre-2020 sources included where they are foundational to 2020s work.

## 1. Numbered Sources

1. RT-1 project page — https://robotics-transformer1.github.io/
2. RT-2 project page — https://robotics-transformer2.github.io/
3. Open X-Embodiment / RT-X project page — https://robotics-transformer-x.github.io/
4. Open X-Embodiment paper — https://arxiv.org/abs/2310.08864
5. Open X-Embodiment code — https://github.com/google-deepmind/open_x_embodiment
6. Hugging Face LeRobot blog — https://huggingface.co/blog/lerobot
7. Hugging Face LeRobot organization — https://huggingface.co/lerobot
8. LeRobot GitHub repository — https://github.com/huggingface/lerobot
9. DROID dataset project page — https://droid-dataset.github.io/
10. BridgeData project page — https://rail-berkeley.github.io/bridgedata/
11. RoboNet project page — https://robonet.wiki/
12. RH20T project page — https://rh20t.github.io/
13. Octo project page — https://octo-models.github.io/
14. Octo arXiv page — https://arxiv.org/abs/2405.12213
15. OpenVLA project page — https://openvla.github.io/
16. OpenVLA arXiv page — https://arxiv.org/abs/2406.09246
17. π0 blog — https://www.pi.website/blog/pi0
18. π0.5 blog — https://www.pi.website/blog/pi05
19. Diffusion Policy project page — https://diffusion-policy.cs.columbia.edu/
20. VIMA project page — https://vimalabs.github.io/
21. LIBERO GitHub repository — https://github.com/Lifelong-Robot-Learning/LIBERO
22. LIBERO project page — https://libero-project.github.io/
23. Meta-World project page — https://meta-world.github.io/
24. ManiSkill GitHub repository — https://github.com/haosulab/ManiSkill
25. RLBench project page — https://sites.google.com/view/rlbench
26. CALVIN GitHub repository — https://github.com/mees/calvin
27. Habitat project page — https://aihabitat.org/
28. AI2-THOR project page — https://ai2thor.allenai.org/
29. ALFRED benchmark page — https://alfredbench.github.io/
30. TEACh benchmark page — https://teachingalfred.github.io/
31. BEHAVIOR benchmark page — https://behavior.stanford.edu/
32. RoboCasa project page — https://robocasa.ai/
33. robomimic project page — https://robomimic.github.io/
34. robosuite project page — https://robosuite.ai/
35. SERL GitHub repository — https://github.com/rail-berkeley/serl

## 2. Evidence Table

| Claim | Sources | Confidence |
|---|---|---:|
| Robot foundation models shifted from single-lab/single-robot policies toward cross-embodiment, internet-pretrained, vision-language-action models during 2022–2025. | RT-1 [1], RT-2 [2], Open X-Embodiment/RT-X [3,4], Octo [13,14], OpenVLA [15,16], π0 [17], π0.5 [18] | High |
| Large open robot datasets are becoming the equivalent of ImageNet-scale infrastructure for robotics, but are still fragmented by robot, action space, camera setup, and task distribution. | Open X-Embodiment [3,4], DROID [9], BridgeData [10], RoboNet [11], RH20T [12], LeRobot [6,8] | High |
| Cross-embodiment learning is empirically promising but not solved; common action representations and normalized dataset formats help, yet real-world generalization remains uneven. | Open X-Embodiment [3,4], DROID [9], Octo [13,14], OpenVLA [15,16], π0.5 [18] | High |
| Simulation benchmarks remain essential for reproducible imitation/RL comparisons, but success in simulation does not automatically imply robust real-world robot deployment. | Meta-World [23], ManiSkill [24], RLBench [25], CALVIN [26], RoboCasa [32], robosuite [34] | High |
| Embodied AI benchmarks broaden evaluation beyond manipulation policies into navigation, instruction following, household activity completion, collaboration, and long-horizon semantic reasoning. | Habitat [27], AI2-THOR [28], ALFRED [29], TEACh [30], BEHAVIOR [31] | High |
| LeRobot is a concrete open-source instantiation of the “HuggingFace/PyTorch for Robotics” thesis: PyTorch policies, Hub-hosted datasets/models, unified dataset format, real/sim evaluation flow, and hardware abstraction. | LeRobot blog [6], LeRobot org [7], LeRobot repo [8] | High |
| Diffusion and transformer policies have become reusable primitives for imitation learning and generalist robot policies. | Diffusion Policy [19], Octo [13,14], OpenVLA [15,16], LeRobot [8] | High |
| 2025–2026 benchmark growth is trending toward larger, more realistic task distributions, including kitchen-scale and household-scale long-horizon manipulation. | RoboCasa365 [32], BEHAVIOR-1K [31], π0.5 [18], Habitat [27] | Medium-High |
| Open-source model availability varies: Octo and OpenVLA expose code/weights, while some frontier VLA systems report capabilities without equivalent open weights. | Octo [13], OpenVLA [15], π0 [17], π0.5 [18] | High |
| There is no single accepted universal robot benchmark analogous to GLUE/ImageNet; the field instead uses task-family benchmarks, dataset-specific evals, real-robot trials, and simulator leaderboards. | LIBERO [21,22], Meta-World [23], ManiSkill [24], RLBench [25], CALVIN [26], Open X-Embodiment [3], DROID [9] | High |

## 3. Key Findings by Theme

### 3.1 Robot foundation models and VLA policies

RT-1 demonstrated that a transformer-based robot policy can be trained on more than 130k real-world episodes spanning more than 700 tasks collected from 13 robots over 17 months, with a closed-loop rate of 3 Hz and reported success rates of 97% on seen tasks and 76% on unseen instructions [1]. Its architecture used an ImageNet-pretrained EfficientNet, FiLM language conditioning, TokenLearner compression, and a transformer that outputs discretized action tokens [1]. This makes RT-1 an early example of a reusable robot-policy architecture that looks much closer to ML infrastructure than one-off robotics code [1].

RT-2 reframed robot control as a vision-language-action problem by representing robot actions as text tokens and co-fine-tuning VLMs on both robot trajectory data and internet-scale vision-language tasks [2]. The project reports approximately 6k evaluation trials, comparisons against RT-1 and VC-1, variants built on PaLM-E 12B and PaLI-X 55B, and stronger performance on novel objects, symbol/icon/number placement, and semantic reasoning tasks [2]. This supports the thesis that robot policies increasingly inherit capability from web-scale vision-language pretraining rather than from robot data alone [2].

Open X-Embodiment/RT-X is a central 2023–2024 reference point for cross-embodiment robot learning: it aggregates more than 1M real robot trajectories across 22 robot embodiments, 60 datasets, 34 labs, 527 skills, and 160,266 tasks [3,4]. RT-1-X and RT-2-X are trained on this data mixture, using a common 7D gripper-frame action format, and the project reports a 50% improvement in small-data settings for RT-1-X and approximately 3x improvement over RT-2 for RT-2-X emergent-skill tests [3]. The implication is that cross-embodiment data mixtures can help, but the shared action abstraction also narrows the range of embodiments and task types that are easy to standardize [3,4].

Octo is an open-source generalist robot policy trained on about 800k Open X-Embodiment trajectories from 25 datasets [13,14]. It is described as a transformer-based diffusion policy, supports language commands and goal images, provides Octo-Small at 27M parameters and Octo-Base at 93M parameters, and reports evaluation across 9 real robot setups at 4 institutions [13]. Octo explicitly links code, weights, and a Colab, making it especially relevant to reusable HuggingFace/PyTorch-style robotics workflows [13].

OpenVLA is a 7B-parameter open-source vision-language-action model pretrained on 970k Open X-Embodiment robot episodes and reports state-of-the-art results across multiple robot platforms, often outperforming RT-1-X and Octo and sometimes RT-2-X [15,16]. Its project page states that paper, code, models, checkpoints, and training pipeline are public and that models are downloadable from Hugging Face [15]. This is one of the strongest examples of an open robot foundation model positioned like a modern ML model artifact [15,16].

π0 and π0.5 represent a partially different frontier: π0 combines a pretrained vision-language model with continuous action generation via flow matching, uses internet-scale VLM pretraining, Open X-Embodiment, and Physical Intelligence’s own multi-robot dexterous dataset across 8 robots, and reports outperforming OpenVLA and Octo on 5 test tasks [17]. π0.5 extends π0 toward home generalization with a two-stage setup that predicts a high-level language step and then low-level motor commands, and its blog states that experiments were done in homes not present in training data [18]. However, the π0 and π0.5 pages do not state the same open-weight availability as Octo or OpenVLA, so their direct utility as reusable open research primitives is lower unless releases appear later [17,18].

### 3.2 Open robot datasets

Open X-Embodiment is the largest and most influential open cross-embodiment aggregation found in this survey, with more than 1M trajectories across 22 embodiments, 60 datasets, and 34 labs [3,4]. It is important not only as a dataset but as an evaluation and modeling substrate because RT-1-X, RT-2-X, Octo, and OpenVLA all derive value from it or compare against models trained on it [3,13,15].

DROID contributes a complementary “in-the-wild” real-robot dataset: 76k demonstration trajectories, 350 hours of interaction data, 564 scenes, 86 tasks, 50 data collectors, and 13 institutions using a shared Franka Panda hardware setup with Zed cameras and Oculus Quest teleoperation [9]. Its project reports policy-learning evaluations on 6 tasks across 4 locations and gains of 22% in-distribution and 17% out-of-distribution versus baselines [9]. DROID’s shared hardware makes it less cross-embodiment than Open X-Embodiment but more controlled for studying environment/task diversity at scale [9].

BridgeData V2 contains 60,096 trajectories, including 50,365 human teleoperation demos and 9,731 scripted pick-and-place rollouts, collected across 24 environments and 13 skills with a WidowX 250 arm [10]. Each trajectory includes a natural-language instruction, and the dataset targets goal-image and language-conditioned offline robot learning [10]. BridgeData is particularly useful for lightweight reproducible language-conditioned manipulation research because the hardware and task scope are narrower than Open X-Embodiment but still diverse [10].

RoboNet predates the main 2020–2026 window but remains relevant because it includes more than 15M video frames, 113 camera viewpoints, and 7 robot platforms, and it explicitly targets cross-robot learning via shared robotic experience [11]. Its transfer results to held-out Franka/Kuka robots make it a precursor to Open X-Embodiment-style data pooling [11].

RH20T is a large multimodal manipulation dataset with more than 110k contact-rich manipulation sequences, 7 robot configurations, force-torque sensors, in-hand cameras, 8–10 global RGB-D cameras, microphones, and tactile sensing on one configuration [12]. It covers 48 RLBench tasks, 29 MetaWorld tasks, and 70 self-proposed tasks for 147 total tasks, making it unusually rich for contact-rich and multimodal imitation learning [12].

### 3.3 Cross-embodiment learning

The strongest cross-embodiment evidence comes from Open X-Embodiment/RT-X, Octo, OpenVLA, RoboNet, and π0/π0.5 [3,11,13,15,17,18]. Across these systems, the recurring pattern is to normalize or abstract actions, pool data across robots, and use transformer/diffusion/VLA architectures to learn a general policy prior [3,13,15,17].

The main contradiction is that “cross-embodiment” means different things across sources [3,9,13,17]. Open X-Embodiment emphasizes many robot embodiments but uses a common gripper-frame 7D action interface [3]. DROID emphasizes many real scenes/tasks but a shared Franka Panda embodiment [9]. π0 claims data across multiple robot forms and dexterous tasks, but the blog does not expose the full dataset details or open release status [17]. This means benchmark claims should be interpreted in terms of both embodiment diversity and action-space compatibility [3,9,17].

For a HuggingFace/PyTorch robotics platform, the key primitive is not merely a dataset loader; it is a canonical conversion layer that maps heterogeneous observations, robot states, actions, episode metadata, language instructions, and calibration into a model-ready format [6,8]. LeRobot’s dataset format pairs synchronized MP4 video or images with Parquet state/action files and supports dataset editing operations such as splitting, deleting episodes, and merging, which directly addresses this standardization need [8].

### 3.4 Imitation learning and RL benchmarks

LIBERO is a benchmark for lifelong robot learning and knowledge transfer with 130 tasks across LIBERO-Spatial, LIBERO-Object, LIBERO-Goal, and LIBERO-100, where LIBERO-100 is split into LIBERO-90 for pretraining and LIBERO-10 for downstream evaluation [21,22]. This makes it useful for evaluating whether robotics policies preserve and transfer knowledge rather than merely overfit one task suite [21].

Meta-World provides 50 simulated manipulation tasks and protocols including ML1, MT1, ML10, MT10, ML45, and MT50 for meta-RL and multi-task RL generalization [23]. It remains a compact benchmark for algorithmic comparison, especially when the research question is multi-task learning or held-out task adaptation rather than realistic visual manipulation [23].

ManiSkill 3 is a GPU-parallel robotics simulator and benchmark using SAPIEN, with manipulation tasks spanning humanoids, mobile manipulators, single-arm robots, tabletop, drawing/cleaning, and dexterous manipulation [24]. The README reports GPU-parallel RGB-D plus segmentation throughput above 30,000 FPS on an RTX 4090 and cites ManiSkill3 as a 2025 RSS paper [24]. This makes ManiSkill especially relevant for large-scale RL and imitation experiments where simulation throughput is a bottleneck [24].

RLBench provides 100 hand-designed vision-guided manipulation tasks and supports reinforcement learning, imitation learning, multi-task learning, geometric computer vision, and few-shot learning [25]. CALVIN focuses on long-horizon language-conditioned robot manipulation, supporting static RGB/depth, gripper RGB/depth, tactile images, proprioception, and both LH-MTLC and MTLC evaluations [26]. Together, RLBench and CALVIN cover the shift from single-task manipulation toward language-conditioned multi-step evaluation [25,26].

Diffusion Policy is a reusable imitation-learning primitive: it models a visuomotor policy as a conditional denoising diffusion process, uses receding-horizon action prediction, and reports evaluation on 12 tasks across 4 robot manipulation benchmarks with an average success-rate gain of 46.9% over prior methods [19]. VIMA similarly frames diverse manipulation tasks as a sequence problem over multimodal prompts and actions, with VIMA-Bench providing 17 task templates, 600k+ expert trajectories, and a four-level generalization protocol [20]. These two works are important because they define policy/model abstractions that can be wrapped as reusable training recipes [19,20].

### 3.5 Embodied AI evaluation

Habitat is a high-throughput embodied AI simulation platform with Habitat-Sim, Habitat-Lab, and Habitat Challenge, covering navigation, interaction, instruction following, and question answering [27]. The project reports physics-enabled 3D simulation, RGB-D and egomotion sensors, URDF robots, Bullet rigid-body mechanics, and performance in the thousands to tens of thousands of FPS depending on setup [27]. Habitat is relevant for evaluating embodied agents that must navigate and interact in 3D worlds rather than merely execute tabletop manipulation [27].

AI2-THOR is a Unity-based embodied AI framework with interactive object states, physics, multi-agent support, and several environment families: iTHOR has 120 indoor rooms and more than 2,000 objects, while RoboTHOR includes 89 apartments and more than 600 objects with LoCoBot/Kinect physical counterparts for 14 apartments [28]. ALFRED builds on this kind of environment for language-grounded household tasks, while TEACh adds text-dialog collaboration between a Commander and Follower [29,30].

BEHAVIOR-1K pushes evaluation toward full household activity completion with 1,000 realistic full-length household tasks, 50 interactive scenes, and 10,000+ objects using OmniGibson [31]. RoboCasa similarly moves manipulation benchmarking toward realistic kitchens: RoboCasa365 adds 365 tasks across 2,500 kitchen environments, 3,200+ objects from 150+ categories, 600+ hours of human demonstrations, and 1,600+ hours of synthetic demonstrations [32]. These benchmarks show that evaluation is moving from isolated manipulation skills toward environment-scale task distributions [31,32].

### 3.6 Data and evaluation standardization

LeRobot is the clearest current open-source system aligned with a HuggingFace/PyTorch robotics workbench thesis [6,7,8]. The Hugging Face organization page states that LeRobot provides “models, datasets, and tools for real-world robotics in PyTorch,” while the GitHub README lists supported policies such as ACT, Diffusion, VQ-BeT, Multitask DiT, HIL-SERL, TDMPC, Pi0Fast, Pi0.5, GR00T N1.5, SmolVLA, and XVLA [7,8].

LeRobot’s dataset and model distribution model is important: datasets are hosted on the Hugging Face Hub, and the dataset format pairs synchronized video/images with Parquet state/action data [6,8]. The LeRobot organization includes visible benchmark collections such as LIBERO, MetaWorld MT50, RobotWin Unified, and LIBERO Plus, and tools such as dataset visualization and annotation spaces [7]. This is exactly the kind of reusable infrastructure that robot learning has historically lacked [7,8].

robomimic and robosuite remain important earlier reusable primitives: robomimic is a framework for robot learning from demonstration with datasets and learning algorithms, and robosuite is a MuJoCo-based modular simulation framework and benchmark for robot learning [33,34]. SERL/HIL-SERL adds a real-world RL primitive layer, with the SERL repository describing DRQ, SAC, BC, Franka robot infrastructure, and tasks like peg insertion, PCB component insertion, cable routing, and object relocation, while noting that the older SERL repository is being deprecated in favor of HIL-SERL [35].

## 4. Contradictions and Open Questions

1. **Open-source frontier gap.** Octo and OpenVLA explicitly release code/weights or training pipelines, while π0 and π0.5 report frontier-like results but their pages do not state equivalent open model releases [13,15,17,18]. For an open HuggingFace/PyTorch workbench, this means Octo/OpenVLA/LeRobot are more directly reusable than π0-style systems unless releases change [13,15,17,18].

2. **Benchmark comparability is weak across model families.** RT-1, RT-2, RT-X, Octo, OpenVLA, and π0 report different task suites, robot setups, generalization categories, and evaluation protocols [1,2,3,13,15,17]. Headline success rates and “outperforms” claims are therefore not always directly comparable [1,2,3,13,15,17].

3. **Cross-embodiment is not the same as real-world generality.** Open X-Embodiment has many robot embodiments but relies on a common 7D gripper-frame action representation for the reported RT-X models [3]. DROID has many real-world scenes and tasks but a shared Franka setup [9]. RH20T has rich multimodal sensing and multiple robot configurations but is more specialized around contact-rich manipulation [12]. A benchmark can be broad along one axis while narrow along another [3,9,12].

4. **Simulation throughput versus physical realism remains unresolved.** ManiSkill emphasizes GPU-parallel simulation and very high rendering throughput [24], while BEHAVIOR and RoboCasa emphasize realistic household or kitchen-scale tasks [31,32]. It remains unclear which simulator/task families best predict real-robot transfer across foundation models [24,31,32].

5. **Robot data schemas are converging but not standardized.** LeRobot’s MP4/image plus Parquet state/action format and Hub distribution are strong practical steps [6,8], but Open X-Embodiment, DROID, BridgeData, RH20T, robomimic, and simulator datasets still differ in sensors, action spaces, calibration, metadata, and task labels [3,9,10,12,33]. A universally accepted equivalent of `datasets` for robotics remains emergent rather than settled [6,8].

6. **Evaluation still lacks a single canonical “robot GLUE.”** LIBERO, Meta-World, ManiSkill, RLBench, CALVIN, Habitat, AI2-THOR, ALFRED, TEACh, BEHAVIOR, and RoboCasa each evaluate different capabilities [21,23,24,25,26,27,28,29,30,31,32]. A useful workbench will likely need a benchmark registry and task taxonomy rather than a single benchmark abstraction [21,23,24,25,26,27,28,29,30,31,32].

## 5. Implications for Argus

1. **Treat LeRobot as the closest reference architecture for a PyTorch/HuggingFace robotics workbench.** LeRobot already combines PyTorch policies, Hub-hosted robot datasets, model artifacts, dataset visualization/annotation tools, real/sim eval flows, and a hardware-agnostic robot interface [6,7,8]. Argus should avoid duplicating this stack blindly and instead decide whether to wrap, interoperate with, or specialize around gaps not covered by LeRobot [6,8].

2. **Prioritize dataset adapters before model novelty.** The literature suggests that robot learning progress is bottlenecked by heterogeneous data representations and evaluation protocols as much as by architectures [3,6,8,9,10,12]. Argus should consider adapters for Open X-Embodiment, DROID, BridgeData, RH20T, LIBERO, Meta-World, ManiSkill, RLBench, CALVIN, RoboCasa, and robomimic-style datasets [3,8,9,10,12,21,23,24,25,26,32,33].

3. **Represent policies as reusable primitives.** ACT, Diffusion Policy, transformer diffusion policies, VLA models, and RL algorithms such as SAC/DRQ/HIL-SERL are recurring units across the ecosystem [8,19,35]. Argus should expose training/evaluation recipes as composable primitives with explicit observation specs, action specs, dataset transforms, checkpoint metadata, and benchmark bindings [8,19,35].

4. **Build benchmark abstraction around capability axes, not just environments.** Current benchmarks cover lifelong transfer, multi-task RL, long-horizon language control, embodied navigation, household interaction, kitchen manipulation, dialog, and full household activities [21,23,24,26,27,28,29,30,31,32]. Argus should classify evaluations by capability—language grounding, cross-embodiment transfer, visual manipulation, long-horizon planning, contact-rich manipulation, sim2real, and real-robot robustness—rather than simply listing benchmark names [21,23,24,26,27,31,32].

5. **Design for both open and closed frontier models.** OpenVLA and Octo are directly reproducible/open compared with π0/π0.5-style systems whose pages do not claim open weights [13,15,17,18]. Argus should support open local models as first-class citizens while allowing evaluation wrappers for externally served or unreleased frontier policies when licenses and access permit [13,15,17,18].

6. **Normalize action/observation schemas explicitly.** Open X-Embodiment’s 7D gripper-frame action format is useful but not universal [3]. RH20T includes force/torque, audio, tactile, multi-camera RGB-D, joint torques, and calibration packages [12]. LeRobot’s dataset format provides a practical storage pattern, but Argus should make embodiment/action/schema conversions visible and auditable rather than hiding them in loaders [8,12].

7. **Expect 2026 growth in realistic synthetic data and household tasks.** RoboCasa365 and BEHAVIOR-1K show that benchmark scale is expanding toward hundreds or thousands of realistic household tasks and large object/scene libraries [31,32]. Argus should be prepared for benchmark suites that are too large to treat as hand-written experiments and instead require registry metadata, subset selection, reproducible seeding, and automated result packaging [31,32].

## 6. Suggested Workbench Primitives

| Primitive | Why it matters | Source anchors |
|---|---|---|
| Robot dataset card/schema | Needed to document embodiment, cameras, state/action spaces, language labels, calibration, licenses, and splits. | LeRobot [8], DROID [9], RH20T [12], Open X [3] |
| Dataset converter/adapter | Required for Hub-style reuse across Open X, DROID, BridgeData, robomimic, simulator datasets. | LeRobot [8], Open X [3], BridgeData [10], robomimic [33] |
| Observation/action spec | Cross-embodiment claims depend on explicit action and sensor definitions. | Open X [3], RH20T [12], Octo [13] |
| Policy recipe | ACT/Diffusion/VLA/RL methods should be reproducible training recipes, not ad hoc scripts. | LeRobot [8], Diffusion Policy [19], OpenVLA [15] |
| Benchmark registry | Benchmarks are diverse and capability-specific; registry metadata is necessary for comparability. | LIBERO [21], Meta-World [23], ManiSkill [24], CALVIN [26], BEHAVIOR [31] |
| Evaluation artifact | Real and simulated evals need result packaging with videos, seeds, success metrics, environment versions, and robot metadata. | Habitat [27], ManiSkill [24], RoboCasa [32], LeRobot [8] |
| Model card for robot policies | Robot policies need model cards that include embodiment, action semantics, safety limits, datasets, eval tasks, and failure modes. | OpenVLA [15], Octo [13], LeRobot [8], π0.5 [18] |

## 7. Bottom Line

The research literature strongly supports the thesis that robotics is moving toward a HuggingFace/PyTorch-like stack: shared datasets, reusable policy architectures, Hub-distributed model artifacts, benchmark registries, and standardized evaluation flows [6,7,8,13,15]. The caveat is that robotics has harder heterogeneity than NLP or vision because action spaces, robot embodiments, sensors, calibration, simulators, and safety constraints are part of the data/model interface [3,8,9,12]. A useful Argus contribution should therefore focus less on being “just another model zoo” and more on rigorous data schemas, converters, benchmark metadata, policy recipes, and reproducible evaluation artifacts that can bridge open robot datasets, simulation benchmarks, and real-world robot deployments [3,6,8,21,24,31,32].
