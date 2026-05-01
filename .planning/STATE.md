---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: Benchmarkable Locomotion Environment
status: ready_to_plan
stopped_at: Phase 04 context gathered
last_updated: "2026-05-01T02:47:13.507Z"
last_activity: 2026-05-01 -- Phase 04 execution started
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 20
  completed_plans: 16
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-30)

**Core value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real time — with user-selectable SLAM/perception algorithms, live metrics, and repeatable locomotion benchmarks that make controller changes comparable instead of anecdotal.
**Current focus:** Phase 04 — evaluation-runner-and-regression

## Current Position

Phase: 5
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-01

Progress: [█████████░] 94%

## Performance Metrics

Phase 2 verification: controller-plugin-baseline passed with 5/5 must-haves verified.
Regression gate: `.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` → 186 passed, 2 pre-existing pytest config warnings.

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
- 2026-04-30: Phase 2 completed — controller protocol/registry, analytical trot adapter, unavailable future-controller placeholders, env/bridge controller seam, clean code review, and verification passed.

### Pending Todos

- Discuss and plan Phase 4: `evaluation-runner-and-regression`.
- Address advisory code-review warning if desired: `ArgusGo2Env` advertises `rgb_array` render mode without implementing `render()`.

### Blockers/Concerns

- Deterministic reset must cover MuJoCo state, terrain parameters, command schedule, and push timing; partial seeding is not enough for this milestone.
- Current position-actuator stack is not a torque-control stack; MPC/WBC work must remain deferred unless a later milestone changes actuator/state/control assumptions.
- Contact/terrain metrics depend on reliable MuJoCo contact and foot identity mapping; validate early in Phase 3 planning.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260324-euj | allow me to hide the output rendering on the C2 portal | 2026-03-24 | f87a052 | [260324-euj-allow-me-to-hide-the-output-rendering-on](./quick/260324-euj-allow-me-to-hide-the-output-rendering-on/) |
| 260324-ffy | persist output mode across page reloads | 2026-03-24 | ee4b663 | [260324-ffy-persist-output-mode-across-page-reloads](./quick/260324-ffy-persist-output-mode-across-page-reloads/) |
| 260324-gfi | fix scene mesh not rendering (Strict Mode) | 2026-03-24 | c69227a | — |
| 260324-gov | extract SliderField reusable component | 2026-03-24 | 9943ba9 | [260324-gov-extract-slider-number-field-as-reusable-](./quick/260324-gov-extract-slider-number-field-as-reusable-/) |
| 260324-h1l | polish SliderField dark mode styling + sig figs | 2026-03-24 | 3aee430 | — |
| 260324-hb0 | add colored scene GLB with material colors from MuJoCo XML | 2026-03-24 | ffb3df0 | [260324-hb0-add-colored-scene-glb-with-material-colo](./quick/260324-hb0-add-colored-scene-glb-with-material-colo/) |
| 260324-ksf | spawn robots facing opposite directions | 2026-03-24 | ffb3df0 | — |

## Session Continuity

Last activity: 2026-04-30 — Phase 3 verified complete; Phase 4 ready to discuss
Stopped at: Phase 04 context gathered
Resume file: .planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md
