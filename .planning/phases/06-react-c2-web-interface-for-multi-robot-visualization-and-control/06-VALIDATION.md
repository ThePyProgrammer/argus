---
phase: 6
slug: react-c2-web-interface-for-multi-robot-visualization-and-control
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python backend) + manual browser checks (frontend) |
| **Config file** | pytest.ini (exists) |
| **Quick run command** | `pytest tests/test_web_server.py tests/test_streaming_viz.py -x` |
| **Full suite command** | `pytest tests/ -x --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_web_server.py tests/test_streaming_viz.py -x`
- **After every plan wave:** Run `pytest tests/ -x --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | C2-01 | unit | `pytest tests/test_web_server.py::test_ws_connect -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | C2-03 | unit | `pytest tests/test_streaming_viz.py::test_cloud_delta -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | C2-04 | unit | `pytest tests/test_streaming_viz.py::test_camera_frame_encode -x` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 1 | C2-06 | unit | `pytest tests/test_streaming_viz.py::test_robot_list_message -x` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 1 | C2-07 | integration | `pytest tests/test_web_server.py::test_command_handling -x` | ❌ W0 | ⬜ pending |
| 06-01-06 | 01 | 1 | C2-08 | unit | `pytest tests/test_streaming_viz.py::test_color_modes -x` | ❌ W0 | ⬜ pending |
| 06-01-07 | 01 | 1 | C2-10 | unit | `pytest tests/test_streaming_viz.py::test_delta_tracking -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | C2-02 | manual | N/A (GLB conversion check) | N/A | ⬜ pending |
| 06-02-02 | 02 | 2 | C2-05 | manual | N/A (browser visual check) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web_server.py` — FastAPI WebSocket endpoint tests (connect, static files, command handling)
- [ ] `tests/test_streaming_viz.py` — WebStreamingViz unit tests (cloud delta, camera encode, robot list, color modes, trajectory, delta tracking)
- [ ] `pip install httpx` — FastAPI async test client dependency

*Existing pytest infrastructure from prior phases covers framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scene GLB loads in Three.js | C2-02 | Requires browser + visual mesh inspection | Open browser, verify office geometry renders correctly |
| Dashboard layout renders all panels | C2-05 | Visual layout check | Open http://localhost:8000, verify 3D viewer, sidebar, camera strip all present |
| Point cloud updates live in browser | C2-03 | End-to-end visual | Start exploration, verify point cloud grows in Three.js viewer |
| Camera feeds stream in browser | C2-04 | End-to-end visual | Verify camera feed strip shows live JPEG frames from robots |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
