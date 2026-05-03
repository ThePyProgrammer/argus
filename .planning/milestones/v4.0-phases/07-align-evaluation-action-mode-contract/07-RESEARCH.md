# Phase 7: align-evaluation-action-mode-contract - Research

**Researched:** 2026-05-01 [VERIFIED: system currentDate]
**Domain:** Python locomotion evaluation CLI action-mode contract, Gymnasium-style action spaces, artifact metadata [VERIFIED: .planning/ROADMAP.md:196-205]
**Confidence:** HIGH [VERIFIED: codebase inspection + focused pytest gate]

## User Constraints

No phase `07-CONTEXT.md` exists in `/home/prannayag/pragnition/robotics/argus/.planning/phases/07-align-evaluation-action-mode-contract`, so there are no locked discussion decisions to copy. [VERIFIED: ls .planning/phases/07-align-evaluation-action-mode-contract]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-ENV-04 | Developer can select action modes for velocity command, joint-position target, and residual-over-baseline control without changing the environment API. [VERIFIED: .planning/REQUIREMENTS.md:15-19] | Existing env supports all three action spaces and decoding in `src/locomotion/actions.py`, but evaluator must stop sending one 3-vector for every mode. [VERIFIED: src/locomotion/actions.py:12-157; src/locomotion/evaluation.py:423-443] |
| LOC-EVAL-03 | Evaluation stores enough metadata to reproduce a run: git commit, controller id, scenario id, seed, environment config, and action mode. [VERIFIED: .planning/REQUIREMENTS.md:35-40] | Manifest currently stores top-level `action_mode` plus per-run cell metadata, but Phase 7 should ensure metadata is written only after completed runs and reflects the mode actually stepped. [VERIFIED: src/locomotion/evaluation.py:291-309; src/locomotion/evaluation.py:597-628] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Project-level `/home/prannayag/pragnition/robotics/argus/CLAUDE.md` contains only placeholder text: `Add your project-specific Claude instructions here.` [VERIFIED: CLAUDE.md:1-3]
- Project-level `/home/prannayag/pragnition/robotics/argus/.claude/CLAUDE.md` also contains only placeholder text. [VERIFIED: system reminder]
- The discovered project skill is `desloppify`, a code-health workflow skill; this phase is not a code-health cleanup request, so no desloppify scan/workflow is required for research. [VERIFIED: .claude/skills/desloppify/SKILL.md:1-9]

## Summary

Phase 7 should be planned as a narrow contract-alignment fix at the CLI/evaluation-runner boundary, not as a controller-family implementation phase. [VERIFIED: .planning/ROADMAP.md:196-205] The milestone audit gap is explicit: `src/main.py` accepts `--action-mode`, `EvaluationMatrix` carries `action_mode`, but `src/locomotion/evaluation.py` currently generates a 3-value velocity command for every action mode. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md:58-62; src/main.py:137; src/locomotion/evaluation.py:423-443] The environment already has mode-specific spaces and decoders for `velocity_command`, `joint_position`, and `residual_baseline`; the runner is the broken layer. [VERIFIED: src/locomotion/actions.py:12-157; tests/locomotion/test_argus_go2_env_action_modes.py:34-330]

Phase 6 is a hard dependency because the runner now selects the active scenario command and exports the exact pre-step command that drove each row. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:31-39] Phase 7 must preserve that same-index command/export behavior while adding mode awareness. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:37-39] The safest plan is to centralize evaluation action construction behind a small validated helper that either returns an action whose shape matches `ArgusGo2EnvConfig.action_mode` or raises before `env_factory(...)`, run directory creation, and artifact writing. [VERIFIED: src/locomotion/evaluation.py:206-232; src/locomotion/actions.py:71-87]

**Primary recommendation:** Add preflight action-mode capability validation and a mode-aware evaluation action builder; support `velocity_command` now, support `joint_position`/`residual_baseline` only if the runner can produce valid 12-value actions from an explicit standard source, otherwise fail fast with actionable CLI/matrix errors before artifacts are created. [VERIFIED: .planning/ROADMAP.md:201-205; src/locomotion/actions.py:71-157; .planning/v4.0-MILESTONE-AUDIT.md:152-157]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Parse `--action-mode` and communicate supported CLI contract | CLI / Application entrypoint | Documentation | `src/main.py` owns `eval-locomotion` argparse flags and user-facing help. [VERIFIED: src/main.py:89-149] |
| Validate evaluation matrix action-mode compatibility before side effects | Evaluation runner / Backend application service | Environment action-space module | `validate_evaluation_matrix()` already validates matrix dimensions before env construction and run-dir creation; action-mode compatibility belongs there. [VERIFIED: src/locomotion/evaluation.py:142-215] |
| Build per-step actions for the selected action mode | Evaluation runner / Backend application service | Environment action decoders | `_action_from_command_context()` currently builds the action passed to `env.step()`, so mode-aware generation belongs in this layer. [VERIFIED: src/locomotion/evaluation.py:245-251; src/locomotion/evaluation.py:423-443] |
| Enforce exact action shapes and bounds | Environment / Gym boundary | `src/locomotion/actions.py` | `ArgusGo2Env` builds mode-specific action spaces and `decode_action()` rejects malformed action arrays before MuJoCo control mutation. [VERIFIED: src/locomotion/env.py:53; src/locomotion/env.py:114-183; src/locomotion/actions.py:71-157] |
| Persist reproducibility metadata only for completed runs | Evaluation artifact exporter | CLI invocation capture | `manifest_runs` is appended after episode completion, and `_build_manifest()` writes top-level manifest metadata. [VERIFIED: src/locomotion/evaluation.py:282-309; src/locomotion/evaluation.py:597-628] |
| Keep action-mode docs/help accurate | Documentation + CLI | Tests | Harness guide documents all three action modes; `test_main_args.py` already checks eval help but not action-mode contract wording. [VERIFIED: docs/locomotion-benchmark.md:37-44; tests/test_main_args.py:235-260] |

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Python | `>=3.10,<3.13` project constraint; uv env currently reports Python-compatible test execution via `uv run` [VERIFIED: pyproject.toml:5; uv run pytest gate] | Project runtime language | Existing Argus source, tests, and CLI are Python. [VERIFIED: pyproject.toml:23-27; src/main.py:1-27] |
| `gymnasium` | `>=1.3.0`; installed uv env reports `1.3.0` [VERIFIED: pyproject.toml:8; uv run python package probe] | Env API and `spaces.Box` action spaces | `ArgusGo2Env` subclasses `gymnasium.Env`, and `actions.py` builds `gymnasium.spaces.Box` action spaces. [VERIFIED: src/locomotion/env.py:9-44; src/locomotion/actions.py:7-87] |
| `numpy` | `>=1.26.0`; installed uv env reports `2.4.3` [VERIFIED: pyproject.toml:12; uv run python package probe] | Numeric action arrays, finite checks, bounds checks | Env, action decoding, and evaluation runner all pass actions as NumPy arrays. [VERIFIED: src/locomotion/actions.py:6-157; src/locomotion/evaluation.py:14; src/locomotion/evaluation.py:249-251] |
| `pytest` | `>=8.0.0` dev optional; installed uv env reports `9.0.2` [VERIFIED: pyproject.toml:41-45; uv run python package probe] | Regression coverage | Existing locomotion and CLI contract tests are pytest tests. [VERIFIED: tests/locomotion/test_argus_go2_env_action_modes.py:1-14; tests/locomotion/test_locomotion_evaluation_runner.py:1-15] |
| Internal `src.locomotion.actions` | Current repo version [VERIFIED: src/locomotion/actions.py] | Authoritative action-mode names, spaces, bounds, and decoders | Avoid duplicating action-mode constants, shapes, or bounds in the evaluator. [VERIFIED: src/locomotion/actions.py:12-157] |
| Internal `src.locomotion.evaluation` | Current repo version [VERIFIED: src/locomotion/evaluation.py] | Matrix validation, runner loop, artifacts | This is the layer identified by the audit as accepting unsupported action-mode behavior. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md:58-62] |

### Supporting

| Library / Module | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| `src.locomotion.controllers.ControllerRegistry` | Current repo version [VERIFIED: src/locomotion/controllers.py] | Controller availability and capability metadata | Use during preflight to reject unavailable controller/action-mode combinations before env construction. [VERIFIED: src/locomotion/evaluation.py:161-173; src/locomotion/controllers.py:397-488] |
| `src.main` argparse CLI | Current repo version [VERIFIED: src/main.py] | User-facing `eval-locomotion` flags/help | Update help to state the implemented action-mode contract and fail-fast behavior. [VERIFIED: src/main.py:93-149] |
| `docs/locomotion-benchmark.md` | Current repo version [VERIFIED: docs/locomotion-benchmark.md] | Canonical harness guide | Update the action-mode table and matrix config workflow to match actual CLI behavior. [VERIFIED: docs/locomotion-benchmark.md:37-88] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Preflight reject unsupported non-default modes | Generate placeholder zero 12-vectors for `joint_position` and `residual_baseline` | Zero 12-vectors would produce misleading runs/artifacts unless explicitly documented as a valid controller policy; the phase goal requires valid actions or fail-fast rejection. [VERIFIED: .planning/ROADMAP.md:201-205] |
| Reusing `actions.py` constants and spaces | Hard-code allowed mode strings and shapes in `evaluation.py` | Hard-coding duplicates the authoritative env contract and risks drift from `build_action_space()`. [VERIFIED: src/locomotion/actions.py:12-87] |
| Writing manifest rows before stepping | Record requested action mode even when run fails before valid step | Requirement says metadata should record only action modes actually used for completed runs. [VERIFIED: .planning/ROADMAP.md:203-205] |

**Installation:**

No new package installation is recommended for Phase 7; use the existing project dependencies. [VERIFIED: pyproject.toml:6-17]

```bash
uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q
```

**Version verification:** The requested npm-version protocol is not applicable because this phase uses Python packages, not npm packages. [VERIFIED: pyproject.toml:1-17] Current uv environment versions were probed with `uv run python`: gymnasium `1.3.0`, numpy `2.4.3`, pytest `9.0.2`. [VERIFIED: uv run python package probe]

## Architecture Patterns

### System Architecture Diagram

```text
User / CI
  |
  | argus eval-locomotion --controller ... --scenario ... --seed ... --action-mode ...
  v
src.main argparse
  |
  | builds EvaluationMatrix(action_mode=...)
  v
validate_evaluation_matrix(matrix)
  |
  |-- invalid controller/scenario/seed/action-mode/capability --> ValueError/UnavailableControllerError before env/run-dir/artifacts
  |
  v
run_evaluation_matrix()
  |
  | per completed cell
  v
ArgusGo2EnvConfig(action_mode=cell["action_mode"])
  |
  v
ArgusGo2Env.action_space = build_action_space(action_mode)
  |
  v
reset(seed) -> info[current_command, command_schedule, action_mode]
  |
  v
mode-aware evaluation action builder
  |-- velocity_command --> 3-vector from active current_command
  |-- joint_position --> 12-vector only from explicit supported source, otherwise fail fast before stepping
  |-- residual_baseline --> 12-vector residual only from explicit supported source, otherwise fail fast before stepping
  v
env.step(action)
  |
  | env validates/decodes action, records metrics/info
  v
append step_rows / episode_rows / manifest_runs only for completed runs
  |
  v
_write_artifacts(manifest.json, steps.jsonl, episodes.csv, summary.json, comparison.md)
```

All diagram nodes map to existing files or planned narrow additions in `src/main.py`, `src/locomotion/evaluation.py`, `src/locomotion/env.py`, and `src/locomotion/actions.py`. [VERIFIED: src/main.py; src/locomotion/evaluation.py; src/locomotion/env.py; src/locomotion/actions.py]

### Recommended Project Structure

```text
src/locomotion/
├── actions.py              # authoritative action-mode constants, spaces, decode validation [VERIFIED: src/locomotion/actions.py]
├── env.py                  # Gymnasium-style env boundary and MuJoCo stepping [VERIFIED: src/locomotion/env.py]
├── evaluation.py           # matrix validation, action construction, run loop, artifact export [VERIFIED: src/locomotion/evaluation.py]
└── controllers.py          # controller capabilities and availability metadata [VERIFIED: src/locomotion/controllers.py]

tests/locomotion/
├── test_argus_go2_env_action_modes.py        # env action-space and decode contract [VERIFIED: tests/locomotion/test_argus_go2_env_action_modes.py]
├── test_locomotion_evaluation_runner.py      # matrix validation and fake-runner behavior [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py]
└── test_locomotion_evaluation_exports.py     # artifact/manifest behavior [VERIFIED: tests/locomotion/test_locomotion_evaluation_exports.py]

tests/
└── test_main_args.py       # CLI parser/help behavior [VERIFIED: tests/test_main_args.py]

docs/
└── locomotion-benchmark.md # user-facing benchmark/action-mode docs [VERIFIED: docs/locomotion-benchmark.md]
```

### Pattern 1: Validate before side effects

**What:** Matrix validation should reject unsupported action modes and controller/action-mode incompatibility before env construction, run-dir creation, or artifact writing. [VERIFIED: src/locomotion/evaluation.py:142-215]
**When to use:** Use this for unknown modes, unavailable placeholder controllers, action-mode/controller mismatch, and unsupported non-default evaluator action generation. [VERIFIED: src/locomotion/evaluation.py:161-173; src/locomotion/controllers.py:467-488]
**Example:**

```python
# Source: existing fail-fast pattern in src/locomotion/evaluation.py:142-215
cells = validate_evaluation_matrix(matrix, max_matrix_runs=run_config.max_matrix_runs)
run_dir = _prepare_run_dir(run_config.output_root)  # happens only after validation
```

### Pattern 2: Action builder must be parameterized by mode

**What:** Replace the current action helper shape assumption with a helper that receives the selected `action_mode` and returns an action compatible with `build_action_space(action_mode)`. [VERIFIED: src/locomotion/evaluation.py:423-443; src/locomotion/actions.py:71-87]
**When to use:** Every call to `env.step()` in `run_evaluation_matrix()` should pass through the mode-aware helper. [VERIFIED: src/locomotion/evaluation.py:245-251]
**Example:**

```python
# Source: current call site that needs mode-awareness, src/locomotion/evaluation.py:245-251
action, source, initial_context = _action_from_command_context(latest_info)
_observation, _reward, terminated, truncated, info = env.step(np.asarray(action, dtype=np.float32))
```

### Pattern 3: Metadata follows executed/completed runs, not requested intent

**What:** Manifest `runs` rows should describe a completed run cell, including the action mode actually used and command/action context. [VERIFIED: src/locomotion/evaluation.py:291-300; src/locomotion/evaluation.py:569-594]
**When to use:** Append manifest rows after episode summary collection, not during validation or before the first successful step. [VERIFIED: src/locomotion/evaluation.py:282-301]
**Example:**

```python
# Source: existing completion-time append, src/locomotion/evaluation.py:291-300
manifest_runs.append(
    _manifest_run_row(cell, reset_info, latest_info, commanded_velocity, command_source, command_context, success)
)
```

### Anti-Patterns to Avoid

- **Accepting CLI modes that cannot be stepped:** This reproduces the audit gap where non-default modes are accepted but get a 3-vector action. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md:152-157]
- **Generating dummy 12-value actions without a declared policy source:** This can create plausible artifacts that do not represent a supported controller evaluation. [VERIFIED: .planning/ROADMAP.md:201-205]
- **Duplicating action-mode constants or bounds in CLI help/tests:** `actions.py` is the authoritative source for supported env modes and bounds. [VERIFIED: src/locomotion/actions.py:12-87]
- **Recording requested action modes for runs that fail preflight:** LOC-EVAL-03 is reproducibility metadata for runs, not a log of rejected requests. [VERIFIED: .planning/REQUIREMENTS.md:37-40; src/locomotion/evaluation.py:291-309]
- **Breaking Phase 6 command row semantics:** Step rows must continue to record the exact pre-step command/action context used for that same step. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:37-39]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Action-mode list | A second hard-coded list in `main.py` or `evaluation.py` | `available_action_modes()` / constants from `src.locomotion.actions` | Existing helper returns the supported env modes. [VERIFIED: src/locomotion/actions.py:54-64] |
| Shape and bound checks | Custom evaluator-only shape math | `build_action_space(mode)` and `decode_action()` semantics | Env contract already defines exact shapes and bounds. [VERIFIED: src/locomotion/actions.py:71-157] |
| Controller availability | Ad hoc controller name checks | `ControllerRegistry.list_controllers()` and existing unavailable-controller error path | Matrix validation already uses registry availability before env construction. [VERIFIED: src/locomotion/evaluation.py:161-173] |
| Artifact metadata writer | Separate metadata file for action-mode fixes | Existing manifest/steps/episodes machinery | Existing artifacts already include action-mode fields; planner should fix semantics in place. [VERIFIED: src/locomotion/evaluation.py:31-55; src/locomotion/evaluation.py:597-660] |
| CLI docs drift checks | Manual eyeballing only | Existing pytest docs/help tests plus new targeted assertions | Existing suite already checks eval help and benchmark docs content. [VERIFIED: tests/test_main_args.py:235-260; tests/test_locomotion_benchmark_docs.py exists from file inventory] |

**Key insight:** The hard part is not action decoding; the env already decodes. The hard part is preventing the evaluator from misrepresenting a requested mode as a completed, reproducible run when it cannot generate a valid action for that mode. [VERIFIED: src/locomotion/actions.py:90-157; .planning/v4.0-MILESTONE-AUDIT.md:152-157]

## Common Pitfalls

### Pitfall 1: Treating env support as evaluator support

**What goes wrong:** Because `ArgusGo2Env` supports `joint_position` and `residual_baseline`, the CLI appears to support evaluating them, but the runner currently emits only a 3-vector. [VERIFIED: src/locomotion/actions.py:71-87; src/locomotion/evaluation.py:423-443]
**Why it happens:** Env action-mode selection and evaluator action generation are separate responsibilities. [VERIFIED: src/locomotion/env.py:53; src/locomotion/evaluation.py:245-251]
**How to avoid:** Add explicit evaluator capability validation by action mode and controller before constructing the env. [VERIFIED: src/locomotion/evaluation.py:142-215]
**Warning signs:** A test for `--action-mode joint_position` reaches `env.step()` with an action shape `(3,)`. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md:58-62]

### Pitfall 2: Controller capability metadata can look surprising

**What goes wrong:** `analytical_trot` controller metadata advertises `action_mode: joint_position` because the controller outputs joint targets, while the evaluation CLI default uses `velocity_command` because the env routes velocity commands through the selected controller. [VERIFIED: src/locomotion/controllers.py:356-373; src/locomotion/env.py:125-140]
**Why it happens:** Controller output mode and env input action mode are related but not identical. [VERIFIED: src/locomotion/controllers.py:432-443; src/locomotion/env.py:125-150]
**How to avoid:** Define the CLI contract in terms of env action input mode and document controller compatibility separately. [VERIFIED: docs/locomotion-benchmark.md:37-44; docs/locomotion-benchmark.md:116-123]
**Warning signs:** Planner proposes rejecting `analytical_trot + velocity_command` solely because controller metadata says `joint_position`. [VERIFIED: src/locomotion/controllers.py:356-373; src/locomotion/env.py:125-140]

### Pitfall 3: Writing artifacts after partial failure

**What goes wrong:** A mid-run unsupported-mode failure could leave artifacts claiming an action mode was evaluated. [VERIFIED: .planning/ROADMAP.md:201-205]
**Why it happens:** Current run directory is created after validation but before per-cell stepping. [VERIFIED: src/locomotion/evaluation.py:214-218]
**How to avoid:** Reject unsupported action modes in `validate_evaluation_matrix()`; if a mode is supported but a specific generated action is invalid, fail before appending manifest rows for that cell. [VERIFIED: src/locomotion/evaluation.py:142-215; src/locomotion/evaluation.py:291-301]
**Warning signs:** `manifest.json` contains a top-level `action_mode` for a run where no cell completed. [VERIFIED: src/locomotion/evaluation.py:597-628]

### Pitfall 4: Breaking Phase 6 same-index command exports

**What goes wrong:** Step row `commanded_velocity` could describe the post-step command instead of the action that drove that same row. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:37-39]
**Why it happens:** Env `info` after `step()` may describe the next active command after simulation time advances. [VERIFIED: src/locomotion/env.py:454-481]
**How to avoid:** Preserve the Phase 6 pattern of capturing executed command/action context before `env.step()` and writing that same context to the row. [VERIFIED: src/locomotion/evaluation.py:245-279]
**Warning signs:** Schedule-transition tests fail or row 0/row 1 labels swap. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py:268-294]

## Code Examples

### Existing env action contract

```python
# Source: src/locomotion/actions.py:81-87
if mode == ACTION_MODE_VELOCITY:
    return spaces.Box(low=_VELOCITY_LOW.copy(), high=_VELOCITY_HIGH.copy(), dtype=np.float32)
if mode == ACTION_MODE_JOINT_POSITION:
    return spaces.Box(low=_JOINT_LOW.copy(), high=_JOINT_HIGH.copy(), dtype=np.float32)
if mode == ACTION_MODE_RESIDUAL_BASELINE:
    return spaces.Box(low=_RESIDUAL_LOW.copy(), high=_RESIDUAL_HIGH.copy(), dtype=np.float32)
```

### Current evaluator bug shape

```python
# Source: src/locomotion/evaluation.py:423-443
# This returns a 3-value command vector regardless of matrix.action_mode.
def _action_from_command_context(info: dict[str, Any]) -> tuple[list[float], str, dict[str, Any]]:
    ...
    return [0.0, 0.0, 0.0], "default_zero", {"command_schedule": []}
```

### Existing fail-fast validation placement

```python
# Source: src/locomotion/evaluation.py:214-218
run_config = config or EvaluationRunConfig()
cells = validate_evaluation_matrix(matrix, max_matrix_runs=run_config.max_matrix_runs)
created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
run_dir = _prepare_run_dir(run_config.output_root)
```

### Existing artifact completion timing

```python
# Source: src/locomotion/evaluation.py:282-301
summary = latest_info.get("locomotion_metrics_summary")
...
episode_rows.append(episode_row)
manifest_runs.append(_manifest_run_row(...))
```

## State of the Art

| Old Approach | Current Required Approach | When Changed / Identified | Impact |
|--------------|---------------------------|----------------------------|--------|
| CLI accepts any non-empty `action_mode` string and lets env/action failure happen later. [VERIFIED: src/locomotion/evaluation.py:153-155] | Validate action mode against supported env/evaluator contract before env construction. [VERIFIED: .planning/ROADMAP.md:201-205] | Phase 7 gap closure identified by milestone audit. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md:152-157] | Prevents misleading runs/artifacts. [VERIFIED: .planning/ROADMAP.md:201-205] |
| Evaluation always emits 3-value velocity actions. [VERIFIED: src/locomotion/evaluation.py:423-443] | Evaluation emits a mode-correct action or rejects unsupported mode. [VERIFIED: .planning/ROADMAP.md:201-205] | Phase 7. [VERIFIED: .planning/ROADMAP.md:196-205] | Satisfies LOC-ENV-04 and LOC-EVAL-03. [VERIFIED: .planning/REQUIREMENTS.md:15-19; .planning/REQUIREMENTS.md:35-40] |
| Documentation lists all three env modes without stating evaluator limitations. [VERIFIED: docs/locomotion-benchmark.md:37-44] | Docs/help must match implemented CLI action-mode contract. [VERIFIED: .planning/ROADMAP.md:201-205] | Phase 7. [VERIFIED: .planning/ROADMAP.md:196-205] | Reduces user confusion and audit drift. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md:70-72] |

**Deprecated/outdated:**
- Treating `--action-mode` as an unconstrained string is outdated for Phase 7 because success criteria require explicit enforcement before misleading runs/artifacts are produced. [VERIFIED: src/main.py:137; .planning/ROADMAP.md:201-205]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | If `joint_position` and `residual_baseline` cannot be generated from an explicit supported evaluator policy in this phase, fail-fast rejection is acceptable. [ASSUMED] | Summary / Standard Stack | Planner may choose to implement safe 12-value action generation instead; user intent allows either valid actions or actionable errors. [VERIFIED: .planning/ROADMAP.md:201-205] |
| A2 | No external official docs are needed because this phase is governed by existing project code and milestone audit evidence. [ASSUMED] | Sources | If planner wants to change Gymnasium behavior, official Gymnasium docs should be consulted first. |

## Open Questions (RESOLVED)

1. **RESOLVED: Phase 7 will support `velocity_command` only in `argus eval-locomotion` and fail fast for `joint_position`/`residual_baseline` until explicit action sources exist.**
   - Resolution basis: Success criteria allow either valid generated actions or fail-fast actionable errors for `velocity_command`, `joint_position`, and `residual_baseline`; no concrete 12-value evaluator action source was found for non-default modes. [VERIFIED: .planning/ROADMAP.md:201-205; src/locomotion/evaluation.py:423-443]
   - Planning consequence: `velocity_command` remains evaluator-runnable; `joint_position` and `residual_baseline` remain environment-supported seams but are rejected during evaluation matrix validation. [VERIFIED: src/locomotion/actions.py:71-87]
2. **RESOLVED: Rejected action modes produce no artifacts; no diagnostic run directory is written.**
   - Resolution basis: Current code writes manifest only after `validate_evaluation_matrix()` and after run-dir creation, so validation-time rejection can prevent misleading run directories entirely. [VERIFIED: src/locomotion/evaluation.py:214-218; src/locomotion/evaluation.py:307-309]
   - Planning consequence: Top-level manifest `action_mode` may continue to describe completed validated runs because rejected modes never reach manifest creation. [VERIFIED: .planning/ROADMAP.md:203-205]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Running project tests and CLI in project environment | Yes [VERIFIED: command probe] | `uv 0.10.10` [VERIFIED: command probe] | Direct `.venv/bin/python` if uv unavailable. [VERIFIED: tests/test_main_args.py:239-243] |
| Python in uv env | Runtime/tests | Yes [VERIFIED: uv run package probe] | Project declares `>=3.10,<3.13`; uv test gate passed in current project env. [VERIFIED: pyproject.toml:5; focused pytest gate] | Use project-managed uv env. [VERIFIED: existing test commands in 06-VERIFICATION.md:90-92] |
| `pytest` | Validation | Yes [VERIFIED: uv run python package probe] | `9.0.2` [VERIFIED: uv run python package probe] | None needed. |
| `gymnasium` | Env/action spaces | Yes in uv env [VERIFIED: uv run python package probe] | `1.3.0` [VERIFIED: uv run python package probe] | None; project dependency. [VERIFIED: pyproject.toml:8] |
| `numpy` | Action arrays | Yes in uv env [VERIFIED: uv run python package probe] | `2.4.3` [VERIFIED: uv run python package probe] | None; project dependency. [VERIFIED: pyproject.toml:12] |
| `git` | Manifest git commit metadata | Yes [VERIFIED: command probe] | `2.54.0` [VERIFIED: command probe] | Existing code records `git_commit_error` if unavailable. [VERIFIED: src/locomotion/evaluation.py:631-642] |

**Missing dependencies with no fallback:** None found for Phase 7 research/planning. [VERIFIED: focused pytest gate]

**Missing dependencies with fallback:** Direct system `python` lacks `gymnasium`, but `uv run` provides project dependencies and focused tests pass. [VERIFIED: python package probe; uv run package probe; focused pytest gate]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `9.0.2` in uv env [VERIFIED: uv run python package probe] |
| Config file | `pyproject.toml` pytest marker config only; no separate pytest.ini was found in required inspection. [VERIFIED: pyproject.toml:47-52] |
| Quick run command | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q` [VERIFIED: focused pytest gate] |
| Full suite command | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:90-92] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| LOC-ENV-04 | Env action spaces and decoders reject malformed shape/NaN/out-of-bounds actions for all three modes. [VERIFIED: tests/locomotion/test_argus_go2_env_action_modes.py:34-330] | unit/contract | `uv run python -m pytest tests/locomotion/test_argus_go2_env_action_modes.py -q` | Yes |
| LOC-ENV-04 | Evaluation rejects unsupported non-default CLI action modes before env construction, or emits valid 12-value actions for supported modes. [VERIFIED: .planning/ROADMAP.md:201-205] | runner contract | Add targeted tests to `tests/locomotion/test_locomotion_evaluation_runner.py`; existing file covers pre-env validation patterns. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py:125-167] | Yes, needs new cases |
| LOC-EVAL-03 | Manifest/steps/episodes record action modes actually used by completed runs only. [VERIFIED: src/locomotion/evaluation.py:291-309; src/locomotion/evaluation.py:597-660] | export contract | Add targeted tests to `tests/locomotion/test_locomotion_evaluation_exports.py`. [VERIFIED: tests/locomotion/test_locomotion_evaluation_exports.py:118-210] | Yes, needs new cases |
| LOC-EVAL-03 | CLI help/docs describe implemented action-mode contract. [VERIFIED: .planning/ROADMAP.md:203-205] | CLI/docs | Add assertions to `tests/test_main_args.py` and docs tests. [VERIFIED: tests/test_main_args.py:235-260; docs/locomotion-benchmark.md:37-88] | Yes, needs new cases |

### Sampling Rate

- **Per task commit:** `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q` [VERIFIED: focused pytest gate: 58 passed]
- **Per wave merge:** `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:90-92]
- **Phase gate:** Full locomotion plus bridge regression gate green before `/gsd-verify-work`. [VERIFIED: .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:90-92]

### Wave 0 Gaps

- [ ] `tests/locomotion/test_locomotion_evaluation_runner.py` — add pre-env-construction rejection tests for unknown action mode, `joint_position`, and `residual_baseline` if unsupported by evaluator. [VERIFIED: tests/locomotion/test_locomotion_evaluation_runner.py:125-167]
- [ ] `tests/locomotion/test_locomotion_evaluation_runner.py` — if a non-default mode is supported, add fake-env tests proving generated action shape matches env action space. [VERIFIED: src/locomotion/actions.py:71-87]
- [ ] `tests/locomotion/test_locomotion_evaluation_exports.py` — add completed-run metadata assertions for action-mode fields and no artifact creation on preflight rejection. [VERIFIED: tests/locomotion/test_locomotion_evaluation_exports.py:118-145]
- [ ] `tests/test_main_args.py` — assert eval help says which action modes are runnable versus rejected/deferred. [VERIFIED: tests/test_main_args.py:235-260]
- [ ] `tests/test_locomotion_benchmark_docs.py` — assert docs match the same implemented action-mode contract. [VERIFIED: file inventory]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | This phase is a local CLI/evaluation-runner contract change, not an auth surface. [VERIFIED: src/main.py:89-149] |
| V3 Session Management | No | No session state is involved in `eval-locomotion`. [VERIFIED: src/main.py:269-325] |
| V4 Access Control | No | Local CLI execution does not introduce role-based access paths. [VERIFIED: src/main.py:89-149] |
| V5 Input Validation | Yes | Validate action modes, controllers, scenarios, seeds, and action shapes before env stepping/artifact writes. [VERIFIED: src/locomotion/evaluation.py:142-203; src/locomotion/actions.py:130-157] |
| V6 Cryptography | No | No cryptographic functionality is involved; git commit metadata is read via `git rev-parse`. [VERIFIED: src/locomotion/evaluation.py:631-642] |

### Known Threat Patterns for CLI/artifact stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Misleading reproducibility artifacts after unsupported action-mode request | Tampering / Repudiation | Fail fast before artifacts; append manifest rows only after completed runs. [VERIFIED: .planning/ROADMAP.md:201-205; src/locomotion/evaluation.py:291-309] |
| CSV formula injection via artifact fields | Tampering | Keep existing `_csv_safe()` behavior for episode CSV string fields. [VERIFIED: src/locomotion/evaluation.py:667-670; tests/locomotion/test_locomotion_evaluation_exports.py:247-258] |
| Output path escape via custom output root | Tampering | Preserve `_prepare_run_dir()` resolved-root containment guard. [VERIFIED: src/locomotion/evaluation.py:397-410] |
| Malformed numeric actions reaching MuJoCo controls | Tampering / Denial of Service | Use finite, shape, and bounds checks before control mutation. [VERIFIED: src/locomotion/actions.py:130-157; src/locomotion/env.py:211-221] |

## Sources

### Primary (HIGH confidence)

- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` — LOC-ENV-04 and LOC-EVAL-03 requirement definitions. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md` — Phase 7 goal, success criteria, and dependencies. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` — current milestone/phase position and v4.0 decisions. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md` — Phase 6 completion evidence and exact command/export semantics to preserve. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md` — original Phase 7 audit gap evidence. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/actions.py` — action-mode constants, spaces, and decoders. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/env.py` — env action-mode behavior, info metadata, and current-command fields. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` — matrix validation, action generation, artifacts, and manifest metadata. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/src/main.py` — CLI parser and eval-locomotion runner entrypoint. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_argus_go2_env_action_modes.py` — existing LOC-ENV-04 coverage. [VERIFIED: Read]
- Focused pytest gate: `58 passed in 32.28s` for runner/export/action-mode/CLI tests. [VERIFIED: Bash]

### Secondary (MEDIUM confidence)

- `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` — canonical user-facing guide; reliable for current docs but must be updated if implementation changes. [VERIFIED: Read]
- `/home/prannayag/pragnition/robotics/argus/pyproject.toml` — declared Python dependencies and pytest config. [VERIFIED: Read]

### Tertiary (LOW confidence)

- No web-search-only sources were used. [VERIFIED: tool usage]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stack components are existing project files or `uv run` probed packages. [VERIFIED: pyproject.toml; uv run package probe]
- Architecture: HIGH — source files directly show CLI → evaluation → env → actions → artifacts flow. [VERIFIED: src/main.py; src/locomotion/evaluation.py; src/locomotion/env.py; src/locomotion/actions.py]
- Pitfalls: HIGH — pitfalls are directly tied to milestone audit findings and Phase 6 verification evidence. [VERIFIED: .planning/v4.0-MILESTONE-AUDIT.md; .planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md]

**Research date:** 2026-05-01 [VERIFIED: system currentDate]
**Valid until:** 2026-05-31 for the current internal code contract; re-research sooner if `src/locomotion/actions.py`, `src/locomotion/evaluation.py`, or CLI action-mode semantics change. [ASSUMED]
