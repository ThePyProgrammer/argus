---
phase: 06
slug: repair-evaluation-runner-semantics
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest, project dev dependency `>=8.0.0` |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` |
| **Full suite command** | `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | Quick gate should stay under ~5 minutes on normal CI hardware; split real MuJoCo smoke to supported environments if dependencies are unavailable. |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q`
- **After every plan wave:** Run `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green, with real MuJoCo smoke either passing in a supported environment or explicitly skipped by existing skip conditions.
- **Max feedback latency:** 5 minutes for quick gate; full suite may run longer depending on simulator availability.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | LOC-EVAL-01 | T-06-01 | Evaluator consumes env-provided current command without unsafe path or network behavior | unit + fake integration | `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | yes | ⬜ pending |
| 06-01-02 | 01 | 1 | LOC-EVAL-01 | T-06-01 | `ArgusGo2Env` exposes current command from simulation time using existing schedule semantics | unit/integration | `python -m pytest tests/locomotion -k current_command -q` | W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | LOC-METRICS-05, LOC-EVAL-02 | T-06-02 | Artifact writes remain contained and CSV formula-safe while preserving `stability.distance_xy_m` | artifact integration | `python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | yes | ⬜ pending |
| 06-03-01 | 03 | 3 | LOC-EVAL-04 | T-06-03 | Stationary command-ignoring controller fails commanded-locomotion baseline gate | unit + optional simulator smoke | `python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | yes | ⬜ pending |
| 06-03-02 | 03 | 3 | LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04 | T-06-12 | Phase gate runs deterministic quick suite without runtime LLM/network dependency | regression | `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` | yes | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/locomotion/test_locomotion_evaluation_runner.py` — add or tighten active-command transition fixture proving zero-at-reset then nonzero-after-transition drives fake env action.
- [ ] `tests/locomotion/test_argus_go2_env_contract.py` or existing env test file — assert `ArgusGo2Env._info()` exposes `current_command` at reset and after schedule transition.
- [ ] `tests/locomotion/test_locomotion_evaluation_exports.py` — add or tighten distance preservation fixture where `command_tracking` omits/zeroes distance and `stability.distance_xy_m` is nonzero.
- [ ] `tests/locomotion/test_locomotion_baseline_regression.py` — add stationary-controller negative fixture for commanded-locomotion baseline failure.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Nonzero real MuJoCo flat-ground smoke in supported environment | LOC-EVAL-04 | Local shell Python may be outside project-supported range and lack MuJoCo/Gymnasium | In a Python `>=3.10,<3.13` environment with dev dependencies installed, run `python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` and confirm real smoke passes or is skipped only by documented dependency/OS conditions. |
| Baseline threshold calibration | LOC-EVAL-04 | Exact minimum distance threshold may need locomotion controls review | Review fixed-seed flat-ground smoke artifacts and confirm threshold rejects stationary/no-op behavior without making the analytical baseline flaky. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5 minutes for quick gate
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 verification passes

**Approval:** pending
