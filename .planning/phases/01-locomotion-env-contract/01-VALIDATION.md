---
phase: 1
slug: locomotion-env-contract
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` |
| **Full suite command** | `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | ~30 seconds for focused contract tests; integration runtime depends on MuJoCo availability |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` plus the focused test file for the module changed by that task.
- **After every plan wave:** Run `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`.
- **Before `/gsd-verify-work`:** Full locomotion and bridge suite must be green in a project-supported Python 3.10-3.12 environment with MuJoCo installed.
- **Max feedback latency:** 60 seconds for focused tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | LOC-ENV-01 | T-1-01 | Environment imports only supported named dependencies and exposes Gymnasium spaces | unit | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` | No; create in Wave 0 | pending |
| 1-02-01 | 02 | 1 | LOC-ENV-02 | T-1-02 | Scenario selection uses named catalog entries, not arbitrary paths | unit | `python -m pytest tests/locomotion/test_argus_go2_env_scenarios.py -q -x` | No; create in Wave 0 | pending |
| 1-03-01 | 03 | 1 | LOC-ENV-03 | T-1-03 | Reset derives spawn pose, terrain parameters, command schedule, and disturbance timing from the reset RNG | unit + integration | `python -m pytest tests/locomotion/test_argus_go2_env_determinism.py -q -x` | No; create in Wave 0 | pending |
| 1-04-01 | 04 | 1 | LOC-ENV-04 | T-1-04 | Action decoding validates mode-specific shape and finite values before writing MuJoCo controls | unit | `python -m pytest tests/locomotion/test_argus_go2_env_action_modes.py -q -x` | No; create in Wave 0 | pending |
| 1-05-01 | 05 | 2 | Runtime preservation | T-1-05 | Existing non-Gym bridge public behavior remains unchanged | regression | `python -m pytest tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q -x` | Existing bridge tests may need dependency-gated execution | pending |

---

## Wave 0 Requirements

- [ ] `tests/locomotion/test_argus_go2_env_contract.py` — stubs and failing tests for LOC-ENV-01.
- [ ] `tests/locomotion/test_argus_go2_env_scenarios.py` — stubs and failing tests for LOC-ENV-02.
- [ ] `tests/locomotion/test_argus_go2_env_determinism.py` — stubs and failing tests for LOC-ENV-03.
- [ ] `tests/locomotion/test_argus_go2_env_action_modes.py` — stubs and failing tests for LOC-ENV-04.
- [ ] `pyproject.toml` — add `gymnasium` dependency or benchmark extra before tests import `gymnasium`.
- [ ] Project-supported Python 3.10-3.12 environment with `mujoco` available for integration checks.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm the non-Gym C2 runtime still starts | Runtime preservation | The web runtime may need local services or rendering dependencies outside unit tests | Run the existing web/simulation boot command used by the project and confirm no import/startup regression after the env wrapper is added. |

---

## Validation Sign-Off

- [x] All phase requirements have planned automated tests or Wave 0 dependencies.
- [x] Sampling continuity has a focused test command for each requirement area.
- [x] Wave 0 lists all missing test artifacts.
- [x] No watch-mode flags are required.
- [x] Feedback latency target is under 60 seconds for focused tests.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
