# Phase 2: controller-plugin-baseline - Research

**Researched:** 2026-04-30  
**Domain:** Python locomotion controller protocol/registry and MuJoCo bridge control-loop refactor  
**Confidence:** HIGH for codebase constraints and registry/control-loop patterns; MEDIUM for exact module split and bridge-helper extraction shape until implementation proves the seam

## User Constraints (from CONTEXT.md)

### Locked Decisions

Copied from `/home/prannayag/pragnition/robotics/argus/.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md` with section headings preserved. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:13-38`]

#### Controller Protocol Shape
- **D-01:** Use a pure action-mapper protocol: controller instances receive an environment observation, a typed command object, and `dt`, then return a validated 12-element Go2 joint-position/action target plus controller metadata.
- **D-02:** Keep MuJoCo stepping, reset lifecycle, scenario handling, action decoding, and bridge/environment resource ownership outside the controller protocol.
- **D-03:** Controllers are stateful per robot/environment instance and expose reset behavior, so gait phase state and future policy hidden state are isolated per robot and can be reset deterministically.
- **D-04:** Represent velocity commands with a typed command object/dataclass carrying `vx`, `vy`, `yaw_rate`, and optional metadata instead of raw arrays or observation-embedded commands.

#### Registry and Placeholder Semantics
- **D-05:** Use a perception-style registry for locomotion controllers: named entries, display names, default controller id, lazy loading, `available()` probing, capability metadata, parameter schemas, and explicit unavailable reasons.
- **D-06:** Every controller entry declares a full benchmark capability contract: family, action mode, deterministic flag, supported observation/command expectations, command limits, parameter schema, CPU latency hint, sim-only/hardware applicability, training/model-path requirements, multi-robot support, and relevant reproducibility metadata.
- **D-07:** Register residual policy, direct policy, MPC, and WBC as discoverable placeholder entries with `available=false` and precise reasons. Selecting/creating one fails immediately with a clear unavailable-controller error; placeholders must not construct objects that fail later in `compute()`.
- **D-08:** The analytical trot is the default registered baseline controller and delegates to existing `TrotGaitController.compute(vx, vy, omega, dt)` for behavior-equivalent 12-joint targets.

#### Bridge and Environment Alignment
- **D-09:** Refactor the bridge loop only enough to extract a shared controller dispatch/control-target application helper used by `ArgusGo2Env`, `MuJoCoBridge`, and `MultiRobotBridge` where practical.
- **D-10:** Preserve existing public bridge lifecycles and return types: single-robot bridge still returns a `SensorFrame`, multi-robot bridge still returns `dict[str, SensorFrame]`, and existing C2/non-Gym runtime paths keep booting.
- **D-11:** Existing C2/non-Gym bridge paths use the registered analytical baseline through the new seam, but Phase 2 does not add user-facing C2 controller selection.
- **D-12:** Avoid evaluation-only controller dispatch branches; the shared seam should serve both benchmark environment usage and bridge runtime usage without duplicating control-loop logic.

#### Controller Metadata Surface
- **D-13:** Emit benchmark controller metadata sufficient for future evaluation reproducibility: `controller_id`, display name, family, action mode, deterministic flag, parameter hash/config summary, and capability/availability summary.
- **D-14:** Include full controller metadata in reset/episode info and whenever controller selection changes. Per-step info should carry only compact fields such as `controller_id` and `action_mode` unless a change occurs.
- **D-15:** Controller selection metadata must be available to downstream metrics/evaluation artifacts so Phase 4 can attribute every action and episode to the controller that produced it.

### Claude's Discretion

Copied from `/home/prannayag/pragnition/robotics/argus/.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md`. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:39-42`]

- The exact class/module names are open, but planning should prefer the existing project style: absolute `src.*` imports, dataclass configuration objects, Protocol-style contracts, pytest unit tests, and registry tests modeled on SLAM/perception registries.
- The planner may decide whether metadata is returned directly from `compute()` or attached by a wrapper/result object, as long as the protocol remains a pure action-mapper and downstream `info` contains the required fields.

### Deferred Ideas (OUT OF SCOPE)

Copied from `/home/prannayag/pragnition/robotics/argus/.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md`. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:105-110`]

- User-facing C2 controller selection is deferred; Phase 2 keeps C2 on the registered analytical baseline through the new seam.
- Implementing residual RL, direct RL, MPC, WBC, ROS/hardware control, or perception-conditioned locomotion remains out of scope.

## Project Constraints (from CLAUDE.md)

- `/home/prannayag/pragnition/robotics/argus/CLAUDE.md` contains only placeholder project instructions and no actionable coding, testing, or security directives. [VERIFIED: codebase read `CLAUDE.md:1-3`]
- `/home/prannayag/pragnition/robotics/argus/.claude/CLAUDE.md` contains only placeholder project instructions and no actionable coding, testing, or security directives. [VERIFIED: project context reminder and local read `.claude/CLAUDE.md`]
- Project skill discovery found `.claude/skills/desloppify`, but that skill is a code-health workflow for explicit technical-debt cleanup requests and is not directly applicable to planning this Phase 2 feature/refactor. [VERIFIED: codebase read `.claude/skills/desloppify/SKILL.md:1-9`, `.claude/skills/desloppify/SKILL.md:16-21`]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-CTRL-01 | Developer can register locomotion controllers behind a common protocol that maps environment observation plus command into actuator/action output. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:21`] | Use a `typing.Protocol` for structural subtyping and a registry modeled on `DetectorRegistry` / `Detection3DRegistry`, including lazy class-path loading and `available()` probing. [CITED: https://docs.python.org/3/library/typing.html] [VERIFIED: codebase read `src/perception/registry.py:96-132`, `src/perception/registry.py:135-218`] |
| LOC-CTRL-02 | Existing analytical trot controller is exposed as the default baseline controller through the same protocol. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:22`] | Wrap `TrotGaitController.compute(vx, vy, omega, dt) -> np.ndarray` without rewriting gait math; make the registry default `analytical_trot`. [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`] |
| LOC-CTRL-03 | Developer can add placeholder adapters for residual policy, direct policy, and future MPC/WBC controllers without modifying the MuJoCo bridge internals. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:23`] | Register placeholder entries with full capability metadata and `available() -> (False, reason)`, and make `create()` fail before constructing an unusable controller. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`, `src/perception/registry.py:155-218`] |
| LOC-CTRL-04 | Multi-robot and single-robot bridges share the same controller/action abstraction where practical, so comparison logic is not duplicated. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:24`] | Extract a small controller dispatch/control-target helper used by `ArgusGo2Env`, `MuJoCoBridge`, and `MultiRobotBridge`; preserve `MuJoCoBridge.step() -> SensorFrame` and `MultiRobotBridge.step() -> dict[str, SensorFrame]`. [VERIFIED: codebase read `src/bridge/sim_bridge.py:134-172`, `src/bridge/multi_bridge.py:204-275`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:29-32`] |

</phase_requirements>

## Summary

Phase 2 is a plugin seam and control-loop refactor, not a new locomotion algorithm phase. [VERIFIED: codebase read `.planning/ROADMAP.md:58-68`, `.planning/REQUIREMENTS.md:60-66`] The current Argus locomotion stack is velocity command -> `TrotGaitController.compute(vx, vy, omega, dt)` -> 12 Go2 joint-position targets -> MuJoCo `data.ctrl` under position actuators. [VERIFIED: codebase read `outputs/locomotion-rd-systems.md:3-9`, `src/locomotion/gait_controller.py:39-86`, `src/bridge/sim_bridge.py:149-154`, `src/bridge/multi_bridge.py:215-223`] The planner should wrap that path as the default registered `analytical_trot` controller and explicitly register unavailable future-controller placeholders rather than adding residual/RL/MPC/WBC implementation work. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`, `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:31-41`]

The strongest project-local pattern is the perception registry, not the older simpler SLAM registry, because perception already validates mandatory capability keys, performs lazy class-path loading, calls `available()` probes, and surfaces unavailable reasons. [VERIFIED: codebase read `src/perception/registry.py:41-132`, `src/perception/registry.py:155-218`] The controller registry should copy that discipline: lightweight imports, deterministic errors, full metadata, registry isolation in tests, and no heavy optional backend import just to list choices. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:26-50`, `tests/perception/test_registry.py:116-134`]

**Primary recommendation:** Implement `src/locomotion/controllers.py` or a small `src/locomotion/controllers/` package containing `LocomotionCommand`, `LocomotionController` protocol, `ControllerResult`, `ControllerRegistry`, `AnalyticalTrotController`, unavailable placeholder classes, and shared dispatch/application helpers consumed by `ArgusGo2Env`, `MuJoCoBridge`, and `MultiRobotBridge`. [ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Controller protocol and typed command | API / Backend | Locomotion domain layer | The protocol transforms observation + command + `dt` into a 12-element actuator/action target inside Python, not in UI or storage. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-21`] |
| Controller registry and availability metadata | API / Backend | Optional backend import boundary | Argus already uses backend registries for algorithm discovery and optional dependency availability. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:15-32`, `src/perception/registry.py:135-218`] |
| Analytical trot baseline adapter | Locomotion domain layer | MuJoCo bridge control loop | The adapter delegates to `TrotGaitController` and returns joint-position targets; bridges only apply the result to `data.ctrl`. [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`, `src/bridge/sim_bridge.py:149-154`] |
| Future residual/direct/MPC/WBC placeholders | API / Backend | Optional backend import boundary | Placeholders are discovery metadata and immediate selection-time errors, not runtime controller implementations. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`] |
| Single-robot bridge dispatch | API / Backend | MuJoCo runtime state | `MuJoCoBridge` must keep returning `SensorFrame` while obtaining controls through the shared controller seam. [VERIFIED: codebase read `src/bridge/sim_bridge.py:134-172`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:29-32`] |
| Multi-robot bridge dispatch | API / Backend | MuJoCo runtime state | `MultiRobotBridge` already stores one gait instance per robot, which maps naturally to one controller instance per robot. [VERIFIED: codebase read `src/bridge/multi_bridge.py:56-64`, `src/bridge/multi_bridge.py:215-223`] |
| Controller metadata in env/evaluation info | API / Backend | Future metrics/evaluation artifacts | Phase 4 requires controller attribution metadata, so Phase 2 must emit reset/step metadata now. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`, `.planning/ROADMAP.md:63-68`] |

## Standard Stack

### Core

| Library / Pattern | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `typing.Protocol` + `@runtime_checkable` | Python stdlib; project supports Python `>=3.10,<3.13`. [VERIFIED: codebase read `pyproject.toml:5`] | Defines the structural `LocomotionController` contract. [CITED: https://docs.python.org/3/library/typing.html] | Protocols provide structural subtyping; runtime-checkable protocols only check attribute presence, so tests should validate behavior and output shape separately. [CITED: https://docs.python.org/3/library/typing.html] |
| Python `dataclasses` | Python stdlib. [VERIFIED: codebase read `src/locomotion/gait_params.py:4-8`, `src/locomotion/env.py:3-25`] | Defines `LocomotionCommand`, metadata/config result objects, and capability records. [ASSUMED] | Existing locomotion and bridge config use dataclasses. [VERIFIED: codebase read `src/locomotion/gait_params.py:7-42`, `src/bridge/env_config.py:7-27`] |
| `numpy` | Current PyPI 2.4.4; local interpreter has 2.4.4; project declares `numpy>=1.26.0`. [VERIFIED: PyPI via `python -m pip index versions numpy`] [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:6-16`] | Represents observations, commands, action vectors, and 12-element joint-position targets. [VERIFIED: codebase read `src/locomotion/gait_controller.py:14-86`, `src/locomotion/actions.py:16-53`] | Existing gait, bridge, action, and observation code is NumPy-based. [VERIFIED: codebase read `src/bridge/sim_bridge.py:14-20`, `src/locomotion/observations.py:3-71`] |
| Existing `TrotGaitController` | Project-local. [VERIFIED: codebase read `src/locomotion/gait_controller.py:19-86`] | Default analytical trot baseline implementation. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`] | ADR-0019 requires benchmarking the current analytical baseline before adding new controller families. [VERIFIED: codebase read `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:31-41`] |
| `pytest` + `pytest-timeout` | Local pytest 9.0.2; project declares `pytest>=8.0.0` and `pytest-timeout>=2.0.0`. [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:41-45`, `pytest.ini:1-16`] | Registry, protocol, metadata, bridge equivalence, and env metadata tests. [VERIFIED: codebase read `tests/perception/test_registry.py:116-220`, `tests/locomotion/test_gait_controller.py:18-163`] | Existing project validation is pytest-based. [VERIFIED: codebase read `pytest.ini:1-16`] |

### Supporting

| Library / Pattern | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `gymnasium` | Current PyPI 1.3.0; project already declares `gymnasium>=1.3.0`; not installed in the current Python 3.14 interpreter. [VERIFIED: PyPI via `python -m pip index versions gymnasium`] [VERIFIED: codebase read `pyproject.toml:6-16`] [VERIFIED: local package probe] | `ArgusGo2Env` reset/step contract and `info` metadata surface. [CITED: https://gymnasium.farama.org/api/env/] [VERIFIED: codebase read `src/locomotion/env.py:28-126`] | Use only for environment integration; do not couple the controller protocol to Gymnasium base classes. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-19`] |
| `mujoco` | Current PyPI 3.8.0; project declares `mujoco>=3.0.0`; not installed in the current Python 3.14 interpreter. [VERIFIED: PyPI via `python -m pip index versions mujoco`] [VERIFIED: codebase read `pyproject.toml:6-16`] [VERIFIED: local package probe] | Bridge/runtime application of 12-element controls to `data.ctrl` and physics stepping. [CITED: https://mujoco.readthedocs.io/en/stable/python.html] | Keep MuJoCo out of controller protocol; only dispatch helpers/bridges touch MuJoCo data handles. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-19`] |
| `importlib` | Python stdlib. [VERIFIED: codebase read `src/perception/registry.py:30-37`] | Lazy class-path loading for registered controller entries. [VERIFIED: codebase read `src/perception/registry.py:96-108`] | Use in registry only; avoid importing future heavy ML/model-based libraries during listing. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:42-50`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Protocol + registry | Switch statements in bridges | Switch statements are simpler initially but contradict ADR-0006 and force bridge edits for each future controller. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:19-32`, `.planning/REQUIREMENTS.md:21-24`] |
| Perception-style registry | Older SLAM registry | SLAM registry is lighter, but perception registry already has capability validation, availability probing, and unavailable reasons needed by Phase 2. [VERIFIED: codebase read `src/slam/registry.py:48-127`, `src/perception/registry.py:41-218`] |
| Placeholder registered classes | Omit unavailable future controllers until implemented | Omitting them hides extension seams and fails LOC-CTRL-03; registered unavailable entries make the boundary visible without implementation creep. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:23`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`] |
| One shared public bridge API | Preserve existing bridge APIs with an internal dispatch helper | Rewriting bridge APIs would break callers; an internal helper satisfies D-09/D-10 with less blast radius. [VERIFIED: codebase read `src/bridge/sensor_types.py:96-109`, `src/bridge/multi_bridge.py:204-275`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:29-32`] |

**Installation:**
```bash
# No new packages are required for Phase 2 beyond existing pyproject dependencies.
# Use a project-supported Python 3.10-3.12 environment before running MuJoCo/Gymnasium integration tests.
```
[VERIFIED: codebase read `pyproject.toml:5-16`] [VERIFIED: local package probe]

**Version verification:** Package currency was checked with `python -m pip index versions gymnasium`, `python -m pip index versions mujoco`, and `python -m pip index versions numpy` on 2026-04-30. [VERIFIED: PyPI]

## Architecture Patterns

### System Architecture Diagram

```mermaid
flowchart TD
  A[Caller: ArgusGo2Env / MuJoCoBridge / MultiRobotBridge] --> B[Controller selection id]
  B --> C[ControllerRegistry.list/create]
  C --> D{entry available?}
  D -->|no| E[UnavailableControllerError before run]
  D -->|yes| F[Per-instance LocomotionController]
  A --> G[Observation/state snapshot]
  A --> H[LocomotionCommand vx/vy/yaw_rate + metadata]
  A --> I[dt]
  G --> J[ControllerDispatch.compute]
  H --> J
  I --> J
  F --> J
  J --> K[ControllerResult: 12 joint targets + metadata]
  K --> L{target validation}
  L -->|invalid| M[ValueError before data.ctrl]
  L -->|valid| N[Apply to control sink]
  N -->|Env / single robot| O[data.ctrl[:]=target]
  N -->|multi robot| P[data.ctrl[robot actuator ids]=target]
  O --> Q[mj_step owned by caller]
  P --> Q
  K --> R[Compact step info: controller_id/action_mode]
  C --> S[Full reset/selection metadata]
```

The diagram assigns MuJoCo stepping to bridges/environment and assigns only observation-command-to-target mapping to controllers, which is required by D-01/D-02. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-19`]

### Recommended Project Structure

```text
src/
├── locomotion/
│   ├── controllers.py          # Protocol, command/result dataclasses, registry, adapters, placeholders [ASSUMED]
│   ├── controller_dispatch.py  # Shared target validation/application helpers if controllers.py grows large [ASSUMED]
│   ├── env.py                  # Existing ArgusGo2Env; add controller config + metadata integration [VERIFIED: codebase read `src/locomotion/env.py:17-126`]
│   ├── actions.py              # Existing action-mode helpers; keep pure action decoding and avoid duplicating controller registry [VERIFIED: codebase read `src/locomotion/actions.py:12-152`]
│   ├── gait_controller.py      # Existing analytical gait implementation; do not rewrite [VERIFIED: codebase read `src/locomotion/gait_controller.py:19-86`]
│   └── gait_params.py          # Existing gait parameter dataclass [VERIFIED: codebase read `src/locomotion/gait_params.py:7-42`]
└── bridge/
    ├── sim_bridge.py           # Replace direct TrotGaitController ownership with default registered controller where practical [VERIFIED: codebase read `src/bridge/sim_bridge.py:42-55`, `src/bridge/sim_bridge.py:197-207`]
    └── multi_bridge.py         # Replace per-robot gait dict with per-robot registered controllers where practical [VERIFIED: codebase read `src/bridge/multi_bridge.py:56-64`, `src/bridge/multi_bridge.py:447-463`]

tests/
├── locomotion/
│   ├── test_locomotion_controller_registry.py  # registry, metadata, placeholders [ASSUMED]
│   ├── test_locomotion_controller_protocol.py  # protocol/result shape/reset behavior [ASSUMED]
│   ├── test_controller_dispatch.py             # validation and ctrl application helper [ASSUMED]
│   └── existing env/gait tests extended for controller metadata [VERIFIED: codebase read `tests/locomotion/test_argus_go2_env_contract.py:100-139`, `tests/locomotion/test_gait_controller.py:18-163`]
└── bridge/
    ├── test_sim_bridge.py       # preserve public behavior and analytical equivalence [VERIFIED: codebase read `tests/bridge/test_sim_bridge.py:21-66`]
    └── test_multi_bridge.py     # preserve dict return and per-robot independence [VERIFIED: codebase read `tests/bridge/test_multi_bridge.py:76-125`]
```

### Pattern 1: Runtime-checkable structural protocol, plus behavioral tests

**What:** Define a small protocol with `reset(seed: int | None = None) -> None`, `compute(observation, command, dt) -> ControllerResult`, and metadata/capability accessors or attributes. [ASSUMED]

**When to use:** Use it for all controller instances created by the registry; do not require future implementations to inherit a base class. [CITED: https://docs.python.org/3/library/typing.html]

**Example:**
```python
# Source: https://docs.python.org/3/library/typing.html
from typing import Protocol, runtime_checkable

@runtime_checkable
class LocomotionController(Protocol):
    def reset(self, seed: int | None = None) -> None: ...
    def compute(self, observation: dict, command: LocomotionCommand, dt: float) -> ControllerResult: ...
```

**Planning note:** Runtime protocol checks only validate member presence and do not validate signatures or types, so Wave 0 tests must assert reset behavior, finite `(12,)` outputs, metadata fields, and registry errors directly. [CITED: https://docs.python.org/3/library/typing.html]

### Pattern 2: Perception-style registry with mandatory capability metadata

**What:** Register controller entries by name/display/class path/klass, validate mandatory capability keys at registration, lazy-load classes, call `available()`, and raise a deterministic unavailable-controller error before construction when `available()` is false. [VERIFIED: codebase read `src/perception/registry.py:63-132`, `src/perception/registry.py:135-218`]

**When to use:** Required for LOC-CTRL-01 and LOC-CTRL-03. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:21-24`]

**Example:**
```python
# Source pattern: src/perception/registry.py:63-132 and src/perception/registry.py:201-218
class ControllerRegistry:
    _controllers: dict[str, dict] = {}
    _default = "analytical_trot"

    @classmethod
    def list_controllers(cls) -> list[dict]:
        # lazy-load, probe available(), copy CAPABILITIES and PARAMETER_SCHEMA
        ...

    @classmethod
    def create(cls, name: str | None = None, **kwargs):
        # unknown -> ValueError; unavailable -> UnavailableControllerError; unloadable -> ImportError
        ...
```

### Pattern 3: Analytical adapter delegates, it does not reinterpret gait math

**What:** The baseline adapter converts `LocomotionCommand(vx, vy, yaw_rate)` into `TrotGaitController.compute(vx, vy, yaw_rate, dt)` and wraps the result in metadata. [VERIFIED: codebase read `src/locomotion/gait_controller.py:39-86`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`]

**When to use:** Default controller in env and both bridge paths. [VERIFIED: codebase read `.planning/ROADMAP.md:62-68`]

**Example:**
```python
# Source: src/locomotion/gait_controller.py:39-86
class AnalyticalTrotController:
    def __init__(self, params: GaitParams | None = None) -> None:
        self._gait = TrotGaitController(params)

    def reset(self, seed: int | None = None) -> None:
        del seed
        self._gait = TrotGaitController()

    def compute(self, observation, command: LocomotionCommand, dt: float) -> ControllerResult:
        del observation
        target = self._gait.compute(command.vx, command.vy, command.yaw_rate, dt)
        return ControllerResult(action=validate_joint_target(target), metadata={"controller_id": "analytical_trot"})
```
[ASSUMED for wrapper shape; delegation target verified]

### Pattern 4: Shared dispatch helper, not shared bridge API

**What:** Extract helper functions/classes for command construction, controller `compute()`, target validation, and target application to one robot’s `data.ctrl` slice; keep each caller’s public lifecycle and step return. [ASSUMED]

**When to use:** Phase 2 bridge alignment, because single bridge returns `SensorFrame` and multi bridge returns `dict[str, SensorFrame]`. [VERIFIED: codebase read `src/bridge/sim_bridge.py:134-172`, `src/bridge/multi_bridge.py:204-275`, `src/bridge/sensor_types.py:96-109`]

**Example:**
```python
# Source pattern: src/bridge/sim_bridge.py:149-154 and src/bridge/multi_bridge.py:215-219
def apply_joint_target(data, target: np.ndarray, ctrl_indices: list[int] | None = None) -> None:
    target = validate_joint_target(target)
    if ctrl_indices is None:
        data.ctrl[:] = target
    else:
        for i, act_id in enumerate(ctrl_indices):
            data.ctrl[act_id] = target[i]
```
[ASSUMED for helper name; target application pattern verified]

### Anti-Patterns to Avoid

- **Controller owns MuJoCo stepping:** D-02 explicitly keeps MuJoCo stepping and resource ownership outside the controller protocol. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-19`]
- **Constructing placeholder controllers that fail in `compute()`:** D-07 requires unavailable placeholders to fail immediately at selection/creation time. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`]
- **Importing future ML/MPC dependencies in the registry module:** ADR-0006 warns registry imports must stay lightweight, and perception tests enforce that pattern for heavy perception dependencies. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:42-50`, `tests/perception/test_registry.py:116-134`]
- **Changing `MuJoCoBridge.step()` or `MultiRobotBridge.step()` return types:** D-10 preserves existing bridge lifecycles and return types. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:29-32`, `src/bridge/sim_bridge.py:134-172`, `src/bridge/multi_bridge.py:204-275`]
- **Duplicating evaluation-only dispatch branches:** D-12 requires the shared seam to serve benchmark and bridge runtime usage. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:29-32`]
- **Letting invalid/NaN controller output reach `data.ctrl`:** Existing action helpers validate finite shape/range before controls reach physics; controller results need the same finite `(12,)` gate. [VERIFIED: codebase read `src/locomotion/actions.py:85-152`] [CITED: https://mujoco.readthedocs.io/en/stable/python.html]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Plugin discovery | Ad hoc bridge `if controller_id == ...` switches | Registry modeled on `src/perception/registry.py` | Argus has an accepted protocol/registry ADR and a proven availability/capability pattern. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:26-32`, `src/perception/registry.py:135-218`] |
| Structural controller interface | Abstract base class forcing inheritance | `typing.Protocol` | Protocols support structural subtyping and avoid inheritance coupling. [CITED: https://docs.python.org/3/library/typing.html] |
| Baseline gait math | New analytical gait implementation | Existing `TrotGaitController` | D-08 requires behavior-equivalent delegation to existing trot. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`, `src/locomotion/gait_controller.py:39-86`] |
| Future-controller scaffolding | Dummy objects that raise during `compute()` | Unavailable registry entries with explicit reasons | D-07 requires failure at selection time, not mid-run. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`] |
| Target validation | Trust controller outputs | Shared finite `(12,)` action validation before `data.ctrl` | MuJoCo control loops update `data.ctrl` in place before stepping, so invalid controls should be blocked first. [CITED: https://mujoco.readthedocs.io/en/stable/python.html] [VERIFIED: codebase read `src/locomotion/actions.py:125-148`] |
| Metadata hashing/config summaries | Unstable `repr()` of nested objects | Deterministic JSON-compatible summary + stable hash helper | Phase 4 needs reproducible metadata attribution. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`, `.planning/ROADMAP.md:89-93`] [ASSUMED for helper implementation] |

**Key insight:** The registry should make future controller families discoverable but unavailable, while the dispatch helper makes the current analytical trot path explicit and reusable; anything more ambitious violates the benchmark-before-sophistication decision. [VERIFIED: codebase read `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:31-41`]

## Runtime State Inventory

This phase refactors runtime controller dispatch and bridge alignment, so runtime state was checked for controller-related migration hazards. [VERIFIED: phase scope from `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:6-10`]

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None found in the repository search for local database files under the project root; Phase 2 does not introduce persistent controller records. [VERIFIED: local `find` for `*.db`, `*.sqlite`, `*.sqlite3`] [ASSUMED: no external datastore is configured for this phase] | No data migration required. [ASSUMED] |
| Live service config | None identified in Phase 2 scope; C2 controller selection is explicitly deferred. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:105-110`] | No live UI/service config migration; keep C2 on analytical baseline. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:30-31`] |
| OS-registered state | None identified; bridge/controller selection is code-level Python state. [ASSUMED] | No OS re-registration required. [ASSUMED] |
| Secrets/env vars | None found in repository search for `.env`; controller placeholders should not require model path secrets in Phase 2. [VERIFIED: local `find` for `.env`] [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:105-110`] | No secret/env migration required. [ASSUMED] |
| Build artifacts | Existing `dimensional_applications.egg-info` and `frontend/dist` were found; they are unrelated to locomotion controller naming. [VERIFIED: local `find` for `*egg-info`, `dist`, `build`] | No package reinstall required for source-only planning, but executor should avoid editing build artifacts. [ASSUMED] |

## Common Pitfalls

### Pitfall 1: Registry listing imports future heavy dependencies

**What goes wrong:** Listing controllers imports future RL/MPC/WBC modules or model dependencies even when those controllers are unavailable. [ASSUMED]  
**Why it happens:** Registry stores classes or direct imports instead of lazy class paths and `available()` probes. [VERIFIED: codebase read `src/perception/registry.py:96-132`]  
**How to avoid:** Keep registry module stdlib/lightweight, store dotted class paths, lazy-load during listing/creation, and make placeholder classes dependency-free. [VERIFIED: codebase read `src/perception/registry.py:30-37`, `src/perception/registry.py:96-108`]  
**Warning signs:** Importing `src.locomotion.controllers` pulls `torch`, MPC solvers, ROS, or other future dependencies into `sys.modules`. [ASSUMED]

### Pitfall 2: Placeholder controllers fail too late

**What goes wrong:** A residual/direct/MPC/WBC placeholder constructs successfully and raises only when `compute()` is called mid-run. [VERIFIED: prohibited by `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`]  
**Why it happens:** Placeholder classes implement the protocol but use runtime `NotImplementedError` instead of registry availability semantics. [ASSUMED]  
**How to avoid:** `available()` returns `(False, precise_reason)`, and `ControllerRegistry.create()` raises `UnavailableControllerError` before instantiation. [VERIFIED: codebase pattern `src/perception/registry.py:111-132`, `src/perception/registry.py:201-218`]  
**Warning signs:** Tests instantiate `ResidualPolicyController` and assert `compute()` raises. [ASSUMED]

### Pitfall 3: Analytical baseline is behavior-adjacent but not behavior-equivalent

**What goes wrong:** The adapter clips, reorders, retimes, or otherwise changes the existing `TrotGaitController` output. [VERIFIED: D-08 requires delegation via `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`]  
**Why it happens:** The wrapper reimplements velocity interpretation, leg order, or standing pose. [ASSUMED]  
**How to avoid:** In tests, compare adapter output directly against a fresh `TrotGaitController.compute(vx, vy, omega, dt)` for zero and nonzero commands. [VERIFIED: codebase read `tests/locomotion/test_gait_controller.py:49-74`, `tests/locomotion/test_gait_controller.py:155-163`]  
**Warning signs:** Flat-ground smoke output changes before Phase 4 regression baselines exist. [VERIFIED: Phase 4 requires analytical-baseline regression from `.planning/ROADMAP.md:89-93`]

### Pitfall 4: Shared abstraction accidentally changes bridge public contracts

**What goes wrong:** Single bridge starts returning env-style tuples, or multi bridge stops returning `dict[str, SensorFrame]`. [VERIFIED: prohibited by `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:29-32`]  
**Why it happens:** Planner tries to centralize bridge APIs instead of only centralizing control-target dispatch. [ASSUMED]  
**How to avoid:** Keep public `start/step/set_velocity/stop` behavior and only replace internals that compute/apply target controls. [VERIFIED: codebase read `src/bridge/sensor_types.py:96-109`, `src/bridge/sim_bridge.py:134-172`, `src/bridge/multi_bridge.py:204-285`]  
**Warning signs:** Existing bridge tests require broad rewrites rather than new controller-specific assertions. [VERIFIED: codebase read `tests/bridge/test_sim_bridge.py:21-66`, `tests/bridge/test_multi_bridge.py:76-125`]

### Pitfall 5: One controller instance is shared across robots

**What goes wrong:** Multi-robot gait phase or future policy hidden state leaks between robots. [VERIFIED: D-03 requires stateful per robot/env isolation from `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-20`]  
**Why it happens:** Registry creates one singleton controller and multi bridge reuses it for all robot IDs. [ASSUMED]  
**How to avoid:** Create one controller instance per robot/environment instance, mirroring the current `_gaits: dict[str, TrotGaitController]` pattern. [VERIFIED: codebase read `src/bridge/multi_bridge.py:56-64`]  
**Warning signs:** Commands to one robot advance another robot’s controller phase. [ASSUMED]

### Pitfall 6: Controller metadata is too sparse for Phase 4

**What goes wrong:** Info only contains a display name or only the action mode, so exported runs cannot attribute actions to controller capabilities/config. [VERIFIED: D-13/D-15 require metadata from `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`]  
**Why it happens:** Metadata is treated as UI garnish instead of benchmark provenance. [ASSUMED]  
**How to avoid:** Emit full metadata at reset/selection changes and compact `controller_id`/`action_mode` per step. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`]  
**Warning signs:** Tests assert only `controller_id` exists and ignore deterministic flag, family, parameter hash/config summary, and availability/capabilities. [ASSUMED]

### Pitfall 7: Local Python environment masks integration failures

**What goes wrong:** Local shell runs Python 3.14 while project supports Python 3.10-3.12, and current interpreter lacks `gymnasium` and `mujoco`. [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:5-16`]  
**Why it happens:** Executor runs tests in the default shell instead of a project-supported environment. [ASSUMED]  
**How to avoid:** Keep pure registry/protocol tests runnable without MuJoCo, and explicitly skip/mark integration tests outside supported Python or without MuJoCo. [VERIFIED: codebase read `tests/locomotion/test_argus_go2_env_contract.py:16-22`]  
**Warning signs:** `ModuleNotFoundError: gymnasium`, `ModuleNotFoundError: mujoco`, or install refusal due to `requires-python`. [VERIFIED: local package probe]

## Code Examples

Verified patterns from official sources and current codebase:

### Registry availability probe

```python
# Source: src/perception/registry.py:111-132
probe = getattr(klass, "available", None)
if probe is None:
    return True, None
result = probe()
if not (isinstance(result, tuple) and len(result) == 2):
    return False, f"available() returned malformed result: {result!r}"
return bool(result[0]), (None if result[1] is None else str(result[1]))
```

### Existing analytical gait target

```python
# Source: src/locomotion/gait_controller.py:39-86
ctrl = TrotGaitController().compute(vx=0.3, vy=0.0, omega=0.0, dt=0.02)
assert ctrl.shape == (12,)
```

### Single-robot target application

```python
# Source: src/bridge/sim_bridge.py:149-154
if action is not None:
    self._data.ctrl[:] = action
else:
    ctrl = self._velocity_to_ctrl()
    self._data.ctrl[:] = ctrl
```

### Multi-robot target application

```python
# Source: src/bridge/multi_bridge.py:215-219
for robot_id in self._config.robot_ids:
    ctrl = self._velocity_to_ctrl(robot_id)
    for i, act_id in enumerate(self._ctrl_indices[robot_id]):
        self._data.ctrl[act_id] = ctrl[i]
```

### Gymnasium info surface for metadata

```python
# Source: https://gymnasium.farama.org/api/env/
# reset returns (observation, info); step returns (observation, reward, terminated, truncated, info)
observation, info = env.reset(seed=123)
observation, reward, terminated, truncated, info = env.step(action)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard-coded trot inside bridge methods | Registry-selected controller instances behind a protocol | v4.0 Phase 2 planning decision. [VERIFIED: codebase read `.planning/ROADMAP.md:58-68`, `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:16-32`] | Future controller families become discoverable without editing bridge internals. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:21-24`] |
| Custom backend switches | Protocol + registry pattern | ADR-0006 accepted on 2026-04-30. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:1-32`] | Selection, capability metadata, optional-dependency availability, and comparisons follow project architecture. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:30-40`] |
| Hidden controller identity | Reset/selection metadata plus compact per-step attribution | Phase 2 D-13/D-15. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`] | Phase 4 exports can attribute results to controller id/family/action mode/config. [VERIFIED: codebase read `.planning/ROADMAP.md:89-93`] |
| New controller family implementation before metrics | Unavailable future-controller placeholders until harness is ready | ADR-0019 on 2026-04-30. [VERIFIED: codebase read `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:31-41`] | Prevents RL/MPC/WBC scope creep before benchmark and metrics exist. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:60-66`] |

**Deprecated/outdated:**
- Bridge-private `_gait` / `_gaits` as the only controller selection mechanism is outdated for v4.0 because Phase 2 requires registry-backed controller comparison seams. [VERIFIED: codebase read `src/bridge/sim_bridge.py:53-54`, `src/bridge/multi_bridge.py:61-64`, `.planning/REQUIREMENTS.md:21-24`]
- Mid-run `NotImplementedError` placeholders are prohibited by D-07; use unavailable registry entries instead. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Put protocol/registry/adapters in `src/locomotion/controllers.py` or a small `controllers/` package. | Summary / Recommended Project Structure | Low; planner can choose different names if responsibilities stay isolated. |
| A2 | Use a separate `controller_dispatch.py` only if helper code grows large. | Recommended Project Structure | Low; file split can be adjusted during planning. |
| A3 | Define `LocomotionController` with `reset()` and `compute()` methods. | Architecture Patterns | Medium; if metadata is attribute-based or result-based differently, tests must still cover D-01/D-03/D-13. |
| A4 | Use deterministic JSON-compatible parameter summaries and stable hashing for controller config. | Don't Hand-Roll / Pitfalls | Medium; exact hash strategy may change, but Phase 4 needs stable metadata. |
| A5 | No external datastore, OS registration, or live service config contains controller selection state. | Runtime State Inventory | Low to medium; repo evidence shows no local DB/env state, but untracked external service state cannot be fully proven from the repo. |

## Open Questions (RESOLVED)

1. **RESOLVED: `ArgusGo2EnvConfig` gains `controller_id: str = "analytical_trot"` in Phase 2.**
   - What we know: Phase 1 env config currently has `scenario_id` and `action_mode` but no `controller_id`. [VERIFIED: codebase read `src/locomotion/env.py:17-25`]
   - Chosen answer: Add `controller_id: str = "analytical_trot"` to env config in Phase 2 so reset/step `info` can satisfy D-13/D-15 before Phase 4. [RESOLVED]

2. **RESOLVED: Controller `compute()` returns `ControllerResult(action: np.ndarray, metadata: dict[str, Any])`.**
   - What we know: CONTEXT allows either metadata returned directly from `compute()` or attached by a wrapper/result object. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:39-42`]
   - Chosen answer: Use `ControllerResult(action: np.ndarray, metadata: dict[str, Any])` because it keeps validation and metadata together without letting controllers own MuJoCo stepping. [RESOLVED]

3. **RESOLVED: `src/locomotion/actions.py` does not own registry selection.**
   - What we know: `actions.decode_action()` currently creates 12-joint targets from action mode and a provided `TrotGaitController`. [VERIFIED: codebase read `src/locomotion/actions.py:85-122`]
   - Chosen answer: Env/bridge dispatch chooses the controller, while `actions.py` remains validation/action-space utilities where still useful. [RESOLVED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All tests/runtime | Warning | Current shell Python 3.14.4; project requires `>=3.10,<3.13`. [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:5`] | Use Python 3.10-3.12 for integration. [ASSUMED] |
| `numpy` | Controller outputs and validation | Yes | 2.4.4 local; project declares `numpy>=1.26.0`. [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:12`] | None. |
| `pytest` | Validation | Yes | 9.0.2 local; project declares `pytest>=8.0.0`. [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:41-45`] | None for pure unit tests. |
| `gymnasium` | Existing env integration and metadata info checks | No in current interpreter | Current PyPI 1.3.0; project declares `gymnasium>=1.3.0`. [VERIFIED: local package probe] [VERIFIED: PyPI] [VERIFIED: codebase read `pyproject.toml:8`] | Pure registry/protocol tests can run without importing env if imports are kept lightweight; env tests need supported environment. [ASSUMED] |
| `mujoco` | Bridge integration/equivalence tests | No in current interpreter | Current PyPI 3.8.0; project declares `mujoco>=3.0.0`. [VERIFIED: local package probe] [VERIFIED: PyPI] [VERIFIED: codebase read `pyproject.toml:7`] | Pure dispatch/application tests can use fake data objects; real bridge smoke requires supported environment. [ASSUMED] |

**Missing dependencies with no fallback:**
- A project-supported Python 3.10-3.12 environment with `gymnasium` and `mujoco` is required for full env/bridge integration tests. [VERIFIED: codebase read `pyproject.toml:5-16`, `tests/locomotion/test_argus_go2_env_contract.py:16-22`]

**Missing dependencies with fallback:**
- Current Python 3.14 interpreter can still run pure registry/protocol tests if imports avoid `gymnasium`/`mujoco` at controller registry import time. [ASSUMED]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 local; project declares `pytest>=8.0.0` and `pytest-timeout>=2.0.0`. [VERIFIED: local package probe] [VERIFIED: codebase read `pyproject.toml:41-45`] |
| Config file | `/home/prannayag/pragnition/robotics/argus/pytest.ini` [VERIFIED: codebase read `pytest.ini:1-16`] |
| Quick run command | `python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_locomotion_controller_protocol.py -q -x` [ASSUMED] |
| Full suite command | `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` [ASSUMED] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOC-CTRL-01 | Common protocol maps observation + typed command + `dt` to finite 12-element actuator/action output. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:21`] | unit | `python -m pytest tests/locomotion/test_locomotion_controller_protocol.py -q -x` | No — Wave 0. [VERIFIED: local file search] |
| LOC-CTRL-02 | `analytical_trot` is default registered baseline and matches `TrotGaitController.compute()`. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:22`, `src/locomotion/gait_controller.py:39-86`] | unit + smoke | `python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_gait_controller.py -q -x` | Registry test missing; gait test exists. [VERIFIED: local file search] [VERIFIED: codebase read `tests/locomotion/test_gait_controller.py:1-163`] |
| LOC-CTRL-03 | residual/direct/MPC/WBC placeholders are discoverable unavailable entries and fail at `create()` with explicit reasons. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:23`] | unit | `python -m pytest tests/locomotion/test_locomotion_controller_registry.py -q -x` | No — Wave 0. [VERIFIED: local file search] |
| LOC-CTRL-04 | Single and multi bridge paths use shared controller/action abstraction where practical without changing public return types. [VERIFIED: codebase read `.planning/REQUIREMENTS.md:24`] | unit + regression | `python -m pytest tests/locomotion/test_controller_dispatch.py tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q -x` | Dispatch test missing; bridge tests exist. [VERIFIED: local file search] [VERIFIED: codebase read `tests/bridge/test_sim_bridge.py:1-180`, `tests/bridge/test_multi_bridge.py:1-125`] |
| Metadata surface | Reset/selection info includes full controller metadata; per-step info includes compact attribution. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`] | unit + env regression | `python -m pytest tests/locomotion/test_argus_go2_env_contract.py tests/locomotion/test_locomotion_controller_registry.py -q -x` | Env test exists; controller metadata tests missing. [VERIFIED: codebase read `tests/locomotion/test_argus_go2_env_contract.py:100-139`] |

### Sampling Rate

- **Per task commit:** Run `python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_locomotion_controller_protocol.py -q -x` plus the focused test file for changed bridge/env modules. [ASSUMED]
- **Per wave merge:** Run `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`. [ASSUMED]
- **Phase gate:** Full locomotion and bridge suite green in a project-supported Python 3.10-3.12 environment; if MuJoCo is unavailable locally, record the blocker and run all pure registry/protocol/dispatch tests. [ASSUMED]

### Wave 0 Gaps

- [ ] `tests/locomotion/test_locomotion_controller_registry.py` — covers LOC-CTRL-01, LOC-CTRL-02, LOC-CTRL-03, metadata listing, default id, unavailable placeholders, lazy import. [ASSUMED]
- [ ] `tests/locomotion/test_locomotion_controller_protocol.py` — covers protocol shape, `LocomotionCommand`, `ControllerResult`, reset isolation, finite `(12,)` output. [ASSUMED]
- [ ] `tests/locomotion/test_controller_dispatch.py` — covers shared target validation and single/multi ctrl application with fake data. [ASSUMED]
- [ ] Extend `tests/locomotion/test_argus_go2_env_contract.py` — covers reset full metadata and per-step compact controller attribution. [ASSUMED]
- [ ] Extend bridge tests — verify `MuJoCoBridge` and `MultiRobotBridge` still expose current public return types while sourcing analytical baseline through the registry seam. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 2 adds local Python controller selection, not authentication. [VERIFIED: codebase read `.planning/ROADMAP.md:58-68`] |
| V3 Session Management | no | No sessions are introduced. [VERIFIED: codebase read `.planning/ROADMAP.md:58-68`] |
| V4 Access Control | no | No user/role access boundary changes are introduced. [VERIFIED: codebase read `.planning/ROADMAP.md:58-68`] |
| V5 Input Validation | yes | Validate controller ids, capability metadata keys/types, command values, `dt`, and finite 12-element controller outputs before applying to MuJoCo controls. [VERIFIED: codebase read `src/perception/registry.py:63-94`, `src/locomotion/actions.py:125-148`] |
| V6 Cryptography | no | No cryptographic operations are required; parameter hash is reproducibility metadata, not a security primitive. [ASSUMED] |

### Known Threat Patterns for Local Controller Plugin Seam

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unknown controller id or typo silently falls back to default | Tampering / Repudiation | Raise deterministic `ValueError` with available controller ids, matching registry patterns. [VERIFIED: codebase read `src/perception/registry.py:207-218`] |
| Unavailable future controller selected and fails mid-run | Tampering / Denial of Service | Probe `available()` and raise unavailable-controller error before construction. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:23-27`] |
| NaN or wrong-shaped target reaches `data.ctrl` | Tampering | Shared finite `(12,)` validation before MuJoCo application. [VERIFIED: codebase read `src/locomotion/actions.py:125-148`] [CITED: https://mujoco.readthedocs.io/en/stable/python.html] |
| Benchmark run cannot prove which controller generated actions | Repudiation | Emit full reset/selection metadata and compact per-step attribution. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md:35-37`] |
| Registry import loads arbitrary heavy/future dependencies | Denial of Service | Lazy class-path loading and lightweight registry imports. [VERIFIED: codebase read `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:42-50`, `src/perception/registry.py:96-108`] |

## Sources

### Primary (HIGH confidence)

- `/home/prannayag/pragnition/robotics/argus/.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md` — locked decisions D-01 through D-15, discretion, deferred scope. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` — LOC-CTRL-01 through LOC-CTRL-04 and out-of-scope boundaries. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md` — Phase 2 success criteria and dependencies. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` — v4 locked decisions and bridge/action seam concerns. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md` — accepted protocol/registry pattern. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` — benchmark harness/controller seam rationale. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` — defer RL/MPC/WBC until benchmark exists. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/outputs/locomotion-rd-systems.md` — current analytical trot + MuJoCo position-servo baseline and future controller ladder. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/perception/registry.py` — registry implementation pattern with capability validation, lazy loading, availability probes, and create semantics. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/gait_controller.py` — analytical trot controller API and behavior. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/bridge/sim_bridge.py` — single-robot current control path and return type. [VERIFIED: codebase read]
- `/home/prannayag/pragnition/robotics/argus/src/bridge/multi_bridge.py` — multi-robot current per-robot gait and control path. [VERIFIED: codebase read]
- `https://docs.python.org/3/library/typing.html` — `Protocol` and `@runtime_checkable` facts. [CITED: official docs]
- `https://gymnasium.farama.org/api/env/` — reset/step signatures and info surface. [CITED: official docs]
- `https://mujoco.readthedocs.io/en/stable/python.html` — MuJoCo `MjModel`, `MjData`, `data.ctrl`, `mj_resetData`, `mj_forward`, and `mj_step` facts. [CITED: official docs]

### Secondary (MEDIUM confidence)

- PyPI package index via `python -m pip index versions gymnasium`, `mujoco`, and `numpy` — current package versions. [VERIFIED: PyPI]
- Local environment probes for Python, pytest, installed packages, and runtime artifact search. [VERIFIED: local commands]

### Tertiary (LOW confidence)

- Proposed file/module names, exact `ControllerResult` shape, and exact parameter-hash helper are planning recommendations. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new external stack is required; existing dependencies and stdlib patterns were verified against codebase, PyPI, and official docs. [VERIFIED: codebase read `pyproject.toml:5-16`] [VERIFIED: PyPI] [CITED: https://docs.python.org/3/library/typing.html]
- Architecture: HIGH for registry/bridge constraints; MEDIUM for exact helper/module split because implementation has not proven the seam. [VERIFIED: codebase read `src/perception/registry.py`, `src/bridge/sim_bridge.py`, `src/bridge/multi_bridge.py`] [ASSUMED]
- Pitfalls: HIGH for scope, placeholder, metadata, and bridge-contract risks because they are locked in CONTEXT/ADRs; MEDIUM for local runtime-state absence because external service state cannot be fully proven from repo-only evidence. [VERIFIED: codebase read `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md`, `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md`] [ASSUMED]

**Research date:** 2026-04-30  
**Valid until:** 2026-05-30 for codebase/architecture mapping; re-check package versions and local environment after 30 days. [ASSUMED]
