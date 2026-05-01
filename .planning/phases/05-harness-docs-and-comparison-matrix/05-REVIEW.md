---
phase: 05-harness-docs-and-comparison-matrix
reviewed: 2026-05-01T07:21:32Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - README.md
  - docs/locomotion-benchmark.md
  - tests/test_locomotion_benchmark_docs.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-01T07:21:32Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the README locomotion section, the canonical locomotion benchmark guide, and the Python documentation guard tests. The guide mostly matches the current CLI/environment surface, but it documents an action mode/controller seam combination that does not exist in the implementation. That is a correctness defect in user-facing documentation: users following the matrix will configure the wrong action mode for the residual controller path.

## Warnings

### WR-01: Residual policy matrix documents the wrong action mode seam

**File:** `docs/locomotion-benchmark.md:119`
**Issue:** The controller-family matrix says residual RL uses controller id `residual_policy` with the `residual_baseline` action mode. The registered placeholder implementation advertises residual policy capabilities with action mode `residual_joint_position`, while the environment action modes are `velocity_command`, `joint_position`, and `residual_baseline`. This mismatch makes the documented seam internally inconsistent: a reader cannot determine whether the residual controller family should be paired with `residual_baseline` or `residual_joint_position`, and matrix configs following the guide may not match controller metadata/promoted capability checks.
**Fix:** Align the documentation with the actual action-mode vocabulary, or rename the implementation capability to the documented action mode. For example, if `residual_baseline` is the intended public seam, update the controller capability metadata to use that exact value and keep the guide consistent:

```python
@locomotion_controller(name="residual_policy", display="Residual Policy")
class ResidualPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("residual_policy", "residual_baseline")
    UNAVAILABLE_REASON = RESIDUAL_POLICY_UNAVAILABLE_REASON
```

Then add a doc guard assertion that the residual matrix row contains the same action-mode string exposed by the implementation.

---

_Reviewed: 2026-05-01T07:21:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
