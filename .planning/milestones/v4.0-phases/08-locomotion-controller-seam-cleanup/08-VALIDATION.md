---
phase: 08
slug: locomotion-controller-seam-cleanup
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-02
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/bridge/test_multi_bridge.py tests/test_locomotion_benchmark_docs.py -q` |
| **Full suite command** | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/test_locomotion_benchmark_docs.py -q` |
| **Estimated runtime** | quick: <60s; full: project-env dependent because MuJoCo tests require supported Python/dependencies |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/bridge/test_multi_bridge.py tests/test_locomotion_benchmark_docs.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/test_locomotion_benchmark_docs.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green in a project-supported Python 3.10-3.12 environment; if the local shell remains Python 3.14 without MuJoCo, record that limitation and run fake/fast tests locally.
- **Max feedback latency:** <60s for fast fake-runtime/docs/registry checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-W0-01 | TBD | 1 | LOC-CTRL-04 | T-08-01 | Invalid multi-robot controller output must fail before mutating `data.ctrl`. | unit / fake bridge | `uv run python -m pytest tests/bridge/test_multi_bridge.py tests/locomotion/test_controller_dispatch.py -q` | `tests/bridge/test_multi_bridge.py` exists | pending |
| 08-W0-02 | TBD | 1 | LOC-CTRL-04 | T-08-02 | Bad/duplicate/out-of-range indexed controls cannot corrupt another robot's controls. | unit / fake bridge | `uv run python -m pytest tests/bridge/test_multi_bridge.py tests/locomotion/test_controller_dispatch.py -q` | `tests/locomotion/test_controller_dispatch.py` exists | pending |
| 08-W0-03 | TBD | 1 | LOC-CTRL-03 | T-08-03 | WBC placeholder metadata must not imply a runnable v4.0 env action mode without explicit deferred wording. | unit | `uv run python -m pytest tests/locomotion/test_locomotion_controller_registry.py -q` | `tests/locomotion/test_locomotion_controller_registry.py` exists | pending |
| 08-W0-04 | TBD | 1 | LOC-REPORT-02 | T-08-03 | Controller-family docs and registry metadata must agree on WBC placeholder vocabulary. | docs guard | `uv run python -m pytest tests/test_locomotion_benchmark_docs.py -q` | `tests/test_locomotion_benchmark_docs.py` exists | pending |
| 08-W0-05 | TBD | 1 | LOC-REPORT-02 | T-08-04 | Phase 7 evaluator action-mode rejection must remain intact after metadata cleanup. | unit | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py::test_unknown_action_mode_fails_before_env_construction tests/locomotion/test_locomotion_evaluation_runner.py::test_unsupported_action_modes_fail_before_env_construction -q` | `tests/locomotion/test_locomotion_evaluation_runner.py` exists | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/bridge/test_multi_bridge.py` — add fake-runtime regression proving invalid per-robot output fails before mutating `data.ctrl` for indexed multi-robot application.
- [ ] `tests/bridge/test_multi_bridge.py` or `tests/bridge/test_multi_bridge_platform_selection.py` — add regression that states the chosen Go2 registry/dispatch unification or explicit platform-runtime boundary.
- [ ] `tests/locomotion/test_locomotion_controller_registry.py` — add WBC placeholder metadata vocabulary assertion.
- [ ] `tests/test_locomotion_benchmark_docs.py` — add docs/registry guard for WBC placeholder vocabulary.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full MuJoCo bridge integration in local shell | LOC-CTRL-04 | Local Python 3.14 is outside project-supported `>=3.10,<3.13` and research found MuJoCo missing in that probe. | Use `uv` with Python 3.10-3.12 and run the full suite command before verification. |

---

## Validation Sign-Off

- [x] All phase requirements have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency <60s for fast fake-runtime/docs/registry checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
