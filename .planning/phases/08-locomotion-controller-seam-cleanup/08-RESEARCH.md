# Phase 8: locomotion-controller-seam-cleanup - Research

**Researched:** 2026-05-02  
**Domain:** Python locomotion controller registry/dispatch seam cleanup, multi-robot bridge control application, and placeholder controller metadata  
**Confidence:** HIGH for codebase-local scope and tests; MEDIUM for whether the final implementation should unify MultiRobotBridge with the registry or document a deliberate platform-runtime boundary

## User Constraints

No Phase 8 CONTEXT.md exists for this run; there are no discuss-phase locked decisions to copy. [VERIFIED: `gsd-sdk query init.phase-op "8"` returned `has_context: false`]

Use roadmap, requirements, state, audit findings, and current code patterns as phase inputs. [VERIFIED: user prompt; `.planning/ROADMAP.md:220-229`; `.planning/REQUIREMENTS.md:83-95`; `.planning/STATE.md:74-78`; `.planning/v4.0-MILESTONE-AUDIT.md:137-141`]

## Project Constraints (from CLAUDE.md)

- `/home/prannayag/pragnition/robotics/argus/CLAUDE.md` contains only placeholder project instructions and no actionable coding, testing, or security directives. [VERIFIED: `CLAUDE.md:1-3`]
- `/home/prannayag/pragnition/robotics/argus/.claude/CLAUDE.md` contains only placeholder project instructions and no actionable coding, testing, or security directives. [VERIFIED: project context reminder]
- Project skill discovery found `.claude/skills/desloppify`; it is a code-health scanner/technical-debt workflow, but it requires its own scan/plan/execute loop and is not directly required for this targeted Phase 8 planning pass. [VERIFIED: `.claude/skills/desloppify/SKILL.md:1-9`; `.claude/skills/desloppify/SKILL.md:16-21`; `.claude/skills/desloppify/SKILL.md:28-47`]
- Do not use `--runner codex` for desloppify workflows if they are invoked later; the project skill overlay says to use Claude subagents exclusively. [VERIFIED: `.claude/skills/desloppify/SKILL.md:285-296`]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-CTRL-04 | Multi-robot and single-robot bridges share the same controller/action abstraction where practical, so comparison logic is not duplicated. [VERIFIED: `.planning/REQUIREMENTS.md:25`] | Phase 8 should close the audit advisory that `MultiRobotBridge` still uses `Go2Platform.make_controller()` plus direct actuator writes while `MuJoCoBridge` uses `ControllerRegistry` and `controller_dispatch`. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:104-106`; `.planning/v4.0-MILESTONE-AUDIT.md:139`; `src/bridge/multi_bridge.py:54-56`; `src/bridge/multi_bridge.py:225-231`; `src/bridge/sim_bridge.py:18-23`; `src/bridge/sim_bridge.py:57-58`; `src/bridge/sim_bridge.py:166-172`] |
| LOC-CTRL-03 | Developer can add placeholder adapters for residual policy, direct policy, and future MPC/WBC controllers without modifying the MuJoCo bridge internals. [VERIFIED: `.planning/REQUIREMENTS.md:24`] | Phase 8 should update WBC placeholder metadata so it no longer advertises `torque_or_joint_position` as if it were a v4.0 env action mode, or explicitly mark the WBC action contract as undefined/deferred. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:30-31`; `.planning/v4.0-MILESTONE-AUDIT.md:140`; `src/locomotion/controllers.py:485-488`; `src/locomotion/actions.py:12-15`; `src/locomotion/actions.py:54-63`] |
| LOC-REPORT-02 | Developer can see an explicit comparison matrix explaining which controller families are supported now versus intentionally deferred. [VERIFIED: `.planning/REQUIREMENTS.md:44-45`] | Phase 8 must keep `docs/locomotion-benchmark.md`, registry tests, and controller-family vocabulary aligned for placeholder controller families. [VERIFIED: `.planning/ROADMAP.md:228-229`; `docs/locomotion-benchmark.md:112-124`; `tests/test_locomotion_benchmark_docs.py:58-75`; `tests/locomotion/test_locomotion_controller_registry.py:146-155`] |

</phase_requirements>

## Summary

Phase 8 is a targeted cleanup phase, not a controller-algorithm phase. [VERIFIED: `.planning/ROADMAP.md:220-229`; `.planning/v4.0-MILESTONE-AUDIT.md:137-141`] The audit says all active v4.0 requirements are satisfied, but the milestone remains routed as tech debt because the multi-robot bridge does not fully share the registry/dispatch seam and the WBC placeholder advertises an action-mode vocabulary outside the current environment catalog. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:43-48`; `.planning/v4.0-MILESTONE-AUDIT.md:137-141`]

The current single-robot bridge (`MuJoCoBridge`) owns a registered `analytical_trot` controller and routes buffered velocity through `command_from_velocity()`, `compute_controller_action()`, and `apply_controller_target()`. [VERIFIED: `src/bridge/sim_bridge.py:18-23`; `src/bridge/sim_bridge.py:57-58`; `src/bridge/sim_bridge.py:214-228`; `src/bridge/sim_bridge.py:166-172`] The current multi-robot bridge owns platform-local controllers from `self._platform.make_controller(rid)`, computes platform `RobotCommand` outputs, manually checks only output shape, then writes indexed controls directly. [VERIFIED: `src/bridge/multi_bridge.py:43-56`; `src/bridge/multi_bridge.py:213-231`] The cleanup should either route Go2 multi-robot control through the same registry/dispatch seam where practical, or document and test that `MultiRobotBridge` is deliberately a platform-runtime boundary because it must support non-Go2 platform controllers such as AGIBOT X2. [VERIFIED: `.planning/ROADMAP.md:225-227`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:21-26`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:45-54`; `tests/bridge/test_multi_bridge_platform_selection.py:48-78`]

**Primary recommendation:** Plan one implementation wave that (1) makes the multi-robot Go2 path use shared target validation/indexed application helpers, preferably via a small adapter from `RobotCommand`/`RobotState` to `LocomotionCommand`/observation when platform is Go2, and (2) updates WBC placeholder metadata/docs/tests so WBC is clearly an unavailable future controller with an undefined/deferred action contract rather than a v4.0 env action mode. [VERIFIED: `src/locomotion/controller_dispatch.py:24-111`; `src/bridge/multi_bridge.py:213-231`; `src/locomotion/controllers.py:376-393`; `src/locomotion/controllers.py:485-488`; `docs/locomotion-benchmark.md:112-124`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Multi-robot controller seam | API / Backend | MuJoCo runtime bridge | The bridge converts buffered robot commands into actuator controls and owns `data.ctrl` mutation; shared validation/dispatch belongs below callers and above MuJoCo stepping. [VERIFIED: `src/bridge/multi_bridge.py:202-235`; `src/locomotion/controller_dispatch.py:45-111`] |
| Per-robot control target validation | API / Backend | MuJoCo runtime bridge | `apply_controller_target()` validates target shape, finiteness, index count, duplicates, and bounds before mutating a control sink. [VERIFIED: `src/locomotion/controller_dispatch.py:67-94`; `tests/locomotion/test_controller_dispatch.py:100-150`] |
| Platform-runtime boundary for non-Go2 controllers | API / Backend | Platform abstraction layer | `MultiRobotBridge` constructs a platform from `create_platform()` and supports platform-specific controllers, while ADR-0017 says humanoid walking should stay behind an external walking policy boundary. [VERIFIED: `src/bridge/multi_bridge.py:43-56`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:21-26`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:45-54`] |
| Controller placeholder metadata | Locomotion domain layer | Documentation/tests | `ControllerRegistry.list_controllers()` exposes capability metadata, and docs/tests assert controller-family support/deferred vocabulary. [VERIFIED: `src/locomotion/controllers.py:244-286`; `docs/locomotion-benchmark.md:112-124`; `tests/test_locomotion_benchmark_docs.py:58-75`] |
| Env action-mode catalog | Locomotion domain layer | Evaluation CLI | `available_action_modes()` only returns `joint_position`, `residual_baseline`, and `velocity_command`; evaluation rejects unsupported or non-runnable action modes before env construction. [VERIFIED: `src/locomotion/actions.py:12-15`; `src/locomotion/actions.py:54-63`; `src/locomotion/evaluation.py:155-168`] |
| Controller-family comparison docs | Documentation | Tests | `docs/locomotion-benchmark.md` is the user-facing matrix for supported/deferred controller families, and Markdown guard tests enforce required tokens. [VERIFIED: `docs/locomotion-benchmark.md:112-124`; `tests/test_locomotion_benchmark_docs.py:58-75`] |

## Standard Stack

### Core

| Library / Pattern | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python project code | `requires-python >=3.10,<3.13` in project metadata; local shell is Python 3.14.4, which is outside the project-supported range. [VERIFIED: `pyproject.toml:5`; local probe `python --version`] | Implement bridge/controller cleanup in existing Python modules. [VERIFIED: `src/bridge/multi_bridge.py`; `src/locomotion/controllers.py`; `src/locomotion/controller_dispatch.py`] | The locomotion harness, bridges, and tests are Python code. [VERIFIED: `pyproject.toml:1-17`; `tests/locomotion/test_controller_dispatch.py`; `tests/bridge/test_multi_bridge.py`] |
| `numpy` | Project declares `numpy>=1.26.0`; local import probe failed before reaching NumPy because `mujoco` is missing in Python 3.14 environment. [VERIFIED: `pyproject.toml:6-16`; local package probe] | 12-element controller target arrays, robot state arrays, command buffers, and control sink writes. [VERIFIED: `src/locomotion/controllers.py:120-135`; `src/locomotion/controller_dispatch.py:14-20`; `src/bridge/multi_bridge.py:12`; `src/bridge/multi_bridge.py:225-231`] | Existing locomotion and bridge code is NumPy-based. [VERIFIED: `src/locomotion/actions.py:6-8`; `src/bridge/multi_bridge.py:12`; `src/bridge/sim_bridge.py:14`] |
| Project-local `ControllerRegistry` | Current implementation in `src/locomotion/controllers.py`. [VERIFIED: `src/locomotion/controllers.py:229-345`] | Registry/metadata source for controller ids, availability, capabilities, parameter hashes, and placeholders. [VERIFIED: `src/locomotion/controllers.py:244-286`; `tests/locomotion/test_locomotion_controller_registry.py:88-155`] | The single-robot bridge and env already use it for controller selection/metadata. [VERIFIED: `src/bridge/sim_bridge.py:23`; `src/bridge/sim_bridge.py:57-58`; `src/locomotion/env.py:435-448`] |
| Project-local `controller_dispatch` helpers | Current implementation in `src/locomotion/controller_dispatch.py`. [VERIFIED: `src/locomotion/controller_dispatch.py:1-111`] | Convert velocity buffers to `LocomotionCommand`, compute validated controller actions, and apply targets to full or indexed `data.ctrl` sinks. [VERIFIED: `src/locomotion/controller_dispatch.py:24-111`] | Tests already prove indexed writes and mutation-before-validation guards for multi-robot-style sinks. [VERIFIED: `tests/locomotion/test_controller_dispatch.py:85-150`; `tests/locomotion/test_controller_dispatch.py:167-183`] |
| `pytest` | Local pytest is 9.0.2; project declares `pytest>=8.0.0` in dev dependencies. [VERIFIED: local probe `pytest --version`; `pyproject.toml:41-45`] | Fast unit coverage for registry metadata, dispatch helpers, multi-bridge behavior, docs guards, and CLI action-mode metadata. [VERIFIED: `tests/locomotion/test_locomotion_controller_registry.py`; `tests/locomotion/test_controller_dispatch.py`; `tests/bridge/test_multi_bridge.py`; `tests/test_locomotion_benchmark_docs.py`] | Existing validation gates are pytest-based. [VERIFIED: `.planning/STATE.md:35-39`; `pyproject.toml:47-53`] |

### Supporting

| Library / Pattern | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mujoco` | Project declares `mujoco>=3.0.0`; local Python 3.14 environment does not have `mujoco` installed. [VERIFIED: `pyproject.toml:6-16`; local package probe] | Runtime physics stepping and `data.ctrl` mutation in bridge integration tests. [VERIFIED: `src/bridge/multi_bridge.py:80-179`; `src/bridge/multi_bridge.py:202-235`] | Do not require MuJoCo for all unit tests; existing tests use monkeypatched fake `mujoco` modules for fast bridge behavior coverage. [VERIFIED: `tests/bridge/test_multi_bridge.py:104-166`; `tests/bridge/test_multi_bridge.py:170-199`] |
| `gymnasium` | Project declares `gymnasium>=1.3.0`; local Python 3.14 probe did not import it because `mujoco` import failed first. [VERIFIED: `pyproject.toml:6-16`; local package probe] | Env action-mode catalog and `ArgusGo2Env` API context. [VERIFIED: `src/locomotion/actions.py:6-8`; `src/locomotion/env.py:29-53`] | Phase 8 should not add new Gymnasium behavior unless WBC metadata changes require env action-mode vocabulary tests. [VERIFIED: `.planning/ROADMAP.md:228-229`; `src/locomotion/actions.py:54-63`] |
| Markdown content guards | Project-local pytest pattern. [VERIFIED: `tests/test_locomotion_benchmark_docs.py:1-130`] | Keep docs matrix and controller registry action-mode vocabulary in sync. [VERIFIED: `tests/test_locomotion_benchmark_docs.py:91-106`] | Add/extend docs guards for WBC once metadata vocabulary changes. [VERIFIED: `.planning/ROADMAP.md:228-229`; `src/locomotion/controllers.py:485-488`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Registry/dispatch unification for Go2 multi-robot | Explicit platform-runtime boundary with tests/docs | Boundary documentation is acceptable if unification is impractical, but the success criteria require the boundary be deliberate and tested rather than accidental drift. [VERIFIED: `.planning/ROADMAP.md:225-227`; `.planning/v4.0-MILESTONE-AUDIT.md:139`] |
| Change WBC action mode to an existing env action mode | Add `torque_or_joint_position` to `available_action_modes()` | Adding a new env action mode would contradict Phase 7’s explicit evaluator contract and imply runnable/action-space support the milestone does not have. [VERIFIED: `src/locomotion/actions.py:54-63`; `src/locomotion/evaluation.py:155-168`; `.planning/ROADMAP.md:228-229`] |
| Leave WBC metadata as-is and rely on `available=False` | Make unavailable metadata explicit about undefined/deferred action contract | `available=False` prevents runtime construction, but the audit identified metadata/docs confusion as tech debt; Phase 8 exists specifically to remove that ambiguity. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:30-31`; `.planning/v4.0-MILESTONE-AUDIT.md:140`] |

**Installation:**
```bash
# No new packages should be required for Phase 8.
# Use the project-supported Python 3.10-3.12 environment for MuJoCo/Gymnasium tests.
uv sync --extra dev
```
[VERIFIED: `pyproject.toml:5-16`; `pyproject.toml:41-45`; local probe `python --version`]

**Version verification:** No npm packages apply. Python dependency constraints were verified from `pyproject.toml`; local pytest/uv/Python availability was probed on 2026-05-02. [VERIFIED: `pyproject.toml:5-16`; local environment probe]

## Architecture Patterns

### System Architecture Diagram

```mermaid
flowchart TD
  A[MultiRobotBridge.start/step] --> B[Per-robot RobotCommand buffer]
  B --> C{Platform/runtime boundary?}
  C -->|Go2 practical unification| D[Adapt RobotCommand to LocomotionCommand]
  D --> E[ControllerRegistry analytical_trot per robot]
  E --> F[compute_controller_action]
  F --> G[apply_controller_target with robot ctrl_indices]
  C -->|Non-Go2 platform boundary| H[Platform make_controller output]
  H --> I[Shared finite/shape/index validation before ctrl writes]
  I --> G
  G --> J[MuJoCo data.ctrl indexed mutation]
  J --> K[mj_step loop owned by bridge]
  K --> L[dict[str, SensorFrame] return]
  M[ControllerRegistry WBC placeholder] --> N{action contract defined?}
  N -->|No v4.0 contract| O[metadata/docs say undefined/deferred]
  N -->|Existing env mode only| P[metadata must match available_action_modes]
  O --> Q[registry + docs guard tests]
  P --> Q
```

The important control-flow invariant is that invalid controller outputs must fail before any `data.ctrl` mutation, including indexed multi-robot writes. [VERIFIED: `src/locomotion/controller_dispatch.py:67-94`; `tests/locomotion/test_controller_dispatch.py:109-150`]

### Recommended Project Structure

```text
src/
├── bridge/
│   └── multi_bridge.py              # close or document/test the registry/dispatch seam gap [VERIFIED: `src/bridge/multi_bridge.py:23-61`; `.planning/v4.0-MILESTONE-AUDIT.md:139`]
└── locomotion/
    ├── controllers.py               # WBC placeholder action contract metadata [VERIFIED: `src/locomotion/controllers.py:376-393`; `src/locomotion/controllers.py:485-488`]
    ├── controller_dispatch.py       # shared validation/indexed application helpers [VERIFIED: `src/locomotion/controller_dispatch.py:24-111`]
    └── actions.py                   # canonical v4.0 env action-mode catalog [VERIFIED: `src/locomotion/actions.py:12-15`; `src/locomotion/actions.py:54-63`]

tests/
├── bridge/
│   ├── test_multi_bridge.py         # add indexed validation/no-mutation regressions if using seam [VERIFIED: existing `tests/bridge/test_multi_bridge.py:170-199`]
│   └── test_multi_bridge_platform_selection.py  # add boundary regression if documenting platform runtime seam [VERIFIED: existing `tests/bridge/test_multi_bridge_platform_selection.py:48-78`]
├── locomotion/
│   ├── test_controller_dispatch.py  # existing shared helper behavior [VERIFIED: `tests/locomotion/test_controller_dispatch.py:1-206`]
│   └── test_locomotion_controller_registry.py  # add WBC placeholder vocabulary assertions [VERIFIED: `tests/locomotion/test_locomotion_controller_registry.py:129-155`]
└── test_locomotion_benchmark_docs.py # add WBC docs/metadata drift guard [VERIFIED: `tests/test_locomotion_benchmark_docs.py:58-75`; `tests/test_locomotion_benchmark_docs.py:91-106`]
```

### Pattern 1: Shared validation before indexed control writes

**What:** Route per-robot control targets through `apply_controller_target(data, target, ctrl_indices=...)` or an equivalent shared helper before writing to `data.ctrl`. [VERIFIED: `src/locomotion/controller_dispatch.py:67-94`]

**When to use:** Use it in the multi-robot step path whenever the output is a Go2 12-joint position target or a platform controller output that can be validated against the platform actuator count before indexed mutation. [VERIFIED: `src/bridge/multi_bridge.py:129-139`; `src/bridge/multi_bridge.py:225-231`; `src/bridge/platforms/types.py` indirectly used by `tests/bridge/test_multi_bridge_platform_selection.py:9-15`]

**Example:**
```python
# Source: src/locomotion/controller_dispatch.py:67-94
validated = apply_controller_target(
    self._data,
    target,
    ctrl_indices=self._ctrl_indices[robot_id],
)
```

### Pattern 2: Preserve platform abstraction while eliminating accidental duplication

**What:** Keep `MultiRobotBridge` public lifecycle and `dict[str, SensorFrame]` return contract, but make its control application either use the shared registry/dispatch path for Go2 or a documented platform-runtime boundary for other platforms. [VERIFIED: `src/bridge/multi_bridge.py:23-32`; `src/bridge/multi_bridge.py:202-315`; `.planning/ROADMAP.md:225-227`]

**When to use:** Use this when planner decides whether LOC-CTRL-04 is satisfied by practical unification or by a deliberate boundary for platform-local controllers. [VERIFIED: `.planning/REQUIREMENTS.md:25`; `.planning/v4.0-MILESTONE-AUDIT.md:139`]

**Example:**
```python
# Source pattern: src/bridge/multi_bridge.py:213-231 and src/locomotion/controller_dispatch.py:67-94
for robot_id in self._config.robot_ids:
    command = self._commands[robot_id]
    state = self._platform.extract_state(self._model, self._data, self._qpos_starts[robot_id], sim_time)
    target = self._controllers[robot_id].compute(command, state, self._dt)
    apply_controller_target(self._data, target, ctrl_indices=self._ctrl_indices[robot_id])
```

### Pattern 3: Placeholder metadata must not imply unsupported env action modes

**What:** Keep WBC discoverable and unavailable, but make its `action_mode` capability either an existing env action mode or an explicit non-env value such as `undefined_deferred` paired with docs/tests that say it is not an env action mode. [VERIFIED: `src/locomotion/controllers.py:467-488`; `src/locomotion/actions.py:54-63`; `.planning/ROADMAP.md:228-229`]

**When to use:** Use this for WBC and any future placeholder whose actuator/action contract is not defined in v4.0. [VERIFIED: `.planning/REQUIREMENTS.md:50-57`; `.planning/REQUIREMENTS.md:61-65`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:55-62`]

**Example:**
```python
# Source pattern: src/locomotion/controllers.py:376-393
# Planner should require a registry test that WBC either:
# 1. uses an existing available_action_modes() value, or
# 2. is documented as undefined/deferred and unavailable.
```

### Anti-Patterns to Avoid

- **Adding `torque_or_joint_position` to the v4.0 env action-mode catalog just to silence a test:** That would create a new public action space/evaluator contract with no implementation, directly repeating the audit problem. [VERIFIED: `src/locomotion/actions.py:54-63`; `src/locomotion/evaluation.py:155-168`; `.planning/v4.0-MILESTONE-AUDIT.md:30-31`]
- **Writing `data.ctrl` inside the multi-robot loop before all validation succeeds:** Existing shared helper tests require no mutation on invalid target, bad indices, duplicate indices, or out-of-range indices. [VERIFIED: `tests/locomotion/test_controller_dispatch.py:109-150`; `src/locomotion/controller_dispatch.py:67-94`]
- **Refactoring platform-specific controller health/status semantics into the benchmark registry without a deliberate design:** `MultiRobotBridge` updates `RobotRuntimeStatus` from platform health, collision summaries, and command state; that is platform-runtime behavior, not just benchmark controller metadata. [VERIFIED: `src/bridge/multi_bridge.py:263-274`; `src/bridge/multi_bridge.py:339-349`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:45-54`]
- **Implementing WBC, MPC, RL, ROS, or hardware behavior in Phase 8:** v4.0 out-of-scope requirements explicitly defer these families. [VERIFIED: `.planning/REQUIREMENTS.md:50-67`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:53-62`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Indexed `data.ctrl` validation | A second shape/finite/index loop inside `MultiRobotBridge` | `apply_controller_target(..., ctrl_indices=...)` | Existing helper validates exact target shape, finite values, index count, duplicate indices, and range before mutation. [VERIFIED: `src/locomotion/controller_dispatch.py:67-94`; `tests/locomotion/test_controller_dispatch.py:85-150`] |
| Controller discovery metadata | A separate multi-bridge-only controller registry | `ControllerRegistry.list_controllers()` | Registry already exposes controller ids, availability, capability metadata, parameter schemas, and unavailable reasons. [VERIFIED: `src/locomotion/controllers.py:229-345`; `tests/locomotion/test_locomotion_controller_registry.py:88-155`] |
| Env action-mode vocabulary | String literals scattered across docs/tests | `src/locomotion/actions.py` constants and `available_action_modes()` | The env action-mode catalog is centralized and already used by evaluation validation/tests. [VERIFIED: `src/locomotion/actions.py:12-15`; `src/locomotion/actions.py:61-63`; `src/locomotion/evaluation.py:155-168`] |
| Docs drift detection | Manual checklist only | Pytest Markdown guards | Existing docs tests already assert controller-family matrix content and residual placeholder metadata alignment. [VERIFIED: `tests/test_locomotion_benchmark_docs.py:58-75`; `tests/test_locomotion_benchmark_docs.py:91-106`] |
| Future WBC contract | A fake torque/joint hybrid action space | Deferred placeholder metadata and explicit docs | v4.0 has position-servo benchmark surfaces and no torque/WBC infrastructure. [VERIFIED: `docs/locomotion-benchmark.md:45-54`; `.planning/REQUIREMENTS.md:61-65`; `.planning/v4.0-MILESTONE-AUDIT.md:140`] |

**Key insight:** The phase is about making boundaries honest: use existing shared validation where it fits, and if multi-platform runtime constraints prevent complete registry unification, write tests/docs that make that boundary explicit rather than leaving accidental divergence. [VERIFIED: `.planning/ROADMAP.md:225-229`; `.planning/v4.0-MILESTONE-AUDIT.md:137-141`]

## Common Pitfalls

### Pitfall 1: Treating LOC-CTRL-04 as requiring platform abstraction deletion

**What goes wrong:** The planner might force every `MultiRobotBridge` platform controller into `ControllerRegistry`, breaking non-Go2 platform semantics and runtime health reporting. [VERIFIED: `src/bridge/multi_bridge.py:43-56`; `src/bridge/multi_bridge.py:263-274`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:45-54`]  
**Why it happens:** The audit says the multi bridge does not fully share the registry/dispatch seam, but the requirement contains the qualifier “where practical.” [VERIFIED: `.planning/REQUIREMENTS.md:25`; `.planning/v4.0-MILESTONE-AUDIT.md:139`]  
**How to avoid:** Plan either Go2-only seam unification or an explicit platform-runtime boundary with tests proving shared validation still protects indexed writes. [VERIFIED: `.planning/ROADMAP.md:225-227`; `src/locomotion/controller_dispatch.py:67-94`]  
**Warning signs:** Plan tasks say “replace `make_controller()` globally” without mentioning `RobotRuntimeStatus`, platform health, or AGIBOT X2 boundary. [VERIFIED: `src/bridge/multi_bridge.py:55-56`; `src/bridge/multi_bridge.py:263-274`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:15-22`]

### Pitfall 2: Preserving output shape checks but losing no-mutation guarantees

**What goes wrong:** Multi-bridge code validates target shape after computing output but still writes some controls before detecting later invalid indices/values. [VERIFIED: current direct write loop in `src/bridge/multi_bridge.py:225-231`; shared helper behavior in `src/locomotion/controller_dispatch.py:67-94`]  
**Why it happens:** A loop that writes per actuator is tempting and readable, but it does not automatically provide all-or-nothing validation. [VERIFIED: `src/bridge/multi_bridge.py:225-231`; `tests/locomotion/test_controller_dispatch.py:109-150`]  
**How to avoid:** Use `apply_controller_target()` for each robot, and add a bridge-level regression with a fake data sink proving invalid multi-robot targets leave `ctrl` unchanged. [VERIFIED: `src/locomotion/controller_dispatch.py:67-94`; `tests/locomotion/test_controller_dispatch.py:109-150`]  
**Warning signs:** New tests only assert `RuntimeError` on wrong shape but do not assert `np.testing.assert_allclose(data.ctrl, before)`. [VERIFIED: `tests/locomotion/test_controller_dispatch.py:109-121`; `tests/locomotion/test_controller_dispatch.py:123-150`]

### Pitfall 3: Fixing WBC by overclaiming `joint_position`

**What goes wrong:** Changing WBC metadata to `joint_position` can make metadata vocabulary legal but may imply a defined WBC action contract that does not actually exist. [VERIFIED: `src/locomotion/controllers.py:481-488`; `.planning/ROADMAP.md:228-229`]  
**Why it happens:** `joint_position` is an existing env action mode, so it is mechanically easy to use. [VERIFIED: `src/locomotion/actions.py:12-15`; `src/locomotion/actions.py:54-63`]  
**How to avoid:** If WBC’s action contract is not defined in v4.0, prefer metadata/docs that explicitly say `action_contract: undefined/deferred` or equivalent, while keeping `available=False`. [VERIFIED: `.planning/ROADMAP.md:228-229`; `.planning/v4.0-MILESTONE-AUDIT.md:140`; `src/locomotion/controllers.py:446-465`]  
**Warning signs:** Docs start saying WBC has a runnable joint-position env seam without mentioning torque/control allocation assumptions and deferred status. [VERIFIED: `docs/locomotion-benchmark.md:112-124`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:55-62`]

### Pitfall 4: Forgetting CLI/evaluation action-mode rejection semantics

**What goes wrong:** WBC metadata/docs changes reintroduce a string that `argus eval-locomotion` accepts incorrectly or reports in completed artifacts. [VERIFIED: Phase 7 success criteria in `.planning/ROADMAP.md:203-207`; `src/locomotion/evaluation.py:155-168`]  
**Why it happens:** Registry metadata, env action modes, and evaluator-runnable modes are related but not identical. [VERIFIED: `src/locomotion/controllers.py:356-393`; `src/locomotion/actions.py:54-63`; `src/locomotion/evaluation.py:155-168`]  
**How to avoid:** Keep tests that unknown action modes fail before env construction and completed velocity runs record only `velocity_command`. [VERIFIED: `tests/locomotion/test_locomotion_evaluation_runner.py:170-210`; `tests/locomotion/test_locomotion_evaluation_exports.py:230-262`]  
**Warning signs:** A docs/registry change requires relaxing Phase 7 tests. [VERIFIED: `tests/locomotion/test_locomotion_evaluation_runner.py:190-210`; `tests/locomotion/test_locomotion_evaluation_exports.py:252-262`]

## Code Examples

Verified patterns from project sources:

### Indexed control application with pre-mutation validation

```python
# Source: src/locomotion/controller_dispatch.py:67-94
validated = apply_controller_target(fake_data, target, ctrl_indices=ctrl_indices)
```

Use this pattern in `MultiRobotBridge` instead of directly assigning `self._data.ctrl[act_id] = ctrl[i]` in a loop. [VERIFIED: `src/bridge/multi_bridge.py:225-231`; `src/locomotion/controller_dispatch.py:67-94`]

### Registry placeholder availability semantics

```python
# Source: src/locomotion/controllers.py:446-465
class _UnavailableControllerBase:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise UnavailableControllerError(self.UNAVAILABLE_REASON)

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return False, cls.UNAVAILABLE_REASON
```

Keep WBC unavailable and fail at selection time; do not create a WBC object that fails later in `compute()`. [VERIFIED: `src/locomotion/controllers.py:446-465`; `tests/locomotion/test_locomotion_controller_registry.py:129-144`]

### Docs guard for registry/docs action-mode alignment

```python
# Source: tests/test_locomotion_benchmark_docs.py:91-106
entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
action_mode = entries["residual_policy"]["capabilities"]["action_mode"]
assert action_mode in available_action_modes()
```

Add an analogous WBC guard, but decide whether the assertion should be “in `available_action_modes()`” or “explicitly marked undefined/deferred and not an env mode” based on the chosen metadata design. [VERIFIED: `tests/test_locomotion_benchmark_docs.py:91-106`; `.planning/ROADMAP.md:228-229`]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct bridge gait/control logic | Single bridge and env use `ControllerRegistry` plus `controller_dispatch`; multi bridge still uses platform-local controllers and direct indexed writes. [VERIFIED: `src/bridge/sim_bridge.py:18-23`; `src/bridge/sim_bridge.py:57-58`; `src/bridge/multi_bridge.py:54-56`; `src/bridge/multi_bridge.py:225-231`] | Phase 2 completed 2026-04-30. [VERIFIED: `.planning/STATE.md:69-71`; `.planning/ROADMAP.md:62-87`] | Phase 8 should remove or bound the remaining inconsistency. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:139`; `.planning/ROADMAP.md:225-227`] |
| Placeholder residual metadata drift | Residual policy now advertises `residual_baseline` and docs/tests guard it. [VERIFIED: `src/locomotion/controllers.py:467-470`; `tests/locomotion/test_locomotion_controller_registry.py:146-155`; `tests/test_locomotion_benchmark_docs.py:91-106`] | Phase 5 gap closure and Phase 7 action-mode alignment. [VERIFIED: `.planning/ROADMAP.md:169-170`; `.planning/ROADMAP.md:198-217`] | WBC needs the same level of vocabulary discipline. [VERIFIED: `.planning/ROADMAP.md:228-229`; `src/locomotion/controllers.py:485-488`] |
| Evaluator accepts all env-supported modes | Evaluator currently runs `velocity_command` and rejects `joint_position`/`residual_baseline` before artifacts. [VERIFIED: `src/locomotion/evaluation.py:155-168`; `tests/locomotion/test_locomotion_evaluation_exports.py:252-262`] | Phase 7 completed 2026-05-02. [VERIFIED: `.planning/ROADMAP.md:198-217`; `.planning/STATE.md:5-8`] | WBC metadata must not undermine the completed action-mode contract. [VERIFIED: `.planning/ROADMAP.md:228-229`] |

**Deprecated/outdated:**
- WBC `action_mode='torque_or_joint_position'` is outdated for v4.0 because it is not in `available_action_modes()` and audit calls it a placeholder metadata debt item. [VERIFIED: `src/locomotion/controllers.py:485-488`; `src/locomotion/actions.py:54-63`; `.planning/v4.0-MILESTONE-AUDIT.md:30-31`; `.planning/v4.0-MILESTONE-AUDIT.md:140`]
- Multi-robot direct control writes are outdated if they bypass shared validation; use shared indexed application or document why the platform runtime boundary must remain. [VERIFIED: `src/bridge/multi_bridge.py:225-231`; `src/locomotion/controller_dispatch.py:67-94`; `.planning/ROADMAP.md:225-227`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No new dependencies should be required for Phase 8. | Standard Stack | If wrong, planner may omit dependency installation tasks. |
| A2 | The best WBC metadata shape is likely an explicit undefined/deferred action contract rather than mapping WBC to `joint_position`. | Summary / Pitfalls | If maintainers prefer legal env-mode-only metadata, planner should update WBC to an existing mode and make docs say it is only a placeholder. |

## Open Questions

1. **Should `MultiRobotBridge` use `ControllerRegistry.create("analytical_trot")` for Go2, or should the platform-local `Go2VelocityController` remain the runtime boundary?**  
   - What we know: `MuJoCoBridge` uses `ControllerRegistry` while `MultiRobotBridge` uses `self._platform.make_controller(rid)`. [VERIFIED: `src/bridge/sim_bridge.py:57-58`; `src/bridge/multi_bridge.py:54-56`]  
   - What's unclear: Whether `Go2VelocityController.compute(RobotCommand, RobotState, dt)` is intended to stay the platform abstraction for swarm/multi-robot runtime even when the underlying behavior resembles the analytical trot. [VERIFIED: `src/bridge/multi_bridge.py:225-231`; `tests/bridge/test_multi_bridge_platform_selection.py:48-78`]  
   - Recommendation: Planner should create tests first that express the chosen boundary: Go2 registry unification if practical, otherwise explicit platform-boundary docs/tests plus shared target validation. [VERIFIED: `.planning/ROADMAP.md:225-227`]

2. **What exact vocabulary should WBC use for an undefined future action contract?**  
   - What we know: `torque_or_joint_position` is not an env action mode and was flagged by audit. [VERIFIED: `src/locomotion/controllers.py:485-488`; `src/locomotion/actions.py:54-63`; `.planning/v4.0-MILESTONE-AUDIT.md:140`]  
   - What's unclear: Whether registry `capabilities["action_mode"]` must always be an env action mode, or can be a sentinel like `undefined_deferred` for unavailable placeholders. [VERIFIED: current tests only enforce residual action-mode membership, not all placeholders; `tests/locomotion/test_locomotion_controller_registry.py:146-155`]  
   - Recommendation: Prefer an explicit `undefined_deferred`/`future_wbc_contract` style value only if docs/tests also state it is not an env action mode; otherwise set WBC to `joint_position` and add a separate capability flag documenting that the WBC contract is deferred. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Running tests and implementation | Available but outside project range | Local `Python 3.14.4`; project requires `>=3.10,<3.13`. [VERIFIED: local probe; `pyproject.toml:5`] | Use `uv` with a supported Python 3.10-3.12 environment. [VERIFIED: `pyproject.toml:5`; local probe `uv 0.10.10`] |
| uv | Project dependency/test environment | Yes | `uv 0.10.10`. [VERIFIED: local probe] | Use an existing supported virtualenv if uv is unavailable. [ASSUMED] |
| pytest | Unit validation | Yes | `pytest 9.0.2`. [VERIFIED: local probe] | Install dev dependencies via `uv sync --extra dev`. [VERIFIED: `pyproject.toml:41-45`] |
| mujoco | Integration tests / real bridge runtime | No in local Python 3.14 probe | Missing module. [VERIFIED: local package probe] | Use fake/monkeypatched bridge unit tests for planner Wave 0; run MuJoCo integration only in supported project env. [VERIFIED: `tests/bridge/test_multi_bridge.py:104-166`; `tests/locomotion/test_argus_go2_env_contract.py:202-209`] |
| gymnasium | Env action-mode import/runtime | Not confirmed in local probe | Probe failed before confirming due to missing `mujoco`. [VERIFIED: local package probe] | Use project-supported uv environment. [VERIFIED: `pyproject.toml:5-16`] |

**Missing dependencies with no fallback:**
- None for Phase 8 planning and fast unit tests, if implementation stays in code/docs/tests and uses monkeypatched bridge tests. [VERIFIED: existing fake-mujoco tests in `tests/bridge/test_multi_bridge.py:104-199`]

**Missing dependencies with fallback:**
- `mujoco` is missing in the local Python 3.14 environment; use fake bridge tests for fast validation and run integration in Python 3.10-3.12 with dependencies installed. [VERIFIED: local package probe; `pyproject.toml:5-16`; `tests/locomotion/test_argus_go2_env_contract.py:202-209`]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 local; project dev dependency declares pytest >=8.0.0. [VERIFIED: local probe; `pyproject.toml:41-45`] |
| Config file | `pyproject.toml` contains pytest markers; no separate pytest.ini was read in this session. [VERIFIED: `pyproject.toml:47-53`] |
| Quick run command | `uv run python -m pytest tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/test_locomotion_benchmark_docs.py -q` [VERIFIED: file paths read in this session] |
| Full suite command | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/test_locomotion_benchmark_docs.py -q` [VERIFIED: `.planning/STATE.md:35-39`; file paths read in this session] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOC-CTRL-04 | Multi-robot control application uses shared validation/indexed application, or an explicit tested platform-runtime boundary. [VERIFIED: `.planning/ROADMAP.md:225-227`] | unit / bridge fake-runtime | `uv run python -m pytest tests/bridge/test_multi_bridge.py tests/locomotion/test_controller_dispatch.py -q` | Existing files yes; new cases needed. [VERIFIED: `tests/bridge/test_multi_bridge.py`; `tests/locomotion/test_controller_dispatch.py`] |
| LOC-CTRL-04 | Invalid multi-robot controller outputs do not mutate `data.ctrl`. [VERIFIED: `.planning/ROADMAP.md:226-227`; `src/locomotion/controller_dispatch.py:67-94`] | unit | `uv run python -m pytest tests/bridge/test_multi_bridge.py::test_multi_bridge_rejects_invalid_controller_output_without_mutating_ctrl -q` | Not currently present; Wave 0 add. [VERIFIED: read `tests/bridge/test_multi_bridge.py:1-284`] |
| LOC-CTRL-03 | WBC placeholder metadata no longer advertises an unsupported v4.0 env action mode without explicit deferred vocabulary. [VERIFIED: `.planning/ROADMAP.md:228-229`] | unit | `uv run python -m pytest tests/locomotion/test_locomotion_controller_registry.py -q` | Existing file yes; WBC-specific assertion needed. [VERIFIED: `tests/locomotion/test_locomotion_controller_registry.py:129-155`] |
| LOC-REPORT-02 | Controller-family docs and registry tests agree on WBC placeholder vocabulary. [VERIFIED: `.planning/ROADMAP.md:228-229`] | docs guard | `uv run python -m pytest tests/test_locomotion_benchmark_docs.py -q` | Existing file yes; WBC-specific guard needed. [VERIFIED: `tests/test_locomotion_benchmark_docs.py:58-75`; `tests/test_locomotion_benchmark_docs.py:91-106`] |
| LOC-REPORT-02 | Phase 7 evaluator action-mode rejection remains intact after metadata vocabulary changes. [VERIFIED: `.planning/ROADMAP.md:203-207`; `.planning/ROADMAP.md:228-229`] | unit | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py::test_unknown_action_mode_fails_before_env_construction tests/locomotion/test_locomotion_evaluation_runner.py::test_unsupported_action_modes_fail_before_env_construction -q` | Existing file yes. [VERIFIED: `tests/locomotion/test_locomotion_evaluation_runner.py` grep results] |

### Sampling Rate

- **Per task commit:** `uv run python -m pytest tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/bridge/test_multi_bridge.py tests/test_locomotion_benchmark_docs.py -q` [VERIFIED: file paths read in this session]
- **Per wave merge:** `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/test_locomotion_benchmark_docs.py -q` [VERIFIED: `.planning/STATE.md:35-39`; file paths read in this session]
- **Phase gate:** Full suite green before `/gsd-verify-work`; if local Python remains 3.14 without MuJoCo, record supported-env limitation and run fake/fast tests locally. [VERIFIED: `pyproject.toml:5`; local package probe; `.planning/config.json:7-12`]

### Wave 0 Gaps

- [ ] `tests/bridge/test_multi_bridge.py` — add a fake-runtime regression proving invalid per-robot output fails before mutating `data.ctrl` for indexed multi-robot application. [VERIFIED: existing file lacks such a test after read through line 284]
- [ ] `tests/bridge/test_multi_bridge.py` or `tests/bridge/test_multi_bridge_platform_selection.py` — add a regression that states the chosen Go2 unification vs platform-runtime boundary. [VERIFIED: `.planning/ROADMAP.md:225-227`; existing platform-selection tests in `tests/bridge/test_multi_bridge_platform_selection.py:48-78`]
- [ ] `tests/locomotion/test_locomotion_controller_registry.py` — add WBC placeholder metadata vocabulary assertion. [VERIFIED: existing residual-only action-mode vocabulary assertion in `tests/locomotion/test_locomotion_controller_registry.py:146-155`]
- [ ] `tests/test_locomotion_benchmark_docs.py` — add docs/registry guard for WBC placeholder vocabulary. [VERIFIED: existing residual-only docs alignment in `tests/test_locomotion_benchmark_docs.py:91-106`]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth boundary is touched by Phase 8. [VERIFIED: phase scope `.planning/ROADMAP.md:220-229`] |
| V3 Session Management | no | No session state is touched by Phase 8. [VERIFIED: phase scope `.planning/ROADMAP.md:220-229`] |
| V4 Access Control | no | No authorization boundary is touched by bridge/controller metadata cleanup. [VERIFIED: phase scope `.planning/ROADMAP.md:220-229`] |
| V5 Input Validation | yes | Validate controller outputs before `data.ctrl` mutation; keep action-mode validation fail-fast. [VERIFIED: `src/locomotion/controller_dispatch.py:67-94`; `src/locomotion/evaluation.py:155-168`] |
| V6 Cryptography | no | No cryptographic behavior is touched by Phase 8. [VERIFIED: phase scope `.planning/ROADMAP.md:220-229`] |

### Known Threat Patterns for Python simulation/controller seam

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Non-finite controller output mutates physics controls | Tampering | Validate target shape and finiteness before writing to `data.ctrl`. [VERIFIED: `src/locomotion/controllers.py:120-135`; `src/locomotion/controller_dispatch.py:67-94`] |
| Bad actuator indices corrupt another robot’s controls | Tampering | Validate ctrl index count, duplicate indices, and range before mutation. [VERIFIED: `src/locomotion/controller_dispatch.py:76-94`; `tests/locomotion/test_controller_dispatch.py:123-150`] |
| Metadata says a controller/action mode is runnable when it is deferred | Spoofing / Information disclosure by misleading artifacts | Keep placeholders `available=False`, fail at selection time, and align docs/registry/evaluator tests. [VERIFIED: `src/locomotion/controllers.py:446-465`; `tests/locomotion/test_locomotion_controller_registry.py:129-144`; `src/locomotion/evaluation.py:155-168`] |
| Evaluation artifacts record rejected action modes | Repudiation | Phase 7 tests assert rejected action modes write no artifacts and completed runs record only actual action mode metadata. [VERIFIED: `tests/locomotion/test_locomotion_evaluation_exports.py:230-262`] |

## Sources

### Primary (HIGH confidence)

- `.planning/ROADMAP.md` — Phase 8 goal, requirements, gap closure, and success criteria. [VERIFIED: `.planning/ROADMAP.md:220-229`]
- `.planning/REQUIREMENTS.md` — LOC-CTRL-03, LOC-CTRL-04, LOC-REPORT-02, future/out-of-scope controller requirements. [VERIFIED: `.planning/REQUIREMENTS.md:20-25`; `.planning/REQUIREMENTS.md:42-46`; `.planning/REQUIREMENTS.md:50-67`; `.planning/REQUIREMENTS.md:83-95`]
- `.planning/STATE.md` — v4.0 state, phase position, regression gate reference, and pending Phase 8 task. [VERIFIED: `.planning/STATE.md:27-39`; `.planning/STATE.md:74-78`]
- `.planning/v4.0-MILESTONE-AUDIT.md` — explicit tech debt items for multi-robot controller seam and WBC placeholder metadata. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:27-35`; `.planning/v4.0-MILESTONE-AUDIT.md:137-141`]
- `src/bridge/multi_bridge.py` — current multi-robot platform controller and direct control write path. [VERIFIED: `src/bridge/multi_bridge.py:43-56`; `src/bridge/multi_bridge.py:213-231`]
- `src/bridge/sim_bridge.py` — current single-robot registry/dispatch path. [VERIFIED: `src/bridge/sim_bridge.py:18-23`; `src/bridge/sim_bridge.py:57-58`; `src/bridge/sim_bridge.py:214-228`]
- `src/locomotion/controllers.py` — controller registry, placeholder capabilities, WBC metadata. [VERIFIED: `src/locomotion/controllers.py:229-345`; `src/locomotion/controllers.py:376-393`; `src/locomotion/controllers.py:485-488`]
- `src/locomotion/controller_dispatch.py` — shared command/compute/apply helpers. [VERIFIED: `src/locomotion/controller_dispatch.py:24-111`]
- `src/locomotion/actions.py` — canonical v4.0 env action-mode catalog. [VERIFIED: `src/locomotion/actions.py:12-15`; `src/locomotion/actions.py:54-63`]
- `docs/locomotion-benchmark.md` — current controller-family matrix and action-mode docs. [VERIFIED: `docs/locomotion-benchmark.md:37-43`; `docs/locomotion-benchmark.md:112-124`]
- `tests/locomotion/test_controller_dispatch.py`, `tests/locomotion/test_locomotion_controller_registry.py`, `tests/bridge/test_multi_bridge.py`, `tests/test_locomotion_benchmark_docs.py` — existing test surfaces. [VERIFIED: files read in this session]

### Secondary (MEDIUM confidence)

- `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md` — rationale for platform-local/external walking policy boundary. [VERIFIED: `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:15-26`; `docs/adr/0017-treat-x2-locomotion-as-external-walking-policy-boundary.md:45-54`]
- `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` — rationale for not adding RL/MPC/WBC behavior before benchmark discipline. [VERIFIED: `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:17-21`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:31-41`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md:53-62`]

### Tertiary (LOW confidence)

- None. [VERIFIED: all findings above were read from local project files or local environment probes]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Phase 8 needs no new libraries and uses existing project-local Python modules and pytest tests. [VERIFIED: `pyproject.toml:5-16`; `src/locomotion/controller_dispatch.py`; `tests/locomotion/test_controller_dispatch.py`]
- Architecture: HIGH for the current seam locations; MEDIUM for whether final planning should choose full Go2 registry unification or explicit platform-runtime boundary. [VERIFIED: `src/bridge/sim_bridge.py:57-58`; `src/bridge/multi_bridge.py:54-56`; `.planning/ROADMAP.md:225-227`]
- Pitfalls: HIGH — pitfalls are direct consequences of current audit findings and existing tests. [VERIFIED: `.planning/v4.0-MILESTONE-AUDIT.md:137-141`; `tests/locomotion/test_controller_dispatch.py:109-150`; `tests/locomotion/test_locomotion_evaluation_exports.py:230-262`]

**Research date:** 2026-05-02  
**Valid until:** 2026-06-01, or sooner if Phase 8 implementation changes `src/bridge/multi_bridge.py`, `src/locomotion/controllers.py`, or `src/locomotion/actions.py`. [ASSUMED]
