# Third-Party License Inventory

This document tracks SPDX identifiers and license obligations for every
runtime dependency in argus. The table is the source of truth — DO NOT add
a runtime dependency without updating this file.

## Runtime Dependencies

| Dep | SPDX | Scope | Upstream | Note |
|-----|------|-------|----------|------|
| Ultralytics YOLOv11 | AGPL-3.0 | Default detector backend (in-process) | https://github.com/ultralytics/ultralytics | **Copyleft** — distributing this codebase as a service triggers AGPL network-use clause. Document in deployment guide. |
| RT-DETRv2 (PekingU) | Apache-2.0 | Real-time transformer backend (in-process ONNX) | https://huggingface.co/PekingU/rtdetr_v2_r18vd | Permissive |
| facebook/BoxeR | CC-BY-NC-4.0 | Reference-quality 3D OBB backend (subprocess) | https://github.com/facebookresearch/boxer | **Non-commercial only — research/academic use.** Capability dict surfaces this in the UI per D-14. NOT for production deployments. |
| DINOv3 (facebook) | DINOv3 License (research-only) | BoxeR feature backbone, downloaded inside subprocess venv | https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m | Coupled with BoxeR's NC restriction. |
| ONNX Runtime | MIT | RT-DETRv2 inference engine | https://github.com/microsoft/onnxruntime | Permissive |
| Hugging Face Transformers | Apache-2.0 | Model loading + RT-DETRv2 export | https://github.com/huggingface/transformers | Permissive |
| huggingface-hub | Apache-2.0 | Snapshot download for pinned checkpoints | https://github.com/huggingface/huggingface_hub | Permissive |
| optimum (HF) | Apache-2.0 | ONNX export tooling (dev-only, not runtime) | https://github.com/huggingface/optimum | Permissive |
| msgpack-python | Apache-2.0 | Subprocess bridge wire encoding | https://github.com/msgpack/msgpack-python | Permissive |
| pyzmq | LGPL-3.0+BSD-3-Clause | Subprocess bridge transport | https://github.com/zeromq/pyzmq | LGPL implications via dynamic linking — accepted (we link against libzmq, do not vendor it). |
| Open3D | MIT | 3D OBB lifter + geometry | https://github.com/isl-org/Open3D | Permissive |
| PyTorch | BSD-3-Clause | Tensor runtime for YOLOv11 + (in subprocess) BoxeR | https://github.com/pytorch/pytorch | Permissive |
| numpy | BSD-3-Clause | Numerical core | https://numpy.org | Permissive |
| scipy | BSD-3-Clause | Numerical / rotation utilities | https://scipy.org | Permissive |
| opencv-python-headless | Apache-2.0 | Image preprocessing (letterbox resize) | https://opencv.org | Permissive |
| scikit-learn | BSD-3-Clause | DBSCAN clustering in PointClusterLifter | https://scikit-learn.org | Permissive |
| MuJoCo | Apache-2.0 | Simulation engine | https://github.com/google-deepmind/mujoco | Permissive |
| FastAPI | MIT | Web/coordination layer | https://github.com/tiangolo/fastapi | Permissive |
| uvicorn | BSD-3-Clause | ASGI server | https://github.com/encode/uvicorn | Permissive |
| websockets | BSD-3-Clause | WebSocket server | https://github.com/python-websockets/websockets | Permissive |

## Indirect / Upstream Dependencies (NOT SHIPPED by argus)

Below deps are pulled in transitively by BoxeR's internal pipeline when BoxeR is active — argus does NOT expose them as user-selectable backends. Listed here for transparency only.

| Dep | SPDX | Scope | Upstream | Note |
|-----|------|-------|----------|------|
| **[NOT-SHIPPED]** OWLv2 (google) | Apache-2.0 | BoxeR's internal 2D proposal network (loaded inside the BoxeR subprocess venv only) | https://huggingface.co/google/owlv2-base-patch16-ensemble | Permissive. Pulled in transitively by BoxeR; argus does NOT expose OWLv2 as a directly selectable backend (dropped per Phase 5 D-10). If Plan 06 confirms BoxeR does NOT actually load OWLv2 at runtime, this row MUST be deleted. |

## NC Compliance Mechanism

facebook/BoxeR is CC-BY-NC-4.0. argus surfaces this in the UI:
- `BoxeRBackend.CAPABILITIES["license"] = "CC-BY-NC-4.0"` is rendered as a pill
  in the Detector Dropdown (Phase 3 D-05 capability badge path).
- Users see the NC restriction inline before selecting BoxeR — no extra modal.

## Audit checklist

- [ ] Every entry in `pyproject.toml [dependencies]` and `[optional-dependencies]` appears here.
- [ ] Every model checkpoint downloaded by `make download-models` has its license documented.
- [ ] CC-BY-NC and AGPL deps are surfaced in the UI via capability dict.
- [ ] Plan 06 has verified whether BoxeR actually loads OWLv2 at runtime; if not, the OWLv2 row in "Indirect / Upstream Dependencies" has been removed.
