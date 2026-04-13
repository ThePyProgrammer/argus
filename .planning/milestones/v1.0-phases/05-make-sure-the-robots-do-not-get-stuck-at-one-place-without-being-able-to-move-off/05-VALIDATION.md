---
phase: 5
slug: robot-locomotion-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/conftest.py (exists) |
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

| Task ID | Plan | Wave | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | unit | `python -m pytest tests/test_locomotion.py -v` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | unit | `python -m pytest tests/test_stuck_recovery.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_locomotion.py` — stubs for position-controlled actuator gait and velocity-to-ctrl
- [ ] `tests/test_stuck_recovery.py` — stubs for turn-in-place recovery behavior

---

## Manual-Only Verifications

| Behavior | Why Manual | Test Instructions |
|----------|------------|-------------------|
| Robot visibly walks forward in MuJoCo | Requires visual confirmation | Run `--control random --max-steps 200`, observe robot translating |
| Multi-robot both move independently | Requires visual confirmation | Run `--control multi --multi-max-steps 200`, observe both robots moving |
| Stuck recovery turn in place | Requires visual confirmation | Run `--control explore`, wait for stuck detection, observe turn behavior |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
