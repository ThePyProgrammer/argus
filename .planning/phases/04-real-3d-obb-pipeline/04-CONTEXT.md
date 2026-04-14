# Phase 4: real-3d-obb-pipeline - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning
**Source:** Discuss-phase deep-dive (4 areas, 7 questions, 11 locked decisions)

<domain>
## Phase Boundary

Replace the depth-median 2D→3D projection with real oriented 3D bounding boxes via PCA on depth-frustum point clusters. Single server-owned geometry path lives in new `src/perception/geometry.py`. Frontend already renders OBBs verbatim from wire format (Phase 2 cleanup) — Phase 4 deletes the last hardcoded-FOV / duplicate-projection code paths.

**In:**
- `src/perception/lifters/point_cluster.py` (new) — `PointClusterLifter` registered as default 3D lifter.
- `src/perception/geometry.py` (new) — single projection entrypoint (single-pixel + batched).
- `src/perception/types.py::SensorFrame` — `intrinsics` field added (`fx, fy, cx, cy`).
- `src/sensors/` (or bridge layer) — populate `intrinsics` at capture from MuJoCo `cam_fovy` + image dims.
- `src/perception/lifters/median_depth.py` — drop hardcoded 70° FOV, consume `frame.intrinsics` instead.
- New `POST /api/detectors/lifter-hotswap` REST route — atomic ref swap of pool's lifter instance, no worker restart, no warmup. Supersedes Phase 3 D-09.
- `frontend/src/components/LifterDropdown.tsx` — call hot-swap endpoint instead of triggering restart flow.
- `frontend/src/components/DetectionBoxes.ts` — already PASS for SC#2 (verified Phase 2 cutover). No frontend code deletion needed beyond closure of any remaining FOV constants.
- `tests/perception/test_point_cluster_lifter.py` — MuJoCo-fixture-driven yaw + center error gates per SC#1.
- `tests/perception/test_geometry.py` — round-trip projection unit tests + grep invariant for single entrypoint.

**Out:**
- Detector backend changes (Phase 5).
- Lifter parameter UI panel (deferred — MedianDepthLifter has sensible defaults; PointClusterLifter ships sensible defaults).
- Multi-frame OBB tracking / smoothing (deferred — single-frame fit per detection).
- Real BoxeR / RT-DETR integration (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### PointClusterLifter Algorithm

- **D-01 (OBB fitting library):** **Open3D `compute_oriented_bounding_box(robust=True)`** is the primary OBB fitter. Open3D is already a project dep (`pyproject.toml`). `robust=True` mode handles small/degenerate clusters gracefully. Convert Open3D's rotation matrix to scipy quaternion via `Rotation.from_matrix().as_quat()`, then pass through `OrientedBox3D.to_wire()` (which auto-flips qw<0 per Phase 1 D-10).

- **D-02 (DBSCAN):** **sklearn DBSCAN** with `eps=0.05m`, `min_samples=10`. Add `scikit-learn>=1.4.0` to `perception` extra in `pyproject.toml`. Defaults tuned for indoor furniture-scale clusters at depth-camera resolution. Largest cluster wins. Background pixels in the bbox frustum are filtered by DBSCAN.

- **D-03 (Rotation DOF):** **FULL 3D OBB rotation** (override of DET-3D-01's "yaw-only" wording). Use Open3D's full rotation matrix as-is — handles tilted/leaning objects (chairs at angles, tables on uneven floors). The DET-3D-01 requirement text is amended in this CONTEXT.md scope: gravity-alignment is dropped because it would discard real physical rotation captured by the depth cluster. Verifier must check this override is documented in VERIFICATION.md.

### Camera Intrinsics + Geometry

- **D-04 (Intrinsics source):** **`SensorFrame` gains an `intrinsics` field** (4-tuple `(fx, fy, cx, cy)` or numpy 3×3 matrix — planner picks). Bridge layer populates at capture time from MuJoCo `cam_fovy` (vertical field of view in degrees) + image dims via `f = h / (2 * tan(fovy_rad/2))`. Single source of truth — no module queries MuJoCo directly. Lifters and `geometry.py` consume `frame.intrinsics`.

- **D-05 (`geometry.py` API):** **Both single-pixel + batched** unprojection helpers:
  - `unproject_pixel_to_world(u: float, v: float, depth: float, intrinsics, pose: np.ndarray(4,4)) -> np.ndarray(3,)`
  - `unproject_pixels_batched(uvs: np.ndarray(N,2), depths: np.ndarray(N,), intrinsics, pose: np.ndarray(4,4)) -> np.ndarray(N,3)`
  PointClusterLifter uses batched (entire bbox frustum). MedianDepthLifter uses single-pixel (bbox center). Both reject the existing hardcoded 70° path. Functions are stateless — no class wrapper.

- **D-06 (Single projection entrypoint):** `src/perception/geometry.py` is the **only** projection module per DET-3D-06. Grep invariant `grep -rn "fov\|FOV\|focal" src/perception/` returns hits ONLY in geometry.py docstrings (never executable constants). `_LEGACY_FOV_DEG = 70.0` deleted from `median_depth.py`.

### Fallback (<50 valid pixels)

- **D-07 (Fallback shape):** **Composition** — `PointClusterLifter.__init__` instantiates a `MedianDepthLifter` as `self._fallback`. `lift()` counts valid depth pixels in the bbox frustum; if `< 50`, delegates to `self._fallback.lift(frame, detection_2d, slam_cloud)` and stamps `outputs_oriented=False` on the returned OBB (median lifter already returns identity quat).

- **D-08 (Wire signaling):** When fallback fires, the returned `OrientedBox3D` carries identity quaternion `[0, 0, 0, 1]` and `outputs_oriented=False` in the envelope-level capability payload (NOT per-box). Frontend already handles identity quaternions correctly via three.js Quaternion default identity — no client change.

### Hot-swap vs Restart

- **D-09 (Lifter switch = HOT-SWAP, supersedes Phase 3 D-09):** **Phase 4 SC#5 wins** — switching lifter does NOT restart workers. New REST endpoint `POST /api/detectors/lifter-hotswap {lifter, params?}` performs an atomic ref swap of the pool's lifter instance (lifters are stateless geometry — no warmup needed). UI dismisses ConfirmModal on 200 OK; no overlay needed. Detector switch STILL triggers full restart (warmup mandated by DetectorProtocol P1).
  - Phase 3 D-09's `POST /api/detectors/lifter-select` route is REMOVED in Phase 4. UI's `LifterDropdown.tsx::handleSwitch` switches to call `lifter-hotswap` instead.
  - This is the ONLY supersession of a prior locked decision in Phase 4.

- **D-10 (Hot-swap atomicity):** Pool exposes `swap_lifter(new_lifter, new_params)` that wraps the lifter ref in a lock during swap (≪1ms, non-blocking for next frame). Workers reading the lifter ref get either old-or-new — no torn state. Tests verify back-to-back swaps under 30Hz submit don't drop frames.

### Testing

- **D-11 (MuJoCo GT fixture for SC#1):** New `tests/perception/fixtures/scene_rotated_chair.xml` (MuJoCo XML) places a single chair body at known pose with non-zero yaw. Test renders one RGBD frame, runs YOLOv11 → PointClusterLifter, asserts:
  - yaw error vs `mj_data.body("chair").xquat` < ±15°
  - center error vs `mj_data.body("chair").xpos` < 0.15m
  - `outputs_oriented=True` in envelope
  - Round-trip via `OrientedBox3D.to_wire/from_wire` ±1e-6 (already covered by Phase 2 lock)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 spec
- `.planning/REQUIREMENTS.md` — DET-3D-01, DET-3D-02, DET-3D-05, DET-3D-06, DET-3D-07
- `.planning/ROADMAP.md` — Phase 4 section (5 success criteria)

### Phase 1 / 2 invariants (MUST not break)
- `src/perception/protocol.py::Detection3DProtocol` — `lift(frame, detection_2d, slam_cloud)` signature with `outputs_oriented` capability key
- `src/perception/types.py::OrientedBox3D` — wire format (D-10 quaternion-only-in-types invariant from Phase 1)
- `src/perception/types.py::Detections3D` — envelope with `capture_pose` + `capture_timestamp` (Phase 2 D-11)
- `src/perception/lifters/median_depth.py` — reference lifter; consumed by PointClusterLifter as fallback delegate (D-07)
- `src/perception/worker_pool.py::DetectorWorkerPool` — `lifter_params` kwarg (Phase 3 03-06); will gain `swap_lifter()` per D-10

### Phase 3 contract (one supersession)
- `.planning/phases/03-frontend-picker-and-ui/03-CONTEXT.md::D-09` — **SUPERSEDED by Phase 4 D-09** (hot-swap replaces restart for lifter)
- `backend/web/detector_routes.py` — `POST /api/detectors/lifter-select` REMOVED; replaced with `POST /api/detectors/lifter-hotswap`
- `frontend/src/components/LifterDropdown.tsx` — `handleSwitch` redirects to hot-swap endpoint
- `frontend/src/stores/detectorStore.ts::restartSubsystem` — lifter no longer participates in restart flow

### External references
- Open3D 0.18+ `compute_oriented_bounding_box(robust=True)` — https://www.open3d.org/docs/release/python_api/open3d.geometry.PointCloud.html#open3d.geometry.PointCloud.get_oriented_bounding_box
- sklearn DBSCAN — https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html
- MuJoCo `cam_fovy` — https://mujoco.readthedocs.io/en/stable/XMLreference.html#camera-fovy

</canonical_refs>

<code_context>
## Code Context (read first; locked patterns)

### Existing perception modules
- `src/perception/lifters/median_depth.py` (220 lines) — reference lifter. Hardcoded `_LEGACY_FOV_DEG = 70.0` at line 43 (TO BE DELETED). `lift()` signature accepts `(frame, detection_2d, slam_cloud)`. Returns `OrientedBox3D` with identity quat.
- `src/perception/protocol.py` (D-04: `lift(..., slam_cloud)` signature is REQUIRED positional). `outputs_oriented` is a capability key on the Detection3DProtocol class.
- `src/perception/types.py::SensorFrame` — currently has `rgb`, `depth`, `pose`, `sim_time`, etc. NO `intrinsics` field today.
- `src/perception/worker_pool.py` — `DetectorWorkerPool.__init__(detector, lifter, lifter_params=None, ...)`. Phase 3 03-06 added `lifter_params` kwarg.

### Existing geometry references (TO BE CONSOLIDATED)
- `src/perception/lifters/median_depth.py:91-92` — only remaining FOV math after Phase 1/2 cleanup. Move into `geometry.py` (no FOV — accepts intrinsics).

### Frontend (already PASS for SC#2)
- `frontend/src/components/DetectionBoxes.ts` (173 lines) — already renders OBBs verbatim from wire format via `THREE.Quaternion`. Phase 2 D-18 cutover removed back-projection. SC#2 verifier should grep for any residual focal-length math; expected zero hits.

### Backend REST routes (Phase 3 surface)
- `backend/web/detector_routes.py` — has 4 detector routes + 4 lifter routes. Phase 4 REMOVES `/lifter-select` (restart-trigger) and ADDS `/lifter-hotswap` (atomic ref swap).

### Bridge layer (intrinsics population)
- `src/bridge/` — confirm location of MuJoCo camera capture; bridge is the right place to compute and stamp `intrinsics` on each `SensorFrame` (D-04). Planner verifies exact module + signature.

</code_context>

<specifics>
## Specifics

- **Image dims:** Existing CameraStrip path uses 480×640 RGBD frames. PointClusterLifter operates on `depth[v0:v1, u0:u1]` slice from `bbox_xyxy`.
- **Chair MuJoCo body name:** `tests/perception/fixtures/scene_rotated_chair.xml` should expose body name `"chair"` for `mj_data.body("chair").xpos/xquat` access.
- **Tracking:** `track_id` is set by detector (already shipped Phase 1). Lifter passes through unchanged.
- **Confidence threshold:** Inherits from detector — lifter does not re-filter detections.
- **Performance budget:** Single-frame OBB fit must complete in <33ms per detection (30Hz worst case). Open3D's robust mode is well within this budget for clusters <2000 points.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-frame OBB tracking / smoothing** — Phase 6 (DET-METRICS-* polish)
- **Lifter parameter UI panel** — Phase 7 (pipeline-editor polish) if PointClusterLifter needs runtime tuning
- **Per-class lifter dispatch** (e.g., MedianDepth for cars, PointCluster for furniture) — Phase 8 stretch
- **DBSCAN replacement with HDBSCAN or OPTICS** — only if SC#1 gates fail
- **GPU-accelerated Open3D OBB fit (CUDA)** — only if 33ms/detection budget regresses
- **Yaw-only constraint** — REJECTED per D-03; documented here so future planners don't re-add it
- **Per-box `outputs_oriented` flag** — REJECTED per D-08; capability is envelope-level

</deferred>

---

*Phase: 04-real-3d-obb-pipeline*
*Context gathered: 2026-04-14*
*Discussion log: 04-DISCUSSION-LOG.md*
