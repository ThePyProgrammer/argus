---
phase: 04
slug: real-3d-obb-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Per-Task Verification Map filled by planner after PLAN.md generation.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) — Vitest already configured for frontend (Phase 3) |
| **Config file** | pytest.ini (exists) |
| **Quick run command** | `pytest tests/perception/test_geometry.py tests/perception/test_point_cluster_lifter.py -x` |
| **Full suite command** | `pytest tests/perception/ tests/integration/test_obb_mujoco_scene.py -q && cd frontend && npx tsc --noEmit && npm test` |
| **Estimated runtime** | ~30s (unit) + ~10s (MuJoCo integration single-frame test) + ~15s (frontend) |

---

## Sampling Rate

- **After every task commit:** Run quick run command scoped to the task's file
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green INCLUDING the SC#1 ±15° / 0.15m gate
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

*Filled by planner after PLAN.md generation.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — add `scikit-learn>=1.4.0` to `perception` extra (D-02)
- [ ] `tests/perception/fixtures/scene_rotated_chair.xml` — MuJoCo XML with chair body at known yaw (D-11)
- [ ] `src/perception/geometry.py` — single projection entrypoint (D-05, D-06)
- [ ] `tests/perception/test_geometry.py` — round-trip projection unit tests + grep invariant scaffold

*Justification: Wave 0 ships the dependency + test scaffolding before any consumer module changes. PointClusterLifter (Wave 2) needs sklearn at import time.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OBB orientation visibly changes when switching lifters via UI | SC#5 | Visual rendering, requires browser interaction | Open C2 page with rotated chair scene, switch MedianDepth → PointCluster via Lifter dropdown, confirm box rotates |
| Hot-swap latency feels instant (no overlay) | D-09, D-10 | Perceptual latency below automated test resolution | Click switch, confirm no RestartOverlay appears and detection continues uninterrupted |
| Open3D OBB fit produces visually-aligned box on rotated chair | SC#1 (visual) | Numerical assertion covered by ±15°/0.15m test, but visual gut-check valuable | Run integration test with rerun.io viz, eyeball OBB alignment |

*Remaining behaviors (geometry math, DBSCAN clustering, fallback on <50 px, REST routes, frontend tsc, grep invariants) have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner fills)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (sklearn install, MuJoCo fixture, geometry.py)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills map)

**Approval:** pending
