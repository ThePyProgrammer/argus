# Phase 4: evaluation-runner-and-regression - Research

**Researched:** 2026-05-01  
**Domain:** Python CLI locomotion benchmark runner, artifact export, offline aggregation, pytest regression  
**Confidence:** HIGH for local integration patterns; MEDIUM for exact regression threshold strategy until calibrated against current baseline artifacts.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### CLI Shape
- **D-01:** Add a dedicated `argus eval-locomotion` style subcommand under the existing installed `argus = src.main:main` entry point. Do not model evaluation as another `--control` runtime mode.
- **D-02:** Matrix inputs should be repeatable flags first, e.g. repeated `--controller`, `--scenario`, and `--seed` values, with optional matrix config-file support for larger saved matrices.
- **D-03:** CLI output should be quiet and artifact-focused by default, printing final artifact paths and the comparison table. Add `--verbose` for per-run progress rows and metric snippets.
- **D-04:** Validate all requested controller ids and availability before starting simulation. Placeholder controllers such as residual policy, direct policy, MPC, and WBC must fail fast with clear unavailable-controller errors rather than being skipped or failing mid-run.

### Export Layout
- **D-05:** Each invocation creates one self-contained timestamped run directory under `outputs/locomotion-evals/` containing the manifest, JSONL, CSV, summary, and Markdown comparison artifacts.
- **D-06:** JSONL export contains one row per environment step with run identifiers, compact metadata keys, and the nested `info["locomotion_metrics"]` payload from Phase 3. It is the time-series/debug artifact.
- **D-07:** CSV export is one flattened episode-summary row per controller/scenario/seed run. It should optimize for spreadsheet inspection and controller/scenario/seed comparisons rather than duplicating per-step JSONL.
- **D-08:** Reproducibility metadata lives in a top-level `manifest.json` with git commit, invocation args, matrix, environment/action config, timestamp, file list, and per-run metadata. Row-oriented artifacts should carry compact ids/keys rather than full repeated metadata.

### Comparison Table
- **D-09:** The default comparison table is a compact research-facing scorecard, not a full flattened metric dump. It should emphasize success rate/failure count, tracking RMSE, distance, stability, action smoothness/position-servo effort proxy, and contact/terrain proxy highlights.
- **D-10:** Aggregates include both per-controller overall rows and per-controller/per-scenario rows across seeds, so the top-level comparison remains simple while scenario-specific failures remain visible.
- **D-11:** Saved comparison artifacts are `summary.json` for machine-readable aggregates and a Markdown scorecard/table for human review. They must be regenerable from saved artifacts without rerunning simulation.
- **D-12:** Include metric direction metadata in `summary.json` and table labels such as `tracking_rmse ↓` and `success_rate ↑`. Do not invent a composite controller score in this phase.

### Regression Gate
- **D-13:** The analytical flat-ground baseline regression should be a threshold gate over fixed-seed runs, asserting no locomotion failure plus bounded tracking, stability, and distance metrics. Prefer robust thresholds over golden snapshot comparisons.
- **D-14:** The default regression uses a small fixed seed set, about 2–3 seeds, to catch seed-specific reset/schedule breakage without making routine pytest runs too slow.
- **D-15:** Test strategy should use fast fake-env/unit tests for runner, export, reload, and aggregation behavior, plus one marked real `ArgusGo2Env` analytical flat-ground smoke/regression test when MuJoCo assets are available.
- **D-16:** By default, any evaluated episode that terminates by locomotion failure makes the CLI/evaluation run exit nonzero after artifacts are written. This keeps the analytical regression meaningful and prevents failures from being silently ignored.

### Claude's Discretion
- Exact module names, parser helper structure, timestamp format, flattened CSV column names, default seed values, pytest marker name, and numeric regression thresholds are open to planner/researcher discretion, provided they satisfy the decisions above and preserve the existing project style.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-METRICS-05 | Metrics are exported as JSONL/CSV plus a machine-readable summary suitable for comparing controllers across seeds. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md lines 26-33] | Use Phase 3 `info["locomotion_metrics"]` and terminal `info["locomotion_metrics_summary"]` as the export source; do not recompute metric semantics. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 177-183, 413-425] |
| LOC-EVAL-01 | Developer can run a CLI evaluation command that executes a controller across a scenario matrix and fixed seed list. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md lines 34-37] | Extend `src.main:main` because `pyproject.toml` exposes only `argus = "src.main:main"`; use `ArgusGo2EnvConfig(scenario_id, controller_id, action_mode, max_episode_steps, ...)` for each matrix cell. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 26-27] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 27-37] |
| LOC-EVAL-02 | Evaluation produces an aggregate comparison table with per-controller mean, standard deviation, and failure counts. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md lines 36-38] | Aggregate from episode-summary rows using NumPy means/stds and explicit failure counts; NumPy is already a core dependency. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 6-17] |
| LOC-EVAL-03 | Evaluation stores enough metadata to reproduce a run: git commit, controller id, scenario id, seed, environment config, and action mode. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md lines 38-39] | `ArgusGo2Env._info()` already exposes seed, scenario id, action mode, controller id, sampled parameters, command schedule, and disturbance schedule; add git commit and invocation/config metadata at manifest level. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 454-471] |
| LOC-EVAL-04 | Evaluation includes regression tests that prevent the analytical trot baseline from silently degrading on the flat-ground smoke scenario. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md lines 38-40] | Implement fake-env unit tests for runner/export/aggregation and one marked real-env threshold regression for `analytical_trot` on `flat_ground`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-38] |
</phase_requirements>

## Summary

Phase 4 should add a thin evaluation layer around existing Phase 1-3 locomotion primitives, not a new metrics or controller subsystem. `ArgusGo2Env` already supplies seeded reset/step, scenario metadata, controller id/action mode, per-step nested metrics, and terminal episode summaries, so the runner should orchestrate matrix execution and artifact export while preserving those payloads. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 76-113, 177-183, 454-471]

The standard implementation shape is: CLI subcommand in `src/main.py` -> matrix validation via `ControllerRegistry` and `list_scenarios()` -> runner loop over controller/scenario/seed -> artifact writer -> offline aggregator -> Markdown scorecard. This follows the user-locked CLI/export decisions and the local convention of dataclasses, absolute `src.*` imports, lazy heavy imports, and focused fake-object pytest coverage. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 16-38] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 83-95]

**Primary recommendation:** Implement `src/locomotion/evaluation.py` as the benchmark orchestration/export/aggregation module, wire it behind `argus eval-locomotion`, and make saved artifacts the only source for offline comparison regeneration. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 22-32]

## Project Constraints (from CLAUDE.md)

- The root `CLAUDE.md` contains only the placeholder text “Add your project-specific Claude instructions here,” so no additional actionable project directives were found there. [VERIFIED: /home/prannayag/pragnition/robotics/argus/CLAUDE.md lines 1-3]
- The checked-in `.claude/CLAUDE.md` contains the same placeholder text and adds no actionable project directives. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.claude/CLAUDE.md lines 1-3]
- A project skill named `desloppify` exists, but it applies to code health scanning/technical debt tasks rather than this benchmark-runner research phase; do not run a health scan as part of Phase 4 planning unless the user explicitly scopes code-health work. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.claude/skills/desloppify/SKILL.md lines 1-18]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| CLI benchmark invocation | API / Backend | OS / CLI shell | The `argus` entry point is a Python backend CLI command, not browser/frontend behavior. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 26-27] |
| Matrix validation | API / Backend | Simulation env | Controller ids come from `ControllerRegistry`; scenario ids come from `src.locomotion.scenarios`; fail-fast must happen before environment construction. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 244-313] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/scenarios.py lines 30-64] |
| Simulation execution | API / Backend | MuJoCo runtime | The runner owns orchestration, while `ArgusGo2Env` owns reset/step/metrics/failure semantics. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 39-183] |
| Artifact persistence | Database / Storage | API / Backend | Phase 4 persists JSONL/CSV/JSON/Markdown files under `outputs/locomotion-evals/`; no database is in scope. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 22-32] |
| Offline comparison regeneration | API / Backend | Database / Storage | Aggregation must read saved artifacts and must not instantiate or step `ArgusGo2Env`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 30-32, 93-94] |
| Analytical regression gate | API / Backend | Test runner | Pytest should invoke the evaluation logic and assert threshold behavior; the gate is not a runtime UI feature. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-38] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `argparse` | Python 3.10-3.12 project range | CLI subcommand parsing | Existing `src/main.py` already uses `argparse`; extending it minimizes CLI churn. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/main.py lines 27-193] [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml line 5] |
| Python stdlib `json`, `csv`, `pathlib`, `datetime`, `subprocess` | Python 3.10-3.12 project range | Manifest/summary JSON, JSONL rows, CSV rows, filesystem paths, git commit lookup | These are sufficient for Phase 4 exports and avoid adding dependencies for simple file formats. [ASSUMED] |
| NumPy | Installed 2.4.3; latest 2.4.4 from PyPI probe | Mean/std aggregation and finite numeric handling | NumPy is already a core project dependency and is used throughout locomotion/env/metrics code. [VERIFIED: pip index versions numpy] [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 6-17] |
| Gymnasium | Installed/latest 1.3.0 from PyPI probe | Existing `ArgusGo2Env` API contract | `ArgusGo2Env` subclasses `gymnasium.Env`, and Gymnasium reset requires returning `(observation, info)` with `super().reset(seed=seed)` for custom env seeding. [VERIFIED: pip index versions gymnasium] [VERIFIED: Context7 /websites/gymnasium_farama reset docs] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 9, 39, 76-113] |
| MuJoCo | Installed 3.6.0; latest 3.8.0 from PyPI probe | Real analytical flat-ground regression execution | `ArgusGo2Env` lazily imports MuJoCo and loads Go2 MJCF when real simulation is available. [VERIFIED: pip index versions mujoco] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 223-246] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | Installed 9.0.2; latest 9.0.3 from PyPI probe | Unit/regression test runner | Use `tmp_path` for artifact tests and `monkeypatch` for fake runner/env seams. [VERIFIED: pip index versions pytest] [VERIFIED: Context7 /pytest-dev/pytest tmp_path and monkeypatch docs] |
| pytest-timeout | Existing dev dependency `>=2.0.0` / dependency group `>=2.4.0` | Guard slow/hung simulation tests | Existing `pytest.ini` sets a 30s timeout. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 41-45, 54-59] [VERIFIED: /home/prannayag/pragnition/robotics/argus/pytest.ini lines 1-9] |
| git CLI | Installed 2.54.0 | Capture reproducibility commit hash | Manifest should record `git rev-parse HEAD` output or a clear unavailable marker if not in a git worktree. [VERIFIED: environment probe `git --version`] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 27-28] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `argparse` | Typer/Click | Better CLI ergonomics, but would add dependency and diverge from existing `src/main.py` style. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/main.py lines 27-193] |
| stdlib `csv`/`json` | pandas | Pandas would simplify tabular analysis, but Phase 4 only needs simple row export and aggregate stats; adding it is unnecessary dependency weight. [ASSUMED] |
| JSONL per-step + CSV per-episode | One giant CSV | One giant CSV duplicates nested per-step payloads poorly; CONTEXT locks JSONL for time-series/debug and CSV for episode summaries. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 22-28] |
| Threshold regression | Golden artifact snapshots | CONTEXT explicitly prefers robust thresholds over golden snapshots. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-36] |

**Installation:** No new runtime packages are recommended; use existing project dependencies. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 6-17]

**Version verification performed:** `pip index versions gymnasium pytest numpy mujoco` and `.venv/bin/python` package metadata probes were run on 2026-05-01. [VERIFIED: tool output in research session]

## Architecture Patterns

### System Architecture Diagram

```text
argus eval-locomotion CLI
  |
  v
Parse repeated flags / optional matrix file
  |
  v
Validate full matrix before simulation
  |-- controllers -> ControllerRegistry.list_controllers()/create availability
  |-- scenarios   -> list_scenarios()
  |-- seeds/config/action mode -> finite/type/range validation
  |
  v
Create timestamped outputs/locomotion-evals/<run-id>/
  |
  v
For each controller x scenario x seed:
  ArgusGo2Env(ArgusGo2EnvConfig(...))
    -> reset(seed)
    -> step(action) until terminated/truncated
    -> collect info["locomotion_metrics"] per step
    -> collect info["locomotion_metrics_summary"] at terminal boundary
  |
  v
Write artifacts
  |-- steps.jsonl       one row per env step
  |-- episodes.csv      one row per controller/scenario/seed
  |-- manifest.json     reproducibility metadata and file list
  |-- summary.json      aggregate means/std/failure counts + metric directions
  |-- comparison.md     compact human scorecard
  |
  v
CLI prints artifact paths + compact comparison table

Saved artifact reload path:
  existing run directory -> read episodes.csv/manifest.json -> rebuild summary.json/comparison.md
  (must not instantiate ArgusGo2Env)
```

### Recommended Project Structure

```text
src/
├── main.py                         # add eval-locomotion subcommand/dispatch branch
└── locomotion/
    ├── evaluation.py               # runner dataclasses, matrix validation, artifact export, aggregation
    ├── env.py                      # consume existing reset/step/metrics surface unchanged unless small accessor needed
    ├── controllers.py              # existing controller registry/availability source
    └── scenarios.py                # existing scenario catalog source

tests/
└── locomotion/
    ├── test_locomotion_evaluation_runner.py      # fake-env runner/matrix/failure behavior
    ├── test_locomotion_evaluation_exports.py     # JSONL/CSV/manifest/summary/reload tests using tmp_path
    └── test_locomotion_baseline_regression.py    # marked real ArgusGo2Env analytical flat-ground threshold gate
```

This structure keeps Phase 4 orchestration in `src/locomotion/evaluation.py` while preserving the established `src.*` absolute import style. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 83-95] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-PATTERNS.md lines 847-865]

### Pattern 1: Matrix Validation Before Side Effects

**What:** Validate all controller ids, controller availability, scenario ids, seed list, action mode, and output directory strategy before constructing any env or writing artifacts. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 16-21]

**When to use:** Always at the start of `eval-locomotion`; unavailable placeholder controllers must raise clear errors before the first simulation cell. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 289-313, 467-488]

**Example:**
```python
# Source: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 289-313
if name not in cls._controllers:
    raise ValueError(
        f"Unknown locomotion controller '{name}'. Available: {list(cls._controllers.keys())}"
    )
available, reason = _probe_availability(klass)
if not available:
    raise UnavailableControllerError(
        f"Controller '{name}' is unavailable: "
        f"{reason or f'{klass.__qualname__}.available() reported unavailable'}"
    )
```

### Pattern 2: Export Existing Metric Payloads, Do Not Recompute

**What:** JSONL rows should carry `info["locomotion_metrics"]`; CSV rows should flatten terminal `info["locomotion_metrics_summary"]`; summary aggregation should operate on those saved episode rows. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 22-32]

**When to use:** Every benchmark run and offline reload path. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 91-94]

**Example:**
```python
# Source: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 177-183
info = self._info()
info["locomotion_metrics"] = self._metrics.latest_info_payload()
if terminated or truncated:
    summary = self._locomotion_summary_payload()
    self._last_locomotion_metrics_summary = copy.deepcopy(summary)
    info["locomotion_metrics_summary"] = summary
```

### Pattern 3: Saved Artifacts Are the Offline Comparison API

**What:** Provide a function like `regenerate_comparison(run_dir: Path)` that reads manifest + episode CSV or summary JSON and rewrites `summary.json`/`comparison.md` without constructing `ArgusGo2Env`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 30-32, 93-94]

**When to use:** CLI reload/regenerate mode and unit tests that assert no simulation rerun. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 37-38]

### Anti-Patterns to Avoid

- **Putting evaluation behind `--control`:** User locked a distinct `eval-locomotion` subcommand; `--control` is for runtime modes like web/explore/multi. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 16-18] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/main.py lines 89-193]
- **Skipping unavailable placeholders:** Placeholder controllers must fail fast and must not be silently skipped. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 19-21]
- **Recomputing Phase 3 metrics in the exporter:** Phase 4 consumes Phase 3 records/summaries; it does not redefine metric semantics. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 6-10]
- **Composite controller score:** CONTEXT forbids inventing a composite score in this phase. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 31-32]
- **Golden snapshot regression:** CONTEXT prefers threshold gates over golden snapshots for the analytical baseline. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-36]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI parsing | Custom `sys.argv` parser | Existing `argparse` style in `src/main.py` | Project already uses `argparse`; subcommands can be added without dependency churn. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/main.py lines 27-193] |
| Controller discovery | New controller registry/list | `ControllerRegistry` | It already lists metadata, availability, deterministic flag, parameter hash, and raises unavailable-controller errors. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 229-313] |
| Scenario catalog | New scenario config namespace | `list_scenarios()` and `sample_scenario()` | Existing scenario module owns valid ids and deterministic sampling. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/scenarios.py lines 30-64, 106-137] |
| Locomotion metrics | New tracker math | `info["locomotion_metrics"]` and `info["locomotion_metrics_summary"]` | Phase 3 already validates command tracking, stability, action quality, and contact/terrain families. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/metrics.py lines 237-269] |
| Aggregation math | Bespoke streaming stats | NumPy `mean`, `std`, counts over saved episode rows | NumPy is already available and sufficient for small benchmark matrices. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 6-17] |
| Artifact tests | Manual temp directory cleanup | pytest `tmp_path` | `tmp_path` is the standard pytest fixture for per-test temp directories. [VERIFIED: Context7 /pytest-dev/pytest tmp_path docs] |

**Key insight:** The hard part is preserving provenance and failure semantics, not inventing more math; use the existing env/controller/scenario/metrics contracts and make artifact generation deterministic and reloadable. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/STATE.md lines 48-56]

## Common Pitfalls

### Pitfall 1: Silent partial matrices
**What goes wrong:** The CLI starts running valid cells and only later discovers a bad controller/scenario. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 19-21]  
**Why it happens:** Validation is interleaved with execution. [ASSUMED]  
**How to avoid:** Build and validate the full matrix first; only then create the run directory and environments. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 16-21]  
**Warning signs:** Tests need to clean up partial artifacts after invalid input. [ASSUMED]

### Pitfall 2: Artifact metadata bloat and inconsistency
**What goes wrong:** Full environment/controller metadata is repeated in every JSONL/CSV row, and rows drift from the manifest. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 23-28]  
**Why it happens:** Export code treats row files as the manifest. [ASSUMED]  
**How to avoid:** Put full reproducibility metadata in `manifest.json`; rows carry compact run ids and matrix keys. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 23-28]  
**Warning signs:** CSV headers include large nested config blobs. [ASSUMED]

### Pitfall 3: Re-running simulation during comparison reload
**What goes wrong:** `summary.json` or Markdown regeneration changes results because it reruns physics. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 30-32]  
**Why it happens:** Aggregation function accepts matrix inputs instead of artifact paths. [ASSUMED]  
**How to avoid:** Separate `run_matrix(...)` from `load_episode_rows(...)` and `write_comparison(...)`; unit-test reload with a fake env constructor that raises if called. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 91-94]  
**Warning signs:** Offline comparison tests import or instantiate `ArgusGo2Env`. [ASSUMED]

### Pitfall 4: Regression thresholds that are either brittle or toothless
**What goes wrong:** A harmless MuJoCo numeric change fails the test, or a real baseline degradation still passes. [ASSUMED]  
**Why it happens:** Thresholds are picked without looking at current multi-seed baseline distribution. [ASSUMED]  
**How to avoid:** First run the fixed seed smoke matrix, inspect tracking/stability/distance summary ranges, then set explicit upper/lower bounds with margin and document the calibration artifact in the test comment. [ASSUMED]  
**Warning signs:** Thresholds equal exact current floating-point values or are broad enough to pass a stationary/failing robot. [ASSUMED]

### Pitfall 5: Exit-code failure before artifact write
**What goes wrong:** A failed locomotion episode exits nonzero but no artifacts remain for debugging. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-39]  
**Why it happens:** The runner raises immediately on terminated episodes. [ASSUMED]  
**How to avoid:** Record the failed episode, finish writing manifest/JSONL/CSV/summary/Markdown, then return nonzero from the CLI. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-39]  
**Warning signs:** Failure-path tests assert only exceptions and not artifact existence. [ASSUMED]

## Code Examples

### Gymnasium Reset Seeding Contract
```python
# Source: Context7 /websites/gymnasium_farama reset docs
# Custom env reset should call this before using self.np_random.
super().reset(seed=seed)
```

### Current Env Metric Export Surface
```python
# Source: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 177-183
info["locomotion_metrics"] = self._metrics.latest_info_payload()
if terminated or truncated:
    summary = self._locomotion_summary_payload()
    self._last_locomotion_metrics_summary = copy.deepcopy(summary)
    info["locomotion_metrics_summary"] = summary
```

### Current Reproducibility Info Surface
```python
# Source: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 454-471
info = {
    "seed": self._last_seed,
    "scenario_id": sample.scenario_id if sample is not None else self.config.scenario_id,
    "action_mode": self.config.action_mode,
    "controller_id": self.config.controller_id,
    "step_count": self._step_count,
    "sim_time": self._current_sim_time(),
    "spawn_pose": sample.spawn_pose if sample is not None else None,
    "sampled_parameters": dict(sample.terrain_parameters) if sample is not None else {},
    "command_schedule": tuple(dict(item) for item in sample.command_schedule) if sample is not None else (),
    "disturbance_schedule": tuple(dict(item) for item in sample.disturbance_schedule) if sample is not None else (),
    "active_push": dict(self._active_push) if self._active_push is not None else None,
}
```

### Pytest Artifact Fixture Pattern
```python
# Source: Context7 /pytest-dev/pytest tmp_path docs
def test_export_writes_manifest(tmp_path):
    run_dir = tmp_path / "locomotion-eval"
    run_dir.mkdir()
    manifest = run_dir / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    assert manifest.read_text(encoding="utf-8") == "{}"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Visual demo / ad hoc logs | Gymnasium-style env with scenario/seed/controller/metrics contracts | v4.0 Phase 1-3, 2026-04-30 | Phase 4 should orchestrate and export, not create a new simulation boundary. [VERIFIED: /home/prannayag/pragnition/robotics/argus/docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md lines 21-30] |
| Hidden analytical trot bridge behavior | Registered `analytical_trot` controller with metadata and availability | v4.0 Phase 2, 2026-04-30 | CLI can validate/select controllers through one registry. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 397-443] |
| Metric semantics in future/export code | Phase 3 nested per-step and terminal summaries | v4.0 Phase 3, 2026-04-30 | Exporter should copy payloads and aggregate saved episode summaries. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 177-183, 413-425] |
| Adding RL/MPC/WBC first | Benchmark before controller sophistication | ADR-0019, 2026-04-30 | Placeholder controllers remain unavailable; Phase 4 must not implement advanced controller families. [VERIFIED: /home/prannayag/pragnition/robotics/argus/docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md lines 31-42] |

**Deprecated/outdated:**
- Treating `--control` as the place for every runtime behavior is wrong for this phase; `eval-locomotion` is a separate benchmark command. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 16-18]
- Golden-file regression is not the selected baseline guard; use threshold assertions. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-36]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python stdlib `json`, `csv`, `pathlib`, `datetime`, and `subprocess` are sufficient for Phase 4 export/metadata needs. | Standard Stack | Planner might miss an edge case requiring a helper dependency, though current formats are simple. |
| A2 | Pandas is unnecessary for the required CSV/summary aggregation. | Alternatives Considered | If matrices become large or users require richer tabular analysis, planner may under-scope tooling. |
| A3 | Validation interleaving, metadata bloat, reload reruns, and artifact-loss failure paths are likely implementation risks. | Common Pitfalls | Planner may over-index on tests for risks that are conventional rather than already observed in code. |
| A4 | Regression thresholds should be calibrated from current multi-seed baseline distribution rather than chosen upfront in research. | Common Pitfalls / Open Questions | Planner must include calibration work before locking numeric bounds. |

## Open Questions

1. **Exact numeric analytical-baseline thresholds**
   - What we know: The regression must assert no locomotion failure plus bounded tracking, stability, and distance metrics over about 2-3 fixed seeds. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-37]
   - What's unclear: Current baseline distribution for the selected smoke seeds was not executed during research. [ASSUMED]
   - Recommendation: Add a Wave 0 calibration task that runs `analytical_trot`/`flat_ground` for chosen seeds and records threshold rationale in the regression test comment. [ASSUMED]

2. **Optional matrix config-file format**
   - What we know: Repeated flags are primary; config-file support is optional for larger matrices. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 16-19]
   - What's unclear: No locked schema or dependency for YAML/TOML was provided. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 40-42]
   - Recommendation: Implement flags first; if config-file support is included, prefer JSON via stdlib unless user asks for YAML/TOML. [ASSUMED]

3. **Pytest marker name for real MuJoCo regression**
   - What we know: Existing marker set includes `integration`, `unit`, `slow_boxer`, `network`, and `x2_asset`; default addopts only exclude slow_boxer/network. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pytest.ini lines 1-17]
   - What's unclear: Whether the baseline regression should run by default or be opt-in depends on actual runtime. [ASSUMED]
   - Recommendation: Use `@pytest.mark.integration` first and keep the smoke max-steps/seed count small enough for the existing 30s timeout; add a dedicated marker only if runtime exceeds routine test expectations. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `.venv/bin/python` | Project-supported test/runtime interpreter | ✓ | Python 3.12.13 | Use project venv; global Python 3.14.4 is outside `>=3.10,<3.13`. [VERIFIED: environment probe] [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml line 5] |
| NumPy | Aggregation and existing env/metrics code | ✓ | 2.4.3 installed | None needed. [VERIFIED: environment probe] |
| Gymnasium | `ArgusGo2Env` | ✓ | 1.3.0 installed | Blocking if missing because env subclass imports it. [VERIFIED: environment probe] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/env.py lines 9, 39] |
| MuJoCo | Real flat-ground analytical regression | ✓ | 3.6.0 installed | Unit tests can use fakes, but real regression needs MuJoCo/assets. [VERIFIED: environment probe] |
| pytest | Phase validation | ✓ | 9.0.2 installed | Use `.venv/bin/python -m pytest` to bind interpreter/deps. [VERIFIED: environment probe] |
| git CLI | Manifest commit metadata | ✓ | 2.54.0 | If unavailable, manifest should record `git_commit: null` plus an error string. [VERIFIED: environment probe] [ASSUMED] |

**Missing dependencies with no fallback:** None found for this phase. [VERIFIED: environment probe]

**Missing dependencies with fallback:** None found; fake-env unit tests remain fallback coverage if MuJoCo/assets are unavailable in a different environment. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-38]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 installed; project dev dependency requires pytest `>=8.0.0`. [VERIFIED: environment probe] [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 41-45] |
| Config file | `/home/prannayag/pragnition/robotics/argus/pytest.ini`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pytest.ini lines 1-17] |
| Quick run command | `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` [ASSUMED] |
| Full suite command | `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion tests/test_main_args.py tests/test_main_platform_args.py -q` [ASSUMED] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| LOC-METRICS-05 | JSONL/CSV/summary artifacts are written with expected row shape and metric payload source | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | ❌ Wave 0 |
| LOC-EVAL-01 | CLI/runner executes controller x scenario x seed matrix and validates unavailable ids before simulation | unit + CLI smoke | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/test_main_args.py -q` | ❌ Wave 0 |
| LOC-EVAL-02 | Aggregate table has per-controller and per-controller/per-scenario mean/std/failure counts | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | ❌ Wave 0 |
| LOC-EVAL-03 | Manifest contains git commit, invocation args, matrix, env/action config, timestamp, file list, and per-run metadata | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | ❌ Wave 0 |
| LOC-EVAL-04 | Analytical trot flat-ground smoke seeds pass thresholds and fail on synthetic degradation | integration + fake unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** quick run command above plus any touched existing test file. [ASSUMED]
- **Per wave merge:** full suite command above. [ASSUMED]
- **Phase gate:** `.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/test_main_args.py -q` to preserve Phase 1-3 locomotion/bridge contracts and CLI parsing. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/STATE.md lines 35-39]

### Wave 0 Gaps

- [ ] `tests/locomotion/test_locomotion_evaluation_runner.py` — covers matrix validation, fake-env execution, failure exit semantics, unavailable controller errors. [ASSUMED]
- [ ] `tests/locomotion/test_locomotion_evaluation_exports.py` — covers JSONL/CSV/manifest/summary/Markdown and reload-without-rerun. [ASSUMED]
- [ ] `tests/locomotion/test_locomotion_baseline_regression.py` — covers real analytical flat-ground threshold regression plus synthetic threshold failure helper. [ASSUMED]
- [ ] Optional pytest marker registration only if a new marker beyond `integration` is chosen. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pytest.ini lines 12-17]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No authentication boundary is introduced by a local CLI benchmark runner. [ASSUMED] |
| V3 Session Management | no | No sessions/cookies/tokens are introduced by this phase. [ASSUMED] |
| V4 Access Control | no | CLI writes local artifacts under a fixed output root; no multi-user authorization model is introduced. [ASSUMED] |
| V5 Input Validation | yes | Validate controller ids via `ControllerRegistry`, scenario ids via `list_scenarios()`, seeds/config as finite typed values, and output paths under the intended run directory. [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 289-313] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/scenarios.py lines 62-64, 121-124] |
| V6 Cryptography | no | No cryptographic primitive is needed; git commit hash is provenance metadata, not security proof. [ASSUMED] |

### Known Threat Patterns for Python CLI Artifact Export

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal or accidental overwrite from user-supplied output/run-id | Tampering | Resolve output paths under `outputs/locomotion-evals/`, create new timestamped directories, and avoid accepting arbitrary artifact filenames by default. [ASSUMED] |
| CSV formula injection when opened in spreadsheets | Tampering | Prefix/sanitize string cells beginning with `=`, `+`, `-`, or `@` if user-controlled strings can reach CSV cells. [ASSUMED] |
| Misleading reproducibility metadata | Repudiation | Record git commit, invocation args, matrix, env/action config, timestamp, file list, per-run metadata, and controller parameter hashes. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 27-28] [VERIFIED: /home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py lines 153-166] |
| Resource exhaustion from huge matrices | Denial of Service | Validate matrix size and print planned run count before execution; optionally require explicit confirmation/flag for very large matrices. [ASSUMED] |

## Sources

### Primary (HIGH confidence)

- `/home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md` — locked Phase 4 decisions, code context, specific ideas. [VERIFIED: local file]
- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` — LOC-METRICS-05 and LOC-EVAL requirements. [VERIFIED: local file]
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` — milestone decisions, current focus, validation history. [VERIFIED: local file]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/env.py` — existing env reset/step/info/metrics summary surface. [VERIFIED: local file]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py` — controller registry, metadata, availability, unavailable placeholders. [VERIFIED: local file]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/metrics.py` — Phase 3 metric families and summary payload structure. [VERIFIED: local file]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/scenarios.py` — scenario catalog and deterministic sampling. [VERIFIED: local file]
- `/websites/gymnasium_farama` via Context7 CLI — Gymnasium reset/seed/custom env docs. [VERIFIED: Context7]
- `/pytest-dev/pytest` via Context7 CLI — pytest `tmp_path` and `monkeypatch` fixtures. [VERIFIED: Context7]

### Secondary (MEDIUM confidence)

- PyPI/package probes via `pip index versions` and `.venv/bin/python` metadata — current and installed package versions. [VERIFIED: environment probe]
- ADR-0018 and ADR-0019 — architecture/process rationale for benchmark-first locomotion. [VERIFIED: local files]

### Tertiary (LOW confidence)

- Assumed implementation-risk and security patterns where no phase-specific exploit/history exists. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing Python/stdlib/NumPy/Gymnasium/MuJoCo/pytest stack is already in `pyproject.toml` and installed in the venv. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml lines 5-17, 41-45] [VERIFIED: environment probe]
- Architecture: HIGH — Phase 4 is directly constrained by CONTEXT and existing env/controller/scenario/metrics modules. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 71-96]
- Pitfalls: MEDIUM — several risks are locked by CONTEXT, but threshold calibration and some exporter/security pitfalls are conventional assumptions pending implementation. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md lines 34-39] [ASSUMED]

**Graph context:** Planning graph tooling is disabled in this environment, so no graph-derived relationships were used. [VERIFIED: graphify status tool output]

**Research date:** 2026-05-01  
**Valid until:** 2026-05-31 for local architecture patterns; 2026-05-08 for package-version currency in fast-moving dependencies.
