# Phase 3: frontend-picker-and-ui - Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 25
**Analogs found:** 25 / 25

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `frontend/src/stores/detectorStore.ts` | store | request-response | `frontend/src/stores/slamStore.ts` | exact |
| `frontend/src/components/DetectorDropdown.tsx` | component | event-driven | `frontend/src/components/AlgorithmDropdown.tsx` | exact |
| `frontend/src/components/LifterDropdown.tsx` | component | event-driven | `frontend/src/components/AlgorithmDropdown.tsx` | role-match |
| `frontend/src/components/DetectorSection.tsx` | component | request-response | `frontend/src/components/AlgorithmSection.tsx` | exact |
| `frontend/src/components/DetectorParameterPanel.tsx` | component | streaming | `frontend/src/components/ParameterPanel.tsx` | exact |
| `frontend/src/components/CapabilityBadge.tsx` | component | transform | `frontend/src/components/CapabilityBadge.tsx` | in-place exact |
| `frontend/src/components/RestartOverlay.tsx` | component | event-driven | `frontend/src/components/RestartOverlay.tsx` | in-place exact |
| `frontend/src/components/AlgorithmSection.tsx` | component | request-response | `frontend/src/components/AlgorithmSection.tsx` | in-place exact |
| `frontend/src/components/Sidebar.tsx` | component | request-response | `frontend/src/components/Sidebar.tsx` | in-place exact |
| `frontend/src/components/CameraFeed.tsx` | component | streaming | `frontend/src/components/CameraFeed.tsx` | in-place exact |
| `frontend/src/hooks/useWebSocket.ts` | hook | streaming | `frontend/src/hooks/useWebSocket.ts` | in-place exact |
| `backend/web/detector_routes.py` | route | CRUD | `backend/web/slam_routes.py` | exact |
| `backend/web/server.py` | config | event-driven | `backend/web/server.py` | in-place exact |
| `src/main.py` | service | event-driven | `src/main.py` restart block | in-place exact |
| `tests/perception/test_lifter_routes.py` | test | request-response | `tests/perception/test_detector_routes.py` | exact |
| `frontend/src/stores/__tests__/detectorStore.shape.test.ts` | test | transform | `tests/perception/test_detector_routes.py` fixture/assertion style + store APIs | role-match |
| `frontend/package.json` | config | transform | `frontend/package.json` | in-place exact |
| `frontend/vitest.config.ts` | config | batch | `frontend/package.json` scripts + standard Vitest config from research | partial |
| `frontend/src/components/SceneViewer.tsx` | component | event-driven | `frontend/src/components/RestartOverlay.tsx` | role-match |
| `frontend/src/components/pipeline/ApplyBar.tsx` | component | event-driven | `frontend/src/components/RestartOverlay.tsx` | role-match |
| `src/perception/worker_pool.py` | service | event-driven | `src/main.py` detector pool construction | role-match |
| `frontend/src/utils/palette.ts` | utility | transform | `frontend/src/utils/palette.ts` | exact |
| `frontend/src/components/ConfirmModal.tsx` | component | event-driven | `frontend/src/components/ConfirmModal.tsx` | exact |
| `frontend/src/stores/controlStore.ts` | store | streaming | `frontend/src/components/ParameterPanel.tsx` sendRaw usage | role-match |
| `frontend/src/components/SliderField.tsx` | component | event-driven | `frontend/src/components/ParameterPanel.tsx` usage | role-match |

## Pattern Assignments

### `frontend/src/stores/detectorStore.ts` (store, request-response)

**Analog:** `frontend/src/stores/slamStore.ts`

**Imports and type pattern** (`frontend/src/stores/slamStore.ts` lines 1-23):
```typescript
import { create } from 'zustand';

export interface SLAMBackend {
  name: string;
  display: string;
  available: boolean;
  capabilities: Record<string, boolean>;
  parameter_schema: {
    type: string;
    properties: Record<string, { type: string; default?: number | boolean; minimum?: number; maximum?: number; description?: string; live_tunable?: boolean; }>;
  };
  reason?: string;
}
```

**Flat store shape and setters** (`frontend/src/stores/slamStore.ts` lines 25-68):
```typescript
interface SlamStoreState {
  backends: SLAMBackend[];
  activeBackend: string;
  activeDisplay: string;
  activeParameters: Record<string, unknown>;
  stagedParams: Record<string, unknown>;
  isRestarting: boolean;
  error: string | null;
  crashMessage: string | null;

  setBackends: (backends: SLAMBackend[]) => void;
  setActive: (name: string, display: string, parameters: Record<string, unknown>) => void;
  setRestarting: (restarting: boolean) => void;
  stageParam: (key: string, value: unknown) => void;
  clearStagedParams: () => void;
  setError: (error: string | null) => void;
  updateActiveParam: (key: string, value: unknown) => void;
  setCrashMessage: (msg: string | null) => void;
  clearCrashMessage: () => void;
}
```

**REST fetch pattern** (`frontend/src/stores/slamStore.ts` lines 70-88):
```typescript
export async function fetchSlamState(): Promise<void> {
  const store = useSlamStore.getState();
  try {
    const [backendsRes, activeRes] = await Promise.all([
      fetch('/api/slam/backends'),
      fetch('/api/slam/active'),
    ]);
    if (backendsRes.ok) store.setBackends((await backendsRes.json()).backends);
    if (activeRes.ok) {
      const data = await activeRes.json();
      store.setActive(data.backend, data.display, data.parameters);
    }
  } catch {
    store.setError('Failed to load SLAM backends. Check that the server is running.');
  }
}
```

**Apply to detectorStore:** clone shape, widen `capabilities` values to `string | number | boolean`, add lifter state/setters, and fetch `/api/detectors/backends`, `/api/detectors/active`, `/api/detectors/lifters`, `/api/detectors/active-lifter` in one `Promise.all`.

---

### `frontend/src/components/DetectorDropdown.tsx` (component, event-driven)

**Analog:** `frontend/src/components/AlgorithmDropdown.tsx`

**Imports and store selection** (`frontend/src/components/AlgorithmDropdown.tsx` lines 1-8):
```typescript
import { useState, useRef, useEffect, useCallback } from 'react';
import { useSlamStore } from '../stores/slamStore';
import { CapabilityBadge } from './CapabilityBadge';

export function AlgorithmDropdown({ onSelect }: { onSelect: (name: string) => void }) {
  const backends = useSlamStore((s) => s.backends);
  const activeBackend = useSlamStore((s) => s.activeBackend);
  const activeDisplay = useSlamStore((s) => s.activeDisplay);
```

**Dropdown behavior** (`frontend/src/components/AlgorithmDropdown.tsx` lines 14-44):
```typescript
useEffect(() => {
  if (!isOpen) return;
  const handleClickOutside = (e: MouseEvent) => {
    if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
      setIsOpen(false);
    }
  };
  document.addEventListener('mousedown', handleClickOutside);
  return () => document.removeEventListener('mousedown', handleClickOutside);
}, [isOpen]);

const handleItemClick = useCallback(
  (backendName: string) => {
    if (backendName !== activeBackend) onSelect(backendName);
    setIsOpen(false);
  },
  [activeBackend, onSelect],
);
```

**Unavailable option + badge row pattern** (`frontend/src/components/AlgorithmDropdown.tsx` lines 94-140):
```typescript
backends.map((backend) => {
  const isActive = backend.name === activeBackend;
  const isAvailable = backend.available;
  const itemStyle: React.CSSProperties = {
    cursor: isAvailable ? 'pointer' : 'not-allowed',
    borderLeft: isActive ? '2px solid #2ecc71' : '2px solid transparent',
    opacity: isAvailable ? 1 : 0.4,
  };
  return (
    <div title={!isAvailable ? (backend.reason ?? 'Unavailable') : undefined}>
      <div>{backend.display}</div>
      {capabilities.map((cap) => (
        <CapabilityBadge key={cap} label={cap} value={true} />
      ))}
    </div>
  );
})
```

**Apply to DetectorDropdown:** use `useDetectorStore`, render exactly `framework`, `license`, `cpu_latency_hint_ms` via `CapabilityBadge label={key} value={backend.capabilities[key]}`.

---

### `frontend/src/components/LifterDropdown.tsx` (component, event-driven)

**Analog:** `frontend/src/components/AlgorithmDropdown.tsx` and detector dropdown clone.

**Core assignment:** copy the same click-outside, escape-key, active-option, unavailable-option, and badge-row patterns from `AlgorithmDropdown.tsx` lines 14-44 and 94-140. Replace `backends/activeBackend/activeDisplay` with `lifters/activeLifter/activeLifterDisplay` from `useDetectorStore`.

**Existing lifter badge precedent** (`frontend/src/components/LifterDropdown.tsx` lines 5-11, if preserving current implementation):
```typescript
const LIFTER_BADGE_KEYS: Array<keyof LifterBackend['capabilities']> = [
  'license',
  'outputs_oriented',
];
```

---

### `frontend/src/components/DetectorSection.tsx` (component, request-response)

**Analog:** `frontend/src/components/AlgorithmSection.tsx`

**Polling fallback pattern** (`frontend/src/components/AlgorithmSection.tsx` lines 9-29):
```typescript
async function pollForRestart(expectedBackend: string) {
  const maxAttempts = 20;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try {
      const res = await fetch('/api/slam/active');
      if (res.ok) {
        const data = await res.json();
        if (data.backend === expectedBackend) {
          await fetchSlamState();
          useSlamStore.getState().setRestarting(false);
          return;
        }
      }
    } catch {
      /* continue polling */
    }
  }
  useSlamStore.getState().setError('Restart timed out. Try again or refresh the page.');
  useSlamStore.getState().setRestarting(false);
}
```

**Confirm → POST → clear staged params pattern** (`frontend/src/components/AlgorithmSection.tsx` lines 51-125):
```typescript
const onConfirmSwitch = useCallback(async () => {
  if (!pendingBackend) return;
  setSwitching(true);
  const selectedBackend = useSlamStore.getState().backends.find((b) => b.name === pendingBackend);
  const pendingDisplayName = selectedBackend?.display ?? pendingBackend;
  useSlamStore.getState().setRestarting(true);
  const params = useSlamStore.getState().stagedParams;
  const body: Record<string, unknown> = { backend: pendingBackend };
  if (Object.keys(params).length > 0) body.params = params;

  try {
    const res = await fetch('/api/slam/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setShowModal(false);
    setSwitching(false);
    if (!res.ok) {
      useSlamStore.getState().setError(`Failed to switch to ${pendingDisplayName}. The previous algorithm is still active.`);
      useSlamStore.getState().setRestarting(false);
      return;
    }
    useSlamStore.getState().clearStagedParams();
    pollForRestart(pendingBackend);
  } catch {
    setShowModal(false);
    setSwitching(false);
    useSlamStore.getState().setRestarting(false);
  }
  setPendingBackend(null);
}, [pendingBackend]);
```

**Section header + badges + error banner pattern** (`frontend/src/components/AlgorithmSection.tsx` lines 140-210):
```tsx
<div onClick={() => setShowSection(!showSection)} style={{ borderTop: '1px solid #2a2a4a', paddingTop: '16px', marginTop: '16px', cursor: 'pointer', userSelect: 'none', display: 'flex', justifyContent: 'space-between' }}>
  <span style={{ fontSize: '12px', fontWeight: 600, color: '#888' }}>SLAM ALGORITHM</span>
  <span style={{ fontSize: '10px', color: '#888' }}>{showSection ? '▼' : '▶'}</span>
</div>
{showSection && (
  <div style={{ marginTop: '8px' }}>
    <AlgorithmDropdown onSelect={onSelect} />
    <ParameterPanel />
  </div>
)}
```

**Apply to DetectorSection:** clone the parent structure, change title to `OBJECT DETECTION`, use `DetectorDropdown`, show active detector badges for `framework/license/cpu_latency_hint_ms`, gate `LifterDropdown` on `activeBackendInfo?.capabilities?.outputs_3d_natively === false`, and reuse `ConfirmModal` for detector and lifter flows. Current mainline has Phase 4 supersession: lifter flow uses `/api/detectors/lifter-hotswap` and no restart overlay; if implementing original Phase 3 only, use `/api/detectors/lifter-select` restart semantics from CONTEXT.

---

### `frontend/src/components/DetectorParameterPanel.tsx` (component, streaming)

**Analog:** `frontend/src/components/ParameterPanel.tsx`

**Debounced reconnect-safe WS send** (`frontend/src/components/ParameterPanel.tsx` lines 1-9):
```typescript
import { useControlStore } from '../stores/controlStore';
import { debounce } from '../utils/debounce';

const debouncedSendParam = debounce((key: unknown, value: unknown) => {
  const sendRaw = useControlStore.getState().sendRaw;
  sendRaw?.({ type: 'slam_param_update', param: key, value });
}, 200);
```

**Live-tunable split** (`frontend/src/components/ParameterPanel.tsx` lines 17-25):
```typescript
function handleParamChange(key: string, value: unknown, liveTunable?: boolean) {
  const store = useSlamStore.getState();
  store.updateActiveParam(key, value);
  if (liveTunable) {
    debouncedSendParam(key, value);
  } else {
    store.stageParam(key, value);
  }
}
```

**Schema-driven controls** (`frontend/src/components/ParameterPanel.tsx` lines 43-107):
```tsx
{Object.entries(properties).map(([key, prop]) => {
  const currentValue = activeParameters[key] ?? prop.default ?? (prop.type === 'boolean' ? false : (prop.minimum ?? 0));
  return (
    <div key={key} style={{ marginBottom: '8px' }}>
      {(prop.type === 'number' || prop.type === 'integer') && (
        <SliderField
          min={prop.minimum ?? 0}
          max={prop.maximum ?? 1}
          step={prop.type === 'integer' ? 1 : ((prop.maximum ?? 1) - (prop.minimum ?? 0)) / 100}
          value={currentValue as number}
          onChange={(val) => handleParamChange(key, val, prop.live_tunable)}
          isInteger={prop.type === 'integer'}
        />
      )}
    </div>
  );
})}
```

**Apply to DetectorParameterPanel:** replace `slam_param_update` with `detector_param_update`, and use `useDetectorStore` setter names unchanged (`updateActiveParam`, `stageParam`).

---

### `frontend/src/components/CapabilityBadge.tsx` (component, transform)

**Analog:** in-place current component.

**Generalized prop + rendering rules** (`frontend/src/components/CapabilityBadge.tsx` lines 1-24):
```typescript
interface CapabilityBadgeProps {
  label: string;
  value: string | number | boolean;
}

export function CapabilityBadge({ label, value }: CapabilityBadgeProps) {
  if (value === false || value === null || value === undefined) return null;
  let text: string;
  if (value === true) {
    text = label.replace('supports_', '').replace('outputs_', '').replace(/_/g, ' ');
  } else if (typeof value === 'number' && label.includes('latency')) {
    text = `~${value}ms`;
  } else {
    text = `${label.replace(/_/g, ' ')}: ${value}`;
  }
```

**Style pattern** (`frontend/src/components/CapabilityBadge.tsx` lines 26-39):
```typescript
const style: React.CSSProperties = {
  display: 'inline-block',
  padding: '1px 8px',
  borderRadius: '8px',
  fontSize: '10px',
  background: 'rgba(46, 204, 113, 0.15)',
  color: '#2ecc71',
  border: '1px solid rgba(46, 204, 113, 0.3)',
  marginRight: '4px',
  marginBottom: '2px',
};
return <span style={style}>{text}</span>;
```

---

### `frontend/src/components/RestartOverlay.tsx` (component, event-driven)

**Analog:** in-place current component.

**Discriminated subsystem prop** (`frontend/src/components/RestartOverlay.tsx` lines 1-12):
```typescript
interface RestartOverlayProps {
  subsystem: 'slam' | 'detector' | 'lifter';
  name: string;
}

const SUBSYSTEM_LABEL: Record<RestartOverlayProps['subsystem'], string> = {
  slam: 'SLAM',
  detector: 'detector',
  lifter: 'lifter',
};
```

**Overlay style and message** (`frontend/src/components/RestartOverlay.tsx` lines 13-47):
```tsx
const overlayStyle: React.CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(13, 13, 26, 0.7)',
  zIndex: 10,
  pointerEvents: 'none',
};
return (
  <div style={overlayStyle}>
    <div style={spinnerStyle} />
    <div style={textStyle}>Restarting {SUBSYSTEM_LABEL[subsystem]} with {name}...</div>
  </div>
);
```

**Apply to call sites:** migrate from `algorithmName={...}` to `subsystem="slam" name={...}`. New detector overlays should pass `subsystem="detector"` or `subsystem="lifter"` if using original restart-driven lifter semantics.

---

### `frontend/src/components/CameraFeed.tsx` (component, streaming)

**Analog:** in-place current component plus `frontend/src/utils/palette.ts`.

**Palette source** (`frontend/src/utils/palette.ts` lines 13-28):
```typescript
export const OKABE_ITO_RGB: [number, number, number][] = [
  [0, 114, 178],
  [230, 159, 0],
  [86, 180, 233],
  [0, 158, 115],
  [240, 228, 66],
  [213, 94, 0],
  [204, 121, 167],
  [0, 0, 0],
];

export function robotColor(index: number): string {
  return OKABE_ITO[index % 8];
}
```

**2D bbox overlay pattern** (`frontend/src/components/CameraFeed.tsx` lines 31-47):
```typescript
{items.map((det, i) => {
  if (!det.bbox_xyxy || det.bbox_xyxy.length < 4) return null;
  const [x1, y1, x2, y2] = det.bbox_xyxy;
  const [cr, cg, cb] = OKABE_ITO_RGB[(det.class_id ?? 0) >= 0
    ? (det.class_id ?? 0) % OKABE_ITO_RGB.length
    : 0];
  const classColor = `rgb(${cr}, ${cg}, ${cb})`;
  const left = `${(x1 / imgWidth) * 100}%`;
  const top = `${(y1 / imgHeight) * 100}%`;
  const width = `${((x2 - x1) / imgWidth) * 100}%`;
  const height = `${((y2 - y1) / imgHeight) * 100}%`;
```

**Label and tooltip pattern** (`frontend/src/components/CameraFeed.tsx` lines 72-120):
```tsx
<div style={{ position: 'absolute', left: 0, padding: '1px 5px', background: isHovered ? classColor : 'rgba(0,0,0,0.75)', color: isHovered ? '#000' : classColor, fontSize: '10px', fontWeight: 700 }}>
  {det.class_name} {(det.score * 100).toFixed(0)}%
</div>
{isHovered && (
  <div style={{ background: 'rgba(0,0,0,0.9)', border: `1px solid ${classColor}` }}>
    <div><strong style={{ color: classColor }}>{det.class_name}</strong></div>
    <div>Score: {(det.score * 100).toFixed(2)}%</div>
    <div>BBox: [{det.bbox_xyxy.map(v => v.toFixed(0)).join(', ')}]</div>
  </div>
)}
```

---

### `frontend/src/hooks/useWebSocket.ts` (hook, streaming)

**Analog:** in-place current hook.

**Imports needed** (`frontend/src/hooks/useWebSocket.ts` lines 1-8):
```typescript
import { useSlamStore, fetchSlamState } from '../stores/slamStore';
import { useDetectorStore, fetchDetectorState } from '../stores/detectorStore';
```

**Detections dispatch** (`frontend/src/hooks/useWebSocket.ts` lines 161-168):
```typescript
case 'detections_3d': {
  const payload = msg.payload as Detection3DEnvelope;
  if (msg.robot_id) {
    store.updateDetections(msg.robot_id, payload);
  }
  break;
}
```

**Detector restart-complete dismissal** (`frontend/src/hooks/useWebSocket.ts` lines 169-177):
```typescript
case 'detector_restart_complete': {
  const payload = msg.payload as DetectorRestartCompletePayload;
  useDetectorStore.getState().setRestarting(false);
  fetchDetectorState();
  const lifter = (payload as DetectorRestartCompletePayload & { lifter?: string }).lifter;
  console.log(`[detector] restart complete: ${payload.backend}${lifter ? ' / lifter=' + lifter : ''}`);
  break;
}
```

**SLAM restart-complete precedent** (`frontend/src/hooks/useWebSocket.ts` lines 210-214):
```typescript
case 'slam_restart_complete': {
  useSlamStore.getState().setRestarting(false);
  usePipelineStore.getState().setIsApplying(false);
  fetchSlamState();
  break;
}
```

---

### `backend/web/detector_routes.py` (route, CRUD)

**Analog:** `backend/web/slam_routes.py`

**Pydantic request models** (`backend/web/slam_routes.py` lines 17-28):
```python
class SelectRequest(BaseModel):
    backend: str
    params: dict | None = None

class MergeSelectRequest(BaseModel):
    strategy: str

class ParamPatch(BaseModel):
    params: dict
```

**Detector select pattern already in target file** (`backend/web/detector_routes.py` lines 56-102):
```python
@router.post("/select")
async def select_backend(req: SelectRequest, request: Request, robot_id: str | None = Query(None, description="Target specific robot; omit for all")):
    backends = {b["name"]: b for b in DetectorRegistry.list_backends()}
    if req.backend not in backends:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {req.backend}")
    if not backends[req.backend]["available"]:
        raise HTTPException(status_code=400, detail=f"Backend unavailable: {backends[req.backend].get('reason', 'unknown')}")
    request.app.state.pending_detector_backend = req.backend
    if req.params:
        request.app.state.pending_detector_params = req.params
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting", "backend": req.backend}
```

**Merge-strategy lifter-route analog** (`backend/web/slam_routes.py` lines 107-175):
```python
@router.get("/merge-strategies")
async def list_merge_strategies():
    import src.coordination.merge_strategies  # noqa: F401
    return {"strategies": MergeRegistry.list_strategies()}

@router.post("/merge-strategy")
async def select_merge_strategy(req: MergeSelectRequest, request: Request):
    import src.coordination.merge_strategies  # noqa: F401
    strategies = {s["name"]: s for s in MergeRegistry.list_strategies()}
    if req.strategy not in strategies:
        raise HTTPException(status_code=404, detail=f"Unknown strategy: {req.strategy}")
    if not strategies[req.strategy]["available"]:
        raise HTTPException(status_code=400, detail=f"Strategy unavailable: {strategies[req.strategy].get('reason', 'unknown')}")
    request.app.state.pending_merge_strategy = req.strategy
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting", "strategy": req.strategy}
```

**Lifter route current pattern** (`backend/web/detector_routes.py` lines 180-234):
```python
@router.get("/lifters")
async def list_lifters():
    import src.perception.lifters  # noqa: F401 — trigger @detection_3d registration
    from src.perception.registry import Detection3DRegistry
    return {"lifters": Detection3DRegistry.list_backends()}

@router.post("/lifter-hotswap")
async def lifter_hotswap(req: LifterSelectRequest, request: Request):
    import src.perception.lifters  # noqa: F401 — force @detection_3d registration
    from src.perception.registry import Detection3DRegistry
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    if req.lifter not in lifters:
        raise HTTPException(status_code=404, detail=f"Unknown lifter: {req.lifter}")
    if not lifters[req.lifter]["available"]:
        raise HTTPException(status_code=400, detail=f"Lifter unavailable: {lifters[req.lifter].get('reason', 'unknown')}")
    pool = getattr(request.app.state, "detector_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Detector pool not initialized")
    params = dict(req.params or {})
    pool.swap_lifter(req.lifter, params)
    request.app.state.active_lifter = req.lifter
    if params:
        request.app.state.pending_lifter_params = params
    return {"status": "swapped", "lifter": req.lifter}
```

**Param patch schema gate** (`backend/web/detector_routes.py` lines 255-281):
```python
@router.patch("/lifter-params")
async def patch_lifter_params(patch: ParamPatch, request: Request):
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry
    active = getattr(request.app.state, "active_lifter", Detection3DRegistry.get_default())
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    schema_props = lifters.get(active, {}).get("parameter_schema", {}).get("properties", {})
    results: dict = {}
    for key, value in patch.params.items():
        if key not in schema_props:
            results[key] = {"status": "unknown_parameter"}
        elif schema_props[key].get("live_tunable", False):
            results[key] = {"status": "applied", "value": value}
            pending = getattr(request.app.state, "pending_lifter_params", {})
            pending[key] = value
            request.app.state.pending_lifter_params = pending
        else:
            results[key] = {"status": "requires_restart", "value": value}
            pending = getattr(request.app.state, "pending_lifter_params", {})
            pending[key] = value
            request.app.state.pending_lifter_params = pending
    return {"results": results}
```

---

### `backend/web/server.py` (config, event-driven)

**Analog:** in-place current app-state and WS dispatch.

**State initialization pattern** (`backend/web/server.py` lines 56-76):
```python
app.state.active_slam_backend = "icp"
app.state.pending_slam_backend = None
app.state.pending_slam_params = {}

app.state.active_detector_backend = "yolov11"
app.state.pending_detector_backend = None
app.state.pending_detector_params = {}

app.state.active_lifter = "median_depth"
app.state.pending_lifter_params = {}
app.state.detector_pool = None
```

**Route mounting pattern** (`backend/web/server.py` lines 78-91):
```python
from backend.web.slam_routes import router as slam_router
app.include_router(slam_router)

from backend.web.detector_routes import router as detector_router
from backend.web.detector_routes import export_router as detections_export_router
app.include_router(detector_router)
app.include_router(detections_export_router)
```

**WS param-update pattern for detector** (`backend/web/server.py` lines 176-208):
```python
elif msg_type == "detector_param_update":
    from src.perception.registry import DetectorRegistry
    param = data.get("param")
    value = data.get("value")
    active = getattr(state, "active_detector_backend", DetectorRegistry.get_default())
    backends = {b["name"]: b for b in DetectorRegistry.list_backends()}
    schema_props = backends.get(active, {}).get("parameter_schema", {}).get("properties", {})

    if param not in schema_props:
        await websocket.send_json({"type": "detector_param_ack", "payload": {"param": param, "status": "unknown_parameter"}})
    elif schema_props[param].get("live_tunable", False):
        pending = getattr(state, "pending_detector_params", {})
        pending[param] = value
        state.pending_detector_params = pending
        await websocket.send_json({"type": "detector_param_ack", "payload": {"param": param, "status": "applied", "value": value}})
    else:
        await websocket.send_json({"type": "detector_param_ack", "payload": {"param": param, "status": "requires_restart"}})
```

---

### `src/main.py` (service, event-driven)

**Analog:** in-place restart block.

**Detector/lifter pool rebuild pattern** (`src/main.py` lines 506-560):
```python
pending_detector = getattr(app.state, "pending_detector_backend", None)
pending_det_params = getattr(app.state, "pending_detector_params", {}) or {}
active_lifter_name = getattr(app.state, "active_lifter", None)
pending_lifter_params = getattr(app.state, "pending_lifter_params", {}) or {}

from src.perception.registry import Detection3DRegistry, DetectorRegistry
import src.perception.backends  # noqa: F401
import src.perception.lifters   # noqa: F401
from src.perception.worker_pool import DetectorWorkerPool

backend_name = pending_detector or DetectorRegistry.get_default()
lifter_name = active_lifter_name or Detection3DRegistry.get_default()
detector_pool = DetectorWorkerPool(
    robot_ids=list(robots.keys()),
    backend_name=backend_name,
    backend_params=pending_det_params,
    lifter_name=lifter_name,
    intrinsics_per_robot=intrinsics_per_robot,
    lifter_params=pending_lifter_params,
)
```

**Warmup before event emission** (`src/main.py` lines 562-599):
```python
# Synchronous warmup BEFORE emitting detector_restart_complete (D-03).
dummy_frames: dict[str, SensorFrame] = {}
for rid in robots:
    cached = None
    if hasattr(bridge, "get_last_frame"):
        try:
            cached = bridge.get_last_frame(rid)
        except Exception:
            cached = None
    if cached is None:
        cached = SensorFrame(
            rgb=np.zeros((480, 640, 3), dtype=np.uint8),
            depth=np.zeros((480, 640), dtype=np.float32),
            ground_truth_pose=np.eye(4),
            sim_time=0.0,
        )
    dummy_frames[rid] = cached

detector_pool.warmup_all(dummy_frames)
detector_pool.start()
app.state.detector_pool = detector_pool
app.state.active_detector_backend = backend_name
```

**Restart-complete WS payload pattern** (`src/main.py` lines 625-641):
```python
streaming_viz._message_queue.append({
    "type": "detector_restart_complete",
    "payload": {
        "backend": getattr(app.state, "active_detector_backend", "yolov11"),
        "lifter": getattr(app.state, "active_lifter", "median_depth"),
    },
})
```

---

### `tests/perception/test_lifter_routes.py` (test, request-response)

**Analog:** `tests/perception/test_detector_routes.py`

**Importable fake class pattern** (`tests/perception/test_detector_routes.py` lines 35-80):
```python
class FakeYolo:
    CAPABILITIES = {
        "framework": "fake",
        "license": "MIT",
        "cpu_latency_hint_ms": 10,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "confidence_threshold": {"type": "number", "live_tunable": True, "default": 0.5},
            "model_path": {"type": "string", "live_tunable": False, "default": "yolo11n.pt"},
        },
    }
    @classmethod
    def available(cls):
        return True, None
```

**Clean-registry fixture** (`tests/perception/test_detector_routes.py` lines 114-130):
```python
@pytest.fixture(autouse=True)
def _clean_registries():
    from src.perception.registry import DetectorRegistry, Detection3DRegistry
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
```

**App client fixture** (`tests/perception/test_detector_routes.py` lines 155-173):
```python
@pytest.fixture
def app_client(register_fakes):
    from backend.web.server import create_app
    command_cb = MagicMock()
    app, _viz = create_app(robot_ids=["r0"], command_cb=command_cb)
    app.state.active_detector_backend = "fake_yolo"
    app.state.pending_detector_backend = None
    app.state.pending_detector_params = {}
    client = TestClient(app)
    return client, command_cb, app
```

**Route assertions** (`tests/perception/test_detector_routes.py` lines 201-233, 257-278):
```python
def test_select_sets_pending_backend(app_client):
    client, cb, app = app_client
    r = client.post("/api/detectors/select", json={"backend": "fake_yolo"})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "restarting", "backend": "fake_yolo"}
    assert app.state.pending_detector_backend == "fake_yolo"
    cb.assert_called_with({"action": "restart"})

def test_patch_params_live_tunable_and_requires_restart(app_client):
    r = client.patch("/api/detectors/params", json={"params": {"confidence_threshold": 0.8, "model_path": "yolo11s.pt", "bogus_key": "nope"}})
    results = r.json()["results"]
    assert results["confidence_threshold"]["status"] == "applied"
    assert results["model_path"]["status"] == "requires_restart"
    assert results["bogus_key"]["status"] == "unknown_parameter"
```

---

### `frontend/src/stores/__tests__/detectorStore.shape.test.ts` (test, transform)

**Analog:** current store test style plus `frontend/src/stores/slamStore.ts` API.

**Structural-equivalence assertion pattern** (`frontend/src/stores/__tests__/detectorStore.shape.test.ts` lines 1-19):
```typescript
import { describe, it, expect } from 'vitest';
import { useSlamStore } from '../slamStore';
import { useDetectorStore } from '../detectorStore';

// DET-UI-06 / D-03: detectorStore structural equivalence with slamStore.
// (1) Superset: every slamStore key has a detectorStore counterpart.
// (2) Exact extras: documented additions set.
// (3) Setter-arity parity.
```

**Key-set and arity checks** (`frontend/src/stores/__tests__/detectorStore.shape.test.ts` lines 42-73):
```typescript
describe('detectorStore structural equivalence with slamStore (D-03)', () => {
  const slamState = useSlamStore.getState() as unknown as Record<string, unknown>;
  const detState = useDetectorStore.getState() as unknown as Record<string, unknown>;
  const slamKeys = new Set(Object.keys(slamState));
  const detKeys = new Set(Object.keys(detState));

  it('detectorStore has every slamStore key (superset)', () => {
    const missing = [...slamKeys].filter((k) => !detKeys.has(k));
    expect(missing).toEqual([]);
  });

  it('every slamStore setter has an equivalent-arity detectorStore setter', () => {
    const slamSetters = [...slamKeys].filter((k) => typeof slamState[k] === 'function');
    for (const setter of slamSetters) {
      const detFn = detState[setter];
      expect(typeof detFn).toBe('function');
      expect((detFn as Function).length).toBe((slamState[setter] as Function).length);
    }
  });
});
```

---

### `frontend/package.json` and `frontend/vitest.config.ts` (config, batch)

**Analog:** current frontend package/config.

**Script and dependency pattern** (`frontend/package.json` lines 6-31):
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "test": "vitest run",
  "test:watch": "vitest"
},
"devDependencies": {
  "jsdom": "^29.0.2",
  "vitest": "^4.1.4"
}
```

**Vitest config pattern** (`frontend/vitest.config.ts` lines 1-13):
```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    include: [
      'src/**/__tests__/**/*.test.{ts,tsx}',
      'src/**/*.test.{ts,tsx}',
    ],
  },
});
```

## Shared Patterns

### Store shape and fetch functions
**Source:** `frontend/src/stores/slamStore.ts` lines 25-88
**Apply to:** `detectorStore.ts`, `detectorStore.shape.test.ts`, `useWebSocket.ts`

Use flat Zustand state, flat setter methods, and top-level `fetchXState()` helpers. Do not introduce slices or middleware for Phase 3 clones.

### Dropdown interaction
**Source:** `frontend/src/components/AlgorithmDropdown.tsx` lines 14-44 and 94-140
**Apply to:** `DetectorDropdown.tsx`, `LifterDropdown.tsx`

Use document-level `mousedown` and `keydown` effects only while open, close after selection, gray unavailable rows with `not-allowed`, and surface unavailable reasons via `title`.

### Restart and polling fallback
**Source:** `frontend/src/components/AlgorithmSection.tsx` lines 9-29, 51-125; `frontend/src/hooks/useWebSocket.ts` lines 210-214
**Apply to:** `DetectorSection.tsx`, `useWebSocket.ts`, `src/main.py`

Primary path is WS `*_restart_complete`; fallback is REST polling every 500ms for 20 attempts. Set `isRestarting` before POST, clear only after WS/poll success or failure.

### Parameter updates
**Source:** `frontend/src/components/ParameterPanel.tsx` lines 6-25; `backend/web/server.py` lines 176-208
**Apply to:** `DetectorParameterPanel.tsx`, detector param WS handling, lifter param REST handling

Local UI always updates first. `live_tunable` sends debounced WS and/or stores pending live params; non-live params stage for next restart/switch. Unknown params must return `unknown_parameter` and not mutate app state.

### REST validation and errors
**Source:** `backend/web/slam_routes.py` lines 17-28, 36-61, 153-175; `backend/web/detector_routes.py` lines 180-281
**Apply to:** lifter list/select/active/params routes and tests

Use Pydantic `BaseModel`, whitelist names against registry output before state mutation, return 404 for unknown, 400 for unavailable, 503 for uninitialized pool where applicable, and keep per-key param results.

### Registry side-effect imports
**Source:** `backend/web/slam_routes.py` lines 107-112; `backend/web/detector_routes.py` lines 180-186
**Apply to:** every lifter route handler

```python
import src.perception.lifters  # noqa: F401 — trigger @detection_3d registration
from src.perception.registry import Detection3DRegistry
```

### Capability badges
**Source:** `frontend/src/components/CapabilityBadge.tsx` lines 1-40
**Apply to:** `AlgorithmDropdown.tsx`, `AlgorithmSection.tsx`, `DetectorDropdown.tsx`, `DetectorSection.tsx`, `LifterDropdown.tsx`

Boolean true renders a label-only pill; false/null/undefined renders nothing; latency numbers render as `~{value}ms`; other values render as `label: value`.

### Test fixtures
**Source:** `tests/perception/test_detector_routes.py` lines 35-173
**Apply to:** `tests/perception/test_lifter_routes.py`

Fakes must be module-level importable classes. Clear registries before and after every test. Build `TestClient` from `create_app`, then force active backend/lifter state to the fake under test.

## No Analog Found

None. Every new or modified file has at least a role-match analog in the codebase. The weakest analog is `frontend/vitest.config.ts`, where the pattern comes from the installed Vite/Vitest stack and research recommendation rather than an older in-tree config.

## Metadata

**Analog search scope:** `frontend/src/components`, `frontend/src/stores`, `frontend/src/hooks`, `frontend/src/utils`, `backend/web`, `src/main.py`, `tests/perception`, `frontend/package.json`
**Files scanned:** 25
**Pattern extraction date:** 2026-04-30
**Important current-main note:** several Phase 3 artifacts already exist in this checkout and have been superseded by later phases in places. In particular, lifter selection is currently `POST /api/detectors/lifter-hotswap` with no restart, while the original Phase 3 context specified `POST /api/detectors/lifter-select` with restart. Planners targeting the original Phase 3 contract should follow CONTEXT.md; planners targeting current main should preserve the hot-swap route and tests.
