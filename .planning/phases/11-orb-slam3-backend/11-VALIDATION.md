---
phase: 11
slug: orb-slam3-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/slam/test_orbslam3_backend.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q --timeout=60` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/slam/test_orbslam3_backend.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/slam/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | BACK-01 | unit | `pytest tests/slam/test_orbslam3_backend.py -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | BACK-02 | unit | `pytest tests/slam/test_orbslam3_backend.py -x` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | BACK-01 | integration | `pytest tests/integration/test_orbslam3_e2e.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/slam/test_orbslam3_backend.py` — stubs for BACK-01, BACK-02
- [ ] `tests/integration/test_orbslam3_e2e.py` — stubs for end-to-end ORB-SLAM3 pipeline

*Existing test infrastructure (pytest, conftest) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full exploration pipeline with ORB-SLAM3 | BACK-01 | Requires MuJoCo sim + ORB-SLAM3 binary | Run `uv run c2`, select ORB-SLAM3, verify map builds |
| Robot marker color changes with tracking status | BACK-01 | Visual verification in browser | Check marker turns red on LOST, green on OK |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
