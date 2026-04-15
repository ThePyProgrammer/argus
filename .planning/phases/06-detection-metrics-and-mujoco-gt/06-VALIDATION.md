---
phase: 6
slug: detection-metrics-and-mujoco-gt
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-15
updated: 2026-04-15
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Sourced from 06-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python) + vitest 2.x (frontend, already Phase 3) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` + `frontend/vitest.config.ts` |
| **Quick run command** | `pytest tests/metrics tests/contract -q --no-header -x` |
| **Full suite command** | `pytest -m "not slow_boxer" -q && pytest -m slow_boxer -q && (cd frontend && npm test -- --run)` |
| **Estimated runtime** | ~40 s (quick) / ~3 min (full incl. slow_boxer) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/metrics tests/contract -q --no-header -x` (fast tier; scoped to Phase 6 new modules)
- **After every plan wave:** Run `pytest -m "not slow_boxer" -q && (cd frontend && npm test -- --run)` (full Python fast tier + vitest)
- **Before `/gsd-verify-work`:** Full suite must be green, including `-m slow_boxer` parametrized RSS cases (honest-skip when `subprocess_venvs/boxer/.ready` or `models/rtdetrv2/*/model.onnx` absent — NOT a failure)
- **Max feedback latency:** 45 seconds (quick tier upper bound)

---

## Per-Task Verification Map

Filled by the planner as tasks were emitted. One row per task that commits a `pytest` or `vitest` assertion or depends on a Wave 0 scaffold.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | DET-METRICS-02 | — | pyproject dependency declared | toml parse | `python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert 'PyYAML>=6.0' in d['project']['optional-dependencies']['perception']"` | ✅ post-commit | ⬜ pending |
| 6-02-01 | 02 | 0 | DET-METRICS-01/02 | — | N/A | collection stub | `pytest tests/metrics/ --collect-only -q` | ✅ post-commit | ⬜ pending |
| 6-02-02 | 02 | 0 | DET-METRICS-03 | T-6-01 | N/A | collection stub | `pytest tests/contract/ --collect-only -q` | ✅ post-commit | ⬜ pending |
| 6-02-03 | 02 | 0 | DET-METRICS-04/05 + CLI | — | N/A | collection stub | `pytest tests/integration/test_detections_export.py tests/integration/test_rss_smoke_backends.py tests/test_main_args.py --collect-only -q` | ✅ post-commit | ⬜ pending |
| 6-03-01 | 03 | 0 | DET-METRICS-01 (FE) | — | N/A | vitest stub | `cd frontend && npx vitest run src/stores/__tests__/metricsStore.detection.shape.test.ts` | ✅ post-commit | ⬜ pending |
| 6-04-01 | 04 | 1 | DET-METRICS-01 | T-6-01, T-6-06 | no mAP keys, bounded deques | unit | `pytest tests/metrics/test_detection_metrics_tracker.py -v` | ❌ W0 dep on 02 | ⬜ pending |
| 6-05-01 | 05 | 1 | DET-METRICS-02 | T-6-04 | yaml.safe_load only | fixture-YAML build | `python -c "import yaml; d=yaml.safe_load(open('tests/perception/fixtures/scene_rotated_chair_gt.yaml')); assert 'chair' in d"` | ✅ post-commit | ⬜ pending |
| 6-05-02 | 05 | 1 | DET-METRICS-02 | T-6-04, T-6-07 | geom_xpos used, safe_load, fail-fast | unit | `pytest tests/metrics/test_mujoco_gt.py -v` | ❌ W0 dep on 02 | ⬜ pending |
| 6-06-01 | 06 | 1 | DET-METRICS-04 | T-6-02, T-6-03, T-6-06 | tempfile.gettempdir, to_wire only, lock | unit | `pytest tests/metrics/test_detection_export.py -v` | ✅ post-commit | ⬜ pending |
| 6-07-01 | 07 | 1 | DET-METRICS-02 | T-6-04 | mapping validates end-to-end | script | `python -c "…assert all body names resolve via mj_name2id and have a geom…"` (see Plan 07 `<verify>`) | ✅ post-commit | ⬜ pending |
| 6-08-01 | 08 | 2 | DET-METRICS-01/03/04 | T-6-01, T-6-08 | payload guard + graceful GT | module import | `python -c "from backend.web.streaming_viz import _assert_no_map_keys; _assert_no_map_keys({'r':{'mAP':1}})"` expect AssertionError | ✅ post-commit | ⬜ pending |
| 6-08-02 | 08 | 2 | DET-METRICS-03 | T-6-01 | runtime guard triggers on forbidden keys | unit | `pytest tests/contract/test_no_map_in_payload.py -v` | ❌ W0 dep on 02 | ⬜ pending |
| 6-09-01 | 09 | 2 | DET-METRICS-04 | T-6-02, T-6-05 | ndjson media type, no path param | route registration | `python -c "from backend.web.detector_routes import router; assert any('/detections/export' in r.path for r in router.routes)"` | ✅ post-commit | ⬜ pending |
| 6-09-02 | 09 | 2 | DET-METRICS-04 | T-6-02, T-6-05 | round-trip ±1e-6, 404, MIME | integration | `pytest tests/integration/test_detections_export.py -v --timeout=120` | ❌ W0 dep on 02 | ⬜ pending |
| 6-10-01 | 10 | 3 | DET-METRICS-01 | — | public detector accessor | module import | `python -c "from src.perception.worker import DetectorWorker; assert isinstance(DetectorWorker.__dict__['detector'], property)"` | ✅ post-commit | ⬜ pending |
| 6-10-02 | 10 | 3 | DET-METRICS-01/02/03 | T-6-08, T-6-09 | pump uses sim_now, graceful GT, CLI flag reserved | CLI test | `pytest tests/test_main_args.py -v --timeout=60` | ❌ W0 dep on 02 | ⬜ pending |
| 6-11-01 | 11 | 4 | DET-METRICS-01 | T-6-01 | FE types declared, no forbidden strings | typecheck | `cd frontend && npx tsc --noEmit` | ✅ post-commit | ⬜ pending |
| 6-11-02 | 11 | 4 | DET-METRICS-01 | T-6-01 | single-set updater, slices present | vitest | `cd frontend && npx vitest run src/stores/__tests__/metricsStore.detection.shape.test.ts` | ❌ W0 dep on 03 | ⬜ pending |
| 6-11-03 | 11 | 4 | DET-METRICS-01/03 | T-6-01, T-6-10 | 7 rows, separator, traffic-light, no forbidden strings | typecheck + grep | `cd frontend && npx tsc --noEmit && ! grep -qE '(mAP|map_50|map_75|mean_average_precision)' frontend/src/components/MetricsPanel.tsx` | ✅ post-commit | ⬜ pending |
| 6-12-01 | 12 | 5 | DET-METRICS-03 | T-6-01, T-6-11 | grep invariant + runtime-guard presence | contract | `pytest tests/contract/test_no_map_in_ui.py -v` | ❌ W0 dep on 02 | ⬜ pending |
| 6-13-01 | 13 | 5 | DET-METRICS-05 | T-6-12 | parametrized RSS, honest-skip, OWLv2 absent | integration | `pytest tests/integration/test_rss_smoke_backends.py -m "not slow_boxer" -v --timeout=300` | ❌ W0 dep on 02 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Every task with an `<automated>` block appears above. Tasks whose file is created by Wave 0 (Plan 02 or Plan 03) carry the ❌ W0 dep marker in the `File Exists` column — those tests exist as skip-stubs pre-wave; real tests replace them in the owning plan.*

---

## Wave 0 Requirements

Wave 0 (infrastructure scaffolds, MUST land before any implementation wave) — owned by Plans 01, 02, 03:

- [ ] `tests/metrics/__init__.py` — new package marker (Plan 02 Task 1)
- [ ] `tests/metrics/test_detection_metrics_tracker.py` — skip-stub for DetectionMetricsTracker (covers DET-METRICS-01; replaced by Plan 04)
- [ ] `tests/metrics/test_mujoco_gt.py` — skip-stub for MuJoCoGTExtractor; fixture path points to `tests/perception/fixtures/scene_rotated_chair.xml` (covers DET-METRICS-02; replaced by Plan 05)
- [ ] `tests/contract/__init__.py` — new package (MISSING per RESEARCH §F5; Plan 02 Task 2)
- [ ] `tests/contract/test_no_map_in_ui.py` — skip-stub for grep invariant (covers DET-METRICS-03; replaced by Plan 12)
- [ ] `tests/contract/test_no_map_in_payload.py` — skip-stub for runtime-guard test (covers DET-METRICS-03; replaced by Plan 08)
- [ ] `tests/integration/test_detections_export.py` — skip-stub for `/api/detections/export` round-trip (covers DET-METRICS-04; replaced by Plan 09)
- [ ] `tests/integration/test_rss_smoke_backends.py` — skip-stub with parametrize placeholder (covers DET-METRICS-05; replaced by Plan 13)
- [ ] `tests/test_main_args.py` — skip-stub for CLI reservation test (covers DET-METRICS-03; replaced by Plan 10)
- [ ] `pyproject.toml` — add `pyyaml` to `[project.optional-dependencies].perception` (RESEARCH §F6; Plan 01)
- [ ] `frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts` — skip-stub for the new `detectionPerRobot` + `detectionHistory` slice (Plan 03; replaced by Plan 11)

**Scaffold invariant (per GSD T-P-01 protocol):**
- Stubs exist as test modules with `pytest.skip(..., allow_module_level=True)` so pytest collection passes before implementation lands.
- Vitest stub uses `it.skip(...)` with the target REQ-ID + replacing-plan name in the description.
- Each stub names its target REQ-ID and the plan that replaces it.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MetricsPanel live updates visible in browser with 2-robot session | DET-METRICS-01 (SC#1) | Needs live coordinator + browser; automated vitest shape test covers store structure but not render cadence | 1. `make download-models` then boot `argus` with `scene_office1.xml` + 2 robots. 2. Open C2 portal. 3. Expand Metrics panel. 4. Confirm detection subsection renders `infer p50/p95`, `det/frame`, `conf`, `queue`, `fresh`, `jitter` per robot, values refresh ≤1s cadence, no React console errors. |
| center_error_m shows 0.0X for chair on scene_office1 | DET-METRICS-02 (SC#2) | Requires live MuJoCo tick loop + detector pipeline; reproducible but not in CI because it needs GPU-less runtime + model weights | 1. Boot coordinator with YOLOv11 + `scene_office1.xml`. 2. Drive a robot near the SwivlChair body. 3. Read `center_error_m` for class `chair` in MetricsPanel — expect value in range [0.00, 0.30] m. |
| JSONL export downloads + parses in external tool | DET-METRICS-04 (SC#4) | End-to-end verify — automated round-trip test exists but manual `curl` + `jq` check catches MIME/header issues | `curl http://localhost:8000/api/detections/export -o detections.jsonl && jq -c '.obb.class_name' detections.jsonl \| sort \| uniq -c` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests/contract/ directory is NEW — RESEARCH §F5)
- [x] No watch-mode flags (pytest runs with `-q`, vitest runs with `--run`)
- [x] Feedback latency < 45s (quick tier)
- [x] BoxeR RSS case honest-skips when venv missing (NOT a failure)
- [x] RT-DETRv2 RSS case honest-skips when ONNX artifact missing (NOT a failure)
- [x] `nyquist_compliant: true` set in frontmatter after planner filled the verification map

**Approval:** Planner — 2026-04-15. Nyquist compliant (every task in the map has an automated command or a Wave 0 scaffold dependency; wave_0_complete flips to true after Plans 01–03 execute).
