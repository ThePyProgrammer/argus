# Phase 5: second-backends-boxer-rtdetr-owlv2 - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning
**Source:** Discuss-phase deep-dive (4 areas, 16 questions, 14 locked decisions including 1 scope amendment — OWLv2 dropped)

<domain>
## Phase Boundary

Plug in two new detector backends as the pluggability regression test — **BoxeR** in subprocess (3D-native OBBs via Phase 2 `SubprocessDetectorBridge`), **RT-DETRv2-S** in-process ONNX (real-time transformer) — with pinned checkpoints via `make download-models`, warmup-blocking restart overlay, and crash-fallback to YOLOv11 within 5 s. Phase directory slug retains `-owlv2` for git-history stability, but **OWLv2 is DROPPED from Phase 5 scope** (see D-10 + Scope Amendment block below).

**In:**
- `src/perception/backends/rtdetrv2_backend.py` (new) — in-process ONNX backend via `onnxruntime>=1.19.0` CPU EP.
- `src/perception/backends/boxer_backend.py` (new) — in-process composer that owns a `SubprocessDetectorBridge` instance and translates the msgpack reply into `Detections3D` via `OrientedBox3D.to_wire()`.
- `scripts/boxer_worker.py` (new) — the real BoxeR subprocess worker script (supersedes Phase 2's `echo_detector_worker.py` fixture). Runs inside `subprocess_venvs/boxer/` — owns its own torch/DINOv3/BoxerNet/moderngl deps.
- `scripts/setup_boxer_subprocess.sh` (new) — idempotent venv bootstrap: creates `subprocess_venvs/boxer/`, installs BoxeR deps, clones facebook/boxer at pinned SHA, downloads weights via BoxeR's own `download_ckpts.sh`.
- `scripts/download_models.py` (new) — Python downloader invoked by `make download-models`. Handles RT-DETRv2 ONNX export (transformers + optimum) + BoxeR checkpoint fetch.
- `Makefile` (new, root) — thin target list: `download-models`, `download-models-rtdetrv2`, `download-models-boxer`.
- `LICENSES.md` (new, root) — per-dependency SPDX table with BoxeR CC-BY-NC-4.0 entry + upstream link.
- `src/perception/subprocess_bridge.py` — EXTENDED msgpack reply schema (additive — see D-02).
- `src/perception/worker_pool.py::DetectorWorkerPool` — GAINED `on_backend_crash()` handler that catches `BridgeHangError`/`SubprocessDiedError`, emits `crash_fallback` WS message, and swaps the active backend to YOLOv11.
- `pyproject.toml` — `perception` extra adds `onnxruntime>=1.19.0`; `dev` extra adds `optimum[exporters]>=1.20.0` (download-time only).
- Frontend: **ZERO changes** beyond what Phase 3 + Phase 4 already shipped. Capability badges + LifterDropdown auto-visibility + CrashToast + RestartOverlay all already handle new backends generically. BoxeR advertises `outputs_3d_natively=true` → LifterDropdown auto-hidden per Phase 3 D-08.
- Tests: `tests/perception/test_rtdetrv2_backend.py`, `tests/perception/test_boxer_backend.py` (unit + integration with mock bridge), `tests/perception/test_crash_fallback.py` (pool-owned watchdog), `tests/integration/test_download_models.py` (offline boot gate).

**Out:**
- OWLv2 backend (dropped per D-10 — moved to REQUIREMENTS.md Out of Scope; `input_type` capability key in Phase 3 D-05 stays reserved for future milestones).
- Detection metrics (Phase 6 — DET-METRICS-*).
- CrashToast UI changes (Phase 3 already shipped it; Phase 5 only ensures backend emits the WS signal).
- Pipeline-editor nodes (Phase 7).
- Hot-swap detector mid-session (permanently out of scope — v2.0 SLAM precedent).
- Multi-prompt / text-prompt UI (was only needed for OWLv2 — N/A now).

### Scope Amendment (2026-04-15)

User decision during discuss-phase: OWLv2 conflicts with the project's real-time pipeline constraint. A 1–4 s/frame backend in a 30 Hz perception worker degrades the live 3D map without a purpose-built one-shot labeling workflow, which is a separate feature. Amendments executed in this commit:

- `REQUIREMENTS.md` — DET-MODELS-04 moved from "Active" to "Out of Scope" with reason.
- `REQUIREMENTS.md` — Traceability table entry for DET-MODELS-04 removed; coverage recount 42/42 → 41/41.
- `ROADMAP.md` — Phase 5 bullet (L19) updated; Phase 5 goal (L104) drops OWLv2; Phase 5 Requirements list drops DET-MODELS-04; Phase 5 SC#5 (OWLv2-specific) removed; prior SC#6 renumbered → SC#5. Total SCs: 6 → 5.

The phase directory slug `05-second-backends-boxer-rtdetr-owlv2` is NOT renamed — slug is git-history-stable and matches the phase_number/name init contract. The `-owlv2` suffix is historical per PROJECT.md evolution rules.

</domain>

<decisions>
## Implementation Decisions

### BoxeR Subprocess + 3D-OBB Wire (DET-MODELS-03, DET-MODELS-06 partial)

- **D-01 (Venv + setup layout):** BoxeR subprocess venv lives at `subprocess_venvs/boxer/` (repo-root, gitignored). Setup script at `scripts/setup_boxer_subprocess.sh`. Script MUST be idempotent — `[ -f subprocess_venvs/boxer/.ready ] && exit 0` at top. Touches `.ready` marker after successful install + weight fetch. `make download-models-boxer` invokes the script. Matches Phase 5 SC#2 literal requirement ("subprocess venv boots via `setup_boxer_subprocess.sh`"). Consistent with v2.0 SLAM subprocess conventions (SLAM backends use system Python but BoxeR's DINOv3+BoxerNet+moderngl cocktail conflicts with the main venv — isolation is mandatory).

- **D-02 (Msgpack reply schema extension — ADDITIVE):** Phase 2 D-17's schema `{ts, inference_ms, n_det, classes, scores, bboxes}` is extended additively with an **optional** `boxes_3d` field carrying 3D-native OBBs as list of dicts:
  ```python
  boxes_3d: list[dict] = [
      {"tx": float, "ty": float, "tz": float,           # center in world frame
       "qx": float, "qy": float, "qz": float, "qw": float,  # orientation (xyzw)
       "w": float, "h": float, "d": float}              # extent (full, not half)
      for _ in range(n_det)
  ]
  ```
  `bboxes` (2D `[x0,y0,x1,y1]`) is still emitted for CameraFeed RGB overlay (Phase 3 D-16 handles it). `boxer_backend.py` (in-process composer) iterates `boxes_3d`, constructs `OrientedBox3D` instances via `types.OrientedBox3D(...)`, and calls `to_wire()` — it does NOT handcraft quaternions (Phase 1 D-10 invariant holds). Non-3D-native workers simply omit `boxes_3d`; the reply schema key is `Optional[list]`. No Phase 2 consumer breakage (all existing consumers use `bboxes` only).

- **D-03 (Crash watchdog ownership):** `DetectorWorkerPool` owns the crash watchdog. Each per-robot worker thread wraps its `bridge.call(frame)` invocation in `try/except (BridgeHangError, SubprocessDiedError)`. On catch:
  1. Pool emits `crash_fallback` WS message: `{subsystem: "detector", crashed_backend: "boxer", fallback_backend: "yolov11", reason: <str>}` (same envelope as `src/exploration/exploration_loop.py:207` SLAM pattern).
  2. Pool calls `DetectorRegistry.create("yolov11")`, runs its `warmup()`, and atomically swaps the backend ref into all worker threads (same atomicity pattern as Phase 4 D-10 lifter hot-swap — `asyncio.Lock` protects the ref; reads are lock-free).
  3. Frontend `CrashToast` (Phase 3 already shipped, see `frontend/src/components/CrashToast.tsx`) renders from `detectorStore.crashMessage` which `useWebSocket.ts:188-200` populates.
  Total time from `kill -9 <pid>` to fallback-complete ≤ 5 s per SC#3 (bridge 5 s watchdog + warmup < 1 s for YOLOv11).

- **D-04 (Post-crash availability):** Once BoxeR crashes + falls back, `DetectorRegistry.set_available("boxer", False, reason="Crashed this session — restart the coordinator to retry.")` is called. Frontend dropdown shows BoxeR greyed-out with the reason inline per Phase 3 D-06 rendering pattern. Session-scoped only — on next process start, registry rebuilds with `available: true`. No auto-retry loop. This is the explicit, user-visible failure mode: one crash → backend is dead until restart.

- **D-05 (Bridge lifecycle):** `BoxeRBackend.__init__` lazily spawns the bridge on first `warmup()` call, NOT at construction time. Rationale: Phase 3 D-10's `/api/detectors/backends` route enumerates all registered backends on every request to populate the dropdown — we MUST NOT spawn a BoxeR subprocess on each enumeration. Construction is cheap (just stores config); warmup is expensive (spawns process, loads weights). Matches Phase 1 TorchBackendMixin warmup contract.

### RT-DETRv2 ONNX Backend (DET-MODELS-02)

- **D-06 (ONNX acquisition strategy):** On-demand export via `transformers` + `optimum` on first run, cached to `./models/rtdetrv2/<sha>/model.onnx`. First-run flow inside `scripts/download_models.py`:
  ```python
  snapshot_download("PekingU/rtdetr_v2_r18vd", revision=RT_DETRV2_SHA, local_dir=f"models/rtdetrv2/{RT_DETRV2_SHA}/pt/")
  optimum.exporters.onnx.main_export(model=f"models/rtdetrv2/{RT_DETRV2_SHA}/pt/",
                                      output=f"models/rtdetrv2/{RT_DETRV2_SHA}/", task="object-detection",
                                      input_shapes={"pixel_values": [1, 3, 320, 320]})
  ```
  Backend's `__init__` checks `models/rtdetrv2/<RT_DETRV2_SHA>/model.onnx` exists; if missing, raises with `make download-models-rtdetrv2` hint (does NOT auto-download — `make download-models` is the one-time pre-fetch gate per SC#4). `optimum[exporters]` lives in the `dev` extra (download-time only, not required for runtime).

- **D-07 (Runtime + EP):** `onnxruntime>=1.19.0` added to `pyproject.toml [project.optional-dependencies].perception`. Session constructed with `ort.SessionOptions()` + `providers=["CPUExecutionProvider"]`. Thread count inherits from `src/_thread_config.py` (Phase 1 D-04 invariant — no module-scope `torch.set_num_threads()` or `ort.SetThreadOptions()` outside `_thread_config.py`). Consider `sess_options.intra_op_num_threads = <from thread_config>` explicitly at session construction.

- **D-08 (Input resolution — FIXED 320×320):** ONNX export is done with static input shape `[1, 3, 320, 320]` per D-06. Backend `__call__` preprocesses: letterbox-resize the MuJoCo 480×640 RGB frame → 320×320 (preserving aspect ratio, black padding), feeds to session, scales detection bboxes back to original 480×640 coords for `bbox_xyxy` (2D CameraFeed overlay) and for any 2D→3D lifting by `PointClusterLifter`. Matches SC#1's "≤250 ms/frame at 320 px" literal target. Session cache is per-shape so fixed input eliminates cold-start recompile variance.

- **D-09 (Session scope — per-worker):** Each `DetectorWorker` thread owns its own `ort.InferenceSession` instance. Memory cost: ~80 MB × N robots (default N=2 → 160 MB total). Within Phase 1 RSS growth budget (SC#3 caps RSS growth at +200 MB over 100 inferences but initial session allocation is a one-time cost, not inference-induced growth). Mirrors Phase 2 symmetric per-robot backend instantiation via `DetectorRegistry.create()`. Avoids cross-thread GIL / session-lock contention of a shared session.

### OWLv2 Scope Drop (REPLACES DET-MODELS-04)

- **D-10 (OWLv2 dropped from Phase 5):** OWLv2 (`google/owlv2-base-patch16-ensemble`) is removed from Phase 5 scope and moved to REQUIREMENTS.md Out of Scope with reason: **"conflicts with real-time pipeline constraint — text-prompted open-vocab detection needs a dedicated one-shot labeling workflow, not a live selectable backend."** A 1–4 s/frame backend in a 30 Hz worker loop starves the live 3D map between detections; no UI gating short of a one-shot labeling mode (which is its own feature, not a backend variant) meaningfully preserves the project's "Multiple robots explore and build map in real-time" core value from PROJECT.md.
  - Phase 3 D-05's `input_type` capability key RESERVATION STANDS — reserved for future open-vocab/text-prompted backends if a proper one-shot workflow is designed. No code activates it in Phase 5.
  - `scripts/download_models.py` does NOT download OWLv2 weights.
  - `LICENSES.md` does NOT list OWLv2 (Apache 2.0 entry not needed — backend not shipped).
  - If the user later wants open-vocab: file a new v4.0 (or later) milestone requirement covering the one-shot labeling UX, not just "add OWLv2 as a backend."

### Checkpoints + Offline + LICENSES (DET-MODELS-07, DET-MODELS-08)

- **D-11 (models/ dir layout):** `models/<backend-slug>/<sha>/<artifact>` — backend-name owned. Concretely:
  - `models/rtdetrv2/<RT_DETRV2_SHA>/pt/` (HF snapshot PyTorch weights, intermediate)
  - `models/rtdetrv2/<RT_DETRV2_SHA>/model.onnx` (exported, production runtime artifact)
  - `models/boxer/<BOXER_SHA>/weights.pth` (BoxeR's BoxerNet checkpoint, downloaded by `setup_boxer_subprocess.sh` via facebook/boxer's own `download_ckpts.sh`)
  - `models/boxer/<BOXER_SHA>/dinov3/` (DINOv3 feature backbone, if BoxeR's download script fetches it there)
  Consistent with existing `models/orbslam3/` + `models/unitree_go2/` v2.0 conventions. `models/` stays gitignored; `.gitkeep` with a README.md documenting the expected layout.

- **D-12 (SHA pinning + offline gate):** Each backend module hard-codes a module-level constant:
  ```python
  # src/perception/backends/rtdetrv2_backend.py
  RT_DETRV2_SHA = "<40-char-hex-sha-from-HF-hub>"    # verify via Context7 at planning time
  # src/perception/backends/boxer_backend.py
  BOXER_SHA = "<40-char-hex-sha-from-github-boxer>"  # pinned git commit
  ```
  HF loaders always pass `revision=RT_DETRV2_SHA, local_files_only=True` after first fetch. `make download-models` wraps the fetch step in `env HF_HUB_OFFLINE=0 ...` (explicit override for the one-time fetch). SC#4's offline verification gate: `tests/integration/test_download_models.py` pre-fetches via `make download-models`, then spawns coordinator under `env HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 argus ...`, asserts all three listed backends (YOLOv11 already cached, RT-DETRv2 from models/, BoxeR via setup script) boot without network. BoxeR SHA pinning = git commit SHA (not HF revision); setup script clones with `git checkout $BOXER_SHA`.

- **D-13 (Makefile + download_models.py split):** `Makefile` at repo root is thin — each target calls into Python:
  ```make
  .PHONY: download-models download-models-rtdetrv2 download-models-boxer
  download-models: download-models-rtdetrv2 download-models-boxer
  download-models-rtdetrv2:
  	uv run python scripts/download_models.py --backend rtdetrv2
  download-models-boxer:
  	bash scripts/setup_boxer_subprocess.sh
  ```
  `scripts/download_models.py` owns all Python-side logic: HF snapshot_download, optimum ONNX export, sha256 verification on downloaded artifacts, rollback-on-failure (removes partial `models/<backend>/<sha>/` dir if any step fails). `setup_boxer_subprocess.sh` handles the venv + git-checkout + BoxeR's own weight fetch (because its weight fetch runs inside the subprocess venv, not the main venv). Matches SC#4's `make download-models` literal requirement.

- **D-14 (LICENSES.md + CC-BY-NC surfacing):** New `LICENSES.md` at repo root. Format: markdown table — per-dependency rows with SPDX identifier, upstream link, and scope note.
  ```markdown
  | Dep | SPDX | Upstream | Scope |
  |-----|------|----------|-------|
  | Ultralytics YOLOv11 | AGPL-3.0 | ... | Runtime dep — copyleft implications for redistribution |
  | RT-DETRv2 (PekingU) | Apache-2.0 | ... | Runtime dep — permissive |
  | facebook/BoxeR | CC-BY-NC-4.0 | https://github.com/facebookresearch/boxer | **Non-commercial only — research/academic use** |
  | ONNX Runtime | MIT | ... | Runtime dep |
  | ... | ... | ... | ... |
  ```
  BoxeR backend advertises `license: "CC-BY-NC-4.0"` via its capability dict — Phase 3 D-05 already renders the `license` badge in `DetectorDropdown` + `DetectorSection`. User sees the CC-BY-NC-4.0 pill inline before selecting — that is the NC surfacing mechanism. No additional ConfirmModal (Phase 3 D-14's existing "Switch Detector" ConfirmModal already gates selection; stacking two modals is awkward). No auto-warning popup. License is a fact rendered in the UI, not an obstacle course.

### Claude's Discretion (planner picks, within the decisions above)

- Exact RT-DETRv2 HF sha value (verify via Context7 research flag — ROADMAP line 115).
- Exact facebook/boxer git commit sha (verify via Context7 — ROADMAP line 115).
- Exact sha256 values for BoxeR-fetched DINOv3/BoxerNet artifacts (computed first fetch, committed into `scripts/download_models.py` constants).
- `ort.SessionOptions` tuning beyond `intra_op_num_threads` (graph optimization level, memory pattern, etc.).
- BoxeR worker script's internal logging + heartbeat cadence (within Phase 2's bridge contract).
- Exact sha256-mismatch rollback cleanup strategy (`models/<backend>/<bad-sha>/` dir → delete vs move to `.trash/`).
- Whether `Makefile` grows non-model targets (test, lint, etc.) — planner may leave it minimal or expand.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 spec
- `.planning/REQUIREMENTS.md` — DET-MODELS-02, DET-MODELS-03, DET-MODELS-06, DET-MODELS-07, DET-MODELS-08 (DET-MODELS-04 was dropped in this commit — see Out of Scope section)
- `.planning/ROADMAP.md` — Phase 5 section (5 success criteria post-amendment; SC#5 formerly OWLv2 is REMOVED, former SC#6 LICENSES.md is renumbered to SC#5)

### Phase 1/2 invariants (MUST hold)
- `src/perception/protocol.py::DetectorProtocol` — every backend honors `warmup()`, `process_frame(frame) -> Detections2D|Detections3D`, `get_metrics()`, `PARAMETER_SCHEMA`, `CAPABILITIES`
- `src/perception/registry.py::DetectorRegistry` — decorator-based registration; `set_available(backend, bool, reason)` used by D-04 post-crash marking
- `src/perception/types.py::OrientedBox3D` — sole quaternion construction site (Phase 1 D-10). BoxeR composer MUST NOT handcraft quaternions; it MUST call `OrientedBox3D(tx=..., ty=..., tz=..., qx=..., qy=..., qz=..., qw=..., w=..., h=..., d=..., class_id=..., class_name=..., score=..., track_id=...).to_wire()`.
- `src/perception/types.py::Detections3D` envelope — `capture_pose` + `capture_timestamp` populated at submission time (Phase 2 D-11). BoxeR's subprocess round-trip must preserve these; they flow through the coordinator → bridge → worker → bridge → composer path unchanged.
- `src/perception/subprocess_bridge.py::SubprocessDetectorBridge` — Phase 2 D-16/D-17 skeleton; Phase 5 composes it (one instance per BoxeR backend instance, NOT per robot — worker pool fans out per-robot frames through the shared bridge sequentially, since BoxeR is a single-process detector). Note: this differs from RT-DETRv2 which has per-robot sessions (D-09); BoxeR is subprocess-bottleneck by design.
- `src/perception/worker_pool.py::DetectorWorkerPool` — gains `on_backend_crash()` handler (D-03). Swap-active-backend atomicity pattern borrowed from Phase 4 D-10.
- `src/_thread_config.py` — Phase 1 D-04 invariant. ORT session threads MUST inherit from this file, not set inline in `rtdetrv2_backend.py`.

### Phase 3 contract (DO NOT break)
- `frontend/src/components/DetectorDropdown.tsx` — capability badges `framework`, `license`, `cpu_latency_hint_ms` (Phase 3 D-05). New backends populate these in their capability dict; zero frontend code change.
- `frontend/src/components/LifterDropdown.tsx` — auto-hidden when active backend advertises `outputs_3d_natively: true` (Phase 3 D-08). BoxeR does; RT-DETRv2 does not. Validated by per-backend selection QA.
- `frontend/src/components/CrashToast.tsx` + `frontend/src/hooks/useWebSocket.ts:188-200` — crash_fallback handler already wired for SLAM. Backend simply emits the WS message in the pool-owned handler (D-03). Phase 3 D-10's log-only wire was provisional; Phase 5 exercises it.
- `frontend/src/stores/detectorStore.ts::crashMessage` + `setCrashMessage/clearCrashMessage` — already shipped in Phase 3 D-02 structural clone.
- `frontend/src/components/RestartOverlay.tsx` — subsystem='detector' render (Phase 3 D-11). Warmup-blocked dismissal via `detector_restart_complete` already wired (Phase 3 D-15).

### Phase 4 contract (DO NOT break)
- `src/perception/lifters/point_cluster.py` (default lifter) — consumes RT-DETRv2 2D detections. BoxeR bypasses it via `outputs_3d_natively: true`.
- `src/perception/worker_pool.py::DetectorWorkerPool::swap_lifter` (Phase 4 D-10) — pattern replicated for backend swap in D-03.

### Research (read for pinning)
- `.planning/research/STACK.md` §"Real-time Transformer Backend: RT-DETRv2" — HF repo + revision strategy + preprocessing normalization notes
- `.planning/research/STACK.md` §"Reference-quality 3D backend: facebook/BoxeR" — multi-minute CPU latency warning; confirms subprocess isolation requirement
- `.planning/research/SUMMARY.md` §"Subprocess Transport" — confirms ZMQ PAIR + msgpack + 5 s HANG_TIMEOUT_MS reuse

### External references (verify via Context7 at planning time, per ROADMAP research flag)
- HuggingFace `PekingU/rtdetr_v2_r18vd` — https://huggingface.co/PekingU/rtdetr_v2_r18vd (pin revision to a specific sha at planning time)
- facebook/boxer — https://github.com/facebookresearch/boxer (pin to a specific git sha)
- onnxruntime CPU EP — https://onnxruntime.ai/docs/execution-providers/CPU-ExecutionProvider.html
- optimum.exporters.onnx — https://huggingface.co/docs/optimum/main/en/exporters/onnx/package_reference/export
- BoxeR license (CC-BY-NC-4.0) — https://creativecommons.org/licenses/by-nc/4.0/

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (fully wired, just compose)
- `src/perception/subprocess_bridge.py::SubprocessDetectorBridge` — Phase 2 skeleton with spawn/send/recv/kill. Test harness at `scripts/echo_detector_worker.py` confirms round-trip works. Phase 5 composes it in `BoxeRBackend`.
- `src/perception/registry.py::DetectorRegistry` — decorator `@detector_backend(id="rtdetrv2", ...)` is the only surface needed to register new backends. No registry changes.
- `src/perception/backends/yolov11_backend.py` — reference implementation of `TorchBackendMixin + DetectorProtocol`. Copy its `warmup()` pattern (dummy tensor → process_frame → discard).
- `frontend/src/components/CrashToast.tsx` — already exists from SLAM. Phase 5 just emits the matching WS message (no component change).
- `scripts/echo_detector_worker.py` — Phase 2 test fixture. Phase 5's `scripts/boxer_worker.py` uses it as a structural template (msgpack loop, heartbeat, exit on sentinel).

### Established patterns (follow these)
- **Backend registration via decorator** — Phase 1 D-03. `@detector_backend(id=..., capabilities=..., parameter_schema=...)`.
- **Capability dict conventions** — Phase 3 D-04/D-05. Keys: `framework`, `license`, `cpu_latency_hint_ms`, `outputs_3d_natively`, `input_type` (reserved), `track_id_support`.
- **Warmup contract** — first `warmup()` call loads weights + runs one inference to JIT/trace/warm the session. Overlay dismisses AFTER warmup completes (Phase 3 D-15). ≤30 s budget per SC#1.
- **Per-backend RSS budget** — SC#3 (Phase 1) caps +200 MB over 100 inferences. Applies to RT-DETRv2 too.
- **Thread config hygiene** — Phase 1 D-04. No `torch.set_num_threads()` or `ort.SessionOptions.intra_op_num_threads = N` outside `_thread_config.py`. Backends READ from the shared config, they DO NOT SET it.

### Integration points
- `src/main.py::restart_block` — Phase 3 already handles `pending_backend` + `pending_lifter`. Phase 5 new backends require ZERO additional restart-block logic (generic via DetectorRegistry).
- `backend/web/detector_routes.py::GET /api/detectors/backends` — auto-populates from `DetectorRegistry.list()`. New backends appear without route edits.
- `pyproject.toml [project.optional-dependencies].perception` — add `onnxruntime>=1.19.0`. No other runtime dep changes.
- `pyproject.toml [project.optional-dependencies].dev` — add `optimum[exporters]>=1.20.0` (download-time only).
- `.gitignore` — add `subprocess_venvs/` and keep `models/` entry (already ignored).

### Caveats (easy-to-miss)
- BoxeR composer runs in the MAIN process and owns the bridge ref; the bridge's subprocess runs the BoxeR worker script. Don't confuse the two.
- BoxeR is a SINGLE-PROCESS detector — one subprocess serves ALL robots. Per-robot fan-out is sequential through the shared bridge. RT-DETRv2 is per-robot by contrast (one ORT session per worker).
- Session construction outside `_thread_config.py` violates Phase 1 D-04 — easy to regress if `ort.SessionOptions()` gets configured in the backend constructor. Read the Phase 1 invariant carefully.

</code_context>

<specifics>
## Specific Ideas

- "If it's not real-time, maybe it shouldn't be integrated" — user rejection of OWLv2 in Area 3 Q4. This is a principle decision, not an ad-hoc drop. Future open-vocab backends are acceptable ONLY if they come with a purpose-built one-shot labeling workflow (not a "select a slow backend as if it were live").
- BoxeR CC-BY-NC-4.0 is surfaced through the existing capability-badge render (D-14), NOT via a new consent modal. Philosophy: render facts, don't gate actions with legal popups.
- `make download-models` is the SC#4 literal — keep the target name exactly as written in the roadmap. Don't rename to `fetch-checkpoints` or similar.
- Phase 5 adds zero frontend components, zero new WS message types, zero new REST routes. All new capability flows through existing Phase 3 surfaces (capability dict → badge, crash_fallback WS message → CrashToast, restart overlay → warmup gate). This is the pluggability regression test working as designed.

</specifics>

<deferred>
## Deferred Ideas

- **OWLv2 backend** — REMOVED from Phase 5. Moved to `.planning/REQUIREMENTS.md` Out of Scope. Re-openable only via a future milestone that specifies a one-shot labeling workflow (not a live backend selection).
- **Text-prompted open-vocab detection UI** — deferred with OWLv2. Phase 3 D-05's `input_type` capability key stays reserved.
- **Multi-prompt comma-separated input** — N/A without OWLv2; revisit if a future open-vocab backend is designed.
- **Warmup UX for slow-first-run ONNX export** — RT-DETRv2 ONNX export can blow SC#1's ≤30 s warmup window if it runs at runtime. Mitigated by forcing `make download-models` ahead of time (D-06 raises with install hint if artifact missing). If user wants automatic fallback export, revisit as Phase 5.x or Phase 6 polish.
- **OpenVINO ONNX EP** — rejected in D-07. Revisit only if hardware target narrows to Intel-only.
- **Dynamic ONNX input shape** — rejected in D-08. Revisit if RT-DETRv2 needs non-square or variable input for a future scene.
- **Shared ORT session across workers** — rejected in D-09. Revisit only if RAM budget is blown at N≥8 robots.
- **Manifest-file sha pinning** — rejected in D-12. Revisit when backend count reaches 5+.
- **Per-class color palette expansion (>8 classes)** — noted in discussion close-out. Not Phase 5 scope; revisit in Phase 6 (MetricsPanel) or as a standalone polish ticket.
- **ConfirmModal gating BoxeR selection for CC-BY-NC** — rejected in D-14 (UX stacking with existing Phase 3 D-14 modal). Revisit only if legal requirement changes.
- **Auto-retry BoxeR after crash** — rejected in D-04. Revisit only if crashes turn out to be transient (they haven't been in v2.0 SLAM subprocess history — OOM/missing-weight errors are terminal).

</deferred>

---

*Phase: 05-second-backends-boxer-rtdetr-owlv2 (slug retains -owlv2 suffix per git-history stability; OWLv2 is NOT shipped — see D-10)*
*Context gathered: 2026-04-15*
*Discussion log: 05-DISCUSSION-LOG.md*
