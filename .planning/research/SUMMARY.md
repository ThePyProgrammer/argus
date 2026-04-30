# Research Summary: v4.0 Benchmarkable Locomotion Environment

**Source report:** `outputs/locomotion-rd-systems.md`
**Provenance:** `outputs/locomotion-rd-systems.provenance.md`
**Date:** 2026-04-30

## Key Findings Used for v4 Scope

1. Argus currently uses an analytical Raibert-style trot that maps velocity commands to 12 Unitree Go2 joint-position targets, then relies on MuJoCo position actuators for tracking.
2. Argus is not currently MPC, WBC, trajectory optimization, reinforcement learning, imitation learning, torque control, ROS 2 deployment, or contact-aware locomotion planning.
3. The safest next step is not to jump directly to RL/MPC/WBC; it is to make the current baseline measurable, reproducible, and comparable.
4. A Gymnasium-style environment contract is the most useful first boundary because it supports baseline evaluation, future learning, and regression testing through one API.
5. Controller-family comparisons require explicit scenarios, deterministic seeds, command tracking, stability metrics, action-quality metrics, contact/terrain proxies, and machine-readable exports.

## Milestone Decisions Derived from Research

- Keep the analytical trot as the deterministic baseline comparator.
- Add controller protocol/registry seams, but defer actual RL/MPC/WBC implementation.
- Build scenario and seed reproducibility before claiming controller improvements.
- Export benchmark artifacts as JSONL/CSV plus summaries so runs can be compared offline.
- Document which controller families are supported now versus deliberately deferred.

## Deferred Research/Implementation Branches

- Residual RL over the analytical trot baseline.
- Direct proprioceptive RL producing PD joint targets.
- Centroidal/convex MPC stance-force planning.
- Whole-body control or inverse-dynamics QP.
- ROS 2 / ros2_control hardware-style deployment.
- Perception-conditioned locomotion over stairs, gaps, and obstacles.

## Evidence Quality

The final report is marked **PASS WITH NOTES**: open arXiv/docs/GitHub/code sources were verified, while some canonical DOI sources redirected correctly but publisher pages blocked direct fetches. v4 scope relies primarily on verified Argus code reads, MuJoCo/Gymnasium docs, and accessible locomotion research sources.
