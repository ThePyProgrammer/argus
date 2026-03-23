# Research Report: Visual SLAM Methodologies for Multi-Camera Pipeline Integration

*Generated: 2026-03-23*
*Research scope: Systematic literature review of all real-time visual SLAM methods suitable for integration into a multi-camera pipeline currently using ICP-based merging. No LiDAR. CPU-only hardware prioritized.*

## Executive Summary

This review catalogues **40+ real-time visual SLAM methods** across four paradigms — classical geometric, deep learning, neural scene representation, and hybrid approaches — evaluating each for integration into a multi-camera pipeline that merges per-camera outputs via ICP. The most critical finding is that **ICP is a poor merge strategy for the sparse point clouds** produced by most feature-based SLAM methods; pose-graph optimization over shared landmarks is both faster and more robust ([ORB-SLAM based ICP Registration](https://www.scitepress.org/Papers/2018/75352/75352.pdf)). For CPU-only deployment with 4+ cameras, the strongest candidates are **OpenVINS** (native N-camera support, 12.8ms/frame), **SchurVINS** (CVPR 2024, lowest CPU usage), and **SVO Pro** (55 FPS on ARM). The most practical upgrade path that preserves the existing ICP pipeline is to adopt a hybrid SLAM like **SL-SLAM** (ORB-SLAM3 + SuperPoint + LightGlue), which improves accuracy 43-57% while keeping the same sparse output format ([SL-SLAM](https://arxiv.org/html/2405.03413v2)). However, the architecturally superior approach is to replace per-camera-instance + ICP merging with either a native multi-camera SLAM or a collaborative backend like **COVINS-G**.

## Key Findings

1. **ICP is wrong for sparse point clouds.** Standard ICP struggles with the sparse outputs (hundreds to low thousands of points) from feature-based SLAM — convergence fails in low-density regions and accuracy degrades with low overlap ([Comparison of Point Cloud Registration Algorithms](https://www.mdpi.com/2078-2489/14/3/149)). Pose-graph optimization or feature-based alignment (DBoW2) should replace ICP for sparse merge.

2. **Hybrid classical+learned SLAM is the best drop-in upgrade.** SL-SLAM replaces ORB features with SuperPoint+LightGlue inside ORB-SLAM3, achieving 43-57% lower ATE on EuRoC while producing identical sparse point cloud output ([SL-SLAM](https://arxiv.org/html/2405.03413v2)). The ICP pipeline works unchanged.

3. **Native multi-camera SLAM dramatically outperforms per-camera merging.** Multicam-SLAM achieves 94-99% tracking rates where single-camera drops to 21% in challenging corridors ([Multicam-SLAM](https://arxiv.org/html/2406.06374v1)). Native multi-camera systems jointly optimize all cameras, eliminating the error introduced by independent tracking + post-hoc merging.

4. **CPU-only multi-instance is feasible but undercharacterized.** SVO Pro runs at 55 FPS on ARM Cortex-A9 using <2 cores ([SVO Pro](https://rpg.ifi.uzh.ch/svo_pro.html)). Four OpenVINS instances need ~8 threads and ~1.5 GB RAM on an 8-core CPU. However, no published study measures actual N-instance scaling with cache contention.

5. **3D Gaussian Splatting SLAM has reached real-time.** Photo-SLAM (>30 FPS, 2.5 GB VRAM), MGSO (>30 FPS monocular), and GPS-SLAM (150+ FPS) now achieve real-time operation ([MemGS comparison](https://arxiv.org/html/2509.13536v1), [GPS-SLAM](https://arxiv.org/abs/2509.11574)). Gaussian outputs can be merged via FPFH+ICP on centers followed by pose-graph optimization, as demonstrated by MAGiC-SLAM (CVPR 2025) ([MAGiC-SLAM](https://arxiv.org/html/2411.16785v1)).

6. **NVIDIA cuVSLAM is the most production-ready multi-camera solution** (up to 32 cameras, Apache-2.0 license) but requires NVIDIA GPU hardware ([cuVSLAM](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/index.html)).

7. **Most "multi-camera" claims have caveats.** OpenVINS supports arbitrary N cameras architecturally but the implementation has hard-coded limits and is "not fully tested" ([OpenVINS Issue #130](https://github.com/rpng/open_vins/issues/130)). SVO Pro's multi-camera research code may not be fully included in the open-source release. Basalt's multi-camera support exists only in research papers, not the official codebase.

8. **Two new methods worth immediate evaluation:** SchurVINS (CVPR 2024, ByteDance, lowest CPU among VIO methods, open source) ([SchurVINS](https://github.com/bytedance/SchurVINS)) and NGD-SLAM (IROS 2025, 56 FPS CPU-only dynamic SLAM) ([NGD-SLAM](https://github.com/yuhaozhang7/NGD-SLAM)).

---

## Detailed Analysis

### 1. Classical Geometric Visual SLAM

Classical methods remain the backbone of deployed visual SLAM systems. They divide into three sub-categories based on how they use image data.

#### Feature-Based (Indirect) Methods

Feature-based systems extract keypoints (ORB, FAST, etc.), match them across frames, and triangulate 3D landmarks. They produce **sparse point cloud maps** and are the most mature category.

**ORB-SLAM3** is the most complete system: it supports monocular, stereo, RGB-D, and visual-inertial modes with pinhole and fisheye lenses, and introduces the Atlas multi-map system that maintains disconnected maps and merges them via place recognition ([ORB-SLAM3 GitHub](https://github.com/UZ-SLAMLab/ORB_SLAM3)). It achieves 2-5x better accuracy than previous approaches on EuRoC and TUM-VI ([ORB-SLAM3 Paper](https://arxiv.org/abs/2007.11898)). However, it does not natively support arbitrary multi-camera rigs — only stereo pairs. The codebase is mature but frozen (last commit December 2021). A community fork, **multi_orbslam3**, adds client-server collaborative SLAM for multiple cameras ([multi_orbslam3](https://github.com/yutongwangBIT/multi_orbslam3)).

**RTAB-Map** stands out for native multi-RGB-D-camera support, deep ROS1/2 integration, and a memory management system that maintains real-time performance in large environments ([RTAB-Map](http://introlab.github.io/rtabmap/)). It produces both dense point clouds and occupancy grids — uniquely dual-format. It uses one "master camera" for visual odometry with supplementary cameras providing depth and loop closure data ([RTAB-Map Issue #384](https://github.com/introlab/rtabmap_ros/issues/384)). Actively maintained with latest release v0.23.1 (October 2025). However, it is too heavy for multi-instance deployment (500 MB-2 GB+ per instance).

**Stella-VSLAM** (community fork of OpenVSLAM) supports perspective, fisheye, and equirectangular (360-degree) cameras, making it interesting for maximizing field-of-view coverage without multiple cameras ([Stella-VSLAM GitHub](https://github.com/stella-cv/stella_vslam)). Actively maintained (February 2026).

#### Direct Methods

Direct methods operate on raw pixel intensities rather than extracted features. They can use all pixels with sufficient gradient, producing denser maps.

**DSO** (Direct Sparse Odometry) jointly optimizes photometric and geometric parameters in a windowed bundle adjustment, running in real-time on a single CPU core. However, it is visual odometry only — no loop closure, no global consistency ([DSO Paper](https://jakobengel.github.io/pdf/DSO.pdf)). **LDSO** adds loop closure to DSO but with conflicting performance reports: the authors claim accuracy "comparable to feature-based systems" ([LDSO Paper](https://arxiv.org/abs/1808.01111)), while an independent study found "far worse results" ([Comparison Study](https://ar5iv.labs.arxiv.org/html/2108.01654)). This discrepancy is likely dataset-dependent and remains unresolved.

Dense RGB-D methods (**KinectFusion**, **ElasticFusion**, **BundleFusion**) produce dense reconstructions ideal for ICP merging, but all require GPU and are limited to single RGB-D cameras ([ElasticFusion GitHub](https://github.com/mp3guy/ElasticFusion)).

#### Semi-Direct Methods

**SVO / SVO Pro** combines direct image alignment for tracking with feature-based methods for mapping. It achieves up to **400 FPS on an i7** and **55 FPS on ARM Cortex-A9** using less than 2 cores ([SVO 2.0](https://rpg.ifi.uzh.ch/svo2.html)). SVO 2.0 explicitly supports multi-camera configurations including non-overlapping setups, making it architecturally ideal for this pipeline. SVO Pro adds visual-inertial fusion, loop closure, and global map optimization ([SVO Pro](https://rpg.ifi.uzh.ch/svo_pro.html)). **Caveat:** It is unclear whether the multi-camera research code is fully included in the open-source `rpg_svo_pro_open` release.

#### Visual-Inertial Methods

**OpenVINS** supports an arbitrary number of cameras through its EKF/MSCKF architecture with online calibration of per-camera intrinsics and extrinsics ([OpenVINS Docs](https://docs.openvins.com/)). It uses only 12.8ms per frame and 1-2 threads ([OpenVINS Timing](https://docs.openvins.com/eval-timing.html)). **Caveat:** The multi-camera path has hard-coded limits and the maintainer acknowledges it is "not fully tested" ([Issue #130](https://github.com/rpng/open_vins/issues/130)).

**Basalt VIO** achieves the fastest per-frame timing and lowest memory usage (107-137 MB RAM) of any VIO system benchmarked ([Comparison Study](https://ar5iv.labs.arxiv.org/html/2108.01654)). Research papers claim multi-camera support, but this does not appear in the official codebase.

**SchurVINS** (CVPR 2024, ByteDance) is a new filter-based VIO using Schur complement for O(n) update complexity, achieving near-lowest CPU usage among all tested VIO systems ([SchurVINS](https://openaccess.thecvf.com/content/CVPR2024/papers/Fan_SchurVINS_Schur_Complement-Based_Lightweight_Visual_Inertial_Navigation_System_CVPR_2024_paper.pdf)). Open source at [github.com/bytedance/SchurVINS](https://github.com/bytedance/SchurVINS).

**Kimera** produces real-time metric-semantic 3D meshes on CPU ([Kimera](https://www.researchgate.net/publication/355988882)). **Kimera-Multi** extends it to multi-robot scenarios with distributed loop closure, but is a multi-robot system, not multi-camera-on-one-robot ([Kimera-Multi GitHub](https://github.com/MIT-SPARK/Kimera-Multi)). **Warning:** Kimera-VIO's memory grows rapidly (~2 GB in 12 seconds at 60 Hz) ([Issue #69](https://github.com/MIT-SPARK/Kimera-VIO-ROS/issues/69)), making it unsuitable for multi-instance deployment.

| Method | Type | Sensors | Map Output | Loop Closure | Multi-Cam | Real-Time Platform | GPU | Open Source |
|--------|------|---------|------------|-------------|-----------|-------------------|-----|-------------|
| ORB-SLAM3 | Feature | Mono/Stereo/RGBD/VIO | Sparse | Yes | Multi-map only | CPU (i7) | No | GPL-3.0 |
| RTAB-Map | Feature | RGBD/Stereo | Dense + grid | Yes | Native multi-RGBD | CPU | No | BSD |
| Stella-VSLAM | Feature | Mono/Stereo/RGBD/360 | Sparse | Yes | No | CPU | No | Multiple |
| DSO | Direct | Mono/(Stereo) | Sparse | No | No | CPU (1 core) | No | Yes |
| LDSO | Direct+Feature | Mono | Sparse | Yes | No | CPU | No | GPL-3.0 |
| ElasticFusion | Direct (Dense) | RGB-D | Dense surfels | Yes | No | GPU required | Yes | Yes |
| SVO Pro | Semi-Direct | Mono/Stereo/Multi | Sparse | Yes | Native | CPU (400fps) | No | GPL-3.0 |
| OpenVINS | Feature+IMU | Arbitrary N + IMU | Sparse | SLAM mode | Native (N cams) | CPU | No | GPL-3.0 |
| Basalt | Feature+IMU | Stereo + IMU | Sparse | Mapping | Research only | CPU (fastest) | No | BSD-3 |
| SchurVINS | Feature+IMU | Stereo + IMU | Sparse | No | No | CPU (lowest) | No | Apache-2.0 |
| VINS-Fusion | Feature+IMU | Mono/Stereo + IMU | Sparse | Yes | Stereo only | CPU | No | GPL-3.0 |
| Kimera | Feature+IMU | Stereo + IMU | Semantic mesh | Yes | Multi-robot | CPU | No | BSD-2 |

---

### 2. Deep Learning & End-to-End Visual SLAM

Deep learning SLAM has evolved through three waves since 2021: end-to-end learned systems, hybrid classical+learned systems, and neural scene representation SLAM ([SLAM Meets NeRF Survey](https://www.mdpi.com/2032-6653/15/3/85)). For a multi-camera pipeline, the hybrid approach is most practical as it preserves existing output formats.

#### End-to-End Learned Systems

**DROID-SLAM** (NeurIPS 2021) remains the accuracy leader: on EuRoC monocular, it reduces ATE by 82% among zero-failure methods and 43% over ORB-SLAM3 ([DROID-SLAM](https://proceedings.neurips.cc/paper/2021/file/89fcd07f20b6785b92134bd6c1d0fa42-Paper.pdf)). It achieves zero failures across TartanAir, EuRoC, and TUM-RGBD. However, it requires ~20 GB VRAM (unverified — flagged as unsourced by gap analysis) and runs at ~20 FPS, making multi-camera deployment impractical.

**DPV-SLAM** (ECCV 2024) closes the gap to DROID-SLAM accuracy while using only 5 GB VRAM at 27-50 FPS — 2.5x faster ([DPV-SLAM](https://arxiv.org/html/2408.01654v1)). It adds loop closure via dBoW2 + pose graph optimization on CPU. Its sparse patch output could potentially feed an ICP merge step, though this is untested.

**DPVO** (NeurIPS 2023) achieves 60-120 FPS at 29-57% of DROID-VO's memory but is visual odometry only — no loop closure or mapping ([DPVO](https://proceedings.neurips.cc/paper_files/paper/2023/file/7ac484b0f1a1719ad5be9aa8c8455fbb-Paper-Conference.pdf)).

**SLAM-Former** (arXiv September 2025) unifies full SLAM into a single transformer at >10 Hz ([SLAM-Former](https://arxiv.org/abs/2509.16909)). Very recent, not yet peer-reviewed, no code release found.

#### Hybrid Classical + Learned Systems (Most Practical)

These systems replace feature extraction/matching in classical SLAM with deep learning while keeping the geometric backend. This is the **most directly relevant category** for the existing pipeline.

**SL-SLAM** (2024) replaces ORB features with SuperPoint and ORB matching with LightGlue throughout ORB-SLAM3's tracking, local mapping, and loop closure. Result: best ATE on 8-9/11 EuRoC sequences, average 43-57% lower ATE than ORB-SLAM3. Feature extraction is actually faster (7.27ms vs 11.98ms) via ONNX+GPU. Output format is identical to ORB-SLAM3 — the ICP pipeline works unchanged. ([SL-SLAM](https://arxiv.org/html/2405.03413v2))

**SELM-SLAM3** (2025) takes the same approach but deploys entirely in C++ via ONNX Runtime with no Python dependency, claiming 87.84% improvement over ORB-SLAM3 ([SELM-SLAM3 GitHub](https://github.com/banafshebamdad/SELM-SLAM3)). Small community (45 stars).

**SuperVINS** (2024) enhances VINS-Fusion with SuperPoint+LightGlue, yielding 39.6% ATE improvement on challenging sequences. Trade-off: deep features add overhead in easy conditions where ORB suffices ([SuperVINS](https://arxiv.org/html/2407.21348v2)).

**All hybrid systems require GPU** for the neural feature extraction step. SELM-SLAM3's ONNX Runtime approach may allow CPU execution at reduced speed, but this is not benchmarked.

#### Dynamic Environment SLAM

**NGD-SLAM** (IROS 2025) achieves 56 FPS on CPU-only by decoupling deep-learning masking from tracking via mask propagation, built on ORB-SLAM3 ([NGD-SLAM](https://github.com/yuhaozhang7/NGD-SLAM)). This is the first dynamic SLAM to achieve real-time on CPU without GPU, making it relevant for environments with moving objects.

| Method | Category | Input | FPS | GPU VRAM | EuRoC ATE (m) | Output | Loop Closure | Code |
|--------|----------|-------|-----|----------|---------------|--------|-------------|------|
| DROID-SLAM | End-to-end | Mono/Stereo/RGBD | ~20 | ~20 GB* | ~0.022 | Dense depth | Global BA | Yes |
| DPV-SLAM | End-to-end | Mono | 27-50 | 5-7 GB | 0.024 | Sparse patches | Yes (2 types) | Yes |
| DPVO | Learned VO | Mono | 60-120 | ~3 GB | Competitive | Patches (no map) | No | Yes |
| SL-SLAM | Hybrid | Mono/Stereo/VIO | ~36 | GPU needed | ~0.019-0.034 | Sparse points | Yes | Yes |
| SELM-SLAM3 | Hybrid (C++ ONNX) | RGBD | Real-time | GPU needed | 87% vs ORB-SLAM3 | Sparse points | Yes | Yes |
| SuperVINS | Hybrid | Mono+IMU | Real-time | GPU needed | Competitive | Sparse points | Yes | Yes |
| MASt3R-SLAM | Foundation model | Mono/Stereo/RGBD | 15 | RTX 4090 | SOTA | Dense points | Yes | Yes (2.8k★) |
| NGD-SLAM | Dynamic | Mono/Stereo/RGBD | 56 | CPU only | Competitive | Sparse points | Yes | Yes |

*\*DROID-SLAM VRAM figure is widely cited but no primary source URL was found in our research.*

---

### 3. Neural Scene Representation SLAM

Since iMAP (ICCV 2021), over 200 papers have appeared on neural SLAM ([NeRF+3DGS SLAM Survey](https://arxiv.org/html/2402.13255v2)). The field has progressed from pure MLPs → hybrid grid+MLP → 3D Gaussian Splatting → hybrid Gaussian+SDF, with each step improving rendering speed.

#### NeRF-Based Methods

NeRF-based SLAM couples a differentiable neural renderer with pose optimization. The key limitation is that ray marching is computationally expensive. Notable systems:

- **NICE-SLAM** (CVPR 2022): Hierarchical grid + MLP, occupancy output, ~5 GB GPU, <1 Hz system FPS — not real-time ([NICE-SLAM GitHub](https://github.com/cvg/nice-slam))
- **ESLAM** (CVPR 2023): Tri-plane architecture, TSDF output, 10x faster than iMAP ([ESLAM](https://www.idiap.ch/paper/eslam/))
- **Co-SLAM** (CVPR 2023): Hash grid encoding, SDF output, 10-17 Hz on RTX 3090 Ti — borderline real-time ([Co-SLAM](https://github.com/HengyiWang/Co-SLAM))
- **Loopy-SLAM** (CVPR 2024): Adds loop closure via point-cloud submaps, 70% reconstruction improvement over ESLAM ([Loopy-SLAM](https://github.com/eriksandstroem/Loopy-SLAM))
- **Orbeez-SLAM** (ICRA 2023): Uses ORB-SLAM2 for tracking + Instant-NGP for mapping — monocular RGB only, 800x faster than baseline dense NeRF ([Orbeez-SLAM](https://github.com/MarvinChung/Orbeez-SLAM))

**Verdict:** Most NeRF-based methods remain below real-time for full system operation and require significant GPU resources. Not recommended for this pipeline.

#### 3D Gaussian Splatting SLAM (Rapidly Maturing)

3DGS replaces volume rendering with rasterization-based splatting, offering dramatically faster rendering. Five concurrent 3DGS SLAM papers appeared in late 2023 ([NeRF+3DGS SLAM Survey](https://arxiv.org/html/2402.13255v2)).

Methods that have reached **real-time (>10 FPS system-wide)**:
- **Photo-SLAM** (2024): ORB-SLAM3 tracking + 3DGS mapping, >30 FPS, 2.5-3.2 GB VRAM ([MemGS comparison](https://arxiv.org/html/2509.13536v1))
- **MGSO** (3DV 2025): DSO tracking + 3DGS mapping, >30 FPS monocular, ~8 GB, extremely compact maps (4.6 MB vs Photo-SLAM's 22.5 MB) ([MGSO](https://arxiv.org/html/2409.13055v3))
- **MemGS** (2025): Voxel-based Gaussian merging, >30 FPS, only 1.95-2.75 GB on Jetson AGX Orin ([MemGS](https://arxiv.org/html/2509.13536v1))
- **RTG-SLAM** (SIGGRAPH 2024): ~18 FPS, ~8.8 GB, opaque/transparent Gaussian classification ([RTG-SLAM](https://github.com/MisEty/RTG-SLAM))
- **GPS-SLAM** (2025): Hybrid SDF+Gaussian, **150+ FPS** — current speed leader by an order of magnitude ([GPS-SLAM](https://arxiv.org/abs/2509.11574))

Methods with **loop closure** (critical for large-scale): LoopSplat (3DV 2025, Gaussian submap registration) ([LoopSplat](https://github.com/GradientSpaces/LoopSplat)), Splat-SLAM (CVPR 2025 Workshop, global optimization) ([Splat-SLAM](https://openreview.net/forum?id=YKtbklD5MV)), Photo-SLAM (via ORB-SLAM3).

**Multi-agent Gaussian SLAM:** MAGiC-SLAM (CVPR 2025) demonstrates multi-agent map merging using FPFH for coarse registration, ICP refinement for loop constraints, and pose-graph optimization. Gaussians are aligned through corrected camera poses rather than direct Gaussian-to-Gaussian registration ([MAGiC-SLAM](https://arxiv.org/html/2411.16785v1)).

| Method | Year | Input | System FPS | GPU Memory | Loop Closure | Code |
|--------|------|-------|------------|------------|-------------|------|
| SplaTAM | 2024 | RGB-D | 0.15-0.28 | ~8 GB | No | Yes |
| MonoGS | 2024 | Mono/Stereo/RGBD | 1-10 | 10-13 GB | No | Yes |
| Photo-SLAM | 2024 | Mono/Stereo/RGBD | **>30** | 2.5-3.2 GB | Yes | Yes |
| RTG-SLAM | 2024 | RGB-D | **~18** | ~8.8 GB | No | Yes |
| MGSO | 2025 | Mono | **>30** | ~8 GB | No | Yes |
| MemGS | 2025 | Mono/RGBD | **>30** | **1.95-2.75 GB** | No | — |
| GPS-SLAM | 2025 | RGB-D | **150+** | N/R | No | Yes |
| LoopSplat | 2025 | RGB-D | N/R | N/R | **Yes** | Yes |

---

### 4. Output Representations & Merge Strategies

The current pipeline uses ICP to merge per-camera SLAM outputs. This section evaluates whether ICP is appropriate for each output type.

#### ICP Compatibility by Representation

| Representation | SLAM Methods | Direct ICP | ICP after Conversion | Better Alternative |
|---------------|-------------|-----------|---------------------|-------------------|
| **Sparse points** | ORB-SLAM3, VINS, DSO, SVO | **Poor** — low density causes convergence failure ([ICP Registration Study](https://www.scitepress.org/Papers/2018/75352/75352.pdf)) | N/A | Pose-graph optimization over shared landmarks |
| **Dense points/surfels** | ElasticFusion, RTAB-Map, DROID-SLAM | **Excellent** — native ICP domain | N/A | GICP with normals |
| **TSDF volumes** | KinectFusion, ESLAM, Co-SLAM, Vox-Fusion | N/A (volumetric) | **Good** via marching cubes | Direct TSDF volume merging (weighted averaging) |
| **Meshes** | Kimera, BundleFusion | **Good** (vertices as points) | N/A | Mesh-based GICP ([Mesh GICP](https://onlinelibrary.wiley.com/doi/abs/10.1002/rob.22032)) |
| **Neural implicit (NeRF)** | iMAP, NICE-SLAM, Co-SLAM | **N/A** (no geometry) | **Moderate** via marching cubes | Submap fusion (MNE-SLAM, Vox-Fusion++) |
| **3D Gaussians** | SplaTAM, Photo-SLAM, MonoGS | **N/A** (not point clouds) | **Good** via 3DGS-to-PC ([3DGS-to-PC](https://github.com/Lewis-Stuart-11/3DGS-to-PC)) | FPFH+ICP on centers + pose-graph (MAGiC-SLAM) |
| **Occupancy grids** | RTAB-Map, OctoMap | **Moderate** (grid-limited resolution) | N/A | Bayesian probability fusion ([Map Merging Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC7730201/)) |

#### Critical Implication

**The current pipeline's ICP merge is suboptimal for its likely inputs.** If the per-camera SLAM produces sparse point clouds (as most feature-based methods do), ICP is fundamentally the wrong tool. The research strongly suggests replacing ICP with:

1. **Pose-graph optimization** over shared feature observations (for sparse maps) — standard in multi-session/multi-robot SLAM
2. **GICP** (Generalized ICP with Gaussian probability models) if dense point clouds are available ([coVoxSLAM](https://arxiv.org/html/2410.21149v1))
3. **FPFH + RANSAC + ICP** pipeline for coarse-to-fine alignment of dense or Gaussian outputs ([MAGiC-SLAM](https://arxiv.org/html/2411.16785v1))

---

### 5. Multi-Camera Architecture Options

Three architectural strategies exist for multi-camera SLAM:

#### A. Native Multi-Camera (Single Instance, All Cameras)

| System | Max Cameras | CPU-Only | Maturity | Stars |
|--------|------------|---------|----------|-------|
| cuVSLAM | 32 | No (NVIDIA required) | Production | 1.3k |
| OpenVINS | Arbitrary (tested ~3-4) | Yes | Research (under-tested multi-cam) | 2.8k |
| MultiCamSLAM | Arbitrary | Yes | Early-stage | 173 |
| MultiCol-SLAM | Arbitrary (fisheye) | Yes | Stale (~2018) | 690 |
| SVO Pro | Multi (research) | Yes | Research (open-source unclear) | 1.6k |

A unified multi-camera SLAM on an Intel N100 handled 4 cameras at 848×480 / 20 FPS ([Multi-Camera SLAM](https://www.mdpi.com/2079-9292/14/23/4556)), showing this approach is more efficient than N separate instances.

#### B. Per-Camera Instances + Backend Merge (Current Architecture)

Run separate SLAM per camera, merge outputs externally. This is what the current pipeline does with ICP. Upgrades:

- **COVINS-G**: Frontend-agnostic server that jointly optimizes multiple VIO outputs. Each camera runs its own VIO frontend (ORB-SLAM3, VINS-Fusion, SVO Pro), and COVINS-G performs joint optimization with cross-agent loop closure ([COVINS-G GitHub](https://github.com/VIS4ROB-lab/covins)). This could replace ICP merging while preserving the per-camera-instance architecture.
- **ORB-SLAM3 Atlas**: Multi-map system that handles map fusion through place recognition. Could replace ICP if cameras have overlapping views ([ORB-SLAM3](https://arxiv.org/abs/2007.11898)).

#### C. Multi-Agent (Repurposed for Multi-Camera)

Multi-robot SLAM systems can be repurposed by treating each camera as an "agent":
- **COVINS-G** (most practical)
- **Kimera-Multi** (distributed loop closure)
- **maplab 2.0** (offline map merge, Apache-2.0) ([maplab GitHub](https://github.com/ethz-asl/maplab))

---

### 6. CPU-Only Multi-Instance Deployment

For running 4+ parallel SLAM instances without GPU:

| Method | Per-Frame (ms) | Threads | RAM/Instance | 4-Instance Feasibility |
|--------|---------------|---------|-------------|----------------------|
| SVO Pro | 2.5-10 | <2 | ~100-200 MB | **Excellent** |
| SchurVINS | 8-12 | 1-2 | ~150-300 MB | **Excellent** |
| OpenVINS | ~12.8 | 1-2 | ~200-400 MB | **Good** |
| Basalt | <10 | 2-3 | ~200-300 MB | **Good** |
| S-MSCKF | 15-20 | 1-2 | ~150-250 MB | **Good** |
| DSO | 20-30 | 1-2 | ~200-300 MB | Good (VO only) |
| ORB-SLAM3 | 25-33 | 3 | ~500 MB | Moderate (heavy) |
| NGD-SLAM | ~17.8 | 3 | ~400-500 MB | Good (dynamic scenes) |
| Kimera-VIO | varies | 3-4 | 500 MB-2 GB | **Poor** (memory explodes) |
| RTAB-Map | 30-100+ | 3-4+ | 500 MB-2 GB+ | **Poor** (too heavy) |

**Hardware recommendations:**

| Cameras | CPU | RAM | Best Methods |
|---------|-----|-----|-------------|
| 4 @ 15 FPS | 8-core/16-thread x86 | 16 GB | OpenVINS, SchurVINS, SVO Pro |
| 8 @ 15 FPS | 16-core/32-thread x86 | 32 GB | SVO Pro, SchurVINS, S-MSCKF |
| 4 @ 15 FPS (ARM) | 8-core ARM (e.g., RPi 5) | 8 GB | SVO Pro, S-MSCKF |

Sources: [SVO Pro benchmarks](https://rpg.ifi.uzh.ch/svo_pro.html), [OpenVINS timing](https://docs.openvins.com/eval-timing.html), [VIO comparison](https://ar5iv.labs.arxiv.org/html/2108.01654), [SchurVINS](https://openaccess.thecvf.com/content/CVPR2024/papers/Fan_SchurVINS_Schur_Complement-Based_Lightweight_Visual_Inertial_Navigation_System_CVPR_2024_paper.pdf)

---

## Master Comparison Table

| Method | Paradigm | Multi-Cam | GPU | FPS | Output | ICP Compatible | Loop Close | License | Maturity |
|--------|----------|-----------|-----|-----|--------|---------------|-----------|---------|----------|
| ORB-SLAM3 | Classical | No (stereo) | No | 30+ | Sparse | Poor | Yes | GPL-3.0 | Mature/frozen |
| SVO Pro | Semi-direct | Yes (native) | No | 400 | Sparse | Poor | Yes | GPL-3.0 | Research |
| OpenVINS | VIO | Yes (N cams) | No | 78+ | Sparse | Poor | SLAM mode | GPL-3.0 | Research |
| SchurVINS | VIO | No | No | 80+ | Sparse | Poor | No | Apache-2.0 | New (2024) |
| Basalt | VIO | Research only | No | 100+ | Sparse | Poor | Mapping | BSD-3 | Research |
| RTAB-Map | Feature | Partial | No | 10-30 | Dense+grid | Excellent | Yes | BSD | Production |
| VINS-Fusion | VIO | Stereo only | No | 30+ | Sparse | Poor | Yes | GPL-3.0 | Mature/frozen |
| NGD-SLAM | Dynamic | No | No | 56 | Sparse | Poor | Yes | — | New (2025) |
| SL-SLAM | Hybrid | No | Yes | ~36 | Sparse | Poor | Yes | — | New (2024) |
| DROID-SLAM | End-to-end | No | Yes (20GB) | ~20 | Dense | Good | BA | MIT | Mature |
| DPV-SLAM | End-to-end | No | Yes (5GB) | 27-50 | Sparse | Moderate | Yes | — | New (2024) |
| MASt3R-SLAM | Foundation | No | Yes (RTX4090) | 15 | Dense | Good | Yes | — | New (2025) |
| Photo-SLAM | 3DGS | No | Yes (2.5GB) | >30 | Gaussians | Convert | Yes | — | New (2024) |
| GPS-SLAM | 3DGS+SDF | No | Yes | 150+ | Hybrid | Convert | No | — | New (2025) |
| MemGS | 3DGS | No | Yes (2GB) | >30 | Gaussians | Convert | No | — | New (2025) |
| cuVSLAM | GPU-accel | Yes (32 cams) | Yes (NVIDIA) | RT | Sparse | N/A | Yes | Apache-2.0 | Production |
| COVINS-G | Backend | Multi-agent | No | N/A | Sparse | N/A | Yes | GPL-3.0 | Research |

---

## Confidence Assessment

### High Confidence
- ICP performs poorly on sparse point clouds — multiple independent sources confirm ([ICP Registration](https://www.scitepress.org/Papers/2018/75352/75352.pdf), [Registration Comparison](https://www.mdpi.com/2078-2489/14/3/149))
- ORB-SLAM3 accuracy and capabilities — extensively benchmarked ([ORB-SLAM3 Paper](https://arxiv.org/abs/2007.11898))
- SVO Pro speed on ARM (55 FPS) — reported by original authors with reproducible benchmarks ([SVO Pro](https://rpg.ifi.uzh.ch/svo_pro.html))
- SL-SLAM 43-57% improvement over ORB-SLAM3 — benchmarked on standard datasets with code available ([SL-SLAM](https://arxiv.org/html/2405.03413v2))
- DROID-SLAM accuracy leadership — peer-reviewed at NeurIPS with reproducible results ([DROID-SLAM](https://proceedings.neurips.cc/paper/2021/file/89fcd07f20b6785b92134bd6c1d0fa42-Paper.pdf))
- GPS-SLAM 150+ FPS — reported with benchmark data ([GPS-SLAM](https://arxiv.org/abs/2509.11574))
- cuVSLAM 32-camera support — documented in official NVIDIA docs ([cuVSLAM](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/index.html))
- CPU-only single-instance benchmarks for SVO, OpenVINS, Basalt — from published comparative studies

### Medium Confidence
- OpenVINS multi-camera "works but has rough edges" — based on GitHub issues, not systematic testing
- SELM-SLAM3 87% improvement claim — small community (45 stars), limited independent validation
- Neural SLAM FPS figures — self-reported by authors, varying test conditions, limited independent verification
- N-instance CPU scaling estimates — extrapolated from single-instance data, no published multi-instance study
- Basalt multi-camera support — claimed in papers but not in official code
- SVO Pro open-source multi-camera status — unclear whether research code is fully released

### Low Confidence / Unresolved
- DROID-SLAM exact VRAM requirement (~20 GB) — widely cited but no primary source URL found
- LDSO performance — contradictory claims from authors vs independent study, likely dataset-dependent
- Real-time latency of Gaussian-to-point-cloud conversion for online ICP — untested
- N-instance cache contention and memory bandwidth effects — completely uncharacterized
- SLAM-Former (Sep 2025) — not yet peer-reviewed, no code release
- MuJoCo integration for any SLAM system — no documentation found

---

## Recommendations

### Tier 1: Safe Bets (Proven, Deploy Now)

1. **Replace ICP with pose-graph optimization.** The single highest-impact change. ICP is fundamentally wrong for the sparse outputs your pipeline likely produces. Use DBoW2/DBoW3 for place recognition across cameras, build inter-camera loop closure constraints, and optimize a pose graph. This is how ORB-SLAM3 Atlas, COVINS-G, and every multi-robot SLAM system handles map merging.

2. **Adopt OpenVINS as primary SLAM backend (if IMU available).** Native N-camera support in a single instance eliminates the need for separate per-camera instances entirely. 12.8ms/frame, CPU-only, ROS1+2. Expect to debug the multi-camera path. ([OpenVINS](https://docs.openvins.com/))

3. **Or adopt SVO Pro for maximum speed margin.** 55 FPS on ARM gives enormous headroom for multi-camera processing. Native multi-camera research exists. CPU-only. ([SVO Pro](https://rpg.ifi.uzh.ch/svo_pro.html))

### Tier 2: High Potential (Promising, Evaluate)

4. **COVINS-G as a merge backend.** Keep per-camera SLAM instances but replace ICP with COVINS-G's joint optimization server. Frontend-agnostic — works with ORB-SLAM3, VINS-Fusion, or SVO Pro. ([COVINS-G](https://github.com/VIS4ROB-lab/covins))

5. **SL-SLAM as a per-camera accuracy upgrade.** Drop-in replacement for ORB-SLAM3 with 43-57% accuracy improvement. Same output format — existing merge pipeline (once fixed to use pose-graph instead of ICP) works unchanged. Requires GPU for SuperPoint/LightGlue. ([SL-SLAM](https://arxiv.org/html/2405.03413v2))

6. **SchurVINS for resource-constrained multi-instance.** Newest, lowest CPU usage among VIO methods, open source (Apache-2.0). No multi-camera native support — would need N instances + merge. ([SchurVINS](https://github.com/bytedance/SchurVINS))

### Tier 3: Experimental (Watch / Long-Term)

7. **3DGS SLAM (Photo-SLAM / GPS-SLAM / MemGS).** Real-time Gaussian SLAM is here, and MAGiC-SLAM shows multi-camera Gaussian merging works. But all require GPU, and the Gaussian-to-ICP conversion pipeline is untested for online operation. Monitor for CPU-capable variants.

8. **MASt3R-SLAM.** Foundation model approach — represents a paradigm shift. Currently 15 FPS on RTX 4090, too heavy for multi-camera. But the architecture will improve rapidly. ([MASt3R-SLAM](https://edexheim.github.io/mast3r-slam/))

9. **NGD-SLAM for dynamic environments.** If your cameras see moving objects (people, vehicles), this is the only CPU-only dynamic SLAM at 56 FPS. ([NGD-SLAM](https://github.com/yuhaozhang7/NGD-SLAM))

### Decision Framework

```
Do you have an NVIDIA GPU?
├── Yes → Evaluate cuVSLAM (32 cameras, production-ready)
│         If cuVSLAM doesn't fit → SL-SLAM per camera + COVINS-G merge
└── No → Do you have an IMU?
          ├── Yes → OpenVINS (native N-camera, single instance)
          │         Fallback: SchurVINS × N + pose-graph merge
          └── No → SVO Pro (native multi-cam, fastest CPU)
                    Fallback: ORB-SLAM3 × N + pose-graph merge
```

---

## Sources

### Primary Sources — Papers & Benchmarks
- [ORB-SLAM3 Paper](https://arxiv.org/abs/2007.11898) — Multi-map SLAM system with Atlas architecture
- [DROID-SLAM NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/file/89fcd07f20b6785b92134bd6c1d0fa42-Paper.pdf) — End-to-end learned SLAM accuracy leader
- [DPV-SLAM ECCV 2024](https://arxiv.org/html/2408.01654v1) — Efficient learned SLAM with loop closure
- [DPVO NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/7ac484b0f1a1719ad5be9aa8c8455fbb-Paper-Conference.pdf) — Fastest learned visual odometry
- [SL-SLAM 2024](https://arxiv.org/html/2405.03413v2) — Hybrid ORB-SLAM3 + SuperPoint + LightGlue
- [SuperVINS 2024](https://arxiv.org/html/2407.21348v2) — Hybrid VINS-Fusion + SuperPoint + LightGlue
- [SchurVINS CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Fan_SchurVINS_Schur_Complement-Based_Lightweight_Visual_Inertial_Navigation_System_CVPR_2024_paper.pdf) — Lowest-CPU VIO system
- [NGD-SLAM IROS 2025](https://arxiv.org/abs/2405.07392) — CPU-only dynamic SLAM at 56 FPS
- [MAGiC-SLAM CVPR 2025](https://arxiv.org/html/2411.16785v1) — Multi-agent Gaussian SLAM merging
- [MNE-SLAM CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Deng_MNE-SLAM_Multi-Agent_Neural_SLAM_for_Mobile_Robots_CVPR_2025_paper.pdf) — Multi-agent neural SLAM
- [Multicam-SLAM 2024](https://arxiv.org/html/2406.06374v1) — Multi-RGB-D-camera SLAM with ICP calibration
- [Comparison of Visual SLAM Approaches](https://ar5iv.labs.arxiv.org/html/2108.01654) — Independent multi-method benchmark
- [How NeRFs and 3DGS are Reshaping SLAM](https://arxiv.org/html/2402.13255v2) — Comprehensive survey (200+ papers)
- [MemGS 2025](https://arxiv.org/html/2509.13536v1) — Memory-efficient Gaussian SLAM with cross-method comparison data
- [GPS-SLAM 2025](https://arxiv.org/abs/2509.11574) — Hybrid SDF+Gaussian SLAM at 150+ FPS
- [MGSO 3DV 2025](https://arxiv.org/html/2409.13055v3) — Monocular real-time Gaussian SLAM

### Primary Sources — Registration & Merging
- [ICP on Sparse Point Clouds](https://www.scitepress.org/Papers/2018/75352/75352.pdf) — ICP convergence failure on sparse data
- [Point Cloud Registration Comparison](https://www.mdpi.com/2078-2489/14/3/149) — ICP degradation with low overlap
- [Mesh-based GICP](https://onlinelibrary.wiley.com/doi/abs/10.1002/rob.22032) — 4-17x better registration range
- [Map Merging Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC7730201/) — Multi-robot map merging methods
- [3DGS-to-PC Conversion](https://github.com/Lewis-Stuart-11/3DGS-to-PC) — Gaussian to point cloud tool

### Primary Sources — Systems & Repositories
- [ORB-SLAM3 GitHub](https://github.com/UZ-SLAMLab/ORB_SLAM3) — 8.4k stars, GPL-3.0, frozen Dec 2021
- [OpenVINS Docs](https://docs.openvins.com/) — N-camera VIO, GPL-3.0
- [SVO Pro](https://rpg.ifi.uzh.ch/svo_pro.html) — 400 FPS, multi-camera, GPL-3.0
- [RTAB-Map](http://introlab.github.io/rtabmap/) — Multi-RGBD, BSD, actively maintained
- [Stella-VSLAM GitHub](https://github.com/stella-cv/stella_vslam) — 360-degree support, active
- [cuVSLAM / Isaac ROS](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/index.html) — 32-camera, NVIDIA-only, Apache-2.0
- [COVINS-G GitHub](https://github.com/VIS4ROB-lab/covins) — Frontend-agnostic collaborative SLAM
- [SchurVINS GitHub](https://github.com/bytedance/SchurVINS) — ByteDance, Apache-2.0
- [NGD-SLAM GitHub](https://github.com/yuhaozhang7/NGD-SLAM) — CPU-only dynamic SLAM
- [SELM-SLAM3 GitHub](https://github.com/banafshebamdad/SELM-SLAM3) — C++ ONNX hybrid SLAM
- [MultiCamSLAM GitHub](https://github.com/neufieldrobotics/MultiCamSLAM) — Generalized camera framework, MIT
- [multi_orbslam3 GitHub](https://github.com/yutongwangBIT/multi_orbslam3) — Collaborative ORB-SLAM3
- [MASt3R-SLAM GitHub](https://github.com/rmurai0610/MASt3R-SLAM) — Foundation model SLAM, 2.8k stars
- [Basalt VIO GitHub](https://github.com/VladyslavUsenko/basalt) — Fastest VIO, BSD-3
- [VINS-Fusion GitHub](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion) — Stereo VIO, GPL-3.0
- [Kimera-VIO GitHub](https://github.com/MIT-SPARK/Kimera-VIO) — Semantic mesh SLAM, BSD-2
- [maplab 2.0 GitHub](https://github.com/ethz-asl/maplab) — Multi-session mapping, Apache-2.0
