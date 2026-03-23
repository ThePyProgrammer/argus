# Research Plan

## Depth Configuration
- **Depth**: standard
- **Target axes**: 5
- **Follow-up policy**: 1 follow-up if gaps found

## Topic
Systematic literature review of visual SLAM methodologies suitable for integration into a multi-camera SLAM pipeline that currently uses ICP-based merging of per-camera SLAM outputs. Real-time only. No LiDAR.

## Research Axes

### Axis 1: Classical Geometric Visual SLAM
- **Question**: What are all established geometric visual SLAM methods (feature-based, direct, and semi-direct) that can run in real-time, and what are their characteristics relevant to multi-camera integration?
- **Search Strategy**: Search for feature-based SLAM (ORB-SLAM, ORB-SLAM2, ORB-SLAM3, PTAM, RTAB-Map), direct methods (DSO, LSD-SLAM, DTAM), semi-direct methods (SVO, SVO2), and any other classical geometric approaches. For each, find: sensor support, output representation, real-time benchmarks, multi-camera capability.
- **Source Priority**: Original papers, GitHub repositories, benchmark results on TUM/EuRoC/KITTI, survey papers (e.g., Taketomi et al., Cadena et al.)
- **Exclusions**: LiDAR-based methods, offline-only methods, methods with no public implementation
- **Output Format**: Narrative overview per sub-category (feature-based, direct, semi-direct) with embedded comparison table
- **Target Length**: 4-6 paragraphs of narrative + 1 comparison table covering all methods

### Axis 2: Deep Learning & End-to-End Visual SLAM
- **Question**: What deep learning-based visual SLAM and visual odometry methods exist that can run in real-time, and how do they compare to classical methods in accuracy, robustness, and output format?
- **Search Strategy**: Search for DROID-SLAM, DPVO (Deep Patch Visual Odometry), TartanVO, DeepV2D, BA-Net, Deep Virtual Stereo Odometry, DynaSLAM, methods using SuperPoint/SuperGlue/LightGlue for feature extraction within SLAM frameworks, any hybrid classical+learned approaches. Check for real-time variants and GPU requirements.
- **Source Priority**: arXiv papers (2020-2026), CVPR/ICCV/ECCV proceedings, GitHub repos with star counts and recent activity, benchmark leaderboards
- **Exclusions**: Methods that are purely visual odometry without mapping (unless mapping can be trivially added), offline-only methods, methods with no code release
- **Output Format**: Narrative analysis of the learned SLAM landscape + comparison table
- **Target Length**: 4-6 paragraphs + 1 comparison table

### Axis 3: Neural Scene Representation SLAM
- **Question**: What neural implicit and explicit representation SLAM methods (NeRF-based, Gaussian Splatting-based, voxel-based) exist, which can run in real-time, and what are their output representations?
- **Search Strategy**: Search for NeRF-SLAM variants (iMAP, NICE-SLAM, Orbeez-SLAM, ESLAM, Co-SLAM, Point-SLAM), Gaussian Splatting SLAM (SplaTAM, MonoGS, Gaussian-SLAM, Photo-SLAM, RTG-SLAM), voxel/TSDF-based (vox-fusion, SHINE-Mapping). For each: real-time capability, output format (implicit field, Gaussians, TSDF), GPU memory requirements.
- **Source Priority**: arXiv papers (2022-2026), CVPR/ECCV/NeurIPS proceedings, GitHub repos, real-time demo videos/benchmarks
- **Exclusions**: Methods that require minutes per frame, methods with no code release, pure novel view synthesis without SLAM/pose estimation
- **Output Format**: Narrative by sub-category (NeRF-based, Gaussian-based, voxel-based) + comparison table
- **Target Length**: 4-6 paragraphs + 1 comparison table

### Axis 4: Output Representations & ICP-Merge Compatibility
- **Question**: For each class of SLAM method, what is the native output representation, and how compatible is it with ICP-based or other point-cloud registration methods for merging multi-camera outputs?
- **Search Strategy**: Categorize output types: sparse point clouds, dense point clouds, meshes, TSDFs, neural implicit fields, 3D Gaussians, occupancy grids. For each, research: ICP applicability (does ICP work on this representation?), alternative registration methods (pose-graph optimization, factor graphs, feature-based alignment, neural field merging), conversion pipelines (e.g., Gaussians → point cloud → ICP). Search for multi-map merging techniques in SLAM literature.
- **Source Priority**: Multi-robot SLAM papers, map merging literature, point cloud registration surveys, multi-session SLAM papers
- **Exclusions**: LiDAR-specific registration, methods that don't produce any 3D output
- **Output Format**: Structured analysis per representation type, with a compatibility matrix (representation × merge method)
- **Target Length**: 3-5 paragraphs + 1 compatibility matrix table

### Axis 5: Multi-Camera Architecture & Integration Feasibility
- **Question**: Which SLAM methods natively support multi-camera rigs, which require per-camera instances, and what are the practical integration considerations (hardware requirements, API surface, codebase maturity, open-source availability)?
- **Search Strategy**: For each method identified in Axes 1-3: check if it supports multi-camera natively (e.g., ORB-SLAM3 multi-cam, Kimera, VINS-Fusion). Catalog: GPU/CPU requirements, supported platforms, language (C++/Python), ROS integration, active maintenance (last commit date, issue response time), license. Search for multi-camera SLAM frameworks and benchmarks.
- **Source Priority**: GitHub repositories (stars, forks, last commit), ROS wiki/packages, robotics forums, deployment case studies
- **Exclusions**: Proprietary/closed-source solutions with no evaluation path, methods requiring specialized hardware beyond GPUs
- **Output Format**: Integration feasibility narrative + master comparison table with practical columns
- **Target Length**: 3-5 paragraphs + 1 master integration table

## Cross-Cutting Concerns
- **Real-time definition**: "Real-time" varies by sensor (30fps for cameras, 10fps may be acceptable for some). Each axis should note actual frame rates where available.
- **GPU dependency**: Many modern methods require CUDA GPUs — this is a recurring constraint that affects all axes.
- **Maturity spectrum**: Methods range from research prototypes to production-ready. Each axis should note maturity level.
- **The ICP question**: The current pipeline uses ICP for merging. Some methods may require replacing ICP entirely — this should be flagged, not excluded.

## Expected Synthesis Structure
1. **Executive Summary** — Key findings and top recommendations
2. **Taxonomy of Visual SLAM Methods** — Classification framework used
3. **Classical Geometric Methods** — from Axis 1
4. **Deep Learning Methods** — from Axis 2
5. **Neural Scene Representation Methods** — from Axis 3
6. **Output Representations & Merge Strategies** — from Axis 4
7. **Integration Feasibility Assessment** — from Axis 5
8. **Master Comparison Table** — unified table across all methods
9. **Recommendations** — tiered recommendations (safe bets, high-potential, experimental)
10. **References**

## Estimated Subagents
- Primary research: 5 subagents (one per axis)
- Expected follow-up: 0-1 gap-filling subagents
