# Axis 5: Multi-Camera Architecture & Integration Feasibility

## Question
Which visual SLAM methods natively support multi-camera rigs, which require per-camera instances, and what are the practical integration considerations (hardware requirements, API surface, codebase maturity, open-source availability)?

## Findings

### 1. Landscape Overview

The visual SLAM ecosystem divides clearly into three tiers of multi-camera support: (a) systems designed from the ground up for arbitrary multi-camera rigs, (b) systems that natively handle stereo but can be extended to more cameras with effort, and (c) systems that are strictly single- or stereo-camera and require running separate instances per camera with external map merging (e.g., ICP).

The current ICP-based merging approach used in this project -- running independent SLAM instances per camera and fusing outputs -- is a valid but suboptimal strategy. Native multi-camera SLAM systems exploit cross-camera feature matching, shared bundle adjustment, and joint optimization to achieve better accuracy and lower drift than post-hoc merging. [Design and Evaluation of a Generic Visual SLAM Framework for Multi Camera Systems](https://arxiv.org/html/2210.07315v2)

---

### 2. Systems with Native Multi-Camera Support (Arbitrary N Cameras)

#### OpenVINS (Confidence: HIGH)
- Designed from the start for "an arbitrary number of asynchronous cameras" with a single IMU. [OpenVINS Documentation](https://docs.openvins.com/)
- Uses MSCKF framework; clones only the IMU poses of a "base camera" and interpolates for others, keeping computation tractable. [OpenVINS Research Paper](https://udel.edu/~ghuang/iros19-vins-workshop/papers/06.pdf)
- Online calibration of per-camera intrinsics and camera-IMU extrinsics (spatial and temporal). [OpenVINS Documentation](https://docs.openvins.com/)
- Practical caveat: a GitHub issue ([#130](https://github.com/rpng/open_vins/issues/130)) shows the maintainer confirmed multi-camera works but "has not been fully tested," and users hit `INVALID MAX CAMERAS` errors when exceeding built-in limits. The feature is functional but not production-hardened.
- **Stars:** 2.8k | **Forks:** 817 | **Language:** C++ | **License:** GPL-3.0 | **ROS:** Yes (ROS1+ROS2) | **GPU:** Not required | **Last release:** v2.7, June 2023. [GitHub - rpng/open_vins](https://github.com/rpng/open_vins)

#### NVIDIA cuVSLAM / Isaac ROS Visual SLAM (Confidence: HIGH)
- Supports up to 32 cameras (16 stereo pairs) in arbitrary geometric arrangements. [cuVSLAM Documentation](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/index.html)
- CUDA-accelerated; requires NVIDIA GPU (Jetson or discrete). Published tutorials for multi-RealSense and multi-HAWK setups. [Tutorial: Multi-camera Visual SLAM with RealSense](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/tutorial_multi_realsense.html)
- Hardware sync across cameras is strongly recommended for best performance. [cuVSLAM Paper](https://arxiv.org/html/2506.04359v2)
- **Stars:** 1.3k | **Forks:** 183 | **Language:** C++ | **License:** Apache-2.0 | **ROS:** Yes (ROS2) | **GPU:** Required (NVIDIA) | **Latest release:** v4.2.0, Feb 2026. [GitHub - NVIDIA-ISAAC-ROS/isaac_ros_visual_slam](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_visual_slam)
- **Important constraint for this project:** Requires NVIDIA GPU, which the current hardware lacks.

#### MultiCol-SLAM (Confidence: MEDIUM)
- Purpose-built for multi-fisheye camera rigs. Extends ORB-SLAM with Scaramuzza's generic camera model and multi-camera bundle adjustment ("MultiCol" model). [GitHub - urbste/MultiCol-SLAM](https://github.com/urbste/MultiCol-SLAM)
- Supports MultiKeyframes, multi-camera loop closing, and arbitrary rigidly-coupled camera configurations. [MultiCol-SLAM Paper](https://arxiv.org/abs/1610.07336)
- Codebase is dated (based on ORB-SLAM1/2 era, published 2016) with only 27 commits on master. Not actively maintained.
- **Stars:** 690 | **Forks:** 227 | **Language:** C++ | **License:** Not specified | **ROS:** No | **GPU:** Not required | **Last significant update:** ~2018 (inactive). [GitHub - urbste/MultiCol-SLAM](https://github.com/urbste/MultiCol-SLAM)

#### MultiCamSLAM (Confidence: MEDIUM)
- Models multi-camera rig as a "generalized camera"; computes cross-camera intra-match features from overlapping views. [GitHub - neufieldrobotics/MultiCamSLAM](https://github.com/neufieldrobotics/MultiCamSLAM)
- Generic framework for any number of cameras in any arrangement. Demonstrated accuracy improvement with increasing camera count. [Design and Evaluation of a Generic Visual SLAM Framework for Multi Camera Systems](https://arxiv.org/html/2210.07315v2)
- Relatively small community; limited adoption evidence.
- **Stars:** 173 | **Forks:** 33 | **Language:** C++ | **License:** MIT | **ROS:** Unknown | **GPU:** Not required | **Last commit:** April 2024. [GitHub - neufieldrobotics/MultiCamSLAM](https://github.com/neufieldrobotics/MultiCamSLAM)

#### SVO Pro (Confidence: MEDIUM)
- The UZH Robotics and Perception Group has published work on "Redesigning SLAM for Arbitrary Multi-Camera Systems" built on SVO Pro. [GitHub - uzh-rpg/rpg_svo_pro_open](https://github.com/uzh-rpg/rpg_svo_pro_open)
- Supports perspective and fisheye/catadioptric cameras in monocular or stereo setups. Multi-camera extensions exist in research but the open-source release may not fully expose them.
- **Stars:** 1.6k | **Forks:** 415 | **Language:** C++ (with CUDA components) | **License:** GPL-3.0 | **ROS:** Yes | **GPU:** Optional (CUDA path exists) | **Last commit:** Limited commits on master. [GitHub - uzh-rpg/rpg_svo_pro_open](https://github.com/uzh-rpg/rpg_svo_pro_open)

---

### 3. Systems with Stereo-Native Support (Extensible to Multi-Camera with Effort)

#### ORB-SLAM3 (Confidence: HIGH)
- Natively supports monocular, stereo, and RGB-D with pinhole and fisheye models. Multi-map and multi-session capable. [ORB-SLAM3 Paper](https://arxiv.org/abs/2007.11898)
- Does NOT natively support arbitrary multi-camera rigs. A community fork ("multi_orbslam3") implements a client-server architecture where each camera runs a separate ORB-SLAM3 client and a server merges maps. [GitHub - yutongwangBIT/multi_orbslam3](https://github.com/yutongwangBIT/multi_orbslam3)
- The core library has not been updated since December 2021; the codebase is mature but frozen.
- **Stars:** 8.4k | **Forks:** 3k | **Language:** C++ | **License:** GPL-3.0 | **ROS:** Community wrappers | **GPU:** Not required | **Last commit:** Dec 2021. [GitHub - UZ-SLAMLab/ORB_SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3)

#### VINS-Fusion (Confidence: HIGH)
- Supports mono+IMU, stereo+IMU, and stereo-only configurations. Does not natively support >2 cameras in a single instance. [GitHub - HKUST-Aerial-Robotics/VINS-Fusion](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion)
- A research extension "VINS-MultiCam" adds ASLfeat-based multi-camera support, but this is a separate research project, not merged into the main repo. [VINS-MultiCam Paper](https://www.researchgate.net/publication/394338905_VINS-MultiCam_An_ASLfeat-Based_MultiCam_Visual-Inertial_Odometry_Framework)
- Ranked top open-source stereo algorithm on KITTI Odometry Benchmark (as of 2019).
- **Stars:** 4.4k | **Forks:** 1.6k | **Language:** C++ | **License:** GPL-3.0 | **ROS:** Yes (ROS1) | **GPU:** Not required | **Last commit:** ~2020 (low activity). [GitHub - HKUST-Aerial-Robotics/VINS-Fusion](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion)

#### Basalt VIO (Confidence: MEDIUM)
- Natively stereo + IMU. Research has extended Basalt to multi-camera setups (optical flow extended to arbitrary camera count), but this is not in the official codebase. [Enhancing VIO Robustness and Accuracy in Challenging Environments](https://www.mdpi.com/2218-6581/14/6/71)
- Achieves 60 FPS stereo processing, 300Hz on Jetson Orin via Schur-complement marginalization. [Basalt VIO on Luxonis](https://docs.luxonis.com/software-v3/depthai/examples/rvc2/vslam/basalt_vio/)
- **Stars:** 858 | **Forks:** 236 | **Language:** C++ | **License:** BSD-3-Clause | **ROS:** Limited | **GPU:** Not required | **Primary repo:** GitLab. [GitHub - VladyslavUsenko/basalt](https://github.com/VladyslavUsenko/basalt)

#### RTAB-Map (Confidence: HIGH)
- Supports multiple synchronized RGB-D cameras when built with `DRTABMAP_SYNC_MULTI_RGBD=ON`. Includes demo launch files for dual-Kinect setups. [GitHub - introlab/rtabmap_ros (Issue #445)](https://github.com/introlab/rtabmap_ros/issues/445)
- Uses one "master camera" for visual odometry with additional cameras providing supplementary depth/loop closure data. Not a true joint multi-camera VO -- more of a multi-sensor fusion approach. [GitHub - introlab/rtabmap_ros (Issue #384)](https://github.com/introlab/rtabmap_ros/issues/384)
- Excellent ROS integration (ROS1+ROS2), actively maintained with latest release v0.23.1 (Oct 2025). [RTAB-Map Official Site](http://introlab.github.io/rtabmap/)
- **Stars:** 3.7k | **Forks:** 903 | **Language:** C++/C | **License:** BSD | **ROS:** Yes (deep integration) | **GPU:** Not required | **Last release:** Oct 2025. [GitHub - introlab/rtabmap](https://github.com/introlab/rtabmap)

#### Kimera-VIO / Kimera-Multi (Confidence: MEDIUM)
- Kimera-VIO supports stereo+IMU or mono+IMU. Kimera-Multi is a multi-ROBOT system (not multi-camera-on-one-robot). Each robot runs its own Kimera-VIO instance, and distributed loop closure merges maps. [GitHub - MIT-SPARK/Kimera-Multi](https://github.com/MIT-SPARK/Kimera-Multi)
- Produces semantic 3D mesh maps; runs on CPU. BSD-2-Clause license (more permissive than GPL alternatives). [GitHub - MIT-SPARK/Kimera-VIO](https://github.com/MIT-SPARK/Kimera-VIO)
- **Stars:** 1.8k | **Forks:** 465 | **Language:** C++ | **License:** BSD-2-Clause | **ROS:** Yes | **GPU:** Not required | **Last commit:** Jan 2025. [GitHub - MIT-SPARK/Kimera-VIO](https://github.com/MIT-SPARK/Kimera-VIO)

#### stella_vslam (OpenVSLAM fork) (Confidence: MEDIUM)
- Supports perspective, fisheye, and equirectangular camera models. Stereo support exists. No native multi-camera (>2) support. [GitHub - stella-cv/stella_vslam](https://github.com/stella-cv/stella_vslam)
- Actively maintained (last update Feb 2026). Users have reported difficulties localizing across different camera configurations. [stella_vslam Discussion #130](https://github.com/stella-cv/stella_vslam/discussions/130)
- **Stars:** ~654-1.1k | **Forks:** ~289-443 | **Language:** C++ | **License:** Multiple | **ROS:** Yes | **GPU:** Not required | **Last update:** Feb 2026. [GitHub - stella-cv/stella_vslam](https://github.com/stella-cv/stella_vslam)

---

### 4. Collaborative/Multi-Agent Systems (Server-Client Architecture)

#### COVINS / COVINS-G (Confidence: MEDIUM)
- Server-backend for collaborative SLAM; agents run VIO frontends (ORB-SLAM3, VINS-Fusion, SVO Pro) and send data to a central server for joint optimization. [GitHub - VIS4ROB-lab/covins](https://github.com/VIS4ROB-lab/covins)
- COVINS-G is frontend-agnostic, accepting any VIO/stereo odometry source. This architecture could be repurposed for multi-camera-on-one-robot by treating each camera as an "agent."
- **Stars:** 439 | **Forks:** 74 | **Language:** C++ | **License:** GPL-3.0 | **ROS:** Yes | **GPU:** Not required. [GitHub - VIS4ROB-lab/covins](https://github.com/VIS4ROB-lab/covins)

#### maplab 2.0 (Confidence: MEDIUM)
- Multi-session, multi-robot mapping framework. Map structure contains visual information from multi-camera systems. Includes ROVIOLI VIO frontend. [GitHub - ethz-asl/maplab](https://github.com/ethz-asl/maplab)
- Designed for offline map processing (merging, optimization, loop closure) rather than real-time multi-camera fusion.
- **Stars:** 2.8k | **Forks:** 746 | **Language:** C++ | **License:** Apache-2.0 | **ROS:** Yes | **GPU:** Not required | **Last release:** Nov 2022. [GitHub - ethz-asl/maplab](https://github.com/ethz-asl/maplab)

---

### 5. Master Comparison Table

| Method | Multi-Cam Native? | Max Cameras | Language | ROS | GPU Needed | Stars | Last Active | License | Maturity |
|---|---|---|---|---|---|---|---|---|---|
| **OpenVINS** | Yes (arbitrary N) | Arbitrary (tested ~3-4) | C++ | ROS1+2 | No | 2.8k | Jun 2023 | GPL-3.0 | Research-grade |
| **cuVSLAM** | Yes (up to 32) | 32 | C++ | ROS2 | Yes (NVIDIA) | 1.3k | Feb 2026 | Apache-2.0 | Production |
| **MultiCol-SLAM** | Yes (arbitrary N) | Arbitrary | C++ | No | No | 690 | ~2018 | Unspecified | Stale |
| **MultiCamSLAM** | Yes (arbitrary N) | Arbitrary | C++ | Unknown | No | 173 | Apr 2024 | MIT | Early-stage |
| **SVO Pro** | Yes (multi-cam research) | Multi | C++ | Yes | Optional | 1.6k | Limited | GPL-3.0 | Research-grade |
| **ORB-SLAM3** | No (stereo max) | 2 | C++ | Community | No | 8.4k | Dec 2021 | GPL-3.0 | Mature/frozen |
| **VINS-Fusion** | No (stereo max) | 2 | C++ | ROS1 | No | 4.4k | ~2020 | GPL-3.0 | Mature/frozen |
| **Basalt VIO** | No (stereo) | 2 | C++ | Limited | No | 858 | GitLab active | BSD-3 | Research-grade |
| **RTAB-Map** | Partial (multi-RGBD) | N (build flag) | C++/C | ROS1+2 | No | 3.7k | Oct 2025 | BSD | Production |
| **Kimera-VIO** | No (stereo) | 2 | C++ | Yes | No | 1.8k | Jan 2025 | BSD-2 | Research-grade |
| **stella_vslam** | No (stereo) | 2 | C++ | Yes | No | ~1k | Feb 2026 | Multiple | Active |
| **COVINS-G** | Multi-agent (repurposable) | N agents | C++ | Yes | No | 439 | Recent | GPL-3.0 | Research-grade |
| **maplab 2.0** | Multi-session (offline) | Multi | C++ | Yes | No | 2.8k | Nov 2022 | Apache-2.0 | Mature |

---

### 6. Practical Integration Considerations

**For a system currently using per-camera SLAM + ICP merging:**

1. **Best native multi-camera replacement (no NVIDIA GPU):** OpenVINS is the strongest candidate. It handles arbitrary cameras with a single IMU, performs joint state estimation, and has ROS1+2 support. However, its multi-camera path is under-tested and may require code-level debugging. Confidence: MEDIUM-HIGH.

2. **Best native multi-camera replacement (with NVIDIA GPU):** cuVSLAM is the most production-ready multi-camera SLAM, supporting up to 32 cameras with full NVIDIA toolchain support. However, this project lacks NVIDIA GPU hardware. Confidence: HIGH (if hardware available).

3. **Best hybrid approach (keep per-camera instances, improve merging):** COVINS-G offers a frontend-agnostic server backend that could replace ICP merging. Each camera runs its own VIO frontend (e.g., ORB-SLAM3 or VINS-Fusion), and COVINS-G performs joint optimization with loop closure detection across agents. This preserves the current architecture while adding proper SLAM-aware merging. Confidence: MEDIUM.

4. **RTAB-Map as a pragmatic middle ground:** Its multi-RGBD support with ROS2 integration makes it deployable with moderate effort. It uses one master camera for VO with supplementary cameras, which is a step up from fully independent instances. Confidence: MEDIUM-HIGH.

5. **Hardware requirements across the board:** All CPU-based methods (OpenVINS, ORB-SLAM3, VINS-Fusion, Basalt, Kimera) run on modern multi-core CPUs without GPU. Only cuVSLAM requires NVIDIA GPU. Memory requirements scale with map size and number of cameras. [Comparison of Modern Open-Source Visual SLAM Approaches](https://arxiv.org/pdf/2108.01654)

6. **Synchronization matters:** Every multi-camera system benefits from hardware-synchronized cameras. cuVSLAM documentation explicitly states that "accurate synchronization significantly impacts performance." [cuVSLAM Documentation](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/index.html) Software sync with proper timestamping is acceptable for slower-moving platforms.

7. **Licensing implications:** GPL-3.0 dominates (ORB-SLAM3, VINS-Fusion, OpenVINS, SVO Pro, COVINS). BSD/Apache alternatives include RTAB-Map (BSD), Kimera (BSD-2), cuVSLAM (Apache-2.0), maplab (Apache-2.0), MultiCamSLAM (MIT), and Basalt (BSD-3). For commercial deployment, BSD/Apache-licensed options are preferable.

8. **Codebase activity warning:** Several high-star projects are effectively frozen -- ORB-SLAM3 (last commit Dec 2021), VINS-Fusion (~2020), MultiCol-SLAM (~2018). Active projects include cuVSLAM (Feb 2026), stella_vslam (Feb 2026), RTAB-Map (Oct 2025), and Kimera (Jan 2025). [Various GitHub repositories cited above]

---

### 7. Conflicting Information

- **OpenVINS multi-camera status:** Documentation claims "arbitrary number of cameras" support, but GitHub issues show users hitting hard-coded camera limits and the maintainer acknowledging the feature is "not fully tested." The truth appears to be that the architecture supports it but the implementation has rough edges.
- **stella_vslam star count:** Different sources report between 654 and 1.1k stars, likely due to caching or counting methodology differences across GitHub API endpoints.
- **Basalt multi-camera:** Research papers claim multi-camera extension, but this does not appear in the official Basalt codebase (neither GitHub mirror nor GitLab primary).

---

### 8. Key Unknowns

1. **OpenVINS actual camera limit:** The hard-coded `max_cameras` constraint and its current value in the latest release is unclear. Would require code inspection to determine if it is trivially configurable or architecturally constrained.
2. **MultiCamSLAM ROS integration:** No clear evidence of ROS wrappers in the repository. Would need verification.
3. **SVO Pro multi-camera release status:** The research paper on "Redesigning SLAM for Arbitrary Multi-Camera Systems" exists, but whether this code is fully included in the open-source `rpg_svo_pro_open` release or held back is uncertain.
4. **cuVSLAM performance on non-Jetson NVIDIA GPUs:** Tutorials focus on Jetson and DGX Spark. Desktop GPU compatibility and performance is not well documented.
5. **COVINS-G real-time performance with >4 agents/cameras:** Benchmarks focus on multi-robot scenarios with 2-5 robots. Performance with, say, 8+ cameras on a single platform feeding one server is undocumented.
6. **Computational scaling:** How CPU and memory usage scales with camera count for OpenVINS, RTAB-Map, and MultiCamSLAM is not well benchmarked in available literature.
7. **MuJoCo simulation compatibility:** None of the surveyed systems document integration with MuJoCo simulation environments. Testing would require custom camera simulation bridges.

## Metadata
- Sources cited: 38
- Search queries executed: 13
- GitHub repositories analyzed: 13
- Confidence levels: 5 HIGH, 7 MEDIUM, 1 MEDIUM-HIGH
- Date of research: 2026-03-23
