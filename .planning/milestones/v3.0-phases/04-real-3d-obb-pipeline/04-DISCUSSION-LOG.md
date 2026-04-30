# Phase 4: real-3d-obb-pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 04-real-3d-obb-pipeline
**Areas discussed:** PointClusterLifter algorithm, Camera intrinsics source, geometry.py API, Fallback + hot-swap contradiction

---

## PointClusterLifter Algorithm

### Q1: OBB fitting library?

| Option | Description | Selected |
|--------|-------------|----------|
| Open3D `compute_oriented_bounding_box(robust=True)` | Single battle-tested call. Open3D already a project dep. Robust mode handles small clusters. Returns OBB with rotation matrix → scipy quaternion. | ✓ |
| Manual PCA via numpy SVD | Full control, no Open3D import in lifter. ~30 lines. Slower convergence on edge cases. | |
| Both — Open3D primary, numpy fallback | Defense-in-depth. ~50 lines. Adds branching complexity. | |

**Selected:** Open3D
**Notes:** Battle-tested; project already imports Open3D heavily for SLAM.

### Q2: DBSCAN library + parameter defaults?

| Option | Description | Selected |
|--------|-------------|----------|
| sklearn DBSCAN, eps=0.05m, min_samples=10 | Mature, fast, accepts numpy directly. Add sklearn to perception extra. | ✓ |
| Open3D cluster_dbscan | No new dep. Slightly slower for small clusters. | |
| Skip DBSCAN — use depth MAD filter only | Background pixels in bbox frustum pollute the OBB. Risk to SC#1. | |

**Selected:** sklearn DBSCAN
**Notes:** Adds `scikit-learn>=1.4.0` to perception extra in pyproject.

### Q3: Yaw-only vs full 3D rotation?

| Option | Description | Selected |
|--------|-------------|----------|
| Yaw-only, gravity-aligned | Per DET-3D-01 wording. Project to xz-plane. Indoor MVP scope. | |
| **Full 3D OBB rotation** | Use Open3D's full rotation as-is. Handles tilted/leaning objects. Beyond DET-3D-01 wording. | ✓ |

**Selected:** Full 3D OBB (USER OVERRIDE of recommended yaw-only)
**Notes:** Captures real physical rotation that yaw-only would discard. Override of DET-3D-01 must be documented in VERIFICATION.md by verifier.

---

## Camera Intrinsics

### Q4: Intrinsics source (replaces hardcoded 70° FOV)?

| Option | Description | Selected |
|--------|-------------|----------|
| Add intrinsics field to SensorFrame, populate at capture | Single source of truth. Bridge populates from MuJoCo cam_fovy + image dims. | ✓ |
| Query MuJoCo cam_fovy on-demand inside lifter | Couples lifter to MuJoCo. Bad for non-MuJoCo deploys. | |
| Per-camera config dict | Decouples from runtime but config drift risk. | |

**Selected:** SensorFrame.intrinsics
**Notes:** Bridge layer is the only place that knows about MuJoCo internals; everywhere downstream consumes the stamped frame.

---

## geometry.py API

### Q5: API surface?

| Option | Description | Selected |
|--------|-------------|----------|
| Both single-pixel + batched | Lifter uses batched, MedianDepthLifter uses single. ~80 lines. | ✓ |
| Batched only | Single callers wrap as 1-element. Cleaner API; uglier sites. | |
| Class-based ProjectionContext | OO style. Overkill for stateless math. | |

**Selected:** Both
**Notes:** Stateless functions; no class needed.

---

## Fallback + Hot-swap

### Q6: <50 valid pixels fallback implementation?

| Option | Description | Selected |
|--------|-------------|----------|
| PointClusterLifter holds MedianDepthLifter instance, delegates | Composition. Inherits fallback's identity-quat behavior. | ✓ |
| Inline degenerate handler returns identity-quat OBB | No MedianDepthLifter dep. ~20 lines duplication. | |
| Throw on degenerate, executor catches | Splits responsibility. Worker_pool changes. Out of scope. | |

**Selected:** Composition
**Notes:** Reuses MedianDepthLifter logic; outputs_oriented=False stamped at lift time.

### Q7: Phase 3 D-09 (lifter restart) vs Phase 4 SC#5 (no restart) — resolve?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 4 SC#5 wins — lifter hot-swap, no restart | New REST endpoint POST /api/detectors/lifter-hotswap. Atomic ref swap. Phase 3 D-09 superseded. | ✓ |
| Phase 3 D-09 wins — SC#5 reworded to drop "no restart" | UX consistency preserved. SC#5 verification trivially passes. | |
| Both — hot-swap default, restart on params change | More code paths. Rejected by Occam. | |

**Selected:** Hot-swap (Phase 4 SC#5 wins)
**Notes:** Lifters are stateless geometry — no warmup needed. Detector switch still restarts (warmup mandated by Protocol P1). Phase 3 D-09 amended in Phase 4 CONTEXT.md as the only supersession.

---

## Claude's Discretion

- Exact `intrinsics` data shape (4-tuple vs 3×3 matrix) — planner picks
- DBSCAN cluster-selection tiebreak (largest, densest, closest-to-bbox-center) — planner picks largest
- Open3D PointCloud creation style (bulk constructor vs append) — planner picks
- Test fixture scene scale / lighting — planner picks defaults that produce reliable depth
- Hot-swap REST response shape (return active lifter name? include params?) — planner picks
- Worker lifter ref locking primitive (threading.Lock vs atomic ref swap pattern) — planner picks

## Deferred Ideas

- Multi-frame OBB smoothing — Phase 6
- LifterParameterPanel — Phase 7
- Per-class lifter dispatch — Phase 8 stretch
- HDBSCAN / OPTICS replacement — only if SC#1 gates fail
- GPU-accelerated Open3D — only if 33ms budget regresses
- Yaw-only constraint — REJECTED per D-03
- Per-box outputs_oriented flag — REJECTED per D-08
