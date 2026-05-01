---
phase: 06-repair-evaluation-runner-semantics
verified: 2026-05-01T10:31:40Z
status: gaps_found
score: 11/12 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The evaluation runner is safe and repeatable for scenario/seed matrices."
    status: partial
    reason: "run_evaluation_matrix validates max_episode_steps and passes it into env config, but the runner loop never enforces the cap itself; a custom or broken env_factory that never terminates/truncates can hang indefinitely. This matches 06-REVIEW.md CR-01 and is in-scope for evaluation-runner semantics."
    artifacts:
      - path: "src/locomotion/evaluation.py"
        issue: "while not (terminated or truncated) loop has no independent max_episode_steps counter or truncation fallback."
      - path: "tests/locomotion/test_locomotion_evaluation_runner.py"
        issue: "No regression test covers an env that ignores/exceeds the matrix step cap."
    missing:
      - "Enforce cell['max_episode_steps'] inside run_evaluation_matrix independent of env behavior."
      - "Add a fake-env regression proving the runner returns after max_episode_steps and writes artifacts."
---

# Phase 6: repair-evaluation-runner-semantics Verification Report

**Phase Goal:** Close milestone audit gaps in real evaluation semantics so scenario command schedules, exported distance metrics, and analytical baseline thresholds measure actual locomotion behavior.
**Verified:** 2026-05-01T10:31:40Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Evaluation actions use the command active at the current simulation time, not `command_schedule[0]`. | VERIFIED | `src/locomotion/evaluation.py:410-421` checks `info.get("current_command")` before schedule fallback. Spot-check with `uv run python` showed fake transition env received step actions `[0.0, 0.0, 0.0]` then `[0.4, 0.0, 0.0]`. |
| 2 | `ArgusGo2Env` exposes `current_command` at reset and every step for evaluator consumption. | VERIFIED | `src/locomotion/env.py:454-480` emits `current_command` from `_command_at_time(_current_sim_time())`; `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py -k current_command -q` passed (`1 passed, 20 deselected`). |
| 3 | Exported step command fields match the same active command vector used for `env.step(action)`. | VERIFIED | `src/locomotion/evaluation.py:243-267` derives action, then records command fields from latest info/current command; transition spot-check output showed step rows with `commanded_velocity: [0.4, 0.0, 0.0]`, `command_source: scenario_schedule`, and matching `command_context.current_command`. |
| 4 | Real evaluation artifacts preserve `stability.distance_xy_m` instead of flattening distance from `command_tracking`. | VERIFIED | `src/locomotion/evaluation.py:474-489` reads `stability` and maps `distance_xy_m` from `_metric_alias(stability, "distance_xy_m", default=0.0)`. |
| 5 | `episodes.csv`, `summary.json`, regenerated comparison output, and `result.episode_rows` report the same nonzero distance value. | VERIFIED | `tests/locomotion/test_locomotion_evaluation_exports.py:261-318` asserts `0.42` through result rows, CSV, summary JSON, and comparison Markdown; quick gate passed. |
| 6 | CSV formula safety and output path containment remain intact while export semantics change. | VERIFIED | `_prepare_run_dir()` still rejects escaped paths at `src/locomotion/evaluation.py:384-397`; CSV writer still applies `_csv_safe` at `src/locomotion/evaluation.py:633-638`; export tests cover formula safety. |
| 7 | A stationary or command-ignoring controller cannot pass commanded flat-ground baseline acceptance. | VERIFIED | `tests/locomotion/test_locomotion_baseline_regression.py:191-213` runs a stationary fake env through `run_evaluation_matrix` and asserts `assert_analytical_flat_ground_thresholds(result.episode_rows)` raises. |
| 8 | The Phase 6 quick gate proves active commands, stability distance exports, and baseline threshold semantics together. | VERIFIED | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` passed (`29 passed in 6.66s`). |
| 9 | Validation metadata records deterministic pytest evidence without claiming runtime AI dependency. | VERIFIED | No runtime AI SDK matches from grep over `src`, `pyproject.toml`, and `tests`; `06-VALIDATION.md` conservatively remains pending from earlier unsupported interpreter evidence instead of overclaiming green status. |
| 10 | CLI evaluation can execute a controller across scenario matrix and fixed seed list. | VERIFIED | `validate_evaluation_matrix()` expands controllers/scenarios/seeds at `src/locomotion/evaluation.py:142-203`; fake-env runner test confirms execution and `uv` quick/full gates pass. |
| 11 | Evaluation produces aggregate comparison table with per-controller mean, standard deviation, and failure counts. | VERIFIED | `src/locomotion/evaluation.py:666-690` computes `failure_count`, metric means, and stds; `comparison.md` generation is tested in export tests and quick gate passed. |
| 12 | The evaluation runner is safe and repeatable for scenario/seed matrices. | FAILED | Review CR-01 is valid: `src/locomotion/evaluation.py:243` loops only on env `terminated`/`truncated` and does not independently enforce `cell["max_episode_steps"]`, so a broken/custom env can hang forever. |

**Score:** 11/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/locomotion/env.py` | Env-owned `current_command` info payload | VERIFIED | Exists, substantive, and wired to evaluator via info payload; current-command contract test passed. Advisory WR-01 notes a metrics attribution ambiguity, but it does not invalidate the phase must-have that `current_command` is exposed and consumed for evaluation actions. |
| `src/locomotion/evaluation.py` | Active-command action generation, stability-sourced distance exports, aggregate comparison | PARTIAL | Active-command and distance semantics are implemented and tested. Blocking gap remains: runner loop lacks independent `max_episode_steps` enforcement. |
| `tests/locomotion/test_argus_go2_env_contract.py` | Env contract regression for schedule-transition `current_command` | VERIFIED | `test_argus_go2_env_info_exposes_current_command_from_schedule_transition` exists and targeted pytest passed. |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | Fake-env regression for zero-to-nonzero schedule transition | PARTIAL | Transition regression exists and passes; missing regression for non-terminating env step-cap enforcement. |
| `tests/locomotion/test_locomotion_evaluation_exports.py` | Artifact regression proving stability-sourced distance survives export layers | VERIFIED | Distance export test asserts result rows, CSV, summary JSON, and comparison Markdown. |
| `tests/locomotion/test_locomotion_baseline_regression.py` | Stationary-controller negative regression for commanded baseline | VERIFIED | Stationary commanded fake env goes through `run_evaluation_matrix` and threshold helper rejects zero distance. |
| `.planning/phases/06-repair-evaluation-runner-semantics/06-VALIDATION.md` | Phase validation evidence | WARNING | File exists and honestly records earlier blocked local evidence. It has not been updated to reflect the later post-merge `uv` gates provided in the prompt and rerun here. This is documentation staleness, not the blocking code gap. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/locomotion/env.py` | `src/locomotion/evaluation.py` | `info['current_command']` | WIRED | `_info()` emits `current_command`; `_action_from_command_context()` and `_command_fields()` consume it. |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | `src/locomotion/evaluation.py` | `run_evaluation_matrix(... env_factory=...) captures env.step(action)` | WIRED | gsd-sdk missed this link, but manual read verifies `test_runner_uses_active_current_command_after_schedule_transition` calls `run_evaluation_matrix` with `_fake_env_factory(... transition_commands=True)` and asserts captured `step` calls. |
| `src/locomotion/metrics.py` | `src/locomotion/evaluation.py` | `summary['stability']['distance_xy_m']` | WIRED | Evaluator flattens from `stability` at `src/locomotion/evaluation.py:488`. |
| `src/locomotion/evaluation.py` | `summary.json` and `comparison.md` | `episode_rows` aggregation | WIRED | `write_comparison_artifacts()` aggregates episode rows and writes both artifacts. |
| `src/locomotion/evaluation.py` | `tests/locomotion/test_locomotion_baseline_regression.py` | `run_evaluation_matrix` episode rows feed threshold helper | WIRED | `test_stationary_controller_fails_commanded_locomotion_baseline_gate` asserts rejected rows after `run_evaluation_matrix`. |
| `tests/locomotion/test_locomotion_baseline_regression.py` | `06-VALIDATION.md` | quick gate command status evidence | PARTIAL | Test exists and quick gate passes under `uv`; validation document still contains pending/blocked rows from earlier unsupported interpreter run. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/locomotion/evaluation.py` | `action`, `commanded_velocity`, `command_context` | `current_command` from env info, then schedule fallback | Yes | FLOWING |
| `src/locomotion/env.py` | `current_command` | `_command_at_time(_current_sim_time())` over scenario sample schedule | Yes | FLOWING |
| `src/locomotion/evaluation.py` | `distance_xy_m` | `locomotion_metrics_summary['stability']['distance_xy_m']` | Yes | FLOWING |
| `src/locomotion/evaluation.py` | aggregate means/std/failure counts | `_coerce_episode_row()` then `_aggregate_groups()` over episode rows | Yes | FLOWING |
| `src/locomotion/evaluation.py` | termination condition | env `terminated` / `truncated` only | No independent cap | HOLLOW for broken envs |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 6 quick gate | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` | `29 passed in 6.66s` | PASS |
| Current command env contract | `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py -k current_command -q` | `1 passed, 20 deselected in 3.95s` | PASS |
| Phase 6 full wave gate | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` | `244 passed in 16.73s` | PASS |
| Runtime AI SDK dependency absence | `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" src pyproject.toml tests` | no output | PASS |
| Transition command data flow | Inline `uv run python` fake-env spot-check | Calls included zero then nonzero actions; step rows reported nonzero current command | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOC-METRICS-05 | 06-02, 06-03 | Metrics are exported as JSONL/CSV plus a machine-readable summary suitable for comparing controllers across seeds. | SATISFIED | Artifact set includes `steps.jsonl`, `episodes.csv`, `summary.json`, `comparison.md`; export tests and quick gate passed; distance now sources from stability. |
| LOC-EVAL-01 | 06-01, 06-03 | Developer can run a CLI evaluation command that executes a controller across a scenario matrix and fixed seed list. | BLOCKED | Matrix expansion and execution are implemented and tested, but CR-01 means the runner can hang forever if an env ignores/exceeds the step cap. This prevents full repeatable-runner goal achievement. |
| LOC-EVAL-02 | 06-02, 06-03 | Evaluation produces an aggregate comparison table with per-controller mean, standard deviation, and failure counts. | SATISFIED | `_aggregate_groups()` computes means/stds/failure counts; comparison Markdown is generated and export tests passed. |
| LOC-EVAL-04 | 06-01, 06-03 | Evaluation includes regression tests that prevent the analytical trot baseline from silently degrading on flat-ground smoke scenario. | SATISFIED | Stationary commanded-locomotion negative regression exists; fixed-seed real smoke remains in `test_analytical_trot_flat_ground_fixed_seed_regression`; quick/full gates passed in project virtualenv. |

No orphaned Phase 6 requirements were found in `.planning/REQUIREMENTS.md`; Phase 6 maps exactly LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, and LOC-EVAL-04.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/locomotion/evaluation.py` | 243 | `while not (terminated or truncated)` without internal step cap | BLOCKER | A custom/broken env can hang evaluation indefinitely, blocking repeatable runner semantics. |
| `.planning/phases/06-repair-evaluation-runner-semantics/06-VALIDATION.md` | 5-45 | Validation rows still pending/blocked despite later `uv` gate evidence | WARNING | Stale validation metadata; does not block code behavior, but should be updated before using validation document as milestone proof. |
| `src/locomotion/env.py` | 140, 166 | Review WR-01: velocity-command metrics record desired command from raw action, not necessarily schedule command | WARNING | Advisory ambiguity. It can affect attribution around schedule transitions, but current Phase 6 must-haves for evaluator action/export semantics are covered by fake and integration gates. Consider addressing in a follow-up if scenario command must remain the metric source of truth inside `ArgusGo2Env.step()`. |

### Human Verification Required

None. The relevant checks are deterministic code/test checks in the project virtualenv.

### Gaps Summary

Phase 6 fixed the headline audit semantics for active scheduled commands, stability-sourced distance export, and commanded-baseline threshold rejection. However, the code review's CR-01 is a real in-scope blocker: `run_evaluation_matrix` still trusts the environment to terminate/truncate and does not enforce the validated `max_episode_steps` cap. That makes LOC-EVAL-01 only partially satisfied because a repeatable evaluation runner must not hang indefinitely on a custom or broken `env_factory`.

The stale `06-VALIDATION.md` pending rows are a documentation warning. The stronger evidence is the project virtualenv gate from the prompt and this verification run, both green.

---

_Verified: 2026-05-01T10:31:40Z_
_Verifier: Claude (gsd-verifier)_
