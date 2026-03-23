# Research Summary: v2.0 Generic SLAM API

**Domain:** Pluggable SLAM backend system for multi-robot 3D reconstruction
**Researched:** 2026-03-23
**Overall confidence:** MEDIUM

## Executive Summary

The v2.0 milestone adds a generic SLAM API abstraction layer with four backends (existing ICP, ORB-SLAM3, OpenVINS, SVO Pro), frontend controls for algorithm selection and parameter tuning, live metrics comparison, and pose-graph optimization for map merging. The existing v1.0 system (7,609 LOC Python + 2,486 LOC TypeScript) provides a solid foundation with MuJoCo simulation, ICP-based SLAM, FastAPI/WebSocket backend, and React/Three.js frontend.

The three new SLAM backends present a gradient of integration difficulty. **ORB-SLAM3** is the easiest: `orbslam3-python` v2.0.0 is pip-installable with pre-built wheels for Python 3.8-3.12. **OpenVINS** is moderate: it has an official ROS-free build path with standard dependencies (Eigen, Ceres, Boost, OpenCV) but requires writing a subprocess wrapper and adding IMU data extraction from MuJoCo (a new sensor path not present in v1.0). **SVO Pro** is the highest risk: the open-source release (rpg_svo_pro_open, last commit 2021) is entangled with the catkin build system and requires significant de-catkinization effort.

For pose-graph optimization, two viable paths exist. **Open3D's built-in GlobalOptimization** (already a project dependency) handles basic pose-graph optimization without new dependencies. **GTSAM** (pip-installable, v4.2 for Python 3.11 or v4.3a1 pre-release for 3.12) provides incremental optimization via iSAM2, which is better for real-time use but adds a dependency. Recommendation: start with Open3D PGO, upgrade to GTSAM if incremental updates are needed.

The most critical architectural insight from research: **sparse vs dense cloud mismatch**. ORB-SLAM3 and SVO Pro produce sparse feature maps (hundreds of points), while the existing pipeline expects dense clouds (tens of thousands of points) for OctoMap and visualization. The solution is to decouple: use SLAM backends for pose estimation only, and continue generating dense clouds from depth images using the SLAM-estimated pose. This preserves all downstream consumers.

## Key Findings

**Stack:** orbslam3-python 2.0.0 (pip), OpenVINS (C++ source build), SVO Pro (C++ source build, high risk), GTSAM 4.2 or Open3D PGO for map merging. No new frontend dependencies.

**Architecture:** Strategy pattern with backend registry. In-process for ICP and ORB-SLAM3 (pybind11). Subprocess isolation for OpenVINS and SVO Pro (shared memory + Unix socket IPC). PoseGraphMerger replaces MapMerger.

**Critical pitfall:** OpenVINS requires IMU data that the v1.0 sensor pipeline does not provide. Must add accelerometer/gyroscope extraction from MuJoCo before OpenVINS can work.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Backend Abstraction + ICP Wrap** -- Foundation, zero behavioral change
   - Addresses: SLAMProtocol, SLAMRegistry, ICPBackend wrapping existing SLAMPipeline
   - Avoids: New backends (prove the interface first)
   - Risk: LOW (pure refactoring)

2. **Frontend Algorithm Controls** -- End-to-end communication path
   - Addresses: Algorithm picker, parameter panel, WebSocket messages
   - Avoids: New backends (test plumbing with ICP only)
   - Risk: LOW (standard frontend components)

3. **Pose-Graph Map Merger** -- Fix the merge strategy
   - Addresses: Replace union-OR voxel merge with Open3D PGO or GTSAM
   - Avoids: Backend-specific complexity (works with ICP poses)
   - Risk: MEDIUM (PGO parameter tuning)

4. **ORB-SLAM3 Backend** -- First new backend, pip-installable
   - Addresses: orbslam3-python integration, sparse cloud handling
   - Avoids: C++ source builds (pip-installable)
   - Risk: MEDIUM (community package quality)

5. **OpenVINS Backend** -- VIO category, requires new sensor path
   - Addresses: IMU extraction from MuJoCo, OpenVINS C++ build, subprocess wrapper
   - Avoids: SVO Pro (easier build than SVO Pro)
   - Risk: MEDIUM-HIGH (new sensor dependency + C++ build)

6. **SVO Pro Backend + Live Metrics Dashboard** -- Highest risk backend + polish
   - Addresses: SVO Pro de-catkinization, metrics comparison UI
   - Avoids: Nothing left
   - Risk: HIGH (catkin build system, 2021 codebase)

**Phase ordering rationale:**
- Phase 1 creates the foundation every other phase depends on
- Phase 2 establishes the frontend-backend communication before adding complexity
- Phase 3 fixes map merging early so all backends benefit from day one
- Phase 4 (ORB-SLAM3) is the easiest new backend -- validates the subprocess/binding pattern
- Phase 5 (OpenVINS) adds IMU pipeline -- bigger scope but documented build path
- Phase 6 (SVO Pro) is highest risk -- doing it last means failure does not block other features

**Research flags for phases:**
- Phase 1-2: Standard patterns, unlikely to need research
- Phase 3: May need deeper research on Open3D PGO vs GTSAM tradeoffs
- Phase 4: NEEDS validation -- test orbslam3-python on target Python version early
- Phase 5: NEEDS research -- MuJoCo IMU sensor configuration, OpenVINS data format expectations
- Phase 6: LIKELY needs research -- SVO Pro build system, possible fallback to DSO

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | ORB-SLAM3 pip package verified on PyPI; GTSAM verified; OpenVINS/SVO Pro build paths documented but untested |
| Features | HIGH | Requirements clearly defined in PROJECT.md; feature dependencies well-mapped |
| Architecture | HIGH | Strategy + Registry pattern is standard; subprocess isolation well-understood; codebase integration points identified |
| Pitfalls | MEDIUM-HIGH | C++ build issues well-documented; sparse/dense mismatch identified from research; IMU requirement discovered |

## Gaps to Address

- **orbslam3-python actual API surface** -- need to verify `get_frame_pose()` and `get_current_points()` methods exist and work correctly
- **MuJoCo Go2 model IMU sensors** -- need to check if accelerometer/gyroscope sensors are defined in the Go2 XML model, or if they need to be added
- **OpenVINS IMU-camera synchronization requirements** -- OpenVINS expects IMU at higher rate than camera; need to determine exact ratio
- **SVO Pro license** -- rpg_svo_pro_open uses GPL-3.0 but some docs mention "non-commercial" restrictions; clarify before integrating
- **Open3D PGO performance at scale** -- how many pose graph nodes before batch optimization becomes too slow for real-time?
- **Python version decision** -- 3.11 (broad wheel compatibility) vs 3.12 (current project default). GTSAM compatibility is the deciding factor.

---

*Research summary: 2026-03-23 -- v2.0 Generic SLAM API milestone*
