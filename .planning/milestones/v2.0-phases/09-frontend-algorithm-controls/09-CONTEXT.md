# Phase 9: Frontend Algorithm Controls - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can browse available SLAM algorithms, select one before a session, and tune its parameters — all from the browser C2 interface. Live metrics dashboard and output format toggle are separate phases (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### Algorithm picker placement & interaction
- Picker lives inside ControlPanel as a collapsible section (expanded initially), positioned above Cloud Config
- Dropdown select style — standard `<select>`-like custom dropdown showing active backend name
- Selecting a different algorithm triggers immediately with a modal confirmation dialog ("Switch to ORB-SLAM3? This will restart the current session. [Cancel] [Switch]")
- Coexists with existing Restart buttons — dropdown = switch algorithm, Restart button = restart with same algorithm

### Parameter panel design
- Parameters render directly below the algorithm dropdown within the same collapsible section
- Controls are dynamically generated from the backend's JSON Schema: sliders for numeric ranges, toggles for booleans
- Numeric sliders include an editable text input alongside — user can type exact values or drag the slider
- Live-tunable vs startup-only distinction shown via visual indicators: lightning bolt icon for live params ("changes apply live"), lock icon for startup-only ("requires restart")
- Live-tunable params send immediately via WebSocket (`sendRaw({ type: 'slam_param_update', param, value })`) on change
- Startup-only params are staged locally and sent with `POST /api/slam/select` on restart

### Session restart UX
- Modal dialog for algorithm switch confirmation — center-screen with backdrop
- During restart: clear point cloud, show "Restarting with [algorithm]..." text overlay + spinner on the 3D viewer, scene mesh stays visible, robot markers reset
- Frontend fetches backend list via REST on app mount: `GET /api/slam/backends` and `GET /api/slam/active`, stored in Zustand
- Re-fetch after algorithm switch to update active backend state

### Capability & status display
- Capability badges shown as colored pill tags (small green-ish pills)
- Pills shown in two places: below the dropdown for the active backend AND inline in the dropdown list per backend for comparison
- Only show positive capabilities (what it CAN do), not negatives
- Unavailable backends visible in dropdown but grayed out and non-selectable
- Hover/tooltip on unavailable backends shows reason string (e.g., "orbslam3-python not installed")

### State management
- New dedicated `slamStore.ts` Zustand store for all SLAM state: backends list, active backend, parameters, isRestarting flag
- Separate from controlStore to keep SLAM concerns isolated

### Claude's Discretion
- Custom dropdown component implementation (native vs custom div-based)
- Modal component implementation (portal vs inline)
- Spinner/loading indicator design
- Exact pill tag colors and sizing
- Debounce strategy for slider → WebSocket parameter updates
- Error handling for failed backend switch or param update

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend API (Phase 8)
- `src/slam/protocol.py` — SLAMProtocol interface, SLAMResult dataclass, TrackingStatus enum. Defines CAPABILITIES and PARAMETER_SCHEMA class attributes
- `src/slam/registry.py` — SLAMRegistry with list_backends() returning name, display, available, capabilities, parameter_schema, reason
- `src/slam/backends/icp_backend.py` — ICPBackend as reference for CAPABILITIES and PARAMETER_SCHEMA format

### Phase 8 context (REST API design)
- `.planning/phases/08-backend-abstraction-icp-wrap/08-CONTEXT.md` — REST endpoint structure: GET /api/slam/backends, POST /api/slam/select, GET /api/slam/active, PATCH /api/slam/params. Live-tunable vs startup-only distinction. Availability with install hints.

### Existing frontend (Phase 6)
- `frontend/src/components/ControlPanel.tsx` — Where algorithm section will be added. Has existing patterns for collapsible sections, buttons, sliders
- `frontend/src/stores/controlStore.ts` — Existing Zustand store pattern with sendRaw/sendCommand for WebSocket communication
- `frontend/src/hooks/useWebSocket.ts` — WebSocket hook dispatching messages to stores. New slam_param_update message type needed
- `frontend/src/utils/messageTypes.ts` — WSMessage type union that needs new SLAM message types
- `frontend/src/components/Sidebar.tsx` — Sidebar layout with header, robot cards, ControlPanel at bottom
- `frontend/src/App.tsx` — Root layout with CSS Grid (viewer, sidebar, camera strip)

### Phase 6 context (UI decisions)
- `.planning/phases/06-react-c2-web-interface-for-multi-robot-visualization-and-control/06-CONTEXT.md` — Mission control layout, dark theme (#1a1a3e), Zustand state management, WebSocket transport pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ControlPanel.tsx`: Existing collapsible sections (Cloud Config, Cloud Offset) — same pattern for Algorithm section
- `controlStore.ts`: `sendRaw()` function for WebSocket messages — reuse for `slam_param_update`
- `useWebSocket.ts`: Message dispatcher switch — add cases for SLAM-related ack messages
- Speed slider in ControlPanel: Existing range input pattern — reuse for numeric parameter sliders
- Color mode toggle: Existing toggle button pattern — reuse for boolean parameters

### Established Patterns
- **Zustand stores**: Flat state with setter functions (controlStore, robotStore). New slamStore follows same pattern
- **Dark theme**: Background #1a1a3e, borders #2a2a4a, text #888/#aaa, accent colors for buttons. All new UI matches this
- **Inline styles**: All components use React inline styles, no CSS modules or Tailwind
- **WebSocket sendRaw**: `sendRaw?.({ type: 'message_type', ...data })` pattern for frontend → backend communication
- **Collapsible sections**: Click-to-toggle pattern with ▼/▶ indicators (Cloud Config uses this)

### Integration Points
- `ControlPanel.tsx`: New Algorithm section added between existing controls and Cloud Config
- `useWebSocket.ts`: New message handler for `slam_param_ack` or similar backend responses
- `messageTypes.ts`: New type entries in WSMessage union for SLAM messages
- `App.tsx` or new hook: REST fetch for `/api/slam/backends` and `/api/slam/active` on mount
- `SceneViewer.tsx`: Loading overlay during restart transition

</code_context>

<specifics>
## Specific Ideas

- Modal confirmation for algorithm switch — center-screen with dark backdrop, matching the existing dark theme aesthetic
- Capability pills should feel like GitHub topic tags — small, rounded, subtle color
- The algorithm dropdown should be a custom component (not native `<select>`) to support rich items with badges and grayed-out entries with tooltips

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-frontend-algorithm-controls*
*Context gathered: 2026-03-23*
