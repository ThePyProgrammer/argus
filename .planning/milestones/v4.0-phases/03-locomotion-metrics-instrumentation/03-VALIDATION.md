---
phase: 3
slug: locomotion-metrics-instrumentation
status: passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-30
updated: 2026-05-03
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 with pytest-timeout 2.4.0 in project venv |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_locomotion_metrics_foot_mapping.py tests/locomotion/test_argus_go2_env_metrics.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/locomotion tests/metrics tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | ~60 seconds quick; full suite depends on MuJoCo integration runtime |
| **Passed evidence** | `03-VERIFICATION.md` records the quick metrics suite as `28 passed, 2 warnings in 1.89s` and the locomotion plus metrics wave suite as `196 passed, 2 warnings in 16.13s` |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_locomotion_metrics_foot_mapping.py tests/locomotion/test_argus_go2_env_metrics.py -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/locomotion tests/metrics -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for quick checks

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-W0-01 | 03-01 Task 1 | 1 | LOC-METRICS-01 | T-03-01 | Desired/measured velocity and yaw errors are computed from explicit test inputs and later env wiring uses world-frame pose deltas, not controller internals | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py::test_records_command_tracking_errors -q` | `tests/locomotion/test_locomotion_metrics_collector.py` exists; verified in `03-VERIFICATION.md` | passed |
| 03-W0-02 | 03-03 Task 1 | 3 | LOC-METRICS-02 | T-03-02 | Threshold failures set `terminated=True` and summarize distance before failure | env fake | `.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_metrics.py::test_failure_threshold_sets_terminated_true -q` | `tests/locomotion/test_argus_go2_env_metrics.py` exists; verified in `03-VERIFICATION.md` | passed |
| 03-W0-03 | 03-01 Task 1 | 1 | LOC-METRICS-03 | T-03-03 | Action-quality metrics are labeled as position-servo proxies and validate finite 12-joint targets | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py::test_records_action_quality_metrics -q` | `tests/locomotion/test_locomotion_metrics_collector.py` exists; verified in `03-VERIFICATION.md` | passed |
| 03-W0-04 | 03-02 Task 1 | 2 | LOC-METRICS-04 | T-03-04 | Missing or duplicate Go2 foot mappings fail fast, terrain-height helper covers flat/slope/rough, and clearance is not hardcoded to zero | unit + integration smoke | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_foot_mapping.py -q` | `tests/locomotion/test_locomotion_metrics_foot_mapping.py` exists; verified in `03-VERIFICATION.md` | passed |
| 03-W0-05 | 03-03 Task 1 | 3 | D-01/D-02/D-04 | T-03-05 | Per-step info stays compact and nested under `info["locomotion_metrics"]`; terminal/truncated info includes summary and accessor preserves latest completed summary | env fake | `.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_metrics.py::test_step_info_contains_nested_locomotion_metrics -q` | `tests/locomotion/test_argus_go2_env_metrics.py` exists; verified in `03-VERIFICATION.md` | passed |

Evidence basis: `03-VERIFICATION.md` verifies metrics collector, foot mapping, and env metrics coverage and reports `28 passed, 2 warnings in 1.89s` for the quick metrics suite plus `196 passed, 2 warnings in 16.13s` for the locomotion plus metrics wave suite.

---

## Wave 0 Requirements

Phase 3 used plan-first test creation instead of a separate pre-existing Wave 0 stub plan. Wave 0 is now complete because the tests were created and verified by `03-VERIFICATION.md`.

- [x] `03-01 Task 1` created `tests/locomotion/test_locomotion_metrics_collector.py` for LOC-METRICS-01/02/03 collector behavior and D-03/D-08/D-13 through D-16.
- [x] `03-02 Task 1` created `tests/locomotion/test_locomotion_metrics_foot_mapping.py` for LOC-METRICS-04 strict Go2 foot mapping, contact classification, terrain-height helper behavior, and non-flat clearance.
- [x] `03-03 Task 1` created `tests/locomotion/test_argus_go2_env_metrics.py` for env wiring, world-frame pose-delta command tracking convention, nested `info["locomotion_metrics"]`, terminal summaries, read-only `last_locomotion_metrics_summary`, and failure termination.
- [x] `03-04 Task 1` strengthened the same three test files with final behavior-level source-audit and boundary assertions.
- [x] Public action-bound helper or equivalent test-visible contract for joint-limit and saturation metrics was created by `03-01 Task 2` and verified through `joint_position_bounds()` coverage in `03-VERIFICATION.md`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | All Phase 3 requirements | All planned behaviors have automated unit, fake-env, or MuJoCo smoke coverage | N/A |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 coverage is mapped to plan-first test creation tasks and is complete
- [x] No watch-mode flags
- [x] Feedback latency < 60s for quick checks
- [x] `nyquist_compliant: true` set in frontmatter
- [x] `wave_0_complete: true` set in frontmatter based on `03-VERIFICATION.md` evidence

**Approval:** passed
