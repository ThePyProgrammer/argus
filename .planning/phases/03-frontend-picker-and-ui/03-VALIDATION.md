---
phase: 03
slug: frontend-picker-and-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Planner fills Per-Task Verification Map after producing PLAN.md files.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest 4.x (frontend, Wave 0 installs) |
| **Config file** | pytest.ini (exists) / frontend/vitest.config.ts (Wave 0 creates) |
| **Quick run command** | `pytest tests/perception/test_lifter_routes.py -x` (per-wave) |
| **Full suite command** | `pytest tests/perception/ tests/integration/ -q && cd frontend && npx tsc --noEmit && npx vitest run` |
| **Estimated runtime** | ~30 seconds (backend) + ~15 seconds (frontend tsc + vitest) |

---

## Sampling Rate

- **After every task commit:** Run quick run command scoped to the task's file
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

*Filled by planner after PLAN.md generation.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — Vitest config (jsdom env, alias for src/)
- [ ] `frontend/package.json` — add `vitest@^4.1.4` + `jsdom@^29.0.2` + `@testing-library/react` (if needed for DetectorSection) + `test` script
- [ ] `frontend/src/__tests__/detectorStore.structural.test.ts` — Vitest stub for DET-UI-06 (structural equivalence slamStore vs detectorStore)
- [ ] `tests/perception/test_lifter_routes.py` — stub for D-10 lifter REST routes (DET-UI-02 coverage backend side)

*Justification: Frontend has no test infrastructure today — Wave 0 bootstraps Vitest before any test-requiring task runs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Restart overlay visually blurs main canvas during detector/lifter restart | DET-UI-04 success criterion (partial) | Visual rendering — automated tsc + Vitest cannot verify blur filter appearance | Open C2 page, switch detector, confirm overlay appears and dismisses only after `detector_restart_complete` |
| CameraFeed 2D bbox overlay aligns with RGB image at same frame | DET-UI-03 success criterion #4 | Frame-sync requires live data; pixel-alignment is perceptual | Open CameraFeed with YOLOv11 active, verify bboxes wrap objects in RGB panel |
| Stacked overlays (concurrent detector + lifter restarts) | D-12 | Requires racing two restart commands | Click detector switch + lifter switch within 100ms, verify both overlays render stacked |

*Remaining behaviors (store shape, dropdown population, badge rendering, REST round-trip, debounce) have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner fills)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (Vitest install)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills map)

**Approval:** pending
