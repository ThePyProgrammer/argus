---
phase: 04-evaluation-runner-and-regression
verified: 2026-05-01T05:43:38Z
status: passed
score: 26/26 must-haves verified
overrides_applied: 0
---

# Phase 4: evaluation-runner-and-regression Verification Report

**Phase Goal:** Provide a repeatable CLI benchmark runner that executes controllers across scenario/seed matrices and exports enough data to compare and reproduce runs.
**Verified:** 2026-05-01T05:43:38Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Roadmap SC1: A CLI evaluation command runs one or more controllers across a named scenario matrix and fixed seed list. | VERIFIED | `src/main.py` defines top-level `eval-locomotion` parser at lines 92-148, repeated `--controller`, `--scenario`, `--seed` flags, and dispatches through `sys.exit(run_eval_locomotion_mode(args))` at lines 923-924. `tests/test_main_args.py` verifies parser and help behavior. |
| 2 | Roadmap SC2: Each run exports JSONL/CSV plus a machine-readable summary with per-controller mean, standard deviation, and failure counts. | VERIFIED | `src/locomotion/evaluation.py` writes `steps.jsonl`, `episodes.csv`, `summary.json` in `_write_artifacts` lines 623-638; aggregation emits `*_mean`, `*_std`, and `failure_count` in `_aggregate_groups` lines 666-690. Export tests verify artifact shape and summaries. |
| 3 | Roadmap SC3: Exported metadata includes git commit, controller id, scenario id, seed, environment config, action mode, and run timestamp. | VERIFIED | `_build_manifest` lines 575-606 includes `git_commit`, matrix/cell metadata, `environment_config`, `action_mode`, `created_at`, files, and runs. Tests assert top-level manifest fields and run command metadata. |
| 4 | Roadmap SC4: The aggregate comparison table can be generated from saved artifacts without re-running simulation. | VERIFIED | `regenerate_comparison(run_dir)` lines 339-345 reads `manifest.json` and `episodes.csv`, then writes summary/Markdown. Test monkeypatches `ArgusGo2Env` to raise if constructed and verifies regeneration succeeds. |
| 5 | Roadmap SC5: A regression test prevents the analytical trot baseline from silently degrading on the flat-ground smoke scenario. | VERIFIED | `tests/locomotion/test_locomotion_baseline_regression.py` defines `assert_analytical_flat_ground_thresholds` and integration test using `analytical_trot`, `flat_ground`, seeds `(101, 202, 303)`, `summary.json`, and threshold checks. |
| 6 | D-02: Developer can define a controller x scenario x seed matrix before any simulation starts, including repeatable flag-shaped inputs and optional saved matrix config support. | VERIFIED | `EvaluationMatrix`, `load_matrix_config`, and `validate_evaluation_matrix` exist in `src/locomotion/evaluation.py`; tests verify matrix expansion and JSON config loading before simulation. |
| 7 | Evaluation runs use the scenario command schedule produced by `ArgusGo2Env` rather than hardcoded stationary actions. | VERIFIED | `_action_from_command_context` and `_command_fields` derive actions from `command_schedule`/`current_command` at lines 410-447. Runner test asserts nonzero `[0.4, 0.0, 0.0]` action is stepped and recorded. |
| 8 | Invalid controller, scenario, seed, action mode, or matrix size inputs fail before creating run directories or environments. | VERIFIED | `run_evaluation_matrix` validates at line 215 before `_prepare_run_dir` line 217 and env construction line 232; tests assert invalid inputs leave no `tmp_path` children and no env calls. |
| 9 | D-04: Unavailable placeholder controllers fail fast with clear unavailable-controller errors before simulation. | VERIFIED | `validate_evaluation_matrix` lines 161-172 raises `UnavailableControllerError` for unavailable registry entries; test verifies `residual_policy` fails before env construction. |
| 10 | D-05: Each evaluation invocation writes one self-contained timestamped run directory with JSONL, CSV, manifest, summary, and Markdown artifacts. | VERIFIED | `_prepare_run_dir` creates timestamped child directories; `_ARTIFACT_FILES` and `_write_artifacts` write exactly `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, `comparison.md`; test asserts exact set. |
| 11 | D-06: Per-step JSONL rows carry compact ids plus nested `locomotion_metrics` payloads from the environment. | VERIFIED | Step rows at lines 256-266 include ids, `step_count`, `sim_time`, command fields, `command_schedule`, and `locomotion_metrics`; test reads `steps.jsonl` and asserts nested metric payload. |
| 12 | D-08: Artifacts preserve top-level manifest reproducibility metadata plus compact row ids, `commanded_velocity`, `command_source`, and command context needed to compare stationary and translational runs. | VERIFIED | Manifest rows include reset metadata, schedules, `commanded_velocity`, `command_source`, and `command_context` in `_manifest_run_row`; tests assert command metadata in manifest and JSONL. |
| 13 | D-07: Episode CSV rows are flattened per controller/scenario/seed and safe to open in spreadsheets. | VERIFIED | `_EPISODE_CSV_FIELDS` defines flattened row schema; `_csv_safe` prefixes formula-like strings; `test_csv_string_cells_are_formula_safe` asserts escaped failure reason. |
| 14 | D-09: Default comparison table is a compact research-facing scorecard emphasizing success rate, failure count, tracking RMSE, distance, stability, action smoothness, effort proxy, and contact/terrain highlights. | VERIFIED | `_SCORECARD_METRICS`, `_aggregate_groups`, and `_comparison_markdown` include success rate, failure count, tracking/distance/base-height/action/effort/slip metrics; export test asserts Markdown sections and direction labels. |
| 15 | D-10: Summary aggregates include per-controller and per-controller/per-scenario mean, standard deviation, and failure counts. | VERIFIED | `aggregate_episode_rows` returns `overall_by_controller` and `by_controller_and_scenario`; `_aggregate_groups` emits mean/std metrics and `failure_count`. |
| 16 | D-11: Saved artifacts can regenerate comparison outputs without rerunning simulation. | VERIFIED | `regenerate_comparison` uses saved manifest and episode CSV only; CLI `--from-run-dir` branch calls it and prints paths; tests monkeypatch env construction to fail if used. |
| 17 | D-12: Summary and Markdown comparison artifacts include metric direction labels such as `tracking_rmse ↓` and `success_rate ↑`, and no composite controller score is invented. | VERIFIED | `METRIC_DIRECTIONS` lines 66-73 contains labels; tests assert labels and absence of `composite_score`. Grep found no `composite_score` in implementation. |
| 18 | D-01: Developer can invoke `argus eval-locomotion` through `src.main:main` as a dedicated subcommand, not a `--control` runtime mode. | VERIFIED | `src/main.py` uses argparse subparser `eval-locomotion`; `--control` choices at lines 149-154 do not include it; tests verify it is absent from control help. |
| 19 | D-02 CLI: CLI accepts repeated `--controller`, `--scenario`, and `--seed` flags, plus optional JSON `--matrix-config`. | VERIFIED | Parser uses `action="append"` for repeated flags and `--matrix-config`; `run_eval_locomotion_mode` loads matrix config and overrides repeated flags when supplied. |
| 20 | D-03: Default CLI output is quiet and artifact-focused; `--verbose` prints per-run progress. | VERIFIED | Default branch prints run_dir, summary, comparison, and comparison contents; per-run lines are guarded by `if args.verbose` at lines 313-321. |
| 21 | D-16: CLI exits nonzero after writing artifacts when evaluated locomotion failure occurs by default. | VERIFIED | `run_evaluation_matrix` writes artifacts before computing/returning exit code lines 294-303; CLI returns `result.exit_code`; tests assert failed episode writes all artifacts before `exit_code == 1`. |
| 22 | D-11 CLI: CLI can regenerate comparison artifacts from a saved run directory without rerunning simulation. | VERIFIED | `run_eval_locomotion_mode` lines 280-285 handles `--from-run-dir` via `regenerate_comparison` and returns 0. |
| 23 | D-14: A pytest regression gate exercises analytical trot on flat ground over a small fixed seed set. | VERIFIED | Integration test in `tests/locomotion/test_locomotion_baseline_regression.py` lines 179-205 uses controller `analytical_trot`, scenario `flat_ground`, seeds `(101, 202, 303)`. |
| 24 | D-13: The gate asserts no locomotion failure plus bounded tracking, stability, and distance metrics for translational command schedules using robust thresholds rather than golden snapshots. | VERIFIED | Threshold helper asserts success/failure_reason, command context, tracking, distance for nonzero translational velocity, base height, roll, and pitch. No golden snapshots are used. |
| 25 | Synthetic degraded summaries fail the same threshold helper so the gate is not toothless. | VERIFIED | Synthetic tests reject locomotion failure, tracking degradation, zero distance for translational command, missing command context, and stability degradation. |
| 26 | D-15: Real MuJoCo smoke path skips cleanly when MuJoCo/assets are unavailable while fast fake-env/unit tests cover runner, export, reload, and aggregation behavior. | VERIFIED | `_skip_if_mujoco_python_unsupported` skips on Python/MuJoCo mismatch; asset check skips when `models/unitree_go2/go2.xml` is absent; fake-env tests cover runner/export/reload. Full phase test command passed. |

**Score:** 26/26 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | Matrix dataclasses, validation, runner loop, artifact writing, summary aggregation, offline regeneration | VERIFIED | Substantive 787-line module; exports `EvaluationMatrix`, `EvaluationRunConfig`, `EvaluationResult`, `load_matrix_config`, `validate_evaluation_matrix`, `run_evaluation_matrix`, `aggregate_episode_rows`, `write_comparison_artifacts`, `regenerate_comparison`; wired through CLI and tests. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | `eval-locomotion` subcommand parser and lazy dispatch | VERIFIED | Parser and dispatch implemented; imports evaluation code lazily inside `run_eval_locomotion_mode`; `main()` exits with eval result code for subcommand only. |
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py` | Fake-env/unit coverage for matrix validation and runner semantics | VERIFIED | Covers validation-before-side-effects, unavailable controller, config loading, command schedule, nonzero failure exit after rows exist. |
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py` | Artifact shape, metadata, CSV safety, production metric schema alias, reload-without-rerun coverage | VERIFIED | Includes post-review production schema regression test mapping `min_base_height_m`, `max_abs_roll_rad`, `action_delta_norm_mean`, contact dictionaries, etc. |
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_baseline_regression.py` | Analytical flat-ground threshold regression and synthetic failure tests | VERIFIED | Includes threshold helper, synthetic degradation coverage, and marked integration test. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_main_args.py` | CLI parser/subprocess smoke coverage | VERIFIED | Covers parser repeated flags, help listing, and `eval-locomotion` separation from `--control`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/locomotion/evaluation.py` | `src.locomotion.controllers.ControllerRegistry` | `validate_evaluation_matrix` | WIRED | Imports `ControllerRegistry`; calls `ControllerRegistry.list_controllers()` and enforces availability before side effects. |
| `src/locomotion/evaluation.py` | `src.locomotion.scenarios.list_scenarios` | `validate_evaluation_matrix` | WIRED | Imports and calls `list_scenarios()` before matrix cell creation. |
| `src/locomotion/evaluation.py` | `steps.jsonl` | per-step write from `step_rows` | WIRED | `_write_artifacts` writes one JSON object per step row; tests parse it. |
| `src/locomotion/evaluation.py` | `episodes.csv` | flattened terminal summary | WIRED | `_episode_csv_row` maps nested summaries into fixed CSV fields; `_write_artifacts` writes CSV with formula-safe string handling. |
| `src/locomotion/evaluation.py` | `summary.json` and `comparison.md` | aggregate saved episode rows | WIRED | `write_comparison_artifacts` writes both artifacts from aggregation output. |
| `src/main.py` | `src.locomotion.evaluation.run_evaluation_matrix` | lazy import in eval dispatch | WIRED | Lazy import and call at lines 272-308. |
| `src/main.py` | `src.locomotion.evaluation.regenerate_comparison` | `--from-run-dir` reload branch | WIRED | Lazy import and branch at lines 280-285. |
| `tests/locomotion/test_locomotion_baseline_regression.py` | `run_evaluation_matrix` | fixed analytical_trot flat_ground seed matrix | WIRED | Integration test calls runner with fixed baseline matrix. |
| `tests/locomotion/test_locomotion_baseline_regression.py` | summary/episode rows | threshold helper over saved metrics | WIRED | Asserts `summary.json` exists and applies helper to `result.episode_rows`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/locomotion/evaluation.py` | `step_rows[*].locomotion_metrics` | `info["locomotion_metrics"]` from env step | Yes | FLOWING — JSONL rows use actual env-provided per-step metric payloads, not static data. |
| `src/locomotion/evaluation.py` | `episode_rows`/`episodes.csv` metric fields | terminal `info["locomotion_metrics_summary"]` or env summary | Yes | FLOWING — `_episode_csv_row` maps actual command tracking/stability/action/contact summaries, including post-review aliases for production schema fields. |
| `src/locomotion/evaluation.py` | `summary.json` aggregate rows | saved/generated episode rows | Yes | FLOWING — `aggregate_episode_rows` computes mean/std/failure counts from materialized episode rows and offline CSV reload. |
| `src/main.py` | CLI matrix/run config | argparse namespace and optional JSON matrix config | Yes | FLOWING — CLI constructs `EvaluationMatrix` and `EvaluationRunConfig`, calls runner, and returns actual `EvaluationResult.exit_code`. |
| `tests/locomotion/test_locomotion_baseline_regression.py` | threshold helper row metrics | `result.episode_rows` from real runner path | Yes | FLOWING — integration test gates runner-produced rows and asserts summary artifact exists. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase runner/export/CLI/regression tests pass | `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_baseline_regression.py /home/prannayag/pragnition/robotics/argus/tests/test_main_args.py -q` | `33 passed in 13.08s` | PASS |
| Post-review export schema fix is present | `grep` for `_metric_alias`, production metric keys, and contact aliases in evaluation/export tests | Found aliases for `min_base_height_m`, `max_abs_roll_rad`, `action_delta_norm_mean`, `position_servo_effort_proxy_mean`, `slip_mean_m_per_s`; test covers production-shaped summary | PASS |
| Dedicated CLI dispatch is wired | `grep` for `def run_eval_locomotion_mode`, `eval-locomotion`, `run_evaluation_matrix`, `regenerate_comparison`, `sys.exit` | Found lazy imports/calls and subcommand exit branch in `src/main.py` | PASS |
| Review fix commit included | `git -C /home/prannayag/pragnition/robotics/argus log --oneline -12` | Top commit `de04b16 fix(04): align locomotion evaluation metric exports` present | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| LOC-METRICS-05 | 04-02 | Metrics are exported as JSONL/CSV plus a machine-readable summary suitable for comparing controllers across seeds. | SATISFIED | `steps.jsonl`, `episodes.csv`, `summary.json` written by `_write_artifacts`; tests parse and assert metric fields and summary labels. |
| LOC-EVAL-01 | 04-01, 04-03 | Developer can run a CLI evaluation command that executes a controller across a scenario matrix and fixed seed list. | SATISFIED | Matrix validation/runner plus `eval-locomotion` CLI dispatch with repeated controller/scenario/seed flags. |
| LOC-EVAL-02 | 04-02, 04-03 | Evaluation produces an aggregate comparison table with per-controller mean, standard deviation, and failure counts. | SATISFIED | `aggregate_episode_rows` and Markdown comparison output include per-controller and per-controller/scenario aggregates with mean/std/failure counts. |
| LOC-EVAL-03 | 04-02, 04-03 | Evaluation stores enough metadata to reproduce a run: git commit, controller id, scenario id, seed, environment config, and action mode. | SATISFIED | Manifest includes git commit, matrix/cell/run metadata, environment config, action mode, timestamp, invocation args, and schedules. |
| LOC-EVAL-04 | 04-04 | Evaluation includes regression tests that prevent the analytical trot baseline from silently degrading on the flat-ground smoke scenario. | SATISFIED | Baseline regression test exercises `analytical_trot`/`flat_ground` seeds `(101, 202, 303)` with threshold helper and synthetic degradation tests. |

No orphaned Phase 4 requirements found in `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md`; the Phase 4 traceability entries are exactly LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-03, and LOC-EVAL-04, and all appear in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py` | 130, 141 | `placeholder` text in test name/comment | Info | Intentional requirement wording for unavailable placeholder controllers, not a stub. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | 460, 465 | `return []` | Info | Utility returns empty sequence for absent command schedule; not user-visible placeholder data and overwritten when command info exists. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | 331 | `return {}` | Info | Empty platform config default for non-AGIBOT platform path; unrelated to eval runner and not a stub. |

### Human Verification Required

None. The requested behavior is covered by code inspection and automated tests; no visual, external service, or manual UX verification is required for this phase.

### Gaps Summary

No blocking gaps found. The phase goal is achieved in the codebase. The post-review fix for locomotion metric export schema alignment is present in `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` and is protected by `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py::test_episode_export_maps_production_locomotion_summary_schema`.

---

_Verified: 2026-05-01T05:43:38Z_
_Verifier: Claude (gsd-verifier)_
