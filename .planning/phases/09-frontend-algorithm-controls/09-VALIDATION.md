---
phase: 9
slug: frontend-algorithm-controls
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | TypeScript type-checking (tsc) for frontend; pytest 8.x for backend |
| **Config file** | `frontend/tsconfig.json` for tsc; `pyproject.toml` for pytest |
| **Quick run command** | `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `cd frontend && npx tsc --noEmit && cd .. && python -m pytest tests/web/test_slam_routes.py -x` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx tsc --noEmit`
- **After every plan wave:** Run `cd frontend && npx tsc --noEmit && cd .. && python -m pytest tests/web/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green + manual browser walkthrough
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | CTRL-01 | type-check + manual | `cd frontend && npx tsc --noEmit` | ✅ tsconfig | ⬜ pending |
| 09-01-02 | 01 | 1 | CTRL-01 | type-check + manual | `cd frontend && npx tsc --noEmit` | ✅ tsconfig | ⬜ pending |
| 09-02-01 | 02 | 1 | CTRL-02 | type-check + backend-test | `cd frontend && npx tsc --noEmit && cd .. && python -m pytest tests/web/test_slam_routes.py -x` | ✅ both | ⬜ pending |
| 09-02-02 | 02 | 1 | CTRL-03 | type-check + manual | `cd frontend && npx tsc --noEmit` | ✅ tsconfig | ⬜ pending |
| 09-03-01 | 03 | 2 | CTRL-04 | type-check + backend-test | `cd frontend && npx tsc --noEmit && cd .. && python -m pytest tests/web/ -x` | ✅ both | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/index.css` or `frontend/src/App.css` — add `@keyframes spin` for restart overlay spinner
- [ ] `frontend/vite.config.ts` — add `/api` proxy to `http://localhost:8000`

*Existing infrastructure covers type checking and backend testing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dropdown shows backends with badge pills | CTRL-01 | Visual rendering, no frontend test framework | Open browser at localhost:5173, verify dropdown lists all backends with colored pills |
| Modal appears on algorithm switch | CTRL-02 | UI interaction, no playwright | Select different algorithm in dropdown, verify modal dialog appears |
| Parameter sliders render from JSON Schema | CTRL-03 | Dynamic form rendering, visual | Open parameter panel, verify sliders with text inputs for numeric params |
| Slider changes send WebSocket messages | CTRL-04 | WebSocket integration, visual | Change a slider, verify backend log shows param update received |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
