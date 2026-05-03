---
phase: 07-align-evaluation-action-mode-contract
verified: 2026-05-02T14:24:34Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/7
  gaps_closed:
    - "Matrix-config action_mode and scalar values are preserved unless CLI scalar overrides are explicit, so unsupported matrix-config modes now fail fast before artifacts."
  gaps_remaining: []
  regressions: []
---

# Phase 7: align-evaluation-action-mode-contract Verification Report

**Phase Goal:** Close milestone audit gaps in CLI action-mode behavior so evaluation either emits valid actions for each supported mode or rejects unsupported modes before misleading runs/artifacts are produced.
**Verified:** 2026-05-02T14:24:34Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The evaluation runner contract for non-default action modes is explicit and enforced before environment stepping. | VERIFIED | `src/locomotion/evaluation.py:31` defines `_EVALUATOR_RUNNABLE_ACTION_MODES = (ACTION_MODE_VELOCITY,)`; `validate_evaluation_matrix()` checks `available_action_modes()` then rejects non-runnable supported modes at `src/locomotion/evaluation.py:158-168`. `run_evaluation_matrix()` calls validation before `_prepare_run_dir()` or env construction at `src/locomotion/evaluation.py:227-245`. |
| 2 | `velocity_command`, `joint_position`, and `residual_baseline` CLI paths either generate actions matching their env action spaces or fail fast with actionable errors. | VERIFIED | Env spaces for all three modes are implemented in `src/locomotion/actions.py:71-87` and guarded by `tests/locomotion/test_argus_go2_env_action_modes.py:33-63`. Evaluation only runs `velocity_command`; validation rejects `joint_position`/`residual_baseline` with actionable messages before side effects (`src/locomotion/evaluation.py:164-168`). Direct CLI and matrix-config paths now preserve/reject correctly: `src/main.py:300-308`, `tests/test_main_args.py:305-345`. Spot-check: matrix-config `joint_position` exited `status=1`, `out_exists=no`, and stderr included the runnable-mode/rejected-mode message. |
| 3 | Exported metadata records only action modes that were actually used for completed runs. | VERIFIED | `_base_row()` includes `"action_mode": cell["action_mode"]` at `src/locomotion/evaluation.py:426-433`; `_build_manifest()` records top-level `action_mode`, `environment_config`, `runs`, and `validated_cells` at `src/locomotion/evaluation.py:610-638`. Rejected modes fail before `_write_artifacts()`, so no rejected-mode metadata is written. `tests/locomotion/test_locomotion_evaluation_exports.py:230-267` verifies completed `velocity_command` metadata and no-artifact rejection. |
| 4 | CLI help/docs match the implemented evaluation action-mode contract. | VERIFIED | CLI help text in `src/main.py:137-145` says `velocity_command is the evaluator-runnable mode` and `joint_position and residual_baseline are env-supported seams`; docs state the same at `docs/locomotion-benchmark.md:37-43`. Tests guard both surfaces at `tests/test_main_args.py:283-302` and `tests/test_locomotion_benchmark_docs.py:110-117`. Spot-check help output contained all required fragments. |
| 5 | Matrix-config scalar values are preserved unless the user explicitly supplies a CLI scalar override. | VERIFIED | Parser scalar defaults are `None` at `src/main.py:134-145`; `run_eval_locomotion_mode()` rebuilds `EvaluationMatrix` with `matrix.<field> if args.<field> is None else args.<field>` at `src/main.py:304-307`. `tests/test_main_args.py:348-427` verifies `residual_baseline`, max steps `7`, sim steps `8`, and heightfield size `9` survive absent CLI overrides. |
| 6 | A matrix-config selecting `joint_position` or `residual_baseline` reaches evaluation validation and fails fast before artifact creation instead of silently running as `velocity_command`. | VERIFIED | `src/main.py:295-308` loads the JSON matrix and preserves `matrix.action_mode` unless `--action-mode` is explicit. `tests/test_main_args.py:305-345` exercises subprocess `python -m src.main eval-locomotion --matrix-config ... action_mode=joint_position` and asserts nonzero exit, actionable error text, and no output root. Manual spot-check produced `status=1` and `out_exists=no`. |
| 7 | Direct CLI default behavior remains `velocity_command`, max episode steps `500`, sim steps per frame `10`, heightfield size `16`, and output root `outputs/locomotion-evals`. | VERIFIED | Parser uses `None` only as override sentinel while `run_eval_locomotion_mode()` falls back to `EvaluationMatrix()` defaults (`src/main.py:295-308`; `src/locomotion/evaluation.py:79-87`). `tests/test_main_args.py:238-250` verifies absent scalar args are `None` and output root remains `outputs/locomotion-evals`; `EvaluationMatrix` defaults provide `velocity_command`, `500`, `10`, `16`. |
| 8 | Explicit CLI scalar overrides still override matrix-config values for `action_mode`, `max_episode_steps`, `sim_steps_per_frame`, and `heightfield_size`. | VERIFIED | The explicit-only merge expressions in `src/main.py:304-307` select `args.*` when non-`None`. `tests/test_main_args.py:429-509` parses `--action-mode velocity_command --max-episode-steps 11 --sim-steps-per-frame 12 --heightfield-size 13` over a fake matrix and asserts those exact override values reach `run_evaluation_matrix()`. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | Fail-fast evaluator action-mode validation and completed-run metadata | VERIFIED | Exists and substantive. Imports `ACTION_MODE_VELOCITY`/`available_action_modes`, defines runnable-mode tuple, validates before `_prepare_run_dir()`, emits action-mode metadata only for validated cells/runs/rows. |
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py` | Pre-side-effect rejection and same-index velocity-command regressions | VERIFIED | Contains unknown-mode and unsupported-mode tests at lines 170-212 with `calls == []` and empty output-root assertions; preserves executed action/row same-index checks at lines 313-338. |
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py` | Completed-run action-mode metadata and no-artifact rejection regressions | VERIFIED | Lines 230-267 verify manifest/validated cells/runs/JSONL/CSV action-mode metadata and no artifacts for rejected modes. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | CLI help, explicit-only scalar merge, matrix-config wiring | VERIFIED | Parser scalar overrides default to `None`; output root default is unchanged; `run_eval_locomotion_mode()` loads matrix config and preserves scalar fields unless explicit CLI values are present. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_main_args.py` | CLI help, matrix-config fail-fast, scalar merge regressions | VERIFIED | Contains portable `sys.executable` subprocess tests, matrix-config no-artifact fail-fast test, parser sentinel test, matrix-preservation test, and explicit override test. No hardcoded `/home/prannayag/pragnition/robotics/argus/.venv/bin/python` path remains. |
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | Canonical benchmark guide action-mode contract | VERIFIED | Lines 37-43 distinguish env-supported action modes from evaluator-runnable support; matrix JSON example uses `"action_mode": "velocity_command"` at line 77. Previous malformed inline-code issue is fixed. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` | Docs contract drift guard | VERIFIED | Lines 110-117 assert current evaluation runs `velocity_command`, both non-default seams are mentioned, and docs include `env-supported seams` and `fail fast`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | `/home/prannayag/pragnition/robotics/argus/src/locomotion/actions.py` | Imports `ACTION_MODE_VELOCITY` and `available_action_modes` | WIRED | `src/locomotion/evaluation.py:16`; validation uses authoritative env mode list at lines 158-168. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py` | Rejection before env factory construction | WIRED | SDK key-link pattern check had a false negative for `calls == []`, but manual file evidence verifies `calls == []` and empty output-root assertions at `tests/locomotion/test_locomotion_evaluation_runner.py:186-212`. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py` | No-artifact rejection and completed metadata tests | WIRED | `tests/locomotion/test_locomotion_evaluation_exports.py:230-267` directly exercises `run_evaluation_matrix()`. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | Lazy imports, `load_matrix_config()`, `EvaluationMatrix`, and `run_evaluation_matrix()` | WIRED | `src/main.py:280-316` imports evaluation functions, loads matrix config, merges defaults/overrides, builds `EvaluationRunConfig`, and calls `run_evaluation_matrix()`. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | `/home/prannayag/pragnition/robotics/argus/tests/test_main_args.py` | Subprocess and fake-module CLI tests | WIRED | `tests/test_main_args.py:253-345` uses `sys.executable -m src.main`; lines 348-509 monkeypatch `src.locomotion.evaluation` to assert exact matrix values. |
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` | Content guard checks action-mode contract | WIRED | Docs text at line 37 is guarded by test assertions at lines 110-117. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | `matrix.action_mode`, `matrix.max_episode_steps`, `matrix.sim_steps_per_frame`, `matrix.heightfield_size` | `load_matrix_config(Path(args.matrix_config))` or `EvaluationMatrix()` defaults, then explicit-only CLI merge | Yes | FLOWING: JSON matrix scalar values are retained when CLI args are `None`; tests capture actual matrix passed to evaluation. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | `cell["action_mode"]` | Validated `EvaluationMatrix.action_mode` through `validate_evaluation_matrix()` | Yes | FLOWING: unsupported modes fail before side effects; completed `velocity_command` cells propagate into env config, manifest, JSONL, and CSV rows. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | CLI help text | argparse subparser | Yes | FLOWING: subprocess help output contains exact contract wording. |
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | Action-mode contract wording | Markdown source consumed by docs tests | Yes | FLOWING: text and matrix example are present and guarded by content tests. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 7 gate | `uv run python -m pytest /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_runner.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_evaluation_exports.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_argus_go2_env_action_modes.py /home/prannayag/pragnition/robotics/argus/tests/test_main_args.py /home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py -q` | `77 passed in 42.39s` | PASS |
| Matrix-config unsupported mode fails before artifacts | Temporary JSON matrix with `action_mode=joint_position`; `uv run python -m src.main eval-locomotion --matrix-config ... --output-root ...` | Exit `1`; output root did not exist; stderr contained runnable-mode and requested-mode message | PASS |
| Evaluation validation accepts/rejects action modes | Python snippet calling `validate_evaluation_matrix(EvaluationMatrix(action_mode=mode))` for all modes | `velocity_command OK`; `joint_position` and `residual_baseline` ValueError with actionable message; unknown mode ValueError with available env modes | PASS |
| CLI help exposes action-mode contract | `uv run python -m src.main eval-locomotion --help | grep -E -- '--action-mode|velocity_command is the evaluator-runnable mode|joint_position and residual_baseline are env-supported seams'` | All required fragments printed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| LOC-ENV-04 | `07-01-PLAN.md`, `07-02-PLAN.md`, `07-03-PLAN.md`; `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:18` | Developer can select action modes for velocity command, joint-position target, and residual-over-baseline control without changing the environment API. | SATISFIED | Env action modes and action spaces are implemented in `src/locomotion/actions.py:12-87`; `ArgusGo2Env` public reset/step API supports all three modes as guarded by `tests/locomotion/test_argus_go2_env_action_modes.py:33-63`. Evaluation/CLI now either runs `velocity_command` or rejects supported-but-unevaluable modes before artifacts, including matrix-config selection. |
| LOC-EVAL-03 | `07-01-PLAN.md`, `07-02-PLAN.md`, `07-03-PLAN.md`; `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:39` | Evaluation stores enough metadata to reproduce a run: git commit, controller id, scenario id, seed, environment config, and action mode. | SATISFIED | `_build_manifest()` records `git_commit`, `matrix`, `environment_config`, `action_mode`, `runs`, and `validated_cells` at `src/locomotion/evaluation.py:617-638`; `_base_row()` records controller/scenario/seed/action_mode at lines 426-433; export tests verify manifest and action-mode propagation. |

No orphaned Phase 7 requirements were found. `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:80` maps LOC-ENV-04 to Phase 7 and line 92 maps LOC-EVAL-03 to Phase 7; all three Phase 7 plans list both IDs in frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | 119-122 | `placeholder` / `not implemented` scope text | INFO | Intentional documentation of unavailable deferred controller families; not a user-visible implementation stub for Phase 7. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py` | 198, 231-247, 493-500 | Empty list/dict initializers and empty returns | INFO | Legitimate accumulators/default serializable sequences populated by execution paths; not stubs. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_main_args.py` | 352-471 | Empty capture dictionaries and fake result rows | INFO | Test scaffolding for asserting CLI merge behavior; not product behavior. |
| `/home/prannayag/pragnition/robotics/argus/src/main.py` | 339, 466, 571, 694 | Empty dict initializers / platform default return | INFO | Existing runtime initialization/default behavior unrelated to Phase 7 action-mode contract. |

### Human Verification Required

None. The phase goal is programmatically checkable through validation order, CLI subprocess behavior, artifact filesystem checks, metadata contents, and static docs/help guards.

### Gaps Summary

No blocking gaps remain. The previous verification blocker is closed: matrix-config scalar values are no longer overwritten by argparse defaults, unsupported matrix-config action modes now reach evaluation validation, and rejected modes fail before output-root/artifact creation. CLI help and benchmark documentation match the implemented contract, completed artifacts record only validated `velocity_command` runs, and LOC-ENV-04 plus LOC-EVAL-03 are accounted for against `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md`.

---

_Verified: 2026-05-02T14:24:34Z_
_Verifier: Claude (gsd-verifier)_
