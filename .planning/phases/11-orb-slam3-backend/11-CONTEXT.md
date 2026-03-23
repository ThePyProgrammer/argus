# Phase 11: ORB-SLAM3 Backend - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrate ORB-SLAM3 as the first real alternative SLAM backend via orbslam3-python. Validates the abstraction layer works with a feature-based algorithm. Produces both ORB-SLAM3's sparse map and depth-generated dense cloud. Supports RGB-D and monocular modes. Frontend and metrics dashboard are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Output & pose role
- Use **full ORB-SLAM3 output**: pose estimates + sparse ORB feature map for visualization/debugging + depth-generated dense cloud for downstream consumers
- Backend calls `depth_to_pointcloud(frame.depth, frame.rgb, intrinsics)` internally using its estimated pose — same utility as ICP, consistent output
- Sparse ORB features available as a secondary layer (SLAMResult.metrics can carry sparse point count and feature positions)
- Supports both **RGB-D** and **monocular** modes, selectable from the parameter panel

### MuJoCo texture handling
- **Hybrid approach**: Add textures to MuJoCo scene XML (checkerboard/wood grain on walls/floors) AND tune ORB-SLAM3 feature extraction params
- Expose key ORB-SLAM3 params in PARAMETER_SCHEMA: `nFeatures` (default 1000), `scaleFactor` (default 1.2), `nLevels` (default 8)
- If ORB-SLAM3 still struggles on flat surfaces, that's informative data — don't mask it

### Fallback & tracking status
- **When LOST**: Return `tracking_status=LOST` + last known pose. Robot stops navigating until tracking recovers. ExplorationLoop's stuck detection handles recovery.
- **Frontend status indicator**: Each robot marker in Three.js changes color — green=OK, red=LOST, yellow=RELOCALIZING. Implemented in this phase (simple color change on existing markers).
- **During INITIALIZING**: Robot drives forward slowly to provide diverse viewpoints for faster initialization. Do NOT block exploration entirely.

### Configuration & assets
- **Vocabulary file + camera config**: Store in `models/orbslam3/`. Git-track the YAML config, `.gitignore` the vocabulary file (ORBvoc.txt ~40MB). Include a download script (`scripts/download_orbslam3_vocab.sh`).
- **Camera calibration**: Backend generates a temporary YAML file from `CameraIntrinsics` on initialization. ORB-SLAM3 reads it. Cleaned up on `reset()`.
- **Process model**: In-process via pybind11 (orbslam3-python). No subprocess isolation needed — that's reserved for OpenVINS/SVO Pro in Phase 12.

### Claude's Discretion
- Exact temporary YAML file format and location (tempfile vs models/ subdirectory)
- How to expose sparse ORB features in SLAMResult.metrics (point list vs count-only)
- Error handling for orbslam3-python import failure (ImportError → mark unavailable in registry)
- Exact MuJoCo XML texture additions (material/texture choice)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing abstraction layer
- `src/slam/protocol.py` — SLAMProtocol, SLAMResult, TrackingStatus definitions
- `src/slam/registry.py` — SLAMRegistry, @slam_backend decorator
- `src/slam/backends/icp_backend.py` — Reference implementation to follow as a template
- `src/slam/backends/__init__.py` — Backend import registration pattern

### Cloud generation
- `src/slam/depth_to_cloud.py` — depth_to_pointcloud utility for dense cloud generation from depth+intrinsics

### Consumer integration
- `src/exploration/exploration_loop.py` §192-207 — `_update_slam()` consuming SLAMResult
- `src/coordination/robot_instance.py` — RobotInstance.create() passing backend_name to registry

### Research
- `.research/report.md` §ORB-SLAM3 — Accuracy benchmarks, capabilities, limitations
- `.planning/research/FEATURES.md` — orbslam3-python PyPI package details, API surface
- `.planning/research/PITFALLS.md` — Build dependency warnings, sparse/dense mismatch fix
- `.planning/research/STACK.md` — orbslam3-python v2.0.0 pip-installable confirmation

### MuJoCo scene
- `models/` — MuJoCo XML scene files to add textures to

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ICPBackend` (icp_backend.py): Direct template — ORB-SLAM3 backend follows identical structure (@slam_backend decorator, CAPABILITIES, PARAMETER_SCHEMA, process_frame → SLAMResult)
- `depth_to_pointcloud()`: Shared utility for generating dense cloud from depth+pose
- `SLAMRegistry`: Already handles lazy-loading — ORB-SLAM3 backend just needs `@slam_backend` decorator and import in `__init__.py`

### Established Patterns
- Backend wraps external library via delegation (ICPBackend wraps SLAMPipeline)
- PARAMETER_SCHEMA uses JSON Schema with `live_tunable` extension
- CAPABILITIES dict with boolean flags
- `process_frame` returns SLAMResult with all fields populated

### Integration Points
- `src/slam/backends/__init__.py` — Add import for orbslam3_backend module
- `models/orbslam3/` — New directory for vocabulary and config files
- `scripts/download_orbslam3_vocab.sh` — New download script
- Frontend robot markers — Color change based on tracking_status (minor Three.js change)

</code_context>

<specifics>
## Specific Ideas

- Follow ICPBackend as a 1:1 structural template — same decorator, same class attributes, same method signatures
- The orbslam3-python package should be added to pyproject.toml optional dependencies (new `slam` group)
- MuJoCo texture additions should be minimal — just enough for ORB features to extract, not photorealistic
- Robot marker color for tracking status: reuse existing marker mesh, just swap material color based on WebSocket status field

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-orb-slam3-backend*
*Context gathered: 2026-03-23*
