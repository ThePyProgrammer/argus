---
phase: 05
slug: harness-docs-and-comparison-matrix
status: revised
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-01
updated: 2026-05-01
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
| **Gap-closure quick run command** | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py tests/locomotion/test_locomotion_controller_registry.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` |
| **Estimated runtime** | ~10 seconds for doc checks; controller registry metadata checks are cheap; full suite depends on MuJoCo test runtime |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py -q`
- **After every gap-closure task commit:** Run `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py tests/locomotion/test_locomotion_controller_registry.py -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py tests/test_main_args.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds for Phase 5 content and metadata checks

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | LOC-REPORT-01 | T-05-01 | Documentation must describe existing harness behavior without executing benchmarks in doc tests | content/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_locomotion_benchmark_guide_required_content -q` | covered by 05-01 | green |
| 05-01-02 | 01 | 1 | LOC-REPORT-02 | T-05-02 | Matrix must not present deferred controller families as runnable v4.0 features | content/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_controller_family_matrix_required_content -q` | covered by 05-01 | green |
| 05-01-03 | 01 | 1 | LOC-REPORT-03 | T-05-03 | Rationale link must point to the locomotion R&D report and current-method wording must stay accurate | content/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_locomotion_rationale_link_and_current_method -q` | covered by 05-01 | green |
| 05-02-01 | 02 | 2 | LOC-REPORT-02 | T-05-02-01 | Residual placeholder metadata must use the public `residual_baseline` action-mode vocabulary while remaining unavailable | metadata/unit | `.venv/bin/python -m pytest tests/locomotion/test_locomotion_controller_registry.py::test_residual_placeholder_advertises_public_residual_baseline_action_mode -q` | planned by 05-02 | pending |
| 05-02-02 | 02 | 2 | LOC-REPORT-02 | T-05-02-02 | Documentation guard must cross-check residual-policy documentation against `ControllerRegistry` metadata without executing the benchmark runtime | content+metadata/unit | `.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py::test_residual_policy_documentation_matches_registry_action_mode -q` | planned by 05-02 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [x] `docs/locomotion-benchmark.md` — canonical harness guide covering LOC-REPORT-01, LOC-REPORT-02, and LOC-REPORT-03
- [x] `README.md` — compact locomotion benchmark command card and guide link
- [x] `tests/test_locomotion_benchmark_docs.py` — Markdown content guards for README and guide
- [x] `src/locomotion/controllers.py` — existing controller metadata surface extended by 05-02 to align the residual placeholder seam
- [x] `tests/locomotion/test_locomotion_controller_registry.py` — existing controller registry test surface extended by 05-02 for metadata drift coverage

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| New-developer readability of the guide | LOC-REPORT-01 | Content tests can assert required facts exist but cannot prove the prose is concise or readable | Read `docs/locomotion-benchmark.md` from top to bottom and confirm the smoke workflow, artifacts, scenario catalog, and matrix can be followed without opening implementation files |

---

## Gap-Closure Validation Notes

- Plan `05-02` is intentionally narrow: it closes the verified residual RL seam mismatch without changing controller availability semantics or expanding Phase 5 scope.
- `05-02-01` samples implementation metadata directly through `ControllerRegistry.list_controllers()` and `available_action_modes()`.
- `05-02-02` samples the documentation-to-registry link from `tests/test_locomotion_benchmark_docs.py` and must remain a Markdown/metadata guard only: no `subprocess`, no `uv`, no `ArgusGo2Env`, and no benchmark execution.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30s for Phase 5 content and metadata checks
- [x] `nyquist_compliant: true` set in frontmatter after validation mapping update

**Approval:** revised for 05-02 gap-closure coverage
