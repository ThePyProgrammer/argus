---
phase: 07
slug: align-evaluation-action-mode-contract
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 in the uv-managed Python environment |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q` |
| **Full suite command** | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | ~35 seconds for the quick gate; full locomotion/bridge gate may take longer |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`
- **Before `/gsd-verify-work`:** Full locomotion plus bridge regression gate must be green
- **Max feedback latency:** ~60 seconds for the focused phase gate

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-W0-01 | TBD | 0 | LOC-ENV-04 | T-07-01 | Unsupported or unevaluable action modes fail before env construction and before run artifacts are created | runner/export contract | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` | ✅ | ⬜ pending |
| 07-W0-02 | TBD | 0 | LOC-ENV-04 | T-07-02 | `velocity_command` evaluation actions preserve Phase 6 same-index command semantics and match the env action space | runner contract | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_argus_go2_env_action_modes.py -q` | ✅ | ⬜ pending |
| 07-W0-03 | TBD | 0 | LOC-EVAL-03 | T-07-03 | Completed-run metadata records the action mode actually stepped; rejected modes do not produce completed-run metadata | export contract | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | ✅ | ⬜ pending |
| 07-W0-04 | TBD | 0 | LOC-ENV-04, LOC-EVAL-03 | — | CLI help and benchmark docs state the implemented evaluation action-mode contract | CLI/docs contract | `uv run python -m pytest tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/locomotion/test_locomotion_evaluation_runner.py` — pre-env-construction rejection tests for unknown/unsupported action modes and same-index `velocity_command` action semantics.
- [ ] `tests/locomotion/test_locomotion_evaluation_exports.py` — completed-run action-mode metadata assertions and no-artifact assertions for preflight rejection.
- [ ] `tests/test_main_args.py` — eval help text assertion for supported versus rejected/deferred action-mode behavior.
- [ ] `tests/test_locomotion_benchmark_docs.py` — benchmark guide assertion for the same action-mode contract.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 coverage is implemented and passing

**Approval:** pending
