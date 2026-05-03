---
phase: 04
slug: evaluation-runner-and-regression
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-01
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| CLI/config input -> evaluation matrix | User-provided controller, scenario, seed, config, and output path values become benchmark execution inputs. | Local CLI strings, JSON config, filesystem paths |
| Matrix -> simulation factory | Validated matrix cells become `ArgusGo2EnvConfig` instances and reset/step calls. | Controller/scenario/seed/action-mode execution metadata |
| Runner memory -> filesystem | Benchmark rows become persistent local JSONL, CSV, JSON, and Markdown artifacts. | Locomotion metrics, command context, reproducibility metadata |
| Saved artifacts -> offline comparison | Existing manifest and episode CSV data regenerate summaries without rerunning simulation. | Saved local artifacts |
| CSV artifact -> spreadsheet application | Episode rows may be opened by spreadsheet software. | Spreadsheet-facing string cells |
| Test fixed matrix -> real MuJoCo env | Regression tests invoke local simulation and write temp artifacts. | Fixed analytical baseline matrix and temp outputs |
| Saved regression artifacts -> assertions | Episode rows and summary data become pass/fail thresholds. | Threshold evidence and summary artifact paths |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| 04-01/T-04-01 | Tampering | `validate_evaluation_matrix` | mitigate | `src/locomotion/evaluation.py` validates controller ids/availability, scenario ids, unique bounded integer seeds, action mode, numeric env config, and matrix size before run directory creation or env construction. | closed |
| 04-01/T-04-02 | Tampering | Output path handling | mitigate | Plan 01 avoided artifact writes; Plan 02 adds timestamped child run directories, output-root containment checks, and fixed artifact filenames. | closed |
| 04-01/T-04-03 | Repudiation | In-memory result provenance | mitigate | Runner rows preserve run id, controller, scenario, seed, action mode, command context, and terminal summaries; Plan 02 manifest records persistent provenance. | closed |
| 04-01/T-04-04 | Tampering | CSV export | mitigate | Plan 02 central CSV writer sanitizes spreadsheet-dangerous string cells before writing `episodes.csv`. | closed |
| 04-01/T-04-05 | Denial of Service | Matrix expansion | mitigate | `max_matrix_runs=1000` default is enforced before simulation and before artifact generation. | closed |
| 04-02/T-04-01 | Tampering | Validated matrix from Plan 01 | mitigate | `run_evaluation_matrix` calls validation before `_prepare_run_dir`; tests assert invalid controller/scenario inputs leave no run directory. | closed |
| 04-02/T-04-02 | Tampering | Run directory/file creation | mitigate | `_prepare_run_dir` resolves the output root, creates one timestamped child directory, rejects path escape, and `_ARTIFACT_FILES` fixes the artifact set. | closed |
| 04-02/T-04-03 | Repudiation | Manifest, summary, offline regeneration | mitigate | Manifest records git commit, invocation args, matrix, environment/action config, timestamp, file list, and per-run metadata; `regenerate_comparison` reads saved `manifest.json` and `episodes.csv` only. | closed |
| 04-02/T-04-04 | Tampering | `episodes.csv` string cells | mitigate | `_csv_safe` prefixes strings beginning with `=`, `+`, `-`, or `@`; export tests cover formula-like failure reasons. | closed |
| 04-02/T-04-05 | Denial of Service | Artifact generation for matrices | mitigate | Artifact generation uses the validated bounded matrix and aggregates already-bounded episode rows. | closed |
| 04-03/T-04-01 | Tampering | `eval-locomotion` CLI args | mitigate | CLI parses repeated flags and optional JSON config into `EvaluationMatrix`, then delegates to `run_evaluation_matrix`; it does not construct environments directly. | closed |
| 04-03/T-04-02 | Tampering | `--output-root` and `--from-run-dir` | mitigate | CLI accepts only root/run-dir path parameters and passes them to Plan 02 artifact APIs; it exposes no arbitrary artifact filename flags. | closed |
| 04-03/T-04-03 | Repudiation | CLI invocation metadata | mitigate | `run_eval_locomotion_mode` passes `sys.argv[1:]` into `EvaluationRunConfig.invocation_args`, which is written into `manifest.json`. | closed |
| 04-03/T-04-04 | Tampering | CLI-generated CSV artifacts | mitigate | CLI-generated runs use the Plan 02 exporter and its formula-safe CSV writer. | closed |
| 04-03/T-04-05 | Denial of Service | CLI matrix flags/config | mitigate | CLI exposes `--max-matrix-runs` defaulting to `1000` and passes it into validation before run directory/env construction. | closed |
| 04-04/T-04-01 | Tampering | Regression matrix values | mitigate | Regression test hardcodes controller `analytical_trot`, scenario `flat_ground`, seeds `(101, 202, 303)`, and action mode `velocity_command`. | closed |
| 04-04/T-04-02 | Tampering | Regression output directory | mitigate | Regression test uses pytest `tmp_path` as `EvaluationRunConfig.output_root`, relying on Plan 02 path controls. | closed |
| 04-04/T-04-03 | Repudiation | Threshold calibration and artifacts | mitigate | Regression asserts `summary.json` exists; thresholds were not calibrated from defaults, so observed-range documentation was not triggered. | closed |
| 04-04/T-04-04 | Tampering | CSV output from regression | mitigate | Regression invokes `run_evaluation_matrix` and adds no alternate CSV writer path, preserving the Plan 02 sanitizer. | closed |
| 04-04/T-04-05 | Denial of Service | Real MuJoCo smoke runtime | mitigate | Regression uses exactly three seeds, `max_episode_steps=25`, and explicit skips for unsupported Python, missing MuJoCo, or missing Go2 assets. | closed |

*Status: open · closed*  
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Threat Flags Verified

| Flag | Source | Disposition |
|------|--------|-------------|
| output-path | `04-01-SUMMARY.md` | Covered by 04-01/T-04-02 and 04-02/T-04-02 path containment and fixed-directory controls. |
| filesystem-artifacts | `04-02-SUMMARY.md` | Covered by 04-02/T-04-02 fixed filenames and output-root containment checks. |
| saved-artifact-reload | `04-02-SUMMARY.md` | Covered by 04-02/T-04-03 saved-artifact-only regeneration. |
| csv-spreadsheet | `04-02-SUMMARY.md` | Covered by 04-02/T-04-04 formula-prefix escaping. |

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-01 | 20 | 20 | 0 | gsd-security-auditor |

---

## Security Audit 2026-05-01

| Metric | Count |
|--------|-------|
| Threats found | 20 |
| Closed | 20 |
| Open | 0 |

Evidence summary:
- Validation before side effects: `src/locomotion/evaluation.py:142`, `src/locomotion/evaluation.py:214`.
- Output-root containment and fixed artifacts: `src/locomotion/evaluation.py:30`, `src/locomotion/evaluation.py:384`, `src/locomotion/evaluation.py:623`.
- Manifest and saved-artifact reload provenance: `src/locomotion/evaluation.py:575`, `src/locomotion/evaluation.py:339`.
- CSV formula defense: `src/locomotion/evaluation.py:74`, `src/locomotion/evaluation.py:645`.
- CLI validation delegation and invocation metadata: `src/main.py:269`, `src/main.py:301`, `src/main.py:308`.
- Regression matrix/runtime bounds: `tests/locomotion/test_locomotion_baseline_regression.py:179`, `tests/locomotion/test_locomotion_baseline_regression.py:187`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-01
