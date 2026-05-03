---
phase: 04
slug: evaluation-runner-and-regression
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-01
updated: 2026-05-01
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` and `[tool.pytest.ini_options]` in `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` |
| **Full Phase 04 command** | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/test_main_args.py tests/locomotion/test_locomotion_baseline_regression.py -q` |
| **Estimated runtime** | ~20 seconds for Phase 04 mapped suite |

---

## Sampling Rate

- **After every task commit:** Run the task's `<automated>` pytest command plus any touched existing test file.
- **After every plan wave:** Run the plan-level verification command from the corresponding `04-*-PLAN.md`.
- **Before `/gsd-verify-work`:** Run `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/test_main_args.py tests/locomotion/test_locomotion_baseline_regression.py -q`.
- **Max feedback latency:** Under 30 seconds for mapped Phase 04 checks; real MuJoCo regression stays narrowly scoped and skips cleanly when unsupported.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | LOC-EVAL-01 | T-04-01, T-04-05 | Invalid controllers/scenarios/seeds and oversized matrices are rejected before simulation or artifact writes; fake-env runner preserves command context and nonzero failure exit semantics. | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | yes | green |
| 04-02-01 | 02 | 2 | LOC-METRICS-05, LOC-EVAL-02, LOC-EVAL-03 | T-04-02, T-04-03, T-04-04 | JSONL, CSV, manifest, summary, Markdown, offline reload, fixed artifact names, and CSV formula defense are covered. | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | yes | green |
| 04-03-01 | 03 | 3 | LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-03 | T-04-01, T-04-02, T-04-03, T-04-05 | `argus eval-locomotion` parses repeatable matrix flags, remains separate from `--control`, delegates to validation/export APIs, and exposes saved comparison regeneration. | unit + CLI smoke | `.venv/bin/python -m pytest tests/test_main_args.py -q` | yes | green |
| 04-04-01 | 04 | 4 | LOC-EVAL-04 | T-04-01, T-04-02, T-04-03, T-04-04, T-04-05 | Analytical trot flat-ground threshold helper rejects synthetic degradation and the marked real MuJoCo smoke regression uses fixed seeds, temp artifacts, and bounded runtime. | unit + integration | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | yes | green |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [x] `tests/locomotion/test_locomotion_evaluation_runner.py` — covers matrix validation, fake-env execution, failure exit semantics, unavailable controller errors.
- [x] `tests/locomotion/test_locomotion_evaluation_exports.py` — covers JSONL/CSV/manifest/summary/Markdown and reload-without-rerun.
- [x] `tests/test_main_args.py` — covers `eval-locomotion` parser shape, artifact flags, and separation from `--control`.
- [x] `tests/locomotion/test_locomotion_baseline_regression.py` — covers real analytical flat-ground threshold regression plus synthetic threshold failure helper.
- [x] Existing `integration` marker registration reused from `pytest.ini`; no new marker required.

---

## Manual-Only Verifications

No manual-only verifications. Generated Markdown comparison contents are checked automatically for required headings and metric direction labels.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s for quick checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-05-01

---

## Validation Audit 2026-05-01

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

Mapped commands run on 2026-05-01:

| Command | Result |
|---------|--------|
| `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | 10 passed |
| `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | 5 passed |
| `.venv/bin/python -m pytest tests/test_main_args.py -q` | 6 passed |
| `.venv/bin/python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | 12 passed |
