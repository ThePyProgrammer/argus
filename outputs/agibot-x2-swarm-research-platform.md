# AGIBOT X2 Platform Research for Humanoid Swarm Control

Accessed date for all sources: **2026-04-30**.

Scope: official/public AGIBOT X2 platform information, SDK/tooling references, manufacturer documentation, public ecosystem context, and independent/third-party reporting relevant to controlling a swarm of AGIBOT X2 humanoid robots. This report focuses on AGIBOT X2/X2 Ultra. Related AGIBOT/Galbot humanoid information is included only where X2-specific public information is missing or where ecosystem tooling appears relevant.

## 1. Numbered source list

1. **AGIBOT X2 series official product page** — https://www.agibot.com/products/X2 — accessed 2026-04-30.
2. **AGIBOT official website / company product and platform overview** — https://www.agibot.com/ — accessed 2026-04-30.
3. **AGIBOT Document Center** — https://www.agibot.com/DOCS — accessed 2026-04-30.
4. **AGIBOT Open Source Doc / open-source area** — https://www.agibot.com/DOCS/OS — accessed 2026-04-30.
5. **AimDK_X2 documentation home** — https://x2-aimdk.agibot.com/en/dev/ — accessed 2026-04-30.
6. **AimDK_X2: About AgiBot X2 overview** — https://x2-aimdk.agibot.com/en/dev/about_agibot_X2/index.html — accessed 2026-04-30.
7. **AimDK_X2: Robot Specifications** — https://x2-aimdk.agibot.com/en/dev/about_agibot_X2/robot_specifications.html — accessed 2026-04-30.
8. **AimDK_X2: Product line / part names** — https://x2-aimdk.agibot.com/en/dev/about_agibot_X2/part_name.html — accessed 2026-04-30.
9. **AimDK_X2: On-board Computer** — https://x2-aimdk.agibot.com/en/dev/about_agibot_X2/onboard_computer.html — accessed 2026-04-30.
10. **AimDK_X2: Sensor overview / FOV** — https://x2-aimdk.agibot.com/en/dev/about_agibot_X2/sensor_fov.html — accessed 2026-04-30.
11. **AimDK_X2: Secondary Development Interfaces** — https://x2-aimdk.agibot.com/en/dev/about_agibot_X2/SDK_interface.html — accessed 2026-04-30.
12. **AimDK_X2: Get the SDK** — https://x2-aimdk.agibot.com/en/dev/get_sdk/index.html — accessed 2026-04-30.
13. **AimDK_X2: Quick Start** — https://x2-aimdk.agibot.com/en/dev/quick_start/index.html — accessed 2026-04-30.
14. **AimDK_X2: Interface Description** — https://x2-aimdk.agibot.com/en/dev/Interface/index.html — accessed 2026-04-30.
15. **AimDK_X2: Operation Guide / Startup Guide** — https://x2-aimdk.agibot.com/en/dev/operation_guide/start_up_guide.html — accessed 2026-04-30.
16. **AimDK_X2: FAQ** — https://x2-aimdk.agibot.com/en/dev/faq/index.html — accessed 2026-04-30.
17. **AimDK_X2: Temporary Transitional Solutions Statement** — https://x2-aimdk.agibot.com/en/dev/temporary_transitional_solutions_statement/index.html — accessed 2026-04-30.
18. **AimDK_X2: Boundaries & Disclaimer for Secondary Development** — https://x2-aimdk.agibot.com/en/dev/boundaries_and_disclaimer/index.html — accessed 2026-04-30.
19. **AimDK_X2: Changelog** — https://x2-aimdk.agibot.com/en/dev/changelog/index.html — accessed 2026-04-30.
20. **AimRT framework official site** — https://aimrt.org/ — accessed 2026-04-30.
21. **Genie Studio official page** — https://genie.agibot.com/en/geniestudio — accessed 2026-04-30.
22. **AGIBOT World Dataset official site** — https://AGIBOT-world.com/ — accessed 2026-04-30.
23. **Humanoid-Robots.io: X2 by AgiBot** — https://www.humanoid-robots.io/robot/x2-by-agibot — accessed 2026-04-30.
24. **OriginOfBots: AgiBot X2 details/specifications/rating** — https://www.originofbots.com/robot/agibot-x2-by-agibot-details-specifications-rating — accessed 2026-04-30.
25. **HumanoidSpecs / AIWiki redirect target** — original URL https://humanoidspecs.com/robots/agibot-x2 redirected to https://aiwiki.ai/wiki/humanoid_robots — accessed 2026-04-30; usable X2-specific content was not retrieved.
26. **The Robot Report: AgiBot funding article** — https://www.therobotreport.com/agibot-raises-97-million-to-develop-humanoid-robots/ — accessed 2026-04-30; retrieval failed with HTTP 403.
27. **The Robot Report: AgiBot mass-production article** — https://www.therobotreport.com/agibot-starts-mass-production-humanoid-robots/ — accessed 2026-04-30; retrieval failed with HTTP 403.

## 2. Evidence table

| Claim | Source(s) | Confidence |
|---|---:|---|
| AGIBOT lists an **AGIBOT X2 series** product line with **X2** and **X2 Ultra** variants. | [1] | High |
| X2 is positioned as a “Fully Intelligent & Agile Robot” for social/reception, indoor autonomous movement, and service/demo scenarios. | [1] | High |
| X2 base differs from X2 Ultra: X2 has 25 DOF, no 3D LiDAR/RGB-D, and no secondary-development support; X2 Ultra has 30 DOF, 3D LiDAR/RGB-D, Orin NX compute, and secondary-development support. | [1] | High |
| AimDK_X2 is AGIBOT’s task-level extension framework for AgiBot X2, supporting Python/C++ and a ROS 2-based communication model. | [5], [14] | High |
| Official SDK package access is not fully self-service; current docs say to contact after-sales technical support, while future versions will support self-service download. | [12] | High |
| Public docs expose an X2 URDF archive named `X2_URDF-v1.3.0.zip`. | [12] | High |
| X2 Ultra has about 1.31 m height, about 39 kg mass, 30 actuated DOF, max speed 1.8 m/s, daily speed limit <=0.8 m/s, and ~2 h walking runtime at 0.5 m/s. | [7] | High |
| Official product page gives X2/X2 Ultra battery as ~500 Wh, while AimDK specs list battery capacity as about 421 Wh. | [1], [7] | High contradiction |
| X2 Ultra development compute unit PC2 is Jetson Orin NX, 157 TOPS, 16 GB memory, 512 GB storage. | [9] | High |
| Using PC1 as build/run machine is “strictly prohibited”; PC1 is identified as 10.0.1.40. | [9] | High |
| Secondary-development physical interfaces include 2x RJ45 1000 Base-T accessible to Orin NX and RK3588, plus 12 V/3 A and 48 V/5 A outputs. | [11] | High |
| Hardware interfaces include USB Type-A x2, USB Type-C x2, RJ45 x2, 12 V/3 A x1, and 48 V/5 A x1. | [7] | High |
| X2 Ultra sensors include RoboSense E1R LiDAR, Orbbec Gemini335 RGB-D, front stereo RGB, interaction RGB, rear RGB, chest/hip IMUs, and head touch sensor. | [10] | High |
| AimDK_X2 exposes control, interaction, and hardware-abstraction APIs; perception and fault/system management modules are marked coming soon. | [14] | High |
| Official startup requires practical operational constraints: >50% battery, clear space for supine startup, flat hard floor, and no supine-to-stand with gripper/dexterous hand installed. | [15] | High |
| AGIBOT ecosystem includes Document Center, Open Source Doc, AGIBOT World Dataset, AimRT Framework, Genie Studio, AIDEA/data services, X1 docs/assets, and X2 product links. | [2], [3], [4], [20], [21], [22] | Medium-High |
| AimRT is a modern robotics runtime framework with Python, ROS 2, gRPC, Zenoh, Iceoryx, MQTT, HTTP, TCP, UDP, MCAP, recording/playback, and executor/scheduling features. | [20] | Medium-High |
| Genie Studio spans data capture, datasets, training/fine-tuning, simulation/evaluation, deployment, multi-robot/multi-effector collection, task orchestration, remote operation, monitoring, and optimization; X2 was not visible in fetched content. | [21] | Medium |
| AGIBOT World public landing content fetched only showed “AGIBOT WORLD,” with no usable details on dataset scale/platform/X2. | [22] | Low for details; High for retrieval limitation |
| Third-party aggregator Humanoid-Robots.io lists X2 as 131 cm, 35 kg, 1.8 m/s, 3 kg payload, 28+ DOF, introduced in 2024; it inconsistently labels status “Production Ready” and “Prototype.” | [23] | Medium-Low |
| OriginOfBots lists estimated X2 price $13,500-$15,000, 2023 launch year, 4.0 rating, and multi-robot coordination as estimated; many claims are not independently verified. | [24] | Low-Medium |
| Independent reporting was attempted but The Robot Report pages were inaccessible via fetch (403), so no independent reporting claims are used here. | [26], [27] | High for access failure |

## 3. Findings by theme

### 3.1 Product identity and variants

AGIBOT’s official product page presents the **AGIBOT X2 series** as a “Fully Intelligent & Agile Robot” with two visible variants: **X2** and **X2 Ultra** [1]. The key platform distinction for development work is blunt: the **base X2 does not support secondary development**, while **X2 Ultra does** [1]. For any swarm-control research requiring direct robot APIs, sensor access, custom autonomy, or orchestration software, the public evidence points to **X2 Ultra**, not base X2, as the relevant purchasable/deployable platform [1], [5], [11], [14].

Official pages and docs also refer to comparison labels such as **X2 Ultra Edition** and **X2 Pro Explorer Edition** [8]. That creates naming clutter: product marketing says X2/X2 Ultra, while technical documentation uses Ultra Edition and sometimes compares against Pro Explorer. Treat model naming as a procurement/support confirmation item, not an implementation detail.

### 3.2 Physical platform and mobility envelope

The official AimDK robot-spec page lists **AgiBot X2 Ultra** at **1310 mm high**, **460 mm wide**, **210 mm long**, approximately **39 kg**, with **30 actuated DOF**: 1 neck, 7 per arm, 3 waist, and 6 per leg [7]. Arm span without end-effector is listed as **558 mm** [7]. Operating temperature is **-10°C to 40°C** [7].

Locomotion-relevant official figures include **1.8 m/s maximum speed**, a **daily-use speed limit <=0.8 m/s**, and roughly **2 hours of continuous walking at 0.5 m/s** [7]. For payload, the docs distinguish between **3 kg maximum payload in a specific posture** and **<=1 kg full-workspace payload**, both without end-effector [7]. That distinction matters for swarm tasks: assigning manipulative work based only on the headline 3 kg number would be unsafe or brittle.

Startup/operation docs show the robot is not a “press play anywhere” platform. Official startup paths include suspended, supine, and sitting startup, with constraints such as battery over **50%**, **0.5 m clear radius** for supine startup, a flat/hard floor, and avoiding supine-to-stand with a dexterous hand or gripper installed [15]. Operational states include zero-torque, standing preparation/position-control standing, stable standing/force-control standing, and locomotion/push-to-walk [15]. For a swarm, these state transitions imply a fleet manager must track per-robot readiness, battery, posture, mode, end-effector configuration, and local clearance before issuing group movement commands.

### 3.3 Compute architecture and developer target

X2 Ultra has three compute roles in the official onboard-computer docs: **PC1 motion control**, **PC3 interaction**, and **PC2 development** [9]. PC2 is the public secondary-development target and is specified as **Jetson Orin NX**, **157 TOPS**, **1024-core NVIDIA Ampere GPU with 32 Tensor Cores**, **8-core Arm Cortex-A78AE**, **16 GB memory**, and **512 GB storage** [9].

A non-negotiable caveat appears in the docs: using **PC1** as the build/run machine is **strictly prohibited**; PC1 is identified as **10.0.1.40** [9]. Swarm-control architecture should therefore avoid placing custom orchestration workloads on the motion-control computer. Use PC2 for onboard autonomy/agents and an external fleet coordinator for multi-robot task allocation, monitoring, and communications.

The official robot specs also list base computing boards **RK3588s + RK3588** and a secondary-development board **Orin NX 16 GB, 157 TOPS** [7]. Secondary-development interfaces include **2x RJ45** ports at **1000 Base-T**, accessible to **Orin NX and RK3588**, plus **12 V/3 A** and **48 V/5 A** power outputs [11]. General hardware interfaces include USB Type-A x2, USB Type-C x2, RJ45 x2, 12 V/3 A x1, and 48 V/5 A x1 [7].

### 3.4 Sensors and perception inputs

For X2 Ultra, the official sensor page provides unusually concrete sensor model data [10]:

- Chest LiDAR: **RoboSense E1R**, 940 nm, **120° horizontal FOV**, **90° vertical FOV** [10].
- RGB-D camera: **Orbbec Gemini335**, depth up to 1280x800, color up to 1920x1080, up to 60 fps, depth FOV 90°x65°, color FOV 94°x68° [10].
- Front stereo RGB camera: **SenYun SDS23NNS1**, up to 2064x1552, up to 40 fps, 156°x120° [10].
- Front interaction RGB camera: **SenYun SM5M12NJ**, up to 2608x1960, up to 30 fps, 110°x80° [10].
- Rear RGB camera: **SenYun SM3S23NS**, up to 2064x1552, up to 30 fps, 156°x120° [10].
- Chest and hip IMUs: **FORSENSE FSS-IMU16460-DM**, 6DoF MEMS, configurable to 1 kHz [10].
- Head touch sensor: **Awinic AW93208GQNR**, up to 250 kHz, with click/press/slide interactions [10].

The sensor stack is adequate on paper for indoor navigation, obstacle awareness, robot-local state estimation, rear awareness, and human interaction. However, the official AimDK interface page says **Perception Module** features such as **vision and SLAM** are **coming soon** [14]. The hardware exists; the public high-level SDK support for full perception/SLAM appears incomplete. A swarm stack should plan to either integrate its own ROS 2 perception/navigation pipeline on PC2, use lower-level sensor interfaces, or rely on vendor/private modules not documented publicly.

### 3.5 SDK and developer workflow

The official **AimDK_X2** documentation describes AimDK_X2 as an SDK/task-level extension framework for secondary developers on AgiBot X2, with high-level control, sensor access, interaction features, and application-building support [5]. The docs indicate support for **Python** and **C++**, and a **ROS 2-based** communication model [5], [14].

SDK access is only partially public. The **Get the SDK** page says developers need the **SDK package** and **URDF files**; it publicly references an **X2 URDF** archive named **`X2_URDF-v1.3.0.zip`** [12]. But the SDK package itself is currently obtained by **contacting after-sales technical support**, with self-service download planned for future versions [12]. That is the main gating item for an external research team: public docs are available, but full SDK bits may require vendor engagement.

Quick Start coverage includes reviewing user/safety guidance, basic system setup, robot/network connection, environment installation/configuration, running examples, and integrating/writing/building/running code [13]. Examples include getting current robot state and making the robot wave [13]. The fetched quick-start excerpt did not expose exact command lines or dependency versions [13].

Official API categories are [14]:

- **Control Module**: motion-mode switching, locomotion control, MC signal configuration/input-source management, preset motion execution, end-effector control including gripper/dexterous hand, and joint control [14].
- **Interaction Module**: voice, screen, LED strip, speech synthesis, audio playback/capture, emoji, video [14].
- **Hardware Abstraction Module**: sensor interfaces and PMU, including IMU, head touch, rear RGB, stereo camera, RGB-D, and LiDAR [14].
- **Coming Soon**: Fault & System Management, permission management, Perception Module, vision, SLAM [14].

For swarm control, the missing public Fault/System Management module is as important as the available motion APIs. Fleet operations need robust fault detection, health reporting, permissions, emergency-stop semantics, degraded-mode handling, and recovery. Public AimDK docs suggest those pieces are not yet complete in the SDK [14].

### 3.6 Version maturity and compatibility caveats

AimDK_X2 documentation is versioned at **0.9.0** in the robot-spec page title [7]. The changelog page lists v0.8.0, v0.8.1, v0.8.2, and v0.9.0, each with sections for newly released features, adjusted features, and deprecated/removed features, although fetched content did not reveal full feature-by-feature details [19].

The FAQ and temporary-transition pages show a platform still moving under users’ feet. Known issues/caveats include [16], [17]:

- Build/source mistakes can produce “Package ‘examples’ not found” [16].
- Example build failures may involve ROS/`colcon` installation/sourcing, dependency errors, or build cache cleanup [16].
- Silent examples over Ethernet require topic checks, correct standing mode for preset motions, and built-in voice system status for audio/TTS [16].
- Direct HAL motor control conflicts with the MC module unless MC is stopped first [16].
- Low battery can cause standing-mode/leg-response problems [16].
- Service calls can hang if request fields are incomplete [16].
- `cv_bridge`/OpenCV mismatch can occur if the Nvidia OpenCV build is used instead of Ubuntu OpenCV in the robot environment [16].
- Some older **McAction** state codes before v0.7.x are no longer supported [16], [17].
- A transitional workaround exists for disabling the built-in interaction system and using a custom voice system, with later restoration implied [17].

The practical read: AimDK_X2 is real and broad enough for development, but not a frozen industrial fleet-control API. Pin SDK/docs versions, maintain compatibility tests, and isolate swarm logic from vendor API churn.

### 3.7 Power, charging, and uptime

Official specs list runtime as about **2 hours** of continuous walking at **0.5 m/s**, charging time **<=1.5 h**, charging modes including direct charging, battery swapping, and optional auto-charging [7]. The product page says Ultra can use an optional auto-charging dock [1].

There is a battery-capacity inconsistency: official product page summary gives approximately **500 Wh** for X2/X2 Ultra [1], while the AimDK robot-spec page gives approximately **421 Wh** [7]. Use runtime and charge-time planning conservatively until vendor confirms final battery SKU.

For a swarm, battery and charge scheduling are not optional. A two-hour walking envelope, startup constraints, and low-battery behavior affecting standing/motion [16] imply a fleet manager must include reserve thresholds, staggered charging, battery-swap workflows, and mission abort/recovery policy.

### 3.8 End effectors and teleoperation

Official product and part-name pages indicate optional end effectors/add-ons such as **OmniPicker**, **OmniHand**, teleoperation accessories, and charging station accessories [1], [8]. The product page notes end-effectors like OmniHand/OmniPicker are for **X2 Ultra** and sold separately [1].

This matters because manipulation capability and startup safety vary by end-effector. The startup guide explicitly says not to use supine-to-stand if a dexterous hand or gripper is installed [15]. A swarm-control planner should treat end-effector configuration as part of each robot’s capability profile and safety constraints.

### 3.9 AGIBOT ecosystem context

The official AGIBOT website identifies the company as **AGIBOT Innovation (Shanghai) Technology Co., Ltd.** and lists multiple humanoid/general robot products including **A2 Ultra, A2 Lite, A2-W, X1, X2, G2, G1, D1 Ultra, D1 Pro, and C5** [2]. It also points to platform/tooling items: **Document Center**, **Open Source Doc**, **AGIBOT World Dataset**, **AimRT Framework**, **One-stop Development Platform for Embodied AI / Genie Studio**, integrated data services, and AGIBOT X1 resources [2], [3], [4].

The Document Center/Open Source area appears more X1-heavy than X2-heavy. Visible open-source items include **AGIBOT X1 Development Guide**, **AGIBOT World Dataset**, **AimRT Framework**, **Inference Code**, **Training Code**, and **AGIBOT_x1_hardware** [4]. X2 appears as a product/manual target, but no dedicated X2 open-source repository was visible in fetched open-source content [3], [4]. This supports the user’s instruction not to over-cover asset/code repos: for X2, the official SDK/docs pointer is AimDK_X2, while broader open-source assets skew toward X1.

**AimRT** is a robotics runtime framework with Python/ROS 2 support, middleware/plugins such as gRPC, Zenoh, Iceoryx, MQTT, HTTP, TCP, UDP, MCAP, and features like executors, scheduling, crash logging, topic logging, and record/playback [20]. It does not explicitly mention AGIBOT in the fetched content, but AGIBOT links it from its open-source ecosystem [4], [20]. For a swarm-control architecture, AimRT may be relevant as a runtime/middleware layer, but public evidence does not show X2-specific AimRT integration.

**Genie Studio** is AGIBOT’s all-in-one embodied-intelligence development platform spanning data capture, datasets, model training/fine-tuning, simulation/evaluation, deployment, multi-robot/multi-effector collection, human-in-the-loop QA, task orchestration, remote operation, monitoring, and optimization [21]. X2 was not mentioned in fetched Genie Studio content [21]. It may be strategically relevant for model/data workflows or multi-robot data collection, but it should not be assumed to be an X2 fleet-control API without vendor confirmation.

**AGIBOT World Dataset** content retrieved from the landing page was too sparse to use: only “AGIBOT WORLD” was visible, with no reliable public details on scale, robot platform, or X2 relevance from the fetched content [22].

### 3.10 Third-party and independent reporting

Third-party aggregators provide some additional context but should not be treated as authoritative.

Humanoid-Robots.io lists X2 as **131 cm**, **35 kg**, **1.8 m/s**, **3 kg payload**, modular electric actuation, and **28+ DOF**, with capabilities such as bipedal locomotion, AI-driven control, dexterous manipulation, emotional expression, hands/legs, and vision sensors [23]. It cites AGIBOT product/manufacturer pages, but it also labels status inconsistently as both **“Production Ready”** and **“Prototype”**, and lists price as N/A [23].

OriginOfBots lists AgiBot X2 with a **2023** launch year, estimated **$13,500-$15,000** price, 4.0 rating, use cases including security patrol, assembly help, elder care, entertainment, research, and logistics support, and estimated multi-robot coordination [24]. It also includes claims about Xyber-Edge, Xyber-DCU, Xyber-BMS, advanced motion demos, and emotion-aware interaction [24]. Because several values are marked estimated and source attribution is weak, use these only as market-intelligence hints, not engineering inputs.

Independent reporting from The Robot Report was attempted for AgiBot funding and mass production context, but both pages returned HTTP 403 through the available fetch path [26], [27]. Therefore this report does not rely on independent reporting claims from those pages.

## 4. Swarm-control implications

1. **Target X2 Ultra, not base X2.** Public official materials say base X2 lacks secondary-development support; X2 Ultra has the sensors, Orin NX board, and SDK-facing development path needed for custom swarm control [1], [9], [11], [14].

2. **Use PC2 as the onboard agent host.** PC1 is motion-control and explicitly off-limits for build/run workloads [9]. A sane architecture is: PC2 per-robot autonomy/safety adapter + external fleet coordinator + vendor motion/interaction/HAL APIs through AimDK_X2.

3. **Expect ROS 2 integration, but verify exact distro and package versions from the SDK package.** Public docs mention ROS 2, Python/C++, `colcon`, topics, and ROS-related troubleshooting [5], [14], [16]. Exact install commands and SDK package contents appear gated behind after-sales support [12], [13].

4. **Plan around incomplete public perception and fault APIs.** Hardware sensors are documented, but Perception and Fault/System Management modules are marked coming soon [10], [14]. For swarm reliability, bring your own fleet health layer, watchdogs, logging, fault taxonomy, and possibly perception/navigation stack.

5. **Battery/charging is a first-class scheduling problem.** Around two hours walking at 0.5 m/s and <=1.5 h charge time means task allocation must include energy budgets, charging queues, swaps, and reserve thresholds [7].

6. **Treat operation state as part of the fleet model.** Standing mode, locomotion mode, zero-torque, controller/app state, startup path, surface condition, end-effector installation, and low-battery behavior all affect whether a robot can safely accept commands [15], [16].

7. **Version-pin and regression-test all vendor API calls.** AimDK_X2 is versioned and active, but v0.9.0-era docs show deprecated/removed features, transitional workarounds, unsupported older McAction codes, and coming-soon modules [16], [17], [19].

8. **Do not over-assume open-source availability for X2.** AGIBOT has open-source ecosystem material, but fetched public open-source docs visibly emphasize X1, AGIBOT World, and AimRT rather than a public X2 SDK repository [3], [4], [12].

## 5. Contradictions and gaps

### Contradictions

- **Battery capacity conflict:** AGIBOT product page reports about **500 Wh**, while AimDK robot specs report about **421 Wh** [1], [7]. Runtime is consistently about 2 hours at 0.5 m/s, but capacity should be confirmed for the exact delivered SKU.
- **Weight/model conflict in third-party listings:** Official docs say X2 Ultra is about **39 kg** [7], while Humanoid-Robots.io lists X2 as **35 kg** [23]. This likely reflects base X2 vs Ultra, but third-party pages do not cleanly separate variants.
- **DOF conflict across sources:** Official product page distinguishes **25 DOF X2** and **30 DOF X2 Ultra** [1]; AimDK specs focus on **30 DOF** X2 Ultra [7]; third-party Humanoid-Robots.io says **28+ DOF** [23]. Use official variant-specific values.
- **Maturity/status conflict in aggregator:** Humanoid-Robots.io simultaneously shows **Production Ready** and **Prototype** [23]. Official AGIBOT page says partner recruitment is open and warns some demos are simulated/final product may differ [1]. Treat production maturity as unresolved until procurement/vendor confirmation.
- **Launch-year conflict:** OriginOfBots says 2023 [24], Humanoid-Robots.io says 2024 [23]. Official fetched pages did not provide a clear launch date.

### Gaps

- **SDK package is not publicly downloadable in the fetched docs.** Official docs say contact after-sales support; self-service download is future work [12].
- **No public X2 fleet/swarm API found.** AimDK_X2 appears robot-local. Public docs do not show fleet orchestration, multi-robot coordination APIs, central scheduler, shared map service, or fleet safety layer [5], [14].
- **Fault/system management is coming soon.** This is a major gap for multi-robot deployment [14].
- **Perception/SLAM module is coming soon.** Sensors are documented, but high-level perception/navigation support is not yet public in AimDK_X2 [10], [14].
- **Disclaimers page content was not retrievable in detail.** Only the existence of a Boundaries & Disclaimer section was confirmed through fetched content, not the actual legal/safety constraints [18].
- **Changelog details were sparse.** Version headings were visible, but not full feature-by-feature changes [19].
- **AGIBOT World details were sparse.** Fetched landing content did not provide dataset scale/platform/X2 relevance [22].
- **Independent reporting could not be used.** The Robot Report pages returned 403 via fetch [26], [27].
- **Galbot-specific information was not found in the X2-focused official materials fetched.** Public AGIBOT materials use AGIBOT/Zhiyuan branding; do not conflate Galbot details with X2 without a separate source.

## 6. Bottom line for the deep-research workflow

The public official record is strong enough to establish that **AGIBOT X2 Ultra** is a plausible humanoid platform for custom research development: it has documented compute, sensors, physical interfaces, Python/C++ ROS 2 SDK surfaces, and concrete motion/interaction/HAL API categories [1], [5], [7], [9], [10], [11], [14]. It is not strong enough to establish an off-the-shelf **swarm-control platform**. The public stack looks robot-local, SDK access is still mediated through support, and the exact modules a fleet operator most needs — perception/SLAM and fault/system management — are publicly marked unfinished [12], [14].

For a swarm of X2 humanoids, the lowest-risk research plan is to treat AimDK_X2 as the per-robot adapter layer, place custom autonomy on PC2, keep PC1 untouched, build external fleet management around robot state/mode/battery/fault telemetry, and verify missing SDK details directly with AGIBOT before committing to architecture or procurement [9], [12], [14], [15], [16].
