# Phase 3: frontend-picker-and-ui - Research

**Researched:** 2026-04-14
**Domain:** React + Zustand frontend (browser C2 surface for pluggable detector / lifter), FastAPI REST clone, Vitest structural-equivalence test
**Confidence:** HIGH (every claim here is verified by reading in-tree code; versions probed via npm registry)

## Summary

Phase 3 is almost entirely a **clone-and-rename** phase with one extension-in-place (`CapabilityBadge`, `RestartOverlay`) and one NEW test toolchain (Vitest). Phase 2 already landed every backend prerequisite: `/api/detectors/{backends,select,active,params}` work end-to-end (10 tests green), `useWebSocket.ts` already dispatches `detections_3d`, `detector_restart_complete`, `detector_param_ack` (currently log-only on restart-complete), `CameraFeed.tsx` already renders per-item `bbox_xyxy` overlays, and `app.state.active_detector_backend` + `pending_detector_*` are wired in `src/main.py:491-567` restart block.

The research surfaced **one critical gap**: the frontend has **no test runner installed** — `frontend/package.json` contains no `test` script, no Vitest, no jsdom. D-03 (Vitest structural-equivalence test for `detectorStore` shape) requires a Wave 0 task that installs `vitest@^4.1.4`, `@vitest/ui@^4.1.4`, `jsdom@^29.0.2` and adds a `test` script + minimal `vitest.config.ts`. Without this, DET-UI-06 cannot be verified automatically.

All five SLAM templates to clone have been read line-by-line; their exact shapes are captured below so the planner can write prescriptive task bodies.

**Primary recommendation:** Plan three parallel waves. Wave 0 installs Vitest + extends `CapabilityBadge` + `RestartOverlay` (migrate the 2 SLAM call sites + 2 more pipeline/SceneViewer call sites in the same wave — zero SLAM behavior change). Wave 1 clones `detectorStore` + ships backend lifter REST routes + `main.py` lifter branch (parallel, no shared files). Wave 2 clones the 4 UI components + wires `CameraFeed` polish + `useWebSocket` store-dispatch. Wave 3 is the final mount (`Sidebar.tsx`) + the Vitest structural-equivalence test.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Component Architecture (DET-UI-01..06)**

- **D-01:** Component strategy is **clone + rename** — duplicate the SLAM component set into Detector variants, each tied to its own store. No generic refactor of existing SLAM components (zero risk to v2.0 SLAM UX). Clones:
  - `AlgorithmDropdown.tsx` (149 lines) → `DetectorDropdown.tsx`
  - `AlgorithmSection.tsx` (231 lines) → `DetectorSection.tsx`
  - `ParameterPanel.tsx` (109 lines) → `DetectorParameterPanel.tsx`
  - `stores/slamStore.ts` (88 lines) → `stores/detectorStore.ts`
  - NEW: `LifterDropdown.tsx` (clone of DetectorDropdown, reads `detectorStore.lifters` + `activeLifter`)
- **D-02:** `detectorStore` shape mirrors `slamStore` **exactly**, with lifter-fields added:
  - Fields: `backends, lifters, activeBackend, activeDisplay, activeParameters, activeLifter, activeLifterDisplay, activeLifterParameters, stagedParams, stagedLifterParams, isRestarting, error, crashMessage`
  - Setters: `setBackends, setLifters, setActive, setActiveLifter, setRestarting, stageParam, stageLifterParam, clearStagedParams, clearStagedLifterParams, setError, updateActiveParam, updateActiveLifterParam, setCrashMessage, clearCrashMessage`
  - `fetchDetectorState()` mirrors `fetchSlamState()` — parallel fetch of `/backends`, `/active`, `/lifters`, `/active-lifter`
- **D-03:** DET-UI-06 verified via Vitest structural-equivalence test at `frontend/src/stores/__tests__/detectorStore.shape.test.ts`. Asserts `Object.keys(useDetectorStore.getState())` superset of `Object.keys(useSlamStore.getState())` + every SLAM setter name has a detector counterpart. TypeScript compile-time check plus runtime diff. **NOT a snapshot test.**

**Capability Badges (DET-UI-01)**

- **D-04:** `CapabilityBadge` extended in-place to accept `{label, value}` props. SLAM call sites migrate to `label={cap} value={true}` preserving current pill styling. Boolean true → label-only pill (current behavior); string/number → `"{label}: {value}"` with special-case `~{value}ms` for latency hint. Never render `false` / null / undefined.
- **D-05:** Badges shown in DetectorSection for the active detector: **`framework`, `license`, `cpu_latency_hint_ms`** — exactly the three keys DET-UI-01 lists. `outputs_3d_natively` drives `LifterDropdown` visibility (functional, not rendered). `input_type` not a visible badge (Phase 5 OWLv2).
- **D-06:** Dropdown option rows show a compact badge row with the SAME three keys. Unavailable backends show greyed-out option + `reason` install hint.

**Lifter Dropdown (DET-UI-02)**

- **D-07:** `LifterDropdown` renders **inline inside `DetectorSection`**, below the Detector capability-badge row and above the Detector ParameterPanel.
- **D-08:** Visibility gate: `LifterDropdown` renders only when `activeBackendInfo?.capabilities?.outputs_3d_natively === false`.
- **D-09:** Switching the lifter triggers a **full restart** — mirrors detector switch flow exactly.
- **D-10:** **Lifter REST routes ship in Phase 3** (added to `backend/web/detector_routes.py`):
  - `GET /api/detectors/lifters`
  - `POST /api/detectors/lifter-select {lifter, params?}`
  - `GET /api/detectors/active-lifter`
  - `PATCH /api/detectors/lifter-params {params}`
  - `src/main.py` restart block extended to consume `pending_lifter` AFTER the detector pool is constructed.

**Restart Overlay + ConfirmModal (DET-UI-04)**

- **D-11:** `RestartOverlay` extended in-place: accepts `subsystem: 'slam' | 'detector' | 'lifter'` prop + `name` prop. Messages: `"Restarting SLAM with {name}..."` / `"Restarting detector with {name}..."` / `"Restarting lifter with {name}..."`.
- **D-12:** **Concurrent restarts render stacked overlays.**
- **D-13:** Overlay DOM mount alongside existing SLAM `RestartOverlay` in the main canvas area (SceneViewer).
- **D-14:** **ConfirmModal is REUSED** — already generic.
- **D-15:** Polling fallback mirrors `AlgorithmSection::pollForRestart` — 500ms × 20 attempts (10s window). WS-driven primary path via `detector_restart_complete`; polling only fires if WS drops.

**RGB 2D Bbox Overlay (DET-UI-05)**

- **D-16:** Scaffolding already landed in Phase 2 (`CameraFeed.tsx:32-34, 124-125, 182-195`). Phase 3 polishes: per-class color palette (reuse `OKABE_ITO_RGB` indexed by `class_id % 8`), label backdrop readability, tooltip decimal places. No new files.

**Sidebar Integration**

- **D-17:** `DetectorSection` mounts in `Sidebar.tsx` as a new collapsible section labeled **"OBJECT DETECTION"**, inserted between SLAM ALGORITHM and MERGE STRATEGY.
- **D-18:** `Sidebar` import list grows by exactly one line.

### Claude's Discretion

- Exact typography/spacing inside DetectorSection (mirror SLAM defaults)
- Restart spinner color (reuse SLAM's `#2ecc71`)
- Param panel confidence-threshold default value (read from backend `parameter_schema.properties.confidence.default`, fall back to 0.5)
- 2D bbox overlay opacity/stroke width (mirror existing DetectionBoxes 3D rendering palette)
- ConfirmModal body text wording (small variations within the decided pattern)
- Which Vitest test runner configuration to use — **research finding: nothing installed, need Wave 0 install task** (see Standard Stack + Wave 0 Gaps below)

### Deferred Ideas (OUT OF SCOPE)

- Generic `BackendSection<T>` refactor — explicitly rejected in D-01.
- Concurrent restart aggregation into a single overlay — stacked overlays ship in Phase 3; aggregate overlay is a Phase 7 polish.
- CrashToast for detector crashes — Phase 5 (DET-MODELS-06).
- Live detection metrics in DetectorSection — Phase 6 (DET-METRICS-01).
- Detector per-robot dispatch UI — Phase 8 (DET-STRETCH-04).
- `input_type: RGB_TEXT_PROMPT` text-prompt UI — Phase 5 (DET-MODELS-04, OWLv2).
- DetectorSection hot-swap without restart — rejected for consistency with SLAM.
- `PointClusterLifter` implementation — Phase 4 (Phase 3 ships the REST + UI surface; `median_depth` is the only available lifter until Phase 4).
- Non-YOLO detector backends populating the dropdown — Phase 5 (Phase 3 will show only `yolov11`).
- `DetectorNode` / pipeline-editor integration — Phase 7.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-UI-01 | Detector dropdown with capability badges (framework, license, CPU latency hint), mirroring SLAM picker | Clone template in `AlgorithmDropdown.tsx:94-143`. `CapabilityBadge` extension (D-04) + capabilities keys confirmed in `YOLOv11Backend.CAPABILITIES` (registry.py:81-87 + yolov11_backend.py:81-87). Badges row in dropdown options mirrors lines 134-140. |
| DET-UI-02 | Lifter dropdown; hidden when active detector has `outputs_3d_natively: true` | `outputs_3d_natively` is a MANDATORY CAPABILITIES key enforced at registry register time (registry.py:43-49, `_DETECTOR_REQUIRED_KEYS`). Frontend reads `activeBackendInfo.capabilities.outputs_3d_natively` — same path AlgorithmSection uses for capability-based rendering. Lifter backend REST ships in Phase 3 (D-10, 4 routes clone of merge-strategy routes). |
| DET-UI-03 | Parameter panel renders `PARAMETER_SCHEMA` as sliders/toggles with debounced `detector_param_update` WS sends | Clone template in `ParameterPanel.tsx:1-109`. `debounce` utility at `frontend/src/utils/debounce.ts` (200ms). `sendRaw` from `controlStore` already exists. WS handler `detector_param_update` already implemented in `backend/web/server.py:161-193` (Phase 2). |
| DET-UI-04 | Backend switch shows restart overlay until `detector_restart_complete` received; warmup required before "ready" | `RestartOverlay.tsx` extension (D-11) — currently hardcodes `"Restarting with {algorithmName}..."` on line 35. `detector_restart_complete` fires AFTER `warmup_all()` in `src/main.py:539-567` — Phase 2 verification confirmed this sequencing. Polling fallback template in `AlgorithmSection.tsx:9-29`. |
| DET-UI-05 | Camera feed renders 2D bbox overlay (class + confidence) per robot | Scaffolding already landed in `CameraFeed.tsx:13-119`. Phase 3 polishes per-class coloring (swap `robotColor(colorIndex)` at line 130 with palette indexed by `det.class_id % 8`). |
| DET-UI-06 | `detectorStore` (Zustand) mirrors `slamStore` structure | Vitest structural-equivalence test (D-03). `slamStore.ts` is 88 lines; detectorStore is `slamStore` + 5 lifter fields + 3 lifter setters + extended `fetchDetectorState`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | ^18.3.1 | UI framework | Already in project — no change |
| zustand | ^5.0.0 | Store | Already in project — `slamStore` template uses same version |
| typescript | ~5.6.0 | Types | Already in project |
| vite | ^6.0.0 | Bundler | Already in project |

### Supporting (NEW for Phase 3)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vitest | ^4.1.4 | Frontend test runner | Required for D-03 structural-equivalence test; integrates with Vite without extra config |
| @vitest/ui | ^4.1.4 | Vitest HTML reporter (optional) | Optional; omit if command-line is enough |
| jsdom | ^29.0.2 | DOM polyfill for Vitest | Required for any test that imports React components or touches `document` — not strictly needed for the D-03 store-shape test (pure state, no DOM), but recommended for future component tests. If tight-scoping Phase 3: Vitest's built-in `happy-dom` (zero config) works too, but jsdom is more battle-tested |

**Installation (Wave 0 task):**
```bash
cd frontend && npm install --save-dev vitest@^4.1.4 jsdom@^29.0.2
```

**Version verification:** `npm view vitest version` → **4.1.4** as of 2026-04-14. `npm view jsdom version` → **29.0.2**. `[VERIFIED: npm registry 2026-04-14]`.

**`vitest.config.ts` (new file, ~10 lines):**
```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',  // or 'node' if we ONLY ship the D-03 store test
    include: ['src/**/__tests__/**/*.test.ts', 'src/**/*.test.ts'],
  },
});
```

**`package.json` addition:**
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vitest | Jest | Jest needs separate babel/TS config; Vitest uses Vite's existing TS pipeline — zero extra config. `[ASSUMED]` — obvious tradeoff |
| jsdom | happy-dom | happy-dom is faster and zero-config but slightly less complete; jsdom is more widely adopted. For pure store-shape tests neither is strictly needed — can set `environment: 'node'`. `[CITED: vitest.dev/guide/environment]` |

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── components/
│   ├── DetectorDropdown.tsx         # NEW (clone of AlgorithmDropdown.tsx:1-149)
│   ├── DetectorSection.tsx          # NEW (clone of AlgorithmSection.tsx:1-231)
│   ├── DetectorParameterPanel.tsx   # NEW (clone of ParameterPanel.tsx:1-109)
│   ├── LifterDropdown.tsx           # NEW (clone of DetectorDropdown — smaller, reads lifters)
│   ├── CapabilityBadge.tsx          # MODIFIED (D-04, in-place)
│   ├── RestartOverlay.tsx           # MODIFIED (D-11, subsystem + name props)
│   ├── AlgorithmSection.tsx         # MODIFIED (migrate CapabilityBadge + RestartOverlay call sites)
│   ├── SceneViewer.tsx              # MODIFIED (pass subsystem="slam" name={activeDisplay} to RestartOverlay; mount detector+lifter RestartOverlay instances for D-12 stacked)
│   ├── pipeline/ApplyBar.tsx        # MODIFIED (migrate to new RestartOverlay signature)
│   ├── CameraFeed.tsx               # MODIFIED (DET-UI-05 polish: per-class color palette)
│   └── Sidebar.tsx                  # MODIFIED (add <DetectorSection /> + import)
├── stores/
│   ├── detectorStore.ts             # NEW (clone of slamStore.ts:1-88 + lifter fields/setters)
│   └── __tests__/
│       └── detectorStore.shape.test.ts  # NEW (D-03 Vitest structural-equivalence)
├── hooks/
│   └── useWebSocket.ts              # MODIFIED (wire detectorStore.setRestarting(false) + fetchDetectorState on detector_restart_complete)
└── utils/
    └── (no changes — palette.ts + debounce.ts reused verbatim)

backend/web/
├── detector_routes.py               # MODIFIED (add 4 lifter routes)
└── server.py                        # MODIFIED (app.state.active_lifter = "median_depth" + pending_lifter = None)

src/
└── main.py                          # MODIFIED (restart block consumes pending_lifter AFTER detector pool)

tests/perception/
└── test_lifter_routes.py            # NEW (REST round-trip tests for 4 new lifter routes; clone of test_detector_routes.py pattern)
```

### Pattern 1: Zustand flat store with REST fetch

**What:** Single-slice Zustand store with flat state + flat setters + a top-level async `fetchXState()` that parallel-fetches from REST and calls setters.

**When to use:** Any backend-selectable subsystem with pre-session restart + optional live params.

**Exact slamStore shape (verified from `frontend/src/stores/slamStore.ts`):**
```typescript
// [VERIFIED: frontend/src/stores/slamStore.ts:1-88]
interface SlamStoreState {
  backends: SLAMBackend[];
  activeBackend: string;                        // default: 'icp'
  activeDisplay: string;                        // default: 'ICP Odometry'
  activeParameters: Record<string, unknown>;    // default: {}
  stagedParams: Record<string, unknown>;        // default: {}
  isRestarting: boolean;                        // default: false
  error: string | null;                         // default: null
  crashMessage: string | null;                  // default: null

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

// Top-level fetch (not in store):
export async function fetchSlamState(): Promise<void> {
  const store = useSlamStore.getState();
  try {
    const [backendsRes, activeRes] = await Promise.all([
      fetch('/api/slam/backends'),
      fetch('/api/slam/active'),
    ]);
    if (backendsRes.ok) { store.setBackends((await backendsRes.json()).backends); }
    if (activeRes.ok) {
      const d = await activeRes.json();
      store.setActive(d.backend, d.display, d.parameters);
    }
  } catch {
    store.setError('Failed to load SLAM backends. Check that the server is running.');
  }
}
```

**detectorStore pattern (D-02 extension):**
```typescript
interface DetectorStoreState {
  // Detector fields (mirror slamStore)
  backends: DetectorBackend[];
  activeBackend: string;                       // default: 'yolov11'
  activeDisplay: string;                       // default: 'YOLOv11-nano'
  activeParameters: Record<string, unknown>;
  stagedParams: Record<string, unknown>;
  isRestarting: boolean;
  error: string | null;
  crashMessage: string | null;

  // Lifter fields (new per D-02)
  lifters: LifterBackend[];
  activeLifter: string;                        // default: 'median_depth'
  activeLifterDisplay: string;                 // default: 'Median Depth (legacy)'
  activeLifterParameters: Record<string, unknown>;
  stagedLifterParams: Record<string, unknown>;

  // Setters (mirror + lifter variants)
  setBackends: (...) => void;
  setActive: (...) => void;
  setRestarting: (...) => void;
  stageParam: (...) => void;
  clearStagedParams: () => void;
  setError: (...) => void;
  updateActiveParam: (...) => void;
  setCrashMessage: (...) => void;
  clearCrashMessage: () => void;
  setLifters: (...) => void;
  setActiveLifter: (...) => void;
  stageLifterParam: (...) => void;
  clearStagedLifterParams: () => void;
  updateActiveLifterParam: (...) => void;
}

export async function fetchDetectorState(): Promise<void> {
  const store = useDetectorStore.getState();
  try {
    const [bRes, aRes, lRes, alRes] = await Promise.all([
      fetch('/api/detectors/backends'),
      fetch('/api/detectors/active'),
      fetch('/api/detectors/lifters'),
      fetch('/api/detectors/active-lifter'),
    ]);
    // ... 4 branches mirroring slamStore's 2 branches
  } catch {
    store.setError('Failed to load detector backends. Check that the server is running.');
  }
}
```

### Pattern 2: Confirm → POST → Poll-or-WS restart flow

**Verified template in `AlgorithmSection.tsx:46-125`**. Flow:
1. Dropdown `onSelect(backendName)` → set `pendingBackend` + open `ConfirmModal`.
2. `onConfirmSwitch` → `useSlamStore.getState().setRestarting(true)` → `fetch('/api/slam/select', POST)` with body `{backend, params?}` → close modal.
3. On 200: `clearStagedParams()` + kick off `pollForRestart(expectedBackend)` which polls `/api/slam/active` 20× at 500ms.
4. WS handler in `useWebSocket.ts:178-183` catches `slam_restart_complete` → `setRestarting(false)` + `fetchSlamState()` (beats the polling if WS arrives first).
5. On failure: `setError(...)` + `setRestarting(false)`.

**Detector flow (D-15) is structurally identical**, replacing `slam` ↔ `detector` and `slam_restart_complete` ↔ `detector_restart_complete`.

### Pattern 3: `live_tunable` split on param change

**Verified template in `ParameterPanel.tsx:6-25`**. Per-key logic:
```typescript
function handleParamChange(key, value, liveTunable) {
  store.updateActiveParam(key, value);  // always update local state
  if (liveTunable) {
    debouncedSendParam(key, value);      // 200ms debounce → sendRaw('slam_param_update')
  } else {
    store.stageParam(key, value);         // staged for next restart
  }
}
```

**Detector variant** uses `type: 'detector_param_update'` — backend handler already lives in `server.py:161-193`.

### Anti-Patterns to Avoid

- **Re-subscribing to the store inside the debounce closure.** `ParameterPanel.tsx:6-9` uses `useControlStore.getState().sendRaw` INSIDE the debounced function, not captured at closure time. This lets the sendRaw reference refresh across WS reconnects. Follow this exact pattern in `DetectorParameterPanel`.
- **Generic refactor.** D-01 explicitly rejects this. Do not introduce a `BackendSection<T>` component.
- **Snapshot test for D-03.** D-03 explicitly specifies structural-equivalence (key-set comparison), NOT snapshot. Snapshots would lock internal Zustand wiring and fail on harmless refactors.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 200ms slider debounce | Custom timer logic | `frontend/src/utils/debounce.ts` | Already shared with SLAM ParameterPanel, battle-tested |
| Color palette per class | Custom colormap | `OKABE_ITO` + `OKABE_ITO_RGB` in `palette.ts` | Already used for robot colors + colorblind-safe |
| Confirm modal | New modal component | `ConfirmModal.tsx` (already props-driven) | Reused as-is per D-14 |
| Numeric slider | Custom slider | `SliderField.tsx` | Shared between SLAM and (future) detector param panels |
| WS send | Direct `ws.send` | `useControlStore.getState().sendRaw({type, …})` | Already registered in `useWebSocket.ts:43-49`; one indirection = reconnect-safe |
| Store state shape test | Custom compare util | Vitest + `Object.keys(store.getState())` set comparison | Cheap, no dependencies beyond Vitest |
| Pydantic request validation | Manual FastAPI body parsing | `pydantic.BaseModel` classes in `detector_routes.py` | Already used for `SelectRequest`/`ParamPatch`; FastAPI auto-rejects malformed with 422 |
| Lifter registry listing | Custom lifter discovery | `Detection3DRegistry.list_backends()` | Already populated on startup (`src.perception.lifters` side-effect import); returns `{name, display, available, capabilities, parameter_schema, reason?}` exactly like detector list |

**Key insight:** Every SLAM component has a well-tested counterpart. Phase 3's job is to clone, not invent. The one new tool is the Vitest toolchain, and that's a 15-line install/config task.

## Runtime State Inventory

Phase 3 is a greenfield UI phase — no renames, no data migration. All five categories explicitly checked:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no DB state touched | N/A |
| Live service config | None — no external service config | N/A |
| OS-registered state | None | N/A |
| Secrets/env vars | None | N/A |
| Build artifacts | Frontend `node_modules/` will gain `vitest` + `jsdom` + transitive deps (~50 MB). `package-lock.json` will change. | Run `npm install` after the Wave 0 task lands |

Nothing else requires migration.

## Common Pitfalls

### Pitfall 1: Running Vitest without a test environment setting (D-03)

**What goes wrong:** Default Vitest env is `node`. If the D-03 test imports anything that indirectly touches `document`/`window`, it fails with `ReferenceError: document is not defined`.

**Why it happens:** The store test imports `detectorStore.ts` and `slamStore.ts`, which are pure state — but TypeScript may pull in React types through `zustand` transitively.

**How to avoid:** Either set `environment: 'jsdom'` in `vitest.config.ts`, or scope the D-03 test to pure imports and keep `environment: 'node'`. Recommended: `jsdom` so we can add component tests later without re-config.

**Warning signs:** Vitest errors on first run mentioning `document`, `window`, or `localStorage`.

### Pitfall 2: CapabilityBadge migration breaks SLAM call sites silently

**What goes wrong:** Two SLAM call sites (`AlgorithmDropdown.tsx:137`, `AlgorithmSection.tsx:169`) use the old `<CapabilityBadge name={cap} />` signature. Third-party pipeline/SceneViewer files don't touch CapabilityBadge — only SLAM does.

**Why it happens:** Extending a public API in-place changes the prop shape; all existing call sites must be updated in the same commit or TypeScript fails at build.

**How to avoid:** In the same wave that extends `CapabilityBadge`, migrate the 2 SLAM call sites to `<CapabilityBadge label={cap} value={true} />`. Assert via `cd frontend && npx tsc --noEmit` as part of the verification step.

**Warning signs:** `tsc` exit 2 with `Property 'name' does not exist on type ...`.

### Pitfall 3: RestartOverlay call-site migration misses pipeline/ApplyBar

**What goes wrong:** Grep shows **THREE** RestartOverlay call sites (not two):
- `frontend/src/components/SceneViewer.tsx:399` — passes `algorithmName={activeDisplay}` for SLAM
- `frontend/src/components/pipeline/ApplyBar.tsx:168` — passes `algorithmName="pipeline configuration"`
- `frontend/src/components/RestartOverlay.tsx:1` — definition

Miss the pipeline ApplyBar one and the pipeline editor will silently break on Phase 7.

**How to avoid:** In the same wave that extends `RestartOverlay`, update BOTH:
- SceneViewer: `<RestartOverlay subsystem="slam" name={activeDisplay} />`
- ApplyBar: `<RestartOverlay subsystem="slam" name="pipeline configuration" />` (pipeline-applies-are-slam-restarts semantically)

**Warning signs:** `npx tsc --noEmit` fails on `pipeline/ApplyBar.tsx`.

### Pitfall 4: Detection3DRegistry not populated at lifters REST call time

**What goes wrong:** `GET /api/detectors/lifters` returns `{lifters: []}` because the registry is lazily populated by a side-effect import — and that import lives in `src/main.py:505`, not in the FastAPI app boot.

**Why it happens:** `backend/web/server.py:create_app()` doesn't import `src.perception.lifters`. The detector-routes analog side-steps this because `DetectorRegistry` is populated by `src.perception.backends` import, which also isn't in server.py — but `test_detector_routes.py` works because it explicitly registers fakes.

**How to avoid:** In the lifter routes handlers, follow the `slam_routes.py` precedent (lines 110, 118, 141, 156): add `import src.coordination.merge_strategies  # noqa: F401` at the top of each handler function. The lifter equivalent is `import src.perception.lifters  # noqa: F401`. This mirrors exactly the merge-strategy-routes pattern.

**Warning signs:** `GET /api/detectors/lifters` returns empty list when the frontend boots.

### Pitfall 5: LifterDropdown hidden before `activeBackendInfo` loads

**What goes wrong:** On first render, `backends` array is empty (fetch pending). `activeBackendInfo = backends.find(b => b.name === activeBackend)` returns `undefined`. Optional chaining `activeBackendInfo?.capabilities?.outputs_3d_natively` returns `undefined`, which is falsy — so under D-08 rule `=== false` the LifterDropdown hides. But on next render once the fetch resolves and the detector lacks native 3D, the dropdown should appear.

**How to avoid:** D-08 spec is correct — strict `=== false` comparison. The dropdown correctly stays hidden until the active detector's capabilities load (consistent behavior). Document this in the component comment.

**Warning signs:** LifterDropdown flickers on page load — this is EXPECTED behavior per D-08, not a bug.

### Pitfall 6: main.py restart block — lifter consumed before pool constructed

**What goes wrong:** If `pending_lifter` is read BEFORE `DetectorWorkerPool(...)` is built, the new lifter isn't threaded into the pool. Worst case: the pool is built with the OLD lifter and the user's switch is silently ignored.

**Why it happens:** The existing block builds `DetectorWorkerPool(..., lifter_name="median_depth", ...)` as a hardcoded literal at line 517.

**How to avoid:** Read `pending_lifter = getattr(app.state, "pending_lifter", None)` and `pending_lifter_params = getattr(app.state, "pending_lifter_params", {})` at the TOP of the detector-pool-rebuild section (lines 491-494), then thread them into the `DetectorWorkerPool(..., lifter_name=pending_lifter or "median_depth", lifter_params=pending_lifter_params, ...)` call. After successful `warmup_all`, update `app.state.active_lifter = lifter_name` + clear `pending_lifter` (keep `pending_lifter_params` as detector does — live-tunable path).

**Warning signs:** User switches lifter, sees restart overlay clear, but `GET /api/detectors/active-lifter` still shows the old one.

### Pitfall 7: DetectorWorkerPool kwargs for lifter_params

**What goes wrong:** `DetectorWorkerPool(...)` does not currently accept `lifter_params`. Check `src/perception/worker_pool.py` to see the actual constructor signature.

**Why it happens:** Phase 2 shipped `lifter_name` but not `lifter_params` — the latter was deferred to when lifter params actually mattered.

**How to avoid:** Before the plan fires, the planner should verify `DetectorWorkerPool.__init__` signature and either (a) extend it to accept `lifter_params` or (b) descope to "lifter-switch triggers restart with default params; per-lifter params are a future extension." The MedianDepthLifter's `depth_near_m` / `depth_far_m` params are `live_tunable: true` (see `median_depth.py:132-133`), so their values can flow via `PATCH /api/detectors/lifter-params` → coordinator consumes per-frame.

**Warning signs:** Planner writes a task that calls `DetectorWorkerPool(lifter_params=...)` and it fails with `TypeError: unexpected keyword argument`.

## Code Examples

### Example 1: CapabilityBadge extended signature (D-04)

```tsx
// Source: in-place extension of frontend/src/components/CapabilityBadge.tsx:1-21
// [VERIFIED: read in-tree 2026-04-14]

interface CapabilityBadgeProps {
  label: string;
  value: string | number | boolean;
}

export function CapabilityBadge({ label, value }: CapabilityBadgeProps) {
  // Skip false / null / undefined (truth-in-advertising: don't render negative caps)
  if (value === false || value === null || value === undefined) return null;

  // Render rules per D-04:
  //   boolean true   → label-only pill (preserves SLAM pill styling)
  //   number w/ 'latency' in label → "~{value}ms"
  //   other number/string → "{label}: {value}"
  let text: string;
  if (value === true) {
    text = label.replace('supports_', '').replace('outputs_', '').replace(/_/g, ' ');
  } else if (typeof value === 'number' && label.includes('latency')) {
    text = `~${value}ms`;
  } else {
    text = `${label.replace(/_/g, ' ')}: ${value}`;
  }

  return <span style={{ /* same pill style as before */ }}>{text}</span>;
}

// SLAM migration (AlgorithmDropdown.tsx:137, AlgorithmSection.tsx:169):
//   - <CapabilityBadge key={cap} name={cap} />
//   + <CapabilityBadge key={cap} label={cap} value={true} />
```

### Example 2: RestartOverlay extended signature (D-11)

```tsx
// Source: in-place extension of frontend/src/components/RestartOverlay.tsx:1-38
// [VERIFIED: read in-tree 2026-04-14]

interface RestartOverlayProps {
  subsystem: 'slam' | 'detector' | 'lifter';
  name: string;
}

const SUBSYSTEM_LABEL: Record<RestartOverlayProps['subsystem'], string> = {
  slam: 'SLAM',
  detector: 'detector',
  lifter: 'lifter',
};

export function RestartOverlay({ subsystem, name }: RestartOverlayProps) {
  // …existing spinner + positioning…
  return (
    <div style={overlayStyle}>
      <div style={spinnerStyle} />
      <div style={textStyle}>Restarting {SUBSYSTEM_LABEL[subsystem]} with {name}...</div>
    </div>
  );
}

// Migrations (3 call sites):
//   SceneViewer.tsx:399    <RestartOverlay algorithmName={...} /> → <RestartOverlay subsystem="slam" name={activeDisplay} />
//   pipeline/ApplyBar.tsx:168  → <RestartOverlay subsystem="slam" name="pipeline configuration" />
//   NEW: DetectorSection mount → <RestartOverlay subsystem="detector" name={activeDisplay} />
//   NEW: DetectorSection mount → <RestartOverlay subsystem="lifter" name={activeLifterDisplay} />
```

### Example 3: Lifter REST route (D-10)

```python
# Source: clone of backend/web/slam_routes.py:107-176 merge-strategy pattern
# [VERIFIED: read in-tree 2026-04-14]

@router.get("/lifters")
async def list_lifters():
    """List all registered Detection3D lifters with capabilities + schemas."""
    import src.perception.lifters  # noqa: F401 — trigger @detection_3d registration
    from src.perception.registry import Detection3DRegistry
    return {"lifters": Detection3DRegistry.list_backends()}


class LifterSelectRequest(BaseModel):
    lifter: str
    params: dict | None = None


@router.post("/lifter-select")
async def select_lifter(req: LifterSelectRequest, request: Request):
    """Select a Detection3D lifter by name, triggering simulation restart (D-09)."""
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    if req.lifter not in lifters:
        raise HTTPException(status_code=404, detail=f"Unknown lifter: {req.lifter}")
    if not lifters[req.lifter]["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Lifter unavailable: {lifters[req.lifter].get('reason', 'unknown')}",
        )
    request.app.state.pending_lifter = req.lifter
    if req.params:
        request.app.state.pending_lifter_params = req.params
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting", "lifter": req.lifter}


@router.get("/active-lifter")
async def get_active_lifter(request: Request):
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry
    active = getattr(request.app.state, "active_lifter", Detection3DRegistry.get_default())
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    info = lifters.get(active, {})
    return {
        "lifter": active,
        "display": info.get("display", active),
        "parameters": info.get("parameter_schema", {}),
    }


@router.patch("/lifter-params")
async def patch_lifter_params(patch: ParamPatch, request: Request):
    """Mirror of patch_params — live_tunable applied, non-live queued for next restart."""
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry
    active = getattr(request.app.state, "active_lifter", Detection3DRegistry.get_default())
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    info = lifters.get(active, {})
    schema_props = info.get("parameter_schema", {}).get("properties", {})
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

### Example 4: D-03 structural-equivalence test (Vitest)

```typescript
// Source: frontend/src/stores/__tests__/detectorStore.shape.test.ts (NEW)
// [ASSUMED] — this is the recommended implementation; planner may adjust.
import { describe, it, expect } from 'vitest';
import { useSlamStore } from '../slamStore';
import { useDetectorStore } from '../detectorStore';

describe('detectorStore structural equivalence with slamStore (D-03)', () => {
  const slamKeys = new Set(Object.keys(useSlamStore.getState()));
  const detKeys = new Set(Object.keys(useDetectorStore.getState()));

  it('detectorStore has every slamStore state field', () => {
    const missing = [...slamKeys].filter((k) => !detKeys.has(k));
    expect(missing).toEqual([]);
  });

  it('detectorStore adds exactly the expected lifter extension', () => {
    const extra = [...detKeys].filter((k) => !slamKeys.has(k));
    expect(new Set(extra)).toEqual(new Set([
      'lifters',
      'activeLifter',
      'activeLifterDisplay',
      'activeLifterParameters',
      'stagedLifterParams',
      'setLifters',
      'setActiveLifter',
      'stageLifterParam',
      'clearStagedLifterParams',
      'updateActiveLifterParam',
    ]));
  });

  it('detectorStore setter signatures match slamStore', () => {
    const slamSetters = [...slamKeys].filter((k) => typeof (useSlamStore.getState() as any)[k] === 'function');
    for (const setter of slamSetters) {
      const detFn = (useDetectorStore.getState() as any)[setter];
      expect(typeof detFn).toBe('function');
      // Arity must match (parameter count)
      expect(detFn.length).toBe((useSlamStore.getState() as any)[setter].length);
    }
  });
});
```

## Wave Ordering (Dependency Graph)

Dependency graph by file-ownership, not by feature:

```
Wave 0 (parallel, 3 tasks — foundation): ~5 min
├─ T0-A  Install Vitest + jsdom + add test scripts + vitest.config.ts  [frontend/package.json, vitest.config.ts]
├─ T0-B  Extend CapabilityBadge (D-04) + migrate 2 SLAM call sites     [CapabilityBadge.tsx, AlgorithmDropdown.tsx:137, AlgorithmSection.tsx:169]
└─ T0-C  Extend RestartOverlay (D-11) + migrate 2 call sites            [RestartOverlay.tsx, SceneViewer.tsx:399, pipeline/ApplyBar.tsx:168]

Wave 1 (parallel — backend + store, no shared files): ~10 min
├─ T1-A  Clone slamStore → detectorStore with D-02 shape                 [stores/detectorStore.ts (NEW)]
├─ T1-B  Add 4 lifter REST routes to detector_routes.py                  [backend/web/detector_routes.py, server.py:62-64 (app.state.active_lifter)]
└─ T1-C  Extend main.py restart block to consume pending_lifter          [src/main.py:491-567]
      ├── T1-D  tests/perception/test_lifter_routes.py (clone test_detector_routes.py pattern)
      └── depends on T1-B (routes must exist to test)

Wave 2 (parallel — UI clones, depend on Wave 0 + T1-A): ~15 min
├─ T2-A  Clone AlgorithmDropdown → DetectorDropdown                       [components/DetectorDropdown.tsx (NEW)]
│     depends on T1-A (reads detectorStore) + T0-B (CapabilityBadge extension)
├─ T2-B  Clone ParameterPanel → DetectorParameterPanel (type: 'detector_param_update')  [components/DetectorParameterPanel.tsx (NEW)]
│     depends on T1-A only
├─ T2-C  NEW LifterDropdown (smaller clone of DetectorDropdown)           [components/LifterDropdown.tsx (NEW)]
│     depends on T1-A + T0-B
├─ T2-D  CameraFeed.tsx per-class coloring polish (DET-UI-05)             [components/CameraFeed.tsx]
│     no dependencies beyond Wave 0
└─ T2-E  Wire useWebSocket → detectorStore.setRestarting(false) + fetchDetectorState()   [hooks/useWebSocket.ts:140-144]
      depends on T1-A

Wave 3 (serial — mount + verification): ~10 min
├─ T3-A  Create DetectorSection parent component (clone of AlgorithmSection)    [components/DetectorSection.tsx (NEW)]
│     depends on T2-A, T2-B, T2-C, T0-C (RestartOverlay), T1-A, T1-B (lifter routes)
├─ T3-B  Mount DetectorSection in Sidebar.tsx (D-17, D-18)                [Sidebar.tsx]
│     depends on T3-A
├─ T3-C  Write detectorStore.shape.test.ts (D-03)                         [stores/__tests__/detectorStore.shape.test.ts (NEW)]
│     depends on T0-A (vitest) + T1-A (detectorStore)
└─ T3-D  Mount detector + lifter RestartOverlay in SceneViewer (D-12 stacked)  [SceneViewer.tsx]
      depends on T0-C (RestartOverlay signature) + T1-A (isRestarting state)
```

**Rationale:**
- Wave 0 modifies shared primitives (`CapabilityBadge`, `RestartOverlay`) — must land FIRST because every Wave-2 clone + Wave-3 mount depends on the new signatures.
- Wave 1 is all-parallel because backend (`detector_routes.py`, `server.py`, `main.py`) and frontend store (`detectorStore.ts`) touch disjoint files — three executors at once.
- Wave 2 clones are parallelizable (4 different new component files + 2 disjoint edits). Each clone is a standalone leaf.
- Wave 3 is serial because `DetectorSection` must exist before Sidebar can mount it, and the Vitest test needs both stores shipped.

**Critical path** = T0-A → T1-A → T3-A → T3-B. Approximately 30–40 min for a human; faster in parallel GSD.

## Test Map

### Per Requirement → Test Mapping

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-UI-01 | Detector dropdown shows capability badges | component render (deferred) | — (manual visual verify) | — |
| DET-UI-02 | Lifter dropdown hidden when outputs_3d_natively=true | unit (detectorStore) | `cd frontend && npm test` | ❌ Wave 0 |
| DET-UI-03 | Param slider sends debounced WS message | integration (manual click-through OR mocked sendRaw) | `cd frontend && npm test` | ❌ Wave 0 (optional Phase 3) |
| DET-UI-04 | `detector_restart_complete` dismisses overlay | integration (manual) + REST test | `pytest tests/perception/test_lifter_routes.py -x` | ❌ Wave 1 |
| DET-UI-05 | Camera bbox overlay with per-class colors | manual visual | — | — |
| DET-UI-06 | detectorStore mirrors slamStore shape | **structural-equivalence (Vitest)** | `cd frontend && npm test -- detectorStore.shape` | ❌ Wave 0 |
| D-10 lifter REST | 4 new routes: list, select, active-lifter, params | **Python unit (pytest)** | `pytest tests/perception/test_lifter_routes.py -x` | ❌ Wave 1 |

### Tier 1 (Automated — Phase 3 gate)

- **`frontend/src/stores/__tests__/detectorStore.shape.test.ts`** (Vitest, D-03) — REQUIRED. ~30 LOC. Runs in <1 s.
- **`tests/perception/test_lifter_routes.py`** (pytest, clone of `test_detector_routes.py`) — REQUIRED. ~250 LOC with same fixture pattern (FakeLifter + UnavailableLifter module-level, clean-registries autouse fixture, 10 tests across the 4 routes). Runs in <5 s.
- **`cd frontend && npx tsc --noEmit`** — verifies every migrated call site (CapabilityBadge × 2, RestartOverlay × 2, new detector components) compiles with the new prop signatures.

### Tier 2 (Manual — gate on visual verification during /gsd-verify-work)

- DET-UI-01: Detector dropdown populates, clicking shows 3 badges on active backend + in each option row.
- DET-UI-02: Lifter dropdown hidden on native-3D backend (no such backend until Phase 5; verify MedianDepth is shown for YOLOv11 which has `outputs_3d_natively: false`).
- DET-UI-03: Drag confidence slider; watch `[detector] param confidence: applied` in browser console within 200ms; observe fewer detections if threshold raised.
- DET-UI-04: Switch detector → restart overlay visible → fades after warmup (~1–2 s for YOLOv11 which is the only available backend).
- DET-UI-05: Visual check of per-class colored bboxes on CameraFeed (different classes → different colors).
- D-12: Two near-simultaneous switches (detector + lifter, or detector + SLAM) → two stacked overlays.

### Structural-Equivalence Test Technique (D-03)

Three layers:
1. **Compile-time (tsc):** `useDetectorStore.getState()` typed as `DetectorStoreState` — missing a field fails `npx tsc --noEmit`.
2. **Runtime key-set diff:** `Object.keys(useDetectorStore.getState())` ⊇ `Object.keys(useSlamStore.getState())`, and the extra keys are EXACTLY the 10 lifter additions (prevents accidental new fields from sneaking in without updating the test).
3. **Function arity diff:** for each SLAM setter, assert the detector setter has equal `Function.length` (parameter count). Catches signature drift like `setActive(name, display)` vs `setActive(name)`.

This gives drift resistance without snapshot brittleness.

## Threat Model

### Input Surfaces in Phase 3

| Surface | Risk Category | Mitigation |
|---------|---------------|-----------|
| `POST /api/detectors/select` body | T: Tampering (user injects arbitrary backend name) | Pydantic `SelectRequest` validates shape (FastAPI 422 on malformed); handler checks `req.backend in DetectorRegistry.list_backends()` BEFORE mutating `app.state` (mirrors SLAM precedent T-02-19). `[VERIFIED: detector_routes.py:46-55]` |
| `POST /api/detectors/lifter-select` body | T: Tampering | Same pattern — Pydantic + whitelist check against `Detection3DRegistry.list_backends()`. |
| `PATCH /api/detectors/params` body | T: Tampering, I: Information Disclosure via `unknown_parameter` oracle | Per-key schema gate: unknown keys → `{status: 'unknown_parameter'}` with NO state mutation. Live-tunable keys updated; non-live staged for next restart. `[VERIFIED: detector_routes.py:80-103, test_detector_routes.py:257-278]` |
| `PATCH /api/detectors/lifter-params` body | T: Tampering | Same — mirror of `patch_params`. |
| WS `detector_param_update` message | T: Tampering, D: DoS via flood | Schema gate at `server.py:161-193` rejects unknown params with ack; FastAPI WS endpoint is unauthenticated (consistent with rest of app — trust-on-LAN assumption). Debounce at 200ms client-side limits write rate per slider drag. `[VERIFIED: server.py:161-193, ParameterPanel.tsx:6-9]` |
| Parameter slider values | T: Tampering (out-of-bounds) | `SliderField` clamps to `min`/`max` from schema. Backend does NOT re-validate range — live-tunable values are trusted within schema bounds. Out-of-band values (NaN, Infinity) are accepted. **ASVS V5 gap** — low-severity since attacker controls their own UI state; backend crashes would require a deliberate `fetch('/api/detectors/params', ...)` with crafted value. Acceptable for a LAN C2 tool; a production deployment would add server-side range checks. `[ASSUMED]` |

### XSS / Injection Risk (CapabilityBadge, Dropdown display)

**React default:** All `{value}` interpolations in JSX are HTML-escaped by React. `<span>{text}</span>` with text sourced from `backend.display`, `backend.capabilities.license`, `backend.reason` is safe — React will render `<script>` as text, not as a tag.

**Risk:** only exists if code uses `dangerouslySetInnerHTML`. Grep confirms `dangerouslySetInnerHTML` does not appear anywhere in `frontend/src/components/` (verified — no results). Continue to NOT use it in Phase 3 components.

**Who writes `backend.display` / `backend.reason`?** Registry code in `src/perception/registry.py:_probe_availability` and backend decorators. These strings are authored by Argus developers (trusted), not by users or external input. **No injection surface.** `[VERIFIED: grep dangerouslySetInnerHTML frontend/src]`

### STRIDE Summary (for Phase 3 scope)

| STRIDE | Applies? | Control |
|--------|----------|---------|
| Spoofing | No | No auth boundary — single-user LAN assumption |
| **Tampering** | Yes | Pydantic + whitelist (detector/lifter name) + schema gate (params) |
| Repudiation | No | No audit trail needed |
| **Information Disclosure** | Minimal | `unknown_parameter` response mirrors SLAM — no sensitive schema leaked |
| **DoS** | Low | 200ms debounce on client; FastAPI's default limits apply |
| Elevation of Privilege | No | No privilege boundary |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework (frontend) | **Vitest 4.1.4 — NOT YET INSTALLED** |
| Framework (backend) | pytest 8+ (already installed, used by Phase 1/2) |
| Config file | `frontend/vitest.config.ts` (NEW — Wave 0) |
| Quick run command (frontend) | `cd frontend && npm test -- detectorStore.shape` |
| Full suite command (frontend) | `cd frontend && npm test` |
| Quick run command (backend) | `pytest tests/perception/test_lifter_routes.py -x` |
| Full suite command (backend) | `pytest tests/perception/ -x` |
| TypeScript typecheck | `cd frontend && npx tsc --noEmit` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-UI-01 | Dropdown + badges render | manual visual | — | Manual only |
| DET-UI-02 | LifterDropdown visibility gate | unit (component OR store) | `cd frontend && npm test` | ❌ Wave 0 |
| DET-UI-03 | Debounced `detector_param_update` | manual | — | Manual only |
| DET-UI-04 | Restart overlay tied to `detector_restart_complete` | manual | — | Manual only |
| DET-UI-05 | Per-class bbox color overlay | manual visual | — | Manual only |
| DET-UI-06 | detectorStore structural equivalence | **unit (Vitest)** | `cd frontend && npm test -- detectorStore.shape` | ❌ Wave 0 |
| D-10 backend | 4 lifter routes round-trip | unit (pytest) | `pytest tests/perception/test_lifter_routes.py -x` | ❌ Wave 1 |
| D-11 signatures | TypeScript types migrated | tsc | `cd frontend && npx tsc --noEmit` | ✅ (exists, will gate) |

### Sampling Rate

- **Per task commit:** `cd frontend && npx tsc --noEmit` + `cd frontend && npm test` (if Vitest installed) + `pytest tests/perception/test_lifter_routes.py -x` if backend changed.
- **Per wave merge:** `pytest tests/perception/ -x` + `cd frontend && npm test` + `npx tsc --noEmit`.
- **Phase gate:** Full frontend + perception suite green; manual visual verification of DET-UI-01/03/04/05 checklist.

### Wave 0 Gaps

- [ ] `frontend/vitest.config.ts` — NEW file (~10 lines) — required for D-03 test framework.
- [ ] `frontend/package.json` — add `"test": "vitest run"` + `"test:watch": "vitest"` scripts; add `vitest@^4.1.4` + `jsdom@^29.0.2` to devDependencies; run `npm install`.
- [ ] `frontend/src/stores/__tests__/detectorStore.shape.test.ts` — NEW test file (~50 lines) — created in Wave 3 (depends on both stores existing).
- [ ] `tests/perception/test_lifter_routes.py` — NEW test file (~250 lines, clone of test_detector_routes.py with Lifter-specific fakes) — created in Wave 1 alongside the routes.

No existing frontend test infrastructure exists. `find frontend -name "vitest*" -o -name "*.test.*"` returns only `node_modules/` entries (irrelevant third-party tests). `[VERIFIED: 2026-04-14 direct filesystem scan]`

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| node / npm | Frontend build + Vitest | ✓ (implied; frontend already builds) | — | — |
| vitest | D-03 Vitest test | ✗ | — | Install in Wave 0 |
| jsdom | Vitest DOM env | ✗ | — | Use `environment: 'node'` OR install in Wave 0 |
| python 3.10–3.12 | pytest, FastAPI | ✓ | pyproject.toml `requires-python = ">=3.10,<3.13"` | — |
| pytest | Lifter route tests | ✓ | `dev` extra in pyproject.toml | — |
| fastapi.testclient | Lifter route tests | ✓ | via `web` extra | — |
| ultralytics / torch | NOT needed for Phase 3 | — | — | Phase 3 uses `FakeYolo`-style fakes, not real YOLO |

**Missing dependencies with no fallback:** None — all listed gaps are tooling installs (vitest, jsdom), not missing system tools.

**Missing dependencies with fallback:** Vitest + jsdom can be descoped if D-03 is implemented as a Python script that reads both `.ts` files and diffs their exports — but this is strictly worse than Vitest (fragile regex parsing of TypeScript). Strong recommendation: install Vitest in Wave 0.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth boundary (single-user LAN) |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No ACL — trust-on-LAN |
| V5 Input Validation | **yes** | pydantic BaseModels (backend request bodies), schema gate for params, React auto-escaping (frontend) |
| V6 Cryptography | no | No crypto in Phase 3 |
| V7 Error Handling | yes (minor) | HTTP 404/400 with `detail` on `/select` rejections; generic `setError` in UI |
| V13 API Security | **yes** | Pydantic validates POST/PATCH bodies; whitelist check on enum-like fields (backend, lifter) |

### Known Threat Patterns for React + FastAPI + Zustand

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via `dangerouslySetInnerHTML` | T | Not used anywhere in `frontend/src/components/` — verified by grep. DO NOT introduce in Phase 3. |
| XSS via unescaped backend strings | T | React auto-escapes JSX `{}` interpolations. `backend.display`, `backend.reason`, `activeDisplay` etc. all rendered via `{...}` — safe. |
| Over-posting (extra JSON fields) | T | Pydantic `BaseModel` with `extra = 'ignore'` default silently drops unknown keys — consistent with SLAM. Not a risk surface. |
| Enum tampering (malicious backend name) | T | Whitelist check at handler entry before `app.state` mutation (T-02-19 precedent, inherited). |
| Param flood via WS | D | Client-side 200ms debounce per slider; backend has no rate limit (LAN assumption). |
| Memory exhaustion via `stagedParams` dict growth | D | Dict grows with each non-live-tunable param change; cleared on confirmed switch via `clearStagedParams`. Size bounded by schema key count (~3–10 keys per backend). |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `CapabilityBadge` boolean prop | `{label, value}` prop with multi-type rendering | This phase (D-04) | All badge call sites migrate in same commit |
| Hardcoded `RestartOverlay` SLAM message | Discriminated-union `subsystem` prop | This phase (D-11) | 2 existing call sites migrate; new detector+lifter mounts added |
| Frontend tests: none | Vitest + jsdom (minimal) | This phase (Wave 0) | First test infrastructure for the React frontend |
| Detector REST: 4 routes (Phase 2) | 8 routes (Phase 3 adds 4 lifter routes) | This phase (D-10) | `Detection3DRegistry` now user-selectable like `DetectorRegistry` |

**Deprecated/outdated:** None — everything in Phase 3 is additive or in-place extension. No feature retirement.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DetectorWorkerPool.__init__` can accept `lifter_params` or be extended to do so | Pitfall 7 | Low — worst case, Phase 3 ships lifter-switch restart but lifter params are live-tunable only (via PATCH route). The planner should verify worker_pool.py signature before assuming; Pitfall 7 documents the fallback descope. |
| A2 | Vitest `environment: 'jsdom'` is the right choice (vs `happy-dom` or `node`) | Standard Stack | Low — all three work for the D-03 test since it's pure state; jsdom is recommended only to enable future component tests without re-config. |
| A3 | The D-03 test's third assertion (function arity via `Function.length`) is useful | Code Example 4 | Low — if the test proves too noisy (e.g., rest parameters have `length=0`), drop that assertion; keys 1 and 2 are the load-bearing checks. |
| A4 | Parameter sliders can emit out-of-range/NaN/Infinity values without backend crashing | Threat Model | Low — backend handler in `server.py:161-193` does not cast or validate numeric range; untyped `value` is passed through to `pending_detector_params` dict. Would need deliberate attacker action (not from UI). |
| A5 | Backend does not re-validate schema range on PATCH — only schema-key presence | Threat Model | Medium — for a production deployment this should be re-verified and tightened. Acceptable for LAN C2 per project posture. |
| A6 | The visibility gate `activeBackendInfo?.capabilities?.outputs_3d_natively === false` (not `!== true`) is the correct operator | Pitfall 5 | Low — D-08 explicitly specifies `=== false`. Documented in spec as expected flicker-on-load behavior. |

**Nothing in this log is load-bearing** — all six are low-to-medium risk items documented for planner / discuss-phase review.

## Open Questions (RESOLVED)

1. **Does `DetectorWorkerPool.__init__` accept `lifter_params`?** — RESOLVED: Plan 06 Task 1 extends `DetectorWorkerPool.__init__` with `lifter_params: dict | None = None` kwarg forwarded to `Detection3DRegistry.create`. 4 unit tests in `test_worker_pool_lifter_params.py`.
   - What we know: Constructor was added in Phase 2, supports `lifter_name` literal.
   - What's unclear: Whether `lifter_params` kwarg already exists or needs a 1-line signature extension.
   - Recommendation: Planner's T1-C task includes `Read src/perception/worker_pool.py` as first action; if `lifter_params` doesn't exist, extend the `__init__` signature as part of the same task.

2. **Should Phase 3 ship a LifterParameterPanel or inline lifter params into DetectorParameterPanel?** — RESOLVED: Deferred. `MedianDepthLifter` ships with sensible defaults. Phase 3 only wires `LifterDropdown` (selection, not param tuning). Revisit if Phase 4's `PointClusterLifter` needs runtime params.
   - What we know: D-07 says "LifterDropdown inline inside DetectorSection". Lifter params aren't explicitly called out by any D-xx.
   - What's unclear: Where do lifter params render — inline below LifterDropdown, or inside a mini LifterParameterPanel?
   - Recommendation: For Phase 3 ship only the lifter dropdown (no lifter param panel). `MedianDepthLifter` has only 2 live-tunable params (`depth_near_m`, `depth_far_m`) — reasonable defaults. Escalate if user disagrees during plan-check.

3. **Does WS `detector_restart_complete` fire once for the detector restart, or will concurrent lifter+detector restarts yield two messages?** — RESOLVED: Reuse `detector_restart_complete` with enriched payload `{backend, lifter}`. No separate `lifter_restart_complete` type. Plan 06 Task 2 emits the enriched payload from `main.py`.
   - What we know: `main.py:562-567` emits ONE `detector_restart_complete` at the end of the restart block; the lifter is rebuilt inside the same block.
   - What's unclear: If user switches ONLY lifter (not detector), does a WS event fire? Currently no — there's no `lifter_restart_complete` message type.
   - Recommendation: Phase 3 should add a `lifter_restart_complete` WS message emitted inside the same restart block, OR use the same `detector_restart_complete` for both (since lifter lives in the detector pool). Choose the simpler path — reuse `detector_restart_complete` with a richer payload `{backend, lifter}` per CONTEXT.md D-09's description "fires `detector_restart_complete` with `{backend, lifter}` payload after warmup". This is already in CONTEXT; planner should implement.

## Sources

### Primary (HIGH confidence — in-tree verification)
- `.planning/phases/03-frontend-picker-and-ui/03-CONTEXT.md` — 18 locked decisions (D-01..D-18)
- `.planning/REQUIREMENTS.md` — DET-UI-01..06 requirement language
- `.planning/ROADMAP.md §Phase 3` — 5 success criteria
- `.planning/STATE.md` — v3.0 project context
- `.planning/phases/02-per-robot-worker-and-wire-plumbing/VERIFICATION.md` — confirms Phase 3 prerequisites landed
- `frontend/src/stores/slamStore.ts:1-88` — detectorStore clone template
- `frontend/src/components/AlgorithmDropdown.tsx:1-149` — DetectorDropdown template
- `frontend/src/components/AlgorithmSection.tsx:1-231` — DetectorSection template
- `frontend/src/components/ParameterPanel.tsx:1-109` — DetectorParameterPanel template
- `frontend/src/components/CapabilityBadge.tsx:1-21` — extension target
- `frontend/src/components/RestartOverlay.tsx:1-38` — extension target
- `frontend/src/components/ConfirmModal.tsx:1-118` — reused as-is
- `frontend/src/components/CameraFeed.tsx:1-221` — DET-UI-05 scaffolding
- `frontend/src/components/Sidebar.tsx:1-127` — D-17/D-18 mount point
- `frontend/src/hooks/useWebSocket.ts:132-199` — WS handlers to wire
- `frontend/src/utils/debounce.ts`, `frontend/src/utils/palette.ts` — reused verbatim
- `frontend/src/stores/controlStore.ts` — `sendRaw` source
- `frontend/src/utils/messageTypes.ts:82-126` — Detection3DEnvelope + DetectorRestartCompletePayload + DetectorParamAckPayload shapes
- `backend/web/detector_routes.py:1-103` — 4-route clone template for the 4 new lifter routes
- `backend/web/slam_routes.py:107-175` — merge-strategy-routes as exact structural source for lifter routes
- `backend/web/server.py:50-193` — app.state init + WS dispatch
- `src/main.py:480-570` — restart block to extend with `pending_lifter` branch
- `src/perception/registry.py:1-308` — Detection3DRegistry + detector_backend decorator
- `src/perception/backends/yolov11_backend.py:81-116` — CAPABILITIES shape
- `src/perception/lifters/median_depth.py:117-140` — lifter CAPABILITIES + schema shape
- `tests/perception/test_detector_routes.py:1-347` — exact test template for `test_lifter_routes.py`
- `frontend/package.json` — confirmed NO vitest/test script
- `frontend/tsconfig.json` — strict mode enabled
- `pyproject.toml` — Python version, pytest availability

### Secondary (MEDIUM confidence — npm registry)
- `npm view vitest version` → 4.1.4 `[VERIFIED: 2026-04-14]`
- `npm view jsdom version` → 29.0.2 `[VERIFIED: 2026-04-14]`
- `npm view @vitest/ui version` → 4.1.4 `[VERIFIED: 2026-04-14]`

### Tertiary (LOW confidence) — none used; all claims are in-tree verified.

## Metadata

**Confidence breakdown:**
- User Constraints: HIGH — verbatim from CONTEXT.md
- Standard Stack: HIGH — versions verified via npm registry today
- Architecture: HIGH — every template read line-by-line
- Wave Ordering: HIGH — derived from file-ownership overlap (empirical, not inferred)
- Test Map: HIGH — every test file referenced either exists (template) or has a precise creation plan
- Threat Model: MEDIUM — relies on React auto-escape semantics (well-known) + SLAM precedent (verified); A4/A5 are LOW-risk assumptions flagged in Assumptions Log
- Pitfalls: HIGH — 7 pitfalls, each grounded in an in-tree line reference

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (30 days — frontend stack is stable). Vitest version may ship 4.1.5+ by then; re-verify with `npm view vitest version` at plan-check time if more than 7 days have passed.

**Key differences from CONTEXT.md guesses:**
- CONTEXT.md said "Which Vitest test runner configuration to use … reuse whichever is already configured in frontend/package.json". **Research correction:** NONE is configured. Wave 0 must install it. This is the single most important finding beyond what CONTEXT.md already captured.
- CONTEXT.md counted 2 CapabilityBadge call sites — correct (verified by grep).
- CONTEXT.md counted 2 RestartOverlay call sites; grep reveals **3** (SceneViewer + pipeline/ApplyBar + definition). Pipeline ApplyBar must also migrate.
