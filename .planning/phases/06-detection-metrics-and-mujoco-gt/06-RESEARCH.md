# Phase 6: detection-metrics-and-mujoco-gt — Research

**Researched:** 2026-04-15
**Domain:** Per-robot detection metrics aggregation, MuJoCo ground-truth extraction, FastAPI streaming JSONL export, parametrized RSS smoke harness
**Confidence:** HIGH (codebase verified end-to-end; mujoco bindings probed live; one cross-cutting scene-data finding flagged as MUST RESOLVE before SC#2)

## Summary

Phase 6 wires honest, MuJoCo-grounded detection metrics into the existing `MetricsPanel` pipeline by composing a new `DetectionMetricsTracker` alongside the existing `MetricsTracker`, adds a `MuJoCoGTExtractor` that reads world-frame body positions for `center_error_m` + `per_class_recall`, ships a `DetectionExportWriter` + `GET /api/detections/export` streaming endpoint, locks `mAP` out of the UI, and generalizes the existing Phase-1 RSS smoke test into a parametrized fixture across YOLOv11 / RT-DETRv2 / BoxeR. CONTEXT.md D-01..D-17 lock every implementation choice; this research validates the codebase reality each decision sits on top of.

Three findings are load-bearing for the planner:

1. **`data.xpos` returns (0,0,0) for every labeled body in `scene_office1.xml`.** All non-robot bodies declare no `pos=` attribute and hold their visible position in mesh vertex coordinates, so `mj_name2id + data.xpos` reads world-origin for chairs, tables, etc. The honest read is `data.geom_xpos[first_geom_of_body]` — verified live (SwivlChair geom_xpos = `[0.681, -2.440, 0.511]`, BrownChair = `[-0.356, 7.985, 0.467]`, MeetingTable = `[-0.347, 7.994, 0.546]`). CONTEXT.md D-08 names `data.xpos` as the GT source — the planner MUST switch to `data.geom_xpos` (or escalate as a CONTEXT.md amendment) or SC#2 cannot pass on `scene_office1.xml`.
2. **Coordinator pump site is `src/coordination/coordinator.py::_send_viz_update` (line 644), not `src/main.py`.** `main.py` only owns the restart block and the pool construction; per-tick metric pumping must live in the same method that already calls `tracker.record_frame(...)` for SLAM (line 705). CONTEXT.md D-17 says "src/main.py or the per-robot coordinator" — Coordinator is the answer.
3. **`DetectorWorker` exposes no public `.detector` accessor.** The reference field is `worker._detector`. CONTEXT.md D-17 references `worker.detector.get_metrics()`. The planner picks one: add a `@property detector` getter on `DetectorWorker`, route the metrics through `DetectorWorkerPool.get_metrics(rid)`, or call `worker._detector.get_metrics()` directly (with a `# noqa: SLF001`). Recommend the property — single-line addition, opens no new abstractions.

**Primary recommendation:** Mirror the existing `MetricsTracker` shape line-for-line in `DetectionMetricsTracker`; pump from `_send_viz_update`; resolve the `data.geom_xpos` finding before Plan 03 (mujoco_gt extractor) is written.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Parallel `DetectionMetricsTracker` class:** Lives at `src/metrics/detection_metrics_tracker.py`, mirrors `MetricsTracker` shape 1:1 with per-robot `dict[robot_id, {<metric>: float, <metric>_history: deque[maxlen=history_size]}]`, exposes `record_frame()` + `get_stats_payload()` + `reset()`. NO inheritance. `WebStreamingViz.__init__` gains `self._detection_metrics_tracker = DetectionMetricsTracker(history_size=60)`.

**D-02 — Per-robot per-tick pump:** `record_frame(robot_id, latest: Detections3D | None, inspect: dict, backend_metrics: dict)`. Inputs: `worker.latest()` (drives detections_per_frame, mean_confidence, freshness), `worker.inspect()` (queue_depth, drops_since_session_start), `detector.get_metrics()` (inference_ms_p50/p95, first_inference_ms). Returns `{"detection_metrics": {<rid>: latest}, "detection_history": {<rid>: histories}}`.

**D-03 — 3D jitter via nearest-neighbor matching (0.5 m gate):** Per-robot `_tracked_center: np.ndarray | None` seeded on first detection of each class. On each frame, find closest prior tracked center within 0.5 m, append new center to bounded history (maxlen=30), update tracked center. Report `3d_center_jitter_m = np.std(np.linalg.norm(history - mean, axis=1))` per class; UI shows aggregate `max` across classes per robot. When Phase 8's ByteTrack `track_id` lands, swap matching step only — math + API unchanged.

**D-04 — EXTEND existing `frontend/src/components/MetricsPanel.tsx`:** Add detection subsection to "Live" tab below SLAM rows. Same robot-keyed column layout. New rows: `infer p50 / infer p95 / det/frame / conf / queue / fresh / jitter`. NO new component. NO additional collapse granularity.

**D-05 — No baseline tab for detection metrics in Phase 6.**

**D-06 — No sparklines yet.** Populate `detectionHistory` arrays in store; render current values only. Sparklines drop in later via `<Sparkline data={detectionHistory[rid]?.inference_ms ?? []} />`.

**D-07 — Robot ordering + palette:** Same `robotId` key order, same `robotColor(index)` from `palette.ts` as SLAM column. Left-border color matches.

**D-08 — Explicit mapping file (NOT substring matching):** Ship `data/scenes/scene_office1_gt.yaml` mapping COCO class names → list of MuJoCo body names. `MuJoCoGTExtractor.__init__(scene_xml_path, mapping_yaml_path, mj_model, mj_data)` reads YAML at startup, resolves each body to id via `mj_name2id`, fail-fast on missing body.

**D-09 — Matching policy: nearest-neighbor in world frame, class-gated:** For each detection class C, look up `body_ids = mapping[C]`, read xpos per body, match detection's OBB center to nearest body by Euclidean distance, 1.0 m gate. Per-class recall = `matched / expected` per frame, ring-buffered over 60 frames. 1.0 m is "correct-instance" gate, NOT accuracy gate — the actual accuracy IS the `center_error_m` value reported.

**D-10 — `mAP`-forbidden UI enforcement:** Grep test `tests/contract/test_no_map_in_ui.py` invokes `git grep -n mAP frontend/src/`; `assert returncode == 1`. Plus runtime guard in `WebStreamingViz._update_stats` payload serialization (asserts no `mAP / map_50 / map_75` key). `--labeled-eval-set` CLI flag RESERVED in `src/main.py::parse_args` with `NotImplementedError`.

**D-11 — Append-on-emit JSONL:** `DetectionExportWriter.__init__(session_id)` opens `/tmp/argus_sessions/<session_id>/detections.jsonl` in append mode, line-buffered (`open(..., "a", buffering=1)`) so SIGKILL preserves data. Each `append(detection, robot_id, backend_id, capture_timestamp)` writes one JSON line containing the full `OrientedBox3D.to_wire()` payload + envelope keys.

**D-12 — Session lifecycle:** UUID4 generated on coordinator boot; `WebStreamingViz` owns the writer. On `reset_cloud_tracking()`, generate new UUID, open new file. Prior session files NOT auto-deleted.

**D-13 — Streaming endpoint:** `GET /api/detections/export` returns `StreamingResponse(generate(), media_type="application/x-ndjson", headers={"Content-Disposition": "attachment; filename=detections-<session>.jsonl"})`. Generator opens file rb, reads 65536-byte chunks until EOF (snapshot-at-request-time, not `tail -f`).

**D-14 — Round-trip test:** `tests/integration/test_detections_export.py` spawns coordinator with YOLOv11 for 30 frames against `scene_office1.xml`, hits export, asserts every line round-trips through `OrientedBox3D.from_wire` to ±1e-6.

**D-15 — Single parametrized pytest harness:** `tests/integration/test_rss_smoke_backends.py` with `@pytest.mark.parametrize("backend_id", ["yolov11", "rtdetrv2", pytest.param("boxer", marks=pytest.mark.slow_boxer)])`. RT-DETRv2 honest-skip if `models/rtdetrv2/<sha>/model.onnx` missing (hint: `make download-models-rtdetrv2`). BoxeR honest-skip if `subprocess_venvs/boxer/.ready` missing (hint: `bash scripts/setup_boxer_subprocess.sh`).

**D-16 — CI inclusion: fast tier only:** `yolov11` + `rtdetrv2` default; BoxeR opt-in via `-m slow_boxer`.

**D-17 — Coordinator hook:** Per robot per tick, after worker submit/latest:
```python
for rid, worker in worker_pool.items():
    latest = worker.latest()
    inspect = worker.inspect()
    backend_metrics = worker.detector.get_metrics()  # NOTE: see Finding F2 — accessor needs decision
    streaming_viz.detection_metrics_tracker.record_frame(rid, latest, inspect, backend_metrics)
    if latest is not None and latest.boxes:
        for obb in latest.boxes:
            streaming_viz.detection_export.append(obb, robot_id=rid, backend_id=..., capture_timestamp=latest.capture_timestamp)
```
Tracker + writer owned by `WebStreamingViz`; coordinator pumps. Zero new threads.

### Claude's Discretion (planner picks within above)

- `history_size` for detection ring buffers (60 matches SLAM; bump to 120 if needed)
- 3D jitter gate threshold (0.5 m default; per-class override later)
- center_error matching gate (1.0 m default)
- `/tmp/argus_sessions/` exact path (`tempfile.gettempdir()` is OS-portable)
- Whether `DetectionMetricsTracker.reset()` rotates the export writer (recommend yes)
- Frontend detection-subsection label spacing/separator
- Whether to add merged `/api/metrics/history` REST (deferred, not SC)
- YAML vs JSON for `scene_office1_gt.yaml` (YAML chosen — readable)
- Whether grep test also covers backend JSON payloads (recommend yes — runtime guard)

### Deferred Ideas (OUT OF SCOPE)

- Detection metrics vs-baseline tab
- Sparkline rendering for detection history
- `--labeled-eval-set` actual implementation (reserved with NotImplementedError only)
- ByteTrack per-object jitter tracking (Phase 8)
- Multi-scene GT mapping infrastructure
- Live-tail `/api/detections/export?follow=true`
- Structured session-replay API
- Per-class jitter breakdown in UI
- Runtime mAP assertion in every payload
- Export format alternatives (Parquet / Arrow)
- Cross-platform tmp path beyond `tempfile.gettempdir()`
- Per-scene jitter gate tuning
- `first_inference_ms` surfaced in panel
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-METRICS-01 | MetricsPanel shows per-robot inference_ms p50/p95, det/frame, mean_conf, queue, freshness, jitter — updating live | `MetricsTracker` template documented (`src/metrics/metrics_tracker.py:12-167`); `WebStreamingViz._update_stats` extension point at `backend/web/streaming_viz.py:367-396`; `metricsStore.updateAllMetrics` single-set pattern at `frontend/src/stores/metricsStore.ts:62-67`; backends already populate `inference_ms_p50/p95` (boxer reference at `src/perception/backends/boxer_backend.py:259-272`) |
| DET-METRICS-02 | MuJoCo GT extractor pulls body positions; coordinator matches detected class_name → body name | `mujoco 3.6.0` verified live; `mj_name2id(model, mjtObj.mjOBJ_BODY, name)` confirmed signature returns `int` (-1 if not found); **`data.xpos[body_id]` returns (0,0,0) for all labeled bodies in scene_office1.xml — see Finding F1; use `data.geom_xpos[first_geom_of_body]` instead**; existing usage pattern in `src/bridge/multi_bridge.py:118` |
| DET-METRICS-03 | center_error_m + per_class_recall against MuJoCo GT; `mAP` forbidden in UI without committed labeled set | grep-test pattern proven (Phase 4 SC#3 grep for `70`); `git grep -n mAP frontend/src/` returns `--frontend/src` only; CLI `--labeled-eval-set` flag will be `parse_args` reservation in `src/main.py` |
| DET-METRICS-04 | `GET /api/detections/export` streams JSONL; round-trips through `OrientedBox3D.from_wire` | FastAPI 0.135.2 verified, `StreamingResponse` from `fastapi.responses` confirmed available; `OrientedBox3D.to_wire/from_wire` reference at `src/perception/types.py:112-189`; existing route module pattern at `backend/web/detector_routes.py` |
| DET-METRICS-05 | RSS growth ≤200 MB over 100 inferences per backend; CI failure on regression | Existing template at `tests/smoke/test_detector_rss.py:1-114` already implements warn=200 / fail=400 pattern via `psutil 7.2.2`; Phase 6 generalizes via parametrize+honest-skip; **OWLv2 listed in SC#5 literal but DROPPED in Phase 5 D-10 — see Finding F4** |
</phase_requirements>

## Standard Stack

### Core (already pinned in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mujoco | 3.6.0 | GT body-position extraction (`mj_name2id`, `data.geom_xpos`) | `[VERIFIED: venv probe]` matches `pyproject.toml` `mujoco>=3.0.0`; bindings stable since 3.0 |
| numpy | ≥1.26 | Percentile math (`np.median`, `np.percentile(arr, 95)`), nearest-neighbor distance | `[VERIFIED: pyproject.toml line 11]` already used in BoxeR ref impl |
| fastapi | 0.135.2 | REST endpoint + `StreamingResponse` for JSONL | `[VERIFIED: venv probe]` `[CITED: fastapi.tiangolo.com/advanced/custom-response]` `StreamingResponse(generator, media_type=...)` is the canonical streaming pattern |
| psutil | 7.2.2 | RSS measurement in smoke test | `[VERIFIED: venv probe]` already used by `tests/smoke/test_detector_rss.py:35-46` |

### Supporting (1 dep to add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | 6.0.3 | Read `data/scenes/scene_office1_gt.yaml` mapping file | `[VERIFIED: venv probe]` already installed system-wide; pin to `>=6.0` in `[project.optional-dependencies].perception` for explicit declaration. Used only inside `src/metrics/mujoco_gt.py`. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| YAML mapping file | JSON mapping file | YAML wins on readability for mapping tables (CONTEXT D-08 example); JSON wins on stdlib-only. CONTEXT locks YAML. |
| `data.xpos` for GT | `data.geom_xpos` for GT | `xpos` is body origin (zero for static bodies with no `pos=` attr); `geom_xpos` is the world-frame geom position. **MUST use `geom_xpos`** — see F1. |
| `tail -f` stream | snapshot-at-request stream | CONTEXT D-13 picks snapshot — REST is not the right surface for live tail; if needed later, use WebSocket. |

**Installation:** Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
perception = [
    "torch>=2.10.0",
    "transformers>=5.3.0",
    "ultralytics>=8.4.24",
    "scikit-learn>=1.4.0",
    "onnx>=1.17.0",
    "onnxruntime>=1.19.0",
    "PyYAML>=6.0",   # NEW Phase 6 — mapping file for MuJoCoGTExtractor
]
```

## Architecture Patterns

### File Layout (extensions to existing tree)
```
src/metrics/
├── metrics_tracker.py              # EXISTS — SLAM tracker, template
├── detection_metrics_tracker.py    # NEW (D-01)
├── mujoco_gt.py                    # NEW (D-08, D-09)
└── detection_export.py             # NEW (D-11)

backend/web/
├── streaming_viz.py                # EXTEND — compose new tracker + writer (D-01, D-12)
└── detector_routes.py              # EXTEND — add GET /api/detections/export (D-13)

data/scenes/
├── scene_office1.xml               # EXISTS — read-only here
└── scene_office1_gt.yaml           # NEW (D-08); committed source

frontend/src/
├── stores/metricsStore.ts          # EXTEND — detectionPerRobot + detectionHistory (D-04)
├── components/MetricsPanel.tsx     # EXTEND — detection subsection in Live tab (D-04)
└── utils/messageTypes.ts           # EXTEND — DetectionMetrics + DetectionMetricHistory types (D-04)

tests/
├── metrics/test_detection_metrics_tracker.py   # NEW (unit)
├── metrics/test_mujoco_gt.py                   # NEW (unit, scene_rotated_chair fixture)
├── integration/test_detections_export.py       # NEW (D-14)
├── integration/test_rss_smoke_backends.py      # NEW (D-15) — supersedes tests/smoke/test_detector_rss.py
└── contract/test_no_map_in_ui.py               # NEW (D-10) — directory does not yet exist
```

### Pattern 1: Per-robot ring-buffer tracker (extend, don't fork)
**What:** Mirror `src/metrics/metrics_tracker.py` line-for-line. Same `_ensure_robot()` initializer, same `record_frame(...)` shape, same `get_stats_payload()` return-dict, same `reset()`.
**When to use:** Any per-robot per-frame metric stream that needs ring-buffer history + latest snapshot.
**Example (template — adapt to detection):**
```python
# Source: src/metrics/metrics_tracker.py:25-56 (verbatim shape)
def _ensure_robot(self, robot_id: str) -> dict:
    if robot_id not in self._per_robot:
        self._per_robot[robot_id] = {
            "inference_ms_p50": 0.0,
            "inference_ms_p95": 0.0,
            "detections_per_frame": 0,
            "mean_confidence": 0.0,
            "queue_depth": 0,
            "freshness_s": 0.0,
            "jitter_m": 0.0,
            # histories — all deque(maxlen=self._history_size)
            "inference_ms_history": deque(maxlen=self._history_size),
            "det_per_frame_history": deque(maxlen=self._history_size),
            "confidence_history": deque(maxlen=self._history_size),
            "freshness_history": deque(maxlen=self._history_size),
            "jitter_history": deque(maxlen=self._history_size),
            # internal — for D-03 nearest-neighbor jitter
            "_tracked_centers": {},  # class_name -> deque[np.ndarray] maxlen=30
        }
    return self._per_robot[robot_id]
```

### Pattern 2: Single-set Zustand updater preserves one-re-render-per-stats
**What:** Extend `updateAllMetrics(slam_metrics, baseline, history)` to `updateAllMetrics(slam_metrics, baseline, history, detection_metrics, detection_history)`. ONE `set()` call covers all five fields. Caller (the `useWebSocket` stats handler) accumulates the new fields from the same payload.
**Why:** Zustand re-renders on every `set()` — splitting into two calls causes two renders per stats message. Phase v2.0 13-01 finding documented in `frontend/src/stores/metricsStore.ts:61` comment.
**Example:**
```typescript
// Source: frontend/src/stores/metricsStore.ts:62-67 (current shape)
updateAllMetrics: (slam_metrics, baseline, history, detection_metrics, detection_history) =>
  set({ perRobot: slam_metrics, baseline, history, detectionPerRobot: detection_metrics, detectionHistory: detection_history }),
```

### Pattern 3: FastAPI StreamingResponse for snapshot-at-request file streaming
**What:** Open file in `rb`, read 65536-byte chunks in an async generator, yield until EOF.
**Source:** `[CITED: fastapi.tiangolo.com/advanced/custom-response/#streamingresponse]`
**Example:**
```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

@router.get("/detections/export")
async def export_detections(request: Request):
    streaming_viz = request.app.state.streaming_viz
    session = streaming_viz.current_session_id()
    # Path resolution uses tempfile.gettempdir() for OS portability
    path = Path(tempfile.gettempdir()) / "argus_sessions" / session / "detections.jsonl"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No detections recorded yet")

    def generate():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="detections-{session}.jsonl"'},
    )
```

### Pattern 4: Parametrized pytest with honest-skip on missing artifacts
**Source:** `tests/smoke/test_detector_rss.py:43-46` (psutil skip), Phase 5 `slow_boxer` mark precedent (`pyproject.toml:47`).
**Example:**
```python
import pytest
from pathlib import Path

def _rtdetrv2_artifact_present() -> bool:
    return any(Path("models/rtdetrv2").glob("*/model.onnx"))

def _boxer_ready() -> bool:
    return Path("subprocess_venvs/boxer/.ready").exists()

@pytest.mark.parametrize("backend_id", [
    "yolov11",
    pytest.param("rtdetrv2", marks=pytest.mark.skipif(
        not _rtdetrv2_artifact_present(),
        reason="run `make download-models-rtdetrv2`",
    )),
    pytest.param("boxer", marks=[
        pytest.mark.slow_boxer,
        pytest.mark.skipif(not _boxer_ready(), reason="run `bash scripts/setup_boxer_subprocess.sh`"),
    ]),
])
def test_rss_growth_capped(backend_id, fixture_frame):
    ...
```

### Pattern 5: Grep-based UI invariant (Phase 4 SC#3 precedent)
**Source:** Phase 4 `tests/perception/test_no_focal_math_frontend.py` (existing grep-test pattern in this repo).
```python
# tests/contract/test_no_map_in_ui.py
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

def test_no_map_in_frontend_src():
    """SC#3: literal `mAP` MUST NOT appear in frontend/src/. Limit scope to
    git-tracked files via `git grep` so untracked editor artifacts and the
    .planning/ docs (which legitimately reference mAP) are excluded."""
    result = subprocess.run(
        ["git", "grep", "-n", "mAP", "--", "frontend/src/"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    # git grep returns 1 when no matches found, 0 when matches present
    assert result.returncode == 1, (
        f"`mAP` found in frontend/src/:\n{result.stdout.decode()}"
    )
```

### Anti-Patterns to Avoid

- **Substring class-name matching against body names** — D-08 explicit-mapping is the only honest path. `body_Cube_003_DefaultMaterial` would false-positive substring-match against `cube`, and the auto-generated `body_BezierCurve_009_SwivlChair` does NOT contain `chair` as a clean lowercase token.
- **Reading `data.xpos` for GT body positions in scene_office1.xml** — returns (0,0,0). Use `data.geom_xpos[first_geom_of_body]`. See Finding F1.
- **Inline JSON-construction of OBB wire payload** — Phase 1 D-10 invariant: only `OrientedBox3D.to_wire()`. The JSONL writer wraps that, never handcrafts.
- **Two `set()` calls in `updateAllMetrics`** — doubles re-renders per stats message.
- **Writing `mAP` in any UI label, even commented-out** — grep test runs on raw bytes; comments count.
- **Calling `tracker.reset()` on `WebStreamingViz.reset_cloud_tracking()` if it also rotates the JSONL writer** — confirm semantics: reset_cloud_tracking is called on session restart per CONTEXT D-12, so writer rotation is correct; but per CONTEXT D-12 the SLAM tracker baseline is intentionally preserved across resets. Detection tracker should follow the same convention (don't blow away history on cloud-tracking reset; ONLY rotate the export writer's session_id).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-robot ring buffer | Custom list-with-cap class | `collections.deque(maxlen=N)` (already pattern in `MetricsTracker`) | O(1) append + auto-eviction; matches BoxeR `_inference_times` deque |
| Percentile computation | Manual sort + index math | `np.median(arr)` + `np.percentile(arr, 95)` | Matches `boxer_backend.py:268` and `rtdetrv2_backend` convention |
| YAML parsing | Custom mini-parser | `yaml.safe_load(open(path))` (PyYAML) | Standard, safe-by-default, no code execution |
| MuJoCo body lookup | XML parse | `mujoco.mj_name2id(model, mjtObj.mjOBJ_BODY, name)` | Already the project pattern (`multi_bridge.py:118`) |
| World-frame body position | Compute from euler+pos+mesh | `data.geom_xpos[geom_id]` (NOT `data.xpos[body_id]` for this scene — see F1) | MuJoCo computes geom world position post-`mj_forward`; the visible mesh location is `geom_xpos`, not `xpos`, when bodies sit at origin |
| File streaming over HTTP | Manual chunked encoding | `fastapi.responses.StreamingResponse(generator, media_type=...)` | Wraps Starlette's chunked response correctly; sets Transfer-Encoding |
| RSS measurement | Read `/proc/self/status` and parse | `psutil.Process().memory_info().rss` | Cross-platform; already the established pattern |
| UUID generation | Increment counter or hash | `uuid.uuid4()` (stdlib) | Globally unique, no collision risk across sessions |
| Path joining | f-string concat | `pathlib.Path / "subdir" / "file"` | Already the codebase convention; OS-agnostic |
| OS-portable temp dir | Hardcode `/tmp/` | `tempfile.gettempdir()` | Windows / macOS portable (CONTEXT D-12 calls this out as Claude's discretion) |

**Key insight:** Every primitive Phase 6 needs is already in stdlib, numpy, mujoco, FastAPI, or established codebase patterns. The work is structural plumbing — parallel-extending an existing tracker, mounting a route, parametrizing an existing test. Resist the urge to abstract a "metrics base class" or "GT framework" — the SLAM and detection trackers genuinely have zero shared fields (CONTEXT D-01).

## Runtime State Inventory

> Phase 6 is greenfield code (new metrics modules + a new YAML data file + new tests + extensions to existing modules). No renames, no schema migrations.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no databases or persistent stores in this codebase | None |
| Live service config | None — no external services with embedded names | None |
| OS-registered state | None — coordinator is a single-process Python app, no OS-level service registration | None |
| Secrets/env vars | None — no new secrets; existing env discipline applies | None |
| Build artifacts | `/tmp/argus_sessions/<session_id>/` JSONL files are debug artifacts (per CONTEXT D-12, not auto-deleted). NOT committed; live outside the repo. | Add `tempfile.gettempdir()` resolution; gitignore is N/A since path is outside repo |

**Verified by:** Codebase grep for `data\.xpos`, `MjData`, `tempfile`, `import yaml` — no migration touch-points found.

## Common Pitfalls

### Pitfall 1: `data.xpos` returns (0,0,0) for static labeled bodies in scene_office1.xml
**What goes wrong:** GT extractor reports world-origin for every chair/table; `center_error_m = ||detection_center - 0||` measures distance from origin, not detection error. SC#2 ("center_error_m = 0.0X for chair") fails because the chair is detected at its true geom location (e.g., `[0.68, -2.44, 0.51]`) and "GT" is `[0,0,0]`.
**Why it happens:** Bodies in `scene_office1.xml` (lines 1257-1317) declare `euler="1.5708 0 0"` but no `pos=` attribute. The body origin stays at world (0,0,0). Mesh OBJ files contain absolute vertex coordinates, so the visible position lives in `data.geom_xpos[geom_of_body]`, not `data.xpos[body]`.
**How to avoid:** Use `data.geom_xpos[first_geom_id_of_body]` as GT. The extractor must walk `model.geom_bodyid` to find the first geom for each body, then read `data.geom_xpos`. Verified live values:
  - SwivlChair body 1, geom_xpos = `[0.681, -2.440, 0.511]`
  - SwivlChair_BLACK body 2, geom_xpos = `[0.714, 0.074, 0.724]`
  - BrownChair body 3, geom_xpos = `[-0.356, 7.985, 0.467]`
  - meetingTable body 16, geom_xpos = `[-0.347, 7.994, 0.546]`
  - BigWhiteTable body 7, geom_xpos = `[1.302, 0.889, 0.593]`
  - woodenDesk body 6, geom_xpos = `[-0.061, -6.130, 0.453]`
  - SmallWhiteTable body 8, geom_xpos = `[1.872, -1.510, 0.504]`
  - shelving body 19, geom_xpos = `[4.616, -8.371, 0.605]`
**Warning signs:** Unit tests pass on `scene_rotated_chair.xml` (which has `pos="0 0 0.45"`), integration test on `scene_office1.xml` reports center_error_m == ||detection_center||.

### Pitfall 2: `mAP` substring leaks into the rendered UI via React component imports
**What goes wrong:** A developer adds a `Map<string, ...>` JS Map iteration helper named with the exact `mAP` substring. Or auto-import suggests `mapState` and a partial-rename leaves `mAPState` somewhere. Grep test fails CI silently from contributor's POV (they ran `npm test`, not `pytest`).
**How to avoid:** D-10 dual-enforcement: grep test in `tests/contract/` runs in pytest CI, payload-time runtime guard in `WebStreamingViz._update_stats` asserts no `mAP / map_50 / map_75` key in the serialized stats dict. Document the rule in `frontend/CLAUDE.md` if it exists.
**Warning signs:** Grep test fails on first commit after merging a PR that touches metric naming; check the PR diff for `mAP` collisions.

### Pitfall 3: `worker.detector` is `worker._detector` — no public accessor
**What goes wrong:** CONTEXT D-17 sample code calls `worker.detector.get_metrics()`. Real attribute is `worker._detector`. Either the pump line raises `AttributeError`, or the planner adds `# noqa: SLF001` on private access.
**How to avoid:** Add a single-line `@property def detector(self) -> "DetectorProtocol": return self._detector` to `DetectorWorker` in the same task that wires the pump. Three lines including the type-hint import.
**Warning signs:** Pump task fails at first run with `AttributeError: 'DetectorWorker' object has no attribute 'detector'`.

### Pitfall 4: `freshness = sim_now - capture_timestamp` requires sim-clock reading
**What goes wrong:** Pump reads `time.time()` instead of sim time → freshness is wall-clock minus sim-clock-offset → values are unbounded and meaningless.
**How to avoid:** `_send_viz_update` already has access to `frames[rid].sim_time` (which IS sim-clock seconds, computed in `multi_bridge.py:402` as `sim_time = self._step_count * self._dt`). Pass it as the `sim_now` param to `record_frame`. Phase 2 D-13 invariant.
**Warning signs:** Freshness values >> 60 (suggests wall-clock leak) or negative (suggests stale capture beat sim_now).

### Pitfall 5: `git grep` returns wrong code when no matches found vs grep
**What goes wrong:** `subprocess.run(["grep", ...])` returns 1 on no-match (Unix grep convention) — same as `git grep`, but if cwd is wrong or the path doesn't exist, it can return 2 or 128 (git error). Test passes incorrectly on a bad path.
**How to avoid:** Set `cwd=REPO_ROOT`, assert `result.returncode in (0, 1)` first ("git grep ran successfully"), THEN check `returncode == 1` (no match). Print stderr on unexpected exit codes.

### Pitfall 6: JSONL writer SIGKILL line-buffering caveat
**What goes wrong:** `open(path, "a", buffering=1)` is line-buffered for TEXT mode. CONTEXT D-13 streams the file in BINARY mode (`open(path, "rb")`). Mixing modes is OK, but the line-buffer flush happens on `\n` write — if the JSON line is constructed with `json.dumps(...) + "\n"` and written via `f.write(...)`, line buffering does flush per-line. Verified: `open(..., "a", buffering=1)` flushes on `\n` per CPython docs. SAFE pattern.
**How to avoid:** Use the canonical pattern below; do not switch to `f.flush()` per write (slow) or rely on default buffering (lossy on SIGKILL).
```python
self._fp = open(path, "a", buffering=1, encoding="utf-8")
def append(self, obb, robot_id, backend_id, capture_timestamp):
    record = {
        "robot_id": robot_id,
        "backend_id": backend_id,
        "capture_timestamp": capture_timestamp,
        "obb": obb.to_wire(),
    }
    self._fp.write(json.dumps(record, separators=(",", ":")) + "\n")
```
**Warning signs:** Round-trip integration test (D-14) passes locally but flakes on slow CI — would indicate writer not flushing before reader opens.

### Pitfall 7: BoxeR RSS smoke test treats subprocess startup as inference RSS growth
**What goes wrong:** BoxeR backend boots a subprocess + venv on `__init__()`, costing 200-800 MB RSS. If RSS measurement starts BEFORE `backend.warmup()`, the subprocess startup memory is counted as inference RSS growth → false fail.
**How to avoid:** Existing `tests/smoke/test_detector_rss.py:82-86` already does the right thing: warm up first, `gc.collect()`, THEN baseline RSS measurement. Phase 6 generalization preserves this order.

### Pitfall 8: `MuJoCoGTExtractor` re-loading the XML breaks pose tracking
**What goes wrong:** Extractor calls `mujoco.MjModel.from_xml_path(...)` to get its own model, then reads `data.xpos` — but `data` is local; the bridge's `data` (the one being stepped) is not visible. Result: positions never update.
**How to avoid:** Extractor accepts `mj_model + mj_data` references in `__init__`, both supplied by the bridge. CONTEXT canonical_refs explicitly says this: "MuJoCoGTExtractor reuses scene_builder's mjModel handle rather than re-loading the XML". The bridge has `_data` (private) — add a public `@property def mj_data(self) -> Any` accessor (single line) when wiring; same for `mj_model` if not already exposed.

## Code Examples

### Example 1: `MuJoCoGTExtractor` body→geom resolution (the hard part)
```python
# Source: combined from mujoco 3.6.0 docs + src/bridge/multi_bridge.py:118 pattern
import mujoco
import yaml
import numpy as np
from pathlib import Path

class MuJoCoGTExtractor:
    """Resolve COCO class names to MuJoCo body GT positions via mapping file.

    NOTE: Reads `data.geom_xpos[first_geom_of_body]`, NOT `data.xpos[body_id]`.
    Bodies in scene_office1.xml have no `pos=` attribute, so `xpos` is (0,0,0).
    The visible position lives in mesh vertex coordinates, exposed via
    `geom_xpos` after `mj_forward()` runs (which the bridge's per-step
    `mj_step` already triggers).
    """

    def __init__(
        self,
        mapping_yaml_path: Path,
        mj_model,  # mujoco.MjModel
        mj_data,   # mujoco.MjData
    ) -> None:
        self._model = mj_model
        self._data = mj_data
        with open(mapping_yaml_path, "r", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)  # {class_name: [body_name_1, ...]}

        # Resolve body -> first geom (for geom_xpos lookup) at construction.
        # Fail-fast on missing body or body with no geom (CONTEXT D-08).
        self._class_to_geom_ids: dict[str, list[int]] = {}
        for class_name, body_names in mapping.items():
            geom_ids: list[int] = []
            for body_name in body_names:
                bid = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_BODY, body_name)
                if bid < 0:
                    raise ValueError(
                        f"GT mapping references unknown body '{body_name}' "
                        f"(class={class_name}). Run `mj_id2name` audit."
                    )
                # Find first geom belonging to this body
                gid = -1
                for g in range(mj_model.ngeom):
                    if mj_model.geom_bodyid[g] == bid:
                        gid = g
                        break
                if gid < 0:
                    raise ValueError(
                        f"Body '{body_name}' has no geom — GT extraction "
                        f"requires geom_xpos. Verify scene XML."
                    )
                geom_ids.append(gid)
            self._class_to_geom_ids[class_name] = geom_ids

    def gt_positions(self, class_name: str) -> list[np.ndarray]:
        """Return list of world-frame (x,y,z) for every GT instance of this class."""
        geom_ids = self._class_to_geom_ids.get(class_name, [])
        return [np.array(self._data.geom_xpos[gid], dtype=np.float64) for gid in geom_ids]

    def expected_count(self, class_name: str) -> int:
        return len(self._class_to_geom_ids.get(class_name, []))

    def all_classes(self) -> list[str]:
        return list(self._class_to_geom_ids.keys())
```

### Example 2: Draft `data/scenes/scene_office1_gt.yaml` (CONTEXT D-08 — actual body names)
```yaml
# COCO class name -> list of MuJoCo body names representing instances of that class.
# Body names verified live via mj_name2id against scene_office1.xml.
# Coordinates below are FYI (data.geom_xpos values from mj_forward(model, data)
# at construction; updated per-step by MuJoCo).
#
# CRITICAL: extractor reads data.geom_xpos[first_geom_of_body], NOT data.xpos —
# all bodies in this scene have body-origin at world (0,0,0).

chair:
  - body_BezierCurve_009_SwivlChair                         # geom_xpos ~ (0.68, -2.44, 0.51)
  - body_BezierCurve_009_SwivlChair_BLACK                   # geom_xpos ~ (0.71, 0.07, 0.72)
  - body_Chocofur_free_12_plastic_cycles_013_BrownChair     # geom_xpos ~ (-0.36, 7.99, 0.47)

dining_table:
  - body_Plane_029_meetingTable                             # geom_xpos ~ (-0.35, 7.99, 0.55)
  - body_Cube_013_BigWhiteTable                             # geom_xpos ~ (1.30, 0.89, 0.59)
  - body_Cube_007_woodenDesk                                # geom_xpos ~ (-0.06, -6.13, 0.45)
  - body_Cube_017_SmallWhiteTable_low_001                   # geom_xpos ~ (1.87, -1.51, 0.50)

# Optional / lower-confidence COCO mappings:
# - "tv" maps to body_Plane_037_Desktop (geom_xpos ~ (0.59, -1.91, 0.94)) only if
#   COCO class id 62 ("tv") is desired; YOLOv11 may also fire class 63 ("laptop").
#   Recommend deferring tv mapping until SC#2 is green for chair.
# - "couch", "potted plant", "book", "vase", "cup", "bottle" — none present in
#   this scene (verified by full geom inventory).
```

### Example 3: Coordinator pump in `_send_viz_update` (the integration site)
```python
# Source: src/coordination/coordinator.py:644-733 — extend _send_viz_update
# This is the SAME method that already pumps SLAM metrics into self._viz.metrics_tracker.

# After the existing SLAM tracker block (line ~705) and BEFORE the self._viz.update(...) call:

if hasattr(self._viz, "detection_metrics_tracker") and self._detector_pool is not None:
    det_tracker = self._viz.detection_metrics_tracker
    det_export = self._viz.detection_export
    sim_now = float(frames[robot_ids[0]].sim_time)  # all robots share sim clock

    for rid in robot_ids:
        worker = self._detector_pool._workers[rid]  # noqa: SLF001 — until pool exposes accessor
        latest = worker.latest()
        inspect = worker.inspect()
        backend_metrics = worker.detector.get_metrics()  # see Pitfall 3 — needs property

        det_tracker.record_frame(
            robot_id=rid,
            sim_now=sim_now,
            latest=latest,
            inspect=inspect,
            backend_metrics=backend_metrics,
        )

        if latest is not None and latest.items:
            for obb in latest.items:
                det_export.append(
                    obb,
                    robot_id=rid,
                    backend_id=backend_metrics.get("backend_name", "unknown"),
                    capture_timestamp=latest.capture_timestamp,
                )

    # GT extractor pump (DET-METRICS-02): center_error + per_class_recall
    if hasattr(self._viz, "gt_extractor") and self._viz.gt_extractor is not None:
        det_tracker.record_gt_match(
            sim_now=sim_now,
            extractor=self._viz.gt_extractor,
            latest_per_robot={rid: self._detector_pool._workers[rid].latest() for rid in robot_ids},
        )
```

### Example 4: `WebStreamingViz._update_stats` extension (additive)
```python
# Source: backend/web/streaming_viz.py:367-396 — extend the payload dict
def _update_stats(self, robot_data, total_coverage, merge_count):
    elapsed = time.monotonic() - self._start_time
    robots = {...}  # unchanged

    # SLAM metrics (existing)
    metrics_payload = self._metrics_tracker.get_stats_payload()

    # Detection metrics (NEW — additive)
    detection_payload = self._detection_metrics_tracker.get_stats_payload()
    # detection_payload = {"detection_metrics": {<rid>: {...}}, "detection_history": {<rid>: {...}}}

    payload = {
        "total_coverage": total_coverage,
        "merge_count": merge_count,
        "elapsed": elapsed,
        "robots": robots,
        "slam_metrics": metrics_payload["slam_metrics"],
        "baseline": metrics_payload["baseline"],
        "metric_history": metrics_payload["metric_history"],
        "detection_metrics": detection_payload["detection_metrics"],
        "detection_history": detection_payload["detection_history"],
    }

    # Runtime guard — D-10 belt-and-suspenders
    forbidden = {"mAP", "map_50", "map_75"}
    leaked = forbidden.intersection(_recursively_flatten_keys(payload))
    assert not leaked, f"Forbidden mAP-family keys in stats payload: {leaked}"

    self._message_queue.append({"type": STATS, "payload": payload})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single global metrics dict | Per-robot ring-buffer trackers | Phase v2.0 13-01 | Pattern locked; mirror it for detection |
| Inheritance for shared metrics infra | Sibling classes with no shared base | CONTEXT D-01 | Detection + SLAM trackers share zero fields; inheritance would be artifact |
| Substring class-name matching against body names | Explicit YAML mapping file | CONTEXT D-08 | Auto-generated body names defeat substring; mapping file is the contract |
| Detection metric data lost on coordinator restart | Disk-backed JSONL session export | CONTEXT D-11 | Survives crashes; supports arbitrarily long sessions |
| `data.xpos` for body GT | `data.geom_xpos` for body GT (this scene) | Phase 6 finding F1 | Bodies declared without `pos=` have origin at world (0,0,0); visible position is in geom_xpos |
| OWLv2 in real-time pipeline | OWLv2 dropped from pipeline | Phase 5 D-10 (2026-04-15) | Phase 6 SC#5 literal is stale; covers YOLOv11 + RT-DETRv2 + BoxeR only |

**Deprecated/outdated:**
- `tests/smoke/test_detector_rss.py` — Phase 6 supersedes via `tests/integration/test_rss_smoke_backends.py` with explicit honest-skip. Recommend deleting the old file once the new one passes; or keep it as a smoke-tier (and the integration one as the parametrized full version).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `mujoco.mjtObj.mjOBJ_BODY` enum import path is stable across mujoco 3.0 → 3.6 | Stack | LOW — verified live on 3.6.0; bindings stable since 3.0 release |
| A2 | `data.geom_xpos` is updated by `mj_forward` / `mj_step` with no extra call needed | Pitfalls F1 / Example 1 | LOW — MuJoCo bindings doc states geom_xpos is computed during forward kinematics |
| A3 | FastAPI `StreamingResponse` does not buffer chunks under default uvicorn middleware | Pattern 3 | MEDIUM — most middlewares pass through; if a client-side proxy buffers, switch to `media_type="text/plain"` to defeat content-type sniffing. Verify in the integration test |
| A4 | `git grep` is available in CI (not just `grep`) | Pattern 5 | LOW — the repo is a git repo, and standard CI uses git checkout; `git grep` ships with git |
| A5 | `tempfile.gettempdir()` returns a writable path on all targeted platforms | Don't Hand-Roll | LOW — Python stdlib guarantees a writable temp dir; if it's not, the `open()` call raises immediately |
| A6 | The "first geom of a body" heuristic identifies the visible mesh, not a collision proxy | Example 1 | MEDIUM — for `scene_office1.xml` the first geom IS the visible mesh (verified live: SwivlChair body 1's first geom is `geom_BezierCurve_009_SwivlChair`, the mesh, not a `_convex_*` collider — convex colliders sit in their own bodies starting at line 1320). Document this assumption; a future scene with collision-first ordering would need a `geom_type == mjGEOM_MESH` filter |
| A7 | DetectorWorker and pool can expose `worker.detector` and `pool.workers` properties without touching the worker contract | Pitfall 3 | LOW — both are pure read-only accessors; no concurrency contract change |
| A8 | `frames[rid].sim_time` is in float seconds, monotonic per session | Pitfall 4 / Example 3 | LOW — verified `multi_bridge.py:402` computes it as `_step_count * _dt`; monotonic by construction |

## Open Questions (RESOLVED)

> All questions resolved during planning revision 2026-04-15. Each entry names the plan(s) that implement the recommendation.

1. **`data.xpos` vs `data.geom_xpos` — confirm with planner before Plan 03 ships**
   - What we know: All bodies in scene_office1.xml have body-origin at world (0,0,0); CONTEXT D-08 names `data.xpos`.
   - What's unclear: Whether the planner wants to (a) silently switch the extractor to `geom_xpos`, (b) escalate as a CONTEXT amendment, or (c) patch `scene_office1.xml` to add `pos=` to each labeled body (pulled from `geom_xpos` once at script time).
   - Recommendation: (a) — extractor uses `data.geom_xpos`. Document in module docstring. The mapping file already lists body names; no contract change.
   - **RESOLVED:** Plan 05 implements `MuJoCoGTExtractor.gt_positions` using `data.geom_xpos[first_geom_of_body]` (RESEARCH F1). Module docstring references D-08, D-09, F1. Acceptance criteria grep-verify `data.geom_xpos` present and `data.xpos[` absent.

2. **`MuJoCoGTExtractor` ownership: who holds the reference?**
   - What we know: CONTEXT canonical_refs says "extractor reuses scene_builder's mjModel handle"; bridge owns `_model` + `_data`; coordinator drives the per-tick pump.
   - What's unclear: Is the extractor instantiated by `WebStreamingViz` (with bridge refs threaded in) or by `Coordinator.set_viz`?
   - Recommendation: `Coordinator.set_viz` — it already has `_bridge` and `_viz` in scope, and the extractor needs both.
   - **RESOLVED:** Plan 10 coordinator-init task wires `streaming_viz.attach_gt_extractor(Path("data/scenes/scene_office1_gt.yaml"), bridge.mj_model, bridge.mj_data)` at bootstrap. `WebStreamingViz.attach_gt_extractor` (Plan 08) stores the extractor with graceful-degradation try/except. Plan 10 also exposes `MultiBridge.mj_model` / `mj_data` public accessors if they're private (RESEARCH Pitfall 8). Integration test in Plan 10 asserts `streaming_viz.gt_extractor is not None` and `"chair" in streaming_viz.gt_extractor.all_classes()` post-bootstrap.

3. **Per-class jitter aggregation: max vs mean?**
   - What we know: D-03 says "UI shows the aggregate `max` across classes per robot".
   - What's unclear: Edge case where one class has 1 datapoint (stddev = 0) and another has 30; `max` masks the noisy class.
   - Recommendation: `max` per CONTEXT; planner's discretion if "median across classes with ≥3 datapoints" is preferred. Document in panel cell tooltip.
   - **RESOLVED:** Plan 04 `DetectionMetricsTracker.record_frame` computes per-class stddev and emits `jitter_m = max(class_jitters)` per CONTEXT D-03. Test 4 (`test_nn_jitter_within_gate`) covers the multi-class max aggregation path.

4. **JSONL writer file rotation timing on `reset_cloud_tracking()`**
   - What we know: D-12 says new UUID on `reset_cloud_tracking`; old file NOT deleted.
   - What's unclear: Can the open `_fp` be mid-write when reset fires? Pump runs on coordinator thread; reset is called via REST handler thread.
   - Recommendation: Lock-protect rotation. `DetectionExportWriter.rotate(new_session_id)` acquires `self._lock`, closes old fp, opens new fp. Single `threading.Lock`.
   - **RESOLVED:** Plan 06 implements `DetectionExportWriter.rotate(new_session_id)` with `threading.Lock`-protected fp swap. Plan 08 `WebStreamingViz.reset_cloud_tracking` calls `self._detection_export.rotate(new_session_id)` exactly once per reset. Tracker state is intentionally preserved (CONTEXT D-12).

5. **The 0.5 m jitter gate vs 1.0 m center_error gate semantic divergence**
   - What we know: D-03 jitter gate = 0.5 m, D-09 center_error gate = 1.0 m. Different gates for different purposes.
   - What's unclear: A detection within 0.7 m of a tracked center counts toward jitter (> 0.5 m gate fails) but counts as a correct GT instance (< 1.0 m gate passes). Could leak inconsistent semantics into the panel.
   - Recommendation: Document explicitly in panel cell help-text. CONTEXT discretion allows tuning these independently per scene; for `scene_office1.xml` the chair geom_xpos values are >2 m apart so neither gate has cross-class collision risk.
   - **RESOLVED:** Plan 04 uses `_JITTER_GATE_M = 0.5` constant (D-03) for jitter NN matching. Plan 05 `MuJoCoGTExtractor.match_detection` uses `_DEFAULT_GATE_M = 1.0` (D-09) for GT correctness matching. Both constants are documented in module docstrings with their decision IDs so downstream tuning by scene does not collide.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.12 | — |
| mujoco | DET-METRICS-02 | ✓ | 3.6.0 | — |
| numpy | DET-METRICS-01 | ✓ | (per pyproject ≥1.26) | — |
| scipy | None directly | ✓ | (per pyproject ≥1.15) | — |
| PyYAML | DET-METRICS-02 | ✓ (system 6.0.3) | 6.0.3 | Add to pyproject `perception` extra to declare |
| fastapi | DET-METRICS-04 | ✓ | 0.135.2 | — |
| psutil | DET-METRICS-05 | ✓ | 7.2.2 | Existing skipif handles missing case |
| ultralytics (YOLOv11) | DET-METRICS-05 | ✓ (assumed from Phase 1) | (per pyproject ≥8.4.24) | — |
| `models/rtdetrv2/<sha>/model.onnx` | DET-METRICS-05 (rtdetrv2 row) | unknown — may need `make download-models-rtdetrv2` | — | Honest-skip per D-15 |
| `subprocess_venvs/boxer/.ready` | DET-METRICS-05 (boxer row) | unknown — may need `bash scripts/setup_boxer_subprocess.sh` | — | Honest-skip + `slow_boxer` mark per D-15 |
| `tests/contract/` directory | DET-METRICS-03 | ✗ — does not exist | — | Wave 0 task creates it (with `__init__.py`) |
| Coordinator running with detector pool | All integration tests | ✓ via existing `tests/integration/test_pool_end_to_end.py` template | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback / scaffolding:**
- `tests/contract/` directory + `__init__.py` — Wave 0 scaffold.
- Optional: `models/rtdetrv2/...` and `subprocess_venvs/boxer/.ready` are NOT phase-blocking — honest-skip per D-15.

## Validation Architecture

> Nyquist validation enabled (config.json `nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-timeout 2.4 + pytest-asyncio 0.23 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (markers: `slow_boxer`, `network`) |
| Quick run command | `uv run pytest tests/metrics/ tests/contract/ -x` |
| Full suite command | `uv run pytest tests/ -x --ignore=tests/integration/test_rss_smoke_backends.py` (skip RSS for fast loop; run separately) |
| RSS-only command | `uv run pytest tests/integration/test_rss_smoke_backends.py -m "not slow_boxer" -v` |
| Slow tier (BoxeR) | `uv run pytest tests/integration/test_rss_smoke_backends.py -m slow_boxer -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-METRICS-01 | Tracker computes p50/p95 from a known sequence | unit | `uv run pytest tests/metrics/test_detection_metrics_tracker.py::test_p50_p95_against_known_sequence -x` | ✗ Wave 0 |
| DET-METRICS-01 | Ring-buffer wraps at history_size | unit | `uv run pytest tests/metrics/test_detection_metrics_tracker.py::test_ring_buffer_eviction -x` | ✗ Wave 0 |
| DET-METRICS-01 | Empty-state defaults are sane (zeros, no NaN) | unit | `uv run pytest tests/metrics/test_detection_metrics_tracker.py::test_empty_state_no_nan -x` | ✗ Wave 0 |
| DET-METRICS-01 | Nearest-neighbor jitter matches within 0.5 m gate | unit | `uv run pytest tests/metrics/test_detection_metrics_tracker.py::test_nn_jitter_within_gate -x` | ✗ Wave 0 |
| DET-METRICS-01 | Stats payload has expected detection_metrics + detection_history shape | unit | `uv run pytest tests/metrics/test_detection_metrics_tracker.py::test_stats_payload_shape -x` | ✗ Wave 0 |
| DET-METRICS-01 | Frontend panel renders detection rows when detectionPerRobot populated | manual / vitest | (frontend tests use vitest from Phase 3) | manual confirm |
| DET-METRICS-02 | `mj_name2id` resolves chair body in fixture scene | unit | `uv run pytest tests/metrics/test_mujoco_gt.py::test_resolves_chair_body -x` | ✗ Wave 0 |
| DET-METRICS-02 | `data.geom_xpos` fetch matches expected world coordinates | unit | `uv run pytest tests/metrics/test_mujoco_gt.py::test_geom_xpos_world_coords -x` | ✗ Wave 0 |
| DET-METRICS-02 | Missing body in mapping raises at construction (fail-fast) | unit | `uv run pytest tests/metrics/test_mujoco_gt.py::test_missing_body_raises -x` | ✗ Wave 0 |
| DET-METRICS-02 | center_error_m math against synthetic detection at known offset | unit | `uv run pytest tests/metrics/test_mujoco_gt.py::test_center_error_known_offset -x` | ✗ Wave 0 |
| DET-METRICS-02 | per_class_recall denominator = mapped instances | unit | `uv run pytest tests/metrics/test_mujoco_gt.py::test_per_class_recall_denominator -x` | ✗ Wave 0 |
| DET-METRICS-03 | `mAP` does not appear in `frontend/src/` | contract | `uv run pytest tests/contract/test_no_map_in_ui.py -x` | ✗ Wave 0 (also creates `tests/contract/__init__.py`) |
| DET-METRICS-03 | Stats payload runtime guard rejects mAP keys | unit | `uv run pytest tests/contract/test_no_map_in_payload.py -x` | ✗ Wave 0 |
| DET-METRICS-03 | `--labeled-eval-set` flag raises NotImplementedError | unit | `uv run pytest tests/test_main_args.py::test_labeled_eval_set_reserved -x` | ✗ Wave 0 |
| DET-METRICS-04 | JSONL file round-trips through `OrientedBox3D.from_wire` | integration | `uv run pytest tests/integration/test_detections_export.py::test_round_trip_30_frames -x --timeout=120` | ✗ Wave 0 |
| DET-METRICS-04 | `GET /api/detections/export` returns 200 + `application/x-ndjson` | integration | `uv run pytest tests/integration/test_detections_export.py::test_endpoint_streams_ndjson -x --timeout=60` | ✗ Wave 0 |
| DET-METRICS-04 | Endpoint returns 404 when no session has emitted yet | integration | `uv run pytest tests/integration/test_detections_export.py::test_no_session_404 -x` | ✗ Wave 0 |
| DET-METRICS-04 | Writer survives SIGKILL (line-buffered flush) | integration | `uv run pytest tests/integration/test_detections_export.py::test_sigkill_preserves_lines -x --timeout=30` | ✗ Wave 0 (manual sigkill via subprocess) |
| DET-METRICS-05 | RSS growth ≤ 200 MB over 100 inferences (yolov11) | integration | `uv run pytest tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[yolov11] -x --timeout=180` | ✗ Wave 0 |
| DET-METRICS-05 | RSS growth ≤ 200 MB over 100 inferences (rtdetrv2) | integration | `uv run pytest tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[rtdetrv2] -x --timeout=300` | ✗ Wave 0 (skips if model artifact missing) |
| DET-METRICS-05 | RSS growth ≤ 200 MB over 100 inferences (boxer) | integration | `uv run pytest tests/integration/test_rss_smoke_backends.py::test_rss_growth_capped[boxer] -m slow_boxer --timeout=900` | ✗ Wave 0 (skips if `subprocess_venvs/boxer/.ready` missing) |

### Sampling Rate
- **Per task commit:** quick run command (unit + contract) → < 30s expected.
- **Per wave merge:** full suite minus RSS — < 5 min.
- **Per phase gate:** RSS fast tier (yolov11 + rtdetrv2) included; BoxeR slow tier on opt-in.

### Wave 0 Gaps
- [ ] `tests/metrics/__init__.py` — covers DET-METRICS-01, DET-METRICS-02
- [ ] `tests/metrics/test_detection_metrics_tracker.py` — covers DET-METRICS-01
- [ ] `tests/metrics/test_mujoco_gt.py` — covers DET-METRICS-02 (use `tests/perception/fixtures/scene_rotated_chair.xml` for unit; this fixture has explicit `pos="0 0 0.45"` so xpos works there)
- [ ] `tests/contract/__init__.py` — directory does not exist yet
- [ ] `tests/contract/test_no_map_in_ui.py` — covers DET-METRICS-03 (grep test)
- [ ] `tests/contract/test_no_map_in_payload.py` — covers DET-METRICS-03 (runtime guard test)
- [ ] `tests/integration/test_detections_export.py` — covers DET-METRICS-04
- [ ] `tests/integration/test_rss_smoke_backends.py` — covers DET-METRICS-05 (parametrized)
- [ ] `data/scenes/scene_office1_gt.yaml` — committed source mapping file
- [ ] `pyproject.toml` `[project.optional-dependencies].perception` += `PyYAML>=6.0`

*(No new framework install — pytest already present per pyproject.)*

## Security Domain

> `security_enforcement` not declared in config; default treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 6 adds no new auth surfaces; existing Argus REST is unauthenticated localhost |
| V3 Session Management | partial | UUID4 session IDs scoped to coordinator boot; not auth sessions, just bucket keys for the JSONL file path. No leakage risk because session_id is exposed via the export endpoint anyway |
| V4 Access Control | no | All Argus REST is unauthenticated localhost; not in scope to change |
| V5 Input Validation | yes | `GET /api/detections/export` takes no path parameter; session_id is server-side only — no path traversal risk. Mapping YAML is loaded with `yaml.safe_load` (no code execution path) |
| V6 Cryptography | no | No crypto in Phase 6 |

### Known Threat Patterns for {Python + FastAPI + MuJoCo}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via filename injection in StreamingResponse | Tampering | session_id is server-generated UUID4 — no user input on the path; verified by D-13 endpoint signature having no path param |
| YAML deserialization RCE | Tampering / EoP | Use `yaml.safe_load`, NEVER `yaml.load` without a Loader. Mapping file is committed source under repo control — not user-supplied at runtime |
| Unbounded JSONL file growth → disk DoS | DoS | CONTEXT D-12 acknowledges and accepts: tmp cleanup is the user's problem. Document in CLAUDE.md / README |
| Fail-fast on missing body raises uncaught exception → crash on coordinator boot | DoS | Caught at `MuJoCoGTExtractor.__init__`, surfaces in main.py log; coordinator can boot without GT extractor (graceful degradation: if extractor construction fails, log warning and don't compute center_error / per_class_recall — frontend simply shows N/A). Plan should include a try/except wrapper in the WebStreamingViz init path |
| Subprocess-bridge crash during RSS smoke loop | DoS (test only) | Existing `BridgeHangError / SubprocessDiedError` typed-except handling in `DetectorWorker._loop` already shields the worker thread. Smoke test catches both and reports as test failure (not silent skip) |
| `git grep` shells out — argv injection? | Tampering | argv is hardcoded; cwd is `Path(__file__).resolve().parents[2]` (no string concat) — safe |

## Sources

### Primary (HIGH confidence)
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/06-detection-metrics-and-mujoco-gt/06-CONTEXT.md` — locked decisions D-01..D-17
- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` — DET-METRICS-01..05 + Phase 5 D-10 OWLv2-drop note
- `/home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md` Phase 6 §132-139 — 5 success criteria + research flag `light`
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` — current position + Phase 6 blocker note ("requires scene inventory")
- `/home/prannayag/pragnition/robotics/argus/src/metrics/metrics_tracker.py:12-167` — template for `DetectionMetricsTracker`
- `/home/prannayag/pragnition/robotics/argus/backend/web/streaming_viz.py:48-396` — extension point for stats payload
- `/home/prannayag/pragnition/robotics/argus/src/perception/worker.py:107-349` — DetectorWorker contract (`_detector` is private; no public accessor — Pitfall 3)
- `/home/prannayag/pragnition/robotics/argus/src/perception/types.py:87-251` — `OrientedBox3D.to_wire()` + `Detections3D.capture_timestamp` semantics
- `/home/prannayag/pragnition/robotics/argus/src/perception/protocol.py:80-87` — `DetectorProtocol.get_metrics()` recommended keys
- `/home/prannayag/pragnition/robotics/argus/src/coordination/coordinator.py:644-747` — `_send_viz_update` integration site (NOT main.py — Finding F2)
- `/home/prannayag/pragnition/robotics/argus/src/perception/backends/boxer_backend.py:259-272` — percentile reference impl
- `/home/prannayag/pragnition/robotics/argus/src/bridge/multi_bridge.py:42-180` — bridge model/data ownership; `mj_name2id` usage pattern
- `/home/prannayag/pragnition/robotics/argus/data/scenes/scene_office1.xml` — body inventory (lines 1257-1317 are the labeled bodies; 1320+ are convex collision proxies)
- `/home/prannayag/pragnition/robotics/argus/tests/perception/fixtures/scene_rotated_chair.xml` — unit-test fixture with proper `pos="0 0 0.45"` chair
- `/home/prannayag/pragnition/robotics/argus/tests/smoke/test_detector_rss.py:1-114` — current RSS smoke test (template for D-15 generalization)
- `/home/prannayag/pragnition/robotics/argus/frontend/src/stores/metricsStore.ts:1-87` — Zustand store shape + `updateAllMetrics` single-set invariant
- `/home/prannayag/pragnition/robotics/argus/frontend/src/components/MetricsPanel.tsx:1-251` — Live tab structure to extend
- `/home/prannayag/pragnition/robotics/argus/frontend/src/utils/messageTypes.ts:48-75` — `SlamMetrics` + `MetricHistory` shapes to mirror
- `/home/prannayag/pragnition/robotics/argus/backend/web/detector_routes.py:22-244` — REST route module pattern
- `/home/prannayag/pragnition/robotics/argus/pyproject.toml` — current dep state (PyYAML to add)
- Live mujoco probe (venv 3.6.0): `mj_name2id(MjModel, type, name) -> int`; -1 on not-found; `mjOBJ_BODY = 1`

### Secondary (MEDIUM confidence)
- `[CITED: fastapi.tiangolo.com/advanced/custom-response/#streamingresponse]` — StreamingResponse pattern (training data; matches FastAPI 0.135.2 signature verified via venv `from fastapi.responses import StreamingResponse`)
- `[CITED: docs.pytest.org/en/latest/how-to/parametrize.html#pytest-mark-parametrize]` — parametrize + nested marks pattern (`pytest.param(..., marks=...)`)
- `[CITED: mujoco.readthedocs.io/en/latest/python.html#mjmodel-and-mjdata]` — `data.geom_xpos` is computed during `mj_forward`; updated each `mj_step`

### Tertiary (LOW confidence)
- `[ASSUMED]` PyYAML version 6.0.3 will continue to be installed; no recent breaking changes
- `[ASSUMED]` `git grep` exit codes: 0 = match, 1 = no match, ≥2 = error (matches GNU grep convention; verify behavior in test setup)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dep verified live in venv (mujoco 3.6.0, fastapi 0.135.2, psutil 7.2.2, PyYAML 6.0.3); only PyYAML needs explicit declaration in pyproject
- Architecture: HIGH — patterns verified against existing codebase files; trackers / writer / extractor each have a 1:1 template (MetricsTracker, JSONL pattern, multi_bridge mj_name2id usage)
- Pitfalls: HIGH (F1 verified live with the actual scene; F2/F3 verified by reading exact line numbers; F4 verified by absence of `OWLv2Backend` in `src/perception/backends/`)
- Validation Architecture: HIGH — pytest infra exists, markers declared, only test files + `tests/contract/` directory missing

**Key cross-cutting findings (all flagged for planner attention):**

- **F1 (CRITICAL):** `data.xpos` returns (0,0,0) for every labeled body in `scene_office1.xml`. Use `data.geom_xpos[first_geom_of_body]`. Verified live values for all 8 candidate bodies provided in Example 2's mapping file draft. **MUST resolve before Plan 03 (mujoco_gt).** Recommendation: extractor reads `geom_xpos` silently; document in module docstring; CONTEXT D-08 wording is non-blocking because it doesn't override implementation choice within Claude's discretion.

- **F2 (MEDIUM):** Coordinator pump site is `src/coordination/coordinator.py::_send_viz_update` (line 644), NOT `src/main.py`. CONTEXT D-17 says "src/main.py or the per-robot coordinator" — Coordinator wins. Plan task should add the new pump block alongside the existing SLAM block (line 696-733).

- **F3 (LOW):** `DetectorWorker.detector` does not exist as a property (private `_detector`). Add 3-line `@property` to worker, OR add `pool.get_metrics(rid)` accessor. Recommend the property — matches the pattern of `metrics_tracker` getter on `WebStreamingViz`.

- **F4 (LOW — documented contradiction):** ROADMAP.md Phase 6 SC#5 lists "YOLOv11, RT-DETRv2, OWLv2, BoxeR" as RSS smoke targets, but Phase 5 D-10 (2026-04-15) DROPPED OWLv2 from the pluggable pipeline. REQUIREMENTS.md DET-MODELS-04 explicitly marks it dropped (line 27). The parametrized smoke test covers `["yolov11", "rtdetrv2", "boxer"]` per CONTEXT D-15 — three backends, not four. **Recommendation:** Proceed with three backends; reference Phase 5 D-10 in the test docstring; do NOT amend ROADMAP SC#5 (the supersession is already documented in REQUIREMENTS.md). Planner notes this in the smoke-test plan task description.

- **F5 (LOW):** `tests/contract/` directory does not exist. Wave 0 task creates `tests/contract/__init__.py` alongside the first contract test file.

- **F6 (LOW):** PyYAML is system-installed (6.0.3) but not declared in `pyproject.toml`. Add to `[project.optional-dependencies].perception` to lock it explicitly.

- **F7 (LOW):** `MuJoCoGTExtractor` failure-mode: D-08 says "fail-fast on missing body at construction time". A bad mapping file would crash coordinator boot. Recommend planner wrap construction in a try/except in `WebStreamingViz`/`Coordinator.set_viz`, log error, set `gt_extractor = None`, and let the panel show "GT N/A". CONTEXT D-08 is non-prescriptive about graceful degradation — Claude's discretion applies.

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days — phase scope locked, codebase moves slowly, mujoco 3.x bindings stable)
