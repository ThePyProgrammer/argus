# Phase 6: repair-evaluation-runner-semantics - Research

**Researched:** 2026-05-01  
**Domain:** Python robotics evaluation runner semantics, MuJoCo/Gymnasium-style locomotion harness, pytest regression gates  
**Confidence:** HIGH

## User Constraints

No `06-CONTEXT.md` exists for this phase, so there are no user-locked decisions, Claude discretion entries, or deferred ideas to copy verbatim. [VERIFIED: gsd-sdk init.phase-op 6]

Phase 6 is constrained by the roadmap goal: repair real evaluation semantics so scenario command schedules, exported distance metrics, and analytical baseline thresholds measure actual locomotion behavior. [VERIFIED: .planning/ROADMAP.md]

The phase must address LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, and LOC-EVAL-04. [VERIFIED: .planning/REQUIREMENTS.md]

The AI-SPEC selects Claude Agent SDK only as developer-assistance guidance and explicitly says not to add an LLM runtime dependency to the robotics evaluator. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md]

Security enforcement is active because `.planning/config.json` does not disable security enforcement, and nyquist validation is enabled because `workflow.nyquist_validation` is `true`. [VERIFIED: .planning/config.json]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-METRICS-05 | Metrics are exported as JSONL/CSV plus a machine-readable summary suitable for comparing controllers across seeds. [VERIFIED: .planning/REQUIREMENTS.md] | Use existing `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md` paths, but flatten `distance_xy_m` from `summary["stability"]`, not `summary["command_tracking"]`. [VERIFIED: src/locomotion/evaluation.py; src/locomotion/metrics.py] |
| LOC-EVAL-01 | CLI evaluation executes a controller across a scenario matrix and fixed seed list. [VERIFIED: .planning/REQUIREMENTS.md] | Preserve existing `EvaluationMatrix` expansion and `argus eval-locomotion` surface while fixing per-step active-command selection for real and fake envs. [VERIFIED: src/locomotion/evaluation.py; src/main.py] |
| LOC-EVAL-02 | Evaluation produces aggregate comparison with per-controller mean, standard deviation, and failure counts. [VERIFIED: .planning/REQUIREMENTS.md] | Existing aggregation computes mean/std/failure_count by controller and by controller/scenario; the plan must ensure the corrected distance value reaches the aggregation inputs. [VERIFIED: src/locomotion/evaluation.py] |
| LOC-EVAL-04 | Evaluation includes regression tests that prevent analytical trot baseline silent degradation on flat-ground smoke. [VERIFIED: .planning/REQUIREMENTS.md] | Existing baseline thresholds only reject zero distance when `commanded_velocity` is translationally nonzero; the plan must force scheduled nonzero commands into rows and add a stationary/command-ignoring negative fixture. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py] |

## Summary

Phase 6 is a targeted semantic repair, not a new subsystem. The existing evaluation runner already validates controller/scenario/seed matrices, writes artifact files, regenerates comparison artifacts offline, and has a flat-ground baseline threshold helper. [VERIFIED: src/locomotion/evaluation.py; tests/locomotion/test_locomotion_evaluation_runner.py; tests/locomotion/test_locomotion_evaluation_exports.py; tests/locomotion/test_locomotion_baseline_regression.py] The audit found two Phase 6 blockers: evaluation action/export command selection currently falls back to `command_schedule[0]`, and episode CSV flattening reads `distance_xy_m` from `command_tracking` even though production metrics put it under `stability`. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md; src/locomotion/evaluation.py; src/locomotion/metrics.py]

The smallest safe plan is to make `ArgusGo2Env._info()` expose a `current_command` payload computed from current simulation time, make `evaluation.py` prefer that payload for action generation and exported command fields, and change `_episode_csv_row()` to flatten distance from the stability summary family. [VERIFIED: src/locomotion/env.py; src/locomotion/evaluation.py; src/locomotion/metrics.py] The current env already has a private `_command_at_time(sim_time)` helper for schedule lookup, so planning should reuse it rather than duplicate command-selection logic in the runner. [VERIFIED: src/locomotion/env.py]

Acceptance should be deterministic pytest and artifact assertions, not prose or an AI eval stack. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md] The local environment currently lacks installed `gymnasium`, `mujoco`, and `pytest-timeout` packages and is running Python 3.14.4 even though `pyproject.toml` requires Python `>=3.10,<3.13`, so real MuJoCo smoke may be unavailable here unless the repository virtualenv is used or dependencies are installed under a supported Python. [VERIFIED: package-version probe; pyproject.toml]

**Primary recommendation:** Plan one implementation wave that fixes active-command propagation and stability-distance flattening, followed by a validation wave that adds failing-before/passing-after tests for schedule transitions, artifact distance preservation, aggregate comparison, and stationary-controller rejection. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md; .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md]

## Project Constraints (from CLAUDE.md)

The project `CLAUDE.md` only contains placeholder text: “Add your project-specific Claude instructions here.” [VERIFIED: /home/prannayag/pragnition/robotics/argus/CLAUDE.md]

No actionable project-specific directives, required tools, forbidden patterns, coding conventions, testing rules, or security requirements were present in the checked `CLAUDE.md`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/CLAUDE.md]

A project skill exists at `.claude/skills/desloppify/SKILL.md`, but it is for code-health scanning and technical-debt workflows; Phase 6 planning should account for its bias toward honest evidence and code health, but the skill does not require running a desloppify scan for this research task. [VERIFIED: .claude/skills/desloppify/SKILL.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Active scenario command lookup | API / Backend | Simulation environment | `ArgusGo2Env` owns simulation time and already implements `_command_at_time`; the runner should consume env-provided `current_command` instead of reimplementing schedule timing. [VERIFIED: src/locomotion/env.py] |
| Velocity action generation during evaluation | API / Backend | Controller adapter | `run_evaluation_matrix()` generates velocity-mode actions from info payloads and passes them to `env.step()`. [VERIFIED: src/locomotion/evaluation.py] |
| Metrics collection and distance source of truth | Simulation environment | Metrics collector | `LocomotionMetricsCollector.episode_summary()` stores `distance_xy_m` in `stability`; env terminal info relays that nested summary. [VERIFIED: src/locomotion/metrics.py; src/locomotion/env.py] |
| Artifact flattening and aggregation | API / Backend | Filesystem artifacts | `evaluation.py` writes JSONL/CSV/summary/comparison artifacts and aggregates episode rows. [VERIFIED: src/locomotion/evaluation.py] |
| CLI input surface | API / Backend | CLI process | `src/main.py` parses `eval-locomotion` flags and constructs `EvaluationMatrix`/`EvaluationRunConfig`. [VERIFIED: src/main.py] |
| Regression gates | Test suite | CI runtime | Existing locomotion tests use pytest and fixtures such as fake envs and `tmp_path` to prove runner/export/baseline behavior. [VERIFIED: tests/locomotion/*.py; Context7 /pytest-dev/pytest] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | Project requires `>=3.10,<3.13`; local `python3` is 3.14.4 | Runtime for evaluator and tests | Project package metadata pins supported Python; MuJoCo smoke tests in this repo skip outside Python `>=3.10,<3.13`. [VERIFIED: pyproject.toml; package-version probe; tests/locomotion/test_locomotion_baseline_regression.py] |
| pytest | Project dev dependency `>=8.0.0`; locally installed 9.0.2 | Unit/integration regression tests | Pytest provides `tmp_path`, `monkeypatch`, `pytest.raises`, parametrization, and assertion introspection patterns already used by this repo. [VERIFIED: pyproject.toml; package-version probe; Context7 /pytest-dev/pytest] |
| numpy | Project dependency `>=1.26.0`; locally installed 2.4.4 | Numeric vectors for actions, commands, metrics | Existing env/evaluation/metrics code uses NumPy arrays for commands, actions, finite checks, and aggregation. [VERIFIED: pyproject.toml; src/locomotion/env.py; src/locomotion/evaluation.py; src/locomotion/metrics.py] |
| gymnasium | Project dependency `>=1.3.0`; not locally installed in probed Python | Gymnasium-style env API and action spaces | `ArgusGo2Env` subclasses `gymnasium.Env` and uses Gymnasium-style reset/step semantics required by LOC-ENV. [VERIFIED: pyproject.toml; src/locomotion/env.py; .planning/REQUIREMENTS.md] |
| mujoco | Project dependency `>=3.0.0`; not locally installed in probed Python | Real Go2 simulation smoke path | Env imports MuJoCo lazily for real stepping; baseline regression skips when MuJoCo is missing or Python is unsupported. [VERIFIED: pyproject.toml; src/locomotion/env.py; tests/locomotion/test_locomotion_baseline_regression.py] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | Python stdlib | Safe artifact path creation and containment checks | Keep `_prepare_run_dir()` using resolved roots and containment checks before writes. [CITED: https://docs.python.org/3/library/pathlib.html] |
| csv/json | Python stdlib | Artifact export and reload | Preserve current JSONL/CSV/summary/comparison stack; do not add pandas for this repair. [VERIFIED: src/locomotion/evaluation.py] |
| pytest-timeout | Project dev dependency `>=2.0.0`; not locally installed in probed Python | Bound test runtime via `pytest.ini` timeout | The repository config uses `timeout = 30`; local missing plugin means a clean dev environment install is needed for parity. [VERIFIED: pyproject.toml; pytest.ini; package-version probe] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reusing `ArgusGo2Env._command_at_time()` and exposing `current_command` | Recompute schedule timing in `evaluation.py` | Duplicates time semantics outside the env and risks mismatch between action command and metrics command. [VERIFIED: src/locomotion/env.py; src/locomotion/evaluation.py] |
| Existing stdlib CSV/JSON artifacts | pandas DataFrame exports | Adds dependency and migration surface for a two-field semantic repair. [VERIFIED: src/locomotion/evaluation.py; pyproject.toml] |
| Deterministic pytest fixtures | LLM/Claude Agent SDK runtime evals | AI-SPEC explicitly says Claude Agent SDK is developer-only and acceptance is deterministic pytest/artifact output. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md] |

**Installation:**
```bash
python -m pip install -e ".[dev]"
```

**Version verification:** Recommended package versions were verified from project metadata and local import metadata, not npm registry, because this is a Python package. [VERIFIED: pyproject.toml; package-version probe]

## Architecture Patterns

### System Architecture Diagram

```text
CLI: argus eval-locomotion
  -> parse matrix flags / optional matrix config
  -> validate controllers, scenarios, seeds, run count
  -> for each controller x scenario x seed cell
      -> ArgusGo2Env.reset(seed)
          -> sample scenario command schedule
          -> emit reset info: schedule + current_command at t=0
      -> loop until terminated/truncated
          -> evaluator reads latest info.current_command
          -> evaluator sends velocity action matching active command
          -> ArgusGo2Env.step(action)
              -> update command, step MuJoCo/fake env, record metrics
              -> emit step info: sim_time + current_command + nested metrics
          -> evaluator writes step row with same command source/vector
      -> terminal summary
          -> metrics summary: stability.distance_xy_m is source of truth
          -> episode CSV row flattens stability.distance_xy_m
  -> write manifest.json + steps.jsonl + episodes.csv
  -> aggregate episodes.csv rows into summary.json and comparison.md
  -> baseline pytest asserts nonzero command implies nonzero distance
```

### Recommended Project Structure

```text
src/locomotion/
├── env.py          # expose current_command in _info(); keep schedule-time logic here
├── evaluation.py   # consume current_command; flatten stability.distance_xy_m; write artifacts
├── metrics.py      # unchanged source of truth for stability.distance_xy_m unless tests reveal schema bug
└── scenarios.py    # unchanged deterministic command schedule sampling unless tests reveal boundary bug

tests/locomotion/
├── test_locomotion_evaluation_runner.py      # active command action-generation fixtures
├── test_locomotion_evaluation_exports.py     # distance preservation and artifact schema fixtures
└── test_locomotion_baseline_regression.py    # stationary-controller rejection and real smoke gate
```

### Pattern 1: Env-owned active command payload

**What:** Compute the active command from env simulation time and include it in `info["current_command"]` with `vx`, `vy`, `omega`, `time`, and `source`. [VERIFIED: src/locomotion/env.py]

**When to use:** Use on reset and every step so the evaluator does not infer active command from the first schedule entry. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md]

**Example:**
```python
# Source: existing env schedule helper in src/locomotion/env.py [VERIFIED]
active = self._command_at_time(self._current_sim_time())
info["current_command"] = {
    "time": self._current_sim_time(),
    "vx": float(active[0]),
    "vy": float(active[1]),
    "omega": float(active[2]),
    "source": "scenario_schedule",
}
```

### Pattern 2: Prefer current command in evaluator

**What:** `_action_from_command_context()` should prefer `info["current_command"]` before falling back to schedule/default-zero. [VERIFIED: src/locomotion/evaluation.py]

**When to use:** Every evaluation step, because `latest_info` represents the current env timestamp while `reset_info["command_schedule"]` is static metadata. [VERIFIED: src/locomotion/evaluation.py; .planning/v4.0-MILESTONE-AUDIT.md]

**Example:**
```python
# Source: recommended patch shape for src/locomotion/evaluation.py [VERIFIED code owner]
current_command = info.get("current_command")
if isinstance(current_command, dict):
    return _command_vector(current_command), str(current_command.get("source", "current_command")), {
        "current_command": dict(current_command),
        "command_schedule": _serializable_sequence(info.get("command_schedule", ())),
    }
```

### Pattern 3: Preserve metric family ownership during flattening

**What:** Flatten `distance_xy_m` from `summary["stability"]` because the production metrics summary stores distance there. [VERIFIED: src/locomotion/metrics.py]

**When to use:** `episodes.csv`, aggregate summary, comparison Markdown, and threshold helper inputs. [VERIFIED: src/locomotion/evaluation.py; tests/locomotion/test_locomotion_baseline_regression.py]

**Example:**
```python
# Source: production summary schema in src/locomotion/metrics.py [VERIFIED]
"distance_xy_m": _metric_alias(stability, "distance_xy_m", default=0.0)
```

### Anti-Patterns to Avoid

- **Schedule-index coupling:** Do not use `command_schedule[0]` as the runtime command after reset; scenario samples intentionally include a zero initial command and later nonzero command. [VERIFIED: src/locomotion/scenarios.py; .planning/v4.0-MILESTONE-AUDIT.md]
- **Metric-family guessing:** Do not read `distance_xy_m` from `command_tracking` unless production metrics move it there; today it lives under `stability`. [VERIFIED: src/locomotion/metrics.py]
- **Stationary success leakage:** Do not let stability-only success count as locomotion success when the active command has nonzero translational speed. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md; tests/locomotion/test_locomotion_baseline_regression.py]
- **Runtime AI dependency creep:** Do not import or depend on `claude-agent-sdk` in package runtime code for this phase. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schedule lookup semantics | A second evaluator-side command scheduler | `ArgusGo2Env._command_at_time()` plus `info["current_command"]` | Env owns simulation time and current command state. [VERIFIED: src/locomotion/env.py] |
| Numeric action/metric coercion | Custom list parsing scattered across tests | Existing NumPy coercion in env/evaluation plus helper assertions | The code already centralizes vector coercion and `_command_vector()`. [VERIFIED: src/locomotion/env.py; src/locomotion/evaluation.py] |
| CSV/JSON export framework | pandas or bespoke report generator | Existing stdlib `csv`, `json`, `jsonlines-by-loop` writer | Current artifact contract is already implemented and tests cover it. [VERIFIED: src/locomotion/evaluation.py; tests/locomotion/test_locomotion_evaluation_exports.py] |
| Regression orchestration | LLM judges or semantic scoring | pytest fixtures with fake envs, `tmp_path`, `pytest.raises`, parametrization | Pytest supports the fixtures/patterns needed and the AI-SPEC requires deterministic tests. [VERIFIED: Context7 /pytest-dev/pytest; .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md] |
| Artifact path safety | Manual string path concatenation | `pathlib.Path.resolve()`, parent containment checks, and mkdir | Python docs state `resolve()` makes paths absolute and resolves symlinks/`..`; current `_prepare_run_dir()` already follows this pattern. [CITED: https://docs.python.org/3/library/pathlib.html; VERIFIED: src/locomotion/evaluation.py] |

**Key insight:** This phase is not missing infrastructure; it is misusing the existing command and metric contracts at integration boundaries. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md]

## Common Pitfalls

### Pitfall 1: Fixing fake env tests but not real env semantics

**What goes wrong:** Tests pass because fake envs emit `current_command`, while real `ArgusGo2Env._info()` still lacks it. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py; src/locomotion/env.py]  
**Why it happens:** Current runner already checks `current_command` after schedule fallback, but real env does not provide that field. [VERIFIED: src/locomotion/evaluation.py; src/locomotion/env.py]  
**How to avoid:** Add env-level tests asserting reset and post-transition step info include active `current_command`. [VERIFIED: src/locomotion/env.py]  
**Warning signs:** `test_runner_uses_scenario_command_schedule...` passes without changing `ArgusGo2Env._info()`. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py]

### Pitfall 2: Current command source and exported command diverge

**What goes wrong:** Action generation uses one command, while `steps.jsonl`, manifest, CSV, or threshold rows record another command. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md]  
**Why it happens:** `_action_from_command_context()` and `_command_fields()` are separate functions. [VERIFIED: src/locomotion/evaluation.py]  
**How to avoid:** Test both the `env.step()` action captured by fake env and the emitted `step_rows`/manifest `commanded_velocity` for the same post-transition command. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py; tests/locomotion/test_locomotion_evaluation_exports.py]  
**Warning signs:** `command_source == "scenario_schedule"` but `commanded_velocity == [0.0, 0.0, 0.0]` after transition. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md]

### Pitfall 3: Distance is fixed in CSV but not aggregate comparison

**What goes wrong:** `episodes.csv` has nonzero distance, but `summary.json` or `comparison.md` still reports zero due to type coercion or stale input rows. [VERIFIED: src/locomotion/evaluation.py]  
**Why it happens:** Aggregation reads flattened episode rows and coerces CSV strings to floats; any wrong flattened field propagates to mean/std. [VERIFIED: src/locomotion/evaluation.py]  
**How to avoid:** Test `result.episode_rows`, `episodes.csv`, regenerated `summary.json`, and `comparison.md` for the same nonzero `distance_xy_m`. [VERIFIED: src/locomotion/evaluation.py; tests/locomotion/test_locomotion_evaluation_exports.py]  
**Warning signs:** `summary["overall_by_controller"][0]["distance_xy_m_mean"] == 0.0` despite a nonzero stability summary. [VERIFIED: src/locomotion/evaluation.py]

### Pitfall 4: Baseline regression remains a standing-still test

**What goes wrong:** The threshold helper only enforces distance if exported commanded translational speed is nonzero, so stale zero commands bypass distance checks. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py]  
**Why it happens:** The current check gates `distance_xy_m >= DISTANCE_XY_MIN_M` under `translational_speed > 0.0`. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py]  
**How to avoid:** Add a negative fixture where a nonzero scheduled command is ignored by a stationary fake env and assert the baseline gate fails. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md]  
**Warning signs:** A row with flat-ground scenario, success true, zero command, and zero distance is accepted. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py]

### Pitfall 5: CSV injection hardening regresses during artifact edits

**What goes wrong:** Formula-like strings in CSV cells can become executable formulas in spreadsheet programs. [CITED: https://owasp.org/www-community/attacks/CSV_Injection]  
**Why it happens:** CSV export edits may bypass `_csv_safe()`. [VERIFIED: src/locomotion/evaluation.py]  
**How to avoid:** Keep `writer.writerow({field: _csv_safe(...)})` and preserve the existing formula-safe test. [VERIFIED: src/locomotion/evaluation.py; tests/locomotion/test_locomotion_evaluation_exports.py]  
**Warning signs:** `test_csv_string_cells_are_formula_safe` fails. [VERIFIED: tests/locomotion/test_locomotion_evaluation_exports.py]

## Code Examples

Verified patterns from project and official sources:

### Pytest temporary artifacts

```python
# Source: Context7 /pytest-dev/pytest tmp_path docs [VERIFIED]
def test_tmp_path(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")
    assert test_file.read_text() == "hello world"
```

### Pytest exception assertion pattern

```python
# Source: Context7 /pytest-dev/pytest monkeypatch/raises docs [VERIFIED]
with pytest.raises(ValueError, match="Unknown locomotion scenario"):
    validate_evaluation_matrix(matrix)
```

### Current artifact-safe CSV write pattern

```python
# Source: src/locomotion/evaluation.py [VERIFIED]
writer.writerow({field: _csv_safe(row.get(field, "")) for field in _EPISODE_CSV_FIELDS})
```

### Current run-directory containment pattern

```python
# Source: src/locomotion/evaluation.py and Python pathlib docs [VERIFIED/CITED]
root = Path(output_root).expanduser().resolve()
candidate = (root / timestamp).resolve()
if root != candidate and root not in candidate.parents:
    raise ValueError(f"Run directory escapes output root: {candidate}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Treat first scenario command as representative for the whole episode | Select active command at current simulation time and export that same command | Phase 6 gap closure, planned 2026-05-01 | Required because sampled schedules start with zero and transition to nonzero commands. [VERIFIED: src/locomotion/scenarios.py; .planning/ROADMAP.md] |
| Flatten `distance_xy_m` from `command_tracking` | Flatten `distance_xy_m` from `stability` | Phase 6 gap closure, planned 2026-05-01 | Required because production metrics summary stores distance in `stability`. [VERIFIED: src/locomotion/metrics.py; src/locomotion/evaluation.py] |
| Baseline accepts stable posture when command export is zero | Baseline requires nonzero command fidelity and nonzero distance for commanded locomotion | Phase 6 gap closure, planned 2026-05-01 | Required to prevent standing-still false passes. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md; .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md] |

**Deprecated/outdated:**
- `command_schedule[0]` as runtime command source: invalid for scenarios with scheduled transitions. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md; src/locomotion/scenarios.py]
- `command_tracking.distance_xy_m` as exported distance source: inconsistent with production `LocomotionMetricsCollector` summary. [VERIFIED: src/locomotion/metrics.py; src/locomotion/evaluation.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

All claims in this research were verified or cited — no user confirmation needed.

## Open Questions (RESOLVED)

1. **Should `current_command["time"]` mean schedule-entry start time or current sim time?**
   - What we know: The current command vector can be computed by `_command_at_time(self._current_sim_time())`. [VERIFIED: src/locomotion/env.py]
   - Resolution: Phase 6 plans must expose top-level `sim_time` from the environment and treat `current_command` vector fidelity (`vx`, `vy`, `omega`) as the load-bearing invariant. If a schedule-entry time is exposed, name it explicitly as `schedule_time` rather than relying on ambiguous `time` semantics. [RESOLVED: .planning/ROADMAP.md; src/locomotion/env.py]

2. **Can the real MuJoCo baseline smoke run in the current machine environment?**
   - What we know: Local probed Python is 3.14.4 and lacks `mujoco`/`gymnasium`, while project metadata requires Python `>=3.10,<3.13`. [VERIFIED: package-version probe; pyproject.toml]
   - Resolution: Fake-env tests are mandatory quick gates for Phase 6 semantics. Real MuJoCo smoke remains conditional on supported Python/dependencies and must follow the existing skip behavior in the baseline regression tests. [RESOLVED: tests/locomotion/test_locomotion_baseline_regression.py; pyproject.toml]

3. **Should Phase 6 modify non-default action-mode behavior?**
   - What we know: The milestone audit routes CLI action-mode mismatch to Phase 7, not Phase 6. [VERIFIED: .planning/ROADMAP.md; .planning/v4.0-MILESTONE-AUDIT.md]
   - Resolution: Phase 6 must not broaden `joint_position` or `residual_baseline` CLI semantics except to avoid regressions; Phase 7 owns action-mode support/rejection scope. [RESOLVED: .planning/ROADMAP.md; .planning/v4.0-MILESTONE-AUDIT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Running tests/evaluator | Partial | Local `python3` 3.14.4 | Use supported project environment with Python `>=3.10,<3.13`. [VERIFIED: package-version probe; pyproject.toml] |
| git | Manifest commit metadata | Yes | 2.54.0 | Existing `_git_commit_info()` records error if unavailable. [VERIFIED: package-version probe; src/locomotion/evaluation.py] |
| pytest | Regression tests | Yes | 9.0.2 locally | Install dev dependencies via `python -m pip install -e ".[dev]"`. [VERIFIED: package-version probe; pyproject.toml] |
| pytest-timeout | Repository timeout setting | No in probed Python | — | Install dev dependencies. [VERIFIED: package-version probe; pytest.ini; pyproject.toml] |
| numpy | Evaluator/env numeric operations | Yes | 2.4.4 locally | Install project dependencies. [VERIFIED: package-version probe; pyproject.toml] |
| gymnasium | `ArgusGo2Env` import | No in probed Python | — | Use fake-env tests for runner-only checks; install project dependencies for env tests. [VERIFIED: package-version probe; src/locomotion/env.py] |
| mujoco | Real Go2 smoke | No in probed Python | — | Existing integration test skips when missing; pure fake-env tests must carry Phase 6 semantic proof. [VERIFIED: package-version probe; tests/locomotion/test_locomotion_baseline_regression.py] |
| argus CLI entrypoint | Manual CLI smoke | Not on PATH | — | Use `python -m src.main eval-locomotion` only if package import environment is configured, or install editable package. [VERIFIED: command availability probe; pyproject.toml] |

**Missing dependencies with no fallback:**
- None for planning and pure unit/fake-env tests; real env tests need a supported Python and installed project dependencies. [VERIFIED: package-version probe; tests/locomotion/test_locomotion_baseline_regression.py]

**Missing dependencies with fallback:**
- `mujoco` and `gymnasium` are missing in the probed interpreter; fake-env tests can still prove evaluation runner/export semantics, while real MuJoCo smoke remains conditional. [VERIFIED: package-version probe; tests/locomotion/test_locomotion_evaluation_runner.py]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest, project dev dependency `>=8.0.0`, locally installed 9.0.2 in probed Python. [VERIFIED: pyproject.toml; package-version probe] |
| Config file | `/home/prannayag/pragnition/robotics/argus/pytest.ini`. [VERIFIED: pytest.ini] |
| Quick run command | `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` [VERIFIED: tests discovered] |
| Full suite command | `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` [VERIFIED: .planning/STATE.md] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| LOC-EVAL-01 | Matrix runner uses active scheduled command for real/fake actions after transition | unit + fake integration | `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | Yes; needs new transition test. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py] |
| LOC-METRICS-05 | JSONL/CSV/summary/comparison preserve nonzero `distance_xy_m` from stability | unit + artifact integration | `python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | Yes; needs distance-from-stability assertion. [VERIFIED: tests/locomotion/test_locomotion_evaluation_exports.py] |
| LOC-EVAL-02 | Aggregate comparison reports nonzero distance means/std/failure counts | artifact integration | `python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py::test_regenerate_comparison_reads_saved_artifacts_without_env -q` | Yes; needs stricter distance assertion. [VERIFIED: tests/locomotion/test_locomotion_evaluation_exports.py] |
| LOC-EVAL-04 | Stationary command-ignoring controller cannot pass commanded locomotion baseline | unit + optional MuJoCo integration | `python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | Yes; needs stationary negative fixture tied to runner outputs. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py] |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q`. [VERIFIED: tests discovered]
- **Per wave merge:** `python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`. [VERIFIED: .planning/STATE.md]
- **Phase gate:** Full suite green before `/gsd-verify-work`, with real MuJoCo smoke either passing in supported environment or explicitly skipped by existing skip conditions. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py]

### Wave 0 Gaps

- [ ] Add/adjust `tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_uses_active_current_command_after_schedule_transition` to prove zero-at-reset then nonzero-after-transition drives fake env action. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py]
- [ ] Add/adjust `tests/locomotion/test_argus_go2_env_scenarios.py` or `test_argus_go2_env_contract.py` to assert `ArgusGo2Env._info()` exposes `current_command` at reset and after schedule transition. [VERIFIED: src/locomotion/env.py; tests/locomotion directory]
- [ ] Add/adjust `tests/locomotion/test_locomotion_evaluation_exports.py::test_episode_export_reads_distance_xy_m_from_stability_summary` where `command_tracking` omits or zeroes distance and `stability.distance_xy_m` is nonzero. [VERIFIED: src/locomotion/evaluation.py; src/locomotion/metrics.py]
- [ ] Add/adjust `tests/locomotion/test_locomotion_baseline_regression.py::test_stationary_controller_fails_commanded_locomotion_baseline_gate` to prove stable posture plus nonzero command plus zero distance fails. [VERIFIED: tests/locomotion/test_locomotion_baseline_regression.py]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | CLI/local artifact runner has no authentication boundary in this phase. [VERIFIED: src/main.py] |
| V3 Session Management | no | No sessions are introduced by Phase 6. [VERIFIED: src/main.py; src/locomotion/evaluation.py] |
| V4 Access Control | partial | Keep artifact writes constrained under resolved `output_root`; do not add arbitrary read/write paths beyond existing CLI flags. [VERIFIED: src/locomotion/evaluation.py; CITED: https://docs.python.org/3/library/pathlib.html] |
| V5 Input Validation | yes | Existing matrix validation checks controller ids, scenario ids, seed uniqueness/range, positive integers, and max matrix size before env construction. [VERIFIED: src/locomotion/evaluation.py] |
| V6 Cryptography | no | No cryptography is required for deterministic local artifacts. [VERIFIED: src/locomotion/evaluation.py] |

### Known Threat Patterns for Python CLI artifact evaluator

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal / artifact escape through output paths | Tampering | Resolve `output_root` and candidate run dirs and verify containment before writing. [VERIFIED: src/locomotion/evaluation.py; CITED: https://docs.python.org/3/library/pathlib.html] |
| CSV formula injection in exported strings | Tampering / Information Disclosure | Prefix formula-like CSV strings with a single quote and keep tests for formula-like `failure_reason`; OWASP notes CSV injection has no universal sanitization strategy. [VERIFIED: src/locomotion/evaluation.py; tests/locomotion/test_locomotion_evaluation_exports.py; CITED: https://owasp.org/www-community/attacks/CSV_Injection] |
| Unbounded matrix causing resource exhaustion | Denial of Service | Keep `max_matrix_runs` validation and positive integer checks. [VERIFIED: src/locomotion/evaluation.py] |
| Network/LLM dependency accidentally added to runtime | Information Disclosure / Supply Chain | Do not add `claude-agent-sdk` or network/model calls to runtime evaluator; AI-SPEC restricts it to developer assistance. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md] |
| Misleading artifacts from unsupported action modes | Tampering / Repudiation | Leave Phase 7 to enforce action-mode support/rejection; Phase 6 should not broaden runtime action-mode behavior. [VERIFIED: .planning/ROADMAP.md] |

## Sources

### Primary (HIGH confidence)

- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` - requirement IDs and active/pending status. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md` - Phase 6 scope, success criteria, Phase 7 boundary. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` - milestone decisions and historical regression command. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md` - gap evidence for command schedule, distance export, and baseline semantics. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-AI-SPEC.md` - AI/runtime constraints and evaluation rubric. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/env.py` - env current-time, schedule, info, metrics summary behavior. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` - runner, artifacts, aggregation, path safety, CSV safety. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/metrics.py` - `stability.distance_xy_m` source of truth. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/scenarios.py` - sampled zero-to-nonzero command schedule. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py` - fake-env runner tests. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py` - artifact tests. [VERIFIED]
- `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_baseline_regression.py` - baseline threshold tests. [VERIFIED]
- Context7 `/pytest-dev/pytest` - pytest fixture and monkeypatch/raises patterns. [VERIFIED]
- Python pathlib docs: https://docs.python.org/3/library/pathlib.html - resolved path and containment guidance. [CITED]

### Secondary (MEDIUM confidence)

- OWASP CSV Injection: https://owasp.org/www-community/attacks/CSV_Injection - CSV formula injection threat and mitigation caveats. [CITED]

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from `pyproject.toml`, local package probes, and source imports. [VERIFIED]
- Architecture: HIGH - based on direct code reads of env/evaluation/metrics/scenario/test files. [VERIFIED]
- Pitfalls: HIGH - each pitfall maps to audit evidence or existing code/tests. [VERIFIED]
- Environment availability: MEDIUM - probe used the default shell Python, not a project virtualenv. [VERIFIED: package-version probe]

**Research date:** 2026-05-01  
**Valid until:** 2026-05-08 for environment availability and dependency versions; 2026-05-31 for architecture findings unless Phase 6/7 code changes land first.
