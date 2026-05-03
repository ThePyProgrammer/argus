---
phase: 06
slug: repair-evaluation-runner-semantics
status: passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-01
updated: 2026-05-03
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest, project dev dependency `>=8.0.0` |
| **Config file** | `pytest.ini` |
| **Quick run command** | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` |
| **Full suite command** | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | Quick gate should stay under ~5 minutes on normal CI hardware; split real MuJoCo smoke to supported environments if dependencies are unavailable. |
| **Passed evidence** | `06-VERIFICATION.md` records the quick gate as `32 passed in 4.58s`, the full locomotion plus bridge gate as `248 passed in 16.06s`, and runtime AI SDK absence as `no output` |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green, with real MuJoCo smoke either passing in a supported environment or explicitly skipped by existing skip conditions.
- **Max feedback latency:** 5 minutes for quick gate; full suite may run longer depending on simulator availability.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | LOC-EVAL-01 | T-06-01 | Evaluator consumes env-provided current command without unsafe path or network behavior | unit + fake integration | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | yes; verified in `06-VERIFICATION.md` | passed |
| 06-01-02 | 01 | 1 | LOC-EVAL-01 | T-06-01 | `ArgusGo2Env` exposes current command from simulation time using existing schedule semantics | unit/integration | `uv run python -m pytest tests/locomotion -k current_command -q` | `tests/locomotion/test_argus_go2_env_contract.py` coverage verified in `06-VERIFICATION.md` | passed |
| 06-02-01 | 02 | 2 | LOC-METRICS-05, LOC-EVAL-02 | T-06-02 | Artifact writes remain contained and CSV formula-safe while preserving `stability.distance_xy_m` | artifact integration | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | yes; verified in `06-VERIFICATION.md` | passed |
| 06-03-01 | 03 | 3 | LOC-EVAL-04 | T-06-03 | Stationary command-ignoring controller fails commanded-locomotion baseline gate | unit + optional simulator smoke | `uv run python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | yes; verified in `06-VERIFICATION.md` | passed |
| 06-03-02 | 03 | 3 | LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04 | T-06-12 | Phase gate runs deterministic quick suite without runtime LLM/network dependency | regression | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` | yes; `06-VERIFICATION.md` quick gate passed and AI SDK grep returned no output | passed |

Evidence basis: `06-VERIFICATION.md` verifies active-command evaluation, export distance preservation, stationary baseline rejection, CLI wiring, output safety, and runtime AI SDK absence. Its acceptance commands report `32 passed in 4.58s`, `248 passed in 16.06s`, and `no output` for the AI SDK dependency scan.

*Status: passed · green · no active unsupported-interpreter blocker remains after uv-based verification.*

---

## Wave 0 Requirements

- [x] `tests/locomotion/test_locomotion_evaluation_runner.py` — active-command transition fixture proves zero-at-reset then nonzero-after-transition drives fake env action; verified in `06-VERIFICATION.md`.
- [x] `tests/locomotion/test_argus_go2_env_contract.py` or existing env test file — asserts `ArgusGo2Env._info()` exposes `current_command` at reset and after schedule transition; verified in `06-VERIFICATION.md`.
- [x] `tests/locomotion/test_locomotion_evaluation_exports.py` — distance preservation fixture keeps `stability.distance_xy_m` nonzero in artifacts; verified in `06-VERIFICATION.md`.
- [x] `tests/locomotion/test_locomotion_baseline_regression.py` — stationary-controller negative fixture for commanded-locomotion baseline failure; verified in `06-VERIFICATION.md`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Nonzero real MuJoCo flat-ground smoke in supported environment | LOC-EVAL-04 | Optional calibration review only; `06-VERIFICATION.md` already records uv-based quick and full gates passing | Re-run `uv run python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` if a fresh local smoke is desired. |
| Baseline threshold calibration | LOC-EVAL-04 | Exact minimum distance threshold can receive future locomotion-controls review, but stationary/no-op rejection is already covered | Review fixed-seed flat-ground smoke artifacts if thresholds are intentionally changed in a later plan. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5 minutes for quick gate
- [x] `nyquist_compliant: true` set in frontmatter after Wave 0 verification passes
- [x] `wave_0_complete: true` set in frontmatter based on `06-VERIFICATION.md` evidence

## Automated Evidence Attempt — 2026-05-01

- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` — passed in `06-VERIFICATION.md`: `32 passed in 4.58s`.
- `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` — passed in `06-VERIFICATION.md`: `248 passed in 16.06s`.
- `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" /home/prannayag/pragnition/robotics/argus/src /home/prannayag/pragnition/robotics/argus/pyproject.toml /home/prannayag/pragnition/robotics/argus/tests 2>/dev/null` — passed in `06-VERIFICATION.md`: `no output`; no runtime AI SDK dependency found.

**Approval:** passed
