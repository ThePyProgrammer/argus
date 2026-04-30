---
phase: 03
slug: frontend-picker-and-ui
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-14
planner_filled: 2026-04-14
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Per-Task Verification Map filled after PLAN.md generation.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest 4.1.4 (frontend, Wave 0 installs via Plan 01) |
| **Config file** | pytest.ini (exists) / frontend/vitest.config.ts (Plan 01 creates) |
| **Quick run command (backend)** | `pytest tests/perception/test_lifter_routes.py tests/perception/test_worker_pool_lifter_params.py -x` |
| **Quick run command (frontend)** | `cd frontend && npm test -- detectorStore.shape` or `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `pytest tests/perception/ tests/integration/ -q && cd frontend && npx tsc --noEmit && npm test` |
| **Estimated runtime** | ~30 seconds (backend) + ~15 seconds (frontend tsc + vitest) |

---

## Sampling Rate

- **After every task commit:** Run quick run command scoped to the task's file
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| P01-T1 | 01 | 0 | DET-UI-06 (infra) | T-03-01, T-03-02 | vitest + jsdom pinned in package-lock | integration | `cd frontend && npm ls vitest jsdom --depth=0` | ❌ (Wave 0 creates) | ⬜ pending |
| P01-T2 | 01 | 0 | DET-UI-06 (infra) | T-03-03 | jsdom env configured | smoke | `cd frontend && npm test` (exit 0 with zero tests) | ❌ (Wave 0 creates) | ⬜ pending |
| P02-T1 | 02 | 0 | DET-UI-01 | T-03-04, T-03-05 | CapabilityBadge handles null/false safely | unit/tsc | `grep -q "value: string \\| number \\| boolean" frontend/src/components/CapabilityBadge.tsx` | ✅ (modifies existing) | ⬜ pending |
| P02-T2 | 02 | 0 | DET-UI-01 | T-03-04 | 2 SLAM call sites migrated (no legacy `name=` prop) | tsc | `cd frontend && npx tsc --noEmit && ! grep -rn "CapabilityBadge.*name=" src/` | ✅ | ⬜ pending |
| P03-T1 | 03 | 0 | DET-UI-04 | T-03-06, T-03-07 | RestartOverlay discriminated union prevents invalid subsystem | tsc | `grep -q "subsystem: 'slam' \\| 'detector' \\| 'lifter'" frontend/src/components/RestartOverlay.tsx` | ✅ | ⬜ pending |
| P03-T2 | 03 | 0 | DET-UI-04 | T-03-06 | 2 call sites (SceneViewer + ApplyBar) migrated | tsc | `cd frontend && npx tsc --noEmit && ! grep -rn "algorithmName" src/` | ✅ | ⬜ pending |
| P04-T1 | 04 | 1 | DET-UI-06 | T-03-08, T-03-09, T-03-10 | fetchDetectorState wraps all 4 fetches in try/catch | tsc | `cd frontend && grep -q "/api/detectors/lifters" src/stores/detectorStore.ts && grep -q "/api/detectors/active-lifter" src/stores/detectorStore.ts && npx tsc --noEmit` | ❌ (Plan 04 creates) | ⬜ pending |
| P05-T1 | 05 | 1 | DET-UI-02, DET-UI-04 | T-03-11, T-03-12 | Pydantic + whitelist check before app.state mutation | integration | `python -c "from backend.web.server import create_app; app, _ = create_app(['r0']); assert app.state.active_lifter == 'median_depth'"` | ✅/❌ (modifies existing + creates test) | ⬜ pending |
| P05-T2 | 05 | 1 | DET-UI-02, DET-UI-04 | T-03-11, T-03-12, T-03-13, T-03-14 | 4 routes round-trip + cold-boot side-effect import (Pitfall 4) | unit | `pytest tests/perception/test_lifter_routes.py -x` | ❌ (Plan 05 creates) | ⬜ pending |
| P06-T1 | 06 | 1 | DET-UI-02, DET-UI-04 | T-03-17 | DetectorWorkerPool lifter_params kwarg forwarded to Detection3DRegistry.create | unit | `pytest tests/perception/test_worker_pool_lifter_params.py tests/perception/test_worker_pool.py -x` | ❌ (Plan 06 creates) | ⬜ pending |
| P06-T2 | 06 | 1 | DET-UI-02, DET-UI-04 | T-03-15, T-03-16 | main.py clears pending_lifter only on success; WS payload carries {backend, lifter} | smoke | `python -c "import ast; ast.parse(open('src/main.py').read())" && grep -q "lifter_name=lifter_name" src/main.py && grep -q '"lifter": getattr' src/main.py` | ✅ | ⬜ pending |
| P07-T1 | 07 | 2 | DET-UI-01 | T-03-18, T-03-19 | Dropdown renders 3-key badges from trusted registry strings | tsc | `cd frontend && test -f src/components/DetectorDropdown.tsx && grep -q "'cpu_latency_hint_ms'" src/components/DetectorDropdown.tsx && npx tsc --noEmit` | ❌ (Plan 07 creates) | ⬜ pending |
| P07-T2 | 07 | 2 | DET-UI-02 | T-03-18 | LifterDropdown uses `s.lifters` + `s.activeLifter` | tsc | `cd frontend && test -f src/components/LifterDropdown.tsx && grep -q "'outputs_oriented'" src/components/LifterDropdown.tsx && npx tsc --noEmit` | ❌ (Plan 07 creates) | ⬜ pending |
| P08-T1 | 08 | 2 | DET-UI-03 | T-03-20, T-03-21, T-03-22 | Debounced `detector_param_update` via sendRaw closure | tsc | `cd frontend && grep -q "'detector_param_update'" src/components/DetectorParameterPanel.tsx && npx tsc --noEmit` | ❌ (Plan 08 creates) | ⬜ pending |
| P08-T2 | 08 | 2 | DET-UI-04 | (no new) | WS detector_restart_complete drives store + refetch | tsc | `cd frontend && grep -q "useDetectorStore.getState().setRestarting(false)" src/hooks/useWebSocket.ts && grep -q "fetchDetectorState()" src/hooks/useWebSocket.ts && npx tsc --noEmit` | ✅ (modifies existing) | ⬜ pending |
| P09-T1 | 09 | 2 | DET-UI-05 | T-03-23, T-03-24 | OKABE_ITO_RGB indexed safely + graceful degradation preserved | tsc | `cd frontend && grep -q "OKABE_ITO_RGB" src/components/CameraFeed.tsx && grep -q "classColor" src/components/CameraFeed.tsx && grep -q "if (!det.bbox_xyxy" src/components/CameraFeed.tsx && npx tsc --noEmit` | ✅ | ⬜ pending |
| P10-T1 | 10 | 3 | DET-UI-04 | (no new) | detectorStore extended with restartSubsystem for D-12 | tsc | `cd frontend && grep -q "restartSubsystem" src/stores/detectorStore.ts && grep -q "setRestartSubsystem" src/stores/detectorStore.ts && npx tsc --noEmit` | ✅ | ⬜ pending |
| P10-T2 | 10 | 3 | DET-UI-01, DET-UI-02, DET-UI-04 | T-03-25, T-03-26, T-03-27, T-03-28 | pollForDetectorRestart + pollForLifterRestart bounded at 20 attempts | tsc | `cd frontend && test -f src/components/DetectorSection.tsx && grep -q "pollForLifterRestart" src/components/DetectorSection.tsx && grep -q "outputs_3d_natively === false" src/components/DetectorSection.tsx && npx tsc --noEmit` | ❌ (Plan 10 creates) | ⬜ pending |
| P10-T3 | 10 | 3 | DET-UI-01, DET-UI-04 | (no new) | ControlPanel mount + 3 stacked RestartOverlays in SceneViewer | tsc | `cd frontend && grep -q "<DetectorSection />" src/components/ControlPanel.tsx && grep -q "subsystem=\"detector\"" src/components/SceneViewer.tsx && grep -q "subsystem=\"lifter\"" src/components/SceneViewer.tsx && npx tsc --noEmit` | ✅ | ⬜ pending |
| P11-T1 | 11 | 3 | DET-UI-06 | T-03-29 | EXPECTED_EXTRAS set-equality locks future drift | unit (Vitest) | `cd frontend && npm test -- detectorStore.shape` | ❌ (Plan 11 creates) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `frontend/vitest.config.ts` — Vitest config (jsdom env, src/ includes) — covered by Plan 01 Task 2
- [x] `frontend/package.json` — add `vitest@^4.1.4` + `jsdom@^29.0.2` + `test` / `test:watch` scripts — covered by Plan 01 Task 1
- [x] `frontend/src/components/CapabilityBadge.tsx` + 2 SLAM call-site migrations — covered by Plan 02
- [x] `frontend/src/components/RestartOverlay.tsx` + 2 SLAM call-site migrations — covered by Plan 03

*Justification: Frontend has no test infrastructure on main — Wave 0 bootstraps Vitest before any test-requiring task runs (Plans 08/11). Wave 0 also extends the shared UI primitives (CapabilityBadge, RestartOverlay) in-place so Wave 2/3 clones and mounts depend on the new signatures without re-migration.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Restart overlay visually blurs main canvas during detector/lifter restart | DET-UI-04 success criterion (partial) | Visual rendering — tsc + Vitest cannot verify blur filter appearance | Open C2 page, switch detector, confirm overlay appears and dismisses only after `detector_restart_complete` |
| CameraFeed 2D bbox overlay aligns with RGB image at same frame | DET-UI-05 success criterion #4 | Frame-sync requires live data; pixel-alignment is perceptual | Open CameraFeed with YOLOv11 active, verify bboxes wrap objects in RGB panel |
| CameraFeed per-class coloring produces distinguishable colors across detected classes | DET-UI-05 D-16 | Visual distinctness judgment | Open scene with multiple object classes (e.g., chair + table + person), verify each class renders in a different OKABE_ITO palette color |
| Stacked overlays (concurrent detector + lifter restarts) | D-12 | Requires racing two restart commands | Click detector switch then lifter switch within 100ms (before first WS fires), verify message correctly reflects the second-triggered subsystem (restartSubsystem tracks most recent) |
| DetectorSection appears between SLAM ALGORITHM and rest of ControlPanel | D-17/D-18 | Layout ordering | Open C2 page; OBJECT DETECTION section header visible under SLAM ALGORITHM, collapsible via chevron |
| Debounced `detector_param_update` (200ms) visible in Network tab | DET-UI-03 | Timing / frame-sync behavior | Open DevTools Network; drag confidence slider; verify only 1 WS send within 200ms of drag-end; next detection payload reflects new threshold |
| LifterDropdown hides when active backend has `outputs_3d_natively: true` | DET-UI-02 | No native-3D backend exists until Phase 5; manual verification only possible by temporarily flipping a capability in dev | Temporarily edit YOLOv11Backend.CAPABILITIES to set `outputs_3d_natively: True`, reload page, verify LifterDropdown disappears; revert change |

*Remaining behaviors (store shape, dropdown population, badge text rendering, REST round-trip, debounce type string, restart overlay text messages) have automated verification via tsc + Vitest + pytest.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (planner filled)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has at least a tsc or grep check)
- [x] Wave 0 covers all MISSING references (Vitest install via Plan 01)
- [x] No watch-mode flags (all test commands use `npm test` which is `vitest run`, not `vitest` watch)
- [x] Feedback latency < 60s (pytest scoped files ~5s; vitest ~3s; tsc ~10s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved by planner 2026-04-14
