---
phase: 10
slug: pose-graph-map-merger
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 with pytest-timeout |
| **Config file** | pytest.ini |
| **Quick run command** | `python -m pytest tests/coordination/ -x -q --timeout=30` |
| **Full suite command** | `python -m pytest tests/ -x -q --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/coordination/ -x -q --timeout=30`
- **After every plan wave:** Run `python -m pytest tests/ -x -q --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-T1 | 01 | 1 | MERG-01 | unit | `python -m pytest tests/coordination/test_merge_registry.py -x` | W0 | pending |
| 10-01-T2 | 01 | 1 | MERG-01 | unit | `python -m pytest tests/coordination/test_merge_strategies.py -x` | W0 | pending |
| 10-02-T1 | 02 | 2 | MERG-01, MERG-03 | unit | `python -m pytest tests/coordination/test_merge_strategies.py::TestOpen3DPGO tests/coordination/test_merge_strategies.py::TestPGOLoopClosure tests/coordination/test_merge_strategies.py::TestLoopClosureFallback -x` | W0 | pending |
| 10-02-T2 | 02 | 2 | MERG-01, MERG-03 | unit | `python -m pytest tests/coordination/test_merge_strategies.py::TestGTSAMPGO -x` | W0 | pending |
| 10-03-T1 | 03 | 2 | MERG-02 | unit | `python -m pytest tests/web/test_merge_routes.py -x` | W0 | pending |
| 10-03-T2 | 03 | 2 | MERG-04 | unit | `python -m pytest tests/coordination/test_coordinator.py -x` | update | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/coordination/test_merge_registry.py` — stubs for MERG-01 registry discovery
- [ ] `tests/coordination/test_merge_strategies.py` — stubs for MERG-01, MERG-03, MERG-04 strategy behavior
- [ ] `tests/web/test_merge_routes.py` — stubs for MERG-02 REST API
- [ ] Update `tests/coordination/test_coordinator.py` — verify MergeProtocol integration

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Merge strategy selector in frontend | MERG-02 | Frontend UI rendering | Start session, verify dropdown shows 3 strategies |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
