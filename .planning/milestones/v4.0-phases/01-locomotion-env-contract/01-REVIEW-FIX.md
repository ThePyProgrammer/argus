---
phase: 01-locomotion-env-contract
fixed_at: 2026-04-30T00:00:00Z
review_path: .planning/phases/01-locomotion-env-contract/01-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-04-30T00:00:00Z
**Source review:** .planning/phases/01-locomotion-env-contract/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: Rough-heightfield scenario creates a flat zero-valued heightfield

**Files modified:** `src/locomotion/scenarios.py`, `src/locomotion/env.py`, `tests/locomotion/test_argus_go2_env_scenarios.py`
**Commit:** 8629d64
**Applied fix:** Added deterministic non-flat rough heightfield samples to scenario metadata, load those samples into MuJoCo model heightfield data, and added regression coverage for non-flat deterministic rough terrain.

### CR-02: Default model path silently disables physics outside the repository root

**Files modified:** `src/locomotion/env.py`, `tests/locomotion/test_argus_go2_env_contract.py`
**Commit:** 0c7b32a
**Applied fix:** Changed the default model directory to resolve from the package/repository location when unspecified and raise `FileNotFoundError` for an explicitly missing configured model path.

### WR-01: Sampled command schedule is reported but never applied during an episode

**Files modified:** `src/locomotion/env.py`, `tests/locomotion/test_argus_go2_env_action_modes.py`
**Commit:** 2f77e59
**Applied fix:** Added scheduled command lookup by simulation time and apply it before non-velocity action decoding, with regression coverage for joint-position mode after the second schedule entry starts.

---

_Fixed: 2026-04-30T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
