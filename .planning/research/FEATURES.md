# Feature Landscape: v2.0 Generic SLAM API

**Domain:** Multi-robot 3D reconstruction with pluggable SLAM backends
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH (existing codebase verified; SLAM API patterns well-documented in pySLAM/SlamPy; backend availability verified via PyPI/GitHub)

## Table Stakes

Features users expect from a pluggable SLAM abstraction with frontend controls. Missing = the abstraction layer provides no value over the hardcoded ICP pipeline.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Abstract SLAM backend interface (Protocol/ABC)** | The entire milestone exists to decouple SLAM from the system. Without an interface, there is no pluggability. | Low | None (new code) | Define a Python Protocol with `process_frame(frame) -> pose`, `reset()`, `global_cloud`, `slam_poses`, `get_cloud_points()`, `get_cloud_colors()`. Mirror the existing `SLAMPipeline` public surface exactly so the ICP backend is a trivial refactor. SlamPy uses this same pattern: a `System` class wrapping arbitrary SLAM methods behind `process_image_*` methods. |
| **Backend registry with discovery** | Users/developers need to register and discover available backends without editing core code. Without a registry, "pluggable" is just marketing. | Low | Abstract interface | Dictionary-based registry: `@slam_backend("icp")` decorator or `SLAMRegistry.register("icp", ICPBackend)`. Factory method returns configured backend by name string. SlamPy uses YAML config (`SLAM.alg: ORB_SLAM3`); pySLAM uses a feature extractor registry. The decorator pattern is more Pythonic and aligns with the existing codebase style. |
| **ICP backend (existing, wrapped)** | Baseline. Proves the abstraction works by wrapping what already exists. Regression test: system must behave identically to v1.0 after the refactor. | Low | Abstract interface, registry | Wrap current `SLAMPipeline` as `ICPBackend(SLAMBackend)`. Zero new algorithm code -- just interface adaptation. This is the proof that the abstraction is correct. |
| **ORB-SLAM3 backend** | The most-cited feature-based visual SLAM. Expected in any multi-algorithm SLAM comparison. Provides sparse feature maps and robust loop closure. | High | Abstract interface, ORB-SLAM3 Python bindings (`orbslam3-python` on PyPI, pybind11-based) | orbslam3-python v2.0.0 (Oct 2025) provides `get_frame_pose()` returning numpy array and `get_current_points()` for feature positions. Requires vocabulary file download and YAML camera config. Returns sparse maps (feature points only, not dense reconstruction) -- this is a fundamental difference from ICP. The backend must handle this: expose sparse points as the "cloud" or mark cloud output as unavailable. |
| **OpenVINS backend** | Visual-inertial navigation system (MSCKF-based EKF). Required to demonstrate VIO category. CPU-friendly. | High | Abstract interface, OpenVINS C++ build, subprocess bridge | OpenVINS has NO native Python bindings. Integration via subprocess with stdin/stdout/shared-memory protocol. Requires IMU data -- MuJoCo provides gyroscope/accelerometer via `mj_sensorData`. Must add IMU to sensor frame pipeline. |
| **SVO Pro backend** | Semi-direct VO, extremely fast (400 FPS on i7). Required for the "fast but less accurate" comparison point. | High | Abstract interface, SVO Pro C++ build, subprocess bridge | Like OpenVINS, SVO Pro is C++ only. Same subprocess integration challenge. rpg_svo_pro_open is the open-source version. Non-commercial research license -- compatible with this project. |
| **Pre-session algorithm selection** | User must choose which SLAM backend to use before starting simulation. This is the minimum viable "algorithm picker." | Low | Registry, frontend WebSocket command | Dropdown in ControlPanel that lists registered backends. Sends `{ type: "set_slam_backend", backend: "orb_slam3" }` via existing WebSocket. Backend validates before simulation starts. Simple -- no hot-swap, no runtime complexity. |
| **Per-algorithm parameter panel** | Each SLAM backend has different tunable parameters (voxel_size for ICP, num_features for ORB-SLAM3, etc.). Users must see and modify these. | Medium | Registry exposes parameter schema, frontend renders dynamically | Each backend declares a `get_params() -> dict` and `set_params(dict)` interface. Frontend renders a dynamic form from the schema. Use typed parameter descriptors: `{ name, type, default, min, max, description }`. |
| **Live SLAM metrics display** | Without metrics, users cannot compare backends meaningfully. The metrics dashboard IS the comparison tool. | Medium | Backend emits metrics per frame, WebSocket streaming | Standard SLAM metrics to emit per-frame: (1) **ATE** -- absolute trajectory error vs ground truth (MuJoCo provides GT poses), (2) **Processing time** (ms/frame), (3) **Memory usage** (point count, estimated MB), (4) **Tracking status** (OK/LOST/INITIALIZING). Stream via existing WebSocket as `{ type: "slam_metrics", ... }`. Display as time-series sparklines or gauges in Sidebar. |
| **Pose-graph optimization for map merging** | PROJECT.md explicitly requires replacing ICP-based map merging with PGO. This is the backend for the merge server, not per-robot SLAM. | High | GTSAM Python bindings, pose data from backends | GTSAM has mature Python bindings (`pip install gtsam`). Build pose graph from per-robot SLAM poses + inter-robot constraints (overlap detection). Replace current voxel-fusion merge with optimized global pose graph + cloud re-alignment. |

## Differentiators

Features that elevate beyond a basic abstraction layer. Not expected, but significantly improve the experience.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Hot-swap algorithm at runtime** | Change SLAM backend mid-session without restarting. PROJECT.md marks this as "stretch goal." | High | Stateful handoff protocol, frontend live-switch UI | Requires: (1) serialize current pose to hand off, (2) re-initialize new backend at current pose, (3) handle cloud continuity. Risk: some backends (ORB-SLAM3) need initialization sequences that cannot start mid-trajectory. Recommend: allow hot-swap but reset the map, keeping only the current pose estimate. |
| **Side-by-side algorithm comparison** | Run two SLAM backends simultaneously on the same sensor stream, show metrics for both in real-time. | Medium | Duplicate pipeline, doubled CPU cost, split-view metrics UI | Run same `SensorFrame` through two backend instances. Display comparison table. CPU cost is the constraint. |
| **Output format toggle (point cloud / voxel grid / mesh)** | PROJECT.md lists this. Different backends produce different native outputs; users want to visualize in their preferred format. | Medium | Open3D conversion pipeline, Three.js rendering modes | Conversion pipeline: point cloud (raw) -> voxel grid (`VoxelGrid`) -> mesh (Poisson/BPA reconstruction). Frontend Three.js already renders point clouds; add `THREE.BoxGeometry` instancing for voxels and `THREE.Mesh` for surfaces. |
| **RPE (Relative Pose Error) metric** | ATE shows global accuracy; RPE shows local consistency and drift rate. Together they fully characterize SLAM performance. | Low | Ground truth poses (already available from MuJoCo) | Standard metric from TUM RGB-D benchmark. Simple to implement (~30 lines). |
| **Automatic backend capability detection** | Some backends produce dense clouds (ICP), some produce sparse (ORB-SLAM3), some need IMU (OpenVINS). The system should know and adapt. | Low | Backend metadata in registry | Each backend declares capabilities: `{ produces_dense_cloud: bool, requires_imu: bool, supports_loop_closure: bool }`. Frontend uses this to gray-out unavailable output formats and warn about missing sensors. |
| **Parameter presets per backend** | "Accuracy mode" vs "Speed mode" vs "Balanced" for each algorithm. | Low | Parameter panel infrastructure | Store 2-3 preset configurations per backend. Dropdown in parameter panel. |
| **SLAM trajectory visualization** | Show the estimated trajectory overlaid with ground truth in the Three.js viewer. | Low | Pose data already streamed, Three.js `Line` geometry | Render `THREE.Line` for estimated trajectory (colored by backend) and a second line for GT. |
| **Export metrics to CSV/JSON** | Allow users to download comparison data for external analysis. | Low | Metrics accumulation, download endpoint | Add `/api/metrics/export?format=csv` endpoint. Frontend adds a "Download Metrics" button. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Deep learning SLAM backends (DROID-SLAM, DPV-SLAM, SplaTAM)** | PROJECT.md explicitly defers to v3.0. Requires NVIDIA GPU which user does not have. | Stick to CPU-compatible backends. Document the interface so GPU backends can be added in v3.0. |
| **ROS 2 as middleware** | v1.0 eliminated ROS dependencies. Re-introducing ROS contradicts that achievement. | Integrate C++ backends via subprocess, NOT via ROS topics. |
| **Custom SLAM algorithm implementation** | Writing a novel SLAM algorithm is a multi-year PhD project. | Wrap proven implementations. The abstraction layer's value is in composition, not computation. |
| **Full EVO benchmark suite integration** | The `evo` library is powerful but heavyweight. | Implement ATE and RPE calculations directly (~50 lines each). Keep evo as optional dev dependency. |
| **Real-time mesh reconstruction toggle** | Poisson/BPA mesh reconstruction is slow (seconds per update). | Offer mesh as an on-demand "Generate Mesh" button, not a continuous mode. |
| **Backend-specific custom UI components** | Building a unique UI panel for each SLAM backend violates the abstraction principle. | Use the dynamic parameter panel (typed schema -> auto-generated controls). |
| **Multi-session persistence / map saving** | Useful but orthogonal to the comparison goal. | Each session starts fresh. Map export as .ply is sufficient. |

## Feature Dependencies

```
Backend Interface (Protocol/ABC)
  |
  +---> ICP Backend (wrap existing SLAMPipeline)
  |       |
  |       +---> Regression tests (v1.0 behavior preserved)
  |
  +---> ORB-SLAM3 Backend
  |       |
  |       +---> orbslam3-python bindings (PyPI)
  |       +---> ORB vocabulary file
  |       +---> Sparse cloud handling
  |
  +---> OpenVINS Backend
  |       |
  |       +---> C++ build / subprocess bridge
  |       +---> IMU sensor data pipeline (NEW -- add to SensorFrame)
  |
  +---> SVO Pro Backend
  |       |
  |       +---> C++ build / subprocess bridge
  |
  +---> Backend Registry
          |
          +---> Parameter schema system
          |       |
          |       +---> Dynamic parameter panel (frontend)
          |       +---> Parameter presets
          |
          +---> Capability metadata
          |       |
          |       +---> Frontend capability-aware UI
          |
          +---> Algorithm picker (frontend dropdown)
                  |
                  +---> WebSocket command: set_slam_backend
                  +---> Pre-session selection enforcement

Metrics Pipeline (parallel to above):
  |
  +---> Per-frame metric emission from backends
  |       |
  |       +---> ATE computation (vs MuJoCo ground truth)
  |       +---> Processing time measurement
  |       +---> Memory/point count tracking
  |       +---> Tracking status
  |
  +---> WebSocket metrics streaming
  |       |
  |       +---> Metrics dashboard (frontend)
  |       +---> Time-series sparklines
  |
  +---> Metrics export (CSV/JSON)

Pose-Graph Optimization (replaces voxel-fusion merge):
  |
  +---> GTSAM Python bindings
  +---> Pose graph construction from backend poses
  +---> Inter-robot constraint detection
  +---> Optimized global map re-alignment
  +---> Replaces current map_merger.py voxel fusion
```

## MVP Recommendation

**Phase 1 -- Backend Abstraction + ICP Wrap (prove the interface):**
1. Define `SLAMBackend` Protocol with methods mirroring existing `SLAMPipeline`
2. Create `SLAMRegistry` with decorator-based registration
3. Wrap existing `SLAMPipeline` as `ICPBackend`
4. Add parameter schema system (`get_param_schema()`, `get_params()`, `set_params()`)
5. Wire through exploration loop to use registry instead of direct `SLAMPipeline`
6. Regression test: system behavior identical to v1.0

**Phase 2 -- Frontend Algorithm Selection + Parameter Panel:**
7. Algorithm picker dropdown in ControlPanel (pre-session only)
8. Dynamic parameter panel rendered from backend schema
9. WebSocket commands for backend selection and parameter updates
10. Parameter presets (balanced/accurate/fast) per backend

**Phase 3 -- Metrics Pipeline:**
11. Per-frame metric emission (ATE, processing time, memory, status)
12. WebSocket metrics streaming
13. Metrics dashboard in Sidebar (sparklines/gauges)
14. Ground truth comparison using MuJoCo poses

**Phase 4 -- Second Backend (ORB-SLAM3):**
15. Integrate orbslam3-python bindings
16. Implement `ORBSlam3Backend` adapter
17. Handle sparse cloud output (different from dense ICP)
18. Test algorithm switching between ICP and ORB-SLAM3

**Phase 5 -- Remaining Backends + PGO:**
19. OpenVINS backend (requires IMU pipeline addition)
20. SVO Pro backend (requires C++ subprocess bridge)
21. GTSAM-based pose-graph optimization for map merging
22. Replace voxel fusion in map merger

**Phase 6 -- Polish + Differentiators:**
23. Output format toggle (point cloud / voxel grid / on-demand mesh)
24. Side-by-side comparison mode (stretch)
25. Trajectory visualization overlay
26. Metrics CSV export

**Defer to v3.0:**
- Hot-swap algorithm at runtime (complex state handoff)
- Deep learning SLAM backends (GPU required)
- Full EVO benchmark integration

**Rationale:** The abstraction layer (Phase 1) is pure refactoring with zero behavioral change and must come first. Frontend controls (Phase 2) can be built in parallel. Metrics (Phase 3) provide the comparison framework before adding new backends. ORB-SLAM3 (Phase 4) is the easiest additional backend (pip-installable). OpenVINS and SVO Pro (Phase 5) are hardest (C++ builds, no Python bindings). PGO (Phase 5) replaces merge strategy and benefits from having multiple backends producing poses.

## Sources

- [SlamPy -- generic SLAM wrapper pattern](https://github.com/GiordanoLaminetti/SlamPy) -- MEDIUM confidence
- [pySLAM v2.10.0 -- modular SLAM framework](https://github.com/luigifreda/pyslam) -- HIGH confidence
- [orbslam3-python on PyPI](https://pypi.org/project/orbslam3-python/) -- HIGH confidence (verified package, v2.0.0)
- [OpenVINS docs](https://docs.openvins.com/) -- HIGH confidence
- [SVO Pro open-source](https://github.com/uzh-rpg/rpg_svo_pro_open) -- HIGH confidence
- [GTSAM Python bindings](https://gtbook.github.io/gtsam-examples/Pose2SLAMExample.html) -- HIGH confidence
- Existing codebase: `src/slam/slam_pipeline.py`, `src/coordination/map_merger.py` -- HIGH confidence

---

*Feature research: 2026-03-23 -- v2.0 Generic SLAM API milestone*
