# Milestone v2.0 Generic SLAM API — Integration Audit

**Auditor:** Integration Checker (Claude)
**Date:** 2026-03-25
**Scope:** Phases 8–14
**Method:** Cross-phase wiring trace, API consumer verification, E2E flow analysis

---

## Integration Check Complete

### Wiring Summary

**Connected:** 18 exports/interfaces properly wired across phases
**Orphaned:** 1 export created but unused by any consumer
**Missing:** 2 expected connections not found

### API Coverage

**Consumed:** 8 routes have confirmed callers
**Orphaned:** 0 routes with no callers

### Auth Protection

**Protected:** N/A — no auth layer in scope for this milestone; simulation is local-only
**Unprotected:** N/A

### E2E Flows

**Complete:** 5 flows work end-to-end
**Broken:** 2 flows have breaks

---

## Detailed Findings

### Connected Exports (18)

| Export / Interface | From | Used By |
|---|---|---|
| `SLAMProtocol`, `SLAMRegistry`, `slam_backend` | Phase 8 | Phase 9 routes, Phase 11/12 backends, Phase 14 PipelineBuilder, `main.py` |
| `SLAMRegistry.list_backends()` | Phase 8 | `slam_routes.py`, `pipeline_builder.py` (NodeCatalog) |
| `SLAMRegistry.create(name, …)` | Phase 8 | `robot_instance.py` (via `RobotInstance.create`), `main.py` restart loop |
| `MergeProtocol`, `MergeRegistry`, `merge_strategy` | Phase 10 | `coordinator.py`, `slam_routes.py`, `pipeline_builder.py` |
| `MergeRegistry.create(name, …)` | Phase 10 | `main.py` restart loop (lines 458–467) |
| `icp_union`, `pgo_open3d`, `pgo_gtsam` (registered in `merge_strategies/__init__.py`) | Phase 10 | `coordinator.py` via `_merger`, REST routes via `MergeRegistry.list_strategies()` |
| `orbslam3_backend` (registers `"orbslam3"`) | Phase 11 | `slam/backends/__init__.py` → `SLAMRegistry`; listed in `/api/slam/backends` |
| `openvins_backend`, `svopro_backend` (registers `"openvins"`, `"svopro"`) | Phase 12 | `slam/backends/__init__.py` → `SLAMRegistry` |
| `SubprocessSLAMBridge` | Phase 12 | `openvins_backend.py`, `svopro_backend.py` |
| `MetricsTracker` | Phase 13 | `WebStreamingViz._metrics_tracker`, read via `get_stats_payload()` |
| `WebStreamingViz._update_stats` → `slam_metrics` in stats payload | Phase 13 | `useWebSocket.ts` `case 'stats'` → `useMetricsStore.updateAllMetrics` |
| `useSlamStore` | Phase 9 | `AlgorithmSection.tsx`, `ApplyBar.tsx`, `useWebSocket.ts` (`slam_restart_complete`, `crash_fallback`) |
| `useMetricsStore.outputMode` / `setOutputMode` | Phase 13 | `ControlPanel.tsx` (toggle buttons), `SceneViewer.tsx` (renderer switch) |
| `usePipelineStore` | Phase 14 | `PipelineEditor.tsx`, `ApplyBar.tsx`, `NodePalette.tsx`, `NodeInspector.tsx`, `App.tsx` |
| `PipelineBuilder.build()` + `PipelineConfig` | Phase 14 | `pipeline_routes.py` `/api/pipeline/apply` |
| `NodeCatalog.get_catalog()` | Phase 14 | `pipeline_routes.py` `/api/pipeline/node-catalog` |
| `fetchSlamState()` | Phase 9 | `AlgorithmSection.tsx` (on mount + after select), `ApplyBar.tsx` (after apply), `useWebSocket.ts` (on `slam_restart_complete`) |
| `crash_fallback` WS message | Phase 12 (`exploration_loop.py` line 211) | `useWebSocket.ts` `case 'crash_fallback'` → `slamStore.setCrashMessage` |

---

### Orphaned Exports (1)

**`fetchNodeCatalog()` and `fetchPresets()`** — exported from `frontend/src/stores/pipelineStore.ts` lines 220 and 242, but neither function is imported or called anywhere in the frontend codebase. The node catalog is fetched inline in `App.tsx` via a raw `fetch('/api/pipeline/node-catalog')` call (line 49), and presets are fetched inline in `PresetSelector.tsx`. The exported store utilities exist but have zero consumers.

- File: `/home/prannayag/pragnition/robotics/dimensional-applications/frontend/src/stores/pipelineStore.ts`
- Lines: 220–253
- Impact: Low — functionality is duplicated by inline fetch calls; exported functions are dead code

---

### Missing Connections (2)

#### MISSING-01: `slam_restart_complete` WebSocket message never emitted by backend

**Expected:** After the restart loop in `main.py` completes (`coordinator._restarting = False`, line 472), a `slam_restart_complete` message should be broadcast to WebSocket clients so `useWebSocket.ts` can clear `slamStore.isRestarting` and re-fetch SLAM state.

**Actual:** No code in `backend/` or `src/` emits `{"type": "slam_restart_complete", …}`. The grep across all Python files returns zero results. The restart loop (lines 408–484 of `main.py`) updates `app.state` values but never calls `streaming_viz._message_queue.append(...)` with this message type.

**Impact:** After a user selects a backend via `POST /api/slam/select` or `POST /api/pipeline/apply`, the frontend `isRestarting` spinner in `AlgorithmSection.tsx` never clears unless the user happens to receive a `stats` push that triggers a stale-state refresh. The `ApplyBar.tsx` workaround (line 47: `setTimeout(() => { fetchSlamState(); setIsApplying(false); }, 1000)`) uses a 1-second blind timeout rather than a proper completion signal, which is unreliable if restart takes longer.

**Fix location:** `src/main.py`, after line 485 (`logger.info("Simulation restarted.")`), add:
```python
if streaming_viz is not None:
    streaming_viz._message_queue.append({"type": "slam_restart_complete", "payload": {}})
```

**Affected requirements:** ABST-05, CTRL-02

---

#### MISSING-02: `crash_fallback` does not actually restart with ICP

**Expected (per BACK-06):** When a subprocess backend crashes, the system should fall back to ICP and keep running.

**Actual:** `exploration_loop.py` lines 205–217 detect tracking loss (`"lost"` status) and emit `crash_fallback` to the WebSocket. The frontend correctly handles this: `useSlamStore.setCrashMessage`, `slamStore.setActive('icp', …)`. However, the `exploration_loop` only emits the message — it does not actually switch the robot's SLAM instance to the ICP backend. The robot continues calling `self._slam.process_frame(frame)` on the crashed subprocess backend. No live swap of `robot.slam` occurs in the exploration loop or coordinator.

**Impact:** The frontend shows a crash toast and updates its UI to say `icp` is active, but the backend is still running (or stalling on) the crashed subprocess. The `app.state.active_slam_backend` is not updated. A restart is the only actual recovery mechanism.

**Affected requirements:** BACK-06

---

### Broken E2E Flows (2)

#### FLOW-BREAK-01: SLAM backend selection — restart confirmation never reaches frontend

**Flow:** User selects backend in `AlgorithmSection.tsx` → `POST /api/slam/select` → `slam_routes.py` stores `pending_slam_backend`, calls `command_cb({"action": "restart"})` → `coordinator._command_handler` sets `_restart_requested = True`, `_should_stop = True` → `_run_simulation_loop` in `main.py` detects `coordinator.restart_requested`, executes restart → new backend active → **gap** → `useWebSocket.ts` `case 'slam_restart_complete'` clears spinner.

**Break at:** Step 7 (backend → frontend restart confirmation). The `slam_restart_complete` WebSocket message is never emitted (see MISSING-01). The `isRestarting` spinner in `AlgorithmSection.tsx` never clears via a proper signal.

**Steps complete:** REST call → pending state set → coordinator restart → new backend instantiated → `app.state.active_slam_backend` updated
**Steps broken:** WebSocket restart-complete notification → frontend spinner cleared → `fetchSlamState()` triggered by WS event

**Workaround in place:** `ApplyBar.tsx` uses a 1-second `setTimeout` (line 47). `AlgorithmSection.tsx` has no such workaround — its `isRestarting` flag is only cleared by the missing `slam_restart_complete` message.

---

#### FLOW-BREAK-02: Pipeline apply — `isApplying` state clears on fixed timeout, not backend signal

**Flow:** User clicks "Apply Pipeline" → `ApplyBar.handleConfirmApply` → `POST /api/pipeline/apply` → `pipeline_routes.py` calls `PipelineBuilder.build()` → stores `pending_pipeline_config` → calls `command_cb({"action": "restart"})` → restart loop reads `pipeline_config.backend_name` and `pipeline_config.merger_name` → restarts → **gap** → `setIsApplying(false)`.

**Break at:** Same as FLOW-BREAK-01. `ApplyBar.tsx` line 47 uses `setTimeout(..., 1000)` to clear the applying state and re-fetch SLAM state. If the simulation restart takes more than 1 second (common for ORB-SLAM3 or OpenVINS initialization), `isApplying` clears before the new backend is ready, and `fetchSlamState()` may return stale data showing the old backend.

**Steps complete:** Validation → serialize → POST → PipelineBuilder → pending config stored → restart triggered → new backend/merger active
**Steps broken:** Reliable restart-complete signal → spinner cleared at correct time → SLAM state reflects new pipeline

---

### Complete E2E Flows (5)

#### FLOW-OK-01: SLAM backend discovery and display

`main.py` imports `src.slam.backends` (line 56) → triggers `icp_backend`, `orbslam3_backend`, `openvins_backend`, `svopro_backend` registration → `GET /api/slam/backends` returns `SLAMRegistry.list_backends()` → `fetchSlamState()` in `slamStore.ts` fetches and calls `store.setBackends(data.backends)` → `AlgorithmSection.tsx` reads `useSlamStore(s => s.backends)` → renders picker. Full chain intact.

#### FLOW-OK-02: Merge strategy selection → coordinator swap

`POST /api/slam/merge-strategy` → `slam_routes.py` stores `pending_merge_strategy` on `app.state` → `command_cb({"action": "restart"})` → `coordinator._command_handler` sets `_restart_requested` → `_run_simulation_loop` reads `pending_merger` (line 434) → `MergeRegistry.create(pending_merger, …)` → `coordinator._merger = merger` (line 471) → `app.state.active_merge_strategy` updated (line 476). Wiring complete; same restart-notification gap as FLOW-BREAK-01 but the backend swap itself is correct.

#### FLOW-OK-03: Metrics pipeline — SLAM frames → dashboard display

`coordinator._send_viz_update()` calls `tracker.record_frame(rid, slam_metrics_dict, tracking_str)` (line 694) and `tracker.record_drift(…)` (lines 712–722) → `streaming_viz._update_stats()` calls `self._metrics_tracker.get_stats_payload()` → appends `{"type": "stats", "payload": {"slam_metrics": …}}` to `_message_queue` → `push_loop` in `server.py` drains and broadcasts → `useWebSocket.ts` `case 'stats'` extracts `payload.slam_metrics` and calls `useMetricsStore.getState().updateAllMetrics(…)` → `MetricsPanel.tsx` renders per-robot ATE/RPE/ms values. Full chain intact.

#### FLOW-OK-04: Output format toggle — frontend only

`ControlPanel.tsx` buttons call `setOutputMode('cloud'|'voxel'|'mesh')` → `metricsStore.setOutputMode` writes to `localStorage` and updates store → `SceneViewer.tsx` subscribes to `state.outputMode` change (line 187) → sets visibility of `pointCloudManager`, `voxelManager`, `meshManager`. This flow is entirely frontend; no backend call needed. Fully wired and self-contained.

#### FLOW-OK-05: Subprocess crash notification → frontend toast

`exploration_loop.py` detects `tracking_status == "lost"` and `hasattr(self._slam, '_bridge')` (subprocess backends expose `_bridge`) → appends `{"type": "crash_fallback", …}` to `streaming_viz._message_queue` → `push_loop` broadcasts → `useWebSocket.ts` `case 'crash_fallback'` calls `slamStore.setCrashMessage(…)` and `slamStore.setActive('icp', …)`. The notification chain is intact. The actual ICP fallback on the backend is not wired (MISSING-02), but the notification itself propagates correctly.

---

### Requirements Integration Map

| Requirement | Integration Path | Status | Issue |
|---|---|---|---|
| ABST-01 | `src/slam/protocol.py` defines `SLAMProtocol` → all backends implement it → `coordinator.py` uses `robot.slam.process_frame()` | WIRED | — |
| ABST-02 | `src/slam/registry.py` `SLAMRegistry` → `slam/backends/__init__.py` registers all backends → `/api/slam/backends` exposes list → `slamStore.fetchSlamState()` fetches | WIRED | — |
| ABST-03 | Each backend declares `PARAMETER_SCHEMA` → `SLAMRegistry.list_backends()` includes it → `slam_routes.py` returns it in `/api/slam/active` → `slamStore.activeParameters` → `AlgorithmSection.tsx` renders schema | WIRED | — |
| ABST-04 | Each backend declares `CAPABILITIES` → `SLAMRegistry.list_backends()` includes it → `slamStore.SLAMBackend.capabilities` type → `AlgorithmSection.tsx` badge display | WIRED | — |
| ABST-05 | `POST /api/slam/select` → `pending_slam_backend` → restart loop applies → new backend active | PARTIAL | `slam_restart_complete` WS message never emitted; frontend spinner relies on blind timeout (ApplyBar) or never clears (AlgorithmSection) |
| ABST-06 | `icp_backend.py` registered as `"icp"` → default in `SLAMRegistry._default` → `RobotInstance.create()` defaults to `"icp"` | WIRED | — |
| BACK-01 | `orbslam3_backend.py` imports `orbslam3`, registers via `@slam_backend("orbslam3")` → available in registry when `orbslam3-python` installed | WIRED | — |
| BACK-02 | `ORBSLAMBackend.process_frame()` uses `depth_to_pointcloud()` for dense cloud output | WIRED | — |
| BACK-03 | `openvins_backend.py` uses `SubprocessSLAMBridge` → spawns `openvins_harness` binary | WIRED | — |
| BACK-04 | `SensorFrame` includes `accel`, `gyro` fields → `openvins_backend` and `svopro_backend` read them for IMU | WIRED | — |
| BACK-05 | `svopro_backend.py` uses `SubprocessSLAMBridge` → spawns DSO binary | WIRED | — |
| BACK-06 | Subprocess crash detected via `tracking_status == "lost"` → `crash_fallback` WS notification reaches frontend | PARTIAL | Notification wired. Actual ICP substitution on crash not implemented — backend keeps running crashed subprocess; no live swap of `robot.slam` |
| MERG-01 | `merge_strategies/__init__.py` registers `icp_union`, `pgo_open3d`, `pgo_gtsam` → `MergeRegistry.list_strategies()` → `/api/slam/merge-strategies` | WIRED | — |
| MERG-02 | `POST /api/slam/merge-strategy` → `pending_merge_strategy` → restart → `MergeRegistry.create(name)` → `coordinator._merger` swap | WIRED | Same restart-signal gap as ABST-05; swap itself is correct |
| MERG-03 | `pgo_open3d` and `pgo_gtsam` implement `MergeProtocol.merge(robot_data)` → `coordinator._merge_via_protocol()` passes `RobotMapData` including poses for loop closure | WIRED | — |
| MERG-04 | All merge strategies expose `last_merged_voxels` attribute → `coordinator._send_viz_update()` reads it → `streaming_viz._update_cloud()` serializes it | WIRED | — |
| CTRL-01 | `GET /api/slam/backends` → `fetchSlamState()` → `slamStore.backends` → `AlgorithmSection.tsx` renders dropdown with capability badges | WIRED | — |
| CTRL-02 | Selecting backend calls `POST /api/slam/select` → restart → new backend → `slam_restart_complete` expected to confirm | PARTIAL | See ABST-05; restart completes but frontend confirmation signal missing |
| CTRL-03 | `activeParameters` from `slamStore` (populated from `/api/slam/active` `parameters` field) → `AlgorithmSection.tsx` renders param inputs from schema | WIRED | — |
| CTRL-04 | Frontend sends `slam_param_update` WS message → `server.py` `_dispatch_ws_message` handles it → stores in `pending_slam_params` (live) or acks `requires_restart` (non-live) → `useWebSocket.ts` `case 'slam_param_ack'` updates store | WIRED | — |
| CTRL-05 | `coordinator._send_viz_update()` → `tracker.record_frame()` / `record_drift()` → `streaming_viz.get_stats_payload()` → `stats` WS msg → `useMetricsStore.updateAllMetrics()` → `MetricsPanel.tsx` renders ATE/RPE/ms | WIRED | — |
| CTRL-06 | `MetricsTracker.capture_baseline()` on restart → `baseline` included in `stats` payload → `useMetricsStore.baseline` → `MetricsPanel.tsx` comparison view | WIRED | — |
| CTRL-07 | `ControlPanel.tsx` output mode buttons → `metricsStore.setOutputMode()` → `SceneViewer.tsx` visibility toggle for `pointCloudManager` / `voxelManager` / `meshManager` | WIRED | — |

**Requirements with no cross-phase wiring (self-contained):**

- CTRL-07 is entirely frontend-local. The toggle writes to `metricsStore` and `SceneViewer` reacts. No backend API call or WebSocket message is involved. This is correct behavior (client-side rendering decision), not a missing connection.

---

## Summary Table

| Finding | Severity | Requirement(s) | File(s) |
|---|---|---|---|
| `slam_restart_complete` never emitted by backend | High | ABST-05, CTRL-02 | `src/main.py` (lines 408–485), `backend/web/server.py` |
| `crash_fallback` emits notification but does not swap to ICP backend | Medium | BACK-06 | `src/exploration/exploration_loop.py` (lines 205–217) |
| `ApplyBar.tsx` uses 1-second blind timeout instead of restart signal | Medium | ABST-05 (pipeline path) | `frontend/src/components/pipeline/ApplyBar.tsx` (line 47) |
| `AlgorithmSection.tsx` `isRestarting` spinner never clears | Medium | CTRL-02 | `frontend/src/components/AlgorithmSection.tsx` |
| `fetchNodeCatalog()` and `fetchPresets()` exported but never called | Low | — | `frontend/src/stores/pipelineStore.ts` (lines 220–253) |

---

*Generated: 2026-03-25*
