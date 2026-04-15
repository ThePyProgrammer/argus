---
phase: 07
slug: pipeline-editor-perception-nodes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Dual stack: pytest (Python) + vitest (TypeScript). Full source: `07-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Python framework** | pytest >=8.0.0 + pytest-asyncio >=0.23.0 |
| **Python config** | `pyproject.toml` `[tool.pytest.ini_options]` — markers `slow_boxer`, `network` |
| **Frontend framework** | vitest 4.1.4 + jsdom 29.0.2 |
| **Frontend config** | `frontend/vitest.config.ts` |
| **Python quick run** | `pytest tests/coordination/test_pipeline_builder_perception.py -x` |
| **Python full suite** | `pytest -x` (excludes `slow_boxer` + `network` by default) |
| **Frontend quick** | `cd frontend && npm run test -- src/stores/__tests__/pipelineStore.dataType.test.ts` |
| **Frontend full** | `cd frontend && npm run test` |
| **Estimated runtime** | ~60 s frontend, ~90 s Python (excluding slow_boxer + integration) |

---

## Sampling Rate

- **After every task commit:** Run the specific test file(s) called out in that task's `<automated>` verify block (see per-task map below)
- **After every plan wave:** Run `pytest tests/coordination/ tests/tracking/ tests/perception/test_swap_backend.py -x` + `cd frontend && npm run test`
- **Before `/gsd-verify-work`:** Both `pytest -x` AND `cd frontend && npm run test` must be green
- **Max feedback latency:** <60 s per-task, <180 s per-wave, <300 s full phase gate

---

## Per-Task Verification Map

Populated during planning — one row per task with automated verification. The planner fills this during Wave 0 scaffolding.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-{PP}-{TT} | {PP} | {W} | DET-PIPELINE-{XX} | T-07-{N} / — | {expected behavior or "N/A"} | unit / integration / contract | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Phase Requirements → Test Map

| Req ID | SC | Behavior | Test Type | Automated Command | File Exists? |
|--------|-----|----------|-----------|-------------------|-------------|
| DET-PIPELINE-01 | SC#1 | `perception` category in palette with 3 node types | vitest unit | `cd frontend && npm run test -- src/utils/__tests__/nodeDefinitions.perception.test.ts` | ❌ Wave 0 |
| DET-PIPELINE-01 | SC#1 | Drag + connect Detections2D → Detections3D without error | vitest integration (jsdom) | `cd frontend && npm run test -- src/stores/__tests__/pipelineStore.connect.perception.test.ts` | ❌ Wave 0 |
| DET-PIPELINE-02 | SC#1 | Port colors + types extended (`Detections2D`, `Detections3D`, `Tracks`) | vitest snapshot | `cd frontend && npm run test -- src/utils/__tests__/portColors.test.ts` | ❌ Wave 0 |
| DET-PIPELINE-03 | SC#2 | `pipelineStore.ts:101` + `pipelineSerializer.ts:112` regression | vitest unit | `cd frontend && npm run test -- src/stores/__tests__/pipelineStore.dataType.test.ts` | ❌ Wave 0 (named in CONTEXT) |
| DET-PIPELINE-03 | SC#2 | Per-edge type mismatch error | vitest unit | `cd frontend && npm run test -- src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` | ❌ Wave 0 (named in CONTEXT) |
| DET-PIPELINE-04 | SC#3 | `perception_rgbd.json` loads + builds without error | pytest contract | `pytest tests/contract/test_perception_rgbd_preset.py -x` | ❌ Wave 0 |
| DET-PIPELINE-04 | SC#3 | Preset apply → live OBBs end-to-end | pytest integration (slow, optional) | `pytest tests/integration/test_perception_rgbd_end_to_end.py -x` | ❌ Wave 0 |
| DET-PIPELINE-05 | SC#5 | `PipelineConfig` populated with detector/lifter/tracker fields | pytest unit | `pytest tests/coordination/test_pipeline_builder_perception.py -x` | ❌ Wave 0 |
| DET-PIPELINE-05 | SC#4 | Hot-apply changes backend without restart (PID stable) | pytest integration | `pytest tests/integration/test_pipeline_apply_hot.py -x` | ❌ Wave 0 |
| DET-PIPELINE-05 | SC#4 | `DetectorWorkerPool.swap_backend` atomicity | pytest unit | `pytest tests/perception/test_swap_backend.py -x` | ❌ Wave 0 |
| DET-PIPELINE-05 | SC#1 | `TrackerRegistry.list()` + `TrackerRegistry.create("none")` | pytest unit | `pytest tests/tracking/test_tracker_registry.py -x` | ❌ Wave 0 |

---

## Wave 0 Requirements

Scaffolding that must land BEFORE any implementation plan runs. Each entry is a skip-stubbed test file + any needed package `__init__.py`.

- [ ] `tests/coordination/test_pipeline_builder_perception.py` — DET-PIPELINE-05 (PipelineConfig extension, build extension, perception catalog)
- [ ] `tests/tracking/__init__.py` + `tests/tracking/test_tracker_registry.py` — DET-PIPELINE-05 (tracker registry + passthrough)
- [ ] `tests/perception/test_swap_backend.py` — DET-PIPELINE-05 SC#4 (pool atomicity)
- [ ] `tests/contract/test_perception_rgbd_preset.py` — DET-PIPELINE-04 (preset integrity)
- [ ] `tests/integration/test_pipeline_apply_hot.py` — DET-PIPELINE-05 SC#4 (hot-apply end-to-end)
- [ ] `tests/integration/test_perception_rgbd_end_to_end.py` — DET-PIPELINE-04 SC#3 (live OBB pipeline; may be marked slow)
- [ ] `frontend/src/stores/__tests__/pipelineStore.dataType.test.ts` — DET-PIPELINE-03 SC#2 (dataType regression)
- [ ] `frontend/src/stores/__tests__/pipelineStore.connect.perception.test.ts` — DET-PIPELINE-01 SC#1 (drag+connect)
- [ ] `frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` — DET-PIPELINE-03 SC#2 (validation)
- [ ] `frontend/src/utils/__tests__/nodeDefinitions.perception.test.ts` — DET-PIPELINE-01 (catalog)
- [ ] `frontend/src/utils/__tests__/portColors.test.ts` — DET-PIPELINE-02 (color + shape extension)

*Existing pytest + vitest infrastructure already covers framework installation. No new test frameworks needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual confirmation of palette `Perception` section with 3 drag-able node types | DET-PIPELINE-01 SC#1 | Requires full React Flow runtime in browser; jsdom does not render port handles with correct visual positioning | `npm run dev`, open pipeline editor, verify `Perception` section appears between `Mergers` and `Filters`, drag each of `Detector (YOLOv11)` / `Detection3D (PointCluster)` / `Tracker (None)` onto canvas, confirm handle colors `#ff8a65 / #ec407a / #26a69a` match UI-SPEC. |
| Per-edge type-mismatch error surfaced in UI with red stroke or toast | DET-PIPELINE-03 SC#2 | vitest only checks `validationErrors` array; visual error surface requires browser | Load the default_icp preset, manually drag an edge from a `PointCloud` output onto a `Detections2D` input, confirm validation error banner appears in ApplyBar or inspector. |
| Hot-apply visual smoothness — no restart overlay flash on detector swap | DET-PIPELINE-05 SC#4 | Timing + visual absence — hard to assert in jsdom | Apply `perception_rgbd` preset, wait for warmup, change `detector_generic.backend` from `yolov11` → `rtdetrv2` in NodeInspector, click Apply, observe that no full-screen RestartOverlay appears; instead a transient toast "Pipeline updated in place". |
| `detector_swap_complete` WS envelope consumed by detectorStore | DET-PIPELINE-05 | Requires live WS connection | In browser devtools, filter WS frames for `detector_swap_complete` during hot-apply; confirm `detectorStore.activeBackend` updates without `isRestarting` toggling. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (11 test file stubs above)
- [ ] No watch-mode flags in any `<automated>` block
- [ ] Feedback latency < 60s per task, < 180s per wave
- [ ] `nyquist_compliant: true` set in frontmatter AFTER Wave 0 lands + planner populates per-task map

**Approval:** pending
