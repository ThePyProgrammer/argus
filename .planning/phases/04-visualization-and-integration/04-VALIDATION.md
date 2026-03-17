---
phase: 4
slug: visualization-and-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 with pytest-timeout |
| **Config file** | pyproject.toml (implicit) |
| **Quick run command** | `python -m pytest tests/test_multi_robot_viz.py -x --timeout=30` |
| **Full suite command** | `python -m pytest tests/ --timeout=60` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_multi_robot_viz.py -x --timeout=30`
- **After every plan wave:** Run `python -m pytest tests/ --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | VIZ-01 | unit | `python -m pytest tests/test_multi_robot_viz.py::test_log_merged_map -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | VIZ-01 | unit | `python -m pytest tests/test_multi_robot_viz.py::test_blueprint_layout -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | VIZ-02 | unit | `python -m pytest tests/test_multi_robot_viz.py::test_log_robot_pose -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | VIZ-02 | unit | `python -m pytest tests/test_multi_robot_viz.py::test_fading_trail -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | VIZ-03 | unit | `python -m pytest tests/test_multi_robot_viz.py::test_heatmap_colors -x` | ❌ W0 | ⬜ pending |
| 04-01-06 | 01 | 1 | VIZ-03 | unit | `python -m pytest tests/test_multi_robot_viz.py::test_heatmap_resolution -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | INT | unit | `python -m pytest tests/test_coordinator.py::test_viz_update_interval -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | INT | smoke | `python -m pytest tests/test_multi_mode.py::test_multi_mode_wiring -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_multi_robot_viz.py` — stubs for VIZ-01, VIZ-02, VIZ-03 (unit tests with mocked rr.log)
- [ ] `tests/test_multi_mode.py` — covers integration wiring of --control multi mode
- [ ] Test approach: mock `rr.log` and `rr.send_blueprint` to verify correct entity paths, colors, and data shapes without launching the Rerun viewer

*Existing `tests/` infrastructure from prior phases covers pytest setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual rendering quality of merged 3D map | VIZ-01 | Requires visual inspection of Rerun viewer output | Run `python src/main.py --control multi`, verify merged map renders correctly in Rerun |
| Fading trail visual appearance | VIZ-02 | Alpha gradient aesthetics require visual check | Observe trajectory trails fade from bright to dim |
| Voronoi plane translucency | VIZ-01 | Mesh3D alpha reliability is empirical | Verify translucent plane visible but not obstructing map |
| Stats HUD readability | VIZ-01 | Text layout requires visual check | Verify coverage %, per-robot stats, elapsed time visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
