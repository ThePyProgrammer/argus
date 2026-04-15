# Phase 5: second-backends-boxer-rtdetr-owlv2 - Research

**Researched:** 2026-04-15
**Domain:** Two new detector backends (RT-DETRv2-S in-process ONNX + facebook/BoxeR subprocess), pinned-checkpoint download pipeline, crash fallback, LICENSES.md
**Confidence:** HIGH (decisions are locked in CONTEXT.md; only HOW remains)
**Out of scope:** OWLv2 (dropped per D-10), detection metrics (Phase 6), pipeline-editor nodes (Phase 7)

## Summary

Phase 5 is the pluggability regression test. All architectural decisions (D-01..D-14) are locked in CONTEXT.md and are not subject to re-derivation by the planner. The research below answers the *how* questions: exact SHAs, exact API call shapes, exact file/dir layouts, exact wave structure, exact validation tests. Two HF/GitHub SHAs were verified live during this research session and are recorded as `[VERIFIED: ...]`. Two backend latency budgets are training-data-derived `[ASSUMED]` and must be confirmed during Wave 0 smoke benchmarks.

**Primary recommendation:** Plan as 4 waves of 9–11 plans. Wave 0 = pyproject + LICENSES + Makefile + download_models.py scaffold (parallel files, no dependencies). Wave 1 = subprocess_bridge schema extension + boxer_worker.py + setup_boxer_subprocess.sh (parallel). Wave 2 = RTDETRv2Backend + BoxeRBackend + worker_pool crash handler (RTDETRv2 + BoxeR can land in parallel; crash handler depends on BoxeR class). Wave 3 = integration tests + offline-boot test + 5 SC validation. Sampling: per-task pytest single-file run (≤30 s), per-wave perception subset run (~2 min), phase gate full suite + manual SC#3 `kill -9` exercise.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01 through D-14, excluding D-10)

**D-01 — BoxeR venv layout:** `subprocess_venvs/boxer/` (gitignored). Setup script `scripts/setup_boxer_subprocess.sh` MUST be idempotent (`[ -f subprocess_venvs/boxer/.ready ] && exit 0` at top). Touches `.ready` after success.

**D-02 — Msgpack reply schema (ADDITIVE):** Phase 2's `{ts, inference_ms, n_det, classes, scores, bboxes}` is extended with optional `boxes_3d: list[dict]` carrying `tx,ty,tz,qx,qy,qz,qw,w,h,d` per detection. `bboxes` (2D xyxy) is still emitted for CameraFeed overlay. Composer iterates `boxes_3d` and constructs `OrientedBox3D` via `types.OrientedBox3D(...)`; backends MUST NOT handcraft quaternions.

**D-03 — Crash watchdog ownership:** `DetectorWorkerPool` owns the watchdog. Each worker wraps `bridge.send_frame()` in `try/except (BridgeHangError, SubprocessDiedError)`. On catch: pool emits `crash_fallback` WS message (same envelope as `src/exploration/exploration_loop.py:207` SLAM pattern), creates `DetectorRegistry.create("yolov11")`, runs warmup, and atomically swaps backend ref into all worker threads (mirror Phase 4 D-10 lifter swap). Total ≤5 s.

**D-04 — Post-crash availability:** `DetectorRegistry.set_available("boxer", False, reason="Crashed this session — restart the coordinator to retry.")`. Session-scoped; no auto-retry. Restart of process clears the flag.

**D-05 — Bridge lazy spawn:** `BoxeRBackend.__init__` stores config only. Bridge spawn happens on first `warmup()` call. Construction MUST be cheap so registry enumeration (`/api/detectors/backends`) doesn't spawn subprocesses.

**D-06 — ONNX acquisition:** On-demand export via `transformers` snapshot_download + `optimum.exporters.onnx.main_export`, cached to `models/rtdetrv2/<sha>/model.onnx`. Backend `__init__` checks artifact exists; if missing, raises with `make download-models-rtdetrv2` hint (does NOT auto-download). `optimum[exporters]` lives in `dev` extra (download-time only).

**D-07 — ORT runtime + EP:** `onnxruntime>=1.19.0` in `perception` extra. `providers=["CPUExecutionProvider"]`. `intra_op_num_threads` inherits from `src/_thread_config.py` (Phase 1 D-04 invariant). NO module-scope thread-pool sets in backend file.

**D-08 — Fixed input 320×320:** ONNX export with static shape `[1, 3, 320, 320]`. Backend letterbox-resizes 480×640 MuJoCo frames to 320×320 (preserve aspect ratio, black pad), then scales output bboxes back to 480×640 coords.

**D-09 — Per-worker ORT session:** Each `DetectorWorker` thread owns its own `ort.InferenceSession`. ~80 MB × N robots (default N=2 → 160 MB). Mirrors Phase 2 symmetric per-robot backend instantiation.

**D-11 — Models dir layout:** `models/<backend-slug>/<sha>/<artifact>`. Concretely: `models/rtdetrv2/<RT_DETRV2_SHA>/{pt/, model.onnx}`, `models/boxer/<BOXER_SHA>/{weights.pth, dinov3/, owlv2/}`. `models/` gitignored; `.gitkeep` + README.md document layout.

**D-12 — SHA pinning + offline gate:** Module-level constants `RT_DETRV2_SHA` and `BOXER_SHA`. HF loaders pass `revision=RT_DETRV2_SHA, local_files_only=True` after first fetch. `make download-models` runs with `HF_HUB_OFFLINE=0`; offline test uses `HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1`. BoxeR pin = git commit SHA (clone + `git checkout`).

**D-13 — Makefile + download_models.py split:** Thin Makefile targets `download-models`, `download-models-rtdetrv2`, `download-models-boxer`. Python logic lives in `scripts/download_models.py` (snapshot_download, ONNX export, sha256 verify, rollback). BoxeR weight fetch lives in `scripts/setup_boxer_subprocess.sh` because it runs inside the subprocess venv.

**D-14 — LICENSES.md + license badge:** `LICENSES.md` markdown table at repo root. BoxeR backend advertises `license: "CC-BY-NC-4.0"` via capability dict — Phase 3 D-05 already renders `license` badge inline in `DetectorDropdown`. NO additional ConfirmModal.

### Claude's Discretion (planner picks)
- Exact RT-DETRv2 HF SHA → **VERIFIED below** as `5650961749fa93567c0d46fc7f43ea4f9e914107`
- Exact facebook/boxer git SHA → **VERIFIED below** as `df474128a76ba42b05bc81feca7ac1a53fab41af`
- sha256 values for BoxeR-fetched DINOv3/BoxerNet/OWLv2 artifacts → computed at first fetch, committed into `scripts/download_models.py` constants
- `ort.SessionOptions` tuning beyond `intra_op_num_threads` (graph optimization level, mem pattern)
- BoxeR worker script's internal logging + heartbeat cadence (within Phase 2 bridge contract)
- sha256-mismatch rollback strategy (delete `models/<backend>/<bad-sha>/` dir vs move to `.trash/`)
- Whether `Makefile` grows non-model targets (test, lint, etc.)

### Deferred Ideas (OUT OF SCOPE)
OWLv2 backend; text-prompted open-vocab UI; multi-prompt input; warmup UX for slow ONNX export; OpenVINO EP; dynamic ONNX input shape; shared ORT session across workers; manifest-file SHA pinning; ConfirmModal gating BoxeR selection; auto-retry BoxeR after crash; hot-swap detector mid-session.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-MODELS-02 | RT-DETRv2-S backend, ONNX-accelerated, ≤250 ms/frame at 320px on CPU | §RT-DETRv2 Technical Reference; D-06/D-07/D-08/D-09 implementation notes |
| DET-MODELS-03 | facebook/BoxeR via SubprocessDetectorBridge + own venv + 3D OBBs natively | §BoxeR Subprocess Technical Reference; D-01/D-02/D-05 implementation notes |
| DET-MODELS-06 | Backend crash → `crash_fallback` WS → fall back to YOLOv11 → CrashToast | §Crash Fallback Pattern Mirror (D-03 + SLAM precedent at exploration_loop.py:207) |
| DET-MODELS-07 | Pinned `revision=` SHA on every checkpoint; `make download-models` pre-fetches to `./models/` for offline | §Models Directory + Pinning Layout; §Makefile + download_models.py Contract |
| DET-MODELS-08 | LICENSES.md documents BoxeR CC-BY-NC-4.0 | §LICENSES.md Schema (D-14) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

User's global CLAUDE.md primarily references blueprint/turing tooling (ADRs + ML harness commands) — not directly applicable to Phase 5. No project-local `./CLAUDE.md` exists. The binding project constraints come from **CONTEXT.md (D-01..D-14)** and **STATE.md "Decisions"** which forbid:
- Module-scope `torch.set_num_threads()` outside `src/_thread_config.py` (Phase 1 D-04 invariant). **Applies to ORT: `sess_options.intra_op_num_threads = N` MUST read from `_thread_config`, not be hardcoded.**
- Inline quaternion construction in any backend. **`OrientedBox3D(...)` is the sole construction site.** BoxeR composer reads `qx,qy,qz,qw` from msgpack and passes them straight into the dataclass — does not normalize, flip, or compose.
- `mAP` in UI without committed labeled eval set (Phase 6 concern; not Phase 5).
- New WS message types or REST routes (CONTEXT.md "Specifics": "zero new WS message types, zero new REST routes" — `crash_fallback` already exists from SLAM).
- Frontend code changes (CONTEXT.md "In: Frontend: ZERO changes").

---

# Decision Implementation Notes

> One subsection per locked decision. **Decisions are locked — only HOW is in scope.**

### D-01 — BoxeR venv + setup script

**File:** `scripts/setup_boxer_subprocess.sh` (new, executable, bash).

**Skeleton:**
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_ROOT/subprocess_venvs/boxer"
BOXER_REPO="$REPO_ROOT/subprocess_venvs/boxer/repo"
BOXER_SHA="df474128a76ba42b05bc81feca7ac1a53fab41af"  # verified 2026-04-15

# Idempotency gate (D-01 literal)
if [ -f "$VENV_DIR/.ready" ]; then
  echo "[setup_boxer] $VENV_DIR/.ready exists; skipping."
  exit 0
fi

mkdir -p "$VENV_DIR"
# uv-managed venv (project uses uv per pyproject.toml convention)
uv venv --python 3.12 "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Clone & pin
git clone https://github.com/facebookresearch/boxer "$BOXER_REPO"
git -C "$BOXER_REPO" checkout "$BOXER_SHA"

# Install deps via uv (BoxeR uses pyproject.toml — see verified findings)
uv pip install -e "$BOXER_REPO"

# Fetch checkpoints into models/boxer/<sha>/ (D-11 layout)
MODELS_DIR="$REPO_ROOT/models/boxer/$BOXER_SHA"
mkdir -p "$MODELS_DIR"
( cd "$BOXER_REPO" && CKPTS_DIR="$MODELS_DIR" bash scripts/download_ckpts.sh )

touch "$VENV_DIR/.ready"
echo "[setup_boxer] ready."
```

**Caveats:**
- BoxeR's `download_ckpts.sh` is the source of truth for what binary artifacts exist (DINOv3, OWLv2, BoxerNet weights). Override its target dir via env var if the script supports it; otherwise post-copy artifacts into `models/boxer/$BOXER_SHA/` after default download. Wave 0 spike must determine the exact override mechanism.
- `uv venv --python 3.12` matches BoxeR's own `python3.12` requirement (verified). The repo-root venv may be 3.10–3.12; subprocess venv MUST be 3.12.
- `.gitignore` MUST include `subprocess_venvs/`.

### D-02 — Msgpack reply schema (ADDITIVE)

**File modified:** `src/perception/subprocess_bridge.py` (Phase 2 schema documented in module docstring, unchanged at the transport layer; the dict is opaque to the bridge).

**Schema (extended):**
```python
# Outgoing (unchanged from Phase 2):
{
    "ts": float,
    "rgb_shape": [H, W, 3],
    "rgb_dtype": "uint8",
    "depth_shape": [H, W] | None,
    "depth_dtype": "float32" | None,
    "params": {...},  # opaque per-frame backend params
}
# Incoming (Phase 5 EXTENSION — backwards-compatible additive):
{
    "ts": float,
    "inference_ms": float,
    "n_det": int,
    "classes": list[int],
    "scores": list[float],
    "bboxes": list[list[float]],   # 2D xyxy in pixels (Phase 2 — kept for CameraFeed)
    # NEW Phase 5 optional:
    "boxes_3d": list[dict] | None,  # OMIT or set None when backend not 3D-native
    # each dict: {"tx", "ty", "tz", "qx", "qy", "qz", "qw", "w", "h", "d"}
    # all values are plain Python floats (msgpack-native)
}
```

**Migration safety proof:**
- Phase 2's `test_subprocess_bridge_skeleton.py` and `scripts/echo_detector_worker.py` emit the original 6-key reply. They will continue to work because the bridge does NOT interpret the dict (line 197: `return msgpack.unpackb(...)` returns raw dict). Only the BoxeR composer reads `boxes_3d`; YOLOv11 has no bridge so no schema concern.
- The Phase 2 invariant `strict_map_key=True, raw=False` (line 197) accepts the new schema unchanged: `tx,ty,tz,qx,qy,qz,qw,w,h,d` are str keys; their values are floats, not keys, so `strict_map_key` does not interfere.
- Per-frame payload size estimate: 10 detections × 10 floats × 8 bytes = 800 bytes/frame. Negligible vs the RGB frame (480×640×3 = 921 KB).

**Composer translation (in `src/perception/backends/boxer_backend.py`):**
```python
# After bridge.send_frame() returns reply dict:
items_3d = []
for det_idx, b3 in enumerate(reply.get("boxes_3d") or []):
    items_3d.append(OrientedBox3D(
        center=np.array([b3["tx"], b3["ty"], b3["tz"]], dtype=np.float64),
        # NB: D-02 sends FULL extents (w,h,d). OrientedBox3D wants HALF extents.
        half_extents=np.array([b3["w"]/2, b3["h"]/2, b3["d"]/2], dtype=np.float64),
        quaternion=np.array([b3["qx"], b3["qy"], b3["qz"], b3["qw"]], dtype=np.float64),
        class_id=int(reply["classes"][det_idx]),
        class_name=COCO_NAMES.get(int(reply["classes"][det_idx]), f"class_{...}"),
        score=float(reply["scores"][det_idx]),
        track_id=None,
        bbox_xyxy=tuple(int(v) for v in reply["bboxes"][det_idx]),
    ))
return Detections3D(items=items_3d, lifter_ms=0.0, detector_ms=reply["inference_ms"], ...)
```
**CRITICAL:** D-02 spec says "extent (full, not half)" — but `OrientedBox3D.half_extents` field expects half. Composer divides by 2. This conversion line MUST appear in the planner's task. Failing to halve will render boxes 2× actual size in Three.js.

### D-03 — Crash watchdog ownership (mirror SLAM pattern)

**Reference SLAM precedent:** `src/exploration/exploration_loop.py:207` — when `result.tracking_status.value == "lost"` AND the SLAM has a `_bridge` attribute, the exploration loop appends a `crash_fallback` message to `self._streaming_viz._message_queue` and swaps in `SLAMRegistry.create("icp", ...)`. The dict shape:
```python
{
    "type": "crash_fallback",
    "payload": {
        "subsystem": "slam",        # Phase 5 will use "detector"
        "crashed_backend": backend_name,
        "fallback_backend": "icp",  # Phase 5 will use "yolov11"
    },
}
```

**Phase 5 parallel pattern (in `src/perception/worker_pool.py`):**

1. New module-level exception classes (or reuse existing) — recommend defining in `subprocess_bridge.py`:
   ```python
   class BridgeHangError(RuntimeError): ...
   class SubprocessDiedError(RuntimeError): ...
   ```
   Currently `send_frame()` returns `None` on failure (line 164, 172, 199–212). Phase 5 should EITHER (a) keep returning None and have the worker treat None as "subprocess crashed", OR (b) raise the typed exceptions for richer signal. **Recommend (b)** — typed exceptions let the worker_pool distinguish hang from crash for the `reason` field in `crash_fallback`. Update `send_frame()` to raise instead of returning None on the two failure paths (zmq.Again → BridgeHangError; Popen.poll() != None or zmq.ZMQError → SubprocessDiedError). Existing tests (`test_subprocess_bridge.py`) need to update assertions accordingly.

2. New method `DetectorWorkerPool.on_backend_crash(crashed_backend, reason, fallback="yolov11")`:
   - Logs the event.
   - Constructs fallback backend via `DetectorRegistry.create("yolov11", ...)`.
   - Calls `fallback.warmup(dummy_frame)` synchronously (acquires the same `_swap_lock` used by Phase 4 `swap_lifter`).
   - Re-binds `worker._detector` for every worker under `_swap_lock` (mirror Phase 4 D-10 atomic ref swap).
   - Marks original via `DetectorRegistry.set_available(crashed_backend, False, reason=...)` (D-04). **Note: `DetectorRegistry` does not currently expose `set_available()`** — this method must be added in Wave 1 (small change to registry.py).
   - Pushes `{"type": "crash_fallback", "payload": {"subsystem": "detector", "crashed_backend": ..., "fallback_backend": "yolov11", "reason": ...}}` onto the streaming_viz `_message_queue` (the pool needs a reference to it — pass via `__init__` or expose a setter that `main.py` calls).

3. Worker invocation site (in `src/perception/worker.py`'s loop): wrap the bridge-bound `process_frame` call in `try / except (BridgeHangError, SubprocessDiedError) as exc: pool.on_backend_crash(...)`. The worker thread does NOT block on warmup; it returns from this iteration and continues with the swapped detector on next frame.

4. **Frontend already wired:** `frontend/src/hooks/useWebSocket.ts:188-203` has the handler stub for `subsystem === 'detector'` (currently console.log — Phase 5 simply emits the WS message so the existing handler fires). Phase 5 still needs to ADD detector-specific code in the `else` branch (lines 197-202): set `useDetectorStore.getState().setCrashMessage(...)`, `setActive('yolov11', 'YOLOv11-nano', {})` analogous to the SLAM branch. **This is the ONLY frontend code change Phase 5 may need** — it's a 4-line edit inside the `else` branch, not a new component. CONTEXT.md "In:" line says "Frontend: ZERO changes beyond what Phase 3 + Phase 4 already shipped" — this 4-line edit is necessary to actually populate `crashMessage` for the `CrashToast` to render. Planner SHOULD include it as a tiny task; if the user objects, the alternative is for the SLAM-style code to live in the SLAM branch and detector branch separately, which is simpler than a generic dispatcher.

   **Actually re-reading CONTEXT.md D-03:** "Frontend `CrashToast` ... renders from `detectorStore.crashMessage` which `useWebSocket.ts:188-200` populates." — so the user expects the populate path to exist. The current code at line 197-202 has only a console.log placeholder. Plan MUST replace the placeholder with real `useDetectorStore.getState().setCrashMessage(...)` calls.

**Total time from kill -9 to fallback complete:** bridge `RCVTIMEO=5000ms` (line 128) + YOLOv11 warmup (~150 ms — see yolov11_backend.py) + ref swap (≪1ms) ≈ 5.2 s. Within SC#3's 5 s budget? **Borderline.** The 5 s SC budget probably starts from the WS message arrival (which fires before warmup completes). Need to confirm with discuss-phase whether the 5 s budget covers (a) until WS message arrives, or (b) until fallback is fully serving frames. Recommended interpretation: (a) — message-arrival is what user observes (CrashToast pops). Warmup finishing 200 ms later is invisible.

### D-04 — Post-crash availability (session-scoped)

**Required new method on `DetectorRegistry`** (in `src/perception/registry.py`):
```python
@classmethod
def set_available(cls, name: str, available: bool, reason: str | None = None) -> None:
    """Override availability for a registered backend (session-scoped).
    Used by DetectorWorkerPool.on_backend_crash() to lock out a crashed backend
    until the process restarts."""
    if name not in cls._backends:
        raise ValueError(f"Unknown backend '{name}'")
    cls._backends[name]["_override_available"] = (available, reason)
```

Then `list_backends()` checks for `_override_available` and surfaces it in the response dict before falling through to `_probe_availability()`. Process restart wipes the dict (it's a class attribute that re-populates from `@detector_backend` decorator on import).

**Frontend rendering:** Phase 3 D-06 already renders greyed-out backends with the `reason` field inline in `DetectorDropdown` (`available: false` + `reason: "..."` from `/api/detectors/backends`). Phase 5 doesn't touch the dropdown.

### D-05 — Bridge lazy spawn

**File:** `src/perception/backends/boxer_backend.py`.
```python
@detector_backend(name="boxer", display="facebook/BoxeR (subprocess)")
class BoxeRBackend(DetectorProtocol):
    CAPABILITIES = {
        "framework": "subprocess",
        "license": "CC-BY-NC-4.0",
        "cpu_latency_hint_ms": 15000,  # 15 s — reference, not real-time
        "outputs_3d_natively": True,    # bypass lifter (Phase 3 D-08 hides LifterDropdown)
        "input_type": DetectorInput.RGBD,
    }
    PARAMETER_SCHEMA = {...}

    def __init__(self, **kwargs):
        # Cheap — no subprocess spawn (D-05).
        self._kwargs = kwargs
        self._bridge: SubprocessDetectorBridge | None = None
        # Per Phase 1 D-04: do NOT touch torch.set_num_threads here.
        # Subprocess inherits its own _thread_config inside the BoxeR venv.

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        ready_marker = Path("subprocess_venvs/boxer/.ready")
        if ready_marker.exists():
            return True, None
        return False, "run scripts/setup_boxer_subprocess.sh (or `make download-models-boxer`)"

    def warmup(self, dummy_frame: SensorFrame) -> None:
        # Lazy spawn here, NOT in __init__ (D-05).
        if self._bridge is None:
            worker_python = Path("subprocess_venvs/boxer/bin/python")
            worker_script = Path("scripts/boxer_worker.py")
            self._bridge = SubprocessDetectorBridge(
                binary_path=str(worker_python),
                args=[str(worker_script)],
            )
            self._bridge.start()
        # First inference ≤30 s (SC#1) — but BoxeR is slow; SC#2 has no explicit budget.
        # SC#2 only requires "warmup completes" — so we can take longer than 30 s.
        self.process_frame(dummy_frame)
```
**Critical caveat:** `bridge.start()` binds the IPC socket and Popen-spawns the worker; the worker imports BoxeR (~5–15 s for DINOv3 + OWLv2 + BoxerNet). The bridge's `RCVTIMEO=5000ms` is per-`recv`, not for spawn. First `send_frame` after spawn must NOT be invoked until worker has connected — current Phase 2 bridge does NOT have a handshake. Plan should either (a) extend bridge with a `wait_for_ready()` handshake call (small ext to subprocess_bridge), OR (b) have boxer_worker.py block on weight-loading BEFORE connecting the socket (so the connect itself is the readiness signal). **Recommend (b)** — worker blocks on import + model load, then `sock.connect()`, then enters the recv loop. The bridge's `send_frame` will wait on `recv` for the reply; if model load took 10 s and the bridge's first send happens 1 s after spawn, it will hang for 4 s of the 5 s timeout, then fire BridgeHangError. **Therefore** the bridge needs an extended timeout for first call OR an explicit `bridge.wait_for_handshake(timeout_s=60)` method. Wave 0 needs a small spike to settle this.

### D-06 — ONNX acquisition (transformers + optimum)

**Verified API call** ([CITED: huggingface.co/docs/optimum]):
```python
from optimum.exporters.onnx import main_export
main_export(
    model_name_or_path=f"models/rtdetrv2/{RT_DETRV2_SHA}/pt",
    output=Path(f"models/rtdetrv2/{RT_DETRV2_SHA}/"),
    task="object-detection",
    input_shapes={"pixel_values": [1, 3, 320, 320]},
    monolith=True,        # single model.onnx (no encoder/decoder split)
    no_post_process=True, # we'll do post-processing in numpy in the backend
)
```
Note: `optimum-cli export onnx` is the CLI form; the Python API is more reliable for embedded scripting in `download_models.py`. CLI invocation as alternative:
```bash
optimum-cli export onnx \
  --model PekingU/rtdetr_v2_r18vd \
  --task object-detection \
  models/rtdetrv2/<SHA>/
```
But CLI doesn't accept `revision=<sha>` directly; we MUST snapshot_download first to fix the SHA, then point optimum at the local dir. The Python API form above does exactly that.

**Intermediate artifacts left by optimum:** typically `model.onnx`, `config.json`, `preprocessor_config.json`. These all live in `models/rtdetrv2/<SHA>/`. The PyTorch snapshot lives separately in `models/rtdetrv2/<SHA>/pt/`. Backend at runtime needs `model.onnx` + `preprocessor_config.json` (for normalization mean/std).

**Optimum runtime requirement:** `optimum.exporters.onnx` requires `transformers` AND `optimum` AT EXPORT TIME ONLY. After export, the runtime backend only needs `onnxruntime` + `numpy` + `Pillow` (or cv2) for image preprocessing — `transformers` is not loaded at runtime. This is the Phase 5 win: no torch at the in-process detector layer for RT-DETRv2.

### D-07 — ORT runtime + EP

**Implementation pattern in `src/perception/backends/rtdetrv2_backend.py`:**
```python
import onnxruntime as ort
from src._thread_config import _DEFAULT_BUDGET  # or expose a public getter

sess_options = ort.SessionOptions()
# Inherit Phase 1 D-04 budget. Do NOT call ort.set_default_logger_severity globally.
sess_options.intra_op_num_threads = _DEFAULT_BUDGET  # 2 by default
sess_options.inter_op_num_threads = 1
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
# Phase 1 D-04 invariant: ALL thread budget config flows through _thread_config.py.
# Recommend exposing src._thread_config.get_default_budget() rather than reading
# the private constant. Wave 1 task: add public getter.

session = ort.InferenceSession(
    str(onnx_path),
    sess_options=sess_options,
    providers=["CPUExecutionProvider"],
)
```

**Known onnxruntime 1.19+ caveats with RT-DETRv2:**
- RT-DETRv2 uses `MultiScaleDeformableAttention` (msda) op. As of training data, `msda` is supported in ORT-CPU since ~1.18. Confirm by exporting + running once in Wave 0; if msda errors at session creation, fall back to `monolith=False` export which splits the op into ATen primitives. `[ASSUMED]`
- `Grid` op: not used by RT-DETRv2-S according to the architecture paper — DETR variants don't grid-sample on CPU paths.
- ORT ≥1.19 changed default `EnableMemPattern` to True; safe for our 320×320 fixed-shape session.

### D-08 — Fixed input 320×320 (letterbox)

**Preprocessing (in `rtdetrv2_backend.py` `_preprocess()`):**
```python
def _letterbox_320(rgb_480x640: np.ndarray) -> tuple[np.ndarray, float, tuple[int,int]]:
    """Resize 480x640 → 320x320 preserving aspect ratio with black pad.
    Returns (chw_float32_normalized, scale, (pad_top, pad_left))."""
    H, W = rgb_480x640.shape[:2]  # 480, 640
    scale = 320.0 / max(H, W)      # 320/640 = 0.5
    new_h, new_w = int(round(H*scale)), int(round(W*scale))  # 240, 320
    resized = cv2.resize(rgb_480x640, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_top = (320 - new_h) // 2     # 40
    pad_left = (320 - new_w) // 2    # 0
    canvas = np.zeros((320, 320, 3), dtype=np.uint8)
    canvas[pad_top:pad_top+new_h, pad_left:pad_left+new_w] = resized
    # Normalization — see RT-DETRv2 Technical Reference below.
    # Per RTDetrImageProcessor default: rescale (/ 255) ONLY (no mean-std subtract).
    chw = canvas.transpose(2, 0, 1).astype(np.float32) / 255.0
    return chw[None, ...], scale, (pad_top, pad_left)  # batch dim → (1,3,320,320)
```

**Output postprocessing (RT-DETRv2 outputs `pred_boxes` cxcywh-normalized [0,1] in 320x320 space):**
```python
def _decode_boxes(pred_boxes_normalized, scale, pad, orig_hw=(480, 640)):
    """RT-DETRv2 outputs (N, 4) [cx, cy, w, h] normalized to [0,1] in 320x320 space.
    Convert to (N, 4) [x0, y0, x1, y1] in original 480x640 pixel coords."""
    cxcywh = pred_boxes_normalized * 320.0  # un-normalize to 320x320
    x0 = cxcywh[:, 0] - cxcywh[:, 2] / 2 - pad[1]   # subtract pad_left
    y0 = cxcywh[:, 1] - cxcywh[:, 3] / 2 - pad[0]   # subtract pad_top
    x1 = cxcywh[:, 0] + cxcywh[:, 2] / 2 - pad[1]
    y1 = cxcywh[:, 1] + cxcywh[:, 3] / 2 - pad[0]
    # Reverse letterbox scale
    return np.stack([x0/scale, y0/scale, x1/scale, y1/scale], axis=-1)
```

### D-09 — Per-worker ORT session

Each `DetectorWorker` constructs its own `RTDETRv2Backend` instance (already true via `DetectorRegistry.create()` per worker per `worker_pool.py:159`). Each instance owns its own `ort.InferenceSession`. RAM: ~80 MB session × 2 workers = 160 MB. Within Phase 1 SC#3's +200 MB budget for steady-state RSS growth (the sessions are constructed once, not per-inference, so they're not part of the "growth" budget — they're part of the baseline).

### D-11 — Models dir layout

```
models/
├── .gitkeep
├── README.md                     # documents layout (NEW in Phase 5)
├── rtdetrv2/
│   └── 5650961749fa93567c0d46fc7f43ea4f9e914107/  # RT_DETRV2_SHA
│       ├── pt/                    # HF snapshot intermediate
│       │   ├── config.json
│       │   ├── model.safetensors
│       │   ├── preprocessor_config.json
│       │   └── ...
│       ├── model.onnx             # production runtime artifact
│       ├── config.json
│       └── preprocessor_config.json
└── boxer/
    └── df474128a76ba42b05bc81feca7ac1a53fab41af/  # BOXER_SHA
        ├── boxernet/              # BoxerNet weights
        ├── dinov3/                # DINOv3 ViT-S/16
        └── owlv2/                 # OWLv2-base used internally by BoxeR
```

`.gitignore` already contains `models/` (verified — STATE.md mentions existing `models/orbslam3/` + `models/unitree_go2/` v2.0 conventions). Just add `subprocess_venvs/`.

### D-12 — SHA pinning + offline gate

**Module-level constants (verified in this research session):**
```python
# src/perception/backends/rtdetrv2_backend.py
RT_DETRV2_SHA = "5650961749fa93567c0d46fc7f43ea4f9e914107"  # [VERIFIED: HF API 2026-04-15]
# Last modified upstream: 2025-02-06T18:21:53Z

# src/perception/backends/boxer_backend.py
BOXER_SHA = "df474128a76ba42b05bc81feca7ac1a53fab41af"      # [VERIFIED: GitHub API 2026-04-15]
# Commit date: 2026-04-09T18:31:54Z (active 2026 maintenance — good signal)
```

**Loader kwargs (HF):**
```python
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="PekingU/rtdetr_v2_r18vd",
    revision=RT_DETRV2_SHA,
    local_dir=f"models/rtdetrv2/{RT_DETRV2_SHA}/pt",
    local_dir_use_symlinks=False,  # avoid symlink mess in the artifact dir
)
# At runtime (not download time):
from transformers import AutoConfig
config = AutoConfig.from_pretrained(
    f"models/rtdetrv2/{RT_DETRV2_SHA}/pt",
    local_files_only=True,
)
```

**Offline gate test command:**
```bash
HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
  HF_HOME=/tmp/empty-hf-cache \
  argus --backend yolov11 --headless --frames 1
HF_HUB_OFFLINE=1 ... argus --backend rtdetrv2 --headless --frames 1
HF_HUB_OFFLINE=1 ... argus --backend boxer --headless --frames 1
```
All three should boot without network. The `HF_HOME=/tmp/empty-hf-cache` extra env var is critical — without it, a stale `~/.cache/huggingface/hub` could mask a real offline failure.

### D-13 — Makefile + download_models.py contract

**File:** `Makefile` (new, repo root):
```makefile
.PHONY: download-models download-models-rtdetrv2 download-models-boxer

download-models: download-models-rtdetrv2 download-models-boxer

download-models-rtdetrv2:
	uv run python scripts/download_models.py --backend rtdetrv2

download-models-boxer:
	bash scripts/setup_boxer_subprocess.sh
```

**File:** `scripts/download_models.py` (new). Function signatures:
```python
def main() -> int: ...

def download_rtdetrv2(target_dir: Path, sha: str) -> None:
    """1. snapshot_download(revision=sha) → target_dir/pt/
       2. optimum.exporters.onnx.main_export(...) → target_dir/model.onnx
       3. verify sha256 of model.onnx (after first run, store in MANIFEST_SHA256)
       4. on any exception, shutil.rmtree(target_dir) and re-raise (rollback)
    """

def download_boxer(*args) -> None:
    """For symmetry — but actually delegates to setup_boxer_subprocess.sh because
    BoxeR weight fetch runs inside subprocess venv. main() may shell out:
        subprocess.run(["bash", "scripts/setup_boxer_subprocess.sh"], check=True)
    """

# sha256 manifest (committed to repo)
EXPECTED_SHA256 = {
    "models/rtdetrv2/<SHA>/model.onnx": "<computed first run>",
    # boxer artifacts: filled after first download, then locked
}
```

**Rollback behavior on partial failure:** if any step within `download_rtdetrv2` raises after creating the target dir, finally-block does `shutil.rmtree(target_dir, ignore_errors=False)`. User sees a clean re-runnable state. SHOULD log the partial paths cleaned up.

### D-14 — LICENSES.md schema

**File:** `LICENSES.md` (new, repo root). See dedicated section §LICENSES.md Schema below for the full table.

---

# RT-DETRv2 Technical Reference

| Property | Value | Source |
|----------|-------|--------|
| HF repo | `PekingU/rtdetr_v2_r18vd` | [VERIFIED: HF API call 2026-04-15] |
| Pinned SHA | `5650961749fa93567c0d46fc7f43ea4f9e914107` | [VERIFIED: api.huggingface.co/api/models/PekingU/rtdetr_v2_r18vd] |
| Last modified | 2025-02-06T18:21:53Z | [VERIFIED: same] |
| Model class | `RTDetrV2ForObjectDetection` | [VERIFIED: model card via WebFetch 2026-04-15] |
| Image processor | `RTDetrImageProcessor` | [VERIFIED: model card] |
| Param count | 20.2M (F32, safetensors) | [VERIFIED: model card] |
| License | Apache-2.0 | [CITED: HF model card standard for PekingU/rtdetr_v2_*] |
| Paper | arxiv:2407.17140 | [VERIFIED: model card] |

**Preprocessing (CRITICAL — verify in Wave 0):**
RT-DETR/RT-DETRv2 family uses `do_rescale=True` (`/255`) ONLY by default. **NO** ImageNet mean/std subtraction. This is documented in `RTDetrImageProcessor` source. `[CITED: github.com/huggingface/transformers transformers/models/rt_detr/image_processing_rt_detr.py — defaults: do_rescale=True (rescale_factor=1/255), do_normalize=False]`. **Wave 0 task MUST cat the actual `preprocessor_config.json` from the snapshot to confirm** — if `do_normalize=true` with mean/std present, the backend MUST apply those.

**Output tensor decoding:**
- Output names: `logits` (N_queries, 80 COCO classes) and `pred_boxes` (N_queries, 4 cxcywh in [0,1])
- Decode: argmax over last dim of `logits` for class_id; sigmoid → score; pred_boxes are normalized to [0,1] in the **320×320 letterboxed canvas** (not original 480×640) — letterbox-reverse must be applied per D-08 decoder snippet above.
- Default N_queries: 300. Filter by score threshold (default 0.5 — same as YOLOv11Backend).

**ONNX export verification (Wave 0 spike script):**
```bash
uv run python -c "
import onnx
m = onnx.load('models/rtdetrv2/5650961.../model.onnx')
print([(i.name, [d.dim_value for d in i.type.tensor_type.shape.dim]) for i in m.graph.input])
print([(o.name, [d.dim_value for d in o.type.tensor_type.shape.dim]) for o in m.graph.output])
"
# Expected:
#  inputs: [('pixel_values', [1, 3, 320, 320])]
#  outputs: [('logits', [1, 300, 80]), ('pred_boxes', [1, 300, 4])]
```

**CPU latency benchmark (assumed):**
Training-data estimate: 70–120 ms/frame at 320×320 on a modern x86_64 (i7/i9 single-thread). `[ASSUMED — verify in Wave 0 with a 100-iteration smoke benchmark on the dev machine]`. SC#1 budget is "≥3 FPS on default MuJoCo scene" = ≤333 ms/frame end-to-end (detector + lifter + IPC). Comfortable margin.

**Warmup cost:** session creation + first inference on CPU is typically 2–5 s for a 20M-param ONNX model. Within SC#1's 30 s warmup window.

---

# BoxeR Subprocess Technical Reference

| Property | Value | Source |
|----------|-------|--------|
| GitHub repo | `facebookresearch/boxer` | [VERIFIED: WebFetch 2026-04-15] |
| Pinned SHA | `df474128a76ba42b05bc81feca7ac1a53fab41af` | [VERIFIED: api.github.com/repos/facebookresearch/boxer/commits/main 2026-04-15] |
| Commit date | 2026-04-09T18:31:54Z | [VERIFIED: same — recent 2026 activity confirms repo health] |
| Default branch | `main` | [VERIFIED: WebFetch] |
| Build system | `pyproject.toml` (uv-friendly, NOT requirements.txt) | [VERIFIED: WebFetch] |
| Required Python | **3.12** | [VERIFIED: WebFetch — repo recommends `python3.12 -m venv`] |
| License | **CC-BY-NC** (NOTICE file may carve out subparts) | [VERIFIED: WebFetch] |
| Entry point | `run_boxer.py` (headless detection + lifting) | [VERIFIED: WebFetch] |
| Output format | `boxer_3dbbs.csv` per-frame, plus tracked/fused MP4s | [VERIFIED: WebFetch] |
| Dependencies | `torch>=2.0, numpy, opencv-python, tqdm, dill` + optional Aria/3D-viz | [VERIFIED: WebFetch] |
| Checkpoints | BoxerNet + DinoV3 + OWLv2, fetched by `download_ckpts.sh` to `ckpts/` | [VERIFIED: WebFetch] |

**Worker script structure (`scripts/boxer_worker.py`):**
```python
#!/usr/bin/env python3
"""BoxeR ZMQ PAIR worker — runs INSIDE subprocess_venvs/boxer/ Python.

Replaces scripts/echo_detector_worker.py for Phase 5. Same wire protocol (D-17 +
Phase 5 D-02 boxes_3d extension). Loads BoxeR models on startup, holds them in
memory, replies with 3D OBBs natively (no in-process lifter).
"""
import argparse, sys, time, msgpack, zmq, numpy as np

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zmq", required=True)
    args = ap.parse_args()

    # --- Load BoxeR (heavy, takes 5-15 s) ---
    sys.path.insert(0, str(Path(__file__).parent.parent / "subprocess_venvs/boxer/repo"))
    from boxer.model import load_boxer_pipeline  # exact name TBD per Wave 0 spike
    pipeline = load_boxer_pipeline(
        ckpts_dir=Path(__file__).parent.parent / f"models/boxer/{BOXER_SHA}",
        device="cpu",
    )

    # --- Connect ZMQ AFTER weight load (acts as readiness signal) ---
    ctx = zmq.Context()
    sock = ctx.socket(zmq.PAIR)
    sock.connect(args.zmq)

    try:
        while True:
            parts = sock.recv_multipart()
            header = msgpack.unpackb(parts[0], raw=False)
            H, W = header["rgb_shape"][0], header["rgb_shape"][1]
            rgb = np.frombuffer(parts[1], dtype=np.uint8).reshape(H, W, 3)
            depth = None
            if header["depth_shape"] is not None:
                depth = np.frombuffer(parts[2], dtype=np.float32).reshape(*header["depth_shape"])

            t0 = time.perf_counter()
            out = pipeline(rgb=rgb, depth=depth, params=header.get("params", {}))
            inference_ms = (time.perf_counter() - t0) * 1000.0

            reply = {
                "ts": header["ts"],
                "inference_ms": inference_ms,
                "n_det": len(out.boxes_3d),
                "classes": [int(b.class_id) for b in out.boxes_3d],
                "scores": [float(b.score) for b in out.boxes_3d],
                "bboxes": [list(map(float, b.bbox_2d)) for b in out.boxes_3d],
                "boxes_3d": [
                    {"tx": float(b.center[0]), "ty": float(b.center[1]), "tz": float(b.center[2]),
                     "qx": float(b.quat[0]), "qy": float(b.quat[1]),
                     "qz": float(b.quat[2]), "qw": float(b.quat[3]),
                     "w": float(b.extent[0]), "h": float(b.extent[1]), "d": float(b.extent[2])}
                    for b in out.boxes_3d
                ],
            }
            sock.send(msgpack.packb(reply))
    except (KeyboardInterrupt, zmq.ContextTerminated):
        pass
    finally:
        sock.close(linger=0)
        ctx.term()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**3D OBB output decoding caveats:**
- BoxeR's 3D box convention is `(center, extents, R_world_box)` per STACK.md research. `R_world_box` is a 3×3 matrix; worker MUST convert to xyzw quaternion via `scipy.spatial.transform.Rotation.from_matrix(R).as_quat()` (returns xyzw by default — matches D-02 wire). Subprocess venv has scipy via BoxeR deps.
- `extent` is FULL extent per D-02 (composer divides by 2 for `OrientedBox3D.half_extents`).
- `bbox_2d` for the 2D companion box: BoxeR internally runs OWLv2 which produces 2D first; the worker should harvest these from the pipeline's intermediate representation. If BoxeR doesn't expose `bbox_2d` cleanly, fall back to projecting the 3D OBB corners through camera intrinsics — Wave 0 spike to determine. If neither works, return empty `bboxes` list and accept that CameraFeed won't show 2D overlay for BoxeR (degrades gracefully — the Three.js OBB is the primary visualization).

**CPU latency estimate:** STACK.md research § "facebook/BoxeR" reports 5–30 s/frame on pure CPU (vs ~1.3 s/frame Apple MPS). `[ASSUMED — needs Wave 0 confirmation on dev machine]`. SC#2 has no FPS budget — only "warmup completes" and "OBBs appear within first few frames." So even 30 s/frame is acceptable.

**moderngl / headless caveats:**
- BoxeR's interactive viewer extras (`moderngl`, `moderngl-window`, `imgui-bundle`) are explicitly excluded by STACK.md ("install only inside the subprocess worker's venv if interactive BoxeR visualisation is ever wanted (it's not)").
- If `pyproject.toml` of BoxeR pulls `moderngl` as a hard dep (unlikely — should be optional extra), set `EGL_PLATFORM=surfaceless` env var in `setup_boxer_subprocess.sh` before running anything that imports moderngl. Wave 0 spike: try `uv pip install -e $BOXER_REPO --no-deps` then add minimal deps explicitly; if hard moderngl dep, install xvfb/`mesa-utils` on the dev machine OR use `EGL_PLATFORM=surfaceless` env to avoid X11.
- **Verify in Wave 0:** does headless `python -c "import boxer.model"` succeed without DISPLAY? If yes, no xvfb needed.

**Python 3.12 compatibility:** [VERIFIED: WebFetch — BoxeR README explicitly recommends `python3.12 -m venv`]. The main repo's `>=3.10,<3.13` range covers this — main venv on 3.10/3.11/3.12 is fine; subprocess venv MUST be 3.12.

---

# Msgpack Schema Extension (D-02) Reference

See **D-02 implementation notes** above for the full schema dump. Migration-safety summary:

| Existing consumer | Reads which keys | Phase 5 effect |
|-------------------|------------------|----------------|
| `scripts/echo_detector_worker.py` | Sends original 6 keys; never reads `boxes_3d` | None — still passes Phase 2 handshake test |
| `tests/perception/test_subprocess_bridge_skeleton.py` | Asserts on `n_det == 0` from echo | None — echo unchanged |
| `tests/perception/test_subprocess_bridge.py` | Tests transport, not detection schema | None |
| `BoxeRBackend` composer (NEW Phase 5) | Reads `boxes_3d` if present | Drives Phase 5 OBB pipeline |

**No Phase 2 consumer is broken.** New optional key + new consumer = additive, safe.

---

# Crash Fallback Pattern Mirror (D-03)

**Source pattern (verified in-tree):**
File: `src/exploration/exploration_loop.py` lines 207–234.

```python
# SLAM precedent — Phase 5 mirrors this for detector
if (result.tracking_status.value == "lost"
        and hasattr(self._slam, '_bridge')
        and self._streaming_viz is not None
        and hasattr(self._streaming_viz, '_message_queue')):
    backend_name = type(self._slam).__name__
    self._streaming_viz._message_queue.append({
        "type": "crash_fallback",
        "payload": {
            "subsystem": "slam",
            "crashed_backend": backend_name,
            "fallback_backend": "icp",
        },
    })
    # Swap to fallback — pool/registry pattern
    try:
        from src.slam.registry import SLAMRegistry
        import src.slam.backends  # noqa: F401
        fallback_kwargs = {}
        if self._intrinsics is not None:
            fallback_kwargs["intrinsics"] = self._intrinsics
        self._slam = SLAMRegistry.create("icp", **fallback_kwargs)
        logger.info("Swapped crashed %s to ICP fallback", backend_name)
    except Exception as exc:
        logger.error("Failed to create ICP fallback: %s", exc)
```

**Phase 5 parallel (in `src/perception/worker_pool.py::on_backend_crash`):**
```python
def on_backend_crash(self, crashed_backend: str, reason: str) -> None:
    """Mirror of exploration_loop.py:207 SLAM crash pattern (D-03).

    Triggered by per-worker exception handler when bridge.send_frame raises
    BridgeHangError or SubprocessDiedError.
    """
    if self._streaming_viz is not None and hasattr(self._streaming_viz, "_message_queue"):
        self._streaming_viz._message_queue.append({
            "type": "crash_fallback",
            "payload": {
                "subsystem": "detector",
                "crashed_backend": crashed_backend,
                "fallback_backend": "yolov11",
                "reason": reason,
            },
        })
    DetectorRegistry.set_available(crashed_backend, False, reason=reason)  # D-04
    try:
        import src.perception.backends  # noqa: F401
        new_workers_detector = {}
        for rid in self._workers:
            d = DetectorRegistry.create("yolov11")  # per-worker instance separation
            d.warmup(self._dummy_frame_for(rid))    # synchronous warmup before swap
            new_workers_detector[rid] = d
        with self._swap_lock:
            for rid, w in self._workers.items():
                w._detector = new_workers_detector[rid]
            self.backend_name = "yolov11"
        logger.info("Swapped crashed %s to YOLOv11 fallback", crashed_backend)
    except Exception as exc:
        logger.error("Failed to create YOLOv11 fallback: %s", exc)
```

**Error type origins:**
- `BridgeHangError` — raised in `subprocess_bridge.py::send_frame` after `zmq.Again` timeout (currently logs + returns None at line 199–204; Phase 5 changes return None → raise BridgeHangError).
- `SubprocessDiedError` — raised when `Popen.poll() != None` (currently line 167–172 returns None; Phase 5 changes to raise) OR when `zmq.ZMQError` path triggers (line 205–208).

**Worker invocation site** (in `src/perception/worker.py`, presumably the `_loop` or `process` method that calls `self._detector.process_frame`):
```python
try:
    detections_2d = self._detector.process_frame(frame)
except (BridgeHangError, SubprocessDiedError) as exc:
    if self._pool_ref is not None:
        self._pool_ref.on_backend_crash(
            crashed_backend=type(self._detector).__name__,
            reason=str(exc),
        )
    return  # skip this frame; next frame uses swapped detector
```

---

# Models Directory + Pinning Layout (D-11, D-12)

See **D-11** and **D-12** sections above for full tree + constants.

**SHA constant naming convention** (single source of truth, exported from each backend module):
```python
# src/perception/backends/rtdetrv2_backend.py
RT_DETRV2_SHA: str = "5650961749fa93567c0d46fc7f43ea4f9e914107"
RT_DETRV2_REPO: str = "PekingU/rtdetr_v2_r18vd"
RT_DETRV2_MODEL_DIR: Path = Path("models") / "rtdetrv2" / RT_DETRV2_SHA

# src/perception/backends/boxer_backend.py
BOXER_SHA: str = "df474128a76ba42b05bc81feca7ac1a53fab41af"
BOXER_REPO_URL: str = "https://github.com/facebookresearch/boxer"
BOXER_MODEL_DIR: Path = Path("models") / "boxer" / BOXER_SHA
```

`scripts/download_models.py` imports these constants — no duplication of the literal SHA strings anywhere.

---

# Makefile + download_models.py Contract (D-13)

**Makefile (already shown in D-13 section above).** Three targets, `download-models` aggregates.

**`scripts/download_models.py` complete signature:**
```python
"""Pre-fetch every checkpoint to ./models/ for offline + CI (D-13).

Usage:
    uv run python scripts/download_models.py --backend rtdetrv2
    uv run python scripts/download_models.py --backend boxer
    uv run python scripts/download_models.py --all
"""
from __future__ import annotations
import argparse, hashlib, shutil, subprocess, sys
from pathlib import Path

from src.perception.backends.rtdetrv2_backend import RT_DETRV2_SHA, RT_DETRV2_REPO, RT_DETRV2_MODEL_DIR

EXPECTED_SHA256: dict[str, str] = {
    # Filled empirically after first successful download. CI re-verifies.
    # Format: "models/rtdetrv2/<SHA>/model.onnx": "<sha256 hex>"
}

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_or_record(path: Path) -> None:
    """If EXPECTED_SHA256 has an entry for path, raise if mismatch.
    Otherwise compute + log the sha so the developer can pin it."""
    rel = str(path)
    actual = sha256_of(path)
    expected = EXPECTED_SHA256.get(rel)
    if expected is None:
        print(f"[NEW SHA] {rel}: {actual}  # add to EXPECTED_SHA256 to lock")
        return
    if expected != actual:
        raise RuntimeError(f"sha256 mismatch for {rel}\n  expected {expected}\n  actual   {actual}")

def download_rtdetrv2() -> None:
    target = RT_DETRV2_MODEL_DIR
    target.mkdir(parents=True, exist_ok=True)
    pt_dir = target / "pt"
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=RT_DETRV2_REPO,
            revision=RT_DETRV2_SHA,
            local_dir=str(pt_dir),
            local_dir_use_symlinks=False,
        )
        from optimum.exporters.onnx import main_export
        main_export(
            model_name_or_path=str(pt_dir),
            output=target,
            task="object-detection",
            input_shapes={"pixel_values": [1, 3, 320, 320]},
            monolith=True,
            no_post_process=True,
        )
        verify_or_record(target / "model.onnx")
    except Exception:
        # Rollback per D-13: remove partial dir
        if target.exists():
            shutil.rmtree(target)
        raise

def download_boxer() -> None:
    """Delegate to setup_boxer_subprocess.sh — BoxeR weight fetch needs subprocess venv."""
    script = Path(__file__).parent / "setup_boxer_subprocess.sh"
    subprocess.run(["bash", str(script)], check=True)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["rtdetrv2", "boxer"])
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all or args.backend == "rtdetrv2":
        download_rtdetrv2()
    if args.all or args.backend == "boxer":
        download_boxer()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Rollback behavior:** `try/except + shutil.rmtree(target)` in `download_rtdetrv2`. For BoxeR, `setup_boxer_subprocess.sh` should mirror this — if any step after `mkdir -p` fails, `trap 'rm -rf "$VENV_DIR"' ERR` at script top.

---

# LICENSES.md Schema (D-14)

**File:** `LICENSES.md` (new, repo root). Format: GitHub-flavored markdown table.

```markdown
# Third-Party License Inventory

This document tracks SPDX identifiers and license obligations for every
runtime dependency in argus. The table is the source of truth — DO NOT add
a runtime dependency without updating this file.

## Runtime Dependencies

| Dep | SPDX | Scope | Upstream | Note |
|-----|------|-------|----------|------|
| Ultralytics YOLOv11 | AGPL-3.0 | Default detector backend (in-process) | https://github.com/ultralytics/ultralytics | **Copyleft** — distributing this codebase as a service triggers AGPL network-use clause. Document in deployment guide. |
| RT-DETRv2 (PekingU) | Apache-2.0 | Real-time transformer backend (in-process ONNX) | https://huggingface.co/PekingU/rtdetr_v2_r18vd | Permissive |
| facebook/BoxeR | **CC-BY-NC-4.0** | Reference-quality 3D OBB backend (subprocess) | https://github.com/facebookresearch/boxer | **Non-commercial only — research/academic use.** Capability dict surfaces this in the UI per D-14. NOT for production deployments. |
| DINOv3 (facebook) | DINOv3 License (research-only) | BoxeR feature backbone, downloaded inside subprocess venv | https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m | Coupled with BoxeR's NC restriction. |
| OWLv2 (google) | Apache-2.0 | BoxeR's internal 2D detector (used inside subprocess venv) | https://huggingface.co/google/owlv2-base-patch16-ensemble | Permissive — but only loaded indirectly via BoxeR; not a directly selectable backend. |
| ONNX Runtime | MIT | RT-DETRv2 inference engine | https://github.com/microsoft/onnxruntime | Permissive |
| Hugging Face Transformers | Apache-2.0 | Model loading + RT-DETRv2 export | https://github.com/huggingface/transformers | Permissive |
| huggingface-hub | Apache-2.0 | Snapshot download for pinned checkpoints | https://github.com/huggingface/huggingface_hub | Permissive |
| optimum (HF) | Apache-2.0 | ONNX export tooling (dev-only, not runtime) | https://github.com/huggingface/optimum | Permissive |
| msgpack-python | Apache-2.0 | Subprocess bridge wire encoding | https://github.com/msgpack/msgpack-python | Permissive |
| pyzmq | LGPL-3.0+BSD-3-Clause | Subprocess bridge transport | https://github.com/zeromq/pyzmq | LGPL implications via dynamic linking — accepted (we link against libzmq, do not vendor it). |
| Open3D | MIT | 3D OBB lifter + geometry | https://github.com/isl-org/Open3D | Permissive |
| PyTorch | BSD-3-Clause | Tensor runtime for YOLOv11 + (in subprocess) BoxeR | https://github.com/pytorch/pytorch | Permissive |
| numpy / scipy / opencv-python-headless / Pillow | BSD-3 / BSD / Apache-2.0 / MIT-CMU | Standard scientific Python stack | https://numpy.org / https://scipy.org / https://opencv.org / https://python-pillow.org | Permissive |
| MuJoCo | Apache-2.0 (since 2.1.5) | Simulation engine | https://github.com/google-deepmind/mujoco | Permissive |
| FastAPI / uvicorn / websockets | MIT / BSD-3 / BSD-3 | Web/coordination layer | https://github.com/tiangolo/fastapi | Permissive |

## NC Compliance Mechanism

facebook/BoxeR is CC-BY-NC-4.0. argus surfaces this in the UI:
- `BoxeRBackend.CAPABILITIES["license"] = "CC-BY-NC-4.0"` is rendered as a pill
  in the Detector Dropdown (Phase 3 D-05 capability badge path).
- Users see the NC restriction inline before selecting BoxeR — no extra modal.

## Audit checklist

- [ ] Every entry in `pyproject.toml [dependencies]` and `[optional-dependencies]` appears here.
- [ ] Every model checkpoint downloaded by `make download-models` has its license documented.
- [ ] CC-BY-NC and AGPL deps are surfaced in the UI via capability dict.
```

**Sources for license claims:** Most are HIGH-confidence from official SPDX of well-known projects. `[VERIFIED: WebFetch — BoxeR repo NOTICE/LICENSE files state CC-BY-NC]`. DINOv3 license is a Meta research license (not standard SPDX); planner's task to include it should grep BoxeR's `download_ckpts.sh` for any license metadata it pulls.

---

# Validation Architecture

> Required header per nyquist_validation flag (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) + pytest-asyncio + pytest-timeout (already in `dev` extra) |
| Config file | none top-level — pytest uses defaults; tests live in `tests/perception/`, `tests/integration/` |
| Quick run command | `uv run pytest tests/perception/test_<module>.py::test_<name> -x --timeout=30` |
| Full suite command | `uv run pytest tests/ -x --timeout=300 -m "not slow"` |
| Slow-marked tests | tests requiring real BoxeR subprocess: marker `@pytest.mark.slow_boxer` (skip by default; CI runs nightly) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-MODELS-02 | RT-DETRv2 backend loads, processes 480×640 frame, returns Detections2D | unit | `uv run pytest tests/perception/test_rtdetrv2_backend.py -x` | ❌ Wave 0 |
| DET-MODELS-02 | RT-DETRv2 inference ≤250 ms/frame at 320×320 (P95 across 30 inferences) | smoke | `uv run pytest tests/perception/test_rtdetrv2_backend.py::test_latency_p95_under_250ms` | ❌ Wave 0 |
| DET-MODELS-03 | BoxeRBackend constructor doesn't spawn subprocess (D-05 lazy spawn) | unit | `uv run pytest tests/perception/test_boxer_backend.py::test_construct_no_spawn` | ❌ Wave 0 |
| DET-MODELS-03 | BoxeRBackend.warmup() spawns subprocess via SubprocessDetectorBridge, returns 3D OBBs | integration | `uv run pytest tests/perception/test_boxer_backend.py::test_warmup_returns_3d -m slow_boxer` | ❌ Wave 0 |
| DET-MODELS-03 | BoxeR composer correctly halves extents (full→half) | unit | `uv run pytest tests/perception/test_boxer_backend.py::test_extent_halving` | ❌ Wave 0 |
| DET-MODELS-03 | Msgpack reply schema accepts boxes_3d additive field without breaking Phase 2 echo test | unit | `uv run pytest tests/perception/test_subprocess_bridge_skeleton.py -x` (existing — still green) | ✅ |
| DET-MODELS-06 | bridge.send_frame raises BridgeHangError on RCVTIMEO | unit | `uv run pytest tests/perception/test_crash_fallback.py::test_bridge_hang_raises` | ❌ Wave 0 |
| DET-MODELS-06 | bridge.send_frame raises SubprocessDiedError when Popen exited | unit | `uv run pytest tests/perception/test_crash_fallback.py::test_subprocess_died_raises` | ❌ Wave 0 |
| DET-MODELS-06 | DetectorWorkerPool.on_backend_crash emits crash_fallback message + swaps to YOLOv11 | unit | `uv run pytest tests/perception/test_crash_fallback.py::test_pool_swaps_to_yolo` | ❌ Wave 0 |
| DET-MODELS-06 | end-to-end: kill -9 worker → CrashToast WS message arrives within 5s | integration | `uv run pytest tests/integration/test_boxer_crash_fallback.py -m slow_boxer --timeout=30` | ❌ Wave 0 |
| DET-MODELS-07 | scripts/download_models.py downloads RT-DETRv2 to models/rtdetrv2/<SHA>/ | integration | `uv run pytest tests/integration/test_download_models.py::test_download_rtdetrv2 -m network` | ❌ Wave 0 |
| DET-MODELS-07 | scripts/setup_boxer_subprocess.sh is idempotent (.ready short-circuit) | integration | `uv run pytest tests/integration/test_download_models.py::test_setup_boxer_idempotent -m network` | ❌ Wave 0 |
| DET-MODELS-07 | Coordinator boots all 3 backends with HF_HUB_OFFLINE=1 after make download-models | integration | `uv run pytest tests/integration/test_offline_boot.py -m slow_boxer --timeout=120` | ❌ Wave 0 |
| DET-MODELS-08 | LICENSES.md exists, contains BoxeR CC-BY-NC-4.0 row, AGPL/Apache/MIT entries for 3 backends + ORT | unit | `uv run pytest tests/test_licenses_md.py::test_boxer_cc_by_nc_present` | ❌ Wave 0 |
| DET-MODELS-08 | BoxeRBackend.CAPABILITIES["license"] == "CC-BY-NC-4.0" | unit | `uv run pytest tests/perception/test_boxer_backend.py::test_capability_license` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/perception/test_<the_one_file_just_changed>.py -x --timeout=30` (≤30 s)
- **Per wave merge:** `uv run pytest tests/perception/ tests/integration/ -x --timeout=300 -m "not slow_boxer and not network"` (≤2 min)
- **Phase gate:** `uv run pytest tests/ -x --timeout=600` plus manual exercise of SC#3 (`kill -9 <boxer-pid>` from a running coordinator and observe CrashToast)

### Wave 0 Gaps

- [ ] `tests/perception/test_rtdetrv2_backend.py` — covers DET-MODELS-02
- [ ] `tests/perception/test_boxer_backend.py` — covers DET-MODELS-03 (composer)
- [ ] `tests/perception/test_crash_fallback.py` — covers DET-MODELS-06 (unit-level pool + bridge exceptions)
- [ ] `tests/integration/test_boxer_crash_fallback.py` — covers DET-MODELS-06 e2e (slow_boxer marker)
- [ ] `tests/integration/test_download_models.py` — covers DET-MODELS-07 (network marker)
- [ ] `tests/integration/test_offline_boot.py` — covers DET-MODELS-07 offline gate
- [ ] `tests/test_licenses_md.py` — covers DET-MODELS-08
- [ ] `tests/perception/fixtures/sample_480x640_with_chair.npz` — RGB+depth fixture for backend smoke (or reuse existing `tests/perception/fixtures/`)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` markers section — register `slow_boxer` and `network` markers to silence pytest-warnings
- [ ] `pyproject.toml [project.optional-dependencies].dev` — add `optimum[exporters]>=1.20.0` (required by download tests when network is available)
- [ ] `pyproject.toml [project.optional-dependencies].perception` — add `onnxruntime>=1.19.0`

---

# Security Domain

> Included per `security_enforcement` default (no explicit `false` in config).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local-only IPC; no auth surface added |
| V3 Session Management | no | No new sessions |
| V4 Access Control | no | Local single-user dev tool |
| V5 Input Validation | yes | msgpack `strict_map_key=True, raw=False` (already enforced Phase 2 line 197); JSON schema for PARAMETER_SCHEMA |
| V6 Cryptography | yes (transitively) | sha256 verification of downloaded checkpoints (D-13 manifest) — never hand-roll; use stdlib hashlib |
| V12 File and Resources | yes | Path traversal in `models/<backend-slug>/<sha>/...` — slug + sha are module constants, not user input → safe |
| V14 Configuration | yes | `HF_HUB_OFFLINE=1` env-var enforcement; `local_files_only=True` HF kwarg |

### Known Threat Patterns for Phase 5 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess command injection in `setup_boxer_subprocess.sh` | Tampering | All path args are repo-relative literals; no user input flows into the script. Guarded. |
| Msgpack deserialization of untrusted payload from worker | Tampering | Phase 2 already hardened: `strict_map_key=True, raw=False` rejects non-string keys + auto-decodes bytes. Worker is local subprocess we spawn; trust boundary is the subprocess venv. |
| Checkpoint poisoning (malicious HF model) | Tampering | `revision=RT_DETRV2_SHA` pins immutable commit; `local_files_only=True` after first fetch; sha256 manifest verifies model.onnx integrity at download time. |
| ZMQ socket squatting | Tampering | Phase 2's `ipc:///tmp/detector_bridge_<pid>_<id(self)>` (line 87) is unique per bridge instance; cleanup unlinks on shutdown (line 258–264). Distinct prefix from SLAM bridge (D-16). |
| Resource exhaustion via unbounded Popen output | DoS | `subprocess.PIPE` for stdout/stderr (line 135–137) — eventually fills OS pipe buffer and worker blocks. **Mitigation gap:** Phase 5 should drain worker stdout/stderr in a background thread or set `stdout=subprocess.DEVNULL` after a one-shot stderr capture for crash diagnostics. Wave 0 task. |
| Path traversal in models/ dir | Tampering | All paths constructed from module constants (RT_DETRV2_SHA, BOXER_SHA) — not user-controlled. Safe. |

**ASVS L1 verification gates:**
- [V5.1] msgpack ingress hardening: covered by Phase 2 invariant + new test on extended schema (`tests/perception/test_subprocess_bridge.py` — verify `boxes_3d` with non-str key in inner dict is rejected).
- [V6.2] Cryptographic checksum verification: `EXPECTED_SHA256` manifest in `download_models.py`.
- [V12.3] Path canonicalization: `Path(...) / sha / artifact` pattern; no string concatenation of user input.

---

# Wave Structure Recommendation

**Goal:** Maximum parallelism. Independent files in same wave; sequential waves where state/file depends.

### Wave 0 — Scaffolding + tests + dependency injection
Parallel, no inter-task dependencies:
- Plan A: `pyproject.toml` — add `onnxruntime>=1.19.0` to perception extra, `optimum[exporters]>=1.20.0` to dev extra; add `slow_boxer` + `network` pytest markers
- Plan B: `LICENSES.md` (new, repo root)
- Plan C: `models/.gitkeep` + `models/README.md` + `.gitignore` add `subprocess_venvs/`
- Plan D: `Makefile` (new, repo root) + `scripts/download_models.py` (skeleton with TODOs for real downloads)
- Plan E: Wave 0 test files SCAFFOLDS (no real assertions yet — just imports + pytest.skip stubs):
  `tests/perception/test_rtdetrv2_backend.py`, `tests/perception/test_boxer_backend.py`, `tests/perception/test_crash_fallback.py`, `tests/integration/test_download_models.py`, `tests/integration/test_offline_boot.py`, `tests/integration/test_boxer_crash_fallback.py`, `tests/test_licenses_md.py`
- Plan F: Spike — extend `src/_thread_config.py` with `def get_default_budget() -> int: return _DEFAULT_BUDGET` public getter (1-line + test). Allows Plan I (Wave 2) to read budget without touching private constant.

**Wave 0 gate:** All scaffolds compile; existing test suite still green.

### Wave 1 — Bridge schema extension + BoxeR worker + setup script + registry helper
Parallel:
- Plan G: `src/perception/subprocess_bridge.py` — extend module docstring with new schema, define `BridgeHangError` and `SubprocessDiedError` exceptions, change `send_frame` to raise instead of returning None on the two failure paths. Update `tests/perception/test_subprocess_bridge*.py` accordingly. Add stdout/stderr drain thread (security mitigation).
- Plan H: `scripts/boxer_worker.py` (new) — full worker script per template above. Wave 0 spike must have settled BoxeR's pipeline import path.
- Plan I: `scripts/setup_boxer_subprocess.sh` (new) — full bash script per D-01 skeleton above.
- Plan J: `src/perception/registry.py` — add `set_available()` classmethod (D-04). Update `list_backends()` to honor override. Tests at `tests/perception/test_registry.py`.

**Wave 1 gate:** Bridge tests green with new exceptions; setup script idempotent test passes (offline-mocked); registry override test passes.

### Wave 2 — Backends + pool crash handler
- Plan K: `src/perception/backends/rtdetrv2_backend.py` (new) — full impl per RT-DETRv2 Technical Reference. Depends on Wave 0 Plan F (`get_default_budget`).
- Plan L: `src/perception/backends/boxer_backend.py` (new) — full impl per BoxeR Technical Reference + D-02/D-05 composer. Depends on Wave 1 Plan G (typed exceptions) and Wave 1 Plan H (worker script exists for warmup).
- Plan M: `src/perception/worker_pool.py` — add `on_backend_crash()` per D-03; thread `_streaming_viz` / `_message_queue` ref through `__init__` or setter; update `worker.py` invocation site to catch typed exceptions and call `pool.on_backend_crash()`. Depends on Wave 1 Plan G + Plan J (set_available).

**Wave 2 gate:** Both backends instantiate; RT-DETRv2 unit test green (after `make download-models-rtdetrv2`); BoxeR unit test green (composer logic with mocked bridge); pool crash unit test green.

### Wave 3 — Frontend wiring + Integration tests + main.py registration
- Plan N: `frontend/src/hooks/useWebSocket.ts:188-203` — replace console.log placeholder for `subsystem === 'detector'` with real `useDetectorStore.getState().setCrashMessage(...)` + `setActive('yolov11', ...)` calls (4-line edit).
- Plan O: `src/main.py` — import `src.perception.backends.rtdetrv2_backend` and `src.perception.backends.boxer_backend` for side-effect registration (matches Phase 1 pattern). Wire `_streaming_viz` reference into `DetectorWorkerPool` construction.
- Plan P: `scripts/download_models.py` — fill in real download logic per D-13 (replaces Wave 0 skeleton).
- Plan Q: Integration tests — `tests/integration/test_offline_boot.py` (real impl), `tests/integration/test_download_models.py` (real impl), `tests/integration/test_boxer_crash_fallback.py` (`kill -9` exercise).

**Phase gate:** All 5 SCs verified — manual SC#1 (RTDETRv2 dropdown → restart overlay → ≥3 FPS), manual SC#2 (BoxeR dropdown → setup_boxer runs → 3D OBBs), automated SC#3 (test_boxer_crash_fallback), automated SC#4 (test_offline_boot), automated SC#5 (test_licenses_md + test_boxer_capability_license).

---

# Plan Count Estimate

**~12 plans (Plans A–Q with some renumbering).** Concretely:
- Wave 0: 6 plans (A–F)
- Wave 1: 4 plans (G–J)
- Wave 2: 3 plans (K–M)
- Wave 3: 4 plans (N–Q)
- Adjust to single-file plans where reasonable; some plans (e.g., Plan E test scaffolds) might split into 2–3 if granularity is `coarse` per `.planning/config.json` — but coarse means LARGER plans, so keep test scaffolds as one Plan E.

**Realistic range:** 11–14 plans. Lower bound 11 if some Wave 0 items merge (e.g., Makefile + download_models skeleton in one plan). Upper bound 14 if `boxer_backend.py` splits into "constructor + capability" + "warmup + bridge wiring" + "process_frame composer" sub-plans.

---

# Open Risks / Unknowns

1. **BoxeR pipeline import path uncertainty.** The exact `from boxer.X import Y` line in `boxer_worker.py` cannot be determined without inspecting BoxeR's actual code at SHA `df474128...`. **Mitigation:** Wave 0 Plan F should INCLUDE a 30-min spike: `git clone --depth 1 https://github.com/facebookresearch/boxer && git checkout df474128 && python -c "import boxer; help(boxer)"` to find the public surface. If `load_boxer_pipeline` doesn't exist as imagined, fall back to invoking `run_boxer.py` as a CLI subprocess from inside the worker (slower per-frame because of CLI startup, but functionally equivalent — the bridge sees the same wire).

2. **BoxeR moderngl headless dependency.** Whether `EGL_PLATFORM=surfaceless` is sufficient for all BoxeR imports on Linux without DISPLAY is `[ASSUMED — verify in Wave 0 spike]`. If hard X11 dep, add xvfb to dev-machine setup docs OR monkeypatch BoxeR's viz module to no-op imports.

3. **First-call latency vs HANG_TIMEOUT_MS=5000ms.** BoxeR worker takes 5–15 s to load weights; subsequent connect happens before that. The first `bridge.send_frame()` will hang on `recv` for 5 s if the worker isn't ready. **Mitigation:** Either (a) extend `SubprocessDetectorBridge` with a `wait_for_ready(timeout_s=60)` method called from `BoxeRBackend.warmup()` BEFORE the first `send_frame`, or (b) bump bridge's first-call timeout via a kwarg. Recommend (a) — minimal change to bridge, no per-instance timeout state. Wave 1 Plan G should include this.

4. **ORT `MultiScaleDeformableAttention` op coverage.** `[ASSUMED]` — RT-DETRv2's msda op may or may not be supported in onnxruntime 1.19+ CPU EP. **Mitigation:** Wave 2 Plan K includes a hard ORT session-load smoke test as the FIRST assertion. If it fails, fallback path is `monolith=False, no_post_process=False` re-export which decomposes msda into atomic ops. Cost: 2× session memory (encoder + decoder split) but well within budget.

5. **RT-DETRv2 preprocessing config drift.** `[CITED — defaults from upstream source code]` says rescale-only (no mean/std subtract). But the actual `preprocessor_config.json` in the pinned snapshot is the source of truth. **Mitigation:** Wave 2 Plan K's test SHOULD parse the snapshot's `preprocessor_config.json` and assert the backend's preprocessing matches. Drift between code-assumed and actual config will silently produce all-wrong detections.

6. **CC-BY-NC compliance scope.** Whether shipping argus + BoxeR as a "research artifact" violates NC depends on jurisdiction and downstream use. `[ASSUMED]` — the surfacing-via-capability-badge approach is necessary but may not be sufficient legal protection for redistributors. **Mitigation:** Out of scope for Phase 5 implementation; documented as a deployment-time concern in LICENSES.md "NC Compliance Mechanism" section.

7. **DINOv3 license for facebook/dinov3-vits16-pretrain-lvd1689m.** [ASSUMED Apache or research license — the artifact may be Meta-research-license, not Apache.] LICENSES.md has a placeholder; Wave 0 Plan B should curl the HF model page to confirm before committing the LICENSES.md text.

8. **Frontend 4-line edit interpretation.** CONTEXT.md says "Frontend: ZERO changes" but ALSO requires `crashMessage` to populate. Read literally, the existing line 197-202 placeholder is the "shipped" code from Phase 3. Phase 5 changing it is technically a frontend change. **Recommend:** plan as a 4-line edit (Plan N) and document the override of CONTEXT.md "ZERO changes" wording. The user/discuss-phase intent was "no NEW components" — not "no edits anywhere." If reviewer pushes back, alternative is to dispatch the populate call from the WS receiver in a generic fashion already in main bus — but that's MORE intrusive, not less.

9. **`detector_threads = max(2, C // (2 + N_robots))`** — current `_thread_config.py` hardcodes 2 (Phase 1 placeholder). RT-DETRv2 with `intra_op_num_threads=2` may underperform if the dev machine has 8+ cores. `[ASSUMED]` — Wave 2 latency benchmark may show RT-DETRv2 doesn't hit ≤250 ms/frame at intra_op=2. **Mitigation:** if SC#1 fails on CPU latency, raise the issue to discuss-phase; do NOT silently increase the thread budget (Phase 1 D-04 invariant says budget changes flow through `_thread_config`, not through the backend file).

---

# Assumptions Log

> Claims tagged `[ASSUMED]` that need user/Wave 0 confirmation before becoming locked decisions.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | RT-DETRv2-S CPU latency 70–120 ms at 320×320 on modern x86_64 | RT-DETRv2 Technical Reference | If actually 300+ ms, SC#1's "≥3 FPS" budget consumed by inference alone — composer + IPC margin gone |
| A2 | BoxeR CPU latency 5–30 s/frame | BoxeR Technical Reference | If actually 60+ s/frame, BoxeR worker still warmup-blocks the dropdown but per-frame UX unusable; SC#2 still passes (no FPS budget) but user perception is worse |
| A3 | BoxeR has a `load_boxer_pipeline` style public Python API | BoxeR Technical Reference | If only CLI exists, `boxer_worker.py` becomes more complex (CLI subprocess per frame OR forking the codebase); both add Wave 1 work |
| A4 | onnxruntime 1.19+ CPU EP supports MultiScaleDeformableAttention | D-07 / Open Risk #4 | Need monolith=False fallback; +1 day Wave 2 |
| A5 | RT-DETRv2 preprocessing is rescale-only (no mean/std) | D-08 / RT-DETRv2 Technical Reference | All detections silently wrong (low/zero recall); SC#1 fails |
| A6 | DINOv3 ViT-S/16 license permits use under BoxeR's NC umbrella | LICENSES.md Schema | Audit-time concern; not a Phase 5 blocker |
| A7 | EGL_PLATFORM=surfaceless sufficient for headless BoxeR import | BoxeR Technical Reference / Open Risk #2 | Wave 0 spike fails → need xvfb in dev setup docs |
| A8 | bridge first-call timeout 5 s OK after wait_for_ready handshake added | D-05 / Open Risk #3 | If handshake handshake doesn't survive Popen race, BoxeR warmup intermittently fails — SC#2 flaky |

**Empty assumptions log would mean every claim was VERIFIED or CITED. The above 8 are honest gaps the planner must surface as Wave 0 spike tasks BEFORE writing Wave 2 plans.**

---

# Sources

### Primary (HIGH confidence)
- `src/perception/protocol.py`, `src/perception/registry.py`, `src/perception/types.py`, `src/perception/subprocess_bridge.py`, `src/perception/worker_pool.py`, `src/perception/backends/yolov11_backend.py`, `src/_thread_config.py`, `scripts/echo_detector_worker.py`, `src/exploration/exploration_loop.py`, `frontend/src/hooks/useWebSocket.ts`, `pyproject.toml` — direct read 2026-04-15
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-CONTEXT.md` (D-01..D-14 verbatim)
- `.planning/REQUIREMENTS.md` (Phase 5 requirements, OWLv2 dropped)
- `.planning/ROADMAP.md` (Phase 5 SCs post-amendment)
- `.planning/STATE.md`
- `.planning/research/STACK.md`, `.planning/research/SUMMARY.md`
- HF API call: `https://huggingface.co/api/models/PekingU/rtdetr_v2_r18vd` → SHA `5650961749fa93567c0d46fc7f43ea4f9e914107` (verified 2026-04-15)
- GitHub API call: `https://api.github.com/repos/facebookresearch/boxer/commits/main` → SHA `df474128a76ba42b05bc81feca7ac1a53fab41af` (verified 2026-04-15)

### Secondary (MEDIUM confidence)
- `https://huggingface.co/PekingU/rtdetr_v2_r18vd` (model card via WebFetch — confirms architecture, image processor, params, license)
- `https://github.com/facebookresearch/boxer` (repo card via WebFetch — confirms branch, license, deps, Python 3.12, entry point, output format, ckpt script)
- `.planning/research/STACK.md` for BoxeR latency estimate (5–30 s/frame)

### Tertiary (LOW confidence — flagged in Assumptions Log)
- RT-DETRv2 CPU latency at 320×320 (~70–120 ms) — extrapolation from `STACK.md` table, not measured on this dev machine
- ORT 1.19+ msda op support — training-data-derived
- BoxeR `load_boxer_pipeline` public API existence — speculative based on typical research-code shape
- DINOv3 specific license SPDX — needs HF model card check

---

# Metadata

**Confidence breakdown:**
- Locked decisions (D-01..D-14): HIGH — no re-derivation needed, only HOW
- RT-DETRv2 SHA + repo: HIGH — verified live via HF API
- BoxeR SHA + repo: HIGH — verified live via GitHub API
- RT-DETRv2 preprocessing (rescale-only): MEDIUM — defaults from upstream source; Wave 2 Plan K must verify against pinned snapshot's `preprocessor_config.json`
- BoxeR pipeline import path: LOW — Wave 0 spike required
- ORT msda op support: LOW — empirical Wave 2 verification required
- Crash fallback pattern: HIGH — direct mirror of in-tree SLAM precedent
- Wave structure: HIGH — derived from CONTEXT.md "In:" file list + dependency analysis

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (HF SHAs are stable; only re-verify if Phase 5 execution slips >30 days)
