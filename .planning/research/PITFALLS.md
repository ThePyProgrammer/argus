# Domain Pitfalls

**Domain:** Generic SLAM API abstraction layer with pluggable C++ backends for multi-robot 3D reconstruction
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH (C++ SLAM library build issues well-documented in GitHub issues; abstraction layer patterns verified against existing codebase; coordinate frame issues verified from official docs)

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: ORB-SLAM3 Build Dependency Hell

**What goes wrong:** ORB-SLAM3 has a notoriously fragile build system with vendored copies of g2o, DBoW2, and Sophus that conflict with system-installed versions. The main CMakeLists.txt expects specific Eigen3 versions, specific OpenCV versions (>4.4), and Pangolin -- all of which may conflict with versions already installed for Open3D or other project dependencies.

**Why it happens:** ORB-SLAM3 was designed as a monolithic research project, not a library. Its build.sh script builds Thirdparty/ subfolders in-tree. The vendored g2o conflicts with any system g2o (which GTSAM also uses). Eigen version mismatches between ORB-SLAM3's Sophus dependency and Open3D's Eigen are common. The C++ standard must be manually bumped from C++11 to C++14 on modern compilers.

**Consequences:** Build failures that take days to debug. Even when it compiles, linking the resulting .so into a Python binding (via pybind11) can produce runtime symbol conflicts with Open3D's linked Eigen or OpenCV. The project currently uses Python 3.14 which may not be supported by older pybind11 versions in ORB-SLAM3 forks.

**Prevention:**
- Use an isolated build environment (Docker container or Nix derivation) for ORB-SLAM3 compilation, separate from the project's venv
- Use the `pyorbslam` or `orbslam3-python` PyPI packages which wrap the build complexity, but verify they work with Python 3.14 first -- these packages only provide AMD64 pre-built binaries
- Pin exact versions: Eigen 3.3.7, OpenCV 4.8+, Pangolin 0.6+
- Build ORB-SLAM3 as a shared library (.so) and load it via ctypes or a thin pybind11 wrapper, keeping it isolated from Open3D's linked libraries
- Convert ORBvoc.txt to ORBvoc.bin (binary vocabulary) -- text format takes ~20 seconds to load, binary takes ~0.5 seconds. This matters for algorithm switching.

**Detection:** If `import orbslam3` causes a segfault or `undefined symbol` error, you have a symbol conflict. Run `ldd` on the .so to check for conflicting library versions.

**Sources:**
- [ORB-SLAM3 Build Failures (GitHub Issues)](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/668)
- [Eigen/Sophus Build Errors](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/794)
- [OpenCV Version Mismatch](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/456)
- [Pangolin Build Error](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/374)
- [pyOrbSlam3 Python Bindings](https://github.com/JHMeusener/pyOrbSlam3)
- [Binary Vocabulary Speedup](https://github.com/raulmur/ORB_SLAM2/pull/21)

### Pitfall 2: Lowest-Common-Denominator Abstraction Destroys Backend Value

**What goes wrong:** The abstraction interface is designed to accommodate all backends equally, resulting in an API so generic it cannot expose backend-specific strengths. ORB-SLAM3's multi-map Atlas, OpenVINS's arbitrary N-camera support, and SVO Pro's 400fps semi-direct tracking all become invisible behind a `process_frame() -> pose` interface.

**Why it happens:** The natural instinct is to make the interface as simple as the existing `SLAMPipeline.process_frame(frame: SensorFrame) -> np.ndarray`. But the existing ICP pipeline is stateless frame-to-frame matching -- it has no concept of keyframes, loop closures, map points, or tracking states. Forcing sophisticated backends into this interface wastes their capabilities.

**Consequences:**
- ORB-SLAM3's loop closure never fires because the API doesn't expose when/whether it happened
- OpenVINS's IMU integration is impossible because `SensorFrame` has no IMU field
- SVO Pro's tracking quality feedback (TRACKING_GOOD/BAD/LOST) is swallowed
- The "live SLAM metrics comparison" feature (a project requirement) cannot report backend-specific metrics
- Algorithm switching becomes meaningless because all backends behave identically through the narrow interface

**Prevention:**
- Design a two-tier API: a **minimal common interface** for pose output (`process_frame -> SlamResult` with pose + status + timing), plus **capability queries** that let callers discover and use backend-specific features
- The `SlamResult` dataclass should include: pose (4x4), tracking_status (enum: TRACKING/LOST/RELOCALIZED), confidence (float), num_features (int), timing_ms (float), and an optional `extras: dict` for backend-specific data
- Add a `capabilities()` method returning a set of enums (HAS_LOOP_CLOSURE, HAS_MAP_POINTS, HAS_MULTI_MAP, HAS_IMU_FUSION)
- Extend `SensorFrame` with optional `imu_data: list[ImuSample] | None` field for VIO backends
- Do NOT try to unify map representations across backends -- let each backend expose its native map type through a separate `get_map()` method with backend-specific return types

**Detection:** If adding a new backend requires zero API changes, the API is probably too narrow. If adding a new backend requires changing the core interface, the API is probably too rigid. The sweet spot: core interface unchanged, new capability flags added.

### Pitfall 3: Coordinate Frame Convention Mismatch Between Backends

**What goes wrong:** Each SLAM backend uses different coordinate frame conventions. OpenVINS uses x-forward, y-left, z-up (FLU). ORB-SLAM3 uses camera-optical convention (z-forward, x-right, y-down). SVO Pro uses yet another convention. The existing ICP pipeline outputs poses in MuJoCo's world frame (seeded from ground truth). Mixing these without explicit transforms produces poses that are correct in magnitude but wrong in orientation.

**Why it happens:** There is no universal standard for SLAM coordinate frames. OpenVINS's convention is documented in [GitHub Issue #61](https://github.com/rpng/open_vins/issues/61) and [Issue #277](https://github.com/rpng/open_vins/issues/277). ORB-SLAM3 operates in camera frame internally. The existing codebase seeds the initial SLAM pose from `frame.ground_truth_pose` (MuJoCo world frame) and chains ICP transforms -- this implicit convention will break when a backend imposes its own frame.

**Consequences:** Robot appears to drive sideways. Map points are rotated 90 degrees. The merged map from two robots using different backends is completely wrong. These bugs are subtle -- the trajectory might look "almost right" but be in a flipped coordinate system, causing navigation failures in specific directions.

**Prevention:**
- Define an explicit `WorldFrame` convention for the project (recommend: MuJoCo's convention, which is z-up, matching the existing codebase)
- Each backend adapter MUST include a `T_world_from_backend` static transform that converts from the backend's output frame to the project's world frame
- Write a `slam_frame_test` that runs each backend on a known straight-line trajectory and asserts the output pose moves in the expected world-frame direction
- Document the convention in the SLAM API protocol class docstring: "All poses returned by process_frame() MUST be in MuJoCo world frame (z-up, right-handed)"
- Store the transform as a class attribute on each backend adapter, not as a config parameter -- it's inherent to the backend, not configurable

**Detection:** Run all backends on the same 10-frame test sequence. If any backend's trajectory orientation differs from ICP baseline by more than 10 degrees (after applying the frame transform), the transform is wrong.

**Sources:**
- [OpenVINS Coordinate System Issue](https://github.com/rpng/open_vins/issues/277)
- [OpenVINS Axes Confusion](https://github.com/rpng/open_vins/issues/61)
- [ORB-SLAM3 Coordinate System](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/681)

### Pitfall 4: SVO Pro's ROS/catkin Build Requirement in a Non-ROS Project

**What goes wrong:** SVO Pro (rpg_svo_pro_open) is built exclusively with catkin (ROS build system). The project has no ROS dependency and uses a vanilla Python venv. Attempting to build SVO Pro requires installing ROS (or at least catkin), which pulls in hundreds of packages and fundamentally changes the build environment.

**Why it happens:** SVO Pro was developed as a ROS package at ETH Zurich. Its CMakeLists.txt uses `catkin_package()`, `catkin_simple`, and depends on `vikit_common`, `vikit_ros`, `svo_ros`, etc. There is no standalone CMake build path.

**Consequences:** Either the entire project adopts ROS (massive scope increase, breaks the existing FastAPI+venv architecture), or SVO Pro integration is blocked. Teams waste days trying to strip catkin from the build only to find deep dependencies on ROS message types.

**Prevention:**
- **Option A (recommended):** Fork rpg_svo_pro_open and create a standalone CMake build that removes catkin/ROS dependencies. This requires replacing `catkin_simple` with plain CMake, removing `svo_ros` (the ROS wrapper), and keeping only `svo_common`, `svo_direct`, `svo_tracker`, and `vikit_common`. The core algorithm has no actual ROS dependency -- it's the build system and I/O layer that depend on ROS.
- **Option B:** Build SVO Pro inside a catkin workspace in a Docker container, produce a shared library, and load it in the main project via ctypes/pybind11. This isolates the ROS dependency to build-time only.
- **Option C:** Use the original SVO (not SVO Pro) which has a simpler build. You lose loop closure and VIO, but gain a much easier integration path. For a simulation with ground-truth odometry available, loop closure is less critical.
- Evaluate effort honestly: if the fork approach takes more than 3 days, drop SVO Pro and substitute with Basalt or SchurVINS which have cleaner standalone builds.

**Detection:** If `cmake ..` fails with "Could not find catkin" or "catkin_simple not found", you've hit this pitfall.

**Sources:**
- [rpg_svo_pro_open GitHub](https://github.com/uzh-rpg/rpg_svo_pro_open)
- [SVO Pro build dependencies](https://github.com/uzh-rpg/rpg_svo_pro_open/blob/master/doc/vio.md)

### Pitfall 5: Breaking Existing ICP Pipeline During Abstraction Refactor

**What goes wrong:** While extracting a generic SLAM API from the existing `SLAMPipeline` class, the refactor introduces regressions in the working ICP backend. The current code has subtle behaviors that are easy to break: initial pose seeding from ground truth (line 70-71), fitness threshold fallback (line 98), periodic outlier removal (line 84), hard-capped cloud size (lines 117-122), and the prev_cloud being rebuilt from raw depth each frame (lines 125-127).

**Why it happens:** The existing `SLAMPipeline` is tightly coupled -- pose estimation, cloud transformation, cloud accumulation, and periodic downsampling are all interleaved in `process_frame()`. Extracting a clean interface requires separating "odometry" (pose estimation) from "mapping" (cloud accumulation), but the current design interleaves them: the cloud is transformed by the pose, then accumulated, in the same method call.

**Consequences:** The v1.0 system stops working. Multi-robot coordination, exploration, and visualization all depend on `SLAMPipeline`'s exact behavior. If the ICP backend wrapper subtly changes timing or output format, downstream components break in hard-to-diagnose ways.

**Prevention:**
- Write characterization tests for the existing `SLAMPipeline` BEFORE any refactoring: capture exact pose outputs, cloud sizes, and timing for a fixed 20-frame test sequence
- The ICP backend adapter should literally wrap the existing `SLAMPipeline` class, not reimplement it. `IcpBackend.process_frame()` should delegate to `SLAMPipeline.process_frame()` and wrap the result
- Keep `SLAMPipeline` untouched as `src/slam/slam_pipeline.py` and create `src/slam/backends/icp_backend.py` that imports and wraps it
- Run the full system end-to-end after the refactor -- automated tests are not sufficient, the integration behavior matters
- Keep the existing `RobotInstance.create()` factory working with the ICP backend by default

**Detection:** Run the full multi-robot exploration for 60 seconds before and after refactoring. Compare: total voxels discovered, final trajectory length, and final pose accuracy vs ground truth. Any regression >5% means the refactor broke something.

## Moderate Pitfalls

### Pitfall 6: OpenVINS Requires IMU Data That MuJoCo Simulation May Not Provide Correctly

**What goes wrong:** OpenVINS is a Visual-Inertial Odometry system -- it requires synchronized IMU measurements (accelerometer + gyroscope at 200-400 Hz) alongside camera images. MuJoCo can provide simulated IMU data via its sensor API, but the data characteristics (noise model, bias, sampling rate) may not match what OpenVINS expects from a real IMU.

**Why it happens:** OpenVINS's EKF is tuned for real IMU noise characteristics. MuJoCo's simulated accelerometer/gyroscope have configurable noise but default to zero noise. Running OpenVINS with perfect IMU data (zero noise, zero bias) can cause filter divergence because the Kalman filter's noise model doesn't match reality.

**Prevention:**
- Add realistic IMU noise to MuJoCo sensors: accelerometer noise ~0.003 m/s^2/sqrt(Hz), gyroscope noise ~0.0003 rad/s/sqrt(Hz), with small random biases
- Use OpenVINS's ROS-free build path (`cmake -DENABLE_ROS=OFF`) -- it exists but is less tested than the ROS path
- Feed IMU data through the `VioManager` C++ API directly, using the simulator example (`run_simulation`) as reference
- If IMU integration proves too difficult, OpenVINS becomes a visual-only system with degraded performance -- consider whether this defeats the purpose of including it
- Alternative: replace OpenVINS with Basalt VIO (similar capability, better standalone build) or SchurVINS (newest, lowest CPU usage)

**Detection:** If OpenVINS immediately diverges (pose jumps to infinity within 5 frames) or produces perfectly smooth trajectories with zero noise, the IMU data is misconfigured.

**Sources:**
- [OpenVINS ROS-Free Installation](https://docs.openvins.com/gs-installing-free.html)
- [OpenVINS IMU configuration docs](https://docs.openvins.com/)

### Pitfall 7: ORB-SLAM3 Vocabulary Loading Blocks Algorithm Switching

**What goes wrong:** ORB-SLAM3 loads a 48MB vocabulary file (ORBvoc.txt) on initialization, which takes ~20 seconds in text format. The "frontend algorithm picker" feature requires switching algorithms, but users will not tolerate a 20-second delay every time they select ORB-SLAM3.

**Why it happens:** DBoW2 vocabulary loading is inherently slow in text format. The vocabulary is a tree structure with ~1M nodes that must be parsed and rebuilt.

**Prevention:**
- Pre-convert to binary format (ORBvoc.bin): reduces load time from ~20s to ~0.5s
- Pre-initialize all backends at startup, not on-demand. Keep them in a "paused" state, ready to receive frames
- If pre-initialization uses too much RAM (ORB-SLAM3 baseline is ~500MB), lazy-initialize on first selection but show a loading indicator in the frontend
- For the "pre-session selection" model (current plan), this is less critical since switching happens before exploration starts. But for the hot-swap stretch goal, pre-initialization is mandatory.

**Detection:** If algorithm switching takes >2 seconds, vocabulary loading is the bottleneck.

### Pitfall 8: Map Representation Mismatch When Switching Backends Mid-Session

**What goes wrong:** The hot-swap stretch goal requires switching SLAM backends during a running session. But each backend maintains internal state (map points, keyframes, pose graph) in completely different formats. Switching from ICP to ORB-SLAM3 means ORB-SLAM3 has no prior map -- it starts from scratch, losing all accumulated mapping. The global point cloud accumulated by ICP is meaningless to ORB-SLAM3.

**Why it happens:** SLAM backends are stateful systems. ORB-SLAM3 tracks ORB features and maintains a covisibility graph. OpenVINS maintains an EKF state vector with feature positions. ICP maintains only the previous frame's point cloud. These internal states are not interchangeable.

**Consequences:** After switching, there is a "map discontinuity" -- the new backend starts building a fresh map from the current position, but the old map is frozen. The merged global map has a visible seam. Worse, exploration's frontier detection may re-explore already-mapped areas because the new backend's local map is empty.

**Prevention:**
- For the pre-session selection model (primary plan): this is a non-issue. Implement this first.
- For hot-swap (stretch goal): transfer only the accumulated global point cloud and the current pose to the new backend. The new backend starts tracking from the current pose but the global map is preserved externally (in the OctoMapBuilder, which is backend-independent)
- Keep the OctoMapBuilder and global cloud accumulation OUTSIDE the SLAM backend abstraction. The backend provides poses; the map accumulation layer is shared infrastructure that persists across backend switches
- Do not attempt to convert ORB-SLAM3 map points to OpenVINS EKF state or vice versa -- this is an unsolved research problem

**Detection:** After a mid-session switch, if coverage percentage drops or the robot re-explores areas it already mapped, the map continuity is broken.

### Pitfall 9: GTSAM/g2o Version Conflict for Pose Graph Optimization

**What goes wrong:** Replacing ICP-based map merging with pose-graph optimization requires a graph optimization library. GTSAM and g2o are the two options. But ORB-SLAM3 vendors its own modified g2o internally. If the project also installs g2o (or GTSAM, which links against g2o-compatible types), symbol conflicts arise at link time or runtime.

**Why it happens:** ORB-SLAM3's Thirdparty/g2o is a modified fork. System-installed g2o has different symbol names for the same types. Two versions of g2o loaded in the same process cause undefined behavior.

**Prevention:**
- Use GTSAM (not g2o) for the project-level pose-graph optimization. GTSAM has clean Python bindings via pybind11 (`pip install gtsam`), does not conflict with ORB-SLAM3's vendored g2o, and is easier to use
- Keep ORB-SLAM3's g2o isolated inside its shared library -- do not export g2o symbols from the ORB-SLAM3 .so
- If using GTSAM Python bindings, verify they work with Python 3.14 before committing to this path
- The pose-graph optimizer should be a separate component from the SLAM backends -- it consumes relative pose constraints from any backend and produces globally consistent poses

**Detection:** If `import gtsam` works in isolation but segfaults after `import orbslam3`, you have a symbol conflict.

**Sources:**
- [g2o Python Bindings](https://github.com/uoip/g2opy)
- [GTSAM Pose Graph Examples](https://gtbook.github.io/gtsam-examples/Pose2SLAMExample_g2o.html)

### Pitfall 10: Frontend State Explosion from Algorithm-Specific Parameters

**What goes wrong:** Each SLAM backend has different tunable parameters. ORB-SLAM3 has ~50 YAML parameters (nFeatures, scaleFactor, nLevels, etc.). OpenVINS has ~30 (max_cameras, num_pts, etc.). SVO Pro has its own set. The "per-algorithm parameter tuning panel" becomes a maintenance nightmare -- every new backend requires new frontend components, new WebSocket message types, and new Zustand store slices.

**Why it happens:** The current `controlStore.ts` has a flat structure. Adding per-algorithm parameter state means either a massive union type or duplicated stores.

**Prevention:**
- Backend adapters should expose parameters as a JSON schema: `{"name": "nFeatures", "type": "int", "min": 500, "max": 5000, "default": 1500, "description": "..."}`. The frontend renders this schema dynamically -- no backend-specific React components needed
- Add a `get_parameter_schema() -> list[ParameterDef]` method to the SLAM API protocol
- Store parameters in the backend, not the frontend. The frontend sends `{"backend": "orbslam3", "params": {"nFeatures": 2000}}` and the backend validates
- Start with ~5 parameters per backend (the ones that actually matter for the simulation use case), not the full parameter set. Most SLAM parameters are irrelevant for MuJoCo's synthetic depth images
- Use a single `algorithmStore.ts` Zustand store with `{activeBackend: string, params: Record<string, Record<string, unknown>>}` structure

**Detection:** If adding a new backend requires changing more than 2 frontend files (the schema renderer and the WebSocket message type), the frontend is too tightly coupled to backend specifics.

## Minor Pitfalls

### Pitfall 11: ORB-SLAM3 Tracking Loss on MuJoCo's Synthetic Images

**What goes wrong:** ORB-SLAM3 extracts ORB features from images. MuJoCo's default renderer produces low-texture synthetic images (flat colored surfaces, no real-world texture detail). ORB feature extraction finds too few features, and tracking is immediately lost.

**Prevention:**
- Use MuJoCo's texture system to add realistic textures to scene objects (wood grain, brick, carpet patterns)
- Lower ORB-SLAM3's minimum feature threshold (nFeatures parameter)
- Alternatively, test with a textured MuJoCo scene first -- if ORB-SLAM3 still struggles, the synthetic rendering may be fundamentally insufficient for feature-based SLAM (direct methods like SVO Pro would be more robust)
- The existing ICP pipeline works on depth geometry, not image features, so it is immune to this problem

### Pitfall 12: Python 3.14 Compatibility with C++ Binding Libraries

**What goes wrong:** The project uses Python 3.14 (visible from `env/lib/python3.14/`). This is a very recent Python version. pybind11-based packages (ORB-SLAM3 wrappers, GTSAM, g2o bindings) may not have pre-built wheels for Python 3.14, requiring source compilation that may fail due to CPython API changes.

**Prevention:**
- Check PyPI wheel availability for `gtsam`, `orbslam3-python`, and `open3d` with Python 3.14 BEFORE starting implementation
- If wheels are unavailable, either: (a) build from source with the latest pybind11 (>= 2.12 for Python 3.14 support), or (b) use a Python 3.12 venv specifically for SLAM backends and communicate via subprocess/IPC
- Open3D already works (it's installed in the current venv), so its pybind11 version is compatible -- check if the same pybind11 version works for other packages

### Pitfall 13: Pose-Graph Optimization Scope Creep

**What goes wrong:** "Replace ICP-based map merging with pose-graph optimization" sounds like a swap, but it's actually a fundamental architecture change. The current MapMerger does simple voxel union -- no graph, no optimization, no loop closures. A pose-graph optimizer needs: nodes (robot poses at keyframes), edges (odometry constraints between consecutive poses, loop closure constraints), and a solver. This requires keyframe selection logic, inter-robot loop closure detection, and graph management -- none of which exist.

**Prevention:**
- Phase the transition: first get the SLAM API abstraction working with the existing voxel-union merge. Then add pose-graph optimization as a separate layer on top
- Use GTSAM's `NonlinearFactorGraph` with `BetweenFactor<Pose3>` for odometry edges. Keep it simple: one factor per SLAM frame (not per keyframe initially)
- For multi-robot merge, start with known spawn transforms as prior factors (you already have these in `MapMerger._transforms`). Do NOT attempt inter-robot loop closure detection in the first iteration
- The pose graph corrects trajectory drift; the voxel merge still happens on the corrected point clouds. These are two separate concerns.

**Detection:** If the pose-graph implementation takes more than 2 weeks, scope is creeping. The minimum viable pose graph is: N nodes, N-1 odometry edges, 2 prior factors (spawn positions), solve, done.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| SLAM API interface design | Lowest-common-denominator abstraction (P2) | Two-tier API with capability queries. Design with 4 backends in mind, not just ICP. |
| SLAM API interface design | Breaking existing ICP pipeline (P5) | Characterization tests first. Wrap, don't rewrite. |
| ORB-SLAM3 backend | Build dependency hell (P1) | Isolated build env. Try PyPI package first. Pin all versions. |
| ORB-SLAM3 backend | Vocabulary loading time (P7) | Binary vocab format. Pre-initialize at startup. |
| ORB-SLAM3 backend | Tracking loss on synthetic images (P11) | Add textures to MuJoCo scene. Test early. |
| OpenVINS backend | IMU data requirements (P6) | Add realistic IMU noise to MuJoCo. Use ROS-free build. |
| OpenVINS backend | Coordinate frame mismatch (P3) | Explicit T_world_from_backend transform. Frame convention tests. |
| SVO Pro backend | catkin/ROS build requirement (P4) | Fork and strip catkin, or use Docker isolation, or substitute Basalt. |
| Pose-graph optimization | Scope creep (P13) | Phase the transition. Simple graph first. GTSAM, not g2o. |
| Pose-graph optimization | g2o version conflict with ORB-SLAM3 (P9) | Use GTSAM (clean Python bindings, no conflict). |
| Frontend algorithm picker | Parameter state explosion (P10) | JSON schema from backend. Dynamic rendering. Single store. |
| Hot-swap stretch goal | Map discontinuity on switch (P8) | Pre-session selection first. External map accumulation. |
| All C++ backends | Python 3.14 compatibility (P12) | Check wheel availability before committing. Have fallback plan. |
| All backends | Coordinate frame mismatch (P3) | Project-wide convention. Per-backend static transform. Regression tests. |

## Sources

- [ORB-SLAM3 GitHub Issues](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues) -- HIGH confidence (direct from maintainers/users)
- [OpenVINS Coordinate Frame Issues](https://github.com/rpng/open_vins/issues/277) -- HIGH confidence (official repo)
- [OpenVINS ROS-Free Build](https://docs.openvins.com/gs-installing-free.html) -- HIGH confidence (official docs)
- [rpg_svo_pro_open GitHub](https://github.com/uzh-rpg/rpg_svo_pro_open) -- HIGH confidence (official repo)
- [pyOrbSlam3 Python Bindings](https://github.com/JHMeusener/pyOrbSlam3) -- MEDIUM confidence (community fork)
- [GTSAM Python Bindings](https://gtbook.github.io/gtsam-examples/Pose2SLAMExample_g2o.html) -- HIGH confidence (official examples)
- [ORB-SLAM3 Binary Vocabulary](https://github.com/raulmur/ORB_SLAM2/pull/21) -- HIGH confidence (verified fix)
- Existing codebase analysis: src/slam/slam_pipeline.py, src/coordination/map_merger.py, src/coordination/robot_instance.py -- HIGH confidence (direct code review)
- .research/findings/axis-1-classical-geometric-slam.md, followup-1-cpu-only-deployment.md -- HIGH confidence (project's own prior research)

---

*Pitfalls research: 2026-03-23 -- v2.0 Generic SLAM API milestone*
