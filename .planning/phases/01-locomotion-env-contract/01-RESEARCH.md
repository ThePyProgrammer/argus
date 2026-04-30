# Phase 1: locomotion-env-contract - Research

**Researched:** 2026-04-30  
**Domain:** Gymnasium-style MuJoCo locomotion environment contract for Unitree Go2 analytical trot baseline  
**Confidence:** HIGH for codebase mapping and Gymnasium/MuJoCo API contract; MEDIUM for scenario XML implementation details until implemented and smoke-tested

## User Constraints

### Locked Decisions

No phase-specific `*-CONTEXT.md` file was found in `/home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract`, so locked decisions come from the v4.0 project state and roadmap. [VERIFIED: codebase read `.planning/STATE.md:47-54`, `.planning/ROADMAP.md:25-34`]

- **Benchmark before controller sophistication:** the locomotion R&D report shows Argus currently uses analytical trot + MuJoCo position actuators; v4.0 must make that baseline measurable before adding RL/MPC/WBC. [VERIFIED: codebase read `.planning/STATE.md:49`, `outputs/locomotion-rd-systems.md:3-9`]
- **Gymnasium-style API:** `ArgusGo2Env` is the common reset/step boundary for evaluation, regression tests, and future learning workflows. [VERIFIED: codebase read `.planning/STATE.md:50`]
- **Scenario catalog:** flat ground, low friction, slope, rough heightfield, and push disturbance are the minimum named scenarios for useful locomotion comparisons. [VERIFIED: codebase read `.planning/STATE.md:51`, `.planning/REQUIREMENTS.md:14-17`]
- **Action modes:** velocity command, joint-position target, and residual-over-baseline control must be selected through environment config while preserving one environment API. [VERIFIED: codebase read `.planning/ROADMAP.md:30-34`]
- **Do not break existing runtime:** existing non-Gym simulation/web paths still boot, especially the C2 multi-robot runtime. [VERIFIED: codebase read `.planning/ROADMAP.md:34`, `.planning/PROJECT.md:5-9`]
- **Deferred:** RL policy training, MPC/WBC implementation, ROS/hardware deployment, replacing the analytical trot, and frontend visualization overhaul are out of scope for v4.0. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:60-66`, `.planning/PROJECT.md:46-60`]

### Claude's Discretion

No phase-specific discretion section exists. [VERIFIED: codebase search phase directory] Research recommendation: add a thin environment package around existing MuJoCo/gait code and avoid moving the C2 runtime into the Gym wrapper in Phase 1. [ASSUMED]

### Deferred Ideas (OUT OF SCOPE)

No phase-specific deferred section exists. Use v4.0 out-of-scope boundaries: no RL training, no MPC/WBC implementation, no ROS/hardware deployment, no replacement of the analytical trot, and no frontend visualization overhaul. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:60-66`]

## Project Constraints (from CLAUDE.md)

- `/home/prannayag/pragnition/robotics/argus/CLAUDE.md` and `/home/prannayag/pragnition/robotics/argus/.claude/CLAUDE.md` contain only placeholder text: `Add your project-specific Claude instructions here.` [VERIFIED: codebase read `CLAUDE.md:1-3`, `.claude/CLAUDE.md:1-3`]
- No actionable project-specific coding, testing, security, or forbidden-pattern directives were found in project CLAUDE files. [VERIFIED: codebase read `CLAUDE.md:1-3`, `.claude/CLAUDE.md:1-3`]
- Project skill discovery found `.claude/skills/desloppify`, but it is a code-health workflow skill and is not directly applicable to this Phase 1 research unless the planner asks for technical-debt cleanup. [VERIFIED: codebase read `.claude/skills/desloppify/SKILL.md:1-9`]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-ENV-01 | Developer can run a Gymnasium-style `ArgusGo2Env` wrapper with `reset(seed=...)` and `step(action)` returning observation, reward, terminated, truncated, and info. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:14`] | Use Gymnasium `Env` API, call `super().reset(seed=seed)`, expose `observation_space`/`action_space`, and wrap existing MuJoCo stepping. [CITED: https://gymnasium.farama.org/api/env/] Existing single-robot bridge already supports `start()`, `step(action=None)`, and `set_velocity`. [VERIFIED: codebase read `src/bridge/sim_bridge.py:64-172`, `src/bridge/sim_bridge.py:187-207`] |
| LOC-ENV-02 | Developer can choose at least flat-ground, low-friction, slope, rough-heightfield, and push-disturbance scenarios from a named scenario catalog. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:15`] | Extend scene generation rather than hard-code scenarios into `ArgusGo2Env`; existing `MultiRobotConfig.scene` only supports `flat`/`office`. [VERIFIED: codebase read `src/bridge/multi_robot_config.py:21-36`, `src/bridge/scene_builder.py:46-166`] MuJoCo XML supports geom friction, heightfield assets, and position actuators. [CITED: https://mujoco.readthedocs.io/en/stable/XMLreference.html] |
| LOC-ENV-03 | Developer can run deterministic seeded resets that reproduce robot spawn pose, terrain parameters, command schedule, and disturbance timing. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:16`] | Use Gymnasium reset seeding (`super().reset(seed=seed)` and `self.np_random`) for scenario sampling and command/disturbance schedules. [CITED: https://gymnasium.farama.org/api/env/] Use MuJoCo `mj_resetData`/state writes/`mj_forward` for physical reset. [CITED: https://mujoco.readthedocs.io/en/stable/python.html] Existing code has unseeded `random.shuffle` in office spawn generation, so do not reuse that path for benchmark determinism without injecting a RNG. [VERIFIED: codebase read `src/coordination/spawn.py:8-85`] |
| LOC-ENV-04 | Developer can select action modes for velocity command, joint-position target, and residual-over-baseline control without changing the environment API. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:17`] | Reuse `TrotGaitController.compute(vx, vy, omega, dt)` for velocity-command and residual baseline modes; reuse existing bridge direct 12-element action path for joint-position target mode. [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`, `src/bridge/sim_bridge.py:134-155`] |

</phase_requirements>

## Summary

Phase 1 should add a thin Gymnasium-style benchmark boundary around the existing single-Go2 MuJoCo path, not rewrite the C2 multi-robot runtime. [VERIFIED: codebase read `src/bridge/sim_bridge.py:26-207`, `src/main.py:322-467`] The current locomotion path is already a velocity command -> `TrotGaitController` -> 12 joint-position targets -> MuJoCo position actuators stack. [VERIFIED: codebase read `outputs/locomotion-rd-systems.md:3-9`, `src/locomotion/gait_controller.py:1-11`, `src/locomotion/xml_patcher.py:1-8`] The missing pieces are the environment contract, deterministic reset/sampling state, named scenario catalog, and action-mode dispatch. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`]

The implementation should put the new public API in a new locomotion environment module, for example `src/locomotion/env.py`, with supporting modules such as `src/locomotion/scenarios.py` and `src/locomotion/actions.py`. [ASSUMED] The wrapper should own benchmark-only scenario construction, seed derivation, command/disturbance schedule generation, action-space selection, observation construction, reward placeholder, and termination/truncation flags. [ASSUMED] It should call existing MuJoCo and gait primitives rather than adding evaluation-specific shortcuts inside `MultiRobotBridge`. [VERIFIED: codebase read `src/bridge/multi_bridge.py:31-64`, `src/bridge/multi_bridge.py:204-223`, `src/bridge/multi_bridge.py:447-463`]

**Primary recommendation:** Implement `ArgusGo2Env` as a single-robot Gymnasium `Env` wrapper backed by direct MuJoCo `MjModel`/`MjData` lifecycle helpers and existing `TrotGaitController`, with deterministic scenario sampling isolated in a scenario catalog module. [CITED: https://gymnasium.farama.org/api/env/] [CITED: https://mujoco.readthedocs.io/en/stable/python.html] [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `ArgusGo2Env.reset/step` Gymnasium contract | API / Backend | Database / Storage: none | The benchmark environment is a Python API boundary over MuJoCo state, not browser/UI logic. [CITED: https://gymnasium.farama.org/api/env/] [VERIFIED: codebase read `src/bridge/sim_bridge.py:26-207`] |
| Scenario catalog and terrain generation | API / Backend | MuJoCo model/XML layer | Scenarios must produce MuJoCo model parameters and schedules before stepping; current scene builders already generate MJCF XML in Python. [VERIFIED: codebase read `src/bridge/scene_builder.py:46-166`] |
| Seeded reset determinism | API / Backend | MuJoCo runtime state | Gymnasium owns RNG seeding; MuJoCo owns qpos/qvel/ctrl/contact simulation state. [CITED: https://gymnasium.farama.org/api/env/] [CITED: https://mujoco.readthedocs.io/en/stable/python.html] |
| Action-mode dispatch | API / Backend | Locomotion controller layer | Velocity mode maps actions through `TrotGaitController`, joint-position mode writes 12-element targets, residual mode adds offsets to baseline targets. [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`, `src/bridge/sim_bridge.py:134-155`] |
| Preserve C2 web/runtime boot | API / Backend | Browser / Client | Existing web mode builds a multi-robot bridge and FastAPI app; the benchmark wrapper should not replace that startup path. [VERIFIED: codebase read `src/main.py:322-467`, `src/main.py:380-390`] |
| Validation and regression checks | API / Backend | CI/test runner | Existing project validation is pytest-based with domain folders under `tests/`. [VERIFIED: codebase read `pytest.ini:1-13`, `tests/locomotion/test_gait_controller.py:1-163`] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `gymnasium` | 1.3.0 current on PyPI; not currently installed locally. [VERIFIED: PyPI via `python -m pip index versions gymnasium`] | Provides the canonical `Env.reset(seed, options) -> (obs, info)` and `Env.step(action) -> (obs, reward, terminated, truncated, info)` contract. [CITED: https://gymnasium.farama.org/api/env/] | Required by the phase requirement and current RL/evaluation ecosystem. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:14`] |
| `mujoco` | 3.8.0 current on PyPI; `pyproject.toml` currently declares `mujoco>=3.0.0`; not installed in current Python 3.14 interpreter. [VERIFIED: PyPI via `python -m pip index versions mujoco`] [VERIFIED: codebase read `pyproject.toml:6-15`] | Loads MJCF, owns `MjModel`/`MjData`, resets state, applies controls/forces, and steps physics. [CITED: https://mujoco.readthedocs.io/en/stable/python.html] | Existing bridge and gait integration already depend on MuJoCo. [VERIFIED: codebase read `src/bridge/sim_bridge.py:64-172`, `src/bridge/multi_bridge.py:83-223`] |
| `numpy` | 2.4.4 current on PyPI and installed locally; `pyproject.toml` declares `numpy>=1.26.0`. [VERIFIED: PyPI via `python -m pip index versions numpy`] [VERIFIED: local `importlib.metadata.version`] [VERIFIED: codebase read `pyproject.toml:6-15`] | Array representation for observations, actions, qpos/qvel snapshots, random sampling, and tests. [VERIFIED: codebase read `src/locomotion/gait_controller.py:14-86`, `tests/conftest.py:17-24`] | Already standard in this codebase. [VERIFIED: codebase read `pyproject.toml:6-15`] |
| `pytest` + `pytest-timeout` | `pytest` 9.0.2 installed locally; `pytest>=8.0.0` and `pytest-timeout>=2.0.0` declared in dev extras. [VERIFIED: local `pytest --version`] [VERIFIED: codebase read `pyproject.toml:40-44`, `pytest.ini:1-13`] | Unit/integration tests and Nyquist validation. [VERIFIED: codebase read `pytest.ini:1-13`] | Existing test suite is pytest-based. [VERIFIED: codebase read `tests/locomotion/test_locomotion.py:1-426`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scipy` | Existing dependency `scipy>=1.15.0`. [VERIFIED: codebase read `pyproject.toml:6-15`] | Optional terrain smoothing/noise utilities if rough heightfield generation needs them. [ASSUMED] | Only use if NumPy-only heightfield generation becomes clumsy; keep Phase 1 simple. [ASSUMED] |
| `xml.etree.ElementTree` | Python stdlib. [VERIFIED: codebase read `src/bridge/scene_builder.py:17-22`] | MJCF XML mutation for scenario construction. [VERIFIED: codebase read `src/bridge/scene_builder.py:46-166`, `src/locomotion/xml_patcher.py:11-62`] | Use for low-friction/slope/heightfield XML generation to match existing project pattern. [VERIFIED: codebase read `src/bridge/scene_builder.py:46-166`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gymnasium.Env` subclass | A duck-typed class with `reset`/`step` only | Duck typing would satisfy a narrow smoke test but would lose standard `action_space`, `observation_space`, `np_random`, wrappers, and seeding behavior. [CITED: https://gymnasium.farama.org/api/env/] |
| Direct MuJoCo lifecycle in `ArgusGo2Env` | Wrap `MuJoCoBridge` directly | Wrapping `MuJoCoBridge` reuses rendering but makes deterministic reset and scenario XML/model rebuild harder because `MuJoCoBridge.start()` currently creates `MjModel`/`MjData`, settles physics, and hides reset state behind private members. [VERIFIED: codebase read `src/bridge/sim_bridge.py:64-132`] Direct lifecycle can still share helper functions and avoids changing C2 path. [ASSUMED] |
| Modify `MultiRobotBridge` for scenarios/action modes | Add benchmark behavior to C2 bridge | This risks breaking C2 boot and duplicates evaluation concerns in a multi-robot web bridge. [VERIFIED: codebase read `.planning/ROADMAP.md:34`, `src/main.py:322-467`] |

**Installation:**
```bash
python -m pip install "gymnasium>=1.3.0" "mujoco>=3.8.0"
```

**Version verification:** package currency was checked with `python -m pip index versions gymnasium`, `python -m pip index versions mujoco`, and `python -m pip index versions numpy` on 2026-04-30. [VERIFIED: PyPI]

## Architecture Patterns

### System Architecture Diagram

```mermaid
flowchart TD
  A[Caller: tests / future CLI / future trainer] --> B[ArgusGo2Env(config)]
  B --> C{reset(seed, options)}
  C --> D[Gymnasium super().reset seeds self.np_random]
  D --> E[ScenarioCatalog.select(name)]
  E --> F[Sample deterministic spawn, terrain params, command schedule, disturbance schedule]
  F --> G[Build or patch MJCF XML]
  G --> H[MuJoCo MjModel + MjData]
  H --> I[mj_resetData + qpos/qvel/ctrl writes + mj_forward]
  I --> J[Initial observation + info]
  A --> K{step(action)}
  K --> L{Action mode}
  L -->|velocity_command| M[TrotGaitController.compute]
  L -->|joint_position| N[Validate 12 joint targets]
  L -->|residual_baseline| O[TrotGaitController.compute + clipped residual]
  M --> P[data.ctrl]
  N --> P
  O --> P
  P --> Q[Optional scheduled push via xfrc_applied]
  Q --> R[mj_step n substeps]
  R --> S[Observation + reward + terminated/truncated + info]
  S --> A
```

This diagram separates benchmark environment ownership from existing C2/web boot, which continues through `src.main.run_web_mode` -> `MultiRobotBridge` -> `Coordinator`. [VERIFIED: codebase read `src/main.py:322-467`]

### Recommended Project Structure

```text
src/
├── locomotion/
│   ├── env.py              # ArgusGo2Env, config dataclasses, reset/step contract [ASSUMED]
│   ├── scenarios.py        # ScenarioSpec catalog and MJCF/schedule sampling [ASSUMED]
│   ├── actions.py          # ActionMode enum/specs and action decoding [ASSUMED]
│   ├── observations.py     # Observation construction helpers if env.py grows too large [ASSUMED]
│   ├── gait_controller.py  # Existing analytical trot baseline [VERIFIED: codebase read `src/locomotion/gait_controller.py:19-86`]
│   └── xml_patcher.py      # Existing Go2 actuator/floor XML helper [VERIFIED: codebase read `src/locomotion/xml_patcher.py:23-138`]
└── bridge/
    ├── sim_bridge.py       # Existing non-Gym single-robot path; do not break [VERIFIED: codebase read `src/bridge/sim_bridge.py:26-207`]
    └── multi_bridge.py     # Existing C2 multi-robot path; do not make benchmark-only changes here [VERIFIED: codebase read `src/bridge/multi_bridge.py:31-64`]

tests/
└── locomotion/
    ├── test_argus_go2_env_contract.py       # reset/step API + spaces [ASSUMED]
    ├── test_argus_go2_env_scenarios.py      # catalog and XML/schedule selection [ASSUMED]
    ├── test_argus_go2_env_determinism.py    # same seed vs different seed [ASSUMED]
    └── test_argus_go2_env_action_modes.py   # velocity, joint target, residual [ASSUMED]
```

### Component Responsibilities

| Component | Responsibility | Existing API to Use | Risk |
|-----------|----------------|---------------------|------|
| `ArgusGo2Env` | Gymnasium public API, config validation, spaces, lifecycle, reward/termination placeholders. [ASSUMED] | `gymnasium.Env`, MuJoCo `MjModel`/`MjData`, `TrotGaitController`. [CITED: https://gymnasium.farama.org/api/env/] [CITED: https://mujoco.readthedocs.io/en/stable/python.html] [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`] | If it wraps `MuJoCoBridge` too tightly, reset determinism may be brittle. [ASSUMED] |
| `ScenarioCatalog` | Named scenarios and deterministic scenario parameter sampling. [ASSUMED] | Existing XML patterns in `scene_builder.py` and `xml_patcher.py`. [VERIFIED: codebase read `src/bridge/scene_builder.py:46-166`, `src/locomotion/xml_patcher.py:23-138`] | Heightfield/slope XML must load under MuJoCo and not require frontend assets. [CITED: https://mujoco.readthedocs.io/en/stable/XMLreference.html] |
| `ActionMode` dispatch | Convert one `step(action)` API into appropriate `data.ctrl` target. [ASSUMED] | Existing direct action support in `MuJoCoBridge.step(action)`. [VERIFIED: codebase read `src/bridge/sim_bridge.py:134-155`] | Residual clipping must respect joint ranges; do not trust policy-shaped residuals blindly. [ASSUMED] |
| Determinism helper | Derive all random elements from Gymnasium `self.np_random`. [CITED: https://gymnasium.farama.org/api/env/] | Existing `RandomWalkController` uses `np.random.default_rng(seed)` as a local pattern. [VERIFIED: codebase read `src/control/random_walk.py:31-102`] | Existing `coordination.spawn.generate_spawn_positions` uses global `random` and should not be reused for benchmark determinism. [VERIFIED: codebase read `src/coordination/spawn.py:8-85`] |

### Pattern 1: Gymnasium reset and step contract

**What:** Subclass `gymnasium.Env`, define `action_space` and `observation_space`, call `super().reset(seed=seed)`, return `(obs, info)` from reset and `(obs, reward, terminated, truncated, info)` from step. [CITED: https://gymnasium.farama.org/api/env/]

**When to use:** Required for LOC-ENV-01 and any future RL/training/evaluation tooling. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:14`]

**Example:**
```python
# Source: https://gymnasium.farama.org/api/env/
class ArgusGo2Env(gymnasium.Env):
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # sample scenario state only from self.np_random
        observation = self._get_obs()
        info = self._get_info()
        return observation, info

    def step(self, action):
        # decode action -> data.ctrl, step MuJoCo, compute observation/reward/done flags
        return observation, reward, terminated, truncated, info
```

### Pattern 2: Direct MuJoCo reset lifecycle for deterministic episodes

**What:** Use `mj_resetData(model, data)`, write qpos/qvel/ctrl for spawn and standing pose, then call `mj_forward(model, data)` before extracting derived state. [CITED: https://mujoco.readthedocs.io/en/stable/python.html]

**When to use:** Every `ArgusGo2Env.reset(seed=...)` call, especially when model XML is reused and only runtime state changes. [ASSUMED]

**Example:**
```python
# Source: https://mujoco.readthedocs.io/en/stable/python.html
mujoco.mj_resetData(model, data)
data.qpos[:] = initial_qpos
data.qvel[:] = 0.0
data.ctrl[:] = standing_targets
mujoco.mj_forward(model, data)
```

### Pattern 3: Scenario config as data, not branches in environment code

**What:** Represent `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance` as named specs with parameter sampler/build hooks. [ASSUMED]

**When to use:** Required by LOC-ENV-02 and LOC-ENV-03 so scenario selection does not require editing environment code. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:15-16`]

**Example:**
```python
# Source pattern: existing registry/catalog style in src/slam/registry.py and src/perception/registry.py
SCENARIOS = {
    "flat_ground": ScenarioSpec(...),
    "low_friction": ScenarioSpec(...),
    "slope": ScenarioSpec(...),
    "rough_heightfield": ScenarioSpec(...),
    "push_disturbance": ScenarioSpec(...),
}
```

Existing Argus uses registry-style discovery for SLAM and perception backends, so a named catalog aligns with project conventions. [VERIFIED: codebase read `src/slam/registry.py:15-129`, `src/perception/registry.py:135-367`]

### Anti-Patterns to Avoid

- **Adding Gymnasium semantics to `MultiRobotBridge.step()`:** `MultiRobotBridge.step()` currently returns `dict[str, SensorFrame]`; changing it to Gymnasium’s five-tuple would break C2/coordinator assumptions. [VERIFIED: codebase read `src/bridge/multi_bridge.py:204-275`, `src/main.py:276-289`]
- **Using global `random` or `np.random` in reset:** deterministic reset requires all sampled spawn, terrain, command, and disturbance parameters to derive from the reset seed. [VERIFIED: codebase read `.planning/STATE.md:75-79`] Existing global `random.shuffle` in spawn generation is a warning sign. [VERIFIED: codebase read `src/coordination/spawn.py:58-85`]
- **Rebuilding unrelated C2 web paths for benchmark scenarios:** Phase 1 success explicitly requires non-Gym simulation/web paths still boot. [VERIFIED: codebase read `.planning/ROADMAP.md:34`]
- **Letting action spaces vary at runtime without matching `action_space`:** Gymnasium environments should expose valid actions through `action_space`. [CITED: https://gymnasium.farama.org/api/env/]
- **Hand-coding scenario logic inside `step()`:** Scenario sampling and schedules should be reset-time artifacts in `info`, not scattered runtime branches. [ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RL environment API | Custom `done`-style four-tuple or bespoke runner contract | `gymnasium.Env` five-tuple API | Gymnasium separates `terminated` and `truncated` and provides standard spaces/seeding semantics. [CITED: https://gymnasium.farama.org/api/env/] |
| Random-number management | Global `random`/`np.random` calls | Gymnasium `super().reset(seed=seed)` and `self.np_random` | Needed to reproduce reset samples and schedules. [CITED: https://gymnasium.farama.org/api/env/] |
| Physics reset | Recreate arbitrary Python object state without resetting MuJoCo | MuJoCo `mj_resetData`, qpos/qvel/ctrl writes, `mj_forward` | MuJoCo derived state/contact state must be synchronized after reset. [CITED: https://mujoco.readthedocs.io/en/stable/python.html] |
| Go2 gait baseline | New gait generator in Phase 1 | Existing `TrotGaitController` | Existing controller already produces velocity-commanded 12-element joint targets. [VERIFIED: codebase read `src/locomotion/gait_controller.py:19-86`] |
| Position actuator conversion | Manually edit `models/unitree_go2/go2.xml` | `patch_actuators_to_position` / `patch_actuators_to_position_with_floor` | Existing patcher converts motors to position actuators without modifying source XML. [VERIFIED: codebase read `src/locomotion/xml_patcher.py:23-62`, `tests/locomotion/test_locomotion.py:85-99`] |
| Named catalog/selection | Ad hoc `if scenario == ...` across environment code | Central scenario catalog module | Project already uses central registries/catalogs for plugin-like choices. [VERIFIED: codebase read `src/slam/registry.py:15-129`, `src/perception/registry.py:135-367`] |

**Key insight:** Phase 1 is an interface and determinism phase, not a locomotion-intelligence phase; custom alternatives to Gymnasium seeding, MuJoCo reset, or existing gait output add risk without satisfying new user value. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`, `outputs/locomotion-rd-systems.md:162-172`]

## Common Pitfalls

### Pitfall 1: Partial seeding that only affects spawn pose

**What goes wrong:** Same `seed` reproduces one variable but not terrain, command schedule, or push timing. [VERIFIED: codebase read `.planning/STATE.md:75-79`]  
**Why it happens:** Scenario samplers call global `random`/`np.random` or use wall-clock state. [VERIFIED: codebase read `src/coordination/spawn.py:58-85`]  
**How to avoid:** Derive all sampled values from `self.np_random` after `super().reset(seed=seed)`. [CITED: https://gymnasium.farama.org/api/env/]  
**Warning signs:** Determinism tests pass for `flat_ground` but fail for `rough_heightfield` or `push_disturbance`. [ASSUMED]

### Pitfall 2: Gym wrapper breaks C2 runtime

**What goes wrong:** Refactoring bridge internals for Gym changes return types or lifecycle used by `run_web_mode`/`Coordinator`. [VERIFIED: codebase read `src/main.py:322-467`, `src/bridge/multi_bridge.py:204-275`]  
**Why it happens:** The benchmark wrapper is treated as the new universal bridge instead of a separate boundary. [ASSUMED]  
**How to avoid:** Add new env modules and tests; keep `MuJoCoBridge` and `MultiRobotBridge` public behavior compatible. [VERIFIED: codebase read `.planning/ROADMAP.md:34`]  
**Warning signs:** Existing bridge tests or `src.main --control web` import/startup tests fail. [ASSUMED]

### Pitfall 3: Action mode mismatch with `action_space`

**What goes wrong:** `action_space` says one shape/range but `step()` expects another shape depending on config. [CITED: https://gymnasium.farama.org/api/env/]  
**Why it happens:** Modes are handled after action validation with no mode-specific space initialization. [ASSUMED]  
**How to avoid:** Build `action_space` during `__init__` from immutable env config and validate every action before applying it. [ASSUMED]  
**Warning signs:** Joint-position tests pass but velocity-command tests sample invalid actions from `env.action_space`. [ASSUMED]

### Pitfall 4: MuJoCo derived state not synchronized after reset

**What goes wrong:** Observations read stale `xpos`, camera transforms, or sensor data after manual qpos/qvel edits. [ASSUMED]  
**Why it happens:** Code writes `data.qpos` and immediately reads derived fields without `mj_forward`. [CITED: https://mujoco.readthedocs.io/en/stable/python.html]  
**How to avoid:** After reset writes, call `mujoco.mj_forward(model, data)` before `_get_obs()`. [CITED: https://mujoco.readthedocs.io/en/stable/python.html]  
**Warning signs:** Same qpos produces inconsistent camera/body pose observations. [ASSUMED]

### Pitfall 5: Scenario XML rebuild cost hidden in `reset()`

**What goes wrong:** Every reset rebuilds and recompiles MuJoCo XML even when only spawn/command/push schedule changes. [ASSUMED]  
**Why it happens:** Scenario identity and sampled parameters are conflated with runtime reset state. [ASSUMED]  
**How to avoid:** Rebuild model only when terrain/geometry-affecting sampled parameters change; use runtime state writes for spawn/command schedule when possible. [ASSUMED]  
**Warning signs:** Contract tests take seconds per reset and become flaky under `pytest-timeout` 30s. [VERIFIED: codebase read `pytest.ini:1-13`]

### Pitfall 6: Python environment mismatch blocks MuJoCo tests

**What goes wrong:** Local tests import `mujoco` under Python 3.14, but the project declares `requires-python = ">=3.10,<3.13"` and local `mujoco` is not installed in the current interpreter. [VERIFIED: codebase read `pyproject.toml:5`] [VERIFIED: local package probe]  
**Why it happens:** Shell Python differs from project-supported Python. [VERIFIED: local `python --version`]  
**How to avoid:** Planner should include either a supported Python environment setup step or mark MuJoCo integration tests as environment-dependent. [ASSUMED]  
**Warning signs:** `ModuleNotFoundError: mujoco` or packaging install refusal due to Python version. [VERIFIED: local package probe]

## Code Examples

Verified patterns from official sources and current codebase:

### Gymnasium Env skeleton

```python
# Source: https://gymnasium.farama.org/api/env/
class ArgusGo2Env(gymnasium.Env):
    metadata = {"render_modes": ["rgb_array"]}

    def __init__(self, config: ArgusGo2EnvConfig | None = None):
        self.config = config or ArgusGo2EnvConfig()
        self.action_space = build_action_space(self.config.action_mode)
        self.observation_space = build_observation_space()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._reset_scenario(options)
        return self._get_obs(), self._get_info()

    def step(self, action):
        ctrl = self._decode_action(action)
        self._data.ctrl[:] = ctrl
        self._step_mujoco()
        return self._get_obs(), self._reward(), self._terminated(), self._truncated(), self._get_info()
```

### Existing baseline control conversion

```python
# Source: src/locomotion/gait_controller.py:39-86 and src/bridge/sim_bridge.py:197-207
ctrl = self._gait.compute(vx, vy, omega, dt)
self._data.ctrl[:] = ctrl
```

### Existing direct joint-position action path

```python
# Source: src/bridge/sim_bridge.py:134-155
if action is not None:
    self._data.ctrl[:] = action
else:
    ctrl = self._velocity_to_ctrl()
    self._data.ctrl[:] = ctrl
```

### MuJoCo reset and derived-state synchronization

```python
# Source: https://mujoco.readthedocs.io/en/stable/python.html
mujoco.mj_resetData(model, data)
data.qpos[:] = initial_qpos
data.qvel[:] = 0.0
data.ctrl[:] = standing_targets
mujoco.mj_forward(model, data)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gym-style `step()` returns `(obs, reward, done, info)` | Gymnasium `step()` returns `(obs, reward, terminated, truncated, info)` | Gymnasium/Gym API changed in v0.26. [CITED: https://gymnasium.farama.org/api/env/] | Phase 1 must implement separate `terminated` and `truncated`, not a single `done`. [CITED: https://gymnasium.farama.org/api/env/] |
| Custom simulator loop only | Standard environment wrapper over simulator loop | v4.0 roadmap decision. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`] | Enables shared evaluation/regression/future learning boundary. [VERIFIED: codebase read `.planning/research/SUMMARY.md:9-21`] |
| Hard-coded analytical gait demo | Benchmarkable analytical baseline with scenarios/seeds/action modes | v4.0 roadmap decision. [VERIFIED: codebase read `.planning/PROJECT.md:62-76`] | Controller claims become reproducible instead of anecdotal. [VERIFIED: codebase read `.planning/PROJECT.md:5-9`] |

**Deprecated/outdated:**
- A single `done` flag is outdated for new Gymnasium-compatible environments; use `terminated` and `truncated`. [CITED: https://gymnasium.farama.org/api/env/]
- Direct global random sampling is not acceptable for deterministic benchmark reset semantics. [CITED: https://gymnasium.farama.org/api/env/] [VERIFIED: codebase read `.planning/STATE.md:75-79`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | New implementation should live in `src/locomotion/env.py`, `scenarios.py`, and `actions.py`. | Summary / Recommended Project Structure | Planner may choose a different file split; low risk if responsibilities remain separated. |
| A2 | Direct MuJoCo lifecycle inside `ArgusGo2Env` is preferable to wrapping `MuJoCoBridge` tightly. | Standard Stack / Architecture Patterns | If bridge reuse is easier than expected, plan may over-split implementation; validate during Wave 0. |
| A3 | `scipy` may be useful but is optional for rough heightfield generation. | Standard Stack | Planner might add unnecessary dependency use; prefer NumPy first. |
| A4 | Scenario logic should be reset-time artifacts rather than step-time branches. | Architecture Patterns | If push disturbance needs per-step scheduling, this still works via a schedule evaluated in step; risk is terminology only. |
| A5 | Scenario XML rebuild cost could matter for tests. | Common Pitfalls | If MuJoCo compile is fast enough, optimization can be deferred. |

## Open Questions (RESOLVED)

1. **What exact observation vector should Phase 1 expose?**
   - RESOLVED: Phase 1 exposes a minimal proprioceptive dict observation; no image observations are included in the benchmark wrapper.
   - Decision detail: Use fields such as `qpos`, `qvel`, command, previous action, and scenario metadata/encoding as needed for contract tests. Existing `SensorFrame` image/depth/camera fields stay in bridge paths and are not part of the Phase 1 `ArgusGo2Env` observation contract. [VERIFIED: codebase read `src/bridge/sensor_types.py:49-64`] [VERIFIED: codebase read `.planning/REQUIREMENTS.md:14-17`]

2. **Should `ArgusGo2Env` require `gymnasium` as a hard runtime dependency?**
   - RESOLVED: Yes. Add `gymnasium>=1.3.0` as a hard runtime dependency in `pyproject.toml`; do not hand-roll a duck-typed Env base.
   - Decision detail: Phase 1 implements a real Gymnasium API with `Env`, spaces, `super().reset(seed=seed)`, and the five-tuple step contract. [VERIFIED: codebase read `pyproject.toml:6-16`, `.planning/REQUIREMENTS.md:14`] [CITED: https://gymnasium.farama.org/api/env/]

3. **How far should scenario physics realism go in Phase 1?**
   - RESOLVED: Use conservative deterministic defaults from Plan 01-02 plus the runtime push force implementation in Plan 01-05.
   - Decision detail: Flat, low-friction, slope, rough-heightfield, and push-disturbance scenarios must be concrete and deterministic, but Phase 1 does not tune realism beyond bounded default ranges. Push disturbance is not XML metadata only: Plan 01-05 applies sampled force during `env.step()` using MuJoCo runtime `xfrc_applied` or an equivalent supported runtime mechanism and clears it outside the active window. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:15-16`]

4. **How to handle local Python 3.14 vs project `<3.13`?**
   - RESOLVED: Supported Python is 3.10-3.12. Integration tests skip outside that range or when `mujoco` is unavailable.
   - Decision detail: Unit tests should still cover pure config/catalog/action behavior where possible, but MuJoCo integration tests must explicitly skip with a clear reason under Python outside `>=3.10,<3.13` or when `import mujoco` fails. [VERIFIED: local `python --version`] [VERIFIED: codebase read `pyproject.toml:5`]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All implementation/tests | Warning | Current shell: Python 3.14.4; project requires `>=3.10,<3.13`. [VERIFIED: local `python --version`] [VERIFIED: codebase read `pyproject.toml:5`] | Use project-supported Python 3.10-3.12 environment. [ASSUMED] |
| `mujoco` Python package | MuJoCo env integration tests and runtime | No in current interpreter | Current PyPI 3.8.0; local import metadata not found. [VERIFIED: PyPI] [VERIFIED: local package probe] | Unit-test pure config/catalog without MuJoCo; integration requires install. [ASSUMED] |
| `gymnasium` Python package | `ArgusGo2Env` base class/spaces/seeding | No in current interpreter | Current PyPI 1.3.0; local import metadata not found. [VERIFIED: PyPI] [VERIFIED: local package probe] | Add dependency; duck typing is not recommended. [CITED: https://gymnasium.farama.org/api/env/] |
| `numpy` | Actions/observations/gait | Yes | 2.4.4 installed. [VERIFIED: local package probe] | None needed. |
| `pytest` | Validation | Yes | 9.0.2 installed. [VERIFIED: local `pytest --version`] | None needed for unit tests. |
| OpenGL/Mesa renderer | MuJoCo rendering paths | Partially | `glxinfo` reports Mesa Intel Graphics OpenGL 4.6. [VERIFIED: local environment probe] | Avoid rendering in contract tests where possible; use state-only tests. [ASSUMED] |
| `xvfb-run` | Headless renderer fallback | No | Command not found. [VERIFIED: local environment probe] | Use MuJoCo headless/offscreen configuration or skip rendering-dependent tests in local shell. [ASSUMED] |

**Missing dependencies with no fallback:**
- `gymnasium` must be added for a real `gymnasium.Env` implementation. [CITED: https://gymnasium.farama.org/api/env/]
- `mujoco` must be available in a project-supported Python environment for integration tests that load/step the robot. [VERIFIED: codebase read `tests/locomotion/test_locomotion.py:120-138`, `tests/locomotion/test_locomotion.py:315-426`]

**Missing dependencies with fallback:**
- Headless display tooling is missing, but Phase 1 contract tests can prefer state-only MuJoCo stepping and pure catalog/action tests. [ASSUMED]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 installed locally; project declares `pytest>=8.0.0`. [VERIFIED: local `pytest --version`] [VERIFIED: codebase read `pyproject.toml:40-44`] |
| Config file | `/home/prannayag/pragnition/robotics/argus/pytest.ini` [VERIFIED: codebase read `pytest.ini:1-13`] |
| Quick run command | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` [ASSUMED] |
| Full suite command | `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` [ASSUMED] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOC-ENV-01 | `ArgusGo2Env.reset(seed=...)` returns `(obs, info)` and `step(action)` returns `(obs, reward, terminated, truncated, info)` with spaces containing sampled values. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:14`] | unit + integration | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` | Missing — Wave 0. [VERIFIED: codebase file listing] |
| LOC-ENV-02 | Catalog contains `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, `push_disturbance`, and env config selects each by name. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:15`] | unit | `python -m pytest tests/locomotion/test_argus_go2_env_scenarios.py -q -x` | Missing — Wave 0. [VERIFIED: codebase file listing] |
| LOC-ENV-03 | Same seed reproduces spawn pose, terrain params, command schedule, disturbance timing; different seed changes randomized elements where applicable. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:16`] | unit + integration | `python -m pytest tests/locomotion/test_argus_go2_env_determinism.py -q -x` | Missing — Wave 0. [VERIFIED: codebase file listing] |
| LOC-ENV-04 | Velocity, joint-position, and residual action modes share `step(action)` but use mode-specific `action_space` and decoding. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:17`] | unit | `python -m pytest tests/locomotion/test_argus_go2_env_action_modes.py -q -x` | Missing — Wave 0. [VERIFIED: codebase file listing] |
| Runtime preservation | Existing non-Gym single/multi bridge tests still pass. [VERIFIED: codebase read `.planning/ROADMAP.md:34`] | regression | `python -m pytest tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q -x` | Existing. [VERIFIED: codebase file listing] |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` plus any new focused test for the touched module. [ASSUMED]
- **Per wave merge:** `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`. [ASSUMED]
- **Phase gate:** Full suite green for locomotion and bridge tests before `/gsd-verify-work`; if MuJoCo is unavailable, planner must explicitly record the environment blocker and run pure unit tests. [ASSUMED]

### Wave 0 Gaps

- [ ] `tests/locomotion/test_argus_go2_env_contract.py` — covers LOC-ENV-01. [ASSUMED]
- [ ] `tests/locomotion/test_argus_go2_env_scenarios.py` — covers LOC-ENV-02. [ASSUMED]
- [ ] `tests/locomotion/test_argus_go2_env_determinism.py` — covers LOC-ENV-03. [ASSUMED]
- [ ] `tests/locomotion/test_argus_go2_env_action_modes.py` — covers LOC-ENV-04. [ASSUMED]
- [ ] Dependency install/config: add `gymnasium` dependency or benchmark extra. [VERIFIED: codebase read `pyproject.toml:6-16`] [CITED: https://gymnasium.farama.org/api/env/]
- [ ] Environment check: ensure tests run under Python 3.10-3.12 with `mujoco` installed. [VERIFIED: codebase read `pyproject.toml:5`] [VERIFIED: local package probe]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 1 adds a local Python benchmark wrapper, not auth flows. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`] |
| V3 Session Management | no | No sessions are introduced by the env wrapper. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`] |
| V4 Access Control | no | No user/role boundary changes are introduced. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`] |
| V5 Input Validation | yes | Validate scenario names, action modes, action shape/range, seed type, and config fields before applying to MuJoCo. [CITED: https://gymnasium.farama.org/api/env/] [ASSUMED] |
| V6 Cryptography | no | No cryptographic operations are required. [VERIFIED: codebase read `.planning/ROADMAP.md:25-34`] |

### Known Threat Patterns for Local Benchmark Wrapper

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Invalid action shape or NaN action corrupts physics state | Tampering | Validate action against `action_space`, check finite values, clip residuals before writing `data.ctrl`. [CITED: https://gymnasium.farama.org/api/env/] [ASSUMED] |
| Arbitrary scenario/model path injection | Tampering | Use named scenario catalog rather than arbitrary user-provided XML path in Phase 1. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:15`] [ASSUMED] |
| Non-deterministic benchmark claims | Repudiation | Emit seed, scenario id, sampled params, action mode, command schedule, and disturbance schedule in reset/step `info`. [VERIFIED: codebase read `.planning/STATE.md:75-79`] [ASSUMED] |
| Resource exhaustion via huge heightfield/action dimensions | Denial of Service | Bound heightfield size and action dimensions in config; keep default tests small. [CITED: https://mujoco.readthedocs.io/en/stable/XMLreference.html] [ASSUMED] |

## Sources

### Primary (HIGH confidence)

- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` — phase requirements and out-of-scope boundaries. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md` — Phase 1 goal and success criteria. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` — locked v4.0 decisions and blockers/concerns. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/.planning/PROJECT.md` — project overview, stack, decisions, active v4 scope. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/outputs/locomotion-rd-systems.md` — current locomotion stack and roadmap rationale. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/gait_controller.py` — analytical trot controller API. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/xml_patcher.py` — Go2 actuator conversion and floor helper. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/bridge/sim_bridge.py` — single-robot MuJoCo bridge lifecycle and direct action path. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/bridge/multi_bridge.py` — multi-robot C2 bridge lifecycle and velocity-to-control path. [VERIFIED: codebase read]
- `https://gymnasium.farama.org/api/env/` — Env reset/step/spaces/seeding API. [CITED: official docs]
- `https://mujoco.readthedocs.io/en/stable/python.html` — MuJoCo Python `MjModel`, `MjData`, `mj_resetData`, `mj_forward`, `mj_step`. [CITED: official docs]
- `https://mujoco.readthedocs.io/en/stable/XMLreference.html` — MJCF friction, heightfield, geom, position actuator facts. [CITED: official docs]
- Context7 `/websites/gymnasium_farama` docs query — Env API and migration details. [VERIFIED: Context7]
- Context7 `/google-deepmind/mujoco` docs query — state access, reset, controls, external force fields. [VERIFIED: Context7]

### Secondary (MEDIUM confidence)

- PyPI package index via `python -m pip index versions gymnasium`, `mujoco`, `numpy` — current package versions. [VERIFIED: PyPI]
- Local environment probes for Python, pytest, node/npm, OpenGL, installed Python packages. [VERIFIED: local commands]

### Tertiary (LOW confidence)

- Assumed file/module split and test filenames are planning recommendations, not existing code. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Gymnasium and MuJoCo APIs verified through official docs/Context7 and package versions checked against PyPI. [CITED: https://gymnasium.farama.org/api/env/] [CITED: https://mujoco.readthedocs.io/en/stable/python.html] [VERIFIED: PyPI]
- Architecture: HIGH for existing code boundaries; MEDIUM for proposed file split because implementation has not started. [VERIFIED: codebase read `src/bridge/sim_bridge.py`, `src/bridge/multi_bridge.py`] [ASSUMED]
- Pitfalls: HIGH for seeding/C2 breakage/environment mismatch; MEDIUM for performance/heightfield details until implemented. [VERIFIED: codebase read `.planning/STATE.md:75-79`, `src/main.py:322-467`, `pyproject.toml:5`] [ASSUMED]

**Research date:** 2026-04-30  
**Valid until:** 2026-05-30 for codebase mapping and Gymnasium/MuJoCo API decisions; re-check PyPI versions after 30 days. [ASSUMED]
