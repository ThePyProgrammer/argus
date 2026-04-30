---
phase: 06-detection-metrics-and-mujoco-gt
verified: 2026-04-15T16:57:00Z
status: human_needed
score: 5/5 success criteria verified (automated)
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Live 2-robot MetricsPanel render cadence"
    expected: "All 9 detection rows (infer p50, infer p95, det/frame, conf, queue, fresh, jitter, err m, recall) refresh live per-robot without React console errors; fresh traffic-light transitions #e0e0e0 → #f1c40f → #e74c3c as capture_timestamp ages past 1s / 3s"
    why_human: "30 Hz WS stats emission + per-row DOM update cadence cannot be observed from vitest shape tests; needs browser + live coordinator"
  - test: "center_error_m reads [0.00, 0.30] m for chair on scene_office1"
    expected: "MetricsPanel err m row shows a small positive value (not --, not 0) once a robot drives within camera range of SwivlChair or BrownChair"
    why_human: "End-to-end MuJoCo tick + YOLOv11 detection + GT match chain; needs model weights + running sim, not in CI budget"
  - test: "curl /api/detections/export | jq round-trip"
    expected: "`curl http://localhost:8000/api/detections/export -o /tmp/dets.jsonl && jq -c '.obb.class_name' /tmp/dets.jsonl | sort | uniq -c` returns non-empty class_name histogram"
    why_human: "MIME / Content-Disposition / chunked transfer behavior across the wire (integration test uses TestClient which bypasses some header semantics)"
---

# Phase 6: detection-metrics-and-mujoco-gt — Verification Report

**Phase Goal:** Honest, MuJoCo-grounded detection metrics — per-robot inference latency, 3D jitter, detection freshness, center_error against GT body positions, per-class recall, and session export. Forbid `mAP` without a committed labeled set.

**Verified:** 2026-04-15
**Status:** human_needed (all 5 SC automated checks green; 3 items require live-runtime human verification per 06-VALIDATION.md §Manual-Only)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Success Criteria Verdict

| #  | Criterion                                                                 | Status    | Evidence |
|----|---------------------------------------------------------------------------|-----------|----------|
| 1  | MetricsPanel live per-robot 7-metric surface (SC#1 / DET-METRICS-01)      | PASS      | `src/metrics/detection_metrics_tracker.py:96-175` writes all 7 live keys + 5 histories per tick; `backend/web/streaming_viz.py:491-503` forwards `detection_metrics` + `detection_history` in stats payload; `src/coordination/coordinator.py:802-823` calls `record_frame` per robot per tick with `sim_now` + `latest` + `inspect` + `backend_metrics`; `frontend/src/components/MetricsPanel.tsx:216-277` renders 7 SC#1 rows (`infer p50/p95`, `det/frame`, `conf`, `queue`, `fresh` with traffic-light, `jitter`). |
| 2  | MuJoCo GT chain (chair center_error_m + per_class_recall) (SC#2 / DET-METRICS-02) | PASS | `data/scenes/scene_office1_gt.yaml:9-12` maps `chair` → 3 real bodies; `src/metrics/mujoco_gt.py:80-101` reads `data.geom_xpos` per F1 fix, resolves via `mj_name2id`, fails-fast on missing body; `src/coordination/coordinator.py:834-846` calls `match_detection` and consumes its return via `record_gt_match` (NOT discarded — revision 2026-04-15 fix); `detection_metrics_tracker.py:180-201 + 236-254` accumulates per-class `center_error_m` ring (maxlen 60) + recall; `MetricsPanel.tsx:266-273` renders `err m` + `recall` rows per Amendment 2026-04-15. Integration test `tests/integration/test_gt_extractor_attach.py` asserts every body in the YAML resolves against the production scene. |
| 3  | `mAP` forbidden in UI + CLI reservation (SC#3 / DET-METRICS-03)           | PASS      | `tests/contract/test_no_map_in_ui.py:49-67` runs `git grep mAP\|map_50\|map_75\|mean_average_precision -- frontend/src/ :!.../__tests__/**` (4 parametrized tokens, all returncode == 1 == no match); runtime guard `backend/web/streaming_viz.py:45-71 + 508` recursively rejects forbidden keys at any depth (exercised by `tests/contract/test_no_map_in_payload.py` — 7 tests green incl. nested under `detection_gt_metrics`); CLI reservation `src/main.py:148-156 + 661-664` raises `NotImplementedError` on `--labeled-eval-set`. All three legs of D-10 present. |
| 4  | `GET /api/detections/export` streams JSONL lossless round-trip (SC#4 / DET-METRICS-04) | PASS | Route registered: `backend/web/server.py:88-91` mounts `export_router`; handler `backend/web/detector_routes.py:266-299` returns `StreamingResponse(generator, media_type="application/x-ndjson")` with `Content-Disposition: attachment; filename="detections-<session>.jsonl"` chunked at 65536 bytes; writer `src/metrics/detection_export.py:109-133` calls `obb.to_wire()` exclusively (Phase 1 D-10 quaternion invariant preserved) and line-buffered append; 3 integration tests in `tests/integration/test_detections_export.py` cover 404-empty, round-trip `OrientedBox3D.from_wire == original` to ±1e-6 across 30 real OBBs, and Content-Disposition session-id embedding. |
| 5  | RSS smoke ≤200 MB over 100 inferences per backend (SC#5 / DET-METRICS-05) | PASS (scope revised per Phase 5 D-10) | `tests/integration/test_rss_smoke_backends.py:96-123` parametrizes exactly 3 backends: `yolov11`, `rtdetrv2` (honest-skip if ONNX missing), `boxer` (`slow_boxer` mark + honest-skip if venv missing). `OWLv2` is explicitly absent from the parametrize ids — lines 6-9 document the Phase 5 D-10 supersession. RSS threshold `< 200 * 1024 * 1024` enforced at line 154. Pitfall 7 measurement order (warmup → gc → rss_before → 100 inferences → gc → rss_after) respected. OWLv2 scope deviation is covered by the roadmap's own supersession note — SC#5 as-stated is satisfied modulo the drop. |

**Score:** 5/5 success criteria verified against codebase evidence.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/metrics/detection_metrics_tracker.py` | DetectionMetricsTracker class (live metrics + GT accumulator) | VERIFIED | 283 lines; live `record_frame` + SC#2 `record_gt_match` / `reset_gt` + `get_stats_payload` emits 3 keys |
| `src/metrics/mujoco_gt.py` | MuJoCoGTExtractor with `data.geom_xpos` + `mj_name2id` + `match_detection` | VERIFIED | 152 lines; F1 fix at line 92-100 (iterates `geom_bodyid` to find first geom); `yaml.safe_load` at line 64 (T-6-04); fail-fast on missing body line 83-88 |
| `src/metrics/detection_export.py` | DetectionExportWriter (tempfile + UUID4 + lock + to_wire) | VERIFIED | 153 lines; `tempfile.gettempdir()` default base_dir; `threading.Lock` guards `append` + `rotate`; line-buffered append mode |
| `backend/web/streaming_viz.py` | Payload composition + mAP runtime guard + gt_extractor attach | VERIFIED | `_assert_no_map_keys` at lines 53-71 (recursive, handles dicts + lists); `attach_gt_extractor` at lines 149-172 (graceful degradation on ValueError/FileNotFoundError); `_update_stats` at 491-508 forwards all 3 detection keys |
| `backend/web/detector_routes.py` | GET /api/detections/export via export_router | VERIFIED | `export_router` prefix `/api/detections` (line 33), handler at 266-299 with `StreamingResponse` + correct MIME + 404 on missing file |
| `src/coordination/coordinator.py` | Per-tick pump using `sim_now`, consume `match_detection` via `record_gt_match` | VERIFIED | `_send_viz_update` (F2 finding) at 802-846; calls `worker.detector.get_metrics()` (F3 public property); uses `frames[robot_ids[0]].sim_time` not `time.time()` (Pitfall 4); `_gid, err = gt_extractor.match_detection(...)` consumed by `det_tracker.record_gt_match` |
| `src/main.py` | `--labeled-eval-set` reserved with NotImplementedError | VERIFIED | CLI at 148-156; raise at 661-664 BEFORE heavy init (deterministic subprocess CLI test) |
| `frontend/src/components/MetricsPanel.tsx` | 9-row detection subsection (7 SC#1 + 2 SC#2 rows) | VERIFIED | Detection separator at 216-229; 7 SC#1 rows at 235-263 (with fresh traffic-light); `err m` + `recall` rows at 266-273 per Amendment 2026-04-15; `aggregateCenterError` / `aggregateRecall` helpers at 53-67 |
| `frontend/src/stores/metricsStore.ts` | 3 new slices + 6-arg `updateAllMetrics` | VERIFIED | `detectionPerRobot` / `detectionHistory` / `detectionGtPerRobot` declared at 28-32; 6-arg setter at 83-90 preserves single-re-render invariant |
| `frontend/src/utils/messageTypes.ts` | DetectionMetrics + DetectionMetricHistory + DetectionGtMetrics types | VERIFIED | Types declared at lines 128-157 |
| `data/scenes/scene_office1_gt.yaml` | COCO→body-name mapping (chair bodies real) | VERIFIED | 3 chair bodies + 4 dining_table bodies, all confirmed against `mj_name2id` by `test_scene_office1_gt_mapping_resolves` |
| `tests/contract/test_no_map_in_ui.py` | Grep invariant + runtime-guard presence | VERIFIED | 4 parametrized tokens × frontend/src grep returncode==1; runtime-guard string presence check on streaming_viz.py |
| `tests/contract/test_no_map_in_payload.py` | Runtime guard recursive rejection | VERIFIED | 7 tests cover healthy payload + all 4 forbidden tokens + nested list + nested under `detection_gt_metrics` |
| `tests/integration/test_detections_export.py` | Round-trip lossless ±1e-6 | VERIFIED | 3 tests (404-empty, 30-OBB round-trip, Content-Disposition session) |
| `tests/integration/test_gt_extractor_attach.py` | End-to-end scene_office1_gt.yaml resolution | VERIFIED | Honest-skip if scene XML or YAML absent; asserts every body resolves + has geom |
| `tests/integration/test_rss_smoke_backends.py` | 3 parametrized backends, 200 MB cap, slow_boxer mark | VERIFIED | `yolov11` + `rtdetrv2` (honest-skip) + `boxer` (slow_boxer + honest-skip); OWLv2 intentionally absent per D-10 precedent |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| Coordinator pump | DetectionMetricsTracker | `record_frame(robot_id, sim_now, latest, inspect, backend_metrics)` | WIRED | `coordinator.py:817-823` calls with all 5 args; `sim_now` sourced from `frames[..].sim_time` (sim clock) |
| Coordinator pump | DetectionExportWriter | `append(obb, robot_id, backend_id, capture_timestamp)` | WIRED | `coordinator.py:828-833` iterates `latest.items`/`latest.boxes` and calls append per OBB |
| Coordinator pump | MuJoCoGTExtractor | `match_detection(cls, center, gate_m=1.0)` return consumed via `record_gt_match` | WIRED | `coordinator.py:840-846` — Previously-identified BLOCKER (match_detection return discarded) is FIXED; `_gid, err` unpacked and routed into tracker |
| WebStreamingViz | DetectionExportWriter | `rotate(new_session_id)` on `reset_cloud_tracking` | WIRED | `streaming_viz.py:121-123` — session rotation preserves tracker history; writer cycles file |
| GET /api/detections/export | DetectionExportWriter.file_path | `app.state.streaming_viz.detection_export.file_path` | WIRED | `detector_routes.py:275-276` + `streaming_viz.py:135-138` public property |
| GT extractor attach | WebStreamingViz | `attach_gt_extractor(yaml, mj_model, mj_data)` at coordinator bootstrap | WIRED | `coordinator.py:216 + 493` call `_attach_gt_extractor_if_possible`; `multi_bridge.mj_model` / `mj_data` accessors added per Plan 10 |
| Payload serialization | Runtime mAP guard | `_assert_no_map_keys(payload)` pre-broadcast | WIRED | `streaming_viz.py:508` called after payload assembly, before queue append |
| Frontend store | MetricsPanel | `detectionPerRobot` + `detectionGtPerRobot` via `useMetricsStore` | WIRED | `MetricsPanel.tsx:78-79` subscribes; rows at 232-248 read both |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| MetricsPanel 7 SC#1 rows | `detectionPerRobot[rid]` | streaming_viz payload (fed by tracker `record_frame` in coordinator pump) | Yes — backend-sourced p50/p95 from DetectorProtocol.get_metrics (verified populated at `boxer_backend.py:259-272` and RT-DETRv2/YOLOv11 per D-02) | FLOWING |
| MetricsPanel err m / recall | `detectionGtPerRobot[rid][class]` | tracker `record_gt_match` fed by coordinator consuming `gt_extractor.match_detection` | Yes — end-to-end chain verified by `test_gt_extractor_attach.py` (scene resolves) + `test_detection_metrics_tracker.py` (record_gt_match → payload) | FLOWING |
| /api/detections/export response | JSONL lines from session file | `DetectionExportWriter.append` called per OBB per tick | Yes — `test_detections_export.py` round-trips 30 real OBBs losslessly | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| PyYAML declared in perception optdeps | `python -c "import tomllib; ... 'PyYAML>=6.0' in perception"` | `['PyYAML>=6.0']` | PASS |
| Phase 6 unit tests | `pytest tests/metrics tests/contract -q --no-header` | `31 passed, 2 warnings in 0.47s` | PASS |
| Phase 6 integration tests (fast tier) | `pytest tests/integration/test_detections_export.py tests/integration/test_gt_extractor_attach.py tests/integration/test_rss_smoke_backends.py tests/test_main_args.py -m "not slow_boxer" -q` | `8 passed, 1 deselected, 2 warnings in 54.12s` (1 deselected = slow_boxer BoxeR case) | PASS |
| Frontend vitest suite | `cd frontend && npm test -- --run` | `Test Files 2 passed (2) · Tests 6 passed (6)` | PASS |
| export_router registered on app | grep server.py for export_router import + include | `include_router(detections_export_router)` at line 91 | PASS |
| `mAP` absent from frontend production source | `git grep -n mAP -- frontend/src/ :!frontend/src/**/__tests__/**` (via contract test) | returncode 1 (no match) for all 4 parametrized tokens | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| DET-METRICS-01 | 04, 08, 10, 11 | Per-robot inference_ms p50/p95 + det/frame + mean_conf + queue + freshness + 3d_jitter (updating live) | SATISFIED | SC#1 evidence above — all 7 metrics end-to-end |
| DET-METRICS-02 | 05, 07, 08, 10, 11 | MuJoCo GT via `mj_name2id` + class_name match; center_error_m + per_class_recall | SATISFIED | SC#2 evidence above — F1 fix + YAML mapping + `record_gt_match` consumption + 2 UI rows |
| DET-METRICS-03 | 08, 10, 12 | `mAP` forbidden in UI without labeled eval set; `--labeled-eval-set` gated | SATISFIED | SC#3 evidence above — 3-legged enforcement (grep + runtime + CLI) |
| DET-METRICS-04 | 06, 09 | GET /api/detections/export streams JSONL; round-trips through `OrientedBox3D.from_wire` | SATISFIED | SC#4 evidence above — route + writer + round-trip test to ±1e-6 |
| DET-METRICS-05 | 13 | RSS ≤200 MB over 100 inferences per backend; CI failure on regression | SATISFIED (scope narrowed per Phase 5 D-10) | SC#5 evidence above — 3 backends (not 4); OWLv2 documented as superseded |

**Orphans:** none. REQUIREMENTS.md maps exactly DET-METRICS-01..05 to Phase 6 and every one is claimed + satisfied by at least one plan.

### CONTEXT.md Decision Compliance (spot-check)

| Decision | Intent | Status | Evidence |
|----------|--------|--------|----------|
| D-01 (parallel tracker, NO inheritance) | `DetectionMetricsTracker` must not extend `MetricsTracker` | COMPLIANT | `detection_metrics_tracker.py:32` — `class DetectionMetricsTracker:` (no base class); module docstring line 4 explicitly notes "parallel sibling … NO inheritance" |
| D-08 (YAML mapping, NOT substring match) | Explicit COCO→body-name list file | COMPLIANT | `mujoco_gt.py:72-102` reads `mapping[class_name] -> list[str]` via `yaml.safe_load`; no substring logic anywhere |
| D-09 (1.0m correct-instance gate in match_detection) | `match_detection(..., gate_m=1.0)` returns `(geom_id, distance)` or `(None, None)` | COMPLIANT | `mujoco_gt.py:42 _DEFAULT_GATE_M = 1.0`; call site `coordinator.py:840` passes `gate_m=1.0` explicitly |
| D-10 (3-legged mAP enforcement) | Grep test + runtime guard + CLI reservation, all three | COMPLIANT | Grep → `test_no_map_in_ui.py`; runtime → `_assert_no_map_keys` in `streaming_viz.py:45-71 + 508`; CLI → `src/main.py:148-156 + 661-664` |
| D-15 (single parametrized test, not per-backend files) | One file with `@pytest.mark.parametrize` over backends | COMPLIANT | `test_rss_smoke_backends.py:96-123` — single parametrize block, one test fn; no per-backend test files exist |

All 5 spot-checked decisions held.

### Anti-Patterns Found

None. Targeted scans for:
- `TODO`/`FIXME`/`XXX` in Phase 6 new files — absent
- Hardcoded empty props passed to MetricsPanel children — N/A (panel is self-contained; reads from store)
- Static/empty returns from export handler — absent (handler reads real file + 404s on missing)
- `mAP`-family strings in production frontend source — absent (confirmed by `test_no_map_in_ui.py` green)
- Placeholder component returns in MetricsPanel.tsx — absent (9 rows render real store data with empty-state `--` fallback)

### Human Verification Required

Automated checks cannot cover these SC#1 / SC#2 / SC#4 live-behavior surfaces — the 06-VALIDATION.md §Manual-Only Verifications table locks these as the human-verification contract:

#### 1. Live 2-robot MetricsPanel render cadence (SC#1)

**Test:** `make download-models` → boot `argus` with `scene_office1.xml` + 2 robots → open C2 portal → expand Metrics panel.
**Expected:** Detection subsection renders 9 rows per robot (`infer p50`, `infer p95`, `det/frame`, `conf`, `queue`, `fresh` with traffic-light, `jitter`, `err m`, `recall`). Values refresh ≤1s cadence. No React console errors. `fresh` transitions #e0e0e0 → #f1c40f → #e74c3c as capture_timestamp ages past 1s / 3s.
**Why human:** 30 Hz WS stats emission + per-row DOM update cadence is a live-only signal; vitest shape tests confirm store structure but not render cadence in a running browser.

#### 2. center_error_m reads [0.00, 0.30] m for chair on scene_office1 (SC#2)

**Test:** Boot coordinator with YOLOv11 + `scene_office1.xml`. Drive a robot near the SwivlChair body (approx `(0.68, -2.44, 0.51)`). Read MetricsPanel `err m` row for the chair class.
**Expected:** Value in range [0.00, 0.30] m once the chair is in view; `--` when no robot has a chair in frame; `recall` grows toward a non-zero value as frames accumulate.
**Why human:** End-to-end MuJoCo tick + YOLOv11 inference + GT match chain requires model weights, running sim, and human-driven camera positioning — not in CI budget.

#### 3. JSONL export downloads + parses cleanly end-to-end (SC#4)

**Test:** `curl http://localhost:8000/api/detections/export -o /tmp/dets.jsonl && jq -c '.obb.class_name' /tmp/dets.jsonl | sort | uniq -c`.
**Expected:** Non-empty class_name histogram; file downloads with `Content-Disposition: attachment; filename="detections-<uuid>.jsonl"`; every line parses as valid JSON.
**Why human:** MIME + chunked transfer behavior across the wire differs from FastAPI TestClient semantics; MIME / Content-Disposition headers only exercised fully by real HTTP client.

### Deferred / Out-of-Scope Items (not gaps)

- **OWLv2 in SC#5 literal:** ROADMAP.md §Phase 6 SC#5 text says "YOLOv11, RT-DETRv2, OWLv2, BoxeR". OWLv2 was dropped 2026-04-15 during Phase 5 D-10 discuss (documented in REQUIREMENTS.md Out of Scope + ROADMAP.md §Phase 5 note). `test_rss_smoke_backends.py:6-9` documents this supersession. SC#5 is considered satisfied at 3 backends, not 4.
- **Pre-existing pytest collection errors** in `tests/perception/` and `tests/slam/` (documented in `deferred-items.md`): unrelated to Phase 6; every new Phase-6 test collects and passes cleanly.
- **Live mAP computation via `--labeled-eval-set`:** explicitly deferred per D-10 — flag is RESERVED with `NotImplementedError`, not shipped.
- **Sparkline rendering for detection history:** deferred per D-06; store slices populated, consumer not built.
- **Detection-metrics vs-baseline tab:** deferred per D-05.
- **Per-class jitter breakdown in UI:** deferred (aggregate max per robot is what SC#1 specifies; per-class payload available for later).

### Gaps Summary

None. All 5 automated success criteria hold end-to-end with code-level evidence and passing tests. The only items keeping overall status at `human_needed` are the three live-runtime surfaces explicitly called out in 06-VALIDATION.md §Manual-Only Verifications, which are the correct surfaces to require human observation (browser-render cadence, MuJoCo-in-the-loop accuracy reading, wire-level HTTP streaming).

---

## Overall Phase Verdict

**PASS (pending human-verification sign-off).**

Every SC has a direct file:line evidence trail in the codebase. All fast-tier + integration (non-`slow_boxer`) tests are green (31 unit + 8 integration + 6 vitest = 45 passing, 1 BoxeR test honest-deselected on missing subprocess venv). No artifact is a stub, no key link is unwired, no CONTEXT decision was violated. The three SC#1 / SC#2 / SC#4 human-verification items are inherent to the phase deliverable (they require a running coordinator + browser + robot driving) — they are not gaps in the implementation, they are the validation boundary the VALIDATION.md document explicitly drew.

---

_Verified: 2026-04-15T16:57:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.6 1M)_
