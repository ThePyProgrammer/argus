---
phase: 6
slug: detection-metrics-and-mujoco-gt
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
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

Filled by the planner as tasks are emitted. Template row:

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | DET-METRICS-01 | — | N/A | unit stub | `pytest tests/metrics/test_detection_metrics_tracker.py::test_stub -q` | ❌ W0 | ⬜ pending |
| 6-01-02 | 01 | 0 | DET-METRICS-02 | — | N/A | unit stub | `pytest tests/metrics/test_mujoco_gt.py::test_stub -q` | ❌ W0 | ⬜ pending |
| 6-01-03 | 01 | 0 | DET-METRICS-03 | T-6-01 (mAP leak) | `mAP` absent in `frontend/src/` | invariant stub | `pytest tests/contract/test_no_map_in_ui.py::test_stub -q` | ❌ W0 | ⬜ pending |
| 6-01-04 | 01 | 0 | DET-METRICS-04 | — | N/A | integration stub | `pytest tests/integration/test_detections_export.py::test_stub -q` | ❌ W0 | ⬜ pending |
| 6-01-05 | 01 | 0 | DET-METRICS-05 | — | RSS bounded | parametrized stub | `pytest tests/integration/test_rss_smoke_backends.py -q --collect-only` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner backfills one row per task once PLAN.md files are emitted. Every task whose `<automated>` block commits `pytest ...` or `npm test ...` must appear here.*

---

## Wave 0 Requirements

Wave 0 (infrastructure scaffolds, MUST land before any implementation wave):

- [ ] `tests/metrics/__init__.py` — new package marker
- [ ] `tests/metrics/test_detection_metrics_tracker.py` — skip-stub for DetectionMetricsTracker (covers DET-METRICS-01)
- [ ] `tests/metrics/test_mujoco_gt.py` — skip-stub for MuJoCoGTExtractor; fixture path points to `tests/perception/fixtures/scene_rotated_chair.xml` (covers DET-METRICS-02; note F1 from RESEARCH — fixture uses proper `pos=` attributes so `data.xpos` also works there for unit tests; scene_office1 integration uses `data.geom_xpos`)
- [ ] `tests/contract/__init__.py` — new package (MISSING per RESEARCH §F5)
- [ ] `tests/contract/test_no_map_in_ui.py` — skip-stub for grep invariant (covers DET-METRICS-03)
- [ ] `tests/integration/test_detections_export.py` — skip-stub for `/api/detections/export` round-trip (covers DET-METRICS-04)
- [ ] `tests/integration/test_rss_smoke_backends.py` — skip-stub with parametrize placeholder (covers DET-METRICS-05)
- [ ] `pyproject.toml` — add `pyyaml` to `[project.optional-dependencies].perception` (RESEARCH §F6 — installed but not declared)
- [ ] `frontend/src/stores/__tests__/metricsStore.detection.shape.test.ts` — skip-stub for the new `detectionPerRobot` + `detectionHistory` slice (mirrors `detectorStore.shape.test.ts` from Phase 3)

**Scaffold invariant (per GSD T-P-01 protocol):**
- Stubs exist as empty test modules with a single skipped test that names the target REQ-ID
- Each stub `pytest.skip("Wave 0 scaffold — implemented in Plan XX", allow_module_level=True)` so pytest collection passes before implementation lands

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MetricsPanel live updates visible in browser with 2-robot session | DET-METRICS-01 (SC#1) | Needs live coordinator + browser; automated vitest shape test covers store structure but not render cadence | 1. `make download-models` then boot `argus` with `scene_office1.xml` + 2 robots. 2. Open C2 portal. 3. Expand Metrics panel. 4. Confirm detection subsection renders `infer p50/p95`, `det/frame`, `conf`, `queue`, `fresh`, `jitter` per robot, values refresh ≤1s cadence, no React console errors. |
| center_error_m shows 0.0X for chair on scene_office1 | DET-METRICS-02 (SC#2) | Requires live MuJoCo tick loop + detector pipeline; reproducible but not in CI because it needs GPU-less runtime + model weights | 1. Boot coordinator with YOLOv11 + `scene_office1.xml`. 2. Drive a robot near the SwivlChair body. 3. Read `center_error_m` for class `chair` in MetricsPanel — expect value in range [0.00, 0.30] m. |
| JSONL export downloads + parses in external tool | DET-METRICS-04 (SC#4) | End-to-end verify — automated round-trip test exists but manual `curl` + `jq` check catches MIME/header issues | `curl http://localhost:8000/api/detections/export -o detections.jsonl && jq -c '.obb.class_name' detections.jsonl \| sort \| uniq -c` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (tests/contract/ directory is NEW — RESEARCH §F5)
- [ ] No watch-mode flags (pytest runs with `-q`, vitest runs with `--run`)
- [ ] Feedback latency < 45s (quick tier)
- [ ] BoxeR RSS case honest-skips when venv missing (NOT a failure)
- [ ] RT-DETRv2 RSS case honest-skips when ONNX artifact missing (NOT a failure)
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills the verification map

**Approval:** pending (planner to fill Per-Task Verification Map + flip `nyquist_compliant: true` when all rows have automated commands or Wave 0 scaffold dependency)
