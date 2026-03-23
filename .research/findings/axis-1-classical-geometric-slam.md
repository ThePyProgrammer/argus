# Axis 1: Classical Geometric Visual SLAM

## Question
What are all established geometric visual SLAM methods (feature-based, direct, and semi-direct) that can run in real-time, and what are their characteristics relevant to multi-camera integration?

## Findings

### 1. Feature-Based (Indirect) Methods

Feature-based visual SLAM methods extract keypoints (corners, blobs) from images and match them across frames to estimate motion and build maps. They produce sparse point-cloud maps and are generally the most mature and widely-deployed category.

#### ORB-SLAM Family (ORB-SLAM, ORB-SLAM2, ORB-SLAM3)

- **ORB-SLAM3** is the most complete system in this lineage. It is "the first real-time SLAM library able to perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fisheye lens models" [ORB-SLAM3 GitHub](https://github.com/UZ-SLAMLab/ORB_SLAM3). (Confidence: High)
- ORB-SLAM3 introduces the **Atlas multi-map system**, which maintains a set of disconnected maps with an active map for tracking. When tracking is lost, a new map is started and "seamlessly merged with previous maps when revisiting mapped areas" [ORB-SLAM3 Paper](https://arxiv.org/abs/2007.11898). (Confidence: High)
- ORB-SLAM3 is reported to be **2 to 5 times more accurate** than previous approaches on EuRoC and TUM-VI benchmarks [ORB-SLAM3 Paper](https://arxiv.org/abs/2007.11898). On TUM-VI Corridor sequences, it achieves ~0.02m position error [Comparison of modern open-source Visual SLAM approaches](https://ar5iv.labs.arxiv.org/html/2108.01654). (Confidence: High)
- **ORB-SLAM2** added stereo and RGB-D support over the original monocular ORB-SLAM, but lacks visual-inertial and multi-map capabilities. It still outperforms some recent methods on KITTI [Visual SLAM Benchmark Comparisons](https://www.researchgate.net/publication/344040390_Comparative_Analysis_of_Monocular_SLAM_Algorithms_Using_TUM_and_EuRoC_Benchmarks). (Confidence: High)
- **Multi-camera limitation**: The base ORB-SLAM3 does not natively support arbitrary multi-camera rigs with non-overlapping fields of view. However, extensions exist:
  - **multi_orbslam3** integrates collaborative SLAM (from CCM-SLAM) into ORB-SLAM3, allowing multiple cameras to perform collaborative SLAM [multi_orbslam3 GitHub](https://github.com/yutongwangBIT/multi_orbslam3). (Confidence: Medium)
  - **Multicam-SLAM** builds on ORB-SLAM2 for non-overlapping multi-RGB-D-camera SLAM, using ICP-based calibration between cameras and achieving 56-100mm trajectory accuracy where single-camera achieves 63-164mm [Multicam-SLAM](https://arxiv.org/html/2406.06374v1). (Confidence: High)
- **Output**: Sparse 3D point map + camera trajectory. No dense reconstruction.
- **Real-time**: Runs at frame rate on modern CPUs (i7 recommended) [ORB-SLAM3 GitHub](https://github.com/UZ-SLAMLab/ORB_SLAM3).

#### PTAM (Parallel Tracking and Mapping)

- PTAM pioneered the split of tracking and mapping into parallel threads, enabling real-time SLAM without requiring markers or pre-made maps [PTAM Project Page](https://www.robots.ox.ac.uk/~gk/PTAM/). (Confidence: High)
- Originally monocular only, limited to small AR workspaces.
- **S-PTAM** extended PTAM to stereo cameras with real-time parallel tracking and mapping [S-PTAM Paper](https://www.sciencedirect.com/science/article/abs/pii/S0921889015302955). **DS-PTAM** further extended it to distributed stereo multi-camera systems [DS-PTAM](https://www.researchgate.net/publication/326935067_DS-PTAM_Distributed_Stereo_Parallel_Tracking_and_Mapping_SLAM_System). (Confidence: Medium)
- Largely superseded by ORB-SLAM family for practical applications, but its architectural influence (parallel threads, keyframe-based mapping) persists in all modern SLAM systems.
- **Output**: Sparse point map.

#### OpenVSLAM / Stella-VSLAM

- OpenVSLAM is a versatile visual SLAM framework supporting monocular, stereo, and RGB-D cameras with perspective, fisheye, and **equirectangular** lens models [OpenVSLAM ACM](http://records.sigmm.org/?open-source-item=openvslam-a-versatile-visual-slam-framework). (Confidence: High)
- The original repository was taken down; **Stella-VSLAM** is the actively maintained community fork [Stella-VSLAM GitHub](https://github.com/stella-cv/stella_vslam). (Confidence: High)
- Based on ORB-SLAM/ORB-SLAM2 architecture but rewritten from scratch for improved scalability and readability.
- Supports equirectangular (360-degree) cameras, which is a unique advantage for multi-camera field-of-view coverage.
- **Output**: Sparse point map + camera trajectory.

#### RTAB-Map (Real-Time Appearance-Based Mapping)

- RTAB-Map is a comprehensive graph-based SLAM library supporting RGB-D, stereo, and LiDAR inputs with a memory management approach that ensures real-time constraints on large-scale environments [RTAB-Map Project Page](http://introlab.github.io/rtabmap/). (Confidence: High)
- **Native multi-camera support**: Supports multiple RGB-D cameras simultaneously (e.g., `rgbd_cameras=2` parameter) by converting stereo pairs to RGB-D representations [RTAB-Map Multi-Camera](https://answers.ros.org/question/269459/rtabmap-with-two-stereo-cameras/). (Confidence: High)
- Uses bag-of-words loop closure detection with a memory management system that limits active locations to maintain real-time performance [RTAB-Map Paper](https://arxiv.org/abs/2403.06341). (Confidence: High)
- Competitive accuracy on KITTI, EuRoC, and TUM RGB-D datasets [RTAB-Map Paper](https://arxiv.org/abs/2403.06341).
- **Output**: Dense 3D point cloud / occupancy grid (when using RGB-D), sparse map + pose graph. Uniquely produces both 2D occupancy grids and 3D point clouds.
- Deeply integrated with ROS/ROS2, making it the most deployment-ready option for robotics.

### 2. Direct Methods

Direct methods operate on raw pixel intensities rather than extracted features. They can use all pixels with sufficient gradient, making them robust in low-texture environments but sensitive to photometric changes (illumination, exposure).

#### LSD-SLAM (Large-Scale Direct Monocular SLAM)

- LSD-SLAM "directly operates on image intensities both for tracking and mapping instead of using keypoints." It produces **semi-dense depth maps** by filtering over many pixelwise stereo comparisons [LSD-SLAM Project Page](https://cvg.cit.tum.de/research/vslam/lsdslam). (Confidence: High)
- Runs in real-time on a CPU, and even on a smartphone [LSD-SLAM Paper](https://jakobengel.github.io/pdf/engel14eccv.pdf). (Confidence: High)
- **Stereo LSD-SLAM** extends to stereo cameras, running "in real-time at high frame rate on standard CPUs" by combining static stereo with temporal multi-view stereo [Stereo LSD-SLAM Paper](https://jakobengel.github.io/pdf/engel2015_stereo_lsdslam.pdf). (Confidence: High)
- An **omnidirectional extension** was developed for fisheye/wide-FOV cameras using the unified omnidirectional model [TUM Visual SLAM Research](https://cvg.cit.tum.de/research/vslam). (Confidence: Medium)
- **Output**: Semi-dense depth maps (more geometry than sparse methods, less than fully dense).
- **Limitation**: No native multi-camera rig support. No loop closure in the original version. Sensitive to illumination changes.

#### DSO (Direct Sparse Odometry)

- DSO is a direct method that samples pixels from high-gradient regions rather than using the entire frame, achieving a balance between computational efficiency and accuracy [DSO Paper](https://jakobengel.github.io/pdf/DSO.pdf). (Confidence: High)
- Unlike feature-based methods, DSO jointly optimizes photometric and geometric parameters in a windowed bundle adjustment, including camera intrinsics and exposure parameters.
- **Stereo DSO** extends DSO to stereo cameras, jointly optimizing all model parameters including intrinsic/extrinsic camera parameters. It "is superior to [Stereo LSD-SLAM and ORB-SLAM2]" on the KITTI testing set [Stereo DSO](https://cvg.cit.tum.de/research/vslam/stereo-dso). (Confidence: High)
- Runs in real-time on a single CPU core.
- **Output**: Sparse point cloud (despite being a direct method, the map is sparse due to point sampling strategy).
- **Limitation**: Visual odometry only -- no loop closure, no global map consistency. Drift accumulates over time.

#### LDSO (Direct Sparse Odometry with Loop Closure)

- LDSO extends DSO by adding loop closure detection and pose-graph optimization, addressing DSO's main weakness [LDSO Paper](https://arxiv.org/abs/1808.01111). (Confidence: High)
- Achieves "overall performance comparable to state-of-the-art feature-based systems, even without global bundle adjustment" [LDSO TUM Page](https://cvg.cit.tum.de/research/vslam/ldso). (Confidence: High)
- Uses a hybrid approach: favors corner features for repeatability (enabling BoW-based loop closure) while retaining DSO's direct tracking.
- However, comparative evaluation found LDSO showed "far worse results compared to sparse algorithms" in some benchmarks [Comparison of Visual SLAM Approaches](https://ar5iv.labs.arxiv.org/html/2108.01654). (Confidence: Medium -- this conflicts with LDSO authors' claims; likely dataset-dependent)
- **Output**: Sparse point cloud + pose graph.
- Monocular only. No native multi-camera support.

#### DTAM (Dense Tracking and Mapping)

- DTAM creates dense 3D surface models and uses them for dense whole-image camera tracking. It "relies not on feature extraction but dense, every pixel methods" [DTAM Paper](https://www.doc.ic.ac.uk/~ajd/Publications/newcombe_etal_iccv2011.pdf). (Confidence: High)
- **Requires GPU** for real-time operation -- algorithms are "highly parallelizable throughout and achieve real-time performance using current commodity GPU hardware" [DTAM Paper](https://ieeexplore.ieee.org/document/6126513/). (Confidence: High)
- Achieves superior tracking under rapid motion compared to feature-based methods due to dense model utilization.
- **Output**: Dense textured depth maps with millions of vertices.
- Monocular only. No multi-camera support. Limited to room-scale environments. No public maintained implementation.

#### Dense RGB-D Methods (KinectFusion, ElasticFusion, BundleFusion)

- **KinectFusion** pioneered real-time dense reconstruction using TSDF volumetric fusion with ICP-based camera tracking. Requires GPU. Limited to small scenes [RGB-D SLAM Review](https://arxiv.org/pdf/1805.07696). (Confidence: High)
- **ElasticFusion** extends to room-scale environments using surfel-based maps with non-rigid surface deformations for loop closure, "without pose graph optimisation or any post-processing steps" [ElasticFusion GitHub](https://github.com/mp3guy/ElasticFusion). (Confidence: High)
- **BundleFusion** achieves globally consistent reconstruction through parallel sparse feature + dense geometry + luminosity matching bundle adjustment in real-time with GPU [BundleFusion](https://www.researchgate.net/publication/324640458_BundleFusion_Real-Time_Globally_Consistent_3D_Reconstruction_Using_On-the-Fly_Surface_Reintegration). (Confidence: High)
- All three are **single RGB-D camera** systems. No native multi-camera rig support, though multiple depth streams could theoretically be fused at the TSDF/surfel level.
- **Output**: Dense 3D reconstruction (TSDF volumes or surfel maps).

### 3. Semi-Direct Methods

Semi-direct methods combine direct image alignment for tracking with feature-based methods for mapping/optimization, aiming for the speed of direct methods with the accuracy of feature-based approaches.

#### SVO / SVO 2.0 / SVO Pro

- SVO uses "direct methods to track and triangulate pixels that are characterized by high image gradients, but relies on proven feature-based methods for joint optimization of structure and motion" [SVO 2.0 Project Page](https://rpg.ifi.uzh.ch/svo2.html). (Confidence: High)
- **Exceptional speed**: Up to **400 fps on an i7 processor** (using less than 2 cores) and **100 fps on embedded processors** (Odroid XU4) [SVO 2.0 Project Page](https://rpg.ifi.uzh.ch/svo2.html). (Confidence: High)
- **Native multi-camera support**: SVO 2.0 explicitly supports monocular, stereo, wide-angle, and multi-camera configurations. "Using multiple cameras greatly improves resilience to on-spot rotations as the field of view of the system is enlarged and depth can be triangulated from inter-camera-rig measurements" [SVO TRO Paper](https://rpg.ifi.uzh.ch/docs/TRO16_Forster-SVO.pdf). (Confidence: High)
- **SVO Pro** adds visual-inertial fusion, loop closure, and global map optimization for monocular, stereo, and wide-angle cameras [SVO Pro Page](https://rpg.ifi.uzh.ch/svo_pro.html). (Confidence: High)
- Supports pinhole, fisheye, and catadioptric camera models [SVO 2.0 Project Page](https://rpg.ifi.uzh.ch/svo2.html).
- Open-source implementation available: [rpg_svo_pro_open](https://github.com/uzh-rpg/rpg_svo_pro_open).
- **Output**: Sparse 3D points + 6-DOF camera poses. Primarily a visual odometry system (SVO Pro adds SLAM capabilities).
- Successfully deployed on MAVs, automotive, and VR applications.

### 4. Visual-Inertial Methods (Feature-Based with IMU Fusion)

These systems tightly couple visual measurements with inertial data, significantly improving robustness and enabling metric scale recovery from monocular cameras.

#### VINS-Mono / VINS-Fusion

- **VINS-Mono** is a real-time monocular visual-inertial state estimator using optimization-based sliding window formulation. Features include IMU pre-integration, online extrinsic calibration, loop closure, and global pose graph optimization [VINS-Mono GitHub](https://github.com/HKUST-Aerial-Robotics/VINS-Mono). (Confidence: High)
- **VINS-Fusion** extends to support mono+IMU, stereo+IMU, stereo-only, and optional GPS fusion. It ranked as "the top open-sourced stereo algorithm on KITTI Odometry Benchmark" (as of Jan 2019) [VINS-Fusion GitHub](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion). (Confidence: High)
- Performs online spatial and temporal calibration between camera and IMU [VINS-Fusion GitHub](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion). (Confidence: High)
- **Output**: 6-DOF trajectory + sparse map + loop-closure-corrected poses.
- Multi-camera support limited to stereo configuration in VINS-Fusion; not arbitrary multi-camera rigs.

#### OpenVINS

- Supports an **arbitrary number of cameras** through its EKF-based architecture [OpenVINS Docs](https://docs.openvins.com/). (Confidence: High)
- Won first place at the IROS 2019 FPV Drone Racing VIO Competition [OpenVINS Docs](https://docs.openvins.com/). (Confidence: High)
- Provides five distinct feature representations and comprehensive online calibration of intrinsics and extrinsics [OpenVINS Docs](https://docs.openvins.com/).
- Out-of-the-box evaluation on EuRoC, TUM-VI, UZH-FPV, and KAIST Urban datasets.
- **Output**: Odometry + feature tracks + 3D positions.
- Memory usage: 1686-6490 MB RAM [Comparison Study](https://ar5iv.labs.arxiv.org/html/2108.01654). (Confidence: Medium)

#### Basalt

- Combines visual-inertial odometry (VIO) with visual-inertial mapping. Uses KLT optical flow on FAST features with tightly-coupled IMU pre-integration [Basalt TUM Page](https://cvg.cit.tum.de/research/vslam/basalt). (Confidence: High)
- Multi-camera setup support: "increases the field of view, allowing for the tracking of more features across frames, and improves the 3D position estimation of landmarks" [Basalt TUM Page](https://cvg.cit.tum.de/research/vslam/basalt). (Confidence: High)
- Outperforms other algorithms in per-frame timing comparisons with lowest memory usage (107-137 MB RAM) [Comparison Study](https://ar5iv.labs.arxiv.org/html/2108.01654). (Confidence: High)
- Includes camera, IMU, and motion capture calibration tools.
- **Output**: Camera trajectory + sparse landmarks.

#### OKVIS / OKVIS2

- OKVIS is a stereo-optimization-based visual-inertial odometry system [VIO Benchmark](https://rpg.ifi.uzh.ch/docs/ICRA18_Delmerico.pdf). (Confidence: High)
- **OKVIS2** adds "realtime scalable visual-inertial SLAM with loop closure" [OKVIS2 Paper](https://arxiv.org/pdf/2202.09199). (Confidence: High)
- Stereo camera + IMU configuration.
- **Output**: 6-DOF trajectory + sparse map.

#### MSCKF (Multi-State Constraint Kalman Filter)

- EKF-based VIO that maintains only a limited sliding window of poses, achieving "accuracy comparable to optimization-based methods under small computational load" [MSCKF GitHub](https://github.com/KumarRobotics/msckf_vio). (Confidence: High)
- Stereo MSCKF variant takes synchronized stereo images + IMU for real-time 6-DOF estimation.
- In multi-camera VIO designs, "the number of independent camera streams to process is considered as a design parameter" [Multi-Camera VIO](https://udspace.udel.edu/items/46413fb7-2a25-45f3-a552-19aa6cd329b0). (Confidence: Medium)

#### Kimera / Kimera2

- Open-source library for "real-time metric-semantic localization and mapping" with four modules: VIO, robust pose graph optimizer, 3D mesher, and dense metric-semantic reconstruction [Kimera ResearchGate](https://www.researchgate.net/publication/355988882_Kimera_An_Open-Source_Library_for_Real-Time_Metric-Semantic_Localization_and_Mapping). (Confidence: High)
- Runs in real-time on a CPU, producing 3D metric-semantic meshes from semantically labeled images.
- Has been extended to "use multiple cameras as well as external (e.g., wheel) odometry sensors" [Frontiers Review](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1347985/full). (Confidence: Medium)
- **Kimera2** improves robustness and accuracy for real-world deployment [Kimera2](https://www.researchgate.net/publication/382903047_Kimera2_Robust_and_Accurate_Metric-Semantic_SLAM_in_the_Real_World). (Confidence: Medium)
- **Output**: 3D metric-semantic mesh + trajectory.

#### MAVIS

- A recent (2024) system for "Multi-Camera Augmented Visual-Inertial SLAM using SE2(3) Based Exact IMU Pre-integration" [MAVIS](https://www.researchgate.net/publication/382992238_MAVIS_Multi-Camera_Augmented_Visual-Inertial_SLAM_using_SE_2_3_Based_Exact_IMU_Pre-integration). (Confidence: Low -- limited details found)
- Specifically designed for multi-camera visual-inertial SLAM.

---

### Comparison Table

| Method | Type | Sensors | Map Output | Loop Closure | Multi-Cam | Real-Time Platform | Open Source |
|--------|------|---------|------------|-------------|-----------|-------------------|-------------|
| **ORB-SLAM3** | Feature | Mono, Stereo, RGB-D, +IMU | Sparse points | Yes | Multi-map (not multi-rig) | CPU (i7) | Yes (GPL) |
| **PTAM** | Feature | Mono | Sparse points | No | No (S-PTAM: stereo) | CPU | Yes |
| **OpenVSLAM/Stella** | Feature | Mono, Stereo, RGB-D, 360 | Sparse points | Yes | No (but equirect.) | CPU | Yes (BSD) |
| **RTAB-Map** | Feature | RGB-D, Stereo, (+LiDAR) | Dense cloud + grid | Yes | Yes (native multi-RGB-D) | CPU | Yes (BSD) |
| **LSD-SLAM** | Direct | Mono, (Stereo variant) | Semi-dense | No (orig.) | No (stereo variant) | CPU | Yes (GPL) |
| **DSO** | Direct | Mono, (Stereo variant) | Sparse | No | No (stereo variant) | CPU (1 core) | Yes |
| **LDSO** | Direct+Feature | Mono | Sparse + pose graph | Yes | No | CPU | Yes (GPL) |
| **DTAM** | Direct (Dense) | Mono | Dense depth maps | No | No | GPU required | Partial |
| **ElasticFusion** | Direct (Dense) | RGB-D | Dense surfels | Yes (deform.) | No | GPU required | Yes |
| **BundleFusion** | Direct (Dense) | RGB-D | Dense TSDF | Yes (BA) | No | GPU required | Yes |
| **SVO/SVO Pro** | Semi-Direct | Mono, Stereo, Multi-cam | Sparse | Yes (Pro) | **Yes (native)** | CPU (400fps i7) | Yes |
| **VINS-Fusion** | Feature+IMU | Mono+IMU, Stereo+IMU, Stereo | Sparse | Yes | Stereo only | CPU | Yes |
| **OpenVINS** | Feature+IMU | Arbitrary N cameras + IMU | Sparse | SLAM mode | **Yes (N cameras)** | CPU | Yes (GPL) |
| **Basalt** | Feature+IMU | Stereo + IMU | Sparse | Mapping module | Yes (multi-cam) | CPU (fastest) | Yes |
| **OKVIS2** | Feature+IMU | Stereo + IMU | Sparse | Yes | Stereo | CPU | Yes |
| **MSCKF** | Feature+IMU | Stereo + IMU | No persistent map | No | Extensible to N | CPU (lightweight) | Yes |
| **Kimera** | Feature+IMU | Stereo + IMU | Semantic mesh | Yes | Extended to multi | CPU | Yes |

---

### Multi-Camera Integration Relevance

For a pipeline that currently uses **ICP-based merging of per-camera SLAM outputs**, the following methods are most relevant:

1. **SVO Pro** -- The only classical geometric SLAM with native, designed-in multi-camera rig support. Supports arbitrary camera configurations including non-overlapping setups. Its extreme speed (400 fps) leaves headroom for multi-camera processing.

2. **OpenVINS** -- Supports arbitrary number of cameras natively in its EKF framework. Best suited if IMU data is available. Handles online calibration of all camera extrinsics.

3. **Basalt** -- Native multi-camera VIO with the lowest memory footprint and fastest per-frame timing. Good for resource-constrained multi-camera setups.

4. **RTAB-Map** -- Native multi-RGB-D-camera support with ROS integration. The most straightforward for multi-camera deployment if RGB-D sensors are used.

5. **Multicam-SLAM** (ORB-SLAM2 extension) -- Directly addresses the non-overlapping multi-camera case using ICP-based inter-camera calibration, which aligns closely with the existing pipeline architecture [Multicam-SLAM](https://arxiv.org/html/2406.06374v1).

6. **ORB-SLAM3** -- While not natively multi-rig, its multi-map system with seamless map merging could replace ICP-based merging: each camera runs its own SLAM, and the Atlas system handles map fusion through place recognition.

Methods that would require the current ICP-merging approach to continue (running independent per-camera instances):
- DSO / Stereo DSO, LSD-SLAM, LDSO -- single-camera only, would need external map merging
- VINS-Fusion, OKVIS -- stereo pairs only, not arbitrary rigs
- ElasticFusion, BundleFusion -- single RGB-D sensor

---

### Key Unknowns

1. **Quantitative multi-camera benchmark results**: No standardized benchmark exists specifically for multi-camera rig SLAM. Most systems are evaluated on single-camera or stereo datasets (EuRoC, KITTI, TUM). The actual performance improvement from native multi-camera support vs. ICP-merged per-camera SLAM is poorly documented in the literature.

2. **SVO Pro multi-camera performance numbers**: While SVO 2.0/Pro claims multi-camera support, specific accuracy/performance numbers for configurations beyond stereo are difficult to find in public benchmarks.

3. **RTAB-Map multi-camera accuracy**: While RTAB-Map supports multiple RGB-D cameras, comparative accuracy data for multi-camera vs. single-camera configurations is sparse.

4. **Scalability to >4 cameras**: Most multi-camera evaluations use 2-4 cameras. How these systems perform with 6+ cameras (e.g., full surround coverage) is largely unexplored in public literature.

5. **ICP merging vs. native multi-camera**: Whether the ICP-based merging approach in the current pipeline is fundamentally limited compared to native multi-camera SLAM integration, or whether it achieves comparable results, is not well studied. The Multicam-SLAM paper suggests native integration improves tracking robustness (94-99% vs 21% in challenging corridors) but does not compare against ICP-merged pipelines specifically.

6. **LDSO performance discrepancy**: The LDSO authors claim performance "comparable to state-of-the-art feature-based systems" [LDSO Paper](https://arxiv.org/abs/1808.01111), but an independent comparison found "far worse results compared to sparse algorithms" [Comparison Study](https://ar5iv.labs.arxiv.org/html/2108.01654). This discrepancy may be dataset-dependent but is unresolved.

7. **Kimera multi-camera details**: The extension of Kimera to multiple cameras is mentioned in a review paper but specific implementation details and public availability are unclear.

8. **MAVIS availability and performance**: This 2024 multi-camera VI-SLAM system is too new to have established benchmark comparisons or public code availability confirmation.

## Metadata
- Sources cited: 38
- Search queries executed: 11
- Key source types: GitHub repositories, arxiv papers, project pages, survey papers, benchmark sites
- Confidence levels: High for well-established systems (ORB-SLAM3, DSO, SVO, VINS), Medium for extensions and comparative claims, Low for very recent systems (MAVIS)
- Date of research: 2026-03-23
