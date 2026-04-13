---
phase: 3
slug: multi-robot-coordination-and-map-merging
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/conftest.py (exists from Phase 1) |
| **Quick run command** | `python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | COORD-01 | unit | `python -m pytest tests/test_multi_bridge.py -v` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | COORD-02 | unit | `python -m pytest tests/test_voronoi.py -v` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | MERGE-01, MERGE-02, MERGE-03 | unit | `python -m pytest tests/test_map_merger.py -v` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | COORD-03 | unit | `python -m pytest tests/test_coordinator.py -v` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 3 | MERGE-04, COORD-01 | integration | `python -m pytest tests/test_multi_robot_integration.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_multi_bridge.py` — stubs for COORD-01 (two-robot MuJoCo bridge)
- [ ] `tests/test_voronoi.py` — stubs for COORD-02 (Voronoi partitioning)
- [ ] `tests/test_map_merger.py` — stubs for MERGE-01, MERGE-02, MERGE-03 (map merging)
- [ ] `tests/test_coordinator.py` — stubs for COORD-03 (re-partitioning coordinator)
- [ ] `tests/test_multi_robot_integration.py` — stubs for MERGE-04 (real-time incremental merging)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Two robots visible in Rerun | COORD-01 | Visual verification | Run multi-robot mode, confirm both trajectories render in Rerun |
| Merged map grows in real-time | MERGE-04 | Visual verification | Run multi-robot exploration, confirm unified map updates live in Rerun |
| Voronoi regions visible | COORD-02 | Visual verification | Confirm Voronoi boundary line renders in Rerun between robot positions |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
