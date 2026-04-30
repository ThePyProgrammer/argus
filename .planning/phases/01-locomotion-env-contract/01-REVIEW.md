---
phase: 01-locomotion-env-contract
reviewed: 2026-04-30T08:30:19Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - pyproject.toml
  - src/locomotion/__init__.py
  - src/locomotion/actions.py
  - src/locomotion/env.py
  - src/locomotion/observations.py
  - src/locomotion/scenarios.py
  - tests/locomotion/test_argus_go2_env_action_modes.py
  - tests/locomotion/test_argus_go2_env_contract.py
  - tests/locomotion/test_argus_go2_env_determinism.py
  - tests/locomotion/test_argus_go2_env_scenarios.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-04-30T08:30:19Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the Phase 1 locomotion environment contract, action-space decoding, observation helpers, scenario sampling/XML generation, packaging metadata, and listed locomotion tests at standard depth. The previously reported blockers are fixed: non-plane terrain XML removes the flat benchmark floor, joint-position bounds match the per-leg Go2 FL/FR/RL/RR actuator order, and real MuJoCo-backed resets now rebuild models after randomized terrain samples so reported metadata and physics terrain do not stay stale.

One API correctness warning remains: the environment advertises `rgb_array` rendering and accepts `render_mode`, but does not implement `render()`, so users selecting the advertised mode cannot obtain frames through the Gymnasium API.

## Warnings

### WR-01: Advertised render mode has no render implementation

**Classification:** WARNING

**File:** `src/locomotion/env.py:24,31,44`

**Issue:** `ArgusGo2EnvConfig` exposes `render_mode`, `ArgusGo2Env.metadata` advertises `rgb_array`, and `__init__` stores `self.render_mode`, but the class does not implement `render()`. A caller can construct `ArgusGo2Env(ArgusGo2EnvConfig(render_mode="rgb_array"))` because the mode is advertised, but the Gymnasium render API will not return an RGB frame. That is an incorrect public contract rather than a style concern.

**Fix:** Either remove the advertised render mode until rendering is supported, or implement `render()` and validate unsupported modes during initialization. For example:

```python
class ArgusGo2Env(gymnasium.Env):
    metadata = {"render_modes": ["rgb_array"]}

    def __init__(self, config: ArgusGo2EnvConfig | None = None) -> None:
        self.config = config or ArgusGo2EnvConfig()
        if self.config.render_mode not in (None, "rgb_array"):
            raise ValueError("render_mode must be None or 'rgb_array'")
        ...

    def render(self) -> np.ndarray | None:
        if self.render_mode is None:
            return None
        if self._model is None or self._data is None:
            self._try_initialize_mujoco()
            self._reset_mujoco_state()
        if self._renderer is None:
            import mujoco
            self._renderer = mujoco.Renderer(self._model)
        self._renderer.update_scene(self._data)
        return self._renderer.render()
```

Add a contract test that constructs the env with `render_mode="rgb_array"`, calls `reset()`, then asserts `render()` returns an `H x W x 3` array when MuJoCo is available.

---

_Reviewed: 2026-04-30T08:30:19Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
