---
phase: 9
slug: milestone-closeout-hygiene
status: passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest via `uv run python -m pytest`; GSD artifact audit via `gsd-sdk` |
| **Config file** | `pyproject.toml`; `pytest.ini`; `.planning` Markdown frontmatter artifacts |
| **Quick run command** | `gsd-sdk query audit-open` |
| **Full suite command** | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | audit: <10 seconds; full suite: use current CLI timing |

---

## Sampling Rate

- **After every task commit:** Run `gsd-sdk query audit-open` after any batch that changes validation, debug, or quick-task artifacts.
- **After every plan wave:** Run `gsd-sdk query audit-open` and inspect changed `VALIDATION.md`, debug, and quick summary frontmatter.
- **Before `/gsd-verify-work`:** `gsd-sdk query audit-open` must report no open closeout blockers.
- **Max feedback latency:** <60 seconds for the audit gate.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | LOC-ENV-01, LOC-CTRL-01, LOC-METRICS-01, LOC-EVAL-01 | T-09-01 | Metadata closure must cite matching verification evidence rather than inventing completion. | governance | `gsd-sdk query audit-open` | yes | green |
| 09-02-01 | 02 | 1 | LOC-ENV-01, LOC-CTRL-01, LOC-METRICS-01, LOC-EVAL-01 | T-09-02 | Debug and quick-task frontmatter must satisfy scanner predicates only when the artifact contains completion evidence or an explicit out-of-closeout disposition. | governance | `gsd-sdk query audit-open` | yes | green |
| 09-03-01 | 03 | 2 | LOC-ENV-01, LOC-CTRL-01, LOC-METRICS-01, LOC-EVAL-01 | T-09-03 | Final closeout audit must fail closed if any open blocking artifacts remain. | governance | `gsd-sdk query audit-open` | yes | green |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `voxel-becomes-pointcloud-closeup` visual disposition | LOC-ENV-01, LOC-METRICS-01 | The debug artifact states browser visual verification is still needed; automation cannot prove the screenshot-level closeup visual outcome. | Either perform and record the visual verification in the debug artifact, or explicitly move the item out of the v4.0 closeout path before the final audit gate. |

Resolved during Plan 02 by manual browser verification or explicit out-of-v4 closeout disposition recorded in .planning/debug/voxel-becomes-pointcloud-closeup.md.

---

## Validation Sign-Off

- [x] All tasks have automated `gsd-sdk query audit-open` verification or an explicit manual disposition.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency <60s for the audit gate.
- [x] `nyquist_compliant: true` set in frontmatter after the final audit gate passes.

Final audit gate: gsd-sdk query audit-open — All artifact types clear. Safe to proceed.

**Approval:** passed
