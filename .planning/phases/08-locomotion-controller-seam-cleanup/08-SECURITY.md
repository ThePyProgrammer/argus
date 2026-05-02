---
phase: 08
slug: locomotion-controller-seam-cleanup
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-03
---

# Phase 08 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Platform controller -> MultiRobotBridge | Platform-local controller output crosses into physics control mutation. | Numeric actuator target arrays |
| MultiRobotBridge ctrl_indices -> MuJoCo data.ctrl | Per-robot actuator indices choose which physics control slots can be mutated. | Actuator index lists and target values |
| ControllerRegistry metadata -> docs/evaluation users | Placeholder metadata can be mistaken for runnable controller/action support. | Controller capability metadata and docs |
| CLI action-mode input -> evaluation runner | User-provided action-mode strings must fail before env construction/artifact creation when unsupported. | CLI action-mode strings |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Tampering | `MultiRobotBridge.step()` and startup controller output | mitigate | `src/bridge/multi_bridge.py:162`, `src/bridge/multi_bridge.py:225`, and `src/bridge/multi_bridge.py:427` route controller targets through `_apply_platform_controller_target()`, which validates one-dimensional float shape and finite values before the single mutation at `src/bridge/multi_bridge.py:458`; guarded by `tests/bridge/test_multi_bridge.py:296` and `tests/bridge/test_multi_bridge.py:339`. | closed |
| T-08-02 | Tampering | `MultiRobotBridge._ctrl_indices` indexed control application | mitigate | `_apply_platform_controller_target()` validates index count, duplicate indices, and bounds at `src/bridge/multi_bridge.py:441` through `src/bridge/multi_bridge.py:457` before assigning `data.ctrl`; guarded by duplicate/out-of-range no-mutation coverage at `tests/bridge/test_multi_bridge.py:320`. | closed |
| T-08-03 | Spoofing | `WBCController.CAPABILITIES` and controller-family docs | mitigate | WBC advertises `undefined_deferred` and `env_action_mode is None` at `src/locomotion/controllers.py:487` through `src/locomotion/controllers.py:489`; docs state it is not a v4.0 env action mode at `docs/locomotion-benchmark.md:122`; guarded by `tests/locomotion/test_locomotion_controller_registry.py:158` and `tests/test_locomotion_benchmark_docs.py:109`. | closed |
| T-08-04 | Repudiation | `argus eval-locomotion` action-mode rejection/reporting | mitigate | `undefined_deferred` is absent from `src/locomotion/actions.py` supported action-mode constants and remains outside `available_action_modes()`; Phase 7 rejection behavior is preserved by `tests/locomotion/test_locomotion_evaluation_runner.py:170` and `tests/locomotion/test_locomotion_evaluation_runner.py:191`. | closed |

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-03 | 4 | 4 | 0 | Claude Code |

### Security Audit 2026-05-03

| Metric | Count |
|--------|-------|
| Threats found | 4 |
| Closed | 4 |
| Open | 0 |

Verification run:

```bash
uv run python -m pytest tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/test_locomotion_benchmark_docs.py tests/locomotion/test_locomotion_evaluation_runner.py::test_unknown_action_mode_fails_before_env_construction tests/locomotion/test_locomotion_evaluation_runner.py::test_unsupported_action_modes_fail_before_env_construction -q
```

Result: 65 passed.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-03
