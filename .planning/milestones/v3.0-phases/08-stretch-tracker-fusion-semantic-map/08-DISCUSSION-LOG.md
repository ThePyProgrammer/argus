# Phase 8: stretch-tracker-fusion-semantic-map - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 08-stretch-tracker-fusion-semantic-map
**Mode:** --auto (all recommended defaults selected without user input)
**Areas discussed:** ByteTrack tracker integration, Multi-robot detection fusion, SemanticMap TTL rendering, Heterogeneous per-robot backends

---

## ByteTrack Tracker Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Inside DetectorWorker thread, post-lift | Tracker runs in worker._loop after lifter.lift(), before storing to _latest | [auto] |
| Separate tracker thread per robot | Dedicated thread consuming worker output | |
| Centralized tracker pool | Single tracker processing all robots | |

**User's choice:** [auto] Inside DetectorWorker thread, post-lift (recommended default)
**Notes:** Mirrors the lifter call site; ByteTrack association is microseconds, not milliseconds -- no separate thread needed.

---

| Option | Description | Selected |
|--------|-------------|----------|
| IoU-based spatial association in world frame | Euclidean distance between OBB centers, configurable threshold | [auto] |
| 2D IoU back-projection | Project OBBs to pixel space, compute 2D IoU | |
| 3D IoU on OBBs | Compute full 3D intersection-over-union | |

**User's choice:** [auto] IoU-based spatial association in world frame (recommended default)
**Notes:** We have world-frame 3D OBBs from the lifter; going back to 2D would be backwards. 3D IoU is expensive and overkill at this scale.

---

| Option | Description | Selected |
|--------|-------------|----------|
| PARAMETER_SCHEMA with track_thresh, match_thresh, frame_gap | Minimal viable schema for ByteTrack's core knobs | [auto] |
| No parameters (hardcoded defaults) | Simpler but less configurable | |
| Full ByteTrack parameter set | All internal tuning knobs exposed | |

**User's choice:** [auto] PARAMETER_SCHEMA with track_thresh, match_thresh, frame_gap (recommended default)
**Notes:** Three parameters cover the essential tuning surface; renders in NodeInspector via Phase 7 tracker_generic param surface.

---

| Option | Description | Selected |
|--------|-------------|----------|
| DetectorWorker._loop: call tracker.track() after lifter.lift() | Track before emitting to latest() -- all downstream consumers see track_ids | [auto] |
| Coordinator-level pump after worker.latest() | Track outside the worker, centralized | |

**User's choice:** [auto] DetectorWorker._loop pump (recommended default)
**Notes:** Keeps tracked output visible to ALL downstream consumers: latest(), MetricsPanel, JSONL export, WS stream.

---

## Multi-Robot Detection Fusion

| Option | Description | Selected |
|--------|-------------|----------|
| New centralized FusionManager in WebStreamingViz | Collects all robots' latest() per tick, merges cross-robot | [auto] |
| Per-worker fusion (worker sees other workers' results) | Distributed fusion | |
| Separate fusion service/thread | Independent processing | |

**User's choice:** [auto] Centralized FusionManager (recommended default)
**Notes:** Fusion is inherently cross-robot; per-worker fusion is impossible. Coordinator tick already iterates all robots.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Nearest-neighbor clustering, same class, 0.5 m gate | Group detections by class within distance, pick highest confidence | [auto] |
| Hungarian assignment across all robots | Optimal matching via cost matrix | |
| DBSCAN spatial clustering | Density-based clustering on detection centers | |

**User's choice:** [auto] Nearest-neighbor class-gated clustering (recommended default)
**Notes:** Simple, matches SC#2 literal. At 2 robots with <20 detections per class, no need for optimal assignment.

---

| Option | Description | Selected |
|--------|-------------|----------|
| New 'fused_detections' WS key alongside per-robot data | Additive -- does not replace per-robot streams | [auto] |
| Replace per-robot detections with fused view | Single merged stream | |

**User's choice:** [auto] Additive fused_detections WS key (recommended default)
**Notes:** MetricsPanel shows fused view while CameraFeed continues per-robot overlays; two independent data paths.

---

## SemanticMap TTL Rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Server-side SemanticMap with delta WS updates | Server owns truth; emits active + expired_ids per tick | [auto] |
| Frontend-only semantic map state | Client manages TTL and state from raw detections | |

**User's choice:** [auto] Server-side SemanticMap (recommended default)
**Notes:** Matches DET-3D-05 precedent: server owns geometry, frontend is dumb renderer.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Opacity proportional to remaining TTL (ghosting) | Fade from opaque to invisible as TTL expires | [auto] |
| Binary visibility (present or gone) | Object disappears instantly at TTL expiry | |
| Color shift (bright to grey) | Object greys out as it ages | |

**User's choice:** [auto] Opacity-based TTL ghosting (recommended default)
**Notes:** Matches SC#3 literal "fade-out within TTL seconds of leaving FOV".

---

| Option | Description | Selected |
|--------|-------------|----------|
| Separate Three.js Group with InstancedMesh | Mirrors DetectionBoxManager pattern; alpha-blended wireframe material | [auto] |
| Overlay on existing reconstruction cloud | Modify reconstruction renderer | |
| CSS overlay on canvas | 2D overlay markers | |

**User's choice:** [auto] Separate Three.js Group + InstancedMesh (recommended default)
**Notes:** Mirrors Phase 4 DetectionBoxManager; InstancedMesh for batch rendering; separate group enables layer toggle.

---

| Option | Description | Selected |
|--------|-------------|----------|
| 10 seconds (configurable) | Long enough for spatial memory, short enough to not clutter | [auto] |
| 5 seconds (short) | Quick cleanup but less spatial memory effect | |
| 30 seconds (long) | Extended memory but potential scene clutter | |

**User's choice:** [auto] 10 seconds (recommended default)
**Notes:** Balance between spatial memory persistence and scene clarity.

---

## Heterogeneous Per-Robot Backends

| Option | Description | Selected |
|--------|-------------|----------|
| Per-robot dropdown in NodeInspector | Extend Phase 7 D-02 backend dropdown with per-robot section | [auto] |
| Dedicated per-robot settings panel | Separate UI surface | |
| REST-only (no frontend) | Per-robot selection via API only | |

**User's choice:** [auto] Per-robot dropdown in NodeInspector (recommended default)
**Notes:** Phase 7 D-02 already has backend dropdown; extend with per-robot selector.

---

| Option | Description | Selected |
|--------|-------------|----------|
| swap_backend_for_robot(rid, ...) on pool | Targeted single-worker swap, same pattern as swap_backend | [auto] |
| Reconstruct entire pool with mixed config | Rebuild pool on any per-robot change | |

**User's choice:** [auto] swap_backend_for_robot (recommended default)
**Notes:** Follows proven construct-outside-lock -> warmup-outside-lock -> rebind-inside-lock pattern.

---

| Option | Description | Selected |
|--------|-------------|----------|
| POST /api/detectors/select?robot_id=... | Backward-compatible extension of existing endpoint | [auto] |
| New POST /api/detectors/select-robot endpoint | Separate endpoint for per-robot | |

**User's choice:** [auto] Optional robot_id param on existing endpoint (recommended default)
**Notes:** Backward-compatible; omitted = all robots (existing), present = single robot.

---

## Claude's Discretion

- ByteTrack internal data structures (numpy cost matrix, scipy Hungarian vs greedy matcher)
- SemanticMapLayer class color palette
- SemanticMap pipeline node inclusion/deferral
- Fused detection MetricsPanel detail level
- TTL opacity curve shape
- Per-robot WS message shape for swap_backend_for_robot
- Hot-apply diff extension scope for tracker params

## Deferred Ideas

- DeepSORT CNN re-ID (CPU killer)
- Kalman filter prediction for occluded objects
- Semantic SLAM loop closure
- Per-robot tracker heterogeneity
- SemanticMap session persistence
- Fusion threshold auto-tuning
- Track-to-track temporal fusion
- 3D IoU for fusion (overkill at 2 robots)
