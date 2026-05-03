# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v4.0 — Benchmarkable Locomotion Environment

**Shipped:** 2026-05-03
**Phases:** 9 | **Plans:** 35 | **Tasks:** 68

### What Was Built

- Gymnasium-style `ArgusGo2Env` with deterministic seeded resets, required locomotion scenarios, and velocity/joint/residual action-mode seams.
- Locomotion controller protocol/registry with analytical trot as the default baseline and unavailable placeholders for residual, direct, MPC, and WBC controller families.
- Command tracking, stability, control-quality, and terrain/contact metrics exposed through env info and evaluation artifacts.
- `argus eval-locomotion` runner for controller x scenario x seed matrices, JSONL/CSV/summary/comparison exports, reproducibility metadata, saved-run regeneration, and baseline regression checks.
- Harness documentation and controller-family comparison matrix grounded in `outputs/locomotion-rd-systems.md`.

### What Worked

- Audit-driven gap closure turned vague locomotion claims into concrete follow-up phases for command schedules, distance export semantics, action-mode contracts, and closeout hygiene.
- Keeping RL/MPC/WBC as unavailable placeholders prevented half-built advanced-controller claims while preserving extension seams.
- Fake-runtime tests made most locomotion contracts testable without requiring every validation step to run full MuJoCo simulation.

### What Was Inefficient

- Milestone completion required extra cleanup phases because validation metadata drifted after verification reports had already passed.
- The SDK-generated milestone accomplishment list was too noisy and needed manual curation before becoming a useful historical summary.
- `audit-open` cleared artifact state but did not detect stale validation frontmatter, so it gave a narrower signal than closeout needed.

### Patterns Established

- Benchmark milestones should define evaluator-runnable modes separately from environment-supported future seams.
- Placeholder controller metadata needs docs/registry drift guards so deferred capability vocabulary cannot imply runnable support.
- Multi-robot controller changes should either use the shared registry path or explicitly document/test a platform-runtime boundary.

### Key Lessons

1. Treat validation metadata as a first-class closeout artifact; passed verification is not enough if the validation contract still says draft or pending.
2. Make benchmark artifacts carry the executed command/action metadata, not just static scenario configuration, or evaluation reports become misleading.
3. Keep future controller families discoverable but unavailable until training/control infrastructure exists.

### Cost Observations

- Model mix: not measured in repository artifacts.
- Sessions: multiple GSD execution/audit/closeout sessions across 2026-04-30 to 2026-05-03.
- Notable: high phase count came from useful audit feedback, but closeout would be cheaper if validation consistency checks ran before milestone audit.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v4.0 | multiple | 9 | Audit-driven gap closure added explicit cleanup phases before archive. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v4.0 | 1072 passed in final Phase 09 full-suite reference | Not measured | Fake-runtime locomotion tests reduced MuJoCo dependency for contract validation. |

### Top Lessons (Verified Across Milestones)

1. Keep roadmap/requirements archives milestone-scoped so active planning files stay small after closeout.
2. Use explicit extension seams for future capabilities, but fail fast when a deferred family is selected.
3. Verify governance artifacts as well as product code before milestone closeout.
