# Axis 3: Neural Scene Representation SLAM

## Question
What neural implicit and explicit representation SLAM methods (NeRF-based, Gaussian Splatting-based, voxel-based) exist, which can run in real-time, and what are their output representations?

## Findings

### 1. NeRF-Based / Neural Implicit SLAM

The first NeRF-inspired SLAM system appeared in 2021 with iMAP, and since then over 200 papers have been posted on arXiv or published at top-tier venues. [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2) The general architecture couples a differentiable neural renderer (volume rendering along rays) with pose optimization, jointly optimizing camera poses and a neural scene representation. A key limitation shared across NeRF-based approaches is that ray marching is computationally expensive, making true real-time operation challenging. [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2)

**iMAP (ICCV 2021)** — The pioneering work. Uses a single MLP mapping 3D coordinates to color and volume density. Achieves close-to-frame-rate camera tracking through parallel tracking/mapping threads. Limited capacity leads to catastrophic forgetting in larger environments. Input: RGB-D. Output: implicit density field. No public code release. [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2)

**NICE-SLAM (CVPR 2022)** — Extends iMAP with a hierarchical multi-resolution grid + MLP architecture (coarse, mid, fine levels). Addresses the scalability and smoothing limitations of iMAP. Uses occupancy-based reconstruction. Input: RGB-D. Output: occupancy grid decodable to mesh. GPU memory ~5 GB reported. Code available. [NICE-SLAM GitHub](https://github.com/cvg/nice-slam), [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2)

**ESLAM (CVPR 2023)** — Introduces multi-scale axis-aligned feature planes (tri-plane architecture) decoded into TSDF and RGB values via shallow MLPs. Runs up to 10x faster than iMAP and NICE-SLAM, with 50%+ improvement in reconstruction accuracy and localization. Memory scales quadratically rather than cubically (vs. voxel grids). Input: RGB-D. Output: TSDF surface. [ESLAM Project Page](https://www.idiap.ch/paper/eslam/), [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2)

**Co-SLAM (CVPR 2023)** — Combines multi-resolution hash grid encoding (inspired by Instant-NGP) with one-blob coordinate encoding for surface coherence. Runs at 10-17 Hz on an RTX 3090 Ti. Performs global BA by sampling ~5% of pixels from all previous keyframes. Input: RGB-D. Output: SDF surface representation. Code available. [Co-SLAM CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/html/Wang_Co-SLAM_Joint_Coordinate_and_Sparse_Parametric_Encodings_for_Neural_Real-Time_CVPR_2023_paper.html), [Co-SLAM GitHub](https://github.com/HengyiWang/Co-SLAM)

**Point-SLAM (ICCV 2023)** — Anchors neural features in a dynamically growing point cloud rather than a fixed grid. Adapts point density to scene information density, reducing runtime and memory in low-detail regions. Competitive tracking/mapping/rendering on Replica, TUM-RGBD, ScanNet. However, volume rendering means it struggles to reach real-time on real scenes. Input: RGB-D. Output: neural point cloud (occupancy-based). Code available. [Point-SLAM arXiv](https://arxiv.org/abs/2304.04278), [Point-SLAM GitHub](https://github.com/eriksandstroem/Point-SLAM)

**Orbeez-SLAM (ICRA 2023)** — Decouples tracking and mapping: uses ORB-SLAM2 for visual odometry and Instant-NGP for NeRF mapping. Works with monocular RGB only (no depth required). Reported 800x faster than baseline dense NeRF methods. Input: monocular RGB. Output: implicit radiance field (hash grid + MLP). Code available. [Orbeez-SLAM arXiv](https://arxiv.org/abs/2209.13274), [Orbeez-SLAM GitHub](https://github.com/MarvinChung/Orbeez-SLAM)

**Loopy-SLAM (CVPR 2024)** — Extends Point-SLAM with loop closure via global place recognition and pose graph optimization on point-cloud submaps. 20% improvement over Point-SLAM and 70% over ESLAM in depth L1 on Replica. Drift-free reconstructions on ScanNet. Input: RGB-D. Output: neural point cloud submaps. Code available. [Loopy-SLAM CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Liso_Loopy-SLAM_Dense_Neural_SLAM_with_Loop_Closures_CVPR_2024_paper.html), [Loopy-SLAM GitHub](https://github.com/eriksandstroem/Loopy-SLAM)

**Confidence: HIGH** for method descriptions and representation types. **MEDIUM** for exact FPS figures (many papers report iteration time rather than system FPS).

---

### 2. 3D Gaussian Splatting-Based SLAM

3DGS-based SLAM methods replace volumetric ray marching with rasterization-based splatting of explicit 3D Gaussians, offering dramatically faster rendering (up to 769 FPS for rendering alone) and more straightforward optimization. Five concurrent 3DGS SLAM papers appeared on arXiv in late 2023, launching this sub-field. [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2)

**SplaTAM (CVPR 2024)** — First major 3DGS SLAM system. Uses silhouette-guided densification. Achieves 2x lower trajectory error than Point-SLAM on Replica (0.36 cm vs. 0.52 cm ATE RMSE). However, system-level FPS is very low: approximately 0.15-0.28 FPS (not real-time). GPU memory: ~8 GB on Replica. Generates ~5M+ Gaussians per scene. Input: RGB-D. Output: 3D Gaussian map. Code available. [SplaTAM Project Page](https://spla-tam.github.io/), [MemGS comparison data](https://arxiv.org/html/2509.13536v1)

**MonoGS / Gaussian Splatting SLAM (CVPR 2024 Highlight + Best Demo)** — First monocular 3DGS SLAM. Supports monocular, stereo (experimental), and RGB-D input. Speedup branch achieves up to 10 FPS on RTX 4090. Standard branch: 1-3 FPS. GPU memory: 10-13 GB on Replica. Live demo capability with Intel RealSense D455. Input: monocular/stereo/RGB-D. Output: 3D Gaussian map. Code available. [MonoGS GitHub](https://github.com/muskie82/MonoGS), [MonoGS Project Page](https://rmurai.co.uk/projects/GaussianSplattingSLAM/), [MemGS comparison data](https://arxiv.org/html/2509.13536v1)

**GS-SLAM (CVPR 2024)** — Uses adaptive Gaussian expansion/deletion strategy and coarse-to-fine tracking via sparse Gaussian selection. Achieves 386 FPS average rendering (100x faster than NeRF-based methods). ATE RMSE of 3.7 cm on TUM-RGBD. Input: RGB-D. Output: 3D Gaussian map. Code available. [GS-SLAM CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Yan_GS-SLAM_Dense_Visual_SLAM_with_3D_Gaussian_Splatting_CVPR_2024_paper.html), [GS-SLAM Project Page](https://gs-slam.github.io/)

**Photo-SLAM (2024)** — Decoupled architecture: ORB-SLAM3 for tracking + 3DGS for mapping. Runs at >30 FPS. GPU memory: 2.5-3.2 GB on Replica. Supports monocular, stereo, and RGB-D. Uses geometry-based densification and Gaussian-Pyramid-based learning. Relatively compact maps. Input: monocular/stereo/RGB-D. Output: 3D Gaussian map. [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2), [MemGS comparison data](https://arxiv.org/html/2509.13536v1)

**RTG-SLAM (SIGGRAPH 2024)** — Focuses on real-time large-scale reconstruction. Forces Gaussians to be opaque or transparent, enabling single-Gaussian-per-surface-region fitting. Achieves ~17.9 FPS with ~8.8 GB memory (vs. 8.65 FPS / 17.3 GB for best NeRF-based method). Categorizes Gaussians into stable/unstable and only optimizes unstable ones. Input: RGB-D. Output: compact 3D Gaussian map. Code available. [RTG-SLAM SIGGRAPH 2024](https://dl.acm.org/doi/10.1145/3641519.3657455), [RTG-SLAM GitHub](https://github.com/MisEty/RTG-SLAM)

**Gaussian-SLAM (2024)** — Organizes scene into independently optimized sub-maps (not kept in GPU memory simultaneously), enabling scalability to large scenes. Uses photometric + geometric losses for frame-to-model tracking. Input: RGB-D. Output: sub-map-organized 3D Gaussians. Code available. [Gaussian-SLAM arXiv](https://arxiv.org/abs/2312.10070), [Gaussian-SLAM GitHub](https://github.com/VladimirYugay/Gaussian-SLAM)

**RD-SLAM (2024)** — Real-Time Dense SLAM using Gaussian Splatting. Achieves 10 FPS, reported as 60x faster than SplaTAM. Input: RGB-D. Output: 3D Gaussian map. [RD-SLAM](https://www.mdpi.com/2076-3417/14/17/7767)

**MGSO (3DV 2025)** — Monocular real-time photometric SLAM. Integrates DSO-based photometric tracking with 3DGS mapping. Achieves >30 FPS on desktop hardware. GPU memory: ~8 GB. Map size extremely compact: 4.6 MB on Replica vs. Photo-SLAM's 22.5 MB. Monocular-only (no depth sensor). PSNR: 31.41 dB on Replica. Input: monocular RGB. Output: compact 3D Gaussian map. [MGSO arXiv](https://arxiv.org/html/2409.13055v3)

**MemGS (2025)** — Memory-efficient 3DGS SLAM targeting embedded deployment (Jetson AGX Orin). Voxel-based Gaussian merging reduces redundancy. Achieves >30 FPS with only 1.95-2.75 GB GPU memory on Replica. Demonstrated on real hardware with RealSense D435i. Input: monocular/RGB-D. Output: memory-efficient 3D Gaussian map. [MemGS](https://arxiv.org/html/2509.13536v1)

**LoopSplat (3DV 2025, Oral)** — Adds loop closure to 3DGS SLAM via submap-based registration. Computes relative constraints directly via 3DGS registration rather than point cloud ICP. Input: RGB-D. Output: globally consistent 3D Gaussian submaps. Code available. [LoopSplat Project Page](https://loopsplat.github.io/), [LoopSplat GitHub](https://github.com/GradientSpaces/LoopSplat)

**Splat-SLAM (CVPR 2025 Workshop)** — First RGB-only 3DGS SLAM with global optimization. Dynamically deforms Gaussian map when keyframe poses/depths are updated. Input: RGB only. Output: globally optimized 3D Gaussian map. [Splat-SLAM OpenReview](https://openreview.net/forum?id=YKtbklD5MV)

**GPS-SLAM / Gaussian-Plus-SDF SLAM (Computational Visual Media 2025)** — Hybrid representation combining colorized SDF (via RGB-D fusion) with 3D Gaussians for detail. Achieves 150+ FPS on Azure Kinect sequences — an order of magnitude faster than prior 3DGS SLAM methods. Uses 50% fewer Gaussians and 75% fewer optimization iterations than pure Gaussian methods. Input: RGB-D. Output: hybrid SDF + Gaussian representation. Code available. [GPS-SLAM arXiv](https://arxiv.org/abs/2509.11574), [GPS-SLAM Journal](https://www.sciopen.com/article/10.26599/CVM.2025.9450513)

**Confidence: HIGH** for method existence and representation types. **HIGH** for FPS/memory data from MemGS comparison tables (directly measured). **MEDIUM** for self-reported FPS in individual papers (conditions vary).

---

### 3. Voxel-Based / TSDF Neural SLAM

These methods combine traditional volumetric representations (voxel grids, octrees, TSDF) with neural features, occupying a middle ground between classical geometry and pure neural implicit methods.

**Vox-Fusion (ISMAR 2022)** — Uses octree-based voxel grid with per-voxel neural features decoded by MLP into SDF values. Supports on-the-fly spatial expansion. Only samples occupied cells, improving training efficiency. Input: RGB-D. Output: voxel-anchored SDF reconstruction. Code available. [Vox-Fusion Project Page](https://zju3dv.github.io/Vox-Fusion/)

**Vox-Fusion++ (arXiv 2024)** — Extends Vox-Fusion with multi-map architecture for large-scale scenes. Handles tracking failure by creating new maps, with loop closure merging map sections. Multi-process framework for real-time operation. Maintains constant map size via region thresholding. Input: RGB-D. Output: multi-map voxel-based SDF. [Vox-Fusion++ arXiv](https://arxiv.org/abs/2403.12536)

**SHINE-Mapping (ICRA 2023)** — Uses sparse hierarchical octree structure with implicit features decoded by shallow network into SDF values. Directly supervises signed distance at sampled 3D points (no volume rendering). Supports incremental mapping with regularization against catastrophic forgetting. Designed for large-scale outdoor scenes. **Note: primarily uses LiDAR input**, though the representation approach is transferable. Output: continuous TSDF field extractable to mesh. Code available. [SHINE-Mapping arXiv](https://arxiv.org/abs/2210.02299), [SHINE-Mapping GitHub](https://github.com/PRBonn/SHINE_mapping)

**ESLAM (CVPR 2023)** — While categorized under NeRF-based above due to its MLP decoder, ESLAM's output is explicitly a TSDF representation stored on tri-planes, making it architecturally a hybrid. Its 10x speedup over NICE-SLAM comes from the efficient tri-plane structure avoiding cubic voxel scaling. [ESLAM Project Page](https://www.idiap.ch/paper/eslam/)

**Confidence: HIGH** for Vox-Fusion and ESLAM. **MEDIUM** for SHINE-Mapping relevance (it is primarily LiDAR-based, which falls at the edge of scope).

---

### 4. Comparison Table: Real-Time Neural SLAM Methods

| Method | Year | Venue | Input | Representation | Output Format | System FPS | GPU Memory | Loop Closure | Code |
|--------|------|-------|-------|----------------|---------------|------------|------------|-------------|------|
| **iMAP** | 2021 | ICCV | RGB-D | MLP | Density field | ~frame-rate | N/R | No | No |
| **NICE-SLAM** | 2022 | CVPR | RGB-D | Grid + MLP | Occupancy | <1 Hz | ~5 GB | No | Yes |
| **Vox-Fusion** | 2022 | ISMAR | RGB-D | Octree + MLP | SDF | N/R | N/R | No | Yes |
| **ESLAM** | 2023 | CVPR | RGB-D | Tri-plane + MLP | TSDF | ~10x iMAP | Quadratic | No | Yes |
| **Co-SLAM** | 2023 | CVPR | RGB-D | Hash grid + MLP | SDF | 10-17 Hz | N/R | No | Yes |
| **Point-SLAM** | 2023 | ICCV | RGB-D | Neural points + MLP | Occupancy | <real-time | Adaptive | No | Yes |
| **Orbeez-SLAM** | 2023 | ICRA | Mono RGB | ORB + Instant-NGP | Radiance field | Real-time tracking | N/R | No | Yes |
| **Loopy-SLAM** | 2024 | CVPR | RGB-D | Neural points + MLP | Point submaps | <real-time | N/R | **Yes** | Yes |
| **SplaTAM** | 2024 | CVPR | RGB-D | 3D Gaussians | Gaussian map | 0.15-0.28 | ~8 GB | No | Yes |
| **MonoGS** | 2024 | CVPR | Mono/Stereo/RGBD | 3D Gaussians | Gaussian map | 1-10 | 10-13 GB | No | Yes |
| **GS-SLAM** | 2024 | CVPR | RGB-D | 3D Gaussians | Gaussian map | N/R (386 render) | N/R | No | Yes |
| **Photo-SLAM** | 2024 | — | Mono/Stereo/RGBD | ORB-SLAM3 + 3DGS | Gaussian map | **>30** | 2.5-3.2 GB | Yes (via ORB) | Yes |
| **RTG-SLAM** | 2024 | SIGGRAPH | RGB-D | 3D Gaussians | Compact Gaussians | **~18** | ~8.8 GB | No | Yes |
| **Gaussian-SLAM** | 2024 | — | RGB-D | 3D Gaussian submaps | Gaussian submaps | Interactive | Scalable | No | Yes |
| **RD-SLAM** | 2024 | — | RGB-D | 3D Gaussians | Gaussian map | **~10** | N/R | No | — |
| **Vox-Fusion++** | 2024 | — | RGB-D | Octree + MLP (multi-map) | SDF multi-maps | Real-time | N/R | **Yes** | Yes |
| **MGSO** | 2025 | 3DV | Mono RGB | DSO + 3DGS | Compact Gaussians | **>30** | ~8 GB | No | Yes |
| **MemGS** | 2025 | — | Mono/RGBD | 3D Gaussians (merged) | Compact Gaussians | **>30** | **1.95-2.75 GB** | No | — |
| **LoopSplat** | 2025 | 3DV | RGB-D | 3D Gaussian submaps | Gaussian submaps | N/R | N/R | **Yes** | Yes |
| **Splat-SLAM** | 2025 | CVPRw | RGB only | 3D Gaussians | Globally opt. Gaussians | N/R | N/R | **Yes** (global) | Yes |
| **GPS-SLAM** | 2025 | CVM | RGB-D | SDF + 3D Gaussians | Hybrid SDF+Gaussian | **150+** | N/R | No | Yes |

*N/R = Not Reported. FPS figures are system-level (tracking+mapping) unless noted. "Render FPS" refers to rendering-only speed.*

Data sources: [MemGS](https://arxiv.org/html/2509.13536v1) for cross-method GPU memory and FPS comparisons; [RTG-SLAM](https://dl.acm.org/doi/10.1145/3641519.3657455) for its own benchmarks; [MGSO](https://arxiv.org/html/2409.13055v3) for monocular performance; individual project pages for other metrics.

---

### 5. Key Trends and Observations

**Representation evolution**: The field has progressed from pure MLP (iMAP) → hybrid grid+MLP (NICE-SLAM, ESLAM, Co-SLAM) → explicit 3D Gaussians (SplaTAM, MonoGS, Photo-SLAM) → hybrid Gaussian+SDF (GPS-SLAM). Each step improved rendering speed and reduced the gap to real-time operation. [How NeRFs and 3D Gaussian Splatting are Reshaping SLAM: a Survey](https://arxiv.org/html/2402.13255v2)

**Real-time threshold**: Methods achieving >30 FPS system-wide include Photo-SLAM, MGSO, MemGS, and GPS-SLAM. These typically decouple tracking from mapping or use extremely efficient representations. GPS-SLAM at 150+ FPS is the current speed leader by leveraging SDF for geometry and Gaussians only for appearance detail. [GPS-SLAM](https://arxiv.org/abs/2509.11574)

**Memory-accuracy tradeoff**: SplaTAM achieves highest PSNR (~34 dB on Replica RGB-D) but requires ~8 GB and generates millions of Gaussians at <1 FPS. MemGS achieves ~37 dB PSNR with <2 GB memory at >30 FPS through voxel-based merging. [MemGS](https://arxiv.org/html/2509.13536v1)

**Loop closure gap**: Most neural/Gaussian SLAM methods lack loop closure. Notable exceptions: Loopy-SLAM (neural point submaps), LoopSplat (Gaussian submap registration), Vox-Fusion++ (multi-map), Photo-SLAM (via ORB-SLAM3), and Splat-SLAM (global optimization). This remains a critical limitation for large-scale deployment. [LoopSplat](https://loopsplat.github.io/), [Loopy-SLAM](https://arxiv.org/html/2402.09944v2)

**Monocular capability**: Most methods require RGB-D. Monocular-capable methods include Orbeez-SLAM, MonoGS, Photo-SLAM, MGSO, Splat-SLAM, and MemGS — critical for multi-camera integration where depth sensors may not be available on all cameras.

**Multi-camera relevance**: For integration into a multi-camera pipeline with ICP-based merging:
- 3DGS outputs can be directly rendered from novel viewpoints, potentially replacing ICP merging with Gaussian registration (as in LoopSplat). [LoopSplat](https://loopsplat.github.io/)
- Sub-map architectures (Gaussian-SLAM, LoopSplat, Vox-Fusion++) naturally align with per-camera SLAM outputs that need merging.
- MNE-SLAM (CVPR 2025) specifically addresses multi-agent neural SLAM for mobile robots. [MNE-SLAM CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Deng_MNE-SLAM_Multi-Agent_Neural_SLAM_for_Mobile_Robots_CVPR_2025_paper.pdf)

---

### 6. Key Unknowns

- **Exact system-level FPS for GS-SLAM and Gaussian-SLAM**: Papers report rendering FPS or per-iteration times but not always end-to-end system throughput.
- **GPU memory for many NeRF-based methods**: iMAP, Co-SLAM, Point-SLAM, and Loopy-SLAM do not consistently report peak VRAM usage in accessible sources.
- **Multi-camera 3DGS SLAM**: No method found that natively handles multiple synchronized cameras with a shared Gaussian map. MNE-SLAM handles multi-agent but with separate robots, not synchronized multi-camera rigs.
- **Outdoor/large-scale Gaussian SLAM benchmarks**: Most 3DGS SLAM evaluation is on indoor datasets (Replica, TUM, ScanNet). LSG-SLAM (2025) targets stereo outdoor scenes but detailed benchmarks were not found.
- **Long-term map maintenance**: How Gaussian maps handle revisitation, map updates over time, and memory growth in continuous operation is under-explored.
- **SHINE-Mapping visual SLAM variant**: SHINE-Mapping is LiDAR-based; whether its octree-SDF approach has been adapted for visual RGB-D SLAM specifically was not confirmed.
- **Exact FPS of Vox-Fusion and Vox-Fusion++**: Real-time operation is claimed but specific frame rates were not found in accessible sources.

## Metadata
- Sources cited: 28
- Search queries executed: 12
- Date of research: 2026-03-23
- Confidence: HIGH for method taxonomy and representation types; HIGH for FPS/memory where MemGS cross-comparison data available; MEDIUM for self-reported metrics from individual papers; LOW for multi-camera integration specifics
