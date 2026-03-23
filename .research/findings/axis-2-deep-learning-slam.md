# Axis 2: Deep Learning & End-to-End Visual SLAM

## Question
What deep learning-based visual SLAM and visual odometry methods exist that can run in real-time, and how do they compare to classical methods in accuracy, robustness, and output format?

## Findings

### 1. Landscape Overview

The deep learning visual SLAM field has evolved rapidly from 2021 to 2025, progressing through three distinct waves: (1) end-to-end learned VO/SLAM systems like DROID-SLAM, (2) hybrid systems that replace specific classical components (feature extraction, matching) with learned modules, and (3) neural scene representation SLAM using NeRF or 3D Gaussian Splatting for mapping. Since iMAP in 2021, over 200 papers on neural SLAM have appeared at top venues. [SLAM Meets NeRF: A Survey of Implicit SLAM Methods](https://www.mdpi.com/2032-6653/15/3/85) (Confidence: high)

For integration into a multi-camera pipeline that currently uses ICP-based merging, the hybrid approach (category 2) is most practical: it preserves the existing SLAM backbone's output format while upgrading robustness. End-to-end systems (category 1) offer the best accuracy but have heavier GPU demands and output dense representations that may not directly replace sparse point cloud outputs used in ICP merging.

---

### 2. End-to-End Learned SLAM Systems

#### DROID-SLAM (NeurIPS 2021, Princeton)
- **Architecture:** Recurrent iterative updates of camera pose and pixelwise depth through a Dense Bundle Adjustment layer. Uses a correlation volume and GRU-based update operator.
- **Input:** Monocular, stereo, and RGB-D (same model, no retraining). [DROID-SLAM Paper](https://arxiv.org/abs/2108.10869)
- **Accuracy:** On EuRoC monocular, reduces ATE by 82% among zero-failure methods and 43% over ORB-SLAM3. On TUM-RGBD, 83% lower ATE than DeepFactors. Zero failures across TartanAir, EuRoC, and TUM-RGBD (ORB-SLAM3 fails on 1/11 EuRoC sequences). [DROID-SLAM NeurIPS proceedings](https://proceedings.neurips.cc/paper/2021/file/89fcd07f20b6785b92134bd6c1d0fa42-Paper.pdf) (Confidence: high)
- **Runtime:** ~20 FPS on a high-end GPU; requires ~20GB VRAM.
- **Output:** Dense depth maps + camera poses. Not directly a sparse point cloud.
- **Limitations:** High GPU memory requirement; struggles on very long outdoor sequences (KITTI).

#### DPV-SLAM (ECCV 2024, Princeton)
- **Architecture:** Extends DPVO with two loop closure mechanisms (proximity-based on single GPU, classical using dBoW2 + pose graph optimization on CPU).
- **Input:** Monocular only.
- **Accuracy:** EuRoC ATE 0.024m (vs DROID-SLAM 0.022m); KITTI ATE 25.76m with loop closure (DROID-SLAM struggles significantly on outdoor); TartanAir ATE 0.16m vs DROID-SLAM 0.24m. [DPV-SLAM ECCV 2024](https://arxiv.org/html/2408.01654v1) (Confidence: high)
- **Runtime:** 27-50 FPS depending on dataset; 5.0GB VRAM (vs DROID-SLAM's 20GB). 2.5x faster than DROID-SLAM.
- **Output:** Sparse patch-based map + camera poses.
- **Code:** Available at [princeton-vl/DPVO](https://github.com/princeton-vl/DPVO) (957 stars, last updated July 2024).

#### DPVO (NeurIPS 2023, Princeton)
- **Architecture:** Recurrent network tracking image patches across time. Uses patch-based correlation instead of dense correlation volumes.
- **Input:** Monocular.
- **Accuracy:** Outperforms all prior work (classical or learned) on EuRoC, TUM-RGBD, TartanAir ECCV 2020 SLAM competition, and ICL-NUIM. [DPVO NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/7ac484b0f1a1719ad5be9aa8c8455fbb-Paper-Conference.pdf) (Confidence: high)
- **Runtime:** 60-120 FPS; uses 29-57% of DROID-VO's memory. Frame rate stays above 48 FPS for 95% of frames.
- **Limitation:** Visual odometry only (no loop closure, no mapping) -- but DPV-SLAM adds these.

#### MINI-DROID-SLAM (2025)
- **Architecture:** Replaces standard GRU in DROID-SLAM with Mini-GRU to reduce computation.
- **Aim:** Reduced complexity while maintaining robustness. [MINI-DROID-SLAM](https://www.mdpi.com/1424-8220/25/17/5448) (Confidence: medium)

#### TartanVO (CMU Robotics Institute)
- **Architecture:** Learning-based VO using an up-to-scale loss function with camera intrinsic parameters incorporated into the model. Trained on TartanAir synthetic data.
- **Input:** Monocular.
- **Accuracy:** Generalizes to multiple real-world datasets. On TQU-SLAM benchmark, ATE of 14.96m vs DPVO's 13.7m. [TartanVO](https://www.ri.cmu.edu/publications/tartanvo-a-generalizable-learning-based-vo/) (Confidence: medium)
- **Limitation:** VO only -- no mapping or loop closure. Less accurate than DPVO/DROID-SLAM on standard benchmarks.

#### SLAM-Former (arXiv September 2025)
- **Architecture:** Unifies full SLAM (frontend tracking + backend global optimization) into a single transformer with 36 layers of frame-attention and global-attention.
- **Input:** Monocular.
- **Runtime:** Real-time (>10 Hz). [SLAM-Former](https://arxiv.org/abs/2509.16909) (Confidence: medium -- very recent, not yet peer-reviewed at a top venue)
- **Output:** Dense reconstruction.

---

### 3. Hybrid Classical + Learned Feature Systems

These systems replace the feature extraction/matching modules of classical SLAM with deep learning models while keeping the geometric backend (bundle adjustment, pose graph optimization) classical. This is the most directly relevant category for the existing multi-camera pipeline.

#### SL-SLAM (2024)
- **Architecture:** ORB-SLAM3 backbone with SuperPoint replacing ORB features and LightGlue replacing projection/BoW matching throughout tracking, local mapping, and loop closure.
- **Input:** Monocular, stereo, monocular-inertial, stereo-inertial.
- **Accuracy:** Best ATE on 8-9/11 EuRoC sequences across all modes. Average 43-57% lower ATE than ORB-SLAM3. Critically, succeeds in V203 (challenging) where ORB-SLAM3 fails. [SL-SLAM](https://arxiv.org/html/2405.03413v2) (Confidence: high)
- **Runtime:** Feature extraction 7.27ms (faster than ORB-SLAM3's 11.98ms via ONNX+GPU), tracking 27.41ms/frame, loop closure 110.71ms. Real-time capable on RTX 3080.
- **Output:** Sparse point cloud + camera poses (same format as ORB-SLAM3).
- **Code:** [github.com/zzzzxxxx111/SLslam](https://github.com/zzzzxxxx111/SLslam)
- **Key insight for multi-camera integration:** Output format is identical to ORB-SLAM3, so ICP-based merging pipeline would work unchanged.

#### SELM-SLAM3 (2025)
- **Architecture:** ORB-SLAM3 + SuperPoint + LightGlue, but deployed entirely in C++ via ONNX Runtime (no Python/PyTorch dependency at runtime).
- **Input:** RGB-D.
- **Accuracy:** 87.84% average improvement over ORB-SLAM3; 36.77% over SOTA RGB-D SLAM on TUM, ICL-NUIM, TartanAir. [SELM-SLAM3](https://github.com/banafshebamdad/SELM-SLAM3) (Confidence: medium -- small repo, 45 stars)
- **Deployment advantage:** C++ ONNX Runtime means no Python overhead, suitable for embedded deployment.

#### SuperVINS (2024)
- **Architecture:** VINS-Fusion enhanced with SuperPoint feature extraction and LightGlue matching.
- **Input:** Visual-inertial (monocular + IMU).
- **Accuracy:** 39.6% ATE improvement over VINS-Fusion on challenging MH05 sequence. Comparable to SOTA VIO on EuRoC and UMA-VI. Slightly worse than VINS-Fusion in easy, texture-rich environments. [SuperVINS](https://arxiv.org/html/2407.21348v2) (Confidence: high)
- **Trade-off:** Deep features help in hard conditions but add overhead in easy conditions where ORB suffices.

#### Light-SLAM (2024)
- **Architecture:** Visual SLAM using LightGlue for robust matching under challenging lighting.
- **Runtime:** ~95ms per frame on RTX 3060. [Light-SLAM](https://arxiv.org/html/2407.02382v1) (Confidence: medium)

---

### 4. Neural Scene Representation SLAM (NeRF / 3DGS)

These systems use neural implicit representations or Gaussian splatting for the map, offering photorealistic rendering but different output formats.

#### MASt3R-SLAM (CVPR 2025)
- **Architecture:** Uses MASt3R (a pre-trained 3D reconstruction foundation model) as a prior for dense SLAM. GPU-accelerated CUDA kernels for projective matching (2ms).
- **Input:** Monocular RGB, stereo, RGB-D, live RealSense.
- **Runtime:** 15 FPS on RTX 4090. [MASt3R-SLAM CVPR 2025](https://edexheim.github.io/mast3r-slam/) (Confidence: high)
- **Output:** Dense 3D point cloud + camera poses.
- **Code:** [github.com/rmurai0610/MASt3R-SLAM](https://github.com/rmurai0610/MASt3R-SLAM) (2.8k stars).
- **Note:** Uses a foundation model rather than task-specific training -- represents the newest paradigm.

#### MonoGS / Gaussian Splatting SLAM (CVPR 2024 Highlight + Best Demo)
- **Architecture:** First monocular SLAM based solely on 3D Gaussian Splatting for tracking, mapping, and rendering.
- **Input:** Monocular, stereo, RGB-D.
- **Runtime:** ~3 FPS live (not real-time for robotics). [MonoGS](https://github.com/muskie82/MonoGS) (Confidence: high)
- **Output:** 3D Gaussian scene representation (photorealistic rendering, not directly a point cloud for ICP).

#### GS-SLAM (CVPR 2024)
- **Architecture:** Dense visual SLAM with 3DGS representation and differentiable splatting rendering.
- **Input:** RGB-D.
- **Runtime:** Rendering at 386 FPS; mapping optimization is the bottleneck. [GS-SLAM](https://gs-slam.github.io/) (Confidence: high)
- **Output:** Gaussian splat map.

#### GO-SLAM (ICCV 2023)
- **Architecture:** NeRF-based dense SLAM with online global bundle adjustment and loop closing.
- **Input:** Monocular, stereo, RGB-D.
- **Runtime:** Near real-time. Requires ~14GB VRAM. [GO-SLAM](https://arxiv.org/abs/2309.02436) (Confidence: high)
- **Output:** Neural implicit surface + camera poses.

#### SplaTAM (2024)
- **Architecture:** 3D Gaussians for dense RGB-D SLAM with explicit volumetric representation.
- **Input:** RGB-D.
- **Output:** Dense Gaussian map. [SplaTAM](https://spla-tam.github.io/) (Confidence: high)

---

### 5. Dynamic Environment SLAM

#### DynaSLAM (Original)
- **Architecture:** ORB-SLAM2 + Mask R-CNN for dynamic object segmentation + background inpainting.
- **Limitation:** Mask R-CNN is computationally expensive, significantly reducing real-time performance. [DynaSLAM comparison](https://ieeexplore.ieee.org/document/10347183/) (Confidence: high)

#### Recent Dynamic SLAM Improvements (2024-2025)
- **ADM-SLAM:** Uses DeepLabv3Pro + multi-view geometry. Outperforms DynaSLAM in real-time performance and accuracy. [ADM-SLAM](https://pmc.ncbi.nlm.nih.gov/articles/PMC11175307/) (Confidence: medium)
- **ARD-SLAM:** 37.8% ATE and 66.4% RPE improvement over DynaSLAM. [ARD-SLAM](https://www.sciencedirect.com/science/article/abs/pii/S0141938224000180) (Confidence: medium)
- **WildGS-SLAM (CVPR 2025):** Monocular Gaussian splatting SLAM for dynamic environments. Outperforms DynaSLAM with only monocular input. [WildGS-SLAM](https://openaccess.thecvf.com/content/CVPR2025/papers/Zheng_WildGS-SLAM_Monocular_Gaussian_Splatting_SLAM_in_Dynamic_Environments_CVPR_2025_paper.pdf) (Confidence: medium)
- **DyGS-SLAM (ICCV 2025):** Real-time accurate localization with Gaussian reconstruction for dynamic scenes. [DyGS-SLAM](https://openaccess.thecvf.com/content/ICCV2025/papers/Hu_DyGS-SLAM_Real-Time_Accurate_Localization_and_Gaussian_Reconstruction_for_Dynamic_Scenes_ICCV_2025_paper.pdf) (Confidence: medium)

---

### 6. Industry/Production Systems

#### NVIDIA cuVSLAM (Isaac ROS)
- **Architecture:** CUDA-accelerated stereo visual-inertial SLAM for robotics. Now available via PyCuVSLAM Python API (2025).
- **Input:** One or more stereo cameras + optional IMU.
- **Runtime:** Real-time, low-latency on NVIDIA Jetson platforms.
- **Integration:** Designed for multi-camera setups natively. [cuVSLAM Isaac ROS](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/index.html) (Confidence: high)
- **Relevance:** Directly supports multi-camera pipelines and runs on embedded NVIDIA hardware.

---

### 7. Comparison Table

| Method | Category | Input | FPS | GPU VRAM | EuRoC ATE (m) | Output Format | Loop Closure | Code Available |
|--------|----------|-------|-----|----------|---------------|---------------|-------------|----------------|
| **ORB-SLAM3** (baseline) | Classical | Mono/Stereo/RGBD/VIO | 30+ | CPU only | ~0.035 | Sparse points + poses | Yes | Yes |
| **DROID-SLAM** | End-to-end learned | Mono/Stereo/RGBD | ~20 | ~20 GB | ~0.022 | Dense depth + poses | No (global BA) | Yes |
| **DPV-SLAM** | End-to-end learned | Mono | 27-50 | 5-7 GB | 0.024 | Sparse patches + poses | Yes (2 types) | Yes |
| **DPVO** | Learned VO | Mono | 60-120 | ~3 GB | Competitive | Patches + poses (no map) | No | Yes |
| **SL-SLAM** | Hybrid (SP+LG on ORB-SLAM3) | Mono/Stereo/VIO | ~36 | Needs GPU | ~0.019-0.034 | Sparse points + poses | Yes | Yes |
| **SELM-SLAM3** | Hybrid (SP+LG, C++ ONNX) | RGBD | Real-time | Needs GPU | 87% better than ORB-SLAM3 | Sparse points + poses | Yes | Yes |
| **SuperVINS** | Hybrid (SP+LG on VINS-Fusion) | Mono+IMU | Real-time | Needs GPU | Competitive | Sparse points + poses | Yes | Yes |
| **MASt3R-SLAM** | Foundation model | Mono/Stereo/RGBD | 15 | RTX 4090 | SOTA | Dense points + poses | Yes | Yes (2.8k stars) |
| **MonoGS** | 3DGS SLAM | Mono/Stereo/RGBD | ~3 | High | Moderate | 3D Gaussians | No | Yes |
| **GS-SLAM** | 3DGS SLAM | RGBD | Real-time render | High | Good | 3D Gaussians | No | Yes |
| **GO-SLAM** | NeRF SLAM | Mono/Stereo/RGBD | Near RT | ~14 GB | Good | Neural implicit | Yes | Yes |
| **SLAM-Former** | End-to-end transformer | Mono | >10 Hz | High | Competitive | Dense | Yes | TBD |
| **cuVSLAM** | GPU-accelerated classical | Multi-stereo+IMU | Real-time | Jetson | Production-grade | Poses + sparse | Yes | Yes (NVIDIA) |

---

### 8. Key Findings for Multi-Camera Pipeline Integration

1. **Hybrid systems (SL-SLAM, SELM-SLAM3, SuperVINS) are the most practical upgrade path.** They preserve the sparse point cloud + pose output format that ICP merging expects, while dramatically improving robustness in challenging conditions. SL-SLAM specifically shows 43-57% ATE improvement over ORB-SLAM3 with the same output format. (Confidence: high)

2. **DPV-SLAM offers the best accuracy-to-compute ratio among end-to-end systems.** At 5GB VRAM and 27-50 FPS, it is feasible to run one instance per camera. Its sparse patch output could potentially be adapted for ICP merging, though this would require custom integration. (Confidence: high)

3. **DROID-SLAM remains the accuracy king but is impractical for multi-camera deployment** due to ~20GB VRAM per instance. Running 4+ instances simultaneously would require multiple high-end GPUs. (Confidence: high)

4. **MASt3R-SLAM represents the frontier** -- using a foundation model for SLAM priors -- but at 15 FPS on an RTX 4090, it is too expensive for multi-instance deployment today. (Confidence: high)

5. **Neural scene representation SLAM (NeRF/3DGS) outputs are incompatible with ICP merging.** These systems produce neural implicit fields or Gaussian splats, not point clouds. Integration would require either (a) extracting point clouds from the neural representation, or (b) replacing the ICP merge step entirely with a neural merge approach. (Confidence: high)

6. **NVIDIA cuVSLAM is the only production-ready system designed for multi-camera setups,** but it is proprietary and tied to NVIDIA Jetson/GPU hardware. Worth evaluating if the platform is compatible. (Confidence: high)

7. **Dynamic environment handling has improved significantly.** Systems like WildGS-SLAM (CVPR 2025) and DyGS-SLAM (ICCV 2025) now handle dynamic objects better than DynaSLAM while being more computationally efficient. For the multi-camera pipeline, adding a YOLO-based dynamic object filter (as in ADM-SLAM) to the existing system may be simpler than replacing the whole SLAM backend. (Confidence: medium)

---

### 9. Key Unknowns

- **Multi-camera deployment of learned SLAM:** No published work specifically benchmarks running multiple DROID-SLAM or DPV-SLAM instances in parallel and merging their outputs. The feasibility of this approach is untested in the literature.
- **Exact VRAM scaling:** Whether GPU memory scales linearly with camera count for learned SLAM methods, or whether model weights can be shared across instances, is not documented.
- **SL-SLAM on non-NVIDIA hardware:** SL-SLAM and similar hybrid approaches use ONNX Runtime for SuperPoint/LightGlue, but their performance on AMD GPUs or CPU-only systems has not been benchmarked. The user's system lacks an NVIDIA GPU, which may be a blocker for all deep learning methods.
- **ICP compatibility of DPV-SLAM patches:** Whether DPV-SLAM's sparse patch output can substitute for ORB feature point clouds in an ICP merge step has not been tested.
- **MASt3R-SLAM scaling:** Whether the foundation model approach can be made efficient enough for multi-camera real-time use within the next 1-2 years is unclear.
- **SLAM-Former maturity:** Published September 2025, no peer-reviewed venue confirmation yet, and no code release found. Its practical applicability is unknown.
- **Quantitative comparison on identical hardware:** Most papers benchmark on different GPUs (RTX 3080, 3090, 4090, A100), making direct FPS comparisons imprecise.

## Metadata
- Sources cited: 32
- Research date: 2026-03-23
- Search queries used: 10
- Pages fetched for detailed extraction: 5
- Confidence assessment: High confidence on DROID-SLAM, DPVO/DPV-SLAM, SL-SLAM benchmark numbers (published at top venues with reproducible code). Medium confidence on newer 2025 systems (SLAM-Former, SELM-SLAM3) due to recency and limited independent validation.
