---
phase: 12
slug: openvins-svo-pro-backends
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/slam/test_subprocess_bridge.py tests/slam/test_openvins_backend.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q --timeout=60` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run `python -m pytest tests/slam/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | BACK-06 | unit | `pytest tests/slam/test_subprocess_bridge.py -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | BACK-04 | unit | `pytest tests/bridge/test_imu_extraction.py -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | BACK-03 | unit | `pytest tests/slam/test_openvins_backend.py -x` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 3 | BACK-05 | unit | `pytest tests/slam/test_svopro_backend.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/slam/test_subprocess_bridge.py` — stubs for BACK-06 (subprocess isolation)
- [ ] `tests/bridge/test_imu_extraction.py` — stubs for BACK-04 (IMU extraction)
- [ ] `tests/slam/test_openvins_backend.py` — stubs for BACK-03 (OpenVINS)
- [ ] `tests/slam/test_svopro_backend.py` — stubs for BACK-05 (SVO Pro/DSO)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full pipeline with OpenVINS | BACK-03 | Requires C++ binary + MuJoCo sim | Build OpenVINS, run sim, select OpenVINS, verify map builds |
| Crash recovery fallback to ICP | BACK-06 | Requires killing subprocess | Start with OpenVINS, kill subprocess, verify ICP fallback + toast |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
