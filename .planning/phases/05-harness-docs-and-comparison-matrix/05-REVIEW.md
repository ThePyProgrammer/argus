---
phase: 05-harness-docs-and-comparison-matrix
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - README.md
  - docs/locomotion-benchmark.md
  - src/locomotion/__init__.py
  - src/locomotion/controllers.py
  - tests/locomotion/test_locomotion_controller_registry.py
  - tests/test_locomotion_benchmark_docs.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the locomotion benchmark documentation, controller registry implementation, lazy locomotion package export, and the related documentation/registry guard tests. The residual-policy documentation mismatch from the prior review has been fixed, but the same metadata-contract problem remains for other controller rows: the registry still advertises action modes that do not match the documented/public benchmark action-mode surface, and the tests only pin the residual case.

## Warnings

### WR-01: Analytical controller metadata advertises the wrong public action mode

**File:** `src/locomotion/controllers.py:359`
**Issue:** `AnalyticalTrotController.CAPABILITIES` advertises `action_mode` as `joint_position`, while the canonical guide says the supported analytical baseline uses the default `velocity_command` action mode (`docs/locomotion-benchmark.md:118`) and the smoke command in both docs uses `analytical_trot` without selecting `joint_position` (`README.md:318`, `docs/locomotion-benchmark.md:14`). This makes `controller_metadata` report a different action-mode seam from the one users actually exercise through `ArgusGo2Env` for the supported baseline. Any matrix generator or validation code using registry metadata will pair `analytical_trot` with `joint_position` instead of the documented/default velocity-command path.
**Fix:** Treat `CAPABILITIES["action_mode"]` as the benchmark input seam and align it with the documented default. Add a guard test so this cannot drift again.

```python
def _analytical_capabilities() -> dict[str, Any]:
    return {
        "family": "analytical",
        "action_mode": "velocity_command",
        "deterministic": True,
        # ...
    }
```

### WR-02: WBC placeholder advertises an unsupported action mode

**File:** `src/locomotion/controllers.py:487`
**Issue:** The WBC placeholder registers `action_mode` as `torque_or_joint_position`, but the benchmark action-mode registry only supports `velocity_command`, `joint_position`, and `residual_baseline`. The documentation correctly says torque/whole-body-control infrastructure is not implemented (`docs/locomotion-benchmark.md:122`), yet the controller registry exposes a mode string that `build_action_space()` and `decode_action()` cannot handle. Even while unavailable, this is bad contract metadata: tooling that lists controller capabilities or prepares future matrix configs from registry output will emit an invalid action mode.
**Fix:** Do not expose action-mode values outside the supported public vocabulary. Use the existing supported seam for the placeholder, or add a separate future-mode field if the point is to document deferred torque support.

```python
@locomotion_controller(name="wbc", display="Whole-Body Control")
class WBCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("wbc", "joint_position")
    UNAVAILABLE_REASON = WBC_UNAVAILABLE_REASON
```

Also extend `test_controller_registry_entries_expose_capabilities_and_parameter_schema` to assert every `entry["capabilities"]["action_mode"]` is in `available_action_modes()`.

---

_Reviewed: 2026-05-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
