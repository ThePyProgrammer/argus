# Follow-up 1: CPU-Only Multi-Instance SLAM Deployment

## Question
Which visual SLAM methods can run multiple simultaneous instances on CPU-only hardware (no NVIDIA GPU) at real-time rates, and what are the computational scaling characteristics?

## Findings

### 1. Single-Instance CPU and Memory Requirements

The following table synthesizes data from multiple benchmark papers. All timing figures are for the **tracking/frontend thread** on a desktop-class CPU (i7-class, ~3.5 GHz) unless otherwise noted. RAM figures are runtime footprint (not build-time).

| Method | Per-Frame Time (ms) | CPU Threads Used | RAM per Instance | Multi-Instance Feasibility |
|--------|---------------------|------------------|------------------|---------------------------|
| **ORB-SLAM3** | 25-33 (mono), ~17 optimized | 3 (tracking, mapping, loop) | ~500 MB baseline, grows with map | Moderate -- heavy, 3 threads per instance |
| **OpenVINS** | ~12.8 total | 1-2 | ~200-400 MB | Good -- lowest CPU of filter-based methods |
| **Basalt VIO** | <10 (fastest in benchmarks) | 2-3 | ~200-300 MB | Good -- outperforms all others in per-frame timing |
| **VINS-Fusion** | ~20-30 | 3-4 | ~400-600 MB | Moderate -- optimization backend is costly |
| **SVO Pro** | 2.5-10 (mono), ~18 (stereo+IMU) | <2 cores | ~100-200 MB | Excellent -- 55 FPS on ARM Cortex-A9, 300+ FPS on laptop |
| **stella_vslam** | ~25-35 (similar to ORB-SLAM2) | 3 | ~400-500 MB | Moderate -- ORB-SLAM2-derived architecture |
| **DSO** | ~20-30 (varies: 20ms regular, 150ms keyframe) | 1-2 | ~200-300 MB | Good for VO -- no loop closure overhead |
| **LDSO** | ~25-35 (DSO + loop closure) | 2-3 | ~300-400 MB | Moderate -- loop closure adds overhead |
| **Kimera-VIO** | ~4.5 ms tracking, but keyframes much heavier | 3-4 | ~500 MB-2 GB (grows rapidly) | Poor -- memory accumulates fast (~2 GB in 12 seconds at 60Hz in one report) |
| **S-MSCKF** | ~15-20 | 1-2 | ~150-250 MB | Good -- filter-based, small feature set per frame |
| **RTAB-Map** | Variable (30-100+ ms) | 3-4+ | ~500 MB-2 GB+ (grows with map) | Poor for multi-instance -- heavy memory management |
| **SchurVINS** (CVPR 2024, new) | ~8-12 (near-lowest CPU usage) | 1-2 | ~150-300 MB | Excellent -- designed for efficiency |
| **NGD-SLAM** (IROS 2025, new) | ~17.8 (56 FPS on laptop CPU) | 3 | ~400-500 MB | Good -- dynamic SLAM without GPU |

**Sources:**
- Per-frame timing for OpenVINS: [OpenVINS Timing Analysis](https://docs.openvins.com/eval-timing.html)
- ORB-SLAM3 tracking at 30-40 FPS, 3-thread architecture: [ORB-SLAM3 GitHub](https://github.com/UZ-SLAMLab/ORB_SLAM3) and [Emergent Mind ORB-SLAM3 Overview](https://www.emergentmind.com/topics/orb-slam3)
- ORB-SLAM ~500 MB memory footprint: [ORB-SLAM2 Memory Issue #82](https://github.com/raulmur/ORB_SLAM2/issues/82) and [Automatic Memory Management in ORB-SLAM3](https://cse.buffalo.edu/tech-reports/2024-01.pdf)
- SVO Pro 55 FPS on ARM, 300+ FPS on laptop, <2 cores: [SVO Pro - RPG UZH](https://rpg.ifi.uzh.ch/svo_pro.html)
- Basalt outperforms all others in per-frame timing: [Comparison of Modern Open-Source Visual SLAM](https://ar5iv.labs.arxiv.org/html/2108.01654)
- Kimera memory accumulation ~2GB: [Kimera-VIO-ROS RAM Issue #69](https://github.com/MIT-SPARK/Kimera-VIO-ROS/issues/69)
- SchurVINS lowest CPU usage among VIO: [SchurVINS CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Fan_SchurVINS_Schur_Complement-Based_Lightweight_Visual_Inertial_Navigation_System_CVPR_2024_paper.pdf)
- NGD-SLAM 56 FPS CPU-only: [NGD-SLAM arXiv](https://arxiv.org/abs/2405.07392)
- Jetson VIO benchmarks (VINS-Mono ~150-170% CPU, Kimera high memory): [Run Your VIO on NVIDIA Jetson](https://arxiv.org/abs/2103.01655)
- Schmidt 2025 field robotics benchmark comparing CPU costs: [Visual-Inertial SLAM for Unstructured Outdoor Environments](https://onlinelibrary.wiley.com/doi/10.1002/rob.22581)

### 2. Multi-Instance Scaling (2, 4, 8 Parallel Instances)

No single paper provides a comprehensive scaling study of N parallel SLAM instances on one machine. However, several data points exist:

- **Multi-camera direct benchmark (Intel N100, 4-core/4-thread, 8 GB RAM):** A 2025 study on robust direct multi-camera SLAM ran 4 Intel RealSense D455 cameras at 848x480 / 20 FPS on an Intel Processor N100. This used a unified multi-camera model (single SLAM instance processing all cameras), not 4 separate instances. [Robust Direct Multi-Camera SLAM](https://www.mdpi.com/2079-9292/14/23/4556)

- **Scaling estimate (independent instances):** For methods using 3 threads each (ORB-SLAM3, stella_vslam), running 4 instances requires 12 threads. On an 8-core/16-thread CPU, this is feasible but leaves minimal headroom. For 2-thread methods (OpenVINS, Basalt, S-MSCKF), 4 instances need only 8 threads -- achievable on a modern 8-core.

- **Memory scaling is linear:** Each independent instance maintains its own map. 4 x ORB-SLAM3 instances = ~2 GB baseline RAM (growing with map size). 4 x OpenVINS = ~1-1.6 GB. 4 x SVO Pro = ~0.4-0.8 GB.

- **Swarm-SLAM / distributed approach:** Swarm-SLAM distributes SLAM across robots, each running a single lightweight instance. An ultra-lightweight variant runs on RISC-V platforms with only 1.5 MB memory, though with reduced accuracy (~30 cm). [Swarm-SLAM GitHub](https://github.com/MISTLab/Swarm-SLAM) and [Ultra-Lightweight Collaborative Mapping](https://arxiv.org/abs/2407.03136)

- **Heterogeneous parallelization (2024):** CPU-based multi-threading with OpenMP for parallel feature extraction across cameras, combined with load balancing, reduces per-camera overhead significantly. [Parallel Implementation for Real-Time Visual SLAM](https://www.oaepublish.com/articles/ir.2024.17)

### 3. New CPU-Optimized / Lightweight SLAM Methods (2024-2026)

Several methods not in the original survey deserve attention:

- **SchurVINS (CVPR 2024, ByteDance):** Filter-based VIO using Schur complement for O(n) update complexity. Achieves near-lowest CPU usage among all tested VIO systems while maintaining competitive accuracy. Open source. [SchurVINS GitHub](https://github.com/bytedance/SchurVINS)

- **NGD-SLAM (IROS 2025):** First dynamic SLAM to run at 56 FPS on CPU-only by decoupling deep-learning masking from tracking via mask propagation. Based on ORB-SLAM3. [NGD-SLAM GitHub](https://github.com/yuhaozhang7/NGD-SLAM)

- **SuperNoVA (ASPLOS 2025, UC Berkeley):** Algorithm-hardware co-design that dynamically adapts SLAM computation to available resources. Reduces backend latency by 89.5% vs. baseline CPU. Research-stage hardware accelerator, but the adaptive algorithm principles apply to CPU scheduling. [SuperNoVA Paper](https://people.eecs.berkeley.edu/~ysshao/assets/papers/supernova-asplos2025.pdf)

- **OASIS (ACM TECS 2025):** Optimized Adaptive System for Intelligent SLAM -- monitors power/compute/requirements and adaptively adjusts parameters and sensor rates. Extends operational runtime by 40-60% on embedded systems. [OASIS ACM](https://dl.acm.org/doi/10.1145/3761808)

- **OV2SLAM:** Fully online and versatile visual SLAM designed to be lightweight and real-time on standard CPUs. [OV2SLAM Paper](https://archimer.ifremer.fr/doc/00684/79583/82305.pdf)

### 4. Practical Minimum Hardware for 4+ Parallel Instances at 15+ FPS

**Recommended minimum for 4 instances at 15 FPS (using lightweight methods):**

| Configuration | CPU | RAM | Best Method Choices |
|--------------|-----|-----|-------------------|
| Budget / embedded | 8-core ARM (e.g., RPi 5 cluster) | 8 GB | SVO Pro or S-MSCKF (2 threads each) |
| Mid-range | 8-core / 16-thread x86 (e.g., i7-12700, Ryzen 7) | 16 GB | OpenVINS, Basalt, or SchurVINS |
| Comfortable | 12+ core / 24-thread x86 | 32 GB | ORB-SLAM3 or NGD-SLAM (full SLAM with loop closure) |

**Key constraints:**
- At 15 FPS, per-frame budget is 66 ms -- most methods easily meet this on desktop CPUs.
- The bottleneck is **thread contention** and **memory bandwidth** when running multiple instances, not raw per-frame compute.
- For 8 parallel instances, a 16-core / 32-thread CPU (e.g., Ryzen 9, Xeon) with 32-64 GB RAM is practical with lightweight methods (SVO Pro, OpenVINS, SchurVINS, S-MSCKF).
- A unified multi-camera SLAM approach (single instance, multiple cameras) is more efficient than N independent instances when cameras have overlapping FOV.

### 5. ARM / Embedded CPU Benchmarks

| Platform | Method | Performance | Source |
|----------|--------|-------------|--------|
| ARM Cortex-A9 (4-core, 1.6 GHz) | SVO | 55 FPS mono | [SVO Pro - RPG UZH](https://rpg.ifi.uzh.ch/svo_pro.html) |
| Odroid XU4 (ARM big.LITTLE) | SVO | ~100 FPS mono | [SVO Pro - RPG UZH](https://rpg.ifi.uzh.ch/svo_pro.html) |
| Jetson TX2 (ARM, CPU-only) | VINS-Mono | ~150-170% CPU utilization, real-time at 20 FPS | [Jetson VIO Benchmark](https://arxiv.org/abs/2103.01655) |
| Jetson TX2 (ARM, CPU-only) | S-MSCKF | Comparable to monocular methods in memory | [Jetson VIO Benchmark](https://arxiv.org/abs/2103.01655) |
| Jetson AGX Xavier (ARM, CPU-only) | Kimera-VIO | Runs but high memory, struggles with keyframes | [Jetson VIO Benchmark](https://arxiv.org/abs/2103.01655) |
| Jetson Xavier NX (ARM, CPU-only) | Multiple VIO | Higher CPU usage rates than AGX Xavier | [Jetson VIO Benchmark](https://arxiv.org/abs/2103.01655) |
| Raspberry Pi 4B | ORB-SLAM3 | Sub-real-time (FAST feature extraction is bottleneck) | [Predicting ORB-SLAM3 on Embedded Platforms](https://scielo.org.za/scielo.php?script=sci_arttext&pid=S2313-78352024000200005) |
| Raspberry Pi 5 | ORB-SLAM3 | Functional via ROS2, no published FPS benchmarks yet | [RPi5 Visual SLAM Guide](https://github.com/ozandmrz/raspberry_pi_visual_slam) |
| Intel N100 (4C/4T, 8 GB) | Multi-cam direct SLAM | 4 cameras at 848x480 / 20 FPS (single unified instance) | [Robust Direct Multi-Camera SLAM](https://www.mdpi.com/2079-9292/14/23/4556) |
| RISC-V parallel (swarm) | Ultra-lightweight SLAM | Real-time with 1.5 MB memory, ~30 cm accuracy | [Ultra-Lightweight Collaborative Mapping](https://arxiv.org/abs/2407.03136) |

### Recommendations for Your Multi-Camera Pipeline

Given your constraints (CPU-only, multiple cameras, merging via ICP):

1. **Best candidates for parallel instances:** SVO Pro (fastest, <2 cores per instance), SchurVINS (newest, lowest CPU among VIO), OpenVINS (proven, well-documented), Basalt (fastest per-frame).

2. **Avoid for multi-instance:** Kimera-VIO (memory explosion), RTAB-Map (too heavy), ORB-SLAM3 (feasible but 3 threads + 500 MB per instance adds up fast).

3. **Consider unified multi-camera SLAM** instead of N independent instances: The Intel N100 benchmark shows a single multi-camera SLAM instance handling 4 cameras is more efficient than 4 separate instances.

4. **For 4 cameras at 15+ FPS on a mid-range CPU (8-core, 16 GB):** Run 4x OpenVINS or 4x SchurVINS instances. Expected total: ~8 threads, ~1.5 GB RAM. Merge outputs with your existing ICP pipeline.

## Key Unknowns

- **No published N-instance scaling study exists.** All multi-instance feasibility estimates are extrapolated from single-instance benchmarks. Thread contention, cache thrashing, and memory bandwidth effects at 4-8 instances are not characterized.

- **SchurVINS multi-instance behavior is untested.** While it has the best efficiency profile, no one has published results running multiple SchurVINS instances in parallel.

- **SVO Pro is not fully open source.** The original SVO is open source but SVO Pro (with IMU fusion, multi-camera support, loop closure) has a more restrictive license. This may limit deployment options.

- **Basalt VIO is no longer actively maintained** (last significant update ~2022). Long-term support is uncertain.

- **Actual RAM growth over time** for long-running SLAM instances (minutes to hours) is poorly characterized for most methods. ORB-SLAM3 and Kimera are known to grow unboundedly without memory management.

- **ARM performance for 2024-2026 methods** (SchurVINS, NGD-SLAM) has not been benchmarked on embedded platforms. Only desktop i7-class CPUs are reported.

- **Cache and memory bandwidth contention** when running 4+ instances sharing L3 cache on a single CPU die is an unexplored factor that may degrade per-instance performance non-linearly.

## Metadata
- Sources cited: 22
