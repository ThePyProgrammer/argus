---
phase: 07
slug: align-evaluation-action-mode-contract
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-02
---

# Phase 07 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| CLI/matrix config -> evaluation validation | User-provided `--action-mode` and JSON `action_mode` cross into matrix execution. | CLI args and JSON scalar configuration |
| Evaluation action builder -> `ArgusGo2Env.step` | Runner-created numeric actions cross into env action validation and MuJoCo control paths. | Velocity command vectors |
| Evaluation runner -> artifact filesystem | Completed run metadata and CSV fields are written under user-selected output roots. | Manifest JSON, JSONL step rows, CSV episode rows |
| CLI help/docs -> user invocation | User reads help/docs and chooses an action mode for evaluation. | Public contract text |
| Matrix config docs -> artifact expectations | User copies documented matrix examples into reproducibility runs. | Documentation snippets and JSON examples |
| Documentation -> future controller work | Env seam descriptions guide future RL/direct/residual work without granting current evaluator support. | Controller-family scope descriptions |
| JSON matrix config -> CLI merge layer | User-provided matrix-config scalar values cross into `src/main.py` before evaluation validation. | Matrix scalar fields |
| CLI scalar flags -> matrix override layer | Explicit CLI flags override saved matrix values and can change action mode/runtime dimensions. | Parsed scalar override fields |
| CLI/evaluation -> artifact filesystem | Invalid action-mode requests must fail before output-root side effects or misleading artifacts. | Output-root paths and evaluation artifacts |
| Test subprocess -> local Python environment | CLI tests execute `python -m src.main`; using the active interpreter avoids machine-specific `.venv` assumptions. | Test subprocess executable path |
| Docs/help -> user behavior | Public contract text influences whether users expect unsupported action modes to produce artifacts. | CLI help and benchmark guide prose |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-07-01 | Tampering / Repudiation | `validate_evaluation_matrix` in `src/locomotion/evaluation.py` | mitigate | Action mode validation rejects unknown, `joint_position`, and `residual_baseline` before `_prepare_run_dir()` or env construction (`src/locomotion/evaluation.py:144`, `src/locomotion/evaluation.py:227`); runner tests assert `calls == []` and empty output roots (`tests/locomotion/test_locomotion_evaluation_runner.py:170`, `tests/locomotion/test_locomotion_evaluation_runner.py:190`). | closed |
| T-07-02 | Tampering / Denial of Service | `env.step(np.asarray(action, dtype=np.float32))` action path | mitigate | `_EVALUATOR_RUNNABLE_ACTION_MODES` is restricted to `ACTION_MODE_VELOCITY` (`src/locomotion/evaluation.py:31`), non-runnable env seams are rejected (`src/locomotion/evaluation.py:164`), and runner actions are 3-value command vectors (`src/locomotion/evaluation.py:258`, `src/locomotion/evaluation.py:485`). | closed |
| T-07-03 | Repudiation | `manifest.json`, `steps.jsonl`, `episodes.csv` | mitigate | Validation precedes artifact directory creation (`src/locomotion/evaluation.py:227`), base rows and manifest include action-mode metadata (`src/locomotion/evaluation.py:426`, `src/locomotion/evaluation.py:633`), export tests assert completed `velocity_command` metadata and rejected modes write no artifacts (`tests/locomotion/test_locomotion_evaluation_exports.py:230`, `tests/locomotion/test_locomotion_evaluation_exports.py:251`). | closed |
| T-07-04 | Tampering | CSV and output path writers in `src/locomotion/evaluation.py` | mitigate | `_prepare_run_dir()` retains resolved-root containment guard (`src/locomotion/evaluation.py:410`), CSV writer applies `_csv_safe()` (`src/locomotion/evaluation.py:668`), and formula-prefix escaping remains in place (`src/locomotion/evaluation.py:680`). | closed |
| T-07-05 | Repudiation | `src/main.py` argparse help | mitigate | `--action-mode` help names `velocity_command` as evaluator-runnable and `joint_position`/`residual_baseline` as fail-fast env seams (`src/main.py:137`); CLI help tests assert the public contract (`tests/test_main_args.py:283`). | closed |
| T-07-06 | Repudiation | `docs/locomotion-benchmark.md` action-mode section | mitigate | Benchmark guide distinguishes current evaluator-runnable `velocity_command` from env-supported seams (`docs/locomotion-benchmark.md:37`) and keeps the matrix example on `velocity_command` (`docs/locomotion-benchmark.md:72`); docs tests guard the wording (`tests/test_locomotion_benchmark_docs.py:110`). | closed |
| T-07-07 | Tampering | Documented matrix/action-mode examples | mitigate | Docs content tests require runnable/deferred wording (`tests/test_locomotion_benchmark_docs.py:110`); the guide says non-default seams fail fast and are not currently evaluator-runnable (`docs/locomotion-benchmark.md:37`) and only shows `velocity_command` in the matrix example (`docs/locomotion-benchmark.md:72`). | closed |
| T-07-08 | Tampering / Information Integrity | Export path/CSV safety when docs mention artifacts | accept | Accepted as out of scope for this docs/help plan, with preserved controls verified: `_prepare_run_dir()` containment (`src/locomotion/evaluation.py:410`) and `_csv_safe()` writer path (`src/locomotion/evaluation.py:668`, `src/locomotion/evaluation.py:680`). | closed |
| T-07-09 | Tampering / Repudiation | `run_eval_locomotion_mode()` matrix rebuild in `src/main.py` | mitigate | Matrix config loads as the base object and scalar fields are replaced only when parsed CLI scalar args are non-`None` (`src/main.py:295`, `src/main.py:300`); tests assert rejected JSON `joint_position` reaches validation and matrix scalars are honored without CLI overrides (`tests/test_main_args.py:305`, `tests/test_main_args.py:348`). | closed |
| T-07-10 | Repudiation | Evaluation artifact output root | mitigate | Validation still precedes run directory creation (`src/locomotion/evaluation.py:227`), and subprocess regression asserts rejected matrix-config `joint_position` exits nonzero without creating `output_root` (`tests/test_main_args.py:305`). | closed |
| T-07-11 | Tampering | Explicit CLI override semantics | mitigate | Parser scalar defaults are `None` (`src/main.py:134`, `src/main.py:137`) and merge semantics preserve matrix values unless explicit CLI scalars are supplied (`src/main.py:300`); tests assert default `None` and explicit scalar overrides (`tests/test_main_args.py:238`, `tests/test_main_args.py:429`). | closed |
| T-07-12 | Denial of Service / Test Portability | `tests/test_main_args.py` subprocess executable | mitigate | CLI subprocess tests use `sys.executable` (`tests/test_main_args.py:253`, `tests/test_main_args.py:283`, `tests/test_main_args.py:305`), and the auditor found no hardcoded `.venv/bin/python` path in `tests/test_main_args.py`. | closed |
| T-07-13 | Information Integrity | `docs/locomotion-benchmark.md` action-mode sentence | mitigate | The benchmark guide has corrected inline-code action-mode wording while preserving the fail-fast contract (`docs/locomotion-benchmark.md:37`), guarded by docs tests (`tests/test_locomotion_benchmark_docs.py:110`). | closed |
| T-07-14 | Tampering | CSV/output path safety in evaluation exports | accept | Accepted as out of scope for the matrix-merge plan, with preserved controls verified: `_prepare_run_dir()` containment (`src/locomotion/evaluation.py:410`), `_csv_safe()` writer path (`src/locomotion/evaluation.py:668`, `src/locomotion/evaluation.py:680`), and rejected matrix-config modes fail before artifact writes (`src/locomotion/evaluation.py:227`, `tests/test_main_args.py:305`). | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-07-01 | T-07-08 | Plan 02 only changed help/docs/tests; export path and CSV safety were already controlled by Plan 01 and verified unchanged. | Phase 07 security audit | 2026-05-02 |
| AR-07-02 | T-07-14 | Plan 03 only changed CLI matrix merge/docs/tests; CSV/output path hardening remained out of scope, and rejected matrix-config modes now fail before artifact writes. | Phase 07 security audit | 2026-05-02 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-02 | 14 | 14 | 0 | Claude Code + gsd-security-auditor |

### Security Audit 2026-05-02

| Metric | Count |
|--------|-------|
| Threats found | 14 |
| Closed | 14 |
| Open | 0 |

Focused verification gate passed: `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` -> 77 passed.

Summary threat flags reviewed:

- `07-01-SUMMARY.md` — none.
- `07-02-SUMMARY.md` — none.
- `07-03-SUMMARY.md` — none.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-02
