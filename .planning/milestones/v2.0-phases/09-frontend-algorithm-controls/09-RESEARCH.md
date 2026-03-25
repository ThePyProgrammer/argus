# Phase 9: Frontend Algorithm Controls - Research

**Researched:** 2026-03-23
**Domain:** React UI components, Zustand state management, REST/WebSocket integration, dynamic form rendering
**Confidence:** HIGH

## Summary

Phase 9 adds the SLAM algorithm picker, dynamic parameter tuning panel, and session restart UX to the existing React/Zustand/Three.js C2 frontend. The backend REST API endpoints already exist (`GET /api/slam/backends`, `POST /api/slam/select`, `GET /api/slam/active`, `PATCH /api/slam/params`) from Phase 8, and the WebSocket transport layer with `sendRaw` is established. This phase is purely frontend work: new components, a new Zustand store, REST fetch calls (first ones in this codebase), Vite proxy configuration for `/api`, and WebSocket message handling for live parameter updates.

The existing codebase is React 18.3.1 + Zustand 5.0.12 + Vite 6, uses inline styles everywhere (no CSS modules or Tailwind), and has zero external UI libraries. All components are functional with hooks. The dark theme (#1a1a3e background, #2a2a4a borders, #888/#aaa text) is consistent across ControlPanel, Sidebar, and SceneViewer. There is no existing test infrastructure for the frontend (no vitest, jest, or playwright config), though the Python backend has pytest tests for the SLAM routes.

**Primary recommendation:** Build all new UI as vanilla React components with inline styles matching the existing pattern. Create a dedicated `slamStore.ts` Zustand store. Add `/api` proxy to Vite config. Use native `fetch()` for REST calls (no axios needed for 4 endpoints). Implement custom dropdown and modal as simple div-based components with portal for modal.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Picker lives inside ControlPanel as a collapsible section (expanded initially), positioned above Cloud Config
- Dropdown select style -- standard `<select>`-like custom dropdown showing active backend name
- Selecting a different algorithm triggers immediately with a modal confirmation dialog ("Switch to ORB-SLAM3? This will restart the current session. [Cancel] [Switch]")
- Coexists with existing Restart buttons -- dropdown = switch algorithm, Restart button = restart with same algorithm
- Parameters render directly below the algorithm dropdown within the same collapsible section
- Controls are dynamically generated from the backend's JSON Schema: sliders for numeric ranges, toggles for booleans
- Numeric sliders include an editable text input alongside -- user can type exact values or drag the slider
- Live-tunable vs startup-only distinction shown via visual indicators: lightning bolt icon for live params, lock icon for startup-only
- Live-tunable params send immediately via WebSocket (`sendRaw({ type: 'slam_param_update', param, value })`) on change
- Startup-only params are staged locally and sent with `POST /api/slam/select` on restart
- Modal dialog for algorithm switch confirmation -- center-screen with backdrop
- During restart: clear point cloud, show "Restarting with [algorithm]..." text overlay + spinner on 3D viewer, scene mesh stays visible, robot markers reset
- Frontend fetches backend list via REST on app mount: `GET /api/slam/backends` and `GET /api/slam/active`, stored in Zustand
- Re-fetch after algorithm switch to update active backend state
- Capability badges shown as colored pill tags (small green-ish pills)
- Pills shown in two places: below the dropdown for active backend AND inline in dropdown list per backend
- Only show positive capabilities (what it CAN do), not negatives
- Unavailable backends visible in dropdown but grayed out and non-selectable
- Hover/tooltip on unavailable backends shows reason string
- New dedicated `slamStore.ts` Zustand store for all SLAM state: backends list, active backend, parameters, isRestarting flag
- Separate from controlStore to keep SLAM concerns isolated

### Claude's Discretion
- Custom dropdown component implementation (native vs custom div-based)
- Modal component implementation (portal vs inline)
- Spinner/loading indicator design
- Exact pill tag colors and sizing
- Debounce strategy for slider to WebSocket parameter updates
- Error handling for failed backend switch or param update

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CTRL-01 | Algorithm picker dropdown lists available SLAM backends with their capability badges | Custom dropdown component consuming `slamStore.backends`; REST fetch from `GET /api/slam/backends` on mount; pill badge rendering from capabilities dict |
| CTRL-02 | Selecting an algorithm triggers pre-session restart with the chosen backend | Modal confirmation component; `POST /api/slam/select` call; `isRestarting` state in slamStore; restart overlay on SceneViewer; re-fetch active backend after restart |
| CTRL-03 | Parameter tuning panel renders dynamically from backend's JSON schema | Schema-driven form renderer mapping JSON Schema `type` + `minimum`/`maximum` to sliders/toggles; `live_tunable` metadata drives icon indicators |
| CTRL-04 | Parameter changes are sent to backend via WebSocket and applied (where supported) | `sendRaw({ type: 'slam_param_update', param, value })` for live-tunable; debounced slider updates; `slam_param_ack` handler in useWebSocket; startup-only params staged in slamStore |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 18.3.1 | UI rendering | Already installed, all components use it |
| zustand | 5.0.12 | State management | Already installed, established store pattern (controlStore, robotStore) |
| vite | 6.x | Build/dev server | Already installed, proxy config needed |
| typescript | 5.6.x | Type checking | Already installed, strict mode enabled |

### Supporting (no new dependencies needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| native fetch | browser built-in | REST API calls | First REST calls in frontend -- `GET /api/slam/backends`, `POST /api/slam/select`, etc. |
| ReactDOM.createPortal | 18.3.1 (built-in) | Modal rendering | Render confirmation modal outside component tree for z-index/stacking |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| native fetch | axios | Overkill for 4 simple endpoints; adds dependency for zero benefit |
| Custom dropdown | react-select | Heavy dependency (30KB+); project uses inline styles exclusively; custom component matches existing ControlPanel patterns |
| Custom modal | react-modal / headless-ui | Another dependency; the modal is simple (backdrop + centered card + 2 buttons); project has no UI library convention |
| lodash.debounce | Custom debounce or setTimeout | Zero-dep debounce is ~5 lines; no reason to add lodash for one utility |

**Installation:**
```bash
# No new packages needed -- everything is built-in or already installed
```

## Architecture Patterns

### New Files to Create
```
frontend/src/
  stores/
    slamStore.ts              # New Zustand store for SLAM state
  components/
    AlgorithmSection.tsx      # Collapsible section: dropdown + params + badges
    AlgorithmDropdown.tsx     # Custom dropdown with rich items (badges, disabled states)
    ParameterPanel.tsx        # Dynamic form renderer from JSON Schema
    ConfirmModal.tsx          # Reusable confirmation modal (portal-based)
    CapabilityBadge.tsx       # Pill tag component for capabilities
    RestartOverlay.tsx        # Loading overlay for SceneViewer during restart
  utils/
    messageTypes.ts           # Extend existing WSMessage union (add slam types)
    debounce.ts               # Simple debounce utility (or inline in ParameterPanel)
```

### Modified Files
```
frontend/src/
  components/
    ControlPanel.tsx          # Add AlgorithmSection before Cloud Config section
    SceneViewer.tsx           # Add RestartOverlay conditional render
  hooks/
    useWebSocket.ts           # Add slam_param_ack handler, dispatch to slamStore
  utils/
    messageTypes.ts           # Add 'slam_param_ack', 'slam_backends' to WSMessage type union
  vite.config.ts              # Add /api proxy to localhost:8000
```
**Backend modified:**
```
backend/web/
  server.py                   # Add slam_param_update handler in _dispatch_ws_message
```

### Pattern 1: Zustand Store for SLAM State
**What:** Dedicated `slamStore.ts` following the flat state + setter pattern established by `controlStore.ts` and `robotStore.ts`.
**When to use:** All SLAM-related state: backends list, active backend name, current parameters, restart flag, errors.
**Example:**
```typescript
// Source: Existing controlStore.ts pattern + Phase 9 CONTEXT.md decisions
import { create } from 'zustand';

interface SLAMBackend {
  name: string;
  display: string;
  available: boolean;
  capabilities: Record<string, boolean>;
  parameter_schema: {
    type: string;
    properties: Record<string, {
      type: string;
      default?: number | boolean;
      minimum?: number;
      maximum?: number;
      description?: string;
      live_tunable?: boolean;
    }>;
  };
  reason?: string;
}

interface SlamStoreState {
  backends: SLAMBackend[];
  activeBackend: string;
  activeDisplay: string;
  activeParameters: Record<string, unknown>;
  stagedParams: Record<string, unknown>;  // startup-only changes pending restart
  isRestarting: boolean;
  error: string | null;

  setBackends: (backends: SLAMBackend[]) => void;
  setActive: (name: string, display: string, parameters: Record<string, unknown>) => void;
  setRestarting: (restarting: boolean) => void;
  stageParam: (key: string, value: unknown) => void;
  clearStagedParams: () => void;
  setError: (error: string | null) => void;
}

export const useSlamStore = create<SlamStoreState>((set) => ({
  backends: [],
  activeBackend: 'icp',
  activeDisplay: 'ICP Odometry',
  activeParameters: {},
  stagedParams: {},
  isRestarting: false,
  error: null,

  setBackends: (backends) => set({ backends }),
  setActive: (name, display, parameters) => set({
    activeBackend: name,
    activeDisplay: display,
    activeParameters: parameters,
  }),
  setRestarting: (restarting) => set({ isRestarting: restarting }),
  stageParam: (key, value) => set((s) => ({
    stagedParams: { ...s.stagedParams, [key]: value },
  })),
  clearStagedParams: () => set({ stagedParams: {} }),
  setError: (error) => set({ error }),
}));
```

### Pattern 2: REST Fetch on Mount
**What:** Fetch backend list and active backend from REST API when app mounts. No existing fetch pattern in codebase -- this establishes one.
**When to use:** App initialization, post-restart re-fetch.
**Example:**
```typescript
// Called from slamStore or a useEffect in App.tsx/ControlPanel.tsx
// Vite proxy: /api -> http://localhost:8000/api
async function fetchSlamState(): Promise<void> {
  const store = useSlamStore.getState();
  try {
    const [backendsRes, activeRes] = await Promise.all([
      fetch('/api/slam/backends'),
      fetch('/api/slam/active'),
    ]);
    if (backendsRes.ok) {
      const { backends } = await backendsRes.json();
      store.setBackends(backends);
    }
    if (activeRes.ok) {
      const { backend, display, parameters } = await activeRes.json();
      store.setActive(backend, display, parameters);
    }
  } catch (err) {
    store.setError('Failed to load SLAM backends');
  }
}
```

### Pattern 3: Schema-Driven Parameter Controls
**What:** Dynamically render form controls from backend's `PARAMETER_SCHEMA` JSON Schema.
**When to use:** ParameterPanel component that reads schema properties and renders slider+input for numbers, toggle for booleans.
**Example:**
```typescript
// Source: Phase 9 CONTEXT.md + ICP backend PARAMETER_SCHEMA format
// ICP PARAMETER_SCHEMA.properties.voxel_size:
// { type: "number", default: 0.03, minimum: 0.01, maximum: 0.2,
//   description: "Voxel size for downsampling (meters)", live_tunable: false }

function renderControl(key: string, schema: ParamSchema, value: unknown, onChange: (v: unknown) => void) {
  if (schema.type === 'number' || schema.type === 'integer') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <input
          type="range"
          min={schema.minimum}
          max={schema.maximum}
          step={schema.type === 'integer' ? 1 : (schema.maximum! - schema.minimum!) / 100}
          value={value as number}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          style={{ flex: 1 }}
        />
        <input
          type="number"
          min={schema.minimum}
          max={schema.maximum}
          step={schema.type === 'integer' ? 1 : 0.001}
          value={value as number}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          style={{ width: '70px', /* dark theme styles */ }}
        />
      </div>
    );
  }
  if (schema.type === 'boolean') {
    return (
      <button
        onClick={() => onChange(!(value as boolean))}
        style={{ /* toggle button styles matching color mode toggle */ }}
      >
        {(value as boolean) ? 'On' : 'Off'}
      </button>
    );
  }
  return null;
}
```

### Pattern 4: Custom Dropdown with Rich Items
**What:** Div-based dropdown (not native `<select>`) to support capability badges, disabled items with tooltips, and styling matching the dark theme.
**When to use:** Algorithm picker component.
**Key aspects:**
- Click trigger toggles open/closed state
- Click-outside closes (useEffect with document listener)
- Each item shows backend display name + capability pills
- Unavailable items are grayed with pointer-events: none and title tooltip
- Keyboard: Escape closes

### Pattern 5: Portal-Based Modal
**What:** `ReactDOM.createPortal` renders modal to `document.body` so it sits above the entire app layout (CSS Grid).
**When to use:** Algorithm switch confirmation dialog.
**Key aspects:**
- Fixed positioning with backdrop (rgba(0,0,0,0.6))
- Z-index above all other content (z-index: 1000)
- Centered card with dark theme styling
- Two buttons: Cancel (muted) and Switch (primary accent)
- Escape key closes

### Anti-Patterns to Avoid
- **Native `<select>` for algorithm dropdown:** Cannot render badges, rich items, disabled-with-tooltip, or dark-themed dropdown list. Must use custom div-based dropdown.
- **Putting SLAM state in controlStore:** CONTEXT.md explicitly requires separate `slamStore.ts`. Mixing concerns makes the already-large controlStore harder to maintain.
- **Forgetting click-outside for dropdown:** Custom dropdowns that only close on item selection create stuck-open UI bugs. Must add document click listener.
- **Sending slider values on every change event:** Range inputs fire continuously during drag. Must debounce WebSocket sends (150-250ms) to avoid flooding the backend.
- **Blocking UI during restart:** REST call to `POST /api/slam/select` should be non-blocking. Show overlay immediately, poll/wait for state change, then re-fetch.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Modal stacking context | Custom z-index management | `ReactDOM.createPortal(modal, document.body)` | Portal escapes CSS stacking context of the grid layout automatically |
| Debounce | Full lodash import or complex timer management | 5-line debounce utility with `setTimeout`/`clearTimeout` | Project has zero utility deps; this is trivial |
| JSON Schema validation | Client-side schema validator | Backend validates via `PATCH /api/slam/params`; frontend uses schema for rendering only | Backend already validates; duplicating on client adds complexity for no user benefit |
| Keyboard accessibility for dropdown | Full ARIA combobox implementation | Basic: Escape to close, Enter to select, click-outside to close | Full ARIA combobox is enormous scope; basic keyboard support covers primary use cases |

**Key insight:** The frontend's role is rendering from the backend's JSON Schema and sending values back. The backend owns validation (min/max/type checking). The frontend should render controls from the schema and clamp displayed values, but not duplicate full validation logic.

## Common Pitfalls

### Pitfall 1: Vite Proxy Missing for /api Routes
**What goes wrong:** Frontend `fetch('/api/slam/backends')` hits Vite's dev server and returns 404 or the SPA HTML.
**Why it happens:** Current `vite.config.ts` only proxies `/ws`. REST endpoints at `/api/*` are not proxied.
**How to avoid:** Add `/api` proxy to `vite.config.ts`:
```typescript
proxy: {
  '/ws': { target: 'ws://localhost:8000', ws: true },
  '/api': { target: 'http://localhost:8000' },
},
```
**Warning signs:** 404 errors or HTML responses when fetching `/api/slam/backends` in dev mode.

### Pitfall 2: Stale Store References in Event Handlers
**What goes wrong:** Callbacks created during WebSocket `onopen` capture stale `sendRaw` reference; new stores subscribe but old closures linger.
**Why it happens:** The existing `useWebSocket` hook creates `sendRaw` in `onopen` and registers it on controlStore. The slamStore also needs `sendRaw`, but must read it from controlStore at call time, not capture it.
**How to avoid:** Always call `useControlStore.getState().sendRaw` at invocation time (which the codebase already does), never capture `sendRaw` in a closure. For slamStore actions, access sendRaw as:
```typescript
const sendRaw = useControlStore.getState().sendRaw;
sendRaw?.({ type: 'slam_param_update', param, value });
```
**Warning signs:** Parameter updates silently fail to send; WebSocket messages are not observed on the server.

### Pitfall 3: Race Condition on Algorithm Switch
**What goes wrong:** User switches algorithm, `POST /api/slam/select` fires restart, but frontend re-fetches active backend before restart completes and gets the old backend.
**Why it happens:** The backend `select` endpoint triggers restart asynchronously (fires command_callback and returns immediately). The re-fetch may arrive before the restart finishes.
**How to avoid:** Use `isRestarting` flag in slamStore. After `POST /api/slam/select`:
1. Set `isRestarting = true` immediately
2. Clear the point cloud via `robotStore.setCloudFull([], [])`
3. Show restart overlay
4. Poll `GET /api/slam/active` on an interval (e.g., 500ms) until the backend name matches the expected new backend, or timeout after ~10 seconds
5. Set `isRestarting = false` and update slamStore with new active backend
**Warning signs:** Dropdown shows old backend after switch; parameters panel shows wrong schema.

### Pitfall 4: WebSocket slam_param_update Handler Missing on Backend
**What goes wrong:** Frontend sends `{ type: 'slam_param_update', param, value }` via WebSocket, but backend's `_dispatch_ws_message` in `server.py` has no handler for it -- message is silently dropped.
**Why it happens:** Phase 8 implemented REST `PATCH /api/slam/params` but did not add a WebSocket message handler for live parameter updates. The CONTEXT.md decision says live-tunable params go via WebSocket.
**How to avoid:** Add a `slam_param_update` case to `_dispatch_ws_message` in `backend/web/server.py` that applies the parameter to the active backend instance and sends a `slam_param_ack` response. This is a small backend change needed alongside the frontend work.
**Warning signs:** Slider changes appear to do nothing; no `slam_param_ack` messages arrive in the frontend.

### Pitfall 5: Modal Doesn't Close on Backdrop Click
**What goes wrong:** Users click outside the modal card expecting it to close, but only the Cancel button works.
**Why it happens:** The backdrop div doesn't have an onClick handler, or the click event propagates from the card to the backdrop.
**How to avoid:** Add `onClick` on the backdrop that closes the modal. Use `e.stopPropagation()` on the inner modal card to prevent backdrop close when clicking inside it.
**Warning signs:** Users feel trapped; modal requires finding the Cancel button.

### Pitfall 6: Numeric Input and Slider Desynchronization
**What goes wrong:** User types a value in the text input that exceeds the slider's range, or the slider and input show different values.
**Why it happens:** The text input allows freeform entry; the range input clamps to min/max. If not clamped consistently, they diverge.
**How to avoid:** Use a single state value. On text input change, clamp to [minimum, maximum] before setting state. Both slider and input read from the same state value.
**Warning signs:** Slider jumps to an end when text input has out-of-range value.

## Code Examples

### Vite Proxy Configuration
```typescript
// Source: Existing vite.config.ts + needed /api proxy
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/api': { target: 'http://localhost:8000' },
    },
  },
});
```

### WebSocket Message Handler Extension
```typescript
// Source: Existing useWebSocket.ts switch pattern + new SLAM messages
// Add to the switch in handleTextMessage:
case 'slam_param_ack': {
  const payload = msg.payload as { param: string; status: string; value?: unknown };
  // Could update slamStore if needed for confirmation
  console.log(`[slam] param ${payload.param}: ${payload.status}`);
  break;
}
case 'slam_restart_complete': {
  // Signal that restart finished, re-fetch active backend
  useSlamStore.getState().setRestarting(false);
  fetchSlamState();  // re-fetch backends + active
  break;
}
```

### messageTypes.ts Extension
```typescript
// Source: Existing messageTypes.ts WSMessage type union
export interface WSMessage {
  type:
    | 'robot_list'
    | 'pose_update'
    | 'cloud_delta'
    | 'cloud_full'
    | 'camera_frame'
    | 'stats'
    | 'command'
    | 'trajectory'
    | 'cloud_configs'
    | 'cloud_config_ack'
    | 'detections'
    | 'scene_description'
    | 'color_mode_ack'
    | 'slam_param_ack'           // new
    | 'slam_restart_complete';   // new
  robot_id?: string;
  payload: unknown;
}
```

### Backend WebSocket Handler for slam_param_update
```python
# Source: Existing _dispatch_ws_message pattern in backend/web/server.py
elif msg_type == "slam_param_update":
    param = data.get("param")
    value = data.get("value")
    # Apply to active backend if live_tunable
    # ... (coordinator or app.state mechanism)
    await websocket.send_json({
        "type": "slam_param_ack",
        "payload": {"param": param, "status": "applied", "value": value},
    })
```

### Simple Debounce Utility
```typescript
// Source: Standard debounce pattern, no dependencies needed
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  ms: number,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
```

### Collapsible Section Pattern (existing, to reuse)
```typescript
// Source: ControlPanel.tsx Cloud Config section pattern
<div
  onClick={() => setShowAlgorithm(!showAlgorithm)}
  style={{
    fontSize: '12px', fontWeight: 600, color: '#888', cursor: 'pointer',
    userSelect: 'none', display: 'flex', justifyContent: 'space-between',
  }}
>
  <span>SLAM ALGORITHM</span>
  <span style={{ fontSize: '10px' }}>{showAlgorithm ? '\u25BC' : '\u25B6'}</span>
</div>
```

### Capability Badge Pill
```typescript
// Source: Phase 9 CONTEXT.md "colored pill tags, small green-ish"
// Only show positive capabilities (where value is true)
function CapabilityBadge({ name }: { name: string }) {
  const label = name.replace('supports_', '').replace('outputs_', '').replace(/_/g, ' ');
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 6px',
      borderRadius: '8px',
      fontSize: '10px',
      fontWeight: 500,
      background: 'rgba(46, 204, 113, 0.15)',
      color: '#2ecc71',
      border: '1px solid rgba(46, 204, 113, 0.3)',
      marginRight: '4px',
      marginBottom: '2px',
    }}>
      {label}
    </span>
  );
}
```

### RestartOverlay on SceneViewer
```typescript
// Source: Phase 9 CONTEXT.md "Restarting with [algorithm]... text overlay + spinner"
// Rendered inside SceneViewer's outer div, conditionally visible
function RestartOverlay({ algorithmName }: { algorithmName: string }) {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: 'rgba(13, 13, 26, 0.7)',
      zIndex: 10, pointerEvents: 'none',
    }}>
      {/* CSS spinner or simple animated border */}
      <div style={{
        width: '40px', height: '40px',
        border: '3px solid #2a2a4a', borderTopColor: '#2ecc71',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
      }} />
      <div style={{ marginTop: '12px', color: '#aaa', fontSize: '14px' }}>
        Restarting with {algorithmName}...
      </div>
    </div>
  );
}
// Note: @keyframes spin needs to be in index.css or a <style> tag
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Zustand v4 `create<T>()(...) ` | Zustand v5 `create<T>((...) => ...)` | Zustand 5.0 (2024) | Simplified API; project is already on v5.0.12 -- no migration needed |
| CSS-in-JS libraries (styled-components, emotion) | Inline styles or Tailwind | 2023-present trend | Project uses inline styles exclusively; stick with this -- zero setup, works |
| Separate REST client (axios, ky) | Native fetch | Fetch is universally supported | Project has no REST calls yet; native fetch with async/await is sufficient |
| React.createPortal from 'react-dom' | Same (unchanged) | Stable since React 16.0 | Portal API unchanged; import from 'react-dom' |

**Deprecated/outdated:**
- Zustand v4 `create()` without type parameter: Project already uses v5 pattern `create<StateType>((set) => ...)`
- `@types/react` default export: Project uses named imports (`import { useState } from 'react'`) which is correct

## Open Questions

1. **Backend WebSocket handler for `slam_param_update`**
   - What we know: CONTEXT.md says live-tunable params send via WebSocket. Backend's `_dispatch_ws_message` currently has no `slam_param_update` handler. Phase 8 only built the REST `PATCH /api/slam/params`.
   - What's unclear: How exactly the backend applies a live parameter to the running backend instance. The coordinator manages robot instances, not the web server. The `slam_param_update` handler needs access to the active backend instance.
   - Recommendation: Add a minimal `slam_param_update` handler to `server.py` that stores the parameter update on `app.state` and optionally sends an ack. The actual parameter application to the running backend may need a callback injection pattern similar to `command_callback`. This is a small backend change that must ship alongside the frontend work.

2. **Restart completion signaling**
   - What we know: `POST /api/slam/select` triggers restart via `command_callback` and returns immediately. There is no explicit "restart complete" signal.
   - What's unclear: Whether the backend sends any WebSocket message when restart finishes, or if the frontend must poll.
   - Recommendation: Implement polling: after `POST /api/slam/select` returns `{ status: 'restarting' }`, poll `GET /api/slam/active` every 500ms. When the returned backend name matches the newly selected backend, restart is complete. Timeout after 10 seconds. Alternatively, a backend enhancement to send a `slam_restart_complete` WebSocket message would be cleaner but requires more backend coordination.

3. **CSS `@keyframes` for spinner animation**
   - What we know: All components use inline styles. Inline styles cannot define `@keyframes`.
   - What's unclear: Whether to add a `<style>` tag in the component, use `index.css`, or use a JavaScript-based animation.
   - Recommendation: Add a minimal `@keyframes spin` rule in `frontend/src/index.css` (or `App.css` if it exists). Alternatively, use JavaScript `requestAnimationFrame` to rotate the spinner element, but CSS is simpler.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None currently configured for frontend; pytest 8.x for backend |
| Config file | None for frontend (Wave 0 gap); `pyproject.toml` for backend pytest |
| Quick run command | `cd frontend && npx tsc --noEmit` (type checking only) |
| Full suite command | Backend: `python -m pytest tests/web/test_slam_routes.py -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-01 | Dropdown lists backends with badges | manual | Visual verification in browser | N/A |
| CTRL-02 | Algorithm selection triggers restart | manual + integration | `python -m pytest tests/web/test_slam_routes.py::test_select_valid_backend -x` (backend portion) | Backend: yes; Frontend: manual |
| CTRL-03 | Parameter panel renders from JSON Schema | manual | Visual verification + `npx tsc --noEmit` (type safety) | N/A |
| CTRL-04 | Parameter changes sent via WebSocket | manual + integration | Visual verification + backend log inspection | N/A |

### Sampling Rate
- **Per task commit:** `cd frontend && npx tsc --noEmit` (type check, ~5s)
- **Per wave merge:** `python -m pytest tests/web/ -x` (backend route tests, ~3s) + manual browser test
- **Phase gate:** Type check clean + backend tests green + manual browser walkthrough

### Wave 0 Gaps
- [ ] No frontend test framework (vitest, jest, or playwright) is configured -- this is a pre-existing gap, not introduced by Phase 9. Frontend validation is manual.
- [ ] No `@keyframes spin` CSS rule exists -- needed for spinner animation in RestartOverlay.
- [ ] Backend `slam_param_update` WebSocket handler does not exist -- must be added alongside frontend work.
- [ ] Vite proxy for `/api` not configured -- must be added in vite.config.ts.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `frontend/src/components/ControlPanel.tsx` -- existing UI patterns, inline styles, collapsible sections, slider, toggle
- Codebase inspection: `frontend/src/stores/controlStore.ts`, `robotStore.ts` -- Zustand v5 store pattern with flat state + setters
- Codebase inspection: `frontend/src/hooks/useWebSocket.ts` -- WebSocket message dispatch pattern, sendRaw registration
- Codebase inspection: `backend/web/slam_routes.py` -- REST API endpoints already implemented (GET /backends, POST /select, GET /active, PATCH /params)
- Codebase inspection: `backend/web/server.py` -- WebSocket dispatch pattern, app.state for SLAM backend selection
- Codebase inspection: `src/slam/backends/icp_backend.py` -- PARAMETER_SCHEMA format with JSON Schema properties, live_tunable metadata
- Codebase inspection: `src/slam/registry.py` -- list_backends() return format with capabilities, parameter_schema, availability
- `frontend/package.json` -- React 18.3.1, Zustand 5.0.x, Three.js 0.170.0, Vite 6.x
- `node_modules/zustand/package.json` -- Confirmed Zustand 5.0.12 installed
- `node_modules/react/package.json` -- Confirmed React 18.3.1 installed

### Secondary (MEDIUM confidence)
- Phase 9 CONTEXT.md -- Locked user decisions for UI placement, interaction patterns, state management
- Phase 8 CONTEXT.md -- REST API design decisions, restart flow, parameter schema depth

### Tertiary (LOW confidence)
- None -- all findings are from direct codebase inspection

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed; versions verified from node_modules
- Architecture: HIGH -- all patterns derived from existing codebase; new components follow established conventions exactly
- Pitfalls: HIGH -- identified from direct code inspection of integration points (vite proxy gap, WebSocket handler gap, restart race condition)

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable -- no fast-moving dependencies; all patterns are well-established)
