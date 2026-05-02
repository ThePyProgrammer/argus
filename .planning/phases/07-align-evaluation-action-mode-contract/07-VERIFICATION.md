---
phase: 07-align-evaluation-action-mode-contract
verified: 2026-05-02T06:12:18Z
status: gaps_found
score: 6/7 must-haves verified
overrides_applied: 0
gaps:
  - truth: "velocity_command, joint_position, and residual_baseline CLI paths either generate actions matching their env action spaces or fail fast with actionable errors"
    status: failed
    reason: "Direct --action-mode CLI rejection works, but --matrix-config scalar values are overwritten by argparse defaults; a config with action_mode=joint_position runs as velocity_command, exits 0, and writes artifacts instead of failing fast."
    artifacts:
      - path: "src/main.py"
        issue: "run_eval_locomotion_mode rebuilds EvaluationMatrix with args.action_mode/default scalar args, ignoring matrix-config action_mode/max_episode_steps/sim_steps_per_frame/heightfield_size when flags are absent."
      - path: "tests/test_main_args.py"
        issue: "No CLI-level regression proves matrix-config action_mode is honored before env construction/artifact creation."
    missing:
      - "Use None parser defaults for scalar CLI overrides or otherwise distinguish absent flags from explicit overrides."
      - "Preserve loaded matrix-config scalar values unless the user explicitly supplies a CLI override."
      - "Add regression for eval-locomotion --matrix-config with action_mode=joint_position/residual_baseline proving fail-fast/no-artifact behavior."
---

# Phase 7: align-evaluation-action-mode-contract Verification Report

**Phase Goal:** Close milestone audit gaps in CLI action-mode behavior so evaluation either emits valid actions for each supported mode or rejects unsupported modes before misleading runs/artifacts are produced.
**Verified:** 2026-05-02T06:12:18Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The evaluation runner contract for non-default action modes is explicit and enforced before environment stepping. | VERIFIED | `src/locomotion/evaluation.py:31` defines `_EVALUATOR_RUNNABLE_ACTION_MODES = (ACTION_MODE_VELOCITY,)`; `validate_evaluation_matrix()` checks `available_action_modes()` then rejects non-runnable supported modes at lines 158-168 before `run_evaluation_matrix()` prepares the run dir or constructs envs at lines 227-245. |
| 2 | `velocity_command` evaluation still constructs envs, steps actions matching its env action space, and preserves Phase 6 same-index command/export semantics. | VERIFIED | `run_evaluation_matrix()` builds step actions from `_action_from_command_context()` at lines 258-264 as 3-value velocity commands; `tests/locomotion/test_locomotion_evaluation_runner.py:313-338` asserts captured fake-env step actions exactly match same-index `step_rows[*]["commanded_velocity"]`. |
| 3 | `velocity_command`, `joint_position`, and `residual_baseline` CLI paths either generate actions matching their env action spaces or fail fast with actionable errors. | FAILED | Direct `--action-mode joint_position` exits non-zero before output creation, but the matrix-config CLI path is broken: a JSON config with `"action_mode":"joint_position"` exited 0 and wrote `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md`. Root cause: `src/main.py:300-307` overwrites loaded matrix config scalars with argparse defaults such as `args.action_mode == "velocity_command"`. |
| 4 | Exported metadata records only action modes that were actually used for completed runs. | VERIFIED | `_base_row()` includes `"action_mode": cell["action_mode"]` at `src/locomotion/evaluation.py:426-433`, feeding step rows, episode CSV rows, and manifest run rows; `_build_manifest()` records top-level `action_mode` and `validated_cells` at lines 610-638. `tests/locomotion/test_locomotion_evaluation_exports.py:230-248` checks manifest, validated cells, runs, JSONL steps, and CSV episodes all record `velocity_command`. |
| 5 | Rejected action modes fail before env construction and before artifact writing in the evaluation library path. | VERIFIED | `run_evaluation_matrix()` calls `validate_evaluation_matrix()` before `_prepare_run_dir()` at `src/locomotion/evaluation.py:227-230`. Runner tests at `tests/locomotion/test_locomotion_evaluation_runner.py:170-212` assert unknown, `joint_position`, and `residual_baseline` leave `calls == []` and `tmp_path` empty. Export tests at `tests/locomotion/test_locomotion_evaluation_exports.py:251-267` assert rejected modes write no artifacts. |
| 6 | CLI help/docs match the implemented evaluation action-mode contract. | VERIFIED with warning | `src/main.py:137-145` help says `velocity_command is the evaluator-runnable mode` and non-default modes are env-supported fail-fast seams; docs at `docs/locomotion-benchmark.md:37-43` state the same and list all three modes. Tests at `tests/test_main_args.py:267-286` and `tests/test_locomotion_benchmark_docs.py:110-117` guard this wording. Warning: docs line 37 has broken inline-code markup noted by review. |
| 7 | LOC-EVAL-03 metadata contains reproducibility fields including git commit, controller id, scenario id, seed, environment config, and action mode. | VERIFIED | `src/locomotion/evaluation.py:617-638` builds manifest with `git_commit`, `matrix`, `environment_config`, top-level `action_mode`, `runs`, and `validated_cells`; run/cell rows include `controller_id`, `scenario_id`, `seed`, and `action_mode` through `_base_row()`. Export tests cover manifest metadata at `tests/locomotion/test_locomotion_evaluation_exports.py:120-145` and action mode at lines 230-248. |

**Score:** 6/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/locomotion/evaluation.py` | Fail-fast evaluator action-mode validation and mode-aware velocity-command action construction | VERIFIED | Exists, substantive, imports `ACTION_MODE_VELOCITY`/`available_action_modes`, validates action mode before side effects, preserves same-index velocity-command stepping. |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | Pre-side-effect rejection regressions and same-index action/export regression | VERIFIED | Contains tests for unknown/unsupported modes with `calls == []` and empty output root, plus same-index captured action assertions. |
| `tests/locomotion/test_locomotion_evaluation_exports.py` | Completed-run metadata and no-artifact rejection regressions | VERIFIED | Contains completed metadata test and parametrized rejected-mode no-artifact test. |
| `src/main.py` | Argparse help and CLI wiring for eval-locomotion action-mode contract | FAILED | Help text is present, but CLI matrix-config scalar merge ignores config `action_mode` and other scalar values by overwriting with parser defaults. |
| `docs/locomotion-benchmark.md` | Canonical benchmark guide action-mode contract | VERIFIED with warning | Content states selected contract and matrix example uses `velocity_command`; inline-code markup on line 37 is malformed. |
| `tests/test_main_args.py` | CLI help contract regression | PARTIAL | Help contract test exists, but missing matrix-config CLI regression for unsupported action-mode config. Also hardcodes a developer venv path in subprocess tests. |
| `tests/test_locomotion_benchmark_docs.py` | Docs contract drift guard | VERIFIED | Content guards verify env-supported seam/fail-fast wording and all action modes. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/locomotion/evaluation.py` | `src/locomotion/actions.py` | `available_action_modes` and `ACTION_MODE_VELOCITY` imported as authoritative env action-mode source | VERIFIED | Import at `src/locomotion/evaluation.py:16`; validation uses `available_action_modes()` at line 158. |
| `src/locomotion/evaluation.py` | `tests/locomotion/test_locomotion_evaluation_runner.py` | Validation rejects before env factory is called | VERIFIED | Tests assert `calls == []` and empty `tmp_path` for invalid modes at lines 170-212. SDK pattern check false-negative was manually contradicted by file evidence. |
| `src/locomotion/evaluation.py` | `tests/locomotion/test_locomotion_evaluation_exports.py` | Artifacts written only after completed velocity_command cells | VERIFIED | `run_evaluation_matrix()` validates before `_prepare_run_dir()`; export no-artifact test at lines 251-267. |
| `src/main.py` | `src/locomotion/evaluation.py` | CLI args/matrix config build `EvaluationMatrix` then call `run_evaluation_matrix()` | FAILED | `src/main.py:295-308` loads matrix config but then overwrites `action_mode` and scalar runtime fields from argparse defaults before calling `run_evaluation_matrix()`, so matrix-config unsupported action modes bypass the fail-fast contract. |
| `src/main.py` | `tests/test_main_args.py` | Help output contains exact runnable/deferred wording | VERIFIED | Test at `tests/test_main_args.py:267-286` checks `--action-mode`, runnable mode wording, and env-supported seam wording. |
| `docs/locomotion-benchmark.md` | `tests/test_locomotion_benchmark_docs.py` | Content guard distinguishes env modes from evaluator-runnable mode | VERIFIED | Test at `tests/test_locomotion_benchmark_docs.py:110-117` checks required wording. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/locomotion/evaluation.py` | `matrix.action_mode` / `cell["action_mode"]` | `EvaluationMatrix` from CLI/config; `validate_evaluation_matrix()` | Yes for library/direct CLI path | FLOWING: validation rejects unsupported/unknown modes and completed rows propagate `cell["action_mode"]`. |
| `src/main.py` | `matrix.action_mode` from `load_matrix_config()` | JSON matrix config in `--matrix-config` workflow | No | HOLLOW/OVERWRITTEN: config value is loaded at `src/main.py:295-296` then discarded at line 304 by `action_mode=args.action_mode`, whose parser default is `velocity_command`. |
| `src/main.py` | Help text for `--action-mode` | argparse subparser | Yes | FLOWING: help command prints exact contract wording. |
| `docs/locomotion-benchmark.md` | Action-mode contract wording | Markdown source consumed by docs tests | Yes | FLOWING with markup warning: content is present but line 37 has malformed inline-code formatting. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase test gate | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` | `73 passed in 17.35s` | PASS |
| Library validation rejects action modes correctly | `uv run python - <<'PY' ... validate_evaluation_matrix(EvaluationMatrix(action_mode=mode)) ... PY` | `velocity_command OK`; `joint_position` and `residual_baseline` ValueError with actionable message; `not_a_mode` unknown-mode ValueError | PASS |
| Direct CLI flag rejects unsupported action mode before artifacts | `uv run python -m src.main eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --action-mode joint_position --output-root "$tmpdir/out"` | Exit 1; no output directory created | PASS |
| Matrix-config CLI rejects unsupported action mode before artifacts | `uv run python -m src.main eval-locomotion --matrix-config matrix.json(action_mode=joint_position) --output-root "$tmpdir/out"` | Exit 0; output dir created with all artifacts | FAIL |
| CLI help exposes action-mode contract | `uv run python -m src.main eval-locomotion --help` | Output includes `--action-mode`, `velocity_command is the evaluator-runnable mode`, and non-default env-supported fail-fast wording | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| LOC-ENV-04 | `07-01-PLAN.md`, `07-02-PLAN.md`; `.planning/REQUIREMENTS.md:18` | Developer can select action modes for velocity command, joint-position target, and residual-over-baseline control without changing the environment API. | PARTIAL / BLOCKED FOR PHASE GOAL | Environment action modes exist in `src/locomotion/actions.py:12-63` and evaluation explicitly supports/rejects them. However CLI matrix-config selection of `joint_position`/`residual_baseline` is silently ignored, so one documented selection path fails the phase goal. |
| LOC-EVAL-03 | `07-01-PLAN.md`, `07-02-PLAN.md`; `.planning/REQUIREMENTS.md:39` | Evaluation stores enough metadata to reproduce a run: git commit, controller id, scenario id, seed, environment config, and action mode. | SATISFIED | Manifest construction at `src/locomotion/evaluation.py:617-638` and row metadata via `_base_row()` include required fields; tests verify manifest metadata and action-mode propagation. |

No orphaned Phase 7 requirements were found: `.planning/REQUIREMENTS.md:80` maps LOC-ENV-04 to Phase 7 and line 92 maps LOC-EVAL-03 to Phase 7; both appear in PLAN frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/main.py` | 300-307 | Matrix config scalar fields overwritten by argparse defaults | BLOCKER | Causes unsupported action_mode in JSON matrix config to run as `velocity_command`, producing misleading artifacts. |
| `docs/locomotion-benchmark.md` | 37 | Broken inline-code markup around contract sentence | WARNING | User-facing docs render the contract awkwardly; does not change executable behavior but weakens documentation quality. |
| `tests/test_main_args.py` | 241-244, 270-273 | Hardcoded absolute `.venv/bin/python` path | WARNING | Tests are non-portable outside this developer checkout; current gate passed in this environment. |
| `docs/locomotion-benchmark.md` | 119-122 | `placeholder` / `not currently` wording | INFO | Intentional v4.0 scope boundary for unavailable controller families, not an implementation stub. |
| `src/locomotion/evaluation.py` | 198, 231-247, 493-500 | Empty list/dict initializers and empty returns | INFO | Legitimate accumulator/default initializers; populated by validation/execution paths, not user-visible stubs. |

### Human Verification Required

None. The phase goal is programmatically checkable through library validation, CLI subprocess behavior, artifact existence, and static docs/help content.

### Gaps Summary

The evaluation library layer is mostly correct: it validates action modes before side effects, only runs `velocity_command`, rejects known-but-unsupported env seams with actionable errors, and records `action_mode` in completed artifacts. Direct CLI `--action-mode joint_position` also fails fast without artifacts.

The phase goal is still not achieved because the documented `--matrix-config` CLI path silently ignores scalar values from JSON configs. A config that selects `joint_position` should fail fast before env construction/artifact creation; instead `src/main.py` overwrites it with the parser default `velocity_command`, runs successfully, and writes a full artifact set. This is a blocker because the phase goal explicitly targets CLI action-mode behavior and avoiding misleading runs/artifacts.

---

_Verified: 2026-05-02T06:12:18Z_
_Verifier: Claude (gsd-verifier)_
