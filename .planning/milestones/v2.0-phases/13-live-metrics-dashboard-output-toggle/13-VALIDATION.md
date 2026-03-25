---
phase: 13
slug: live-metrics-dashboard-output-toggle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 + pytest-asyncio >=0.23.0; tsc for frontend |
| **Config file** | `pytest.ini`; `frontend/tsconfig.json` |
| **Quick run command** | `pytest tests/web/ tests/slam/test_drift_metrics.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q && cd frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/web/ tests/slam/test_drift_metrics.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q && cd frontend && npx tsc --noEmit`
- **Before `/gsd:verify-work`:** Full suite must be green + manual browser walkthrough
- **Max feedback latency:** 12 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | CTRL-05 | unit | `pytest tests/web/test_metrics_tracker.py -x -q` | Wave 0 | ⬜ pending |
| 13-01-02 | 01 | 1 | CTRL-06 | unit | `pytest tests/web/test_metrics_tracker.py -x -q -k baseline` | Wave 0 | ⬜ pending |
| 13-02-01 | 02 | 2 | CTRL-05 | type-check + manual | `cd frontend && npx tsc --noEmit` | ✅ | ⬜ pending |
| 13-02-02 | 02 | 2 | CTRL-06 | type-check + manual | `cd frontend && npx tsc --noEmit` | ✅ | ⬜ pending |
| 13-03-01 | 03 | 2 | CTRL-07 | unit | `pytest tests/web/test_mesh_reconstruction.py -x -q` | Wave 0 | ⬜ pending |
| 13-03-02 | 03 | 2 | CTRL-07 | type-check + manual | `cd frontend && npx tsc --noEmit` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/web/test_metrics_tracker.py` — MetricsTracker ring buffer, baseline capture, history serialization
- [ ] `tests/web/test_mesh_reconstruction.py` — Open3D mesh generation, graceful degradation when Open3D unavailable
- [ ] Extend `tests/web/test_streaming_viz.py` — slam_metrics in stats payload

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Metrics panel shows live ATE/RPE/ms per robot | CTRL-05 | Visual rendering, real-time updates | Run session, verify metrics table updates in bottom panel |
| Sparkline charts vs ICP baseline | CTRL-06 | SVG rendering, visual comparison | Switch from ICP to another backend, toggle to vs Baseline view |
| Output format toggle transitions | CTRL-07 | Three.js rendering modes, fade animation | Click Cloud/Voxel/Mesh buttons, verify geometry changes with fade |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 12s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
