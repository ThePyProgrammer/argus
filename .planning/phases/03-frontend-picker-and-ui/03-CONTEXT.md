# Phase 3: frontend-picker-and-ui - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the user-facing detector control surface in the browser: Detector dropdown (populated from `GET /api/detectors/backends`) with capability badges, Lifter dropdown (hidden when `outputs_3d_natively: true`), detector parameter panel with debounced `detector_param_update` WS sends, restart overlay that dismisses only on `detector_restart_complete` (Phase 2 already guarantees this fires AFTER `warmup()`), RGB 2D bbox overlay per robot in CameraFeed, and a `detectorStore` (Zustand) that structurally mirrors `slamStore`. Also: Lifter REST routes (`GET /api/detectors/lifters`, `POST /api/detectors/lifter-select`, `GET /api/detectors/active-lifter`, `PATCH /api/detectors/lifter-params`) on the backend to power the lifter dropdown; Phase 4's `PointClusterLifter` lands needing only registry registration.

**Out of scope (deferred to later phases):**
- `PointClusterLifter` PCA-OBB implementation — Phase 4 (this phase ships the REST + UI surface; `median_depth` is the only available lifter until Phase 4)
- Live detection metrics (inference_ms p50/p95, detections/frame, 3d_center_jitter_m) — Phase 6 (DET-METRICS-01)
- `CrashToast` for detector crash_fallback — Phase 5 (DET-MODELS-06); Phase 3 just logs the existing `detector_restart_complete` WS signal path
- Non-YOLO backends populating the dropdown — Phase 5 (Phase 3 will show only `yolov11` in the dropdown)
- `DetectorNode` / pipeline-editor integration — Phase 7

</domain>

<decisions>
## Implementation Decisions

### Component Architecture (DET-UI-01..06)

- **D-01:** Component strategy is **clone + rename** — duplicate the SLAM component set into Detector variants, each tied to its own store. No generic refactor of existing SLAM components (zero risk to v2.0 SLAM UX). Clones:
  - `AlgorithmDropdown.tsx` (149 lines) → `DetectorDropdown.tsx`
  - `AlgorithmSection.tsx` (231 lines) → `DetectorSection.tsx` (becomes the parent section that contains dropdown + capability-badge row + lifter dropdown + parameter panel + error banner + ConfirmModal call site)
  - `ParameterPanel.tsx` (109 lines) → `DetectorParameterPanel.tsx` (mirrors the `live_tunable` / debounced-update logic but reads from `detectorStore` and sends `detector_param_update` via `sendRaw`)
  - `stores/slamStore.ts` (88 lines) → `stores/detectorStore.ts`
  - NEW: `LifterDropdown.tsx` (clone of DetectorDropdown, reads `detectorStore.lifters` + `activeLifter`)
- **D-02:** `detectorStore` shape mirrors `slamStore` **exactly**:
  - Fields: `backends, lifters, activeBackend, activeDisplay, activeParameters, activeLifter, activeLifterDisplay, activeLifterParameters, stagedParams, stagedLifterParams, isRestarting, error, crashMessage`
  - Setters: `setBackends, setLifters, setActive, setActiveLifter, setRestarting, stageParam, stageLifterParam, clearStagedParams, clearStagedLifterParams, setError, updateActiveParam, updateActiveLifterParam, setCrashMessage, clearCrashMessage`
  - `fetchDetectorState()` mirrors `fetchSlamState()` — parallel fetch of `/backends`, `/active`, `/lifters`, `/active-lifter`
- **D-03:** **DET-UI-06 verification** via a Vitest structural-equivalence test in `frontend/src/stores/__tests__/detectorStore.shape.test.ts`. Test imports both store type definitions + default states, asserts `Object.keys(detectorStore.getState())` superset of `Object.keys(slamStore.getState())` (detector adds lifter fields), and asserts every SLAM setter name has a detector counterpart. TypeScript compile-time check plus runtime diff. Fails if either store drifts from the other's shape.

### Capability Badges (DET-UI-01)

- **D-04:** `CapabilityBadge` is **extended in-place** to accept `{label, value}` props. Current signature `<CapabilityBadge name />` (boolean-gated) migrates to `<CapabilityBadge label="framework" value="ultralytics" />`. SLAM call sites (`AlgorithmSection.tsx:169`) update to pass `label={cap} value={true}` using a boolean-default rendering that preserves their current pill styling. Non-boolean values render as `"{value}"` text; booleans render as the label only (current behavior) when `value === true`, omitted when `value === false`. Latency hint renders as `~{value}ms` (pill prefix `~`). License renders verbatim (e.g., `AGPL-3.0`). Framework renders as-is (e.g., `ultralytics`).
- **D-05:** Badges shown in DetectorSection for the active detector: **`framework`, `license`, `cpu_latency_hint_ms`** — exactly the three keys DET-UI-01 lists. `outputs_3d_natively` is FUNCTIONAL (drives `LifterDropdown` visibility) not rendered. `input_type` is not a visible badge (reserved for Phase 5 when `RGB_TEXT_PROMPT` backends like OWLv2 arrive and need a UI prompt input). Adding/removing visible keys is a one-line change in `DetectorSection.tsx`.
- **D-06:** Dropdown option rows (inside `DetectorDropdown.tsx`, per-backend in the list) show a compact badge row with the SAME three keys. Unavailable backends (`available: false`) show greyed-out option + `reason` install hint (mirrors `AlgorithmDropdown.tsx:34-77` pattern).

### Lifter Dropdown (DET-UI-02)

- **D-07:** `LifterDropdown` renders **inline inside `DetectorSection`**, below the Detector capability-badge row and above the Detector ParameterPanel. Single collapsible section ("OBJECT DETECTION") groups detector + its lifter — cohesive because lifter is a detector-dependent choice (hidden when `outputs_3d_natively: true`). NOT a separate sidebar section.
- **D-08:** Visibility gate: `LifterDropdown` renders only when `activeBackendInfo?.capabilities?.outputs_3d_natively === false`. When the active detector advertises `outputs_3d_natively: true` (future BoxeR), the dropdown is hidden AND the Detector ParameterPanel still renders (params belong to the detector, not the lifter).
- **D-09:** **Switching the lifter triggers a full restart** — mirrors the detector switch flow exactly. UX consistency over efficiency. Flow: `ConfirmModal` ("Switch lifter to X? This will restart the current session.") → `POST /api/detectors/lifter-select {lifter, params?}` → backend sets `app.state.pending_lifter` + triggers `command_callback({"action": "restart"})` → `main.py` restart block constructs the new lifter via `Detection3DRegistry.create(pending_lifter)`, threads it into the DetectorWorkerPool's workers, fires `detector_restart_complete` with `{backend, lifter}` payload after warmup → overlay dismisses. This means users who switch lifter mid-session lose current map state exactly as they would for a detector switch — acceptable because lifter switches are rare and the trade-off is ONE restart code path instead of two.
- **D-10:** **Lifter REST routes ship in Phase 3** (added to `backend/web/detector_routes.py`):
  - `GET /api/detectors/lifters` → `{lifters: Detection3DRegistry.list_backends()}`
  - `POST /api/detectors/lifter-select {lifter, params?}` → set `app.state.pending_lifter` + `pending_lifter_params`, call `command_callback({"action": "restart"})`, return `{status: "restarting", lifter}`
  - `GET /api/detectors/active-lifter` → `{lifter, display, parameters}`
  - `PATCH /api/detectors/lifter-params {params}` → per-key `live_tunable` split (mirror `/params` handler)
  - `src/main.py` restart block extended to consume `pending_lifter` AFTER the detector pool is constructed (so workers receive the new lifter at the same time as any detector rebuild). Default lifter on first boot: `median_depth`. Phase 4's `PointClusterLifter` lands by simply registering via `@detection_3d("point_cluster", ...)` — no route changes.

### Restart Overlay + ConfirmModal (DET-UI-04)

- **D-11:** `RestartOverlay` is **extended in-place** to accept a `subsystem: 'slam' | 'detector' | 'lifter'` prop + `name` prop. Message changes from hard-coded "Restarting with {algorithmName}..." to: `"Restarting SLAM with {name}..."` / `"Restarting detector with {name}..."` / `"Restarting lifter with {name}..."`. SLAM call site (currently passing `algorithmName`) migrates to `subsystem="slam" name={...}`.
- **D-12:** **Concurrent restarts render stacked overlays.** If the user triggers a SLAM restart and a detector restart within the same frame (e.g., from the pipeline editor applying changes), both overlays mount — one per subsystem. Absolute-positioned, stacked vertically in the SceneViewer area. Each dismisses independently when its respective `*_restart_complete` WS message arrives. Phase 3 deliverable is the mounting logic; pipeline-editor-driven concurrent restarts are Phase 7's problem.
- **D-13:** **Overlay DOM mount:** alongside the existing SLAM `RestartOverlay` in the main canvas area (same parent as SceneViewer / CameraStrip; absolute-positioned over the viewport). Detector restart blurs the same viewport as SLAM restart. This is semantically loose (detector restart doesn't invalidate the 3D map) but visually clean and matches user mental model of "system is working, don't click things right now."
- **D-14:** **ConfirmModal is REUSED** — it's already generic (takes `heading`, `body`, `confirmLabel`, `cancelLabel`, `confirmDisabled`, `confirmText`, `onConfirm`, `onCancel` props). DetectorSection passes detector-specific text:
  - Switch: `heading="Switch Detector"`, body: `"Switch detector to {display}? This will restart perception."`, confirm: `"Switch Detector"`, cancel: `"Keep Current"`
  - Lifter switch: `heading="Switch Lifter"`, body: `"Switch lifter to {display}? This will restart the current session."`, confirm: `"Switch Lifter"`, cancel: `"Keep Current"`
- **D-15:** **Polling fallback** mirrors `AlgorithmSection::pollForRestart` — 500ms × 20 attempts (10s window) polling `GET /api/detectors/active` until `backend === expectedBackend`; if timeout, set error "Restart timed out. Try again or refresh the page." This fires when the WS is disconnected or drops the `detector_restart_complete` message. The primary path is still WS-driven (`useWebSocket.ts:140-144` already handles `detector_restart_complete`; Phase 3 wires `detectorStore.setRestarting(false)` on receipt — currently log-only).

### RGB 2D Bbox Overlay (DET-UI-05)

- **D-16:** DET-UI-05 **scaffolding already landed in Phase 2** (`CameraFeed.tsx:32-34, 124-125, 182-195` — consumes `det.bbox_xyxy` from the `detections_3d` envelope items). Phase 3 polishes:
  - Per-class color palette (reuse existing `OKABE_ITO_RGB` palette indexed by class_id modulo 8)
  - Hover tooltip shows `class_name + score` (2 decimal places) — already partial
  - Labels pinned to top-left of bbox with backdrop for readability
  - Graceful degradation unchanged: items without `bbox_xyxy` simply skip their 2D overlay (future `outputs_3d_natively` backends that don't provide 2D bboxes)
- No new files for DET-UI-05; edits to `CameraFeed.tsx` only.

### Sidebar Integration

- **D-17:** `DetectorSection` mounts in `Sidebar.tsx` as a new collapsible section labeled **"OBJECT DETECTION"**, inserted BETWEEN the existing SLAM ALGORITHM section and the MERGE STRATEGY section (if any). Section header style matches SLAM ALGORITHM (12px bold, color #888, chevron toggle).
- **D-18:** `Sidebar` import list grows by exactly one line: `import DetectorSection from './DetectorSection'`. No other files in the existing sidebar surface change.

### Claude's Discretion

- Exact typography/spacing inside DetectorSection (mirror SLAM defaults)
- Restart spinner color (reuse SLAM's `#2ecc71`)
- Param panel confidence-threshold default value (read from backend's `parameter_schema.properties.confidence.default`, fall back to 0.5)
- 2D bbox overlay opacity/stroke width (mirror existing DetectionBoxes 3D rendering palette)
- ConfirmModal body text wording (small variations within the decided pattern)
- Which Vitest test runner configuration to use for DET-UI-06 (reuse whichever is already configured in `frontend/package.json`)

### Folded Todos

None — no pending todos matched Phase 3 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §Phase 3 — goal + 5 success criteria
- `.planning/REQUIREMENTS.md` §DET-UI-01..06 — the 6 requirements this phase must deliver
- `.planning/PROJECT.md` — overall v3.0 vision, "browser-based C2" non-negotiable
- `.planning/phases/02-per-robot-worker-and-wire-plumbing/02-CONTEXT.md` — Phase 2 REST/WS contract (select → restart → warmup → detector_restart_complete)
- `.planning/phases/02-per-robot-worker-and-wire-plumbing/VERIFICATION.md` — confirms Phase 3 prerequisites are met on main
- `.planning/research/ARCHITECTURE.md` §Answer to Q5 (FastAPI routes + WS messages) — OBB wire format the CameraFeed overlay consumes

### In-Tree Patterns to Mirror (Frontend)
- `frontend/src/stores/slamStore.ts` (88 lines) — template for `detectorStore.ts`
- `frontend/src/components/AlgorithmDropdown.tsx` (149 lines) — template for `DetectorDropdown.tsx` AND `LifterDropdown.tsx`
- `frontend/src/components/AlgorithmSection.tsx` (231 lines) — template for `DetectorSection.tsx` (parent section)
- `frontend/src/components/ParameterPanel.tsx` (109 lines) — template for `DetectorParameterPanel.tsx` (mirrors `live_tunable` + debounced `sendRaw` pattern; send type is `detector_param_update`)
- `frontend/src/components/CapabilityBadge.tsx` (21 lines) — **extend in-place** (accept `label` + `value` props; SLAM call sites migrate)
- `frontend/src/components/RestartOverlay.tsx` (38 lines) — **extend in-place** (accept `subsystem` prop)
- `frontend/src/components/ConfirmModal.tsx` — **reused as-is** (already generic)
- `frontend/src/components/Sidebar.tsx` — mount point for `DetectorSection`
- `frontend/src/hooks/useWebSocket.ts:132-150` — `detections_3d` + `detector_restart_complete` + `detector_param_ack` handlers already exist; Phase 3 wires `detectorStore.setRestarting(false)` on `detector_restart_complete`

### In-Tree Patterns to Mirror (Backend)
- `backend/web/slam_routes.py::list_merge_strategies / select_merge_strategy / get_active_merge_strategy / patch_merge_params` — EXACT STRUCTURAL TEMPLATE for the 4 new lifter routes in `detector_routes.py`
- `src/main.py` lines 430-540 restart block — the block Phase 2 extended for `pending_detector_backend`; Phase 3 adds a `pending_lifter` branch inside the same `if coordinator._restart_requested:` scope
- `src/perception/registry.py::Detection3DRegistry` — lifter registry (already populated with `median_depth` on main); Phase 3 does NOT touch registry

### Code to Modify (Phase 3)
- `frontend/src/components/CapabilityBadge.tsx` — extend props (D-04)
- `frontend/src/components/RestartOverlay.tsx` — accept `subsystem` prop (D-11)
- `frontend/src/components/AlgorithmSection.tsx` — migrate to new CapabilityBadge + RestartOverlay signatures (back-compat adapter)
- `frontend/src/components/Sidebar.tsx` — add `<DetectorSection />` mount (D-18)
- `frontend/src/components/CameraFeed.tsx` — DET-UI-05 polish (per-class colors, label backdrop; D-16)
- `frontend/src/hooks/useWebSocket.ts` — wire `detectorStore.setRestarting(false)` + `fetchDetectorState()` on `detector_restart_complete` (currently log-only)
- `backend/web/detector_routes.py` — add 4 lifter routes (D-10)
- `backend/web/server.py` — initialize `app.state.active_lifter = "median_depth"`, `app.state.pending_lifter = None`
- `src/main.py` restart block — consume `pending_lifter` after pool is constructed (D-09, D-10)

### Code to Create (Phase 3)
- `frontend/src/stores/detectorStore.ts` (D-02)
- `frontend/src/stores/__tests__/detectorStore.shape.test.ts` (D-03 — structural equivalence test)
- `frontend/src/components/DetectorDropdown.tsx` (D-01)
- `frontend/src/components/DetectorSection.tsx` (D-01 — parent component; mounts dropdown + lifter dropdown + capability badges + param panel + error banner + ConfirmModal)
- `frontend/src/components/LifterDropdown.tsx` (D-07, D-08)
- `frontend/src/components/DetectorParameterPanel.tsx` (D-01 — debounced `detector_param_update` via sendRaw)
- `tests/perception/test_lifter_routes.py` — REST round-trip tests for the 4 new lifter routes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/components/SliderField.tsx` — already shared (numeric slider) — used by SLAM ParameterPanel, will be used by DetectorParameterPanel verbatim
- `frontend/src/components/ConfirmModal.tsx` — fully props-driven; used for both detector + lifter switches (D-14)
- `frontend/src/utils/debounce.ts` — already used by SLAM ParameterPanel for 200ms debounced slider updates; DetectorParameterPanel uses it identically
- `frontend/src/stores/controlStore.ts::sendRaw` — the raw WS send function; DetectorParameterPanel calls `sendRaw({type: 'detector_param_update', param, value})`
- `frontend/src/utils/palette.ts::OKABE_ITO_RGB` — the robot/class color palette reused for per-class bbox coloring in CameraFeed (D-16)
- `frontend/src/hooks/useWebSocket.ts:132-150` — message handlers for `detections_3d`, `detector_restart_complete`, `detector_param_ack` already scaffolded in Phase 2 (currently log-only on the restart message; Phase 3 adds the store wiring)
- `backend/web/slam_routes.py` — exact structural clone source for the 4 new lifter routes

### Established Patterns
- **Pre-session selection with restart + polling fallback** — SLAM pattern: set `pending_*`, POST, wait for `*_restart_complete` WS, fall back to REST polling every 500ms × 20 attempts if WS is slow/dropped. Mirror for detector AND lifter.
- **`live_tunable` split on PATCH /params** — Param handlers in SLAM return `applied` (live) or `requires_restart` (staged in `pending_*_params`); the SLAM ParameterPanel uses this flag to decide between `sendRaw('slam_param_update')` (live) and `stageParam()` (restart-required). Detector mirrors.
- **Zustand store shape** — Flat state + flat setters + top-level fetch function (`fetchSlamState`). No slices, no middleware. D-02 mirrors this.
- **Capability badge rendering** — Currently gates on `true`; Phase 3 generalizes to render arbitrary `{label, value}` pairs.
- **Section header style** — 12px bold, color `#888`, chevron toggle, `borderTop: '1px solid #2a2a4a'`, `marginTop: 16px` inside Sidebar. DetectorSection mirrors.

### Integration Points
- **Sidebar** mounts DetectorSection (`Sidebar.tsx`). One-line import + one-line JSX addition.
- **useWebSocket** already dispatches `detections_3d` to `robotStore.updateDetections(rid, payload)` (Phase 2). Phase 3 adds `detectorStore.setRestarting(false) + fetchDetectorState()` on `detector_restart_complete` (currently log-only).
- **CameraFeed** already reads `robots.get(rid)?.detections_3d?.items` and renders positioned HTML divs with optional `bbox_xyxy` (Phase 2). Phase 3 polishes colors + label styling.
- **main.py restart block** already has a detector branch (Phase 2 Plan 02-09). Phase 3 extends the same block with a lifter sub-branch.

### Constraints
- `frontend/src/components/AlgorithmSection.tsx` is unchanged in Phase 3 EXCEPT migration to the new CapabilityBadge + RestartOverlay prop signatures. No behavioral changes to SLAM UX.
- Phase 3 does NOT introduce Phase 4's `PointClusterLifter` — the lifter dropdown will show ONLY `median_depth` until Phase 4 lands.
- Phase 3 does NOT fire `CrashToast` for detector crashes — that's Phase 5 (DET-MODELS-06). The `crash_fallback` WS handler already has a `subsystem` discriminator (Phase 2) but the detector branch is log-only.
- Phase 3 does NOT show the live inference metrics (p50/p95, jitter) — those belong to Phase 6's MetricsPanel.

</code_context>

<specifics>
## Specific Ideas

- DetectorSection title: "OBJECT DETECTION" (matches existing "SLAM ALGORITHM" 12px bold + #888 header style).
- ConfirmModal copy: `"Switch detector to {display}? This will restart perception."` for detector swap; `"Switch lifter to {display}? This will restart the current session."` for lifter swap.
- RestartOverlay message templates: `"Restarting SLAM with {name}..."`, `"Restarting detector with {name}..."`, `"Restarting lifter with {name}..."`.
- Lifter REST route shape (mirror of existing merge-strategy routes): `GET /api/detectors/lifters` returns `{lifters: [{name, display, available, capabilities, parameter_schema, reason?}]}` (clone of SLAM merge-strategy list shape).
- CapabilityBadge rendering convention: boolean true → label-only pill (current behavior); string/number → `"{label}: {value}"` or prefixed (`~{value}ms` for latency); never render `false` booleans. Null/undefined values skip the badge.
- DET-UI-06 test lives at `frontend/src/stores/__tests__/detectorStore.shape.test.ts`; run via `npm test` (or whichever runner frontend/package.json has configured).

</specifics>

<deferred>
## Deferred Ideas

- **Generic BackendSection<T> refactor** — explicitly rejected in D-01. If a third backend type (e.g., merger) needs the same surface, revisit.
- **Concurrent restart aggregation into a single overlay** — stacked overlays ship in Phase 3 (D-12). Combining into one `"Restarting: SLAM + Detector"` aggregate message is a Phase 7 pipeline-editor polish if and when concurrent restarts become common.
- **CrashToast for detector crashes** — Phase 5 DET-MODELS-06 (requires BoxeR subprocess crash-fallback machinery that Phase 3 doesn't have yet).
- **Live detection metrics in DetectorSection** — Phase 6 DET-METRICS-01 (MetricsPanel owns this).
- **Detector per-robot dispatch UI** (heterogeneous per-robot backends) — Phase 8 DET-STRETCH-04.
- **`input_type: RGB_TEXT_PROMPT` text-prompt UI** — Phase 5 DET-MODELS-04 (OWLv2 ships with the required prompt field; Phase 3 only handles RGB_ONLY).
- **DetectorSection hot-swap without restart** — rejected for consistency with SLAM; detector switch triggers full restart (Phase 2 D-02 already locked this). Lifter switch also triggers full restart (D-09, UX consistency with detector).

### Reviewed Todos (not folded)

None — no pending todos matched Phase 3 scope.

</deferred>

---

*Phase: 03-frontend-picker-and-ui*
*Context gathered: 2026-04-14*
