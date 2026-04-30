---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: Benchmarkable Locomotion Environment
status: planning
stopped_at: roadmap drafted, pending approval (2026-04-30)
last_updated: "2026-04-30"
last_activity: 2026-04-30
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-30)

**Core value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real time — with user-selectable SLAM/perception algorithms, live metrics, and repeatable locomotion benchmarks that make controller changes comparable instead of anecdotal.
**Current focus:** v4.0 — Benchmarkable Locomotion Environment

## Current Position

Phase: Not started
Plan: Not started
Status: Roadmap drafted, pending approval
Last activity: 2026-04-30

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

No v4.0 execution metrics yet.

**Historical reference:**

- v1.0 shipped multi-robot 3D reconstruction MVP.
- v2.0 shipped Generic SLAM API and pipeline editor foundation.
- v3.0 shipped pluggable perception, real 3D OBBs, detection metrics, pipeline perception nodes, and semantic detection fusion.

## Accumulated Context

### Decisions (v4.0 — locked pre-roadmap)

- **Benchmark before controller sophistication:** the locomotion R&D report shows Argus currently uses analytical trot + MuJoCo position actuators; v4.0 must make that baseline measurable before adding RL/MPC/WBC.
- **Gymnasium-style API:** `ArgusGo2Env` is the common reset/step boundary for evaluation, regression tests, and future learning workflows.
- **Scenario catalog:** flat ground, low friction, slope, rough heightfield, and push disturbance are the minimum named scenarios for useful locomotion comparisons.
- **Controller protocol:** the existing analytical trot is the default registered controller; residual/direct-policy/MPC/WBC entries are seams/placeholders, not implementations.
- **Metrics-first evaluation:** command tracking, stability, control quality, contact proxies, exports, and reproducibility metadata are required outputs, not optional diagnostics.
- **CLI-first benchmark:** frontend overhaul is out of scope; machine-readable artifacts and concise docs are enough for this milestone.

### Research Basis

- Final report: `outputs/locomotion-rd-systems.md`
- Provenance: `outputs/locomotion-rd-systems.provenance.md`
- Planning summary: `.planning/research/SUMMARY.md`

### Roadmap Evolution

- 2026-03-23: v2.0 roadmap created — 6 phases (8-13), 23 requirements mapped
- 2026-03-23: Phase 14 added: Interactive ComfyUI-style React Flow state graph creation system to customize the end-to-end SLAM pipeline + parameters
- 2026-04-13: v3.0 milestone started — Pluggable Perception & 3D Object Detection, phase numbering reset to 1
- 2026-04-13: v3.0 ROADMAP.md created — 8 phases, 42 requirements, 100% coverage
- 2026-04-30: v4.0 milestone started — Benchmarkable Locomotion Environment, 5 phases, 20 requirements, 100% coverage

### Pending Todos

- Approve v4.0 roadmap.
- Start `/gsd-plan-phase 1` for `locomotion-env-contract` after approval.
- Commit planning docs if the roadmap is approved and the workflow proceeds with `commit_docs: true`.

### Blockers/Concerns

- Deterministic reset must cover MuJoCo state, terrain parameters, command schedule, and push timing; partial seeding is not enough for this milestone.
- Current position-actuator stack is not a torque-control stack; MPC/WBC work must remain deferred unless a later milestone changes actuator/state/control assumptions.
- Multi-robot direct-action parity may expose bridge duplication; solve the controller/action seam once rather than creating evaluation-only shortcuts.
- Contact/terrain metrics depend on reliable MuJoCo contact and foot identity mapping; validate early in Phase 3 planning.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260324-euj | allow me to hide the output rendering on the C2 portal | 2026-03-24 | f87a052 | [260324-euj-allow-me-to-hide-the-output-rendering-on](./quick/260324-euj-allow-me-to-hide-the-output-rendering-on/) |
| 260324-ffy | persist output mode across page reloads | 2026-03-24 | ee4b663 | [260324-ffy-persist-output-mode-across-page-reloads](./quick/260324-ffy-persist-output-mode-across-page-reloads/) |
| 260324-gfi | fix scene mesh not rendering (Strict Mode) | 2026-03-24 | c69227a | — |
| 260324-gov | extract SliderField reusable component | 2026-03-24 | 9943ba9 | [260324-gov-extract-slider-number-field-as-reusable-](./quick/260324-gov-extract-slider-number-field-as-reusable-/) |
| 260324-h1l | polish SliderField dark mode styling + sig figs | 2026-03-24 | 3aee430 | — |
| 260324-hb0 | add colored scene GLB with material colors from MuJoCo XML | 2026-03-24 | a28d18f | [260324-hb0-add-colored-scene-glb-with-material-colo](./quick/260324-hb0-add-colored-scene-glb-with-material-colo/) |
| 260324-ksf | spawn robots facing opposite directions | 2026-03-24 | ffb3df0 | — |

## Session Continuity

Last activity: 2026-04-30 — v4.0 roadmap drafted
Stopped at: roadmap approval gate
Resume file: None
