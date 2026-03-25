---
phase: 14
slug: interactive-comfyui-esque-react-flow-state-graph-creation-system-to-customize-the-end-to-end-slam-pipeline-parameters
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend), Vite build check (frontend) |
| **Config file** | pyproject.toml `[project.optional-dependencies] dev` |
| **Quick run command** | `python -m pytest tests/web/test_pipeline_routes.py -x -q --timeout=10` |
| **Full suite command** | `python -m pytest tests/ -x -q --timeout=30 && cd frontend && npm run build` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/web/test_pipeline_routes.py -x -q --timeout=10`
- **After every plan wave:** Run `python -m pytest tests/ -x -q --timeout=30 && cd frontend && npm run build`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-T1 | 01 | 1 | P14-01 | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_apply_valid_config -x` | W0 | pending |
| 14-T2 | 01 | 1 | P14-02 | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_reject_cycle -x` | W0 | pending |
| 14-T3 | 01 | 1 | P14-03 | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_reject_unconnected -x` | W0 | pending |
| 14-T4 | 01 | 1 | P14-04 | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_preset_crud -x` | W0 | pending |
| 14-T5 | 01 | 1 | P14-05 | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_node_catalog -x` | W0 | pending |
| 14-T6 | 01 | 1 | P14-06 | unit | `python -m pytest tests/coordination/test_pipeline_builder.py -x` | W0 | pending |
| 14-T7 | 02 | 2 | P14-07 | build | `cd frontend && npx tsc --noEmit` | existing | pending |
| 14-T8 | 02 | 2 | P14-08 | build | `cd frontend && npm run build` | existing | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/web/test_pipeline_routes.py` — stubs for P14-01 through P14-05
- [ ] `tests/coordination/test_pipeline_builder.py` — stubs for P14-06
- [ ] `data/presets/builtin/` directory with 3 default preset JSON files

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Graph editor renders with colored nodes | P14-UI | Visual rendering | Open C2, toggle to Pipeline Editor, verify node colors match UI-SPEC |
| Drag-and-drop from palette to canvas | P14-UI | Browser interaction | Drag a SLAM Backend node from palette, verify it appears on canvas |
| Animated edges during pipeline execution | P14-UI | Visual animation | Apply pipeline, start session, verify edge animations |
| Node parameter inline display | P14-UI | Visual rendering | Verify 2-3 primary params show inline on nodes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
