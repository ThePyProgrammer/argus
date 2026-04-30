# Phase 4: evaluation-runner-and-regression - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01T01:19:57+08:00
**Phase:** 04-evaluation-runner-and-regression
**Areas discussed:** CLI shape, Export layout, Comparison table, Regression gate

---

## CLI Shape

| Question | Option | Description | Selected |
|---|---|---|---|
| Entry point | Argus subcommand | Add an `argus eval-locomotion` style command under the existing `argus = src.main:main` entry point, keeping one installed CLI while separating benchmark mode from `--control` runtime modes. | ✓ |
| Entry point | Control mode | Add something like `argus --control eval`; smallest parser change, but it mixes offline benchmarking with interactive/simulation control modes. | |
| Entry point | Separate script | Add a focused module/script such as `python -m src.locomotion.evaluate`; clean for tests, but less discoverable than the installed `argus` command. | |
| Matrix input | Repeat flags | Flags like `--controller analytical_trot --scenario flat_ground --seed 1 --seed 2`, with repeatable values for matrices; straightforward for shell scripts and pytest. | |
| Matrix input | Config file | Use a YAML/JSON matrix file as the primary interface; cleaner for large matrices, but adds schema/documentation work and is heavier for Phase 4 smoke runs. | |
| Matrix input | Both, flags first | Support repeat flags now and optional `--matrix-config` for saved configs; flexible, but more surface area to test in this phase. | ✓ |
| Runtime output | Quiet default | Print run start/end and final artifact paths/table only; detailed per-step data goes to JSONL/CSV so CLI output stays stable for tests and scripts. | |
| Runtime output | Progress rows | Print one row per controller/scenario/seed result as it completes; more reassuring for humans, but noisier to snapshot in tests. | |
| Runtime output | Verbose flag | Quiet by default plus `--verbose` for per-run rows and metric snippets; adds one flag but balances automation and debugging. | ✓ |
| Unavailable controllers | Fail fast | Validate all requested controllers before starting any simulation and exit with a clear unavailable-controller error; matches Phase 2 selection semantics. | ✓ |
| Unavailable controllers | Skip unavailable | Warn and continue with available controllers; convenient for broad matrices, but can hide accidental misspellings or deferred-scope leakage. | |
| Unavailable controllers | Require flag | Fail fast by default, with an explicit `--skip-unavailable` escape hatch; flexible, but extra behavior to test. | |

**User's choices:** Argus subcommand; Both, flags first; Verbose flag; Fail fast.
**Notes:** Current code has a single `argus` installed script and an argparse `--control` mode tree; user selected separation from runtime control modes.

---

## Export Layout

| Question | Option | Description | Selected |
|---|---|---|---|
| Directory structure | Run directory | Create one timestamped run directory under `outputs/locomotion-evals/`, containing all run files plus summary; easy to archive and reproduce one invocation. | ✓ |
| Directory structure | Flat outputs | Write files directly to a chosen output directory; simpler paths, but repeated runs can collide or mix artifacts. | |
| Directory structure | Matrix tree | Nested directories by controller/scenario/seed; highly navigable for large sweeps, but more cumbersome for summary-only use. | |
| JSONL contents | Per-step rows | One JSONL row per environment step with run ids, metadata keys, and nested `locomotion_metrics`; this preserves raw time-series data for later analysis. | ✓ |
| JSONL contents | Per-episode rows | One JSONL row per controller/scenario/seed episode summary; compact, but loses per-step behavior needed for debugging regressions. | |
| JSONL contents | Both streams | Write per-step JSONL plus a separate per-episode JSONL; most complete, but duplicates summary data already present in machine-readable summary. | |
| CSV contents | Episode summary | One row per controller/scenario/seed episode with flattened summary metrics; easy to open in spreadsheets and compute controller averages. | ✓ |
| CSV contents | Per-step CSV | Mirror JSONL at per-step granularity; useful for plotting but can get large and awkward with nested metric families. | |
| CSV contents | Aggregate only | Only write per-controller aggregate rows; very compact, but fails the requirement for JSONL/CSV exports with run-level comparability. | |
| Metadata placement | Dedicated manifest | Write a top-level `manifest.json` with git commit, invocation args, env config, matrix, timestamp, file list, and per-run metadata; rows carry compact ids/keys. | ✓ |
| Metadata placement | Every row | Repeat full metadata in every JSONL/CSV row; self-contained rows, but verbose and brittle for large scenario parameters such as heightfields. | |
| Metadata placement | Summary only | Put metadata only in the machine-readable summary; compact, but weaker for standalone JSONL/CSV analysis. | |

**User's choices:** Run directory; Per-step rows; Episode summary; Dedicated manifest.
**Notes:** Phase 3 already exposes terminal episode summaries and nested per-step metrics; exports should preserve those surfaces.

---

## Comparison Table

| Question | Option | Description | Selected |
|---|---|---|---|
| Default emphasis | Scorecard | Compact columns for success rate/failures, tracking RMSE, distance, stability, action smoothness/effort proxy, and contact proxy highlights; good research-facing default. | ✓ |
| Default emphasis | Failure first | Rank and display failures, failure reasons, distance before failure, and success rate first; best for guarding regressions, less broad for controller comparison. | |
| Default emphasis | All metrics | Flatten every summary metric into the table; maximally complete, but wide and harder to read in terminal/Markdown. | |
| Aggregate grouping | Overall + scenario | Compute per-controller overall aggregates plus per-controller/per-scenario breakdowns, all across seeds; satisfies top-level comparison while keeping scenario effects visible. | ✓ |
| Aggregate grouping | Scenario only | Only group by controller and scenario; avoids hiding terrain differences, but lacks a simple overall controller summary. | |
| Aggregate grouping | Overall only | Only group by controller across all scenarios/seeds; simplest, but can mask failures that happen only on slope/rough/push scenarios. | |
| Saved formats | JSON + Markdown | Machine-readable `summary.json` plus a human-readable Markdown comparison table regenerated from artifacts; minimal dependencies and easy to diff. | ✓ |
| Saved formats | JSON + CSV | Machine-readable summary plus aggregate CSV; spreadsheet-friendly, but less directly readable in docs/terminal output. | |
| Saved formats | JSON + both | Produce `summary.json`, aggregate CSV, and Markdown table; most useful, but slightly more export code and tests. | |
| Metric direction | Explicit directions | Include metric direction metadata in `summary.json` and table labels such as `tracking_rmse ↓` and `success_rate ↑`; avoids inventing a composite score. | ✓ |
| Metric direction | Composite rank | Compute an overall rank/score from normalized metrics; convenient but opinionated and risky before more controllers exist. | |
| Metric direction | Raw values only | Show raw values without directions; simplest, but easier to misread for effort/smoothness/failure metrics. | |

**User's choices:** Scorecard; Overall + scenario; JSON + Markdown; Explicit directions.
**Notes:** User selected no composite scoring for this phase.

---

## Regression Gate

| Question | Option | Description | Selected |
|---|---|---|---|
| Regression type | Threshold gate | Run analytical_trot on flat_ground with fixed seed(s) and assert bounded success/failure, tracking RMSE, stability, and distance metrics; robust to tiny physics variation. | ✓ |
| Regression type | Golden snapshot | Compare exported summary to a checked-in golden file with tolerances; stronger drift detection, but more brittle under harmless MuJoCo/numeric changes. | |
| Regression type | Smoke invariants | Only assert command succeeds, exports exist, and no failure occurs; fast and stable, but too weak to catch silent baseline degradation. | |
| Seed coverage | Small fixed set | Use 2–3 fixed seeds for the flat-ground analytical baseline; catches seed-specific breakage without making pytest too slow. | ✓ |
| Seed coverage | Single seed | Fastest and simplest, but weaker against stochastic reset/schedule bugs. | |
| Seed coverage | Full default matrix | Use the same seed list as benchmark defaults; strongest, but can make routine tests slow. | |
| Test split | Fast fake env + one real smoke | Unit-test export/aggregation with fake summaries and add one marked real-env smoke/regression test for analytical flat-ground if MuJoCo assets are available. | ✓ |
| Test split | All real env | Exercise the actual `ArgusGo2Env` for most runner tests; high confidence, but slower and more brittle. | |
| Test split | All fake env | Keep tests fast and deterministic with fake episodes only; validates export logic but not the actual baseline behavior. | |
| Failure exit | Any episode failure exits nonzero | If any requested run terminates by locomotion failure, the command exits nonzero unless explicitly running in report-only mode; prevents regressions from being ignored. | ✓ |
| Failure exit | Always zero if artifacts written | Treat evaluation as measurement only; useful for comparing weak controllers, but bad for the Phase 4 analytical baseline regression gate. | |
| Failure exit | Separate strict flag | Default always writes artifacts and exits zero, with `--strict`/test mode making failures nonzero; flexible but one more mode to document. | |

**User's choices:** Threshold gate; Small fixed set; Fast fake env + one real smoke; Any episode failure exits nonzero.
**Notes:** User selected robust thresholds instead of golden snapshots.

---

## Claude's Discretion

- Exact module names, parser helper structure, timestamp format, flattened CSV column names, default seed values, pytest marker name, and numeric regression thresholds.

## Deferred Ideas

None — discussion stayed within phase scope.
