# Literature survey: AGIBOT X2 and comparable humanoid learning/control

Accessed date for all sources: **2026-04-30**.

Scope: prior work using AGIBOT/AgiBot humanoids and directly comparable humanoid platforms for learning and control. The emphasis is what has already been demonstrated and what transfers to **AGIBOT X2 simulation training**, including swarm-scale training implications. This is not a raw asset repository inventory.

## Executive takeaways

- The only source found with an explicit **AgiBot X2** learning/control claim is **WholeBodyVLA**, which reports a unified latent VLA plus RL locomotion/motion policy on AgiBot X2 and a **21.3% improvement** over a prior baseline [2]. That is the closest prior art for X2 loco-manipulation transfer.
- AgiBot-specific public work is currently stronger for **manipulation datasets and VLA/world-model learning** than for open, low-level X2 locomotion controllers [1], [2], [3], [4], [5], [6].
- The directly transferable control recipes come from comparable humanoids: Unitree G1/H1, Booster T1, Agility Digit, and Fourier N1. Common successful patterns are teacher-student RL, motion-retargeting plus RL tracking, modular residual controllers, embodiment-aware distillation, and heavy domain randomization [7], [9], [10], [12], [15], [16], [17], [18], [20], [21].
- Benchmarks/datasets relevant to simulation training include AgiBot World Colosseo, HumanoidBench, ALMI-X, LeVERB's closed-loop task benchmark, CLAW motion-language data, and comparable humanoid trajectory/control datasets [1], [7], [9], [13], [14], [22].
- For swarm training, no source found demonstrates multi-AGIBOT-X2 swarm control. The literature supports training **single-robot robust primitives** first, then composing multi-agent coordination in simulation with shared policies, randomized embodiment/dynamics, and task-level planners.

## 1. Numbered paper/source list

### AGIBOT-specific and AgiBot-adjacent sources

1. **AgiBot World Colosseo: A Large-scale Manipulation Platform for Scalable and Intelligent Embodied Systems**. AgiBot-World-Contributors, Qingwen Bu, Jisong Cai, Li Chen, Xiuqi Cui, Yan Ding, Siyuan Feng, Shenyuan Gao, Xindong He, Xuan Hu, Xu Huang, Shu Jiang, Yuxin Jiang, Cheng Jing, Hongyang Li, et al. arXiv:2503.06669, submitted 2025-03-09, revised 2025-08-04. URL: https://arxiv.org/abs/2503.06669. Project: https://agibot-world.com/. Code: https://github.com/OpenDriveLab/AgiBot-World. Accessed 2026-04-30.
2. **WholeBodyVLA: Towards Unified Latent VLA for Whole-Body Loco-Manipulation Control**. Haoran Jiang, Jin Chen, Qingwen Bu, Li Chen, Modi Shi, Yanjie Zhang, Delong Li, Chuanzhe Suo, Chuang Wang, Zhihui Peng, Hongyang Li. arXiv:2512.11047, submitted/revised 2025-12. URL: https://arxiv.org/abs/2512.11047. Accessed 2026-04-30.
3. **Is Diversity All You Need for Scalable Robotic Manipulation?** Modi Shi, Li Chen, Jin Chen, Yuxiang Lu, Chiming Liu, Guanghui Ren, Ping Luo, Di Huang, Maoqing Yao, Hongyang Li. arXiv:2507.06219, submitted 2025-07-08. URL: https://arxiv.org/abs/2507.06219. Accessed 2026-04-30.
4. **A1: A Fully Transparent Open-Source, Adaptive and Efficient Truncated Vision-Language-Action Model**. Kaidong Zhang, Jian Zhang, Rongtao Xu, Yu Sun, Shuoshuo Xue, Youpeng Wen, Xiaoyu Guo, Minghao Guo, Weijia Liufu, Liu Zihou, Kangyi Ji, Yangsong Zhang, Jiarun Zhu, Jingzhi Liu, Zihang Li, Ruiyi Chen, Meng Cao, Jingming Zhang, Shen Zhao, Xiaojun Chang, Feng Zheng, Ivan Laptev, Xiaodan Liang. arXiv:2604.05672, submitted 2026-04. URL: https://arxiv.org/abs/2604.05672. Accessed 2026-04-30.
5. **BridgeV2W: Bridging Video Generation Models to Embodied World Models via Embodiment Masks**. Yixiang Chen, Peiyan Li, Jiabing Yang, Keji He, Xiangnan Wu, Yuan Xu, Kai Wang, Jing Liu, Nianfeng Liu, Yan Huang, Liang Wang. arXiv:2602.03793, submitted 2026-02-03. URL: https://arxiv.org/abs/2602.03793. Accessed 2026-04-30.
6. **StableIDM: Stabilizing Inverse Dynamics Model against Manipulator Truncation via Spatio-Temporal Refinement**. Kerui Li, Zhe Jing, Xiaofeng Wang, Zheng Zhu, Yukun Zhou, Guan Huang, Dongze Li, Qingkai Yang, Huaibo Huang. arXiv:2604.17887, submitted 2026-04-20. URL: https://arxiv.org/abs/2604.17887. Accessed 2026-04-30.

### Benchmarks, datasets, and general humanoid task sources

7. **HumanoidBench: Simulated Humanoid Benchmark for Whole-Body Locomotion and Manipulation**. Carmelo Sferrazza, Dun-Ming Huang, Xingyu Lin, Youngwoon Lee, Pieter Abbeel. arXiv:2403.10506, submitted 2024-03-15, revised 2024-06-18. URL: https://arxiv.org/abs/2403.10506. Project/code: https://humanoid-bench.github.io. Accessed 2026-04-30.
8. **Applying Model Predictive Control to HumanoidBench**. arXiv:2408.00342. URL: https://arxiv.org/abs/2408.00342. Accessed 2026-04-30.
9. **Adversarial Locomotion and Motion Imitation for Humanoid Policy Learning**. Jiyuan Shi, Xinzhe Liu, Dewei Wang, Ouyang Lu, Sören Schwertfeger, Chi Zhang, Fuchun Sun, Chenjia Bai, Xuelong Li. arXiv:2504.14305, NeurIPS 2025 note. URL: https://arxiv.org/abs/2504.14305. Project: https://almi-humanoid.github.io. Code: https://github.com/TeleHuman/ALMI-Open. Dataset: https://huggingface.co/datasets/TeleEmbodied/ALMI-X. Accessed 2026-04-30.
10. **Learning Sim-to-Real Humanoid Locomotion in 15 Minutes**. Younggyo Seo, Carmelo Sferrazza, Juyue Chen, Guanya Shi, Rocky Duan, Pieter Abbeel. arXiv:2512.01996. URL: https://arxiv.org/abs/2512.01996. Accessed 2026-04-30.
11. **LeVERB: Humanoid Whole-Body Control with Latent Vision-Language Instruction**. Haoru Xue, Xiaoyu Huang, Dantong Niu, Qiayuan Liao, Thomas Kragerud, Jan Tommy Gravdahl, Xue Bin Peng, Guanya Shi, Trevor Darrell, Koushil Sreenath, Shankar Sastry. arXiv:2506.13751. URL: https://arxiv.org/abs/2506.13751. Accessed 2026-04-30.
12. **FRoM-W1: Towards General Humanoid Whole-Body Control with Language Instructions**. Peng Li et al. arXiv:2601.12799. URL: https://arxiv.org/abs/2601.12799. Accessed 2026-04-30.
13. **CLAW: Composable Language-Annotated Whole-body Motion Generation**. Jianuo Cao, Yuxin Chen, Masayoshi Tomizuka. arXiv:2604.11251. URL: https://arxiv.org/abs/2604.11251. Accessed 2026-04-30.
14. **Learning Versatile Humanoid Manipulation with Touch Dreaming**. Yaru Niu, Zhenlong Fang, Binghong Chen, Shuai Zhou, Revanth Krishna Senthilkumaran, Hao Zhang, Bingqing Chen, Chen Qiu, H. Eric Tseng, Jonathan Francis, Ding Zhao. arXiv:2604.13015. URL: https://arxiv.org/abs/2604.13015. Accessed 2026-04-30.

### Comparable humanoid learning/control sources

15. **Learning Whole-Body Humanoid Locomotion via Motion Generation and Motion Tracking**. Zewei Zhang, Kehan Wen, Michael Xu, Junzhe He, Chenhao Li, Takahiro Miki, Clemens Schwarke, Chong Zhang, Xue Bin Peng, Marco Hutter. arXiv:2604.17335. URL: https://arxiv.org/abs/2604.17335. Accessed 2026-04-30.
16. **Embodiment-Aware Generalist Specialist Distillation for Unified Humanoid Whole-Body Control**. Quanquan Peng, Yunfeng Lin, Yufei Xue, Jiangmiao Pang, Weinan Zhang. arXiv:2602.02960. URL: https://arxiv.org/abs/2602.02960. Accessed 2026-04-30.
17. **AGILE: [end-to-end workflow for humanoid loco-manipulation learning]**. Huihua Zhao, Rafael Cathomen, Lionel Gulich, Wei Liu, Efe Arda Ongan, Michael Lin, Shalin Jain, Soha Pouya, Yan Chang. arXiv:2603.20147. URL: https://arxiv.org/abs/2603.20147. Accessed 2026-04-30.
18. **APEX: Learning Adaptive High-Platform Traversal for Humanoid Robots**. Yikai Wang, Tingxuan Leng, Changyi Lin, Shiqi Liu, Shir Simon, Bingqing Chen, Jonathan Francis, Ding Zhao. arXiv:2602.11143. URL: https://arxiv.org/abs/2602.11143. Accessed 2026-04-30.
19. **ULTRA: Unified Multimodal Control for Autonomous Humanoid Whole-Body Loco-Manipulation**. Xialin He, Sirui Xu, Xinyao Li, Runpei Dong, Liuyu Bian, Yu-Xiong Wang, Liang-Yan Gui. arXiv:2603.03279. URL: https://arxiv.org/abs/2603.03279. Accessed 2026-04-30.
20. **SteadyTray: Learning Object Balancing Tasks in Humanoid Tray Transport via Residual Reinforcement Learning**. Anlun Huang, Zhenyu Wu, Soofiyan Atar, Yuheng Zhi, Michael Yip. arXiv:2603.10306. URL: https://arxiv.org/abs/2603.10306. Accessed 2026-04-30.
21. **Learn to Teach: Sample-Efficient Privileged Learning for Humanoid Locomotion over Diverse Terrains**. Feiyang Wu, Xavier Nal, Jaehwi Jang, Wei Zhu, Zhaoyuan Gu, Anqi Wu, Ye Zhao. arXiv:2402.06783, submitted 2024-02-09, revised 2025-08-09. URL: https://arxiv.org/abs/2402.06783. Accessed 2026-04-30.
22. **PPF: Pre-training and Preservative Fine-tuning of Humanoid Locomotion via Model-Assumption-based Regularization**. Hyunyoung Jung, Zhaoyuan Gu, Ye Zhao, Hae-Won Park, Sehoon Ha. arXiv:2504.09833. URL: https://arxiv.org/abs/2504.09833. Accessed 2026-04-30.
23. **Revisiting Reward Design and Evaluation for Robust Humanoid Standing and Walking**. Bart van Marum, Aayam Shrestha, Helei Duan, Pranay Dugar, Jeremy Dao, Alan Fern. arXiv:2404.19173, IROS 2024 note. URL: https://arxiv.org/abs/2404.19173. Accessed 2026-04-30.
24. **Template Model Inspired Task Space Learning for Robust Bipedal Locomotion**. Guillermo A. Castillo, Bowen Weng, Shunpeng Yang, Wei Zhang, Ayonga Hereid. arXiv:2309.15442, IROS 2023 note. URL: https://arxiv.org/abs/2309.15442. Accessed 2026-04-30.

## 2. Evidence table

| Claim | Source(s) | Confidence | Notes for AGIBOT X2 simulation training |
|---|---:|---|---|
| AgiBot World Colosseo provides a large-scale manipulation dataset with over 1M trajectories, 217 tasks, and five deployment scenarios. | [1] | High | Useful for manipulation pretraining and task diversity, less directly for low-level X2 locomotion unless embodiment/action spaces align. |
| GO-1 uses latent action representations and reports ~30% average gain over Open X-Embodiment, >60% success on hard dexterous/long-horizon tasks, and +32% over RDT. | [1] | Medium-high | Strong evidence that latent action abstractions help large heterogeneous robot datasets. Confirm exact metrics in paper before using as benchmark target. |
| WholeBodyVLA is the clearest AGIBOT X2-specific whole-body loco-manipulation source found. | [2] | High | Prioritize reproducing its assumptions: egocentric video, latent VLA, RL locomotion/motion policy. |
| WholeBodyVLA reports 21.3% improvement over a prior baseline on AgiBot X2. | [2] | Medium | WebFetch extraction gave the metric but not the complete metric definition. Verify in paper before quoting in formal publications. |
| Task diversity may matter more than more demonstrations per task; multi-embodiment pretraining can be optional if single-embodiment data are strong. | [3] | Medium-high | For X2, collect diverse tasks before obsessing over many repeated demos. Multi-robot data helps but is not a magic tax to pay blindly. |
| Expert variation can confuse policy learning; debiasing velocity ambiguity improved GO-1-Pro by 15%, comparable to 2.5x more pretraining data. | [3] | Medium | Important when mixing teleoperators/demonstrators in X2 swarm data; normalize or model demonstrator style. |
| A1 and BridgeV2W show AgiBot-related VLA/world-model evaluations, but are less directly low-level control sources. | [4], [5] | Medium | Useful for perception/action model interfaces and predictive simulation, not sufficient for gait/control. |
| StableIDM improves AgiBot benchmark action accuracy and real-robot replay success under manipulator truncation/partial visibility. | [6] | Medium | Relevant to egocentric/occluded humanoid manipulation, especially if X2 hands/arms leave camera view. |
| HumanoidBench covers simulated whole-body locomotion and manipulation for a humanoid with dexterous hands; SOTA RL struggles on many tasks. | [7] | High | Good baseline benchmark for algorithm sanity before X2-specific environment investment. |
| Hierarchical methods with strong low-level skills do better on HumanoidBench than flat SOTA RL on many tasks. | [7] | Medium-high | For X2 swarm: train robust low-level walking/reaching/standing primitives, then layer coordination/task policies above. |
| ALMI validates separating lower-body stable walking from upper-body imitation on Unitree H1 and releases ALMI-X data/code. | [9] | High | Transferable architecture for X2 expressive loco-manipulation: isolate balance from upper-body swarm tasks. |
| Fast off-policy RL can train sim-to-real humanoid locomotion in about 15 minutes on one RTX 4090 for Unitree G1 and Booster T1. | [10] | Medium | Promising for rapid X2 iteration; hardware-specific results should not be assumed without actuator/sensor matching. |
| LeVERB reports a latent vision-language instruction hierarchy with 150+ tasks and 58.5% overall zero-shot success. | [11] | Medium | Provides a task-level evaluation template for language-to-whole-body X2 control. |
| FRoM-W1 combines language-conditioned human motion generation, retargeting, and RL execution on Unitree H1/G1. | [12] | Medium | Relevant if X2 policies need commandable whole-body motions. Retargeting quality will dominate transfer. |
| CLAW creates language-annotated, physically grounded whole-body trajectories for Unitree G1 in MuJoCo. | [13] | Medium | Good precedent for generating X2 motion-language datasets synthetically. |
| Touch Dreaming reports 90.9% relative success improvement on five contact-rich humanoid tasks and 30% gain from latent tactile prediction. | [14] | Medium | If X2 has tactile or force sensors, train contact predictors; if not, simulate privileged contact for distillation. |
| Unitree G1 whole-body locomotion can use online diffusion motion generation plus RL tracking to traverse boxes, hurdles, stairs, and mixed terrain. | [15] | Medium-high | Strong transferable pattern for X2 terrain navigation; use generated references, then closed-loop tracker refinement. |
| Embodiment-aware generalist-specialist distillation supports one policy across Unitree H1, G1, Fourier N1, and others. | [16] | Medium | Directly relevant to X2 if training with proxy morphologies or multiple X2 variants. Encode embodiment explicitly. |
| AGILE shows reproducible training/evaluation/deployment descriptors can yield consistent sim-to-real across G1 and Booster T1 skills. | [17] | Medium | For swarm work, standardized descriptors and evaluation are boring but necessary; otherwise results will be theater. |
| APEX demonstrates zero-shot 0.8 m platform traversal on Unitree G1 by combining terrain-conditioned climbing/walking/crawling/stand-up skills. | [18] | Medium | Relevant for X2 robust locomotion skill library and recovery in cluttered multi-robot environments. |
| ULTRA uses retargeting, latent skill compression, multimodal control, and RL to support G1 loco-manipulation from egocentric perception. | [19] | Medium | Transferable for X2 task policies that must use both dense references and sparse goals. |
| SteadyTray's residual RL modularizes walking and tray stabilization, reporting 96.9% speed-tracking success and 74.5% push resilience. | [20] | Medium | Good pattern for X2 carrying/cooperative transport: preserve locomotion policy and learn residual stabilization. |
| L2T reports zero-shot sim-to-real on Digit over 12+ terrains without depth estimation. | [21] | Medium-high | Privileged teacher/student training is a safe bet for X2 locomotion under terrain/dynamics variation. |
| PPF reaches 1.5 m/s on Digit and remains stable on slippery, sloped, uneven, sandy terrain. | [22] | Medium | Use model-based priors where valid, then fine-tune without catastrophic forgetting. |
| Reward-design studies on Digit show command tracking, disturbance recovery, and power use trade off and must be evaluated together. | [23] | High | X2 swarm metrics need energy, falls, collision recovery, and command tracking; one reward number is not enough. |
| Task-space layered control inspired by template models improves Digit sample efficiency and robustness. | [24] | Medium | X2 policies can benefit from lower-level model-based structure rather than fully end-to-end joint targets. |
| No public work found demonstrating swarm control with multiple AGIBOT X2 humanoids. | Search across AGIBOT/X2/humanoid swarm terms | Medium-high | Treat swarm control as an open integration problem, not a solved literature baseline. |

## 3. AGIBOT-specific works

### 3.1 AgiBot World Colosseo [1]

AgiBot World Colosseo is the central public AgiBot dataset/platform source found. It introduces a large manipulation dataset: **over 1 million trajectories**, **217 tasks**, and **five deployment scenarios** [1]. Its collection pipeline emphasizes standardized capture and human quality checks. It also claims extensibility from grippers to dexterous hands and visuo-tactile sensing [1].

The accompanying policy, **GO-1**, uses latent action representations and reports notable gains: roughly **30%** over Open X-Embodiment pretraining, **>60% success** on difficult dexterous and long-horizon tasks, and **32%** over RDT [1]. For X2 simulation training, the practical point is not “copy GO-1 and pray.” The useful part is the latent-action abstraction and the evidence that broad task diversity helps general-purpose manipulation.

Transfer to AGIBOT X2:

- Use it for manipulation priors, task taxonomies, and data-scaling expectations.
- Do not assume it solves X2 locomotion or balance. The dataset is manipulation-centered.
- For swarm work, it can seed per-robot manipulation behaviors before adding multi-agent coordination.

### 3.2 WholeBodyVLA on AgiBot X2 [2]

WholeBodyVLA is the most directly relevant source because it explicitly reports results on **AgiBot X2**. The method uses a unified latent VLA setup that can learn from **low-cost action-free egocentric videos**, plus an **LMO reinforcement-learning policy** for core motion primitives such as advancing, turning, and squatting [2]. It reports outperforming a prior baseline by **21.3%** on AgiBot X2 [2].

Transfer to AGIBOT X2:

- Strong candidate baseline architecture: egocentric video or observation encoder, latent VLA, low-level RL motor policy.
- Particularly relevant for X2 whole-body loco-manipulation in larger spaces.
- Reproduction needs the exact action/observation definition and benchmark metric; the web extraction did not expose those details.

### 3.3 Diversity scaling for AgiBot/GO-1-Pro [3]

The diversity paper studies **task, embodiment, and expert diversity** for scalable robotic manipulation [3]. It concludes that task diversity is especially valuable; multi-embodiment pretraining can be optional; strong single-embodiment data can transfer well; and expert variation can inject velocity ambiguity [3]. A debiasing method reportedly improves **GO-1-Pro** by **15%**, comparable to **2.5x** more pretraining data [3].

Transfer to AGIBOT X2:

- For X2 data collection, prioritize broad task coverage and state/action consistency.
- If multiple teleoperators provide demonstrations, model or normalize style differences.
- Multi-embodiment data is useful, but do not use it as an excuse for sloppy X2-specific data.

### 3.4 AgiBot-related VLA/world-model/action prediction works [4], [5], [6]

A1 proposes an open, adaptive VLA model with early stopping and layer/denoising reuse to reduce inference cost while preserving manipulation performance on AgiBot and other platforms [4]. BridgeV2W maps robot actions into embodiment masks so video generation models better preserve robot embodiment and viewpoint, with evaluation on **DROID and AgiBot-G1** data [5]. StableIDM stabilizes inverse dynamics under partial robot visibility/manipulator truncation and reports improved AgiBot benchmark action accuracy and real-robot replay success [6].

Transfer to AGIBOT X2:

- A1: useful if X2 swarm deployment needs low-latency VLA inference.
- BridgeV2W: relevant to embodied world models for sim imagination or video prediction.
- StableIDM: relevant when egocentric cameras lose sight of hands/arms during whole-body tasks.
- None of these should be mistaken for a full X2 locomotion controller.

## 4. Comparable humanoid works

### 4.1 Unitree G1/H1 and Booster T1

Unitree G1/H1 are the closest public comparable humanoid platforms by volume of recent learning/control work.

- **Motion generation + RL tracking**: Zhang et al. combine an online diffusion motion generator with an RL whole-body tracker and deploy on Unitree G1 over boxes, hurdles, stairs, and mixed terrain [15]. Transfer lesson: generate terrain-aware references online, then train a tracker robust enough to follow them under closed-loop perturbations.
- **Fast sim-to-real locomotion**: Seo et al. show a practical off-policy RL recipe using FastSAC/FastTD3, mass-parallel simulation, minimalist rewards, strong randomization, and deployment on Unitree G1 and Booster T1 after roughly 15 minutes of training on one RTX 4090 [10]. Transfer lesson: rapid iteration is possible if the simulator and reward are disciplined.
- **ALMI for H1**: ALMI separates lower-body stable walking from upper-body imitation and alternates updates, with simulation and real Unitree H1 validation plus released code/dataset [9]. Transfer lesson: decouple balance from expressive or task-specific upper-body motion.
- **Embodiment-aware distillation**: EAGLE trains a shared policy across multiple humanoids, improves robot-specific specialists, and distills back into a generalist, covering Unitree H1/G1 and Fourier N1 [16]. Transfer lesson: encode embodiment and iterate specialist/generalist training if using proxy robots or mixed X2 variants.
- **AGILE workflow**: AGILE emphasizes interactive environment verification, reproducible training, unified evaluation, and descriptor-based deployment on Unitree G1 and Booster T1 [17]. Transfer lesson: for X2 swarm experiments, evaluation plumbing is a first-class artifact.
- **APEX high-platform traversal**: APEX traverses 0.8 m platforms on a 29-DoF Unitree G1 using terrain-conditioned climbing, walking/crawling, stand/lie transitions, LiDAR/elevation-map processing, and perception artifact modeling [18]. Transfer lesson: multi-skill composition and recovery are critical for cluttered environments.
- **ULTRA loco-manipulation**: ULTRA retargets mocap, compresses skills into latent space, and trains a controller that can follow dense references or sparse goals from egocentric perception [19]. Transfer lesson: build one policy interface that handles both reference tracking and task intent.
- **SteadyTray residual RL**: SteadyTray keeps locomotion separate and learns a residual tray-stabilizing controller, reporting 96.9% speed-tracking success and 74.5% disturbance resilience on Unitree G1 [20]. Transfer lesson: for cooperative carrying or payload tasks, residual stabilization beats retraining the whole gait stack.
- **FRoM-W1 and LeVERB**: these show language or vision-language instruction can be mapped into latent actions/motions and executed by RL whole-body controllers [11], [12]. Transfer lesson: language should probably command reusable whole-body primitives, not raw joints.
- **CLAW**: creates physically grounded language-labeled G1 motion trajectories in MuJoCo [13]. Transfer lesson: synthetic motion-language generation is feasible for X2 if the simulator has faithful kinematics and contacts.

### 4.2 Agility Digit and Cassie-adjacent biped methods

Digit is not a humanoid with the same upper-body manipulation profile as X2, but it is a strong source for bipedal locomotion and sim-to-real training.

- **Learn to Teach (L2T)**: single-stage teacher-student privileged learning reports zero-shot sim-to-real on Digit across 12+ terrains without depth estimation [21]. Transfer lesson: privileged simulation teachers and proprioceptive students are reliable for robust X2 walking.
- **PPF**: pretraining from a model-based controller followed by preservative RL fine-tuning reaches 1.5 m/s on Digit and handles slippery, sloped, uneven, and sandy terrain [22]. Transfer lesson: preserve model-based behavior only where assumptions are valid.
- **Reward design/evaluation**: van Marum et al. benchmark command tracking, disturbance recovery, and energy efficiency on Digit and show reward trade-offs [23]. Transfer lesson: X2 reward design must report multi-axis robustness, not a single cherry-picked success metric.
- **Template model inspired task-space learning**: Castillo et al. combine ALIP-inspired task-space planning with model-based tracking and report improved robustness/sample efficiency on Digit [24]. Transfer lesson: structured action spaces and template-model priors still matter.

### 4.3 Tactile/contact-rich humanoid manipulation

Touch Dreaming combines a balance-capable lower-body RL controller, VR whole-body demonstrations, tactile sensing, behavior cloning, and prediction of future tactile latents [14]. It reports a **90.9% relative improvement** in average success over a stronger baseline and a **30% relative gain** from latent tactile prediction [14].

Transfer to AGIBOT X2:

- If X2 has tactile sensing or force/torque proxies, use prediction of future contact latents as an auxiliary objective.
- If tactile sensing is absent, train in simulation with privileged contact labels and distill into proprioceptive/visual policies.
- For swarm tasks involving handoffs, pushing, carrying, or cooperative manipulation, contact anticipation is probably more valuable than another decorative VLM layer.

## 5. Datasets and benchmarks

| Dataset/benchmark | Source | What it contains | Relevance to AGIBOT X2 |
|---|---:|---|---|
| AgiBot World Colosseo | [1] | >1M trajectories, 217 tasks, five scenarios, manipulation-centered dataset and GO-1 policy stack. | Primary AgiBot-specific data source; use for manipulation pretraining/task design, not as complete locomotion solution. |
| HumanoidBench | [7] | Simulated humanoid with dexterous hands, whole-body locomotion and manipulation tasks, open-source code. | Good algorithm benchmark before X2-specific simulator investment; tests whether methods handle full-body humanoid control. |
| MuJoCo MPC on HumanoidBench | [8] | MPC baseline/regularization on HumanoidBench. | Baseline for model-based control comparisons and smoother motion. |
| ALMI-X | [9] | Large MuJoCo-based whole-body trajectory set for humanoid policy learning; code and Hugging Face dataset. | Useful for imitation/motion tracking baselines and architecture comparison. |
| LeVERB benchmark | [11] | Closed-loop benchmark with 150+ tasks across 10 categories for latent vision-language whole-body control. | Template for X2 instruction-following evaluation. |
| CLAW motion-language data | [13] | Unitree G1 motion-language pairs from kinematic planning and MuJoCo simulation. | Recipe for generating X2 motion-language data. |
| AgiBot-G1 / AgiBot benchmark references | [5], [6] | World-model and inverse-dynamics evaluations involving AgiBot data/benchmarks. | Useful for perception/action prediction under embodiment and visibility constraints. |
| Digit terrain/controller benchmarks | [21], [22], [23], [24] | Real-world locomotion over diverse terrain, reward/evaluation tests, model-prior RL. | Transferable locomotion robustness and evaluation methodology. |
| G1 platform traversal/manipulation benchmarks | [15], [18], [19], [20] | Terrain obstacles, platform traversal, tray transport, whole-body loco-manipulation. | Strong basis for X2 task suite design. |

## 6. Contradictions and gaps

1. **AGIBOT X2-specific public evidence is thin.** WholeBodyVLA is the only explicitly X2-focused work found [2]. Most AgiBot public work is manipulation/VLA/world-model oriented [1], [3], [4], [5], [6]. There is no broad public X2 locomotion benchmark comparable to the Unitree G1 literature.

2. **No demonstrated AGIBOT X2 swarm-control paper was found.** The search found humanoid whole-body control, manipulation, and single-robot sim-to-real, but not multi-X2 swarm coordination. Swarm control for X2 should be treated as a new composition layer over single-robot primitives.

3. **Dataset scale versus data quality is unresolved.** AgiBot World emphasizes scale [1], while the diversity study argues that task diversity and debiasing can beat brute-force data growth [3]. The sane conclusion: collect diverse tasks, but keep demonstrator/action distributions clean.

4. **Multi-embodiment pretraining is useful but not mandatory.** EAGLE argues embodiment-aware multi-humanoid distillation works [16], while the diversity study says multi-embodiment pretraining can be optional if single-embodiment data are strong [3]. For X2, use multi-embodiment data to bootstrap, then fine-tune aggressively on X2-specific dynamics.

5. **VLA papers do not replace motor control.** A1, BridgeV2W, StableIDM, LeVERB, FRoM-W1, and WholeBodyVLA provide perception/language/action abstractions [2], [4], [5], [6], [11], [12]. The locomotion stack still needs RL tracking, teacher-student training, residual stabilization, or model-based priors [10], [15], [20], [21], [22], [24].

6. **Benchmarks are fragmented.** HumanoidBench tests generic simulated full-body control [7]. AgiBot World tests scalable manipulation [1]. Unitree/Digit papers test hardware-specific locomotion [15], [18], [21], [22], [23], [24]. There is no single benchmark that covers X2 whole-body loco-manipulation plus swarm coordination.

7. **Metric definitions need verification.** Several recent 2026 papers expose claims through abstracts/search extraction, but not full experimental detail in this survey. Before turning these into formal baselines, verify exact success metrics, control frequencies, actuator limits, observation spaces, and train/test task splits.

## 7. Recommendations for AGIBOT X2 simulation training

1. **Start from a hierarchical stack.** Train robust X2 low-level primitives first: stand, walk, turn, squat, recover, reach, carry. HumanoidBench and ALMI both suggest hierarchical methods with strong low-level skills outperform flat policies on full-body tasks [7], [9].

2. **Use teacher-student and privileged simulation.** L2T and similar Digit work make a strong case for privileged teacher policies and deployable proprioceptive students [21]. This is especially relevant for X2 swarm settings where real-time perception may be occluded by other robots.

3. **Retarget human/G1/H1 motion cautiously.** FRoM-W1, CLAW, ULTRA, and G1 motion-generation work show the value of retargeted references and RL trackers [12], [13], [15], [19]. X2-specific joint limits, inertia, foot geometry, and hand payload assumptions must be enforced in simulation.

4. **Encode embodiment explicitly.** If using data from G1/H1/Digit/Fourier as priors, follow EAGLE's lesson: condition policies on embodiment/dynamics, specialize on X2, then distill if needed [16].

5. **Make residual controllers the default for payload/cooperative tasks.** SteadyTray shows modular residual RL can preserve locomotion while stabilizing carried objects [20]. For multiple X2 robots carrying objects together, train locomotion and payload residuals separately before joint coordination.

6. **Borrow AgiBot World's task-diversity discipline, not just its scale.** Use AgiBot World and the diversity study to define broad manipulation scenarios and avoid demonstrator bias [1], [3].

7. **Design a swarm benchmark explicitly.** Include per-robot fall rate, inter-robot collision rate, formation error, cooperative object pose error, recovery time, energy, and task success. The literature does not hand this to us; build it or accept hand-wavy demos.

8. **Keep VLA above the control loop.** Use VLA/world models for task selection, intent, and semantic grounding [2], [4], [5], [11], [12]. Keep balance-critical control in fast RL/model-based loops [10], [15], [21], [22], [24].

## 8. Source-to-training transfer map

| Training need for AGIBOT X2 | Best source precedents | Practical transfer |
|---|---:|---|
| X2 whole-body loco-manipulation baseline | [2], [19] | Implement latent high-level policy + RL motion/locomotion policy; evaluate on egocentric tasks. |
| Manipulation/task pretraining | [1], [3], [4] | Use AgiBot World-style latent actions and task-diverse data; avoid demonstrator velocity ambiguity. |
| Fast locomotion iteration | [10], [21], [22], [24] | Massively parallel sim, privileged teacher, model-prior pretraining, minimalist rewards. |
| Terrain and obstacle robustness | [15], [18], [21], [22] | Online motion generation, multi-skill traversal, terrain randomization, recovery behaviors. |
| Whole-body imitation | [9], [12], [13], [19] | Retarget motions, separate upper/lower body or references/goals, train RL tracker. |
| Language/semantic task control | [11], [12], [13] | Convert language to latent whole-body verbs or motion references; do not issue raw joint language actions. |
| Contact-rich manipulation | [14], [20] | Use tactile/contact prediction and residual stabilization; preserve balance controller. |
| Multi-robot/swarm extension | No direct X2 source; compose [7], [16], [17], [20], [23] | Shared policy with robot IDs/embodiment conditioning, centralized training/decentralized execution, explicit collision/recovery metrics. |

## 9. Search notes

Searches covered AGIBOT X2, AgiBot World, Zhiyuan Robotics/AgiBot, arXiv AGIBOT results, humanoid sim-to-real reinforcement learning, Unitree G1/H1, Booster T1, Agility Digit, HumanoidBench, whole-body control, VLA, retargeting, tactile humanoid manipulation, and recent arXiv/conference-style works. WebSearch was partially unavailable due provider failure, so arXiv search pages and direct WebFetch retrievals were used for extraction.
