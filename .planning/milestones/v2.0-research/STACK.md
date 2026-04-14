# Technology Stack: v2.0 SLAM API Additions

**Project:** Multi-Robot 3D Reconstruction -- Generic SLAM API
**Researched:** 2026-03-23
**Scope:** NEW additions only. Existing stack (MuJoCo, Open3D, FastAPI, React, Three.js, Zustand) is validated and unchanged.

## Executive Summary

The three SLAM backends (ORB-SLAM3, OpenVINS, SVO Pro) are all C++ libraries with varying degrees of Python accessibility. ORB-SLAM3 has usable pip-installable bindings. OpenVINS and SVO Pro do not -- they require building from source with custom pybind11 wrappers or subprocess isolation. For pose-graph optimization, GTSAM is the clear winner with pip-installable wheels and comprehensive Python API. The recommended architecture is: **in-process pybind11 bindings** for ORB-SLAM3 (via existing PyPI package), **subprocess isolation** for OpenVINS and SVO Pro (built from source, communicated via shared memory or pipes), and **GTSAM** for pose-graph optimization replacing the current union-OR voxel merge.

## Recommended Stack Additions

### SLAM Backend: ORB-SLAM3

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| orbslam3-python | 2.0.0 | ORB-SLAM3 Python bindings (PyPI) | Pre-built wheels for Python 3.8-3.12 on x86_64 and aarch64. Provides enhanced bindings with hardware adaptation and performance monitoring. Avoids building ORB-SLAM3 from source (notoriously painful CMake + Pangolin + DBoW2 chain). | MEDIUM |
| ORB vocabulary file | n/a | ORB feature vocabulary for place recognition | Required by ORB-SLAM3. ~140MB binary file downloaded once. Ships with ORB-SLAM3 source or can be extracted from orbslam3-python package. | HIGH |

**Integration notes:**
- ORB-SLAM3 operates in RGB-D mode (matching existing pipeline's depth camera setup)
- Outputs sparse 3D landmarks + camera poses as 4x4 SE(3) matrices
- The existing `SLAMPipeline.process_frame()` interface (takes SensorFrame, returns 4x4 pose) maps cleanly
- ORB-SLAM3 manages its own map internally; extract landmarks for visualization
- GPL-3.0 license -- compatible with existing project (already GPL-adjacent via Open3D)

**Alternative considered:** pyOrbSlam3 (JHMeusener) -- more transparent pybind11 wrapper but requires building ORB-SLAM3 from source. Only use if orbslam3-python wheels fail for the project's Python version.

### SLAM Backend: OpenVINS

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| open_vins (source build) | v2.7.1+ | Visual-Inertial Navigation System | ROS-free build officially supported (`-DENABLE_ROS=OFF`). EKF/MSCKF architecture, 12.8ms/frame, 1-2 threads. Arbitrary N-camera support (though "not fully tested" per maintainers). | MEDIUM |
| Eigen3 | 3.4+ | Linear algebra (OpenVINS dep) | Required build dependency. Available via system package manager. | HIGH |
| Ceres Solver | 2.2+ | Nonlinear optimization (OpenVINS dep) | Required build dependency. `sudo apt install libceres-dev` or build from source. | HIGH |
| OpenCV | 4.x | Computer vision (OpenVINS dep) | Already in project dependencies (opencv-python-headless). Need the C++ dev libraries for build. | HIGH |
| Boost | 1.71+ | C++ utilities (OpenVINS dep) | `sudo apt install libboost-all-dev`. | HIGH |

**Integration approach -- subprocess isolation:**

OpenVINS has NO Python bindings and no pip package. The recommended pattern:

1. Build OpenVINS ROS-free from source as a standalone executable
2. Write a thin C++ harness that reads frames from stdin/shared-memory and writes poses to stdout/shared-memory
3. Python backend spawns OpenVINS as a subprocess, communicates via:
   - **Option A (recommended):** Shared memory (`multiprocessing.shared_memory`) for frame data + Unix domain socket for control messages
   - **Option B (simpler):** Named pipes with msgpack-serialized frames (higher latency, ~2-5ms overhead)

**Why subprocess over pybind11 wrapper:**
- OpenVINS codebase is large (~50 KLOC) with deep Eigen/Ceres dependencies
- Writing pybind11 wrappers for `VioManager` is possible but fragile across versions
- Subprocess isolation prevents C++ crashes from taking down the Python process
- MuJoCo simulation already runs at ~30 FPS; 2-5ms subprocess overhead is negligible

**Caveat:** OpenVINS requires IMU data. MuJoCo provides simulated IMU via `mj_sensordata`. The bridge must extract accelerometer + gyroscope readings alongside RGB-D frames. This is a NEW sensor requirement not present in the v1.0 ICP pipeline.

### SLAM Backend: SVO Pro

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| rpg_svo_pro_open (source build) | master | Semi-direct Visual Odometry | 400 FPS on i7, 55 FPS on ARM. Semi-direct method (direct tracking + feature mapping). Supports mono/stereo/multi-cam. Loop closure + global BA via GTSAM integration. | LOW |

**Integration approach -- subprocess isolation (same pattern as OpenVINS):**

SVO Pro has NO Python bindings. It is a catkin/CMake project designed for ROS. Building ROS-free requires:

1. Clone `rpg_svo_pro_open` and its dependencies (vikit, rpg_common)
2. Set `USE_ROS=FALSE` in CMakeLists.txt
3. Manually resolve catkin-isms in the build (replace catkin_simple macros with standard CMake)
4. Build as a standalone C++ library/executable

**This is the highest-risk backend.** The SVO Pro open-source release is research code from 2021 with catkin entanglement. De-catkinizing it is non-trivial. Budget significant time for build system wrestling.

**Build dependencies (same as OpenVINS plus):**
- GTSAM (SVO Pro uses it for backend optimization)
- fast_neon or SSE-optimized FAST detector (bundled in repo)
- yaml-cpp for configuration

**Recommendation:** Implement SVO Pro LAST. Get ORB-SLAM3 and OpenVINS working first. If SVO Pro build proves too painful, consider substituting with a simpler visual odometry (e.g., DSO or a pure-Python semi-direct tracker using OpenCV).

### Pose-Graph Optimization

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| gtsam | 4.2 (stable) | Pose-graph optimization for map merging | **pip install gtsam**. Pre-built wheels for Python 3.8-3.11 on Linux x86_64 + macOS. Full factor graph library with SE(3) pose types, Levenberg-Marquardt/Gauss-Newton/Dogleg optimizers, incremental solving (iSAM2). Used by SVO Pro internally, so dependency is shared. | HIGH |

**Why GTSAM over g2o:**
- GTSAM has official, maintained Python wheels on PyPI (`pip install gtsam`)
- g2o-python (v0.0.12, last release May 2023) is a community wrapper, less maintained
- GTSAM achieves lower objective function values on benchmark PGO datasets
- GTSAM's iSAM2 provides incremental updates ideal for real-time map merging
- GTSAM has comprehensive Python examples and documentation
- SVO Pro already uses GTSAM internally, reducing total dependency count

**Python 3.12 compatibility note:** GTSAM 4.2 stable wheels only support Python 3.8-3.11. For Python 3.12, use `pip install gtsam-develop` (4.3a1 pre-release, published January 2026) or pin project Python to 3.11. Given pyproject.toml says `>=3.10,<3.13`, recommend testing with Python 3.11 first.

**How GTSAM replaces current map merging:**

Current `MapMerger` does union-OR voxel fusion with no optimization. Replace with:

```python
import gtsam

# Each robot's SLAM backend produces a pose trail
# Add odometry factors between consecutive poses
graph = gtsam.NonlinearFactorGraph()
initial = gtsam.Values()

# Between-pose factors from each robot's odometry
for i in range(len(poses_a) - 1):
    graph.add(gtsam.BetweenFactorPose3(
        key_a(i), key_a(i+1), relative_pose, odom_noise))

# Cross-robot loop closure factors (from shared landmark detection)
graph.add(gtsam.BetweenFactorPose3(
    key_a(i), key_b(j), relative_transform, loop_noise))

# Optimize
optimizer = gtsam.LevenbergMarquardtOptimizer(graph, initial)
result = optimizer.optimize()
```

This produces globally consistent poses. Then re-project each robot's point clouds using optimized poses for the merged map.

### Frontend Additions

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| (existing React + Zustand) | -- | Algorithm picker UI, parameter panels, metrics display | No new frontend framework dependencies needed. The algorithm selection, parameter tuning, and metrics panels are pure UI components using existing stack. | HIGH |

**Frontend architecture for SLAM controls:**
- Algorithm picker: Zustand store holds `selectedAlgorithm: 'icp' | 'orbslam3' | 'openvins' | 'svo_pro'`
- Parameter panel: JSON schema per algorithm defines tunable params, rendered as form controls
- Live metrics: WebSocket stream already exists; add SLAM-specific metrics (tracking FPS, map points, loop closures, memory usage) to the existing telemetry payload
- Output format toggle: Already have point cloud + voxel grid; add mesh visualization option via Three.js `BufferGeometry`

No new npm packages required. Three.js already handles all 3D rendering needs.

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| msgpack | 1.1+ | Binary serialization for subprocess IPC | Serializing frames/poses between Python and C++ subprocess backends | HIGH |
| pybind11 | 2.12+ | C++ Python binding generation | Only if writing custom wrappers (fallback for orbslam3-python) | HIGH |
| psutil | 6.0+ | Process/memory monitoring | Live SLAM metrics: per-backend memory usage, CPU utilization | HIGH |

### Build System Requirements

| Requirement | Purpose | Notes |
|-------------|---------|-------|
| CMake >= 3.16 | Building OpenVINS, SVO Pro from source | System package or pip install cmake |
| GCC >= 9 or Clang >= 10 | C++17 support for OpenVINS/SVO Pro | System compiler |
| Eigen3 >= 3.4 | Linear algebra (all C++ backends) | `sudo apt install libeigen3-dev` |
| libceres-dev >= 2.0 | Nonlinear optimization (OpenVINS) | `sudo apt install libceres-dev` |
| libboost-all-dev >= 1.71 | OpenVINS dependency | `sudo apt install libboost-all-dev` |
| Pangolin (optional) | ORB-SLAM3 visualization (debug only) | Only needed if building ORB-SLAM3 from source |

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| ROS / ROS 2 | Project explicitly removed ROS dependency in v1.0. All backends must build ROS-free. |
| RTAB-Map | Too heavy for multi-instance (500MB-2GB per instance). Already rejected in v1.0 for Python binding issues. |
| PCL (Point Cloud Library) | Open3D already covers all point cloud needs. PCL Python bindings are poor. |
| Pangolin (runtime) | Desktop-only 3D viewer. Project uses browser-based Three.js visualization. |
| octomap-python | CMake build fails in nix (documented in KEY DECISIONS). Keep Open3D VoxelGrid. |
| DBoW2 / FBoW | Vocabulary-based place recognition. Handled internally by ORB-SLAM3. Not needed as standalone. |
| Torch / CUDA | No NVIDIA GPU available. Deep learning backends deferred to v3.0. |
| Swarm-SLAM / COVINS-G | Collaborative SLAM systems -- overkill for 2-robot simulation. Pose-graph merging via GTSAM is simpler. |

## Installation Plan

```bash
# --- Phase 1: ORB-SLAM3 (pip-installable) ---
pip install orbslam3-python==2.0.0

# --- Phase 2: Pose-graph optimization ---
pip install gtsam==4.2       # Python 3.11
# OR
pip install gtsam-develop    # Python 3.12 (pre-release 4.3a1)

# --- Phase 3: Supporting libraries ---
pip install msgpack psutil

# --- Phase 4: OpenVINS (build from source) ---
sudo apt install libeigen3-dev libboost-all-dev libceres-dev
git clone https://github.com/rpng/open_vins.git
cd open_vins/ov_msckf && mkdir build && cd build
cmake .. -DENABLE_ROS=OFF -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
# Binary: build/run_subscribe_msckf (or custom harness)

# --- Phase 5: SVO Pro (build from source, highest risk) ---
git clone https://github.com/uzh-rpg/rpg_svo_pro_open.git
# Requires de-catkinization of CMakeLists.txt files
# Dependencies: Eigen3, OpenCV, GTSAM, yaml-cpp
# See PITFALLS.md for build system warnings
```

## Version Compatibility Matrix

| Component | Version | Python 3.11 | Python 3.12 | CPU-only | pip install |
|-----------|---------|-------------|-------------|----------|-------------|
| orbslam3-python | 2.0.0 | Yes | Yes | Yes | Yes |
| gtsam | 4.2 | Yes | No (use 4.3a1) | Yes | Yes |
| gtsam-develop | 4.3a1 | Yes | Yes | Yes | Yes |
| open_vins | v2.7+ | n/a (C++) | n/a (C++) | Yes | No (source) |
| rpg_svo_pro_open | master | n/a (C++) | n/a (C++) | Yes | No (source) |
| msgpack | 1.1+ | Yes | Yes | Yes | Yes |
| psutil | 6.0+ | Yes | Yes | Yes | Yes |

**Recommendation:** Use Python 3.11 for broadest wheel compatibility (GTSAM 4.2 stable). If staying on 3.12, use gtsam-develop 4.3a1.

## Integration Architecture

```
                    Generic SLAM API (Python ABC)
                    /          |           \          \
              ICPBackend  ORBBackend  OpenVINSBackend  SVOBackend
              (in-process) (in-process) (subprocess)   (subprocess)
                  |            |            |              |
              Open3D ICP   orbslam3-py  open_vins C++  svo_pro C++
                                          (stdin/shm)   (stdin/shm)
                    \          |           /          /
                     Pose-Graph Merger (GTSAM)
                              |
                     Merged Global Map
```

Each backend implements a common Python interface:
- `process_frame(rgb, depth, timestamp) -> SE3Pose`
- `get_landmarks() -> PointCloud`
- `get_metrics() -> dict` (FPS, memory, map points, loop closures)
- `reset()` / `shutdown()`

The in-process backends (ICP, ORB-SLAM3) call C/Python libraries directly.
The subprocess backends (OpenVINS, SVO Pro) communicate via shared memory for frame data and Unix sockets for control/results.

## Risk Assessment

| Component | Risk | Mitigation |
|-----------|------|------------|
| orbslam3-python wheels | MEDIUM -- community package, may have bugs or missing features | Fall back to pyOrbSlam3 (build from source) or pyslam's ORB tracker |
| GTSAM Python 3.12 | LOW -- pre-release 4.3a1 available | Pin to Python 3.11, or use gtsam-develop |
| OpenVINS build | LOW -- ROS-free build officially documented | Follow official guide, deps are standard |
| OpenVINS IMU requirement | MEDIUM -- v1.0 pipeline has no IMU data path | Must add IMU sensor extraction from MuJoCo (`mj_sensordata`) |
| SVO Pro build | HIGH -- catkin-entangled, last commit 2021 | Budget extra time. Have fallback (DSO or skip SVO Pro) |
| Subprocess IPC latency | LOW -- MuJoCo runs at ~30 FPS, 2-5ms overhead is fine | Benchmark early. Switch to shared memory if pipes are slow |

## Sources

- [orbslam3-python on PyPI](https://pypi.org/project/orbslam3-python/) -- MEDIUM confidence (community package)
- [pyOrbSlam3 (JHMeusener)](https://github.com/JHMeusener/pyOrbSlam3) -- MEDIUM confidence
- [pyorbslam (edavalosanaya)](https://github.com/edavalosanaya/pyorbslam) -- LOW confidence (still in development)
- [OpenVINS ROS-Free Installation Guide](https://docs.openvins.com/gs-installing-free.html) -- HIGH confidence (official docs)
- [OpenVINS v2.0 Release (ROS-Free)](https://github.com/rpng/open_vins/releases/tag/v2.0) -- HIGH confidence
- [rpg_svo_pro_open GitHub](https://github.com/uzh-rpg/rpg_svo_pro_open) -- MEDIUM confidence (research code, 2021)
- [SVO Plain CMake Wiki](https://github.com/uzh-rpg/rpg_svo/wiki/Installation:-Plain-CMake-(No-ROS)) -- MEDIUM confidence (SVO v1, not Pro)
- [GTSAM on PyPI](https://pypi.org/project/gtsam/) -- HIGH confidence (official package)
- [GTSAM 4.2 Release](https://github.com/borglab/gtsam/releases/tag/4.2) -- HIGH confidence
- [g2o-python on GitHub](https://github.com/miquelmassot/g2o-python) -- MEDIUM confidence
- [G2O vs GTSAM vs Ceres Comparison](https://medium.com/@jianzhuhuai0108/g2o-vs-gtsam-vs-ceres-solver-from-a-programmers-perspective-f45ac68a90fd) -- MEDIUM confidence
- [pySLAM v2.10.0](https://www.luigifreda.com/2026/02/08/pyslam-v-2-10-0-a-hybrid-python-c-framework-for-visual-slam-and-3d-perception/) -- MEDIUM confidence
- Project .research/report.md (internal SLAM literature review) -- HIGH confidence

---

*Stack research for v2.0 SLAM API additions: 2026-03-23*
