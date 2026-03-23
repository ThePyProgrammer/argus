---
phase: 8
slug: backend-abstraction-icp-wrap
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/slam/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/slam/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | ABST-01 | unit | `pytest tests/slam/test_slam_protocol.py -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | ABST-02 | unit | `pytest tests/slam/test_slam_registry.py -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | ABST-06 | integration | `pytest tests/slam/test_icp_backend.py -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | ABST-03 | unit | `pytest tests/slam/test_parameter_schema.py -x` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 1 | ABST-04 | unit | `pytest tests/slam/test_capabilities.py -x` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 2 | ABST-05 | integration | `pytest tests/api/test_slam_api.py -x` | ❌ W0 | ⬜ pending |
| 08-03-02 | 03 | 2 | ABST-05 | e2e | `pytest tests/test_slam_restart.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/slam/test_slam_protocol.py` — stubs for ABST-01 (SLAMProtocol interface)
- [ ] `tests/slam/test_slam_registry.py` — stubs for ABST-02 (registry discover/list/instantiate)
- [ ] `tests/slam/test_icp_backend.py` — stubs for ABST-06 (ICP wrapped as backend)
- [ ] `tests/slam/test_parameter_schema.py` — stubs for ABST-03 (JSON Schema params)
- [ ] `tests/slam/test_capabilities.py` — stubs for ABST-04 (capability queries)
- [ ] `tests/api/test_slam_api.py` — stubs for ABST-05 (REST endpoints)

*Existing test infrastructure (pytest, conftest) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full simulation runs identically to v1.0 with ICP backend | ABST-06 | Regression requires running full sim loop | Run `python -m src.main`, verify robots explore and map merges |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
