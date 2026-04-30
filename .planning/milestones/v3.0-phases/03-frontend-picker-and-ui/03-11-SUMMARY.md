---
phase: 03
plan: 11
subsystem: frontend
tags: [frontend, vitest, structural-equivalence, testing, DET-UI-06]
requirements: [DET-UI-06]
dependency-graph:
  requires:
    - 03-01  # Vitest runner configured
    - 03-04  # detectorStore.ts with lifter fields (D-02)
    - 03-10  # detectorStore.restartSubsystem + setRestartSubsystem (D-12 wiring)
  provides:
    - "DET-UI-06 drift gate — Vitest test locks detectorStore ⊇ slamStore + documented extras"
    - "T-03-29 (Tampering) mitigation — symmetric set-equality catches missing AND added keys"
  affects:
    - "All future plans that touch frontend/src/stores/detectorStore.ts"
tech-stack:
  added: []
  patterns:
    - "Structural-equivalence test — Object.keys superset + exact-extras set + Function.length parity"
    - "Symmetric set-equality as two-way drift gate (both missing + extra keys fail)"
key-files:
  created:
    - frontend/src/stores/__tests__/detectorStore.shape.test.ts
  modified: []
decisions:
  - "Three-layer check: (1) superset of slamStore keys, (2) exact-match extras set, (3) setter-arity parity via Function.length — each layer catches a different class of drift"
  - "EXPECTED_EXTRAS encoded as a Set literal in the test — load-bearing contract; future plans that add detectorStore fields MUST update this set in the same commit"
  - "Test file is the merge-time contract, not a local-green requirement — written against the 03-10-merged detectorStore shape per Wave 3 parallel-execution plan"
metrics:
  duration: ~6min
  completed: 2026-04-14
  tasks: 1
  files: 1
  commits: 1
---

# Phase 03 Plan 11: Vitest Structural-Equivalence Test (DET-UI-06) Summary

One-liner: Locked `detectorStore` to mirror `slamStore`'s shape plus a
documented 12-key extras set via a 3-layer Vitest contract — superset check,
exact-extras check, and setter-arity parity — so any future drift between the
two stores fails CI immediately.

## What Shipped

**New file:** `frontend/src/stores/__tests__/detectorStore.shape.test.ts`
(69 lines) — contains one `describe` block with three `it` blocks:

1. **Superset check** — `Object.keys(useSlamStore.getState())` ⊆
   `Object.keys(useDetectorStore.getState())`. Every SLAM field and setter
   must have a detectorStore counterpart. If `detectorStore` loses a mirrored
   field (e.g., a refactor drops `crashMessage`), this test fails with the
   precise missing key.
2. **Exact-extras check** — the keys in `detectorStore` that are NOT in
   `slamStore` must exactly equal the documented 12-key `EXPECTED_EXTRAS`
   set. Symmetric set-equality → both additions AND removals fail. This is
   T-03-29's mitigation (threat: EXPECTED_EXTRAS drifts out of sync with
   the actual store).
3. **Setter-arity parity** — for every function-valued key in slamStore, the
   detectorStore counterpart must have the same `Function.length`. Catches
   signature drift like `setActive(name, display, parameters)` (arity 3)
   being refactored to `setActive(name)` (arity 1).

## Contract: EXPECTED_EXTRAS — the 12 Documented Additions

### Lifter state (Plan 03-04 / D-02) — 5 keys
| Key | Type | Role |
|-----|------|------|
| `lifters` | `LifterBackend[]` | List of available 3D-lifter backends |
| `activeLifter` | `string` | Currently-active lifter name (default `median_depth`) |
| `activeLifterDisplay` | `string` | Display name for the active lifter |
| `activeLifterParameters` | `Record<string, unknown>` | Live param values for the active lifter |
| `stagedLifterParams` | `Record<string, unknown>` | Pending-restart lifter param overrides |

### Lifter setters (Plan 03-04 / D-02) — 5 keys
| Key | Arity | Role |
|-----|-------|------|
| `setLifters` | 1 | Replace the lifters list |
| `setActiveLifter` | 3 | `(name, display, parameters)` — mirror of SLAM's `setActive` |
| `stageLifterParam` | 2 | Stage a pending lifter param value |
| `clearStagedLifterParams` | 0 | Clear the staged-lifter-params map |
| `updateActiveLifterParam` | 2 | Patch a single active-lifter param in place |

### Restart-subsystem tracking (Plan 03-10 Task 1 / D-12) — 2 keys
| Key | Type / Arity | Role |
|-----|--------------|------|
| `restartSubsystem` | `'detector' \| 'lifter' \| null` | Which subsystem's restart overlay is active (used by `RestartOverlay` subsystem prop) |
| `setRestartSubsystem` | 1 | Toggle the restart-subsystem discriminator |

**Total detectorStore surface = 17 (slamStore mirror) + 12 (extras) = 29 keys.**

## Verification State

```bash
cd frontend && npm test
```

**Local-worktree result (this worktree, 03-10 not yet merged):**
- 2 of 3 tests pass (superset check + setter-arity parity).
- 1 test fails (exact-extras check) because `restartSubsystem` +
  `setRestartSubsystem` aren't in this worktree's detectorStore — they land
  via Plan 03-10 Task 1, which runs in parallel (Wave 3) with this plan.
- This is the explicitly-expected state per the orchestrator prompt: "the
  test file IS the contract (declares what SHOULD exist). Write the test;
  it will pass once merged with 03-10."

**Post-merge result (after Wave 3 executor output is merged to main):**
- All 3 tests will pass.
- CI's `npm test` exits 0.

**Reproducing the intended result here:** if a verifier wants a local green,
cherry-pick Plan 03-10's Task 1 commit (adds `restartSubsystem` state field
+ `setRestartSubsystem` setter to `detectorStore.ts`) on top of this plan's
commit — the 3rd assertion will flip to pass.

## Deviations from Plan

None. Executed exactly as written. The "local test fails because 03-10
hasn't merged here" is not a deviation — it's called out in the orchestrator
prompt as the expected Wave 3 parallel-execution state.

## Reminders for Future Plans

**If you add a new field or setter to `frontend/src/stores/detectorStore.ts`:**

1. Decide whether it mirrors a slamStore key (then slamStore must also
   have it — if not, add it to both stores) OR is a detector-only extra.
2. If detector-only: add the key name to `EXPECTED_EXTRAS` in
   `frontend/src/stores/__tests__/detectorStore.shape.test.ts` **in the
   same commit**. The symmetric set-equality assertion will otherwise fail.
3. If it's a setter, ensure its `Function.length` matches the slamStore
   counterpart's arity (or, if it's a detector-only extra, no constraint —
   arity parity only applies to mirrored keys).

## Cross-References

- Plan 03-04 (D-02): added the 10 lifter keys to `detectorStore.ts`.
- Plan 03-10 Task 1 (D-12): added `restartSubsystem` + `setRestartSubsystem`
  to `detectorStore.ts` — required for this test's EXPECTED_EXTRAS set to
  match.
- 03-RESEARCH.md §Code Examples #4: original 10-extras test skeleton (this
  plan updated the extras count from 10 to 12 to account for 03-10's
  restart-subsystem additions).
- T-03-29 threat (this plan's threat model): Tampering-class drift between
  EXPECTED_EXTRAS and the actual store — mitigated by symmetric
  set-equality assertion.

## Commits

- `c2c2285` — `test(03-11): add detectorStore structural-equivalence test for DET-UI-06`

## Self-Check: PASSED

- `frontend/src/stores/__tests__/detectorStore.shape.test.ts` — FOUND
- Commit `c2c2285` — FOUND in git log
- File contains `detectorStore structural equivalence` — FOUND (describe string)
- File contains `EXPECTED_EXTRAS` — FOUND
- File contains `restartSubsystem` + `setRestartSubsystem` — FOUND (both in EXPECTED_EXTRAS list)
- File contains 3 `it(` blocks — FOUND
- Vitest reports exactly 3 tests in the file — FOUND (2 passed + 1 merge-time-pending)
