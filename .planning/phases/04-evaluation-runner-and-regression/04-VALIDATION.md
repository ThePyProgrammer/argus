---
phase: 04
slug: evaluation-runner-and-regression
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-01
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/locomotion tests/test_main_args.py tests/test_main_platform_args.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` plus any touched existing test file.
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/locomotion tests/test_main_args.py tests/test_main_platform_args.py -q`.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds for quick feedback; real MuJoCo regression may be slower and should stay narrowly scoped.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | LOC-EVAL-01 | T-04-01 | Invalid controllers/scenarios/seeds are rejected before simulation or artifact writes. | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | no, Wave 0 | pending |
| 04-01-02 | 01 | 0 | LOC-METRICS-05, LOC-EVAL-02, LOC-EVAL-03 | T-04-02, T-04-03 | Exported paths stay under the run directory and CSV cells are safe for spreadsheet inspection. | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | no, Wave 0 | pending |
| 04-02-01 | 02 | 1 | LOC-EVAL-01 | T-04-01 | CLI uses `argus eval-locomotion` and validates matrix inputs before constructing environments. | unit + CLI smoke | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/test_main_args.py -q` | no, Wave 0 | pending |
| 04-02-02 | 02 | 1 | LOC-METRICS-05, LOC-EVAL-03 | T-04-02, T-04-03 | JSONL, CSV, manifest, and summary artifacts are written after both success and locomotion-failure runs. | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | no, Wave 0 | pending |
| 04-03-01 | 03 | 1 | LOC-EVAL-02 | T-04-03 | Offline comparison reads saved artifacts only and does not instantiate `ArgusGo2Env`. | unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | no, Wave 0 | pending |
| 04-04-01 | 04 | 2 | LOC-EVAL-04 | T-04-04 | Analytical trot flat-ground threshold test fails on synthetic degradation and records calibrated bounds. | integration + unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_baseline_regression.py -q` | no, Wave 0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/locomotion/test_locomotion_evaluation_runner.py` — covers matrix validation, fake-env execution, failure exit semantics, unavailable controller errors.
- [ ] `tests/locomotion/test_locomotion_evaluation_exports.py` — covers JSONL/CSV/manifest/summary/Markdown and reload-without-rerun.
- [ ] `tests/locomotion/test_locomotion_baseline_regression.py` — covers real analytical flat-ground threshold regression plus synthetic threshold failure helper.
- [ ] Optional pytest marker registration only if a new marker beyond `integration` is chosen.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Inspect generated Markdown comparison for research-facing readability | LOC-EVAL-02 | Table formatting/readability is partly human-facing, though contents are testable. | Run the CLI against a tiny matrix and inspect `comparison.md` headings and metric direction labels. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s for quick checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
