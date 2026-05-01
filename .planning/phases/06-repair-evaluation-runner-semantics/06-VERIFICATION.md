---
phase: 06-repair-evaluation-runner-semantics
verified: 2026-05-01T12:11:26Z
status: gaps_found
score: 13/15 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 11/12
  gaps_closed:
    - "The evaluation runner is safe and repeatable for scenario/seed matrices: run_evaluation_matrix now enforces cell['max_episode_steps'] with runner_step_count and a non-terminating-env regression proves bounded artifact writing."
  gaps_remaining: []
  regressions:
    - "Exported step command fields do not always match the action that actually drove env.step(action) across command-schedule transitions."
gaps:
  - truth: "Exported step command fields match the same active command vector used for env.step(action)."
    status: failed
    reason: "run_evaluation_matrix records command fields after env.step() from latest_info, so a schedule transition during the step can label the just-completed step with the next command rather than the action actually passed to env.step(action). A spot-check showed the first transition step called env.step([0.0, 0.0, 0.0]) but recorded commanded_velocity [0.4, 0.0, 0.0]."
    artifacts:
      - path: "src/locomotion/evaluation.py"
        issue: "Loop computes action/source from pre-step latest_info, but computes commanded_velocity/command_source/command_context from post-step latest_info before writing the row."
      - path: "src/locomotion/env.py"
        issue: "Velocity-command step dispatch uses the caller action directly while _info() reports schedule-derived current_command, so real env export labels can diverge from controller input at schedule boundaries."
      - path: "tests/locomotion/test_locomotion_evaluation_runner.py"
        issue: "Transition regression asserts the final post-transition row only and does not catch the first-step action/export mismatch."
    missing:
      - "Make the runner's step row record the command/action that drove that exact env.step(), or make ArgusGo2Env velocity-command execution and _info() report the same command for the step."
      - "Add a regression that checks every captured env.step(action) has a matching exported step row commanded_velocity, including the transition-boundary first step."
      - "Add real ArgusGo2Env/controller-path coverage or a focused fake dispatch test proving schedule-derived current_command does not drift from controller input."
  - truth: "Regression coverage proves nonzero scheduled commands drive real/fake evaluation actions and baseline checks cannot pass as stationary standing tests."
    status: partial
    reason: "Fake-env runner coverage proves zero then nonzero actions and stationary baseline rejection exists, but the real ArgusGo2Env velocity-command path is not covered for schedule-transition controller dispatch. Existing review evidence identifies the real env can report schedule-derived current_command while dispatching the caller action for the just-completed step."
    artifacts:
      - path: "tests/locomotion/test_argus_go2_env_contract.py"
        issue: "Current-command test calls _info() after manipulating time; it does not exercise ArgusGo2Env.step() controller dispatch under a schedule transition."
      - path: "tests/locomotion/test_locomotion_evaluation_runner.py"
        issue: "Fake transition test proves runner behavior but misses the mismatched first row and does not cover the real environment/controller path."
    missing:
      - "Add regression coverage for real or dispatch-patched ArgusGo2Env velocity-command step semantics across a command schedule transition."
human_verification: []
---

# Phase 6: repair-evaluation-runner-semantics Verification Report

**Phase Goal:** Close milestone audit gaps in real evaluation semantics so scenario command schedules, exported distance metrics, and analytical baseline thresholds measure actual locomotion behavior.
**Verified:** 2026-05-01T12:11:26Z
**Status:** gaps_found
**Re-verification:** Yes — after gap closure plan 06-04

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Evaluation actions use the command active at the current simulation time/current command instead of always using `command_schedule[0]`. | VERIFIED | `src/locomotion/evaluation.py:414-425` checks `info.get("current_command")` before schedule fallback. Targeted runner regression passed and the spot-check captured calls `[0.0, 0.0, 0.0]` then `[0.4, 0.0, 0.0]`. |
| 2 | `ArgusGo2Env` exposes enough current-command state at reset/step for evaluator consumption. | VERIFIED | `src/locomotion/env.py:454-480` emits `current_command` with `time`, `vx`, `vy`, `omega`, and `source`; `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py -k current_command -q` passed (`1 passed`). |
| 3 | Exported step command fields match the same active command vector used for `env.step(action)`. | FAILED | Spot-check demonstrated mismatch: calls were `[[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]]`, but exported rows were `[(1, [0.4, 0.0, 0.0]), (2, [0.4, 0.0, 0.0])]`. `src/locomotion/evaluation.py:245-259` records command fields from post-step `latest_info`, not the pre-step action source. |
| 4 | Real evaluation artifacts read `distance_xy_m` from the stability episode summary. | VERIFIED | `src/locomotion/evaluation.py:472-493` maps `distance_xy_m` from `stability` via `_metric_alias(stability, "distance_xy_m", default=0.0)`. |
| 5 | `distance_xy_m` is preserved in result rows, `episodes.csv`, `summary.json`, comparison output, and threshold paths. | VERIFIED | `tests/locomotion/test_locomotion_evaluation_exports.py:261-318` asserts `0.42` through result rows, CSV, summary JSON, and comparison Markdown; targeted test passed. |
| 6 | CSV formula safety and output path containment remain intact. | VERIFIED | `_prepare_run_dir()` still contains the resolved-root escape guard at `src/locomotion/evaluation.py:388-401`; CSV writer still applies `_csv_safe` at `src/locomotion/evaluation.py:637-642`. |
| 7 | A stationary or command-ignoring controller cannot pass commanded flat-ground baseline acceptance. | VERIFIED | `tests/locomotion/test_locomotion_baseline_regression.py:191-213` routes a stationary env through `run_evaluation_matrix` and asserts `assert_analytical_flat_ground_thresholds(result.episode_rows)` raises. Targeted test passed. |
| 8 | Regression coverage proves nonzero scheduled commands drive real/fake evaluation actions and baseline checks cannot pass as stationary standing tests. | FAILED | Fake-env and stationary-baseline tests pass, but real `ArgusGo2Env.step()` schedule-transition controller dispatch is not covered. `06-REVIEW.md` CR-01 identifies the real velocity-command path can report schedule `current_command` while dispatching a different caller action for the step. |
| 9 | Validation metadata records deterministic pytest evidence without adding runtime AI dependency. | VERIFIED | `06-VALIDATION.md` conservatively does not overclaim older blocked local gates; `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" /home/prannayag/pragnition/robotics/argus/src /home/prannayag/pragnition/robotics/argus/pyproject.toml /home/prannayag/pragnition/robotics/argus/tests` produced no output. |
| 10 | CLI evaluation can execute a controller across a scenario matrix and fixed seed list. | VERIFIED | `src/main.py:93-148` defines `eval-locomotion`; `src/main.py:269-325` constructs `EvaluationMatrix` and calls `run_evaluation_matrix`. Matrix expansion is validated at `src/locomotion/evaluation.py:142-203`. |
| 11 | Evaluation produces aggregate comparison tables with per-controller means, standard deviations, and failure counts. | VERIFIED | `src/locomotion/evaluation.py:670-694` computes `failure_count`, means, and stds; `write_comparison_artifacts()` writes `summary.json` and `comparison.md`. Export tests passed. |
| 12 | The evaluation runner is safe and repeatable for scenario/seed matrices even when an env never terminates/truncates. | VERIFIED | Previous gap closed: `src/locomotion/evaluation.py:243-252` initializes/increments `runner_step_count` and forces `truncated = True` at `cell["max_episode_steps"]`. Non-terminating-env regression passed. |
| 13 | `run_evaluation_matrix` enforces each validated cell `max_episode_steps` inside the runner loop independent of env behavior. | VERIFIED | `src/locomotion/evaluation.py:243-252`; targeted test `test_runner_enforces_matrix_max_episode_steps_when_env_never_terminates` passed. |
| 14 | A fake non-terminating env regression returns after the matrix cap and still writes all five artifacts. | VERIFIED | `tests/locomotion/test_locomotion_evaluation_runner.py:268-353` asserts exactly 3 steps and existence of `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md`; targeted test passed. |
| 15 | LOC-EVAL-01 is satisfied by bounded controller × scenario × seed execution rather than trusting env termination. | VERIFIED | Matrix validation plus runner-owned cap now bound custom env execution; `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` passed (`12 passed`). |

**Score:** 13/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/locomotion/env.py` | Env-owned `current_command` info payload | PARTIAL | `_info()` emits schedule-derived `current_command`, but in velocity-command mode `step()` dispatches the caller action and then `_info()` may report the next schedule command. This can make real step metadata diverge from controller input at schedule boundaries. |
| `src/locomotion/evaluation.py` | Active-command action generation, distance export, runner-owned cap | PARTIAL | Distance export and runner cap are implemented. Step row command fields are written from post-step info, creating action/export mismatches across transitions. |
| `tests/locomotion/test_argus_go2_env_contract.py` | Env current-command regression | PARTIAL | `_info()` transition test exists and passes, but no test covers `ArgusGo2Env.step()` dispatch/metrics under a schedule transition. |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | Active-command fake-env and non-terminating-env regressions | PARTIAL | Non-terminating cap regression exists and passes. Transition test misses the first-row mismatch between captured action and exported `commanded_velocity`. |
| `tests/locomotion/test_locomotion_evaluation_exports.py` | Stability-distance artifact regression | VERIFIED | Distance regression asserts result rows, CSV, summary JSON, and Markdown comparison. |
| `tests/locomotion/test_locomotion_baseline_regression.py` | Stationary-controller negative regression | VERIFIED | Stationary commanded locomotion fixture routes through `run_evaluation_matrix` and threshold helper rejects zero distance. |
| `.planning/phases/06-repair-evaluation-runner-semantics/06-VALIDATION.md` | Validation evidence record | WARNING | Still records older blocked local pytest evidence and `nyquist_compliant: false` despite later `uv run` green gates in 06-04 summary and this verification. Documentation stale, not the blocking code defect. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/locomotion/env.py` | `src/locomotion/evaluation.py` | `info['current_command']` | WIRED | Env emits and evaluator consumes `current_command`. Semantics are incomplete at transition-boundary row labeling. |
| `src/locomotion/evaluation.py` | `tests/locomotion/test_locomotion_evaluation_runner.py` | fake env captures `env.step(action)` | PARTIAL | Tests prove zero then nonzero calls and max-step cap, but do not assert per-row action/export equality for each step. |
| `src/locomotion/metrics.py` | `src/locomotion/evaluation.py` | `summary['stability']['distance_xy_m']` | WIRED | Evaluator flattens from stability and export test confirms artifact propagation. |
| `src/locomotion/evaluation.py` | `summary.json` and `comparison.md` | episode row aggregation | WIRED | `write_comparison_artifacts()` aggregates episode rows and writes both artifacts. |
| `src/locomotion/evaluation.py` | `tests/locomotion/test_locomotion_baseline_regression.py` | episode rows feed threshold helper | WIRED | Stationary fake env and real fixed-seed smoke both route through `run_evaluation_matrix`. |
| `src/main.py` | `src/locomotion/evaluation.py` | CLI `eval-locomotion` subcommand | WIRED | `run_eval_locomotion_mode()` constructs matrix/config and calls `run_evaluation_matrix`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/locomotion/evaluation.py` | `action` | pre-step `latest_info.current_command`, fallback to schedule | Yes | FLOWING |
| `src/locomotion/evaluation.py` | `commanded_velocity` in step rows | post-step `latest_info.current_command` | Not always same as action | HOLLOW at schedule transition boundary |
| `src/locomotion/env.py` | `current_command` | `_command_at_time(_current_sim_time())` | Yes | FLOWING |
| `src/locomotion/env.py` | controller command in velocity mode | caller `action` | Yes, but not necessarily same as `_info().current_command` | PARTIAL |
| `src/locomotion/evaluation.py` | `distance_xy_m` | `locomotion_metrics_summary['stability']['distance_xy_m']` | Yes | FLOWING |
| `src/locomotion/evaluation.py` | runner termination condition | env termination/truncation plus runner-owned `runner_step_count` cap | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Targeted Phase 6 regressions | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_enforces_matrix_max_episode_steps_when_env_never_terminates tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_uses_active_current_command_after_schedule_transition tests/locomotion/test_locomotion_evaluation_exports.py::test_episode_export_reads_distance_xy_m_from_stability_summary tests/locomotion/test_locomotion_baseline_regression.py::test_stationary_controller_fails_commanded_locomotion_baseline_gate -q` | `4 passed in 3.88s` | PASS |
| Phase 6 quick gate | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` | `30 passed in 4.97s` | PASS |
| Current-command env contract | `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py -k current_command -q` | `1 passed, 20 deselected in 3.80s` | PASS |
| Runner module gate | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | `12 passed in 4.52s` | PASS |
| Action/export transition spot-check | Inline `uv run python` fake-env script | Calls `[[0.0,0.0,0.0],[0.4,0.0,0.0]]`; rows `[(1,[0.4,0.0,0.0]),(2,[0.4,0.0,0.0])]` | FAIL |
| Runtime AI SDK absence | `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" /home/prannayag/pragnition/robotics/argus/src /home/prannayag/pragnition/robotics/argus/pyproject.toml /home/prannayag/pragnition/robotics/argus/tests` | no output | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOC-METRICS-05 | 06-02, 06-03, 06-04 | Metrics are exported as JSONL/CSV plus a machine-readable summary suitable for comparing controllers across seeds. | SATISFIED | Artifact set is written; stability distance is preserved through result rows, CSV, summary JSON, and comparison Markdown; export regression passed. |
| LOC-EVAL-01 | 06-01, 06-03, 06-04 | Developer can run a CLI evaluation command that executes a controller across a scenario matrix and fixed seed list. | SATISFIED | CLI is wired; matrix validation expands controller/scenario/seed cells; runner now enforces `max_episode_steps` independent of env behavior; runner tests passed. |
| LOC-EVAL-02 | 06-02, 06-03, 06-04 | Evaluation produces an aggregate comparison table with per-controller mean, standard deviation, and failure counts. | SATISFIED | `_aggregate_groups()` computes means/std/failure counts and `comparison.md` is generated from saved rows. |
| LOC-EVAL-04 | 06-01, 06-03, 06-04 | Evaluation includes regression tests that prevent analytical trot baseline from silently degrading on flat-ground smoke scenario. | PARTIAL | Stationary/no-op commanded baseline rejection exists and fixed-seed smoke remains. However, Phase 6's scheduled-command regression coverage does not prove the real `ArgusGo2Env` velocity-command controller path uses/export-labels the same active command at schedule transitions. |

No orphaned Phase 6 requirements were found in `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md`; Phase 6 maps exactly LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, and LOC-EVAL-04.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/locomotion/evaluation.py` | 245-259 | pre-step action, post-step command label | BLOCKER | Step artifacts can claim the command active after a transition rather than the action that drove the just-completed step. |
| `src/locomotion/env.py` | 125-140, 454-480 | velocity action dispatch and schedule-derived info can describe different commands | BLOCKER | Real env/controller metrics and exported command labels can diverge at scheduled command transitions. |
| `src/locomotion/evaluation.py` | 543-547 | `float(item)` over dict contact metrics without tolerant coercion | WARNING | Malformed saved/fake contact metrics can abort artifact writing. This is robustness debt from `06-REVIEW.md` WR-01, not the phase-goal blocker. |
| `.planning/phases/06-repair-evaluation-runner-semantics/06-VALIDATION.md` | 5-85 | stale pending validation status | WARNING | Validation document does not reflect later green `uv run` evidence; summaries and this verification provide stronger current evidence. |

### Human Verification Required

None. The blocking gaps are deterministic code/data-flow defects with reproducible spot-check evidence.

### Gaps Summary

Plan 06-04 closed the previous blocker: evaluation matrix execution is now bounded by the validated per-cell `max_episode_steps`, and a non-terminating fake env proves artifacts are still written after forced truncation.

Phase 6 still does not achieve the full goal. The remaining blocker is semantic, not existence-based: command fields can be exported from post-step `current_command` while the actual `env.step(action)` used the pre-step action. That means artifacts and tracking evidence may claim a nonzero scheduled command for a step that actually executed the previous zero command at the transition boundary. The current tests pass because they assert only that a later nonzero action occurs; they do not verify per-step equality between captured action and exported row fields, nor do they cover the real `ArgusGo2Env` velocity-command dispatch path across schedule transitions.

---

_Verified: 2026-05-01T12:11:26Z_
_Verifier: Claude (gsd-verifier)_
