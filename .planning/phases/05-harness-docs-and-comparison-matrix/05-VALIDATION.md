---
phase: 05
slug: harness-docs-and-comparison-matrix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` |
| **Estimated runtime** | ~10 seconds for doc checks; full suite depends on MuJoCo test runtime |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py tests/test_main_args.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds for Phase 5 content checks

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | LOC-REPORT-01 | T-05-01 | Documentation must describe existing harness behavior without executing benchmarks in doc tests | content/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_locomotion_benchmark_guide_required_content -q` | missing Wave 0 | pending |
| 05-01-02 | 01 | 1 | LOC-REPORT-02 | T-05-02 | Matrix must not present deferred controller families as runnable v4.0 features | content/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_controller_family_matrix_required_content -q` | missing Wave 0 | pending |
| 05-01-03 | 01 | 1 | LOC-REPORT-03 | T-05-03 | Rationale link must point to the locomotion R&D report and current-method wording must stay accurate | content/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_locomotion_rationale_link_and_current_method -q` | missing Wave 0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `docs/locomotion-benchmark.md` — canonical harness guide covering LOC-REPORT-01, LOC-REPORT-02, and LOC-REPORT-03
- [ ] `README.md` — compact locomotion benchmark command card and guide link
- [ ] `tests/test_locomotion_benchmark_docs.py` — Markdown content guards for README and guide

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| New-developer readability of the guide | LOC-REPORT-01 | Content tests can assert required facts exist but cannot prove the prose is concise or readable | Read `docs/locomotion-benchmark.md` from top to bottom and confirm the smoke workflow, artifacts, scenario catalog, and matrix can be followed without opening implementation files |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for Phase 5 content checks
- [ ] `nyquist_compliant: true` set in frontmatter after validation execution

**Approval:** pending
