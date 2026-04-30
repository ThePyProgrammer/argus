---
phase: 01-locomotion-env-contract
reviewed: 2026-04-30T00:00:00Z
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
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-04-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the locomotion environment contract implementation, action decoding, observation helpers, scenario generation, packaging dependency changes, and the listed contract tests. `uv.lock` was provided in scope but excluded from source review as a lock file per review rules.

The test suite passed locally with `.venv/bin/python -m pytest` for the listed locomotion tests, but standard-depth review found correctness defects not covered by the current assertions. The rough-heightfield scenario creates a flat zero-valued heightfield, the default model path silently disables MuJoCo when the process is not launched from the repository root, and the sampled command schedule is exposed as metadata without being applied during stepping.

## Critical Issues

### CR-01: Rough-heightfield scenario creates a flat zero-valued heightfield

**Classification:** BLOCKER

**File:** `src/locomotion/scenarios.py:168-175`

**Issue:** `_add_rough_heightfield` declares an MJCF `<hfield>` with `nrow`, `ncol`, and `size`, but it never supplies height data via `content`/`file` or asset bytes. MuJoCo loads this as an all-zero heightfield, so the `rough_heightfield` benchmark scenario is physically flat despite reporting randomized `roughness_amplitude`. This directly invalidates the named scenario catalog behavior for rough terrain and lets the current tests pass while exercising no roughness.

**Fix:** Generate deterministic heightfield samples from the seeded scenario sample, serialize them into the MJCF-supported heightfield representation, and load them through assets. One safe direction is to store the generated grid in the `ScenarioSample` metadata or add an asset payload returned by `build_scenario_xml`:

```python
def _add_rough_heightfield(
    asset: ET.Element,
    worldbody: ET.Element,
    sample: ScenarioSample,
    assets: dict[str, bytes],
) -> None:
    size = int(sample.terrain_parameters.get("heightfield_size", 16))
    bounded_size = int(np.clip(size, 4, 64))
    amplitude = float(sample.terrain_parameters.get("roughness_amplitude", 0.02))
    heights = np.asarray(sample.terrain_parameters["heightfield_data"], dtype=np.float32)
    heights = heights.reshape((bounded_size, bounded_size))
    asset_name = "rough_heightfield.bin"
    assets[asset_name] = heights.astype(np.float32).tobytes()
    ET.SubElement(
        asset,
        "hfield",
        name="rough_heightfield",
        file=asset_name,
        nrow=str(bounded_size),
        ncol=str(bounded_size),
        size=f"5 5 {max(amplitude, 0.02):g} 0.02",
    )
```

Also add a regression test that loads the generated model and asserts `np.ptp(model.hfield_data) > 0` for `rough_heightfield`.

### CR-02: Default model path silently disables physics outside the repository root

**Classification:** BLOCKER

**File:** `src/locomotion/env.py:145-149`

**Issue:** `ArgusGo2EnvConfig.model_dir` defaults to the relative string `models/unitree_go2`, and `_try_initialize_mujoco` checks it with `Path(self.config.model_dir)`. If a user imports the package or runs the environment from any working directory other than the repository root, `(model_dir / "go2.xml").exists()` is false and the environment silently sets `_model`/`_data` to `None`. `reset()` and `step()` still return Gymnasium-shaped results, but no MuJoCo physics runs. That is an incorrect benchmark environment: callers can believe they are evaluating locomotion while receiving zero observations and no simulation.

**Fix:** Resolve the default model directory relative to the installed project/package location, or fail loudly when the configured model path is missing. For example:

```python
@dataclass
class ArgusGo2EnvConfig:
    scenario_id: str = "flat_ground"
    action_mode: str = "velocity_command"
    model_dir: str | None = None


def _resolved_model_dir(self) -> Path:
    if self.config.model_dir is not None:
        return Path(self.config.model_dir).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "models" / "unitree_go2"


def _try_initialize_mujoco(self) -> None:
    ...
    model_dir = self._resolved_model_dir()
    go2_xml = model_dir / "go2.xml"
    if not go2_xml.exists():
        raise FileNotFoundError(f"Go2 model not found: {go2_xml}")
```

If a no-physics fallback is intentionally supported, make it explicit with a configuration flag such as `allow_missing_mujoco: bool = False`; do not silently downgrade the benchmark path.

## Warnings

### WR-01: Sampled command schedule is reported but never applied during an episode

**Classification:** WARNING

**File:** `src/locomotion/env.py:72-77`

**Issue:** `reset()` initializes `_command` from `command_schedule[0]`, but `step()` never advances the sampled command schedule by simulation time. For `joint_position` and `residual_baseline` modes, `_command` stays at the initial zero command forever; for `velocity_command`, `_command` is overwritten by the action instead of the sampled schedule. This makes `command_schedule` misleading benchmark metadata and undermines residual-over-baseline control, which decodes against `_command` but has no separate command input in its 12-value action API.

**Fix:** Apply the active scheduled command before decoding non-velocity actions, or remove `command_schedule` from the benchmark contract if actions are meant to be the only command source. A concrete implementation could be:

```python
def _command_at_time(self, sim_time: float) -> np.ndarray:
    sample = self._scenario_sample
    if sample is None:
        return self._command
    active = sample.command_schedule[0]
    for item in sample.command_schedule:
        if float(item["time"]) <= sim_time + 1e-12:
            active = item
        else:
            break
    return np.array([active["vx"], active["vy"], active["omega"]], dtype=np.float32)


def step(self, action: np.ndarray):
    if self.config.action_mode != ACTION_MODE_VELOCITY:
        self._command = self._command_at_time(self._current_sim_time())
    ctrl = decode_action(action, self.config.action_mode, self._gait, self._dt, self._command)
    ...
```

Add tests that step past the second schedule entry in `joint_position` or `residual_baseline` mode and assert `info["command_schedule"]` corresponds to an applied `observation["command"]`.

---

_Reviewed: 2026-04-30T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
