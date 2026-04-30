---
phase: 2
slug: controller-plugin-baseline
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 local; project declares `pytest>=8.0.0` and `pytest-timeout>=2.0.0` |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_locomotion_controller_protocol.py -q -x` |
| **Full suite command** | `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | Pure registry/protocol tests should run in under 30 seconds; full MuJoCo/Gymnasium suite requires a supported Python 3.10-3.12 project environment |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_locomotion_controller_protocol.py -q -x` plus any focused test file for changed env/bridge modules.
- **After every plan wave:** Run `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` in a supported project environment.
- **Before `/gsd-verify-work`:** Full locomotion and bridge suite must be green, or the verification report must record the missing dependency/environment blocker.
- **Max feedback latency:** 60 seconds for pure controller registry/protocol changes.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 02-01 | 1 | LOC-CTRL-01, LOC-CTRL-02, LOC-CTRL-03 | T-2-01, T-2-02 | Unknown/unavailable controller ids fail deterministically before runtime control application | unit | `python -m pytest tests/locomotion/test_locomotion_controller_registry.py -q -x` | No - Wave 0 | pending |
| 2-02-01 | 02-02 | 1 | LOC-CTRL-01, LOC-CTRL-02 | T-2-03 | Controller output is finite shape `(12,)` before any bridge/control sink consumes it | unit | `python -m pytest tests/locomotion/test_locomotion_controller_protocol.py -q -x` | No - Wave 0 | pending |
| 2-03-01 | 02-03 | 2 | LOC-CTRL-01, LOC-CTRL-04 | T-2-03 | Shared dispatch validates finite target shape before applying controls | unit | `python -m pytest tests/locomotion/test_controller_dispatch.py -q -x` | No - Wave 0 | pending |
| 2-04-01 | 02-04 | 3 | LOC-CTRL-04 | T-2-04 | Single-robot bridge public `step() -> SensorFrame` behavior is preserved while sourcing controls through the registered analytical baseline | regression | `python -m pytest tests/bridge/test_sim_bridge.py -q -x` | Existing | pending |
| 2-05-01 | 02-05 | 3 | LOC-CTRL-04 | T-2-04 | Multi-robot bridge public `step() -> dict[str, SensorFrame]` behavior is preserved with one controller instance per robot | regression | `python -m pytest tests/bridge/test_multi_bridge.py -q -x` | Existing | pending |
| 2-06-01 | 02-06 | 4 | LOC-CTRL-02, controller metadata decisions D-13/D-15 | T-2-05 | Reset info contains full controller metadata and step info contains compact controller attribution | regression | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` | Existing | pending |

---

## Wave 0 Requirements

- [ ] `tests/locomotion/test_locomotion_controller_registry.py` — covers LOC-CTRL-01, LOC-CTRL-02, LOC-CTRL-03, default id, registry listing, capability metadata, unavailable placeholder reasons, and lazy import behavior.
- [ ] `tests/locomotion/test_locomotion_controller_protocol.py` — covers `LocomotionCommand`, `ControllerResult`, protocol shape, deterministic reset isolation, and finite `(12,)` analytical baseline outputs.
- [ ] `tests/locomotion/test_controller_dispatch.py` — covers shared target validation and single/multi control-sink application using fake data objects.
- [ ] Extend `tests/locomotion/test_argus_go2_env_contract.py` — covers full reset metadata and compact per-step controller attribution.
- [ ] Extend existing bridge tests only where needed to assert the controller seam preserves public return types.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full MuJoCo/Gymnasium bridge smoke in this local shell | LOC-CTRL-02, LOC-CTRL-04 | Current shell uses Python 3.14.4 while the project supports Python `>=3.10,<3.13`, and this interpreter lacks `gymnasium` and `mujoco` | Use a supported project environment and run `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target documented for pure unit tests.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
