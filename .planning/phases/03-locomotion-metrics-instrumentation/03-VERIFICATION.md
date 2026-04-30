---
phase: 03-locomotion-metrics-instrumentation
verified: 2026-04-30T15:14:45Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Stability metrics include fall rate, roll/pitch bounds, base-height deviation, and distance before failure with explicit termination thresholds."
    status: failed
    reason: "Default progress-stall termination fires for valid zero-command standing episodes after the progress window, so stability termination thresholds are not consistently valid across scenarios/controllers."
    artifacts:
      - path: "src/locomotion/metrics.py"
        issue: "_stability_payload calls _progress_stalled without considering desired translational command; record_step does not pass desired command into stability failure evaluation."
      - path: "src/locomotion/env.py"
        issue: "ArgusGo2Env.step sets terminated=True for any collector failure_reason, so the false progress_stalled failure becomes an immediate Gymnasium termination."
    missing:
      - "Gate progress-stalled failure on a non-trivial desired translational command, or otherwise disable progress checks for standing/zero-command windows."
      - "Add a regression test proving repeated zero-command standing steps do not terminate as progress_stalled."
---

# Phase 3: locomotion-metrics-instrumentation Verification Report

**Phase Goal:** Make locomotion behavior measurable: command tracking, stability, action quality, and contact/terrain proxies are computed consistently across scenarios and controllers.
**Verified:** 2026-04-30T15:14:45Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Metric collection reports forward/lateral/yaw command tracking error over time using desired command and measured base motion. | VERIFIED | `src/locomotion/metrics.py` computes desired, measured, signed error, absolute error, and RMSE for `vx`, `vy`, and `yaw_rate`; `src/locomotion/env.py` measures velocity from world-frame pose and wrapped yaw deltas, not qvel. Focused tests pass. |
| 2 | Stability metrics include fall rate, roll/pitch bounds, base-height deviation, and distance before failure with explicit termination thresholds. | FAILED | Required fields exist, but default progress-stall logic terminates zero-command standing episodes. Spot-check: 26 zero-command records produced `progress_stalled` and `episode_summary().success == False`. Review CR-01 independently identifies the same correctness defect. |
| 3 | Control-quality metrics include action smoothness, joint-limit violations, energy/effort proxy, and actuator saturation or equivalent position-servo proxy. | VERIFIED | `src/locomotion/metrics.py` exposes `action_delta_norm`, `action_jerk_proxy_norm`, joint-limit counts, `position_servo_effort_proxy`, and `position_target_saturation_proxy`; tests verify labels and calculations. |
| 4 | Terrain/contact metrics include foot slip, foot clearance, contact timing/duty factor, and per-scenario success rate. | VERIFIED | `Go2FootMapping`, `terrain_height_at`, `foot_contact_payload_from_mujoco`, per-foot contact/slip/clearance/transition payloads, and duty/slip/clearance/scenario_success summaries exist and are covered by tests. Review WR-01 is a quality warning on bounded-history horizon consistency, not a must-have blocker for existence of these metrics. |
| 5 | Per-step and per-episode metric values are available through `info` or a metrics collector without tying them to one specific controller implementation. | VERIFIED | `ArgusGo2Env` owns `LocomotionMetricsCollector`, emits nested `info["locomotion_metrics"]`, terminal `info["locomotion_metrics_summary"]`, and `last_locomotion_metrics_summary`; action-quality records validated 12-joint targets from dispatch/decode, not a controller-specific raw command. |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/locomotion/metrics.py` | Collector/config/records/summaries plus foot mapping and contact terrain helpers | PARTIAL | Substantive and wired. Contains all metric families, but stability progress-stall threshold is behaviorally wrong for zero-command standing episodes. |
| `src/locomotion/actions.py` | Public copied joint bounds helper | VERIFIED | `joint_position_bounds()` returns copies of the 12-joint lower/upper bounds used by action-quality metrics. |
| `src/locomotion/env.py` | Env metrics ownership, reset/step recording, nested info, termination, summaries | PARTIAL | Substantive and wired to collector; false collector `progress_stalled` failures propagate to `terminated=True`. |
| `src/locomotion/scenarios.py` | Terrain metadata/plumbing for terrain-height proxy | VERIFIED | Scenario samples include terrain kind, slope parameters, and rough heightfield metadata. Rough heightfield data was spot-checked as loaded into MuJoCo model data. |
| `tests/locomotion/test_locomotion_metrics_collector.py` | Tests for command/stability/action-quality collector behavior and traceability | WARNING | Passes and covers required metrics, but lacks a zero-command no-progress regression; review IN-01 notes brittle scope string scanning. |
| `tests/locomotion/test_locomotion_metrics_foot_mapping.py` | Tests for strict foot mapping and contact/terrain metrics | VERIFIED | Covers strict FL/FR/RL/RR mapping, missing/duplicate/no-heuristic failures, terrain height helper, slip, clearance, duty factor, and scenario success. |
| `tests/locomotion/test_argus_go2_env_metrics.py` | Tests for env metrics wiring and failure termination | WARNING | Passes and covers nested info/summary/action-target/world-delta behavior, but lacks regression for zero-command standing not triggering progress_stalled termination. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/locomotion/metrics.py` | `src/locomotion/actions.py` | `joint_position_bounds()` import | WIRED | Imported at module line 12 and used in `_action_quality_payload`. |
| `src/locomotion/env.py` | `src/locomotion/metrics.py` | `LocomotionMetricsCollector`, `Go2FootMapping`, `foot_contact_payload_from_mujoco` | WIRED | Env constructs collector, resolves mapping on reset, records metrics on step, emits payloads. |
| `src/locomotion/env.py` | Gymnasium step return | `terminated` set from metric failure | WIRED WITH BLOCKER | Termination wiring exists, but it propagates the false zero-command progress-stall failure. |
| `tests/locomotion/*metrics*.py` | Production metrics/env code | Direct imports and behavior assertions | WIRED | Phase quick command passed: 23 tests passed with two pre-existing pytest config warnings. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ArgusGo2Env.step` per-step metrics | `info["locomotion_metrics"]` | `_record_locomotion_metrics()` from MuJoCo qpos/qvel/pose deltas/control targets/contact data | Yes | FLOWING |
| `ArgusGo2Env.step` episode summary | `info["locomotion_metrics_summary"]` | `LocomotionMetricsCollector.episode_summary()` on terminated/truncated | Partially | HOLLOW EDGE: summary is real, but can be produced by false `progress_stalled` termination for zero-command episodes. |
| `LocomotionMetricsCollector.contact_terrain` | per-foot contact/slip/clearance | explicit foot inputs or `foot_contact_payload_from_mujoco()` and `terrain_height_at()` | Yes | FLOWING |
| `terrain_height_at` rough terrain | heightfield sample | `ScenarioSample.terrain_parameters["heightfield_data"]` | Yes | FLOWING; additional spot-check confirmed MuJoCo model hfield data matches sampled data after reset. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 3 quick metrics suite | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_locomotion_metrics_foot_mapping.py tests/locomotion/test_argus_go2_env_metrics.py -q` | `23 passed, 2 warnings` | PASS |
| Zero-command standing does not fail progress threshold | Python snippet recording 26 zero-command stationary collector steps | Last failure reason was `progress_stalled`; summary success was `False` | FAIL |
| Rough heightfield reset has real sampled hfield data | Python snippet resetting `ArgusGo2Env(scenario_id="rough_heightfield")` and comparing sampled data to `env._model.hfield_data` | sizes 256/256, equal True, nonzero True | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOC-METRICS-01 | 03-01, 03-03, 03-04 | Evaluation captures command tracking error for forward velocity, lateral velocity, and yaw rate. | SATISFIED | Collector records desired/measured/signed/absolute errors and summaries; env derives measured vx/vy/yaw from pose/time deltas; tests cover qvel rejection. |
| LOC-METRICS-02 | 03-01, 03-03, 03-04 | Evaluation captures stability metrics: fall rate, roll/pitch bounds, base height deviation, and distance before failure. | BLOCKED | Fields exist, but explicit termination threshold semantics are defective because zero-command stationary episodes falsely fail as `progress_stalled`. |
| LOC-METRICS-03 | 03-01, 03-03, 03-04 | Evaluation captures control-quality metrics: action smoothness, joint-limit violations, energy/effort proxy, and actuator saturation. | SATISFIED | Action delta, jerk proxy, commanded/observed joint-limit counts, effort proxy, saturation proxy are computed and tested. |
| LOC-METRICS-04 | 03-02, 03-03, 03-04 | Evaluation captures terrain/contact proxies: foot slip, foot clearance, contact timing/duty factor, and scenario success rate. | SATISFIED WITH WARNING | Metrics and tests exist. Review WR-01 warns contact summaries mix lifetime accumulators with bounded retained records after history rollover; fix recommended for consistency but not classified as a must-have blocker here. |

No orphaned Phase 3 requirements found in `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md`: LOC-METRICS-01 through LOC-METRICS-04 are all declared in plan frontmatter and accounted for above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/locomotion/metrics.py` | 284 | `_progress_stalled` checked without desired-command gating | BLOCKER | Valid standing/zero-command episodes terminate as failures. |
| `src/locomotion/metrics.py` | 125-134, 478-510 | bounded `_steps` plus unbounded contact accumulators | WARNING | Contact summaries can use a different horizon than other summary families after history rollover. |
| `tests/locomotion/test_locomotion_metrics_collector.py` | 244-251 | source-text forbidden-term scan | INFO | Brittle scope guard; does not block the phase goal. |

### Human Verification Required

None. The blocking gap is programmatically reproducible.

### Gaps Summary

Phase 3 is close but not achieved. The code computes and wires the required metric families, and the focused Phase 3 tests pass. However, stability termination semantics are wrong: standing still under a zero desired command is a valid behavior, especially during the default command schedule's initial zero-command window, but the collector flags it as `progress_stalled` after the default progress window. Because the env directly maps any collector failure reason to Gymnasium `terminated=True`, this produces false failed episodes and violates the phase goal's requirement that metrics be computed consistently across scenarios and controllers.

---

_Verified: 2026-04-30T15:14:45Z_
_Verifier: Claude (gsd-verifier)_
