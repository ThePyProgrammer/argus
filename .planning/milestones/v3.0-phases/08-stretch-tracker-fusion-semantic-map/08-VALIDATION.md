---
phase: 8
slug: stretch-tracker-fusion-semantic-map
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), vitest 3.x (frontend) |
| **Config file** | `pyproject.toml` (pytest), `frontend/vitest.config.ts` (vitest) |
| **Quick run command** | `uv run pytest tests/tracking/ tests/perception/test_fusion_manager.py tests/perception/test_semantic_map.py tests/perception/test_heterogeneous_backends.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && cd frontend && npx vitest run --reporter=verbose` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | DET-STRETCH-01 | — | N/A | unit | `uv run pytest tests/tracking/test_bytetrack_tracker.py -x -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | DET-STRETCH-01 | — | N/A | unit | `uv run pytest tests/tracking/test_bytetrack_association.py -x -q` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 1 | DET-STRETCH-04 | — | N/A | unit | `uv run pytest tests/perception/test_heterogeneous_backends.py -x -q` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 2 | DET-STRETCH-01 | — | N/A | unit | `uv run pytest tests/perception/test_fusion_manager.py -x -q` | ❌ W0 | ⬜ pending |
| 08-05-01 | 05 | 2 | DET-STRETCH-03 | — | N/A | unit | `uv run pytest tests/perception/test_semantic_map.py -x -q` | ❌ W0 | ⬜ pending |
| 08-06-01 | 06 | 3 | DET-STRETCH-01 | — | N/A | integration | `uv run pytest tests/integration/test_bytetrack_e2e.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/tracking/test_bytetrack_tracker.py` — skip-stubs for DET-STRETCH-01
- [ ] `tests/tracking/test_bytetrack_association.py` — skip-stubs for DET-STRETCH-01 association
- [ ] `tests/perception/test_fusion_manager.py` — skip-stubs for DET-STRETCH-02
- [ ] `tests/perception/test_semantic_map.py` — skip-stubs for DET-STRETCH-03
- [ ] `tests/perception/test_heterogeneous_backends.py` — skip-stubs for DET-STRETCH-04
- [ ] `tests/integration/test_bytetrack_e2e.py` — skip-stubs for DET-STRETCH-01 integration
- [ ] `frontend/src/stores/__tests__/semanticMapStore.test.ts` — vitest skip-stub for semanticMapStore

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SemanticMap TTL fade-out visible in 3D viewer | DET-STRETCH-03 SC#3 | Visual fade effect requires human observation in browser | Open C2, enable ByteTrack + SemanticMap, observe objects fading after robots move away |
| Per-robot backend labels in MetricsPanel | DET-STRETCH-04 SC#4 | Visual confirmation of per-robot backend labels | Set Robot 0 = yolov11, Robot 1 = rtdetrv2, verify both backends labeled correctly in MetricsPanel |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
