---
phase: 08-locomotion-controller-seam-cleanup
reviewed: 2026-05-02T16:43:33Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - docs/locomotion-benchmark.md
  - src/bridge/multi_bridge.py
  - src/locomotion/controllers.py
  - tests/bridge/test_multi_bridge.py
  - tests/bridge/test_multi_bridge_platform_selection.py
  - tests/locomotion/test_locomotion_controller_registry.py
  - tests/test_locomotion_benchmark_docs.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-02T16:43:33Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the listed bridge, locomotion controller registry, documentation, and related tests at standard depth. The main correctness risk is in the new platform/config seam: valid-looking `MultiRobotConfig` inputs can crash during bridge construction, and the analytical controller metadata now contradicts the evaluator and documentation action-mode contract, which can corrupt benchmark metadata and compatibility checks.

## Critical Issues

### CR-01: Go2 `platform_config` can crash bridge construction with duplicate `model_dir`

**File:** `src/bridge/multi_bridge.py:43-47`

**Issue:** `MultiRobotBridge.__init__` always injects `model_dir=self._config.model_dir` for `platform == "go2"` and then expands `self._config.platform_config`. If callers use the newly documented/configured seam with `MultiRobotConfig(platform="go2", platform_config={"model_dir": "..."})`, Python raises `TypeError: create_platform() got multiple values for keyword argument 'model_dir'` before the bridge can start. That makes a valid platform config path unusable and is not covered by the new tests.

**Fix:** Merge kwargs once, letting explicit `platform_config` override the legacy `model_dir` field or rejecting duplicate configuration with a clear validation error. For example:

```python
platform_kwargs = dict(self._config.platform_config)
if self._config.platform == "go2" and "model_dir" not in platform_kwargs:
    platform_kwargs["model_dir"] = self._config.model_dir
self._platform = create_platform(self._config.platform, **platform_kwargs)
```

Add a regression test constructing `MultiRobotBridge(MultiRobotConfig(platform="go2", platform_config={"model_dir": "models/unitree_go2"}))`.

## Warnings

### WR-01: Analytical controller registry metadata disagrees with the evaluator action-mode contract

**File:** `src/locomotion/controllers.py:356-360`

**Issue:** `_analytical_capabilities()` advertises `"action_mode": "joint_position"` for `analytical_trot`, but the benchmark documentation and evaluator contract state that `argus eval-locomotion` runs `analytical_trot` through `velocity_command`. `ArgusGo2Env` stores registry metadata in run/info payloads, so this mismatch can produce artifacts where the run cell says `velocity_command` while controller metadata says `joint_position`. That is a reproducibility/compatibility bug at the registry boundary, especially if downstream code uses controller capabilities to validate whether a matrix cell is runnable.

**Fix:** Make the registry capability match the public evaluator contract, or split input action mode from output target type if both are needed. For the current documented contract:

```python
def _analytical_capabilities() -> dict[str, Any]:
    return {
        "family": "analytical",
        "action_mode": "velocity_command",
        # ... unchanged fields ...
        "model_requirements": {
            "requires_model_artifact": False,
            "artifacts": [],
            "output_target": "joint_position",
        },
    }
```

Then add a test asserting `ControllerRegistry.list_controllers()` reports `analytical_trot` with `capabilities["action_mode"] == "velocity_command"` and that the locomotion guide's analytical row matches the registry.

---

_Reviewed: 2026-05-02T16:43:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
