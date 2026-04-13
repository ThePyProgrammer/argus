---
phase: 2
slug: autonomous-exploration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/conftest.py (exists from Phase 1) |
| **Quick run command** | `python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | EXPL-01 | unit | `python -m pytest tests/test_frontier_detector.py -v` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | EXPL-02 | unit | `python -m pytest tests/test_goal_selector.py -v` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | EXPL-02 | unit | `python -m pytest tests/test_path_planner.py -v` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | EXPL-02 | integration | `python -m pytest tests/test_exploration_loop.py -v` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | EXPL-03 | unit | `python -m pytest tests/test_coverage_tracker.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_frontier_detector.py` — stubs for EXPL-01 (frontier boundary detection)
- [ ] `tests/test_goal_selector.py` — stubs for EXPL-02 (goal selection policy)
- [ ] `tests/test_path_planner.py` — stubs for EXPL-02 (A* pathfinding)
- [ ] `tests/test_exploration_loop.py` — stubs for EXPL-02 (autonomous explore-map-navigate cycle)
- [ ] `tests/test_coverage_tracker.py` — stubs for EXPL-03 (coverage % tracking)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual frontier display in Rerun | EXPL-01 | Requires visual inspection of 3D voxel overlay | Run exploration, confirm frontier voxels highlighted in Rerun viewer |
| Robot movement in SimWorld | EXPL-02 | Requires running SimWorld gym environment | Run full exploration loop, observe robot navigating to frontiers |
| Coverage progress in logs | EXPL-03 | Requires running exploration loop | Verify periodic log output shows increasing coverage % |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
