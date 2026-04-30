# Technology Stack: v3.0 Pluggable Perception & 3D Object Detection

**Project:** Multi-Robot 3D Reconstruction — Generic Detector API
**Researched:** 2026-04-13
**Scope:** NEW additions only. v1.0/v2.0 stack (MuJoCo, Open3D, FastAPI, React 18, Three.js, React Flow, Zustand 5, ZMQ+msgpack SubprocessSLAMBridge, GTSAM) is validated and unchanged.

## Executive Summary

The headline finding: **`facebook/boxer` is not a competitor to YOLO — it is a full 2D→3D lifting pipeline**. It ingests an image + camera intrinsics + gravity (+ optional depth/pose), runs OWLv2 internally for open-vocabulary 2D detection, and lifts boxes to oriented 3D bounding boxes via its BoxerNet transformer on top of DINOv3 features. This is almost exactly the v3.0 target (pluggable detection + real 3D OBBs), but it is **research code with no pip package** and the authors report ~2 min for 90 frames on Apple MPS; on a pure CPU it will be minutes per frame. It is therefore valuable as a quality baseline / offline backend, not as a real-time backend.

For real-time-ish CPU detection, the v3.0 stack should standardise on **HuggingFace `transformers` pipelines** as the lingua franca (matching the already-declared `transformers>=5.3.0` in the `perception` extra), exposing three tiers:

1. **Fast / real-time (≥1 FPS CPU):** keep YOLOv11-nano; add RT-DETRv2-S (Baidu) and RF-DETR-Nano (Roboflow) as transformer options. All are ONNX-exportable and run in the 100–300 ms range at low resolution on CPU.
2. **Open-vocabulary (slower, ~1 frame / several seconds):** OWLv2 (`google/owlv2-base-patch16-ensemble`). This is what BoxeR uses internally, so integrating it directly is strictly cheaper than using BoxeR for 2D-only.
3. **3D lifting (reference-quality, offline):** `facebook/boxer` run through the v2.0 `SubprocessSLAMBridge` pattern (renamed to a generic subprocess bridge) so its multi-minute latency and heavy dependency cocktail (DINOv3 + OWLv2 + BoxerNet + moderngl) do not block the main FastAPI process.

For the **real 3D OBB pipeline** that replaces the current depth-median projection, the pragmatic CPU-only choice is **Open3D `compute_oriented_bounding_box(robust=True)` on the depth-frustum point cloud inside each 2D bbox** (PCA of the convex hull). This runs in <5 ms per detection, produces true oriented boxes, and lives inside the existing Open3D dependency. The deep-learning alternatives (FCOS3D, ImVoxelNet, Frustum-PointNets, MonoFlex, Cube R-CNN, ovmono3d) either require GPU, require LiDAR, are trained on autonomous-driving datasets that do not transfer to an indoor office MuJoCo scene, or have research-grade code quality that does not justify the maintenance burden for a simulation. **Use Open3D OBB as the default 3D method; expose BoxeR as the "high-quality offline" backend.**

No new heavy build-from-source dependencies are needed for v3.0 (unlike v2.0). All new backends install via pip and reuse the v2.0 subprocess pattern for isolation.

## Recommended Stack Additions

### Core Backend: HuggingFace Transformers as the Detector Lingua Franca

The existing `perception` extra in `pyproject.toml` already declares `torch>=2.10.0`, `transformers>=5.3.0`, `ultralytics>=8.4.24`. No change needed to the declared versions — these are current (Transformers v5.5.0 was the latest as of April 2026; v5.3 is inside the supported window).

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| transformers | >=5.3.0 (already declared) | Unified model loading for RT-DETR, OWLv2, DINOv3 via `AutoModelForObjectDetection` / `AutoModelForZeroShotObjectDetection` | v5.3+ ships stable RT-DETRv2, OWLv2, DINOv3 support. Weekly minor releases in v5 series; 5.3.0 is LTS-enough for a 6-week milestone. One import surface for every HuggingFace-hosted detector. | HIGH |
| torch | >=2.10.0 (already declared) | Tensor runtime | 2.10+ has matured CPU inductor compile paths and int8 quantisation helpers. BoxeR requires `torch>=2.0`, so we are overqualified. | HIGH |
| ultralytics | >=8.4.24 (already declared) | YOLOv11-nano legacy backend | Kept for regression-free v2.0 behaviour. Will be wrapped behind the new `DetectorProtocol`, not removed. | HIGH |

**Integration note:** the detector registry exposes each backend as an implementation of a new `DetectorProtocol` (analog of `SLAMProtocol`). The `process_frame(rgb, depth, pose, intrinsics) -> list[Detection3D]` contract covers all tiers; backends that do not produce 3D data fall through to the default Open3D OBB post-processor (see below).

### Real-Time Backend (in-process, CPU): RT-DETRv2 and RF-DETR-Nano

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| RT-DETRv2 via `transformers` | `PekingU/rtdetr_v2_r18vd` (HF checkpoint) | Transformer end-to-end detector, COCO-pretrained, ONNX-exportable | Ships as a native `transformers` model (`RTDetrV2ForObjectDetection`). Baidu's RT-DETR family is the only true transformer detector competitive with YOLO on CPU. R18VD small checkpoint is the CPU-sensible choice. | HIGH |
| RF-DETR (roboflow) | `rfdetr>=1.3.0` (optional) | DETR with DINOv2 backbone, trained by Roboflow, ICLR 2026 | Roboflow publishes Nano/Small ONNX weights. Measured ~180 ms/frame at 320×320 on Intel Core Ultra 7 CPU (issue #641). Higher mAP than RT-DETR-S at the same latency. | MEDIUM |
| onnxruntime | >=1.20 | CPU-optimised inference for exported detectors | Users of both RT-DETR and RF-DETR report ONNX runtime is 2–3× faster than raw PyTorch on CPU, especially once `CPUExecutionProvider` + `graph_optimization_level=ORT_ENABLE_ALL` is set. | HIGH |

**CPU latency reality check (honest estimates, single i7/i9 CPU):**

| Model | Input | PyTorch CPU | ONNX CPU | FPS |
|-------|-------|-------------|----------|-----|
| YOLOv11-nano | 640×640 | ~80–150 ms | ~50–100 ms | 2–5 |
| RT-DETRv2-S (r18vd) | 640×640 | ~300–500 ms | ~150–250 ms | 2–4 |
| RT-DETRv2-S | 320×320 | ~120–200 ms | ~70–120 ms | 5–8 |
| RF-DETR-Nano | 320×320 | ~300 ms | ~180 ms (confirmed) | 3–5 |
| OWLv2-base | 768×768 | ~3–8 s | ~1.5–4 s | 0.25–0.5 |
| DETR-ResNet50 | 800×1333 | ~1–2 s | — | 0.5–1 |

RT-DETRv2-S and RF-DETR-Nano at 320×320 are the only transformer detectors that can plausibly hit the 2 FPS budget already enforced by the background thread. **If 2 FPS cannot be hit after quantisation, they run in the subprocess bridge like heavy SLAM backends do.**

### Open-Vocabulary Backend (in-process, CPU, slow): OWLv2

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| OWLv2 via `transformers` | `google/owlv2-base-patch16-ensemble` | Zero-shot open-vocabulary detection from text prompts | OWLv2 is stable in `transformers` since v4.35 and is the 2D detector BoxeR uses internally. Integrating it standalone gives us "text-prompt an object" without the BoxeR 3D stack. Expect 1–4 s/frame on CPU — runs as a low-FPS backend (max_fps ≈ 0.2) or via subprocess. | HIGH |

This is the detector to demo when the user wants to type "potted plant, office chair" in the C2 UI and see novel objects labelled. Not a real-time backend.

### 3D Lifting Backend (subprocess, CPU, offline-ish): facebook/BoxeR

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| facebook/boxer | git main (no pip release) | OWLv2 → BoxerNet transformer → oriented 3D boxes with multi-view fusion | The canonical v3.0 "real 3D OBB regression" backend. Outputs `boxer_3dbbs.csv` with oriented 3D boxes in metric world space. License: **CC-BY-NC-4.0 (non-commercial)** — acceptable for a research simulation, flag in `LICENSES.md`. | MEDIUM |
| dinov3 weights | `facebook/dinov3-vits16-pretrain-lvd1689m` (smallest ViT-S/16) | Frozen visual backbone used by BoxerNet | Required by BoxeR's checkpoint downloader. ViT-S/16 is the smallest DINOv3 variant (~22M params); ViT-B/16 also viable. Auto-downloaded via `scripts/download_ckpts.sh`. | HIGH |
| opencv-python | already present (`opencv-python-headless>=4.0.0`) | BoxeR's image I/O | Already a v1.0 dependency. | HIGH |
| dill | >=0.3 | BoxeR's tensor serialisation | Direct BoxeR requirement; small pure-Python dep. | HIGH |
| tqdm | >=4.66 | BoxeR's progress bars | Direct BoxeR requirement; trivial. | HIGH |

**Integration approach — subprocess bridge (re-use v2.0 pattern):**

BoxeR has NO pip package, no Python API, and is a CLI (`python run_boxer.py --input <dir> --force_cpu`) that reads sequence directories on disk and writes CSVs. The v2.0 `SubprocessSLAMBridge` (ZMQ PAIR + msgpack over IPC, crash detection) should be generalised to a `SubprocessDetectorBridge` that:

1. On startup, spawns a persistent Python worker process (not BoxeR's one-shot CLI) that imports BoxeR's internal modules (`boxer.model`, `boxer.owl`, `boxer.boxer_net`) and holds the models in memory.
2. The main process streams `(rgb_jpg_bytes, intrinsics, gravity_vec, optional_depth, optional_pose)` over ZMQ IPC (msgpack-packed).
3. Worker returns `list[OrientedBox3D]` with `(center_world, extents, R_world_box, class_name, confidence)`.
4. Crash detection: if worker dies or exceeds a per-frame watchdog (e.g. 30 s), main falls back to the configured fast backend and flags the error in the metrics panel.
5. Because BoxeR expects multi-frame pose sequences for its multi-view fusion mode, the bridge supports two operating modes: **single-frame** (disable tracking, output per-frame boxes) and **windowed** (buffer last N poses and run `--track`).

**Honest CPU latency:** the BoxeR authors report ~2 min / 90 frames on Apple MPS (~1.3 s/frame MPS). On a pure CPU, expect **5–30 s/frame** depending on scene complexity (OWLv2 alone is 1–4 s). This is a "run once per room scan" backend, not a live-telemetry backend.

**Checkpoints required on disk (~1–2 GB total):** DINOv3 ViT-S/16, OWLv2-base-ensemble, BoxerNet — all hosted on HuggingFace; downloaded once via BoxeR's `scripts/download_ckpts.sh`.

**Dependency cocktail to avoid in the main process:** `moderngl`, `moderngl-window`, `imgui-bundle`, `projectaria-tools` — these are BoxeR's visualization/Aria-rig extras. Do **not** install them in the main FastAPI process; install only inside the subprocess worker's venv if interactive BoxeR visualisation is ever wanted (it's not, we have Three.js).

### 3D OBB Post-Processor (in-process, fast): Open3D PCA-OBB

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| open3d | already present (`>=0.18.0`) | `PointCloud.get_oriented_bounding_box(robust=True)` / `compute_oriented_bounding_box` | Default post-processor for any 2D detector. For each 2D bbox, unproject depth pixels inside the bbox to a point cloud, then fit an oriented box via PCA of the convex hull. ~1–5 ms per detection on CPU. Already a v1.0 dependency. | HIGH |

**Why this, not a deep 3D detector:**

- **FCOS3D / ImVoxelNet / MonoFlex / Cube R-CNN:** All trained on KITTI / nuScenes / Waymo — autonomous-driving priors do not transfer to an indoor office room with chairs and bottles. Retraining is out of scope.
- **Frustum-PointNets:** Requires PointNet++ with CUDA ops (`furthest_point_sampling`, `ball_query`). No CPU implementation.
- **ovmono3d (3DV 2026 open-vocabulary monocular 3D):** Interesting but training-only code, no runnable checkpoint for arbitrary scenes as of April 2026.
- **OpenM3D / Group3D:** Multi-view indoor-specific but all require GPU and are research code.

PCA-OBB on the depth frustum is the honest "baseline that works today on CPU." When higher quality is needed, escalate to the BoxeR subprocess backend. This two-tier design mirrors the v2.0 ICP-vs-ORB-SLAM3 choice.

**Integration:** the `DetectorProtocol` returns `list[Detection2D]`; a separate `ThreeDLifter` component (pluggable like SLAM: `PCAFromDepthLifter`, `BoxerLifter`, `CenterProjectionLifter` for backward compat) turns them into `list[Detection3D]` with OBBs. This is the single cleanest way to keep the 2D and 3D concerns decoupled.

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| onnxruntime | >=1.20 | CPU-optimised model graph execution | When exporting RT-DETRv2 or RF-DETR to ONNX for 2–3× speedup | HIGH |
| onnx | >=1.17 | Model export glue | Only during one-time export of PyTorch detector → `.onnx`. Not a runtime dep if weights are shipped as ONNX. | HIGH |
| timm | >=1.0.11 | Backbone implementations (DINOv2/DINOv3 variants for RF-DETR) | Required by RF-DETR for its DINOv2 backbone loader | MEDIUM |
| huggingface-hub | >=0.26 (comes with transformers) | Checkpoint download + cache | Already pulled in transitively. Used by the BoxeR subprocess worker to resolve `facebook/boxer`, `facebook/dinov3-vits16-pretrain-lvd1689m`, `google/owlv2-base-patch16-ensemble`. | HIGH |
| Pillow | >=10 (comes with transformers) | Image I/O for HF processors | Transitive. No explicit dep needed. | HIGH |
| scipy | already present (`>=1.15.0`) | `scipy.spatial.ConvexHull` for robust PCA-OBB | `compute_oriented_bounding_box(robust=True)` uses scipy under the hood in Open3D. | HIGH |

No new msgpack/pyzmq/psutil deps — all already pulled in by v2.0.

### pyproject.toml additions

Extend the existing `perception` optional-dependencies group; do not split into a new extra (keeps the install UX as `pip install -e '.[perception]'`):

```toml
[project.optional-dependencies]
perception = [
    "torch>=2.10.0",
    "transformers>=5.3.0",
    "ultralytics>=8.4.24",
    # v3.0 additions:
    "onnxruntime>=1.20.0",
    "timm>=1.0.11",
    "dill>=0.3.8",
]
# BoxeR itself is NOT pip-installable — installed into the subprocess worker's venv
# via git clone in scripts/setup_boxer_subprocess.sh (see ARCHITECTURE.md).
```

`rfdetr` is intentionally left out of the default extra (Roboflow's package pins old torch versions); if a developer wants to benchmark RF-DETR, they install it manually into the subprocess venv.

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| **CUDA / cuDNN / TensorRT** | Hard constraint: no NVIDIA GPU. Any dep that lists `nvidia-*` wheels as a requirement is banned. |
| **Grounding DINO (original)** | Runs on CPU but 8–15 s/frame at 640×640; OWLv2 is strictly better open-vocab at the same cost with first-class `transformers` support. |
| **nanoowl** | TensorRT-only OWL-ViT optimisation — NVIDIA Jetson-only by design. |
| **mmdetection / mmdetection3d** | Huge toolbox (~500 deps, its own model zoo, OpenMMLab C++ ops some of which need CUDA). We use 2 models; the HF `transformers` path is 99% smaller. |
| **detectron2** | Same reason as mmdet — huge and trending away from maintenance; most modern detectors have first-class HF releases now. |
| **FCOS3D / ImVoxelNet / MonoFlex / Cube R-CNN** | Trained on outdoor autonomous-driving datasets (KITTI/nuScenes). Will not detect office furniture. Retraining is out of milestone scope. |
| **Frustum-PointNets / VoteNet / 3DETR** | All require CUDA PointNet++ ops. No working CPU fallback. |
| **Open3D ML (torch/tf modules)** | 3D deep-learning model zoo inside Open3D — pulls in large extra deps and all flagship models are GPU-trained. The plain `open3d` geometry API (already installed) is all we need. |
| **ovmono3d (3DV 2026)** | Research code, no runnable inference checkpoint without retraining per-scene as of April 2026. Revisit at v3.1 if an official release lands. |
| **DROID-SLAM / neural-SLAM variants** | Already excluded in v2.0 for same GPU reason; keep excluded. |
| **BoxeR interactive viewer deps** (`moderngl`, `moderngl-window`, `imgui-bundle`) | BoxeR's desktop visualizer. We have Three.js. Skip. |
| **projectaria-tools** | Only needed for Project Aria glasses data. We use MuJoCo cameras. Skip. |
| **DETR-ResNet50 (original facebook/detr-resnet-50)** | Historical interest only; RT-DETRv2 is strictly faster and more accurate. Keep out of the registry. |

## Integration Architecture (preview — full in ARCHITECTURE.md)

```
                       DetectorProtocol (Python ABC)
             /            |            |            \
     YOLOv11-nano   RT-DETRv2-S   OWLv2-base    BoxeR worker
     (in-process,   (in-process,  (in-process,  (subprocess,
      ultralytics)   transformers) transformers) ZMQ+msgpack)
             \            |            |            /
              \           v            v           /
               └─────> Detection2D list <─────────┘
                               |
                               v
                      ThreeDLifterProtocol
                      /          |           \
         CenterProjection  PCA-OBB (Open3D)   BoxerLifter
         (v1.0 legacy)     (default v3.0)     (ships boxes directly,
                                                no post-processing)
                               |
                               v
                        Detection3D list
                      (center, extents, R, class, conf)
                               |
                               v
                   WebSocket → frontend/DetectionBoxes.ts
```

The dashed subprocess box is the **same** `SubprocessSLAMBridge` pattern from v2.0, generalised. Crash detection, ICP-style fallback (here: fallback to YOLO + PCA-OBB), and the ZMQ PAIR + msgpack IPC are unchanged.

## Version Compatibility Matrix

| Component | Version | Python 3.11 | Python 3.12 | CPU-only | pip install |
|-----------|---------|-------------|-------------|----------|-------------|
| transformers | 5.3–5.5 | Yes | Yes | Yes | Yes |
| torch | 2.10+ | Yes | Yes | Yes | Yes (CPU wheel) |
| ultralytics | 8.4+ | Yes | Yes | Yes | Yes |
| onnxruntime | 1.20+ | Yes | Yes | Yes | Yes |
| timm | 1.0.11+ | Yes | Yes | Yes | Yes |
| RT-DETRv2 (HF ckpt) | any | — | — | Yes | via transformers |
| OWLv2-base | any | — | — | Yes (slow) | via transformers |
| facebook/boxer | git main | — | Yes (authors recommend 3.12) | Yes (very slow) | No — subprocess venv |
| DINOv3 ViT-S/16 ckpt | any | — | — | Yes | via transformers |
| open3d | 0.18+ | Yes | Yes | Yes | Yes |

**Recommendation:** stay on Python 3.12 (project already requires `>=3.10,<3.13`). BoxeR authors themselves use 3.12; all transformers checkpoints are version-agnostic.

## CPU Latency Summary (single-thread, 2–4 CPU cores, honest estimates)

| Backend | 2D latency | 3D latency | Total | Expected FPS | Role |
|---------|-----------|-----------|-------|--------------|------|
| YOLOv11-nano + CenterProjection (v1.0) | 80–150 ms | <1 ms | 80–150 ms | 2–5 | Legacy / regression baseline |
| YOLOv11-nano + PCA-OBB (default v3.0) | 80–150 ms | 2–5 ms/det | ~100–200 ms | 2–4 | **Default real-time backend** |
| RT-DETRv2-S @ 320×320 ONNX + PCA-OBB | 70–120 ms | 2–5 ms/det | ~100–180 ms | 3–5 | Transformer real-time backend |
| RF-DETR-Nano @ 320×320 ONNX + PCA-OBB | ~180 ms | 2–5 ms/det | ~200–250 ms | 3–5 | Alternative transformer backend |
| OWLv2-base (in-process) + PCA-OBB | 1.5–4 s | 2–5 ms/det | 1.5–4 s | 0.25–0.5 | Open-vocab on-demand backend |
| BoxeR subprocess | 5–30 s | (native) | 5–30 s | 0.03–0.2 | Offline high-quality OBB backend |

This is what the metrics panel in the C2 UI will actually show. Users choose the latency/quality tradeoff per session.

## Sources

- [facebook/boxer on HuggingFace](https://huggingface.co/facebook/boxer) — HIGH confidence (official model repo)
- [facebookresearch/boxer GitHub](https://github.com/facebookresearch/boxer) — HIGH confidence (official code)
- [OWL-ViT (transformers docs)](https://huggingface.co/docs/transformers/en/model_doc/owlvit) — HIGH
- [Scaling OVD / OWLv2 paper](https://arxiv.org/abs/2306.09683) — HIGH
- [RF-DETR (Roboflow, ICLR 2026)](https://github.com/roboflow/rf-detr) — HIGH
- [RF-DETR-Nano CPU benchmark (issue #641)](https://github.com/roboflow/rf-detr/issues/641) — HIGH (direct measurement: ~200 ms @ 312×312 CPU)
- [RT-DETR on Ultralytics docs](https://docs.ultralytics.com/models/rtdetr/) — HIGH
- [RTDETRv2 vs YOLOv8 comparison](https://docs.ultralytics.com/compare/rtdetr-vs-yolov8/) — MEDIUM
- [Best Object Detection Models 2026 (Roboflow blog)](https://blog.roboflow.com/best-object-detection-models/) — MEDIUM
- [DINOv3 (transformers docs)](https://huggingface.co/docs/transformers/model_doc/dinov3) — HIGH
- [facebook/dinov3-vits16-pretrain-lvd1689m](https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m) — HIGH
- [transformers v5.3 release notes](https://github.com/huggingface/transformers/releases) — HIGH
- [Open3D OrientedBoundingBox API](https://www.open3d.org/docs/release/python_api/open3d.geometry.OrientedBoundingBox.html) — HIGH
- [Open Vocabulary Monocular 3D Object Detection (ovmono3d, 3DV 2026)](https://arxiv.org/abs/2411.16833) — MEDIUM (future reference)
- Project `.planning/milestones/v2.0-research/STACK.md` — HIGH (internal, subprocess pattern to reuse)
- Project `src/perception/detector.py`, `src/perception/detection_3d.py` — HIGH (current state)

---

*Stack research for v3.0 Pluggable Perception & 3D Object Detection: 2026-04-13*
