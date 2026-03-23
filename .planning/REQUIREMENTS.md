# Requirements: Multi-Robot 3D Reconstruction

**Defined:** 2026-03-23
**Core Value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.

## v2.0 Requirements

Requirements for the Generic SLAM API milestone. Each maps to roadmap phases.

### Backend Abstraction

- [x] **ABST-01**: System defines a SLAMProtocol interface with process_frame(rgb, depth, timestamp) -> SLAMResult(pose, points, metrics)
- [x] **ABST-02**: System provides a SLAMRegistry that discovers, lists, and instantiates available backends by name
- [x] **ABST-03**: Each backend declares its parameters as a JSON schema (voxel_size, feature_count, etc.)
- [x] **ABST-04**: Each backend declares capabilities (supports_imu, outputs_dense, supports_loop_closure, supports_stereo)
- [x] **ABST-05**: User can select a SLAM algorithm via REST API before starting a session, triggering system restart with the new backend
- [x] **ABST-06**: Existing ICP-based SLAMPipeline is wrapped as the first backend with zero behavioral change

### SLAM Backends

- [x] **BACK-01**: ORB-SLAM3 backend integrates via orbslam3-python, producing pose estimates from RGB-D frames
- [x] **BACK-02**: ORB-SLAM3 backend uses SLAM-estimated poses with depth-image-generated dense clouds (not sparse ORB features) for downstream consumers
- [ ] **BACK-03**: OpenVINS backend integrates via subprocess bridge, accepting RGB + IMU data
- [ ] **BACK-04**: System extracts accelerometer and gyroscope data from MuJoCo simulation to feed VIO backends
- [ ] **BACK-05**: SVO Pro backend integrates via subprocess bridge with de-catkinized build
- [ ] **BACK-06**: Each C++ backend runs in subprocess isolation so crashes do not take down the main process

### Map Merging

- [x] **MERG-01**: System supports pluggable merge strategies: ICP union (existing), Open3D pose-graph optimization, and GTSAM incremental PGO
- [x] **MERG-02**: User can select merge strategy from frontend alongside SLAM algorithm selection
- [x] **MERG-03**: Pose-graph merger accepts inter-robot loop closure constraints for globally consistent maps
- [x] **MERG-04**: Merged map output is API-compatible with existing visualization pipeline (last_merged_voxels, last_merged_cloud)

### Frontend Controls

- [x] **CTRL-01**: Algorithm picker dropdown lists available SLAM backends with their capability badges
- [x] **CTRL-02**: Selecting an algorithm triggers pre-session restart with the chosen backend
- [x] **CTRL-03**: Parameter tuning panel renders dynamically from backend's JSON schema
- [x] **CTRL-04**: Parameter changes are sent to backend via WebSocket and applied (where supported)
- [ ] **CTRL-05**: Live metrics dashboard shows ATE, RPE, processing time (ms/frame), and tracking status per robot
- [ ] **CTRL-06**: Metrics comparison view shows current algorithm vs baseline ICP side-by-side
- [ ] **CTRL-07**: Output format toggle switches Three.js viewer between point cloud, voxel grid, and mesh rendering modes

## v3.0 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Deep Learning Backends

- **DL-01**: DROID-SLAM backend (requires NVIDIA GPU)
- **DL-02**: DPV-SLAM backend (requires NVIDIA GPU, 5GB VRAM)
- **DL-03**: SL-SLAM hybrid backend (ORB-SLAM3 + SuperPoint + LightGlue)

### Neural Representation Backends

- **NEUR-01**: Photo-SLAM backend (3DGS mapping, requires GPU)
- **NEUR-02**: GPS-SLAM backend (hybrid SDF+Gaussian, requires GPU)

### Advanced Features

- **ADV-01**: Hot-swap SLAM algorithm mid-session without restarting
- **ADV-02**: Multi-algorithm comparison mode (run 2+ algorithms simultaneously on same data)
- **ADV-03**: COVINS-G collaborative backend for multi-robot joint optimization

## Out of Scope

| Feature | Reason |
|---------|--------|
| LiDAR SLAM backends | System exists to replace LiDAR with cameras |
| GPU-dependent backends | No NVIDIA GPU available; defer to v3.0 |
| Hot-swap mid-session | Complex state transfer; pre-session selection sufficient for v2.0 |
| Real-world deployment | Simulation only |
| Custom SLAM algorithm development | Wrapping existing open-source implementations only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ABST-01 | Phase 8 | Complete |
| ABST-02 | Phase 8 | Complete |
| ABST-03 | Phase 8 | Complete |
| ABST-04 | Phase 8 | Complete |
| ABST-05 | Phase 8 | Pending |
| ABST-06 | Phase 8 | Complete |
| BACK-01 | Phase 11 | Complete |
| BACK-02 | Phase 11 | Complete |
| BACK-03 | Phase 12 | Pending |
| BACK-04 | Phase 12 | Pending |
| BACK-05 | Phase 12 | Pending |
| BACK-06 | Phase 12 | Pending |
| MERG-01 | Phase 10 | Complete |
| MERG-02 | Phase 10 | Complete |
| MERG-03 | Phase 10 | Complete |
| MERG-04 | Phase 10 | Complete |
| CTRL-01 | Phase 9 | Complete |
| CTRL-02 | Phase 9 | Complete |
| CTRL-03 | Phase 9 | Complete |
| CTRL-04 | Phase 9 | Complete |
| CTRL-05 | Phase 13 | Pending |
| CTRL-06 | Phase 13 | Pending |
| CTRL-07 | Phase 13 | Pending |

**Coverage:**
- v2.0 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after roadmap creation*
