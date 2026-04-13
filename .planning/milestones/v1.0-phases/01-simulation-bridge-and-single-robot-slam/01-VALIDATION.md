---
phase: 1
slug: simulation-bridge-and-single-robot-slam
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (aliased in Nix flake: `python -m pytest`) |
| **Config file** | None — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/ -x --timeout=30` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x --timeout=30`
- **After every plan wave:** Run `python -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | SIM-01 | integration | `python -m pytest tests/test_sim_bridge.py::test_lifecycle -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | SIM-02 | integration | `python -m pytest tests/test_sim_bridge.py::test_sensor_extraction -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | SIM-03 | integration | `python -m pytest tests/test_sim_bridge.py::test_movement_command -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | SIM-04 | integration | `python -m pytest tests/test_sim_bridge.py::test_ground_truth_pose -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | SLAM-01 | integration | `python -m pytest tests/test_slam_pipeline.py::test_slam_processes_frames -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | SLAM-02 | integration | `python -m pytest tests/test_slam_pipeline.py::test_point_cloud_output -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 2 | SLAM-03 | unit | `python -m pytest tests/test_octomap_builder.py::test_occupancy_grid -x` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 2 | SLAM-04 | unit | `python -m pytest tests/test_drift_metrics.py::test_ate_rpe -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest.ini` — basic pytest configuration with timeout
- [ ] `tests/__init__.py` — test package init
- [ ] `tests/conftest.py` — shared fixtures (mock SimWorld env, sample sensor data)
- [ ] `tests/test_sim_bridge.py` — SIM-01 through SIM-04
- [ ] `tests/test_slam_pipeline.py` — SLAM-01, SLAM-02
- [ ] `tests/test_octomap_builder.py` — SLAM-03
- [ ] `tests/test_drift_metrics.py` — SLAM-04
- [ ] Framework install: `pip install pytest pytest-timeout`

*Note: SIM-01 through SIM-04 tests require SimWorld to be running. These are integration tests that may need to be skipped in CI. SLAM-03 and SLAM-04 can be unit-tested with synthetic data.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Point cloud visually resembles environment | SLAM-02 | Visual quality judgment | View Rerun dashboard, compare point cloud shape to SimWorld scene |
| Keyboard teleop responsive | SIM-03 | Requires human interaction | Press WASD keys, verify robot moves in expected directions |
| Rerun dashboard streams live | VIZ (Phase 4 prep) | Visual streaming check | Run system, verify Rerun window updates in real-time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
