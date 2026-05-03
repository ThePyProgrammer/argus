---
phase: 1
slug: locomotion-env-contract
status: passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-30
updated: 2026-05-03
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
| **Passed evidence** | `01-VERIFICATION.md` records the full phase gate: `.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` → `134 passed in 9.51s` |

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
| 1-01-01 | 01 | 0 | LOC-ENV-01 | T-1-01 | Environment imports only supported named dependencies and exposes Gymnasium spaces | unit | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` | `tests/locomotion/test_argus_go2_env_contract.py` exists; verified in `01-VERIFICATION.md` | passed |
| 1-02-01 | 02 | 1 | LOC-ENV-02 | T-1-02 | Scenario selection uses named catalog entries, not arbitrary paths | unit | `python -m pytest tests/locomotion/test_argus_go2_env_scenarios.py -q -x` | `tests/locomotion/test_argus_go2_env_scenarios.py` exists; verified in `01-VERIFICATION.md` | passed |
| 1-03-01 | 03 | 1 | LOC-ENV-03 | T-1-03 | Reset derives spawn pose, terrain parameters, command schedule, and disturbance timing from the reset RNG | unit + integration | `python -m pytest tests/locomotion/test_argus_go2_env_determinism.py -q -x` | `tests/locomotion/test_argus_go2_env_determinism.py` exists; verified in `01-VERIFICATION.md` | passed |
| 1-04-01 | 04 | 1 | LOC-ENV-04 | T-1-04 | Action decoding validates mode-specific shape and finite values before writing MuJoCo controls | unit | `python -m pytest tests/locomotion/test_argus_go2_env_action_modes.py -q -x` | `tests/locomotion/test_argus_go2_env_action_modes.py` exists; verified in `01-VERIFICATION.md` | passed |
| 1-05-01 | 05 | 2 | Runtime preservation | T-1-05 | Existing non-Gym bridge public behavior remains unchanged | regression | `python -m pytest tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q -x` | Existing bridge tests passed in the `01-VERIFICATION.md` full phase gate | passed |

Evidence basis: `01-VERIFICATION.md` verified the required artifacts and reported the full locomotion/bridge phase gate as `134 passed in 9.51s`.

---

## Wave 0 Requirements

- [x] `tests/locomotion/test_argus_go2_env_contract.py` — implemented and verified for LOC-ENV-01 in `01-VERIFICATION.md`.
- [x] `tests/locomotion/test_argus_go2_env_scenarios.py` — implemented and verified for LOC-ENV-02 in `01-VERIFICATION.md`.
- [x] `tests/locomotion/test_argus_go2_env_determinism.py` — implemented and verified for LOC-ENV-03 in `01-VERIFICATION.md`.
- [x] `tests/locomotion/test_argus_go2_env_action_modes.py` — implemented and verified for LOC-ENV-04 in `01-VERIFICATION.md`.
- [x] `pyproject.toml` — contains the runtime Gymnasium dependency; `01-VERIFICATION.md` cites `gymnasium>=1.3.0`.
- [x] Project-supported Python 3.10-3.12 environment with `mujoco` available for integration checks — full gate in `01-VERIFICATION.md` passed with `134 passed in 9.51s`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm the non-Gym C2 runtime still starts | Runtime preservation | Optional local runtime smoke; Phase 1 verification already included bridge regression coverage and confirmed bridge files were unchanged | Run the existing web/simulation boot command used by the project if a fresh visual C2 smoke is desired. |

---

## Validation Sign-Off

- [x] All phase requirements have planned automated tests or Wave 0 dependencies.
- [x] Sampling continuity has a focused test command for each requirement area.
- [x] Wave 0 lists all missing test artifacts.
- [x] No watch-mode flags are required.
- [x] Feedback latency target is under 60 seconds for focused tests.
- [x] `nyquist_compliant: true` set in frontmatter.
- [x] `wave_0_complete: true` set in frontmatter based on `01-VERIFICATION.md` evidence.

**Approval:** passed
