# Roadmap: Multi-Robot 3D Reconstruction

## Milestones

- **v4.0 Benchmarkable Locomotion Environment** — Phases 1-9 shipped 2026-05-03. Archive: `.planning/milestones/v4.0-ROADMAP.md`
- **v3.0 Pluggable Perception & 3D Object Detection** — shipped 2026-04-30. Archive: `.planning/milestones/v3.0-ROADMAP.md`
- **v2.0 Generic SLAM API** — shipped 2026-03-25. Archive: `.planning/milestones/v2.0-ROADMAP.md`
- **v1.0 Multi-Robot 3D Reconstruction MVP** — shipped 2026-03-23. Archive: `.planning/milestones/v1.0-ROADMAP.md`

## Current Planning State

No active milestone is open. Start the next milestone with `/gsd-new-milestone`; it will create fresh requirements and a new roadmap instead of extending this shipped v4.0 scope.

## Recently Shipped

| Milestone | Phases | Plans | Shipped | Archive |
|-----------|--------|-------|---------|---------|
| v4.0 Benchmarkable Locomotion Environment | 1-9 | 35/35 | 2026-05-03 | `.planning/milestones/v4.0-ROADMAP.md` |

## Accepted Closeout Debt

- Phase 08 validation metadata remains stale in `08-VALIDATION.md` even though `08-VERIFICATION.md` passed 8/8.
- `MultiRobotBridge` remains an explicit platform-runtime controller boundary rather than the exact single-robot controller registry path; validation-before-mutation is tested and this was accepted under the requirement's "where practical" caveat.
- `audit-open` is clean but does not detect stale phase validation metadata.
