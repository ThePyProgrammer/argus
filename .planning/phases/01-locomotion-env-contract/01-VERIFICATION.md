---
phase: 01-locomotion-env-contract
verified: 2026-04-30T08:33:12Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 16/16
  gaps_closed:
    - "Code-review blocker fixed: non-plane terrain XML now removes flat benchmark_floor before adding slope or rough-heightfield terrain."
    - "Code-review blocker fixed: joint_position action space now uses per-leg FL/FR/RL/RR Go2 joint bounds."
    - "Code-review blocker fixed: real MuJoCo-backed randomized resets now rebuild model/data instead of reusing stale terrain."
  gaps_remaining: []
  regressions: []
---

# Phase 1: locomotion-env-contract Verification Report

**Phase Goal:** Establish a stable Gymnasium-style benchmark boundary around the existing Go2 MuJoCo locomotion path, including named scenarios, deterministic resets, and action modes.
**Verified:** 2026-04-30T08:33:12Z
**Status:** passed
**Re-verification:** Yes — after final code-review fixes.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ArgusGo2Env.reset(seed=...)` and `ArgusGo2Env.step(action)` return the Gymnasium-style contract: observation, reward, terminated, truncated, and info. | VERIFIED | `src/locomotion/env.py` defines `ArgusGo2Env(gymnasium.Env)`, calls `super().reset(seed=seed)`, returns `(observation, info)` from reset and `(observation, reward, terminated, truncated, info)` from step. Current phase gate passed: `.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` returned `134 passed in 9.51s`. |
| 2 | The named scenario catalog includes at least `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance`, each selectable without changing environment code. | VERIFIED | `src/locomotion/scenarios.py` defines all five keys in `SCENARIOS`; `list_scenarios()` returns sorted catalog keys; `ArgusGo2Env.reset` calls `sample_scenario(self.config.scenario_id, self.np_random, heightfield_size=...)`. Scenario tests cover catalog membership and env reset selection. |
| 3 | Reusing the same seed reproduces robot spawn pose, terrain parameters, command schedule, and disturbance timing; changing the seed changes randomized scenario elements where applicable. | VERIFIED | `sample_scenario` derives spawn pose, terrain, command, and disturbance fields from the provided Gymnasium RNG. `tests/locomotion/test_argus_go2_env_determinism.py` asserts same-seed equality and different-seed variation for rough heightfield and push disturbance. Additional spot-check confirmed rough-heightfield reset with seeds 123 and 456 produced different `heightfield_data`. |
| 4 | Action modes for velocity command, joint-position target, and residual-over-baseline control are selected through environment config while preserving one environment API. | VERIFIED | `src/locomotion/actions.py` defines all three constants, action spaces, and `decode_action`; `src/locomotion/env.py` builds `action_space` from `self.config.action_mode` and one `step(action)` path calls `decode_action(...)` for every mode. Joint-position spot-check confirmed per-leg FL/FR/RL/RR bounds: front thigh high `3.4907`, rear thigh high `4.5379`, rear thigh low `-0.5236`. |
| 5 | Existing non-Gym simulation/web paths still boot, so the benchmark wrapper does not break the C2 runtime. | VERIFIED | Bridge regression tests were included in the current gate: `tests/bridge/test_sim_bridge.py` and `tests/bridge/test_multi_bridge.py` passed as part of `134 passed in 9.51s`. `git diff -- src/bridge/sim_bridge.py src/bridge/multi_bridge.py src/main.py` produced no output. |
| 6 | Developer can instantiate `ArgusGo2Env` with default `ArgusGo2EnvConfig`. | VERIFIED | `ArgusGo2EnvConfig` defaults are present in `src/locomotion/env.py`; `tests/locomotion/test_argus_go2_env_contract.py` imports and instantiates the default env/config and checks default model-dir resolution. |
| 7 | Unknown scenario names fail with `ValueError` listing available named scenarios. | VERIFIED | `sample_scenario` rejects ids not in `SCENARIOS` with `ValueError(... Available: {list_scenarios()})`; tests assert every required scenario id appears in the error. |
| 8 | Invalid action shape or NaN action raises `ValueError` before state advances. | VERIFIED | `decode_action` enforces exact shape, finite values, and bounds. `ArgusGo2Env.step` computes scheduled non-velocity command in a local variable, calls `decode_action(...)`, and only then commits `_command`, `_previous_action`, and `_step_count`. Regression test `test_env_rejects_invalid_non_velocity_action_after_schedule_advances_without_state_change` covers joint and residual modes after schedule advancement. |
| 9 | Step info reports selected action mode and sampled reproducibility metadata. | VERIFIED | `_info()` returns `seed`, `scenario_id`, `action_mode`, `spawn_pose`, `sampled_parameters`, `command_schedule`, `disturbance_schedule`, `step_count`, `sim_time`, and `active_push`; tests assert metadata in reset and step info. |
| 10 | `ArgusGo2Env` can build a MuJoCo model for each named scenario when MuJoCo and supported Python are available. | VERIFIED | `_try_initialize_mujoco` builds XML via `build_scenario_xml` and calls `mujoco.MjModel.from_xml_string`; integration-gated tests reset/close every named scenario when MuJoCo is available. |
| 11 | Scenario XML generation does not modify source Go2 XML on disk. | VERIFIED | `build_scenario_xml` reads `go2.xml`, calls `patch_actuators_to_position`, mutates parsed XML in memory, and tests compare `go2.xml` contents before and after generation. |
| 12 | Low friction, slope, rough heightfield, and push disturbance have concrete MJCF/runtime representations. | VERIFIED | `build_scenario_xml` updates flat/low-friction floor, removes the flat benchmark floor for slope and rough heightfield, adds slope marker geometry, adds rough heightfield asset/geom, and keeps push as runtime schedule metadata; `ArgusGo2Env._apply_push_disturbance` applies runtime force through `xfrc_applied`. Spot-check printed `non_plane_floor_removed` for slope and rough-heightfield XML. |
| 13 | Resource-heavy rough heightfield dimensions are bounded by config defaults and validation. | VERIFIED | `ArgusGo2EnvConfig.heightfield_size` defaults to 16; env rejects `heightfield_size > 64`; `sample_scenario` clips rough heightfield size to `[4, 64]`; tests assert bounded metadata. |
| 14 | `ArgusGo2Env.step(action)` decodes controls, writes MuJoCo `ctrl`, advances physics by configured substeps, and returns observation/info from updated state. | VERIFIED | `step` calls `decode_action`, writes `self._data.ctrl[:]`, loops `mujoco.mj_step` for `sim_steps_per_frame`, increments step count, and extracts observation/info. Fake-data test asserts decoder call, ctrl write, step count, and `sim_time` update. |
| 15 | Push disturbance applies deterministic runtime force during active window and clears outside it. | VERIFIED | `_apply_push_disturbance` clears `xfrc_applied`, applies scheduled force inside `[time, time + duration)`, records `active_push`, and returns no active push outside the window. Fake-data test covers active and clear behavior. |
| 16 | Reset applies complete sampled spawn pose including yaw converted to MuJoCo free-joint quaternion. | VERIFIED | `_reset_mujoco_state` writes `qpos[:3]` and `qpos[3:7] = (cos(yaw / 2), 0, 0, sin(yaw / 2))`; contract test asserts `qpos[3:7]` and standing joint pose. |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Runtime Gymnasium dependency | VERIFIED | Contains `gymnasium>=1.3.0`. |
| `src/locomotion/actions.py` | Action mode constants, spaces, validation, decoding | VERIFIED | Exports velocity/joint/residual constants, `available_action_modes`, `build_action_space`, and `decode_action`; validates finite shape/bounds; uses `TrotGaitController.compute` for velocity and residual baseline. Per-leg Go2 joint bounds are present for FL/FR/RL/RR. |
| `src/locomotion/env.py` | Gymnasium env boundary, scenario/action wiring, MuJoCo lifecycle | VERIFIED | Substantive and wired: reset samples scenarios, rebuilds real MuJoCo model/data for randomized terrain, step decodes before mutation, writes controls, advances MuJoCo when present, emits metadata, and closes owned handles. |
| `src/locomotion/observations.py` | Observation space and extraction helpers | VERIFIED | Builds `spaces.Dict` for qpos/qvel/command/previous_action and extracts from MuJoCo data or zero-filled fallback. |
| `src/locomotion/scenarios.py` | Scenario catalog, deterministic sampling, XML builder | VERIFIED | Defines dataclasses/catalog, `list_scenarios`, `sample_scenario`, `build_scenario_xml`, terrain helpers, and asset loading. Non-plane XML removes `benchmark_floor`. |
| `tests/locomotion/test_argus_go2_env_contract.py` | Contract, MuJoCo lifecycle, fake-data behavior tests | VERIFIED | Covers default contract, integration-gated reset/step, randomized-terrain model rebuild, ctrl writes, push force lifecycle, and yaw quaternion reset. |
| `tests/locomotion/test_argus_go2_env_action_modes.py` | Action helper and env integration tests | VERIFIED | Covers all mode spaces/decoding, per-leg joint bounds, one env API, invalid-action no-advance behavior, and scheduled non-velocity invalid-action regression. |
| `tests/locomotion/test_argus_go2_env_determinism.py` | Seed determinism tests | VERIFIED | Covers same/different seed reset metadata and step metadata preservation. |
| `tests/locomotion/test_argus_go2_env_scenarios.py` | Scenario catalog/XML tests | VERIFIED | Covers required scenario names, XML parseability, source preservation, friction/slope/hfield/push metadata, and no flat `benchmark_floor` for slope/rough terrain. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/locomotion/env.py` | `gymnasium.Env` | Class inheritance and `super().reset(seed=seed)` | VERIFIED | `class ArgusGo2Env(gymnasium.Env)` and reset seeding are present. |
| `src/locomotion/env.py` | `src.locomotion.observations` | Observation space and extraction | VERIFIED | Imports `build_observation_space` and `extract_observation`; uses them in init/reset/step. |
| `src/locomotion/env.py` | `src/locomotion/actions.py` | `build_action_space` in init and `decode_action` in step | VERIFIED | Both imports and usages present; step commits state only after `decode_action` succeeds. |
| `src/locomotion/env.py` | `src/locomotion/scenarios.py` | Reset-time `sample_scenario` and XML build | VERIFIED | Reset samples scenario with Gymnasium RNG; real MuJoCo resets clear stale model/data and reinitialize via `build_scenario_xml`. |
| `src/locomotion/scenarios.py` | `src/locomotion/xml_patcher.py` | In-memory `patch_actuators_to_position` | VERIFIED | `build_scenario_xml` calls `patch_actuators_to_position(str(go2_xml_path))` and mutates parsed string only. |
| `src/locomotion/env.py` | MuJoCo runtime | `MjModel.from_xml_string`, `data.ctrl[:]`, `mj_step`, `xfrc_applied` | VERIFIED | Model construction, control write, stepping loop, and push-force logic are present and tested. |
| `src/locomotion/actions.py` | `TrotGaitController` | `gait.compute` for velocity/residual | VERIFIED | Decode paths use `gait.compute` and return finite 12-vectors. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/locomotion/env.py` | Observation dict | `extract_observation(self._data, self._command, self._previous_action)` | Yes | VERIFIED: real MuJoCo `qpos/qvel` used when `_data` exists; zero-fill fallback is only for no-model unit paths. |
| `src/locomotion/env.py` | Scenario metadata in `info` | `sample_scenario(self.config.scenario_id, self.np_random, ...)` | Yes | VERIFIED: sampled spawn, terrain, command, and disturbance schedules flow into `_info`. |
| `src/locomotion/env.py` | Control vector | `decode_action(...)` | Yes | VERIFIED: decoded vector is stored in `_previous_action` and written to `data.ctrl[:]` when MuJoCo data exists. |
| `src/locomotion/env.py` | Non-velocity scheduled command | `_command_at_time(...)` local variable, committed after decode | Yes | VERIFIED: scheduled command is calculated before decode but not assigned to `_command` until after `decode_action` succeeds. |
| `src/locomotion/env.py` | Randomized terrain model/data | `sample_scenario(...)` then `build_scenario_xml(...)` on reset | Yes | VERIFIED: real MuJoCo-backed reset clears `_model`/`_data` and rebuilds; spot-check printed `rough_reset_rebuilt_model`. |
| `src/locomotion/scenarios.py` | Rough heightfield values | Seeded RNG in `_sample_terrain_parameters` | Yes | VERIFIED: rough heightfield data is seeded, bounded, non-flat, stored in metadata, and loaded into MuJoCo model hfield data when present. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase tests | `cd /home/prannayag/pragnition/robotics/argus/.worktrees/phase-1-locomotion-env-contract && .venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` | `134 passed in 9.51s` | PASS |
| Fixed blocker: non-plane terrain XML removes flat floor | Python spot-check built slope and rough-heightfield XML and asserted no `./worldbody/geom[@name='benchmark_floor']`. | Printed `non_plane_floor_removed`. | PASS |
| Fixed blocker: joint-position bounds are per-leg Go2 bounds | Python spot-check printed `build_action_space(ACTION_MODE_JOINT_POSITION).low/high`. | Front leg thigh bounds are `[-1.5708, 3.4907]`; rear leg thigh bounds are `[-0.5236, 4.5379]`; calf/hip bounds match expected vectors. | PASS |
| Fixed blocker: randomized reset rebuilds real MuJoCo-backed model/data | Python spot-check reset rough-heightfield env with seeds 123 and 456, asserted different heightfield data and different model object ids. | Printed `rough_reset_rebuilt_model`. | PASS |
| Bridge files unchanged by phase wrapper | `git diff -- src/bridge/sim_bridge.py src/bridge/multi_bridge.py src/main.py` | No output | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOC-ENV-01 | 01-01, 01-04, 01-05 | Gymnasium-style `ArgusGo2Env` wrapper with `reset(seed=...)` and `step(action)` returning observation, reward, terminated, truncated, and info. | SATISFIED | `ArgusGo2Env` implemented; contract tests pass; full phase gate passes. |
| LOC-ENV-02 | 01-02, 01-05 | Choose flat-ground, low-friction, slope, rough-heightfield, and push-disturbance scenarios from named catalog. | SATISFIED | `SCENARIOS` includes all five; `sample_scenario` rejects unknowns; env reset selects by config; scenario XML/runtime representations exist. |
| LOC-ENV-03 | 01-02, 01-05 | Deterministic seeded resets reproduce spawn pose, terrain parameters, command schedule, and disturbance timing. | SATISFIED | Determinism tests cover same seeds and different randomized fields; metadata sourced from seeded `self.np_random`; real MuJoCo reset rebuilds randomized terrain. |
| LOC-ENV-04 | 01-03, 01-04 | Select action modes for velocity command, joint-position target, and residual-over-baseline control without changing the environment API. | SATISFIED | Mode spaces/decoding and single env API are implemented; joint-position per-leg bounds verified; invalid-action pre-mutation behavior is verified for immediate and advanced schedule cases. |

Orphaned Phase 1 requirements: none. `.planning/REQUIREMENTS.md` maps exactly LOC-ENV-01 through LOC-ENV-04 to Phase 1, and all four appear in plan frontmatter across the five plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/locomotion/scenarios.py` | 227 | `assets: dict[str, bytes] = {}` | Info | Benign accumulator initialization in `_load_asset_bytes`; not a stub because it is populated from files when assets exist and empty assets are valid when no asset directory exists. |
| `tests/locomotion/test_locomotion.py` | 130, 179 | `assets = {}` | Info | Test fixture values, not production stubs. |
| `tests/locomotion/test_argus_go2_env_contract.py` | 197 | `built_samples = []` | Info | Test accumulator for asserting randomized reset rebuilds; not a production stub. |

No blocker stub, TODO, placeholder, empty implementation, or hardcoded-empty production data flow was found in Phase 1 source/tests.

### Human Verification Required

None. The phase goal is covered by code inspection and automated tests; no visual or external-service behavior is required for Phase 1. The advisory warning about advertised `rgb_array` render mode lacking `render()` does not invalidate LOC-ENV-01 through LOC-ENV-04 or the roadmap Phase 1 success criteria.

### Gaps Summary

No remaining gaps. The previous verification gap and the final code-review blockers are closed: invalid scheduled non-velocity actions validate before mutation, non-plane terrain XML no longer keeps the flat benchmark floor, joint-position mode uses per-leg Go2 bounds, and randomized MuJoCo-backed resets rebuild model/data so terrain is not stale. Phase 1 establishes the requested Gymnasium-style benchmark boundary, named deterministic scenarios, action modes, and bridge compatibility.

---

_Verified: 2026-04-30T08:33:12Z_
_Verifier: Claude (gsd-verifier)_
