# Phase 1: detector-api-foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 01-detector-api-foundation
**Areas discussed:** Protocol surface, Availability + capability contract, Eval-mode enforcement, YOLO migration

---

## Protocol Surface

### Q: What is the shape of DetectorProtocol.process_frame?

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror SLAM exactly | `process_frame(frame: SensorFrame) -> Detections2D`. Prompts/class filters via apply_params. | ✓ |
| Add text_prompt arg | `process_frame(frame, text_prompt: str \| None = None) -> Detections2D`. | |
| Polymorphic input dataclass | `process_frame(request: DetectorRequest) -> Detections2D`. | |

**User's choice:** Mirror SLAM exactly
**Notes:** "open-vocab prompts should be configured to the specific model, not per query, same with optional class filters." Per-model configuration via `apply_params()` locked as the canonical pattern.

---

### Q: Which protocol methods are required on every detector backend?

| Option | Description | Selected |
|--------|-------------|----------|
| warmup(dummy_frame) | Mandatory; addresses first-inference stall. | ✓ |
| reset() | Required even for stateless backends (no-op OK). | ✓ |
| get_metrics() -> dict | At minimum {inference_ms_p50/p95, n_frames}. | ✓ |
| apply_params(dict) -> dict | Returns echo of accepted params; drives WS param updates. | ✓ |

**User's choice:** All four required.
**Notes:** Full method surface locked at the Protocol level; no optional methods.

---

### Q: Should Detections2D carry backend-specific extras (masks, features, text_logits)?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — optional dict field | `extras: dict[str, Any] \| None = None` alongside typed required fields. | ✓ |
| No — strict typed shape | Only class_id, class_name, score, bbox. | |
| Defer to Phase 5 | Ship strict now; add extras when OWLv2 needs text_logits. | |

**User's choice:** Yes — optional dict field
**Notes:** Forward-compatible without locking in backend-specific fields on the Protocol.

---

### Q: Does Detection3DProtocol.lift take the SLAM point cloud (slam_cloud)?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — required param | May be `None`; Phase 4 PointClusterLifter consumes it. | ✓ |
| No — depth only | Phase 4 would need to bolt slam_cloud back on later. | |
| Optional with capability flag | Lifters advertise requires_point_cloud; coordinator branches. | |

**User's choice:** Yes — required param
**Notes:** Contract is set once for Phase 1 and Phase 4 uses it without a Protocol edit.

---

## Availability + Capability Contract

### Q: How should a backend report its install hint when missing?

| Option | Description | Selected |
|--------|-------------|----------|
| Hint on decorator | `@detector_backend(..., requires=['ultralytics>=8.4.24'])`. | |
| Classmethod probe | `@classmethod available() -> tuple[bool, str \| None]`. | ✓ |
| Hybrid | Decorator requires + override-able available(). | |

**User's choice:** Classmethod probe
**Notes:** Handles BoxeR's non-pip setup script + ONNX weight presence + pip deps uniformly. Registry never invents hint text.

---

### Q: Which capability keys are MANDATORY on every detector backend's CAPABILITIES dict?

| Option | Description | Selected |
|--------|-------------|----------|
| framework + license + cpu_latency_hint_ms | The three UI-badge fields (DET-UI-01). | ✓ |
| outputs_3d_natively | Core architectural switch — bypass lifter registry. | ✓ |
| input_type | Enum RGB_ONLY / RGBD / RGB_TEXT_PROMPT. | ✓ |
| Just outputs_3d_natively (minimal) | Light contract; risk of missing license. | |

**User's choice:** All five keys mandatory.
**Notes:** Registration must fail at import time if any MANDATORY key is missing. Prevents license/framework omission in shipped backends.

---

### Q: How are builtin backends registered at startup?

| Option | Description | Selected |
|--------|-------------|----------|
| Side-effect import (SLAM pattern) | `import src.perception.backends  # noqa: F401`. | ✓ |
| Explicit register_builtin_backends() | main.py calls a registration function. | |
| Entry points | pyproject.toml entry-points; runtime scan. | |

**User's choice:** Side-effect import (SLAM pattern)
**Notes:** Matches existing `import src.slam.backends` line in main.py.

---

## Eval-Mode Enforcement

### Q: How should model.eval() + torch.inference_mode() be enforced?

| Option | Description | Selected |
|--------|-------------|----------|
| TorchBackendMixin base class | Compile-time hard to forget; concrete enforcement. | ✓ |
| Decorator on process_frame | Runtime auto-wrap. | |
| Doc + smoke test only | Trust backends; catch regressions empirically. | |
| Registry post-init assertion | Can't catch missing inference_mode. | |

**User's choice:** TorchBackendMixin base class
**Notes:** Mixin `__init__` calls `self.model.eval()`; provides `_inference()` context manager for `torch.inference_mode()`. Non-torch future backends opt out.

---

### Q: Where does the RSS smoke test live in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| tests/smoke/test_detector_rss.py | Dedicated file; auto-parametrizes over registry. | ✓ |
| tests/perception/test_yolo_backend.py | Colocated; per-backend duplication risk. | |
| Parametrized over registry | (Same file as option 1 with parametrize decorator.) | |

**User's choice:** tests/smoke/test_detector_rss.py (parametrized over `DetectorRegistry.list_backends()`)
**Notes:** Phase 5 backends are auto-covered; no per-backend test-file edit needed.

---

### Q: How strict is the 200 MB RSS budget in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard fail at 200 MB | Literal ROADMAP reading; CI noise risk. | |
| Warn at 200 MB, fail at 400 MB | Two-tier guard rails. | ✓ |
| Hard fail with explicit warmup exclusion | Steady-state delta only. | |

**User's choice:** Warn at 200 MB, fail at 400 MB
**Notes:** 200 MB annotation preserves ROADMAP success criterion as an alert; 400 MB prevents true regression. Smoke test still excludes 5 warmup iterations from the measured baseline.

---

## YOLO Migration

### Q: How should YOLOv11Backend be produced from the existing ObjectDetector?

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap ObjectDetector (minimal change) | YOLOv11Backend delegates to ObjectDetector._detect. | |
| Extract _detect into backend, delete old | Rewires coordinator in Phase 1. | |
| Shim + hybrid | Fresh YOLOv11Backend; ObjectDetector stays; Phase 2 deletes it. | ✓ |

**User's choice:** Shim + hybrid
**Notes:** Fresh implementation against the new Protocol; both paths coexist for one phase; Phase 2's DetectorWorkerPool rewire retires ObjectDetector.

---

### Q: Where does the 2D→3D projection code live at end of Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| MedianDepthLifter wraps detection_3d.py | Two projection paths still exist. | |
| Consolidate into lifter now | Fix Pitfall P3 in Phase 1. | ✓ |
| New geometry.py module now | Align Phase 1 and Phase 4 now. | |

**User's choice:** Consolidate into lifter now
**Notes:** Both `detector.py` inline projection and `detection_3d.py::project_detections_to_3d` move into `MedianDepthLifter.lift()` in Phase 1. Fixes the duplicate-projection pitfall before Phase 4 builds on top.

---

### Q: What is the fixture-frame regression test's failure threshold?

| Option | Description | Selected |
|--------|-------------|----------|
| Bit-exact bbox + count | Strongest; YOLO NMS deterministic on CPU. | ✓ (Claude's Discretion) |
| Count-exact + bbox ±2px | Robust to float reorderings. | |
| Count + class_ids only | Lowest precision. | |

**User's choice:** You decide — Claude picked bit-exact.
**Notes:** Bit-exact is achievable because YOLO's NMS on CPU is deterministic; relax to ±2 px only if CI flakes, and document the reason.

---

## Claude's Discretion

- File layout for `src/perception/` (types.py vs protocol.py vs registry.py, backends/, lifters/)
- `PARAMETER_SCHEMA` JSON-Schema structure for YOLOv11
- `DetectorInput` Python `Enum` vs `Literal` string
- `OrientedBox3D` dataclass field order (skeleton-only in Phase 1)
- Test fixture format (NPZ vs synthetic)

## Deferred Ideas

- `src/perception/geometry.py` canonical unprojection — deferred to Phase 4
- Dynamic thread budget tuning based on robot count — Phase 2+
- Entry-point-based third-party backend registration — rejected for v3.0
- `DetectorRequest` polymorphic input dataclass — rejected
