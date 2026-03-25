# Phase 14: Interactive ComfyUI-esque React Flow Pipeline Graph - Research

**Researched:** 2026-03-23
**Domain:** React Flow node-graph editor, pipeline configuration backend, Zustand state management
**Confidence:** HIGH

## Summary

Phase 14 adds a ComfyUI-style visual node-graph editor using `@xyflow/react` (React Flow v12) where users build SLAM processing pipelines by dragging nodes onto a canvas, connecting typed ports, and tuning parameters. The graph serializes to JSON and is sent to a backend `PipelineBuilder` via `POST /api/pipeline/apply`, triggering the existing Coordinator restart mechanism.

The frontend work is substantial: 9 new components, 1 new Zustand store (`pipelineStore`), and integration with the existing `App.tsx` layout via a view toggle. The backend work is moderate: new pipeline routes, a `PipelineBuilder` that interprets graph JSON into Coordinator configuration, and preset CRUD endpoints. Both sides build on well-established patterns already in the codebase (Zustand stores, FastAPI routes, registry-based discovery).

**Primary recommendation:** Use `@xyflow/react` v12.x with custom nodes, custom edges, and `isValidConnection` for typed port enforcement. Follow existing project conventions (inline styles, Zustand flat stores, FastAPI routers). Reuse `ParameterPanel` rendering logic in `NodeInspector`, `ConfirmModal` for apply confirmations, and `RestartOverlay` for pipeline restart feedback.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Free-form node graph** -- users can add, remove, and rewire nodes freely (not a fixed pipeline)
- **Four node categories:** Core pipeline (Sensor, SLAM, Merger, Viz Output), Processing/filter, Splitter/combiner, Custom parameter
- **Typed ports with visual hints** -- each port has a data type (PointCloud, Pose, Image, Scalar). Only compatible types connect. Colored sockets per type.
- **Auto-discover from registries** -- SLAM backends and merge strategies auto-populate from `SLAMRegistry` and `MergeRegistry`
- **Compact inline + detail panel** -- nodes show 2-3 key params inline; selected node opens right-side inspector with full JSON Schema rendering
- **Key params determined by schema metadata** -- add `primary: true` to JSON Schema properties
- **Custom parameter nodes use typed connections** -- Scalar output port connects to any matching input port, overriding node's own param value
- **Live-tunable vs startup-only distinction preserved** -- lightning bolt for live, lock for startup-only
- **Apply button triggers restart** -- "Apply Pipeline" serializes graph config, POSTs to backend, triggers `Coordinator.reset_for_restart()`
- **Named presets** -- save/load graph configs as named JSON files on backend. Ship with 3 built-in defaults.
- **JSON graph config format** -- nodes array (type, id, params) + edges array (source_id:port -> target_id:port). Endpoint: `POST /api/pipeline/apply`
- **Animated edges + node status while running** -- pulsing/flowing dots, status badges, throughput on edges
- **Toggleable full-width panel** -- toggle between "3D Viewer" and "Pipeline Editor" as hero area content
- **Node palette: sidebar + context menu** -- collapsible left panel with categories; right-click for searchable add-node menu
- **ComfyUI-style colored headers** -- per-category colors, dark canvas, minimap

### Claude's Discretion
- React Flow configuration details (edge types, connection validation implementation)
- Exact port type color scheme and socket shapes
- Node layout algorithm (auto-layout on load vs manual placement only)
- Animation implementation for edge data flow
- Preset file storage location and naming convention
- PipelineBuilder architecture on the backend
- Graph validation error display (toast, inline, modal)
- Debounce strategy for live parameter updates from the graph
- Default presets content (which nodes, which connections)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @xyflow/react | ^12.10 | Node-graph canvas, custom nodes/edges, drag-to-connect, minimap, controls | Only mature React node-graph library; 20k+ GitHub stars, actively maintained, used by ComfyUI-like tools |
| react | ^18.3.1 | Already in project | Existing dependency |
| zustand | ^5.0.0 | pipelineStore state management | Existing dependency, flat store pattern established |
| typescript | ~5.6.0 | Type safety | Existing dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @xyflow/react/MiniMap | (included) | Graph navigation minimap | Always visible in bottom-right |
| @xyflow/react/Background | (included) | Dot grid canvas background | Canvas visual treatment |
| FastAPI | >=0.100.0 | Pipeline REST endpoints | Backend route module |
| pydantic | (existing) | Request/response validation | Pipeline config schema |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @xyflow/react | rete.js | Rete is more opinionated but less mature; React Flow has better docs, larger community |
| @xyflow/react | litegraph.js | LiteGraph is what ComfyUI actually uses but has no React integration, imperative canvas API |
| Custom SVG canvas | N/A | Would require months of work; React Flow handles zoom, pan, selection, undo natively |

**Installation:**
```bash
cd frontend && npm install @xyflow/react
```

**CSS import required** (sole CSS import for this phase):
```typescript
import '@xyflow/react/dist/style.css';
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
  components/
    pipeline/
      PipelineEditor.tsx      # Root React Flow canvas wrapper
      PipelineNode.tsx         # Custom node component (all categories)
      NodePalette.tsx          # Left sidebar with draggable node types
      NodeInspector.tsx        # Right panel for selected node params
      PortHandle.tsx           # Custom Handle with typed socket visuals
      EdgeAnimated.tsx         # Custom edge with flowing dot animation
      PresetSelector.tsx       # Dropdown for preset management
      ApplyBar.tsx             # Bottom bar with Apply Pipeline CTA
    ViewToggle.tsx             # Toggle between 3D Viewer and Pipeline Editor
  stores/
    pipelineStore.ts           # Graph state, presets, validation, node statuses
  utils/
    pipelineTypes.ts           # TypeScript types for pipeline nodes, edges, ports
    pipelineValidation.ts      # Graph validation (cycles, unconnected ports, no output)
    pipelineSerializer.ts      # Serialize React Flow state to backend JSON format
    nodeDefinitions.ts         # Static + registry-derived node type definitions

backend/web/
  pipeline_routes.py           # Pipeline apply, preset CRUD, node catalog endpoints
src/coordination/
  pipeline_builder.py          # Interprets graph JSON into Coordinator config
```

### Pattern 1: Custom Node with Typed Ports
**What:** Single `PipelineNode` component renders all node categories using data-driven configuration
**When to use:** Every node on the canvas
**Example:**
```typescript
// Source: https://reactflow.dev/learn/customization/custom-nodes
import { Handle, Position, type NodeProps } from '@xyflow/react';

type PipelineNodeData = {
  label: string;
  category: 'sensor' | 'slam' | 'merger' | 'filter' | 'splitter' | 'parameter' | 'output';
  headerColor: string;
  inputs: PortDef[];
  outputs: PortDef[];
  inlineParams: Record<string, ParamDef>;
  status: 'idle' | 'processing' | 'error' | 'initializing';
};

function PipelineNode({ data, selected }: NodeProps) {
  return (
    <div style={{ /* node body styles */ }}>
      <div style={{ background: data.headerColor, /* header */ }}>
        {data.label}
      </div>
      {data.inputs.map((port, i) => (
        <Handle
          key={port.id}
          type="target"
          position={Position.Left}
          id={port.id}
          style={{ top: 52 + i * 24, background: PORT_COLORS[port.dataType] }}
        />
      ))}
      {/* inline params, output handles */}
    </div>
  );
}
```

### Pattern 2: Connection Validation via isValidConnection
**What:** Enforce typed port compatibility at the ReactFlow level
**When to use:** On the ReactFlow component to prevent incompatible connections
**Example:**
```typescript
// Source: https://reactflow.dev/examples/interaction/validation
const isValidConnection = useCallback((connection: Connection) => {
  const sourceNode = nodes.find(n => n.id === connection.source);
  const targetNode = nodes.find(n => n.id === connection.target);
  if (!sourceNode || !targetNode) return false;

  const sourcePort = sourceNode.data.outputs.find(
    (p: PortDef) => p.id === connection.sourceHandle
  );
  const targetPort = targetNode.data.inputs.find(
    (p: PortDef) => p.id === connection.targetHandle
  );
  if (!sourcePort || !targetPort) return false;

  // Type compatibility check
  return sourcePort.dataType === targetPort.dataType;
}, [nodes]);

<ReactFlow
  isValidConnection={isValidConnection}
  // ...
/>
```

### Pattern 3: Drag-and-Drop from Palette
**What:** Native HTML DnD API to drag node types from palette onto canvas
**When to use:** NodePalette -> PipelineEditor interaction
**Example:**
```typescript
// Source: https://reactflow.dev/examples/interaction/drag-and-drop
// In PipelineEditor:
const { screenToFlowPosition } = useReactFlow();

const onDrop = useCallback((event: React.DragEvent) => {
  event.preventDefault();
  const type = event.dataTransfer.getData('application/pipeline-node');
  if (!type) return;

  const position = screenToFlowPosition({
    x: event.clientX,
    y: event.clientY,
  });

  addNode(type, position);  // pipelineStore action
}, [screenToFlowPosition]);

const onDragOver = useCallback((event: React.DragEvent) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
}, []);
```

### Pattern 4: Animated Edge with SVG animateMotion
**What:** Flowing dots along edges when pipeline is running
**When to use:** Custom edge component for active data flow visualization
**Example:**
```typescript
// Source: https://reactflow.dev/examples/edges/animating-edges
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react';

function EdgeAnimated({ id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data }: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  const isActive = data?.fps > 0;

  return (
    <>
      <BaseEdge id={id} path={edgePath}
        style={{ stroke: isActive ? '#4fc3f7' : '#4a4a6a' }} />
      {isActive && (
        <circle r="3" fill="#4fc3f7" opacity={0.6}>
          <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
    </>
  );
}
```

### Pattern 5: pipelineStore Composition with Zustand
**What:** Flat Zustand store following existing project conventions (controlStore, slamStore pattern)
**When to use:** All pipeline graph state management
**Key insight:** Use React Flow's `onNodesChange`/`onEdgesChange`/`onConnect` callbacks wired directly to store actions. Store holds canonical nodes/edges arrays and derives validation state.

### Pattern 6: Backend PipelineBuilder
**What:** A class that interprets the frontend's graph JSON into Coordinator configuration
**When to use:** `POST /api/pipeline/apply` endpoint
**Architecture:**
```python
# pipeline_builder.py
class PipelineBuilder:
    """Interprets graph JSON into coordinator pipeline configuration.

    Validates graph structure, resolves node types to registry entries,
    extracts parameter overrides, and produces a PipelineConfig that
    the Coordinator can use for restart.
    """

    def build(self, graph_json: dict) -> PipelineConfig:
        nodes = graph_json["nodes"]
        edges = graph_json["edges"]
        # 1. Validate DAG (no cycles)
        # 2. Find SLAM backend node -> SLAMRegistry.create(name, **params)
        # 3. Find Merger node -> MergeRegistry.create(name, **params)
        # 4. Apply custom parameter node overrides via edge connections
        # 5. Return PipelineConfig with backend name, params, merger name, params
        ...
```

### Anti-Patterns to Avoid
- **Defining nodeTypes inside render function:** Causes React Flow to remount all nodes every render. Define `nodeTypes` as a module-level constant or useMemo.
- **Storing React Flow internal state separately:** Do NOT maintain separate node position state -- let React Flow's `onNodesChange` be the single source of truth flowing into pipelineStore.
- **Using display:none on Handles:** React Flow needs handle dimensions for edge routing. Use `visibility: hidden` or `opacity: 0` instead.
- **Hand-rolling pan/zoom/selection:** React Flow provides all of this. Do not build custom canvas interaction.
- **Coupling PipelineBuilder to specific backends:** The builder should only know about registries, not specific backend classes. Keep it generic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canvas pan/zoom/selection | Custom SVG/Canvas with pointer events | `@xyflow/react` ReactFlow component | Months of work for correct behavior; React Flow handles touch, trackpad, keyboard nav |
| Edge path routing | Bezier math, collision avoidance | `getBezierPath` / `getSmoothStepPath` from @xyflow/react | Battle-tested SVG path generation |
| Minimap | Custom scaled-down canvas render | `<MiniMap />` from @xyflow/react | Built-in, styled, interactive |
| Graph cycle detection | Recursive DFS from scratch | Kahn's algorithm (topological sort) in `pipelineValidation.ts` | Simple, O(V+E), well-documented -- but DO implement this yourself since it's ~20 lines |
| JSON Schema param rendering | New form renderer | Reuse `ParameterPanel.tsx` rendering logic | Already handles number sliders, booleans, live_tunable indicators |
| Confirmation dialogs | New modal component | Reuse `ConfirmModal.tsx` | Portal-based, Escape key support, dark theme |
| Restart overlay | New loading state | Reuse `RestartOverlay.tsx` | Already styled, spinner animation |

**Key insight:** The project already has param rendering, modals, restart overlays, and dark theme styling. The graph editor is the genuinely new work -- everything else is composition of existing pieces.

## Common Pitfalls

### Pitfall 1: nodeTypes Object Identity Causes Full Remount
**What goes wrong:** Defining `nodeTypes = { pipeline: PipelineNode }` inside a component causes React Flow to unmount and remount all nodes on every render.
**Why it happens:** React Flow uses referential equality to detect nodeTypes changes.
**How to avoid:** Define nodeTypes at module scope or wrap in `useMemo` with empty deps.
**Warning signs:** Nodes lose selection/focus state on any state change.

### Pitfall 2: React Flow CSS Not Imported
**What goes wrong:** Canvas renders but nodes are invisible, handles don't work, edges don't render.
**Why it happens:** React Flow v12 requires `@xyflow/react/dist/style.css` import.
**How to avoid:** Import in `PipelineEditor.tsx` at the top. This is the only external CSS import in the project.
**Warning signs:** Empty canvas with no visible content despite nodes in state.

### Pitfall 3: Handle Position Hardcoding vs Dynamic Positioning
**What goes wrong:** Handle positions overlap or don't align with port labels when node height varies.
**Why it happens:** Using fixed `top` values that don't account for variable inline param count.
**How to avoid:** Calculate handle positions relative to node content. Use CSS to position handles alongside their labels, not absolute pixel offsets.
**Warning signs:** Handles visually disconnected from their port labels.

### Pitfall 4: Stale Closure in isValidConnection
**What goes wrong:** Connection validation uses stale node data, allowing invalid connections.
**Why it happens:** `isValidConnection` callback captures old `nodes` array in closure.
**How to avoid:** Read nodes from `pipelineStore.getState().nodes` inside the callback instead of depending on the reactive `nodes` value.
**Warning signs:** Validation works initially but breaks after adding/removing nodes.

### Pitfall 5: Graph Serialization Losing Custom Parameter Overrides
**What goes wrong:** Custom parameter nodes are connected but their values don't appear in the serialized config sent to backend.
**Why it happens:** Serializer only reads node's own params, not incoming parameter-node edges.
**How to avoid:** In `pipelineSerializer.ts`, traverse edges from parameter nodes and merge their values into connected node params before serialization.
**Warning signs:** Backend ignores parameter node connections; uses default values.

### Pitfall 6: Backend Preset Files Overwritten on Restart
**What goes wrong:** User presets lost when server restarts.
**Why it happens:** Storing presets in memory or temp directory.
**How to avoid:** Store presets as JSON files in a persistent directory (e.g., `data/presets/`). Built-in presets in `data/presets/builtin/` (read-only). User presets in `data/presets/user/`.
**Warning signs:** Presets disappear after server restart.

### Pitfall 7: Applying Pipeline Config Without Validation
**What goes wrong:** Backend receives malformed graph JSON, crashes or produces silent misconfiguration.
**Why it happens:** Frontend validation is bypassable; backend trusts client input.
**How to avoid:** Validate graph JSON server-side in `PipelineBuilder.build()` -- check for cycles, verify all node types exist in registries, verify port type compatibility, verify required connections.
**Warning signs:** Backend errors on valid-looking graph configurations.

## Code Examples

### React Flow Provider Setup
```typescript
// PipelineEditor.tsx must be wrapped in ReactFlowProvider
// Source: https://reactflow.dev/learn
import { ReactFlow, ReactFlowProvider, MiniMap, Background } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Module-level to avoid remount
const nodeTypes = { pipeline: PipelineNode };
const edgeTypes = { animated: EdgeAnimated };

function PipelineEditorInner() {
  const nodes = usePipelineStore(s => s.nodes);
  const edges = usePipelineStore(s => s.edges);
  const onNodesChange = usePipelineStore(s => s.onNodesChange);
  const onEdgesChange = usePipelineStore(s => s.onEdgesChange);
  const onConnect = usePipelineStore(s => s.onConnect);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      isValidConnection={isValidConnection}
      defaultEdgeOptions={{ type: 'animated' }}
      fitView
    >
      <MiniMap style={{ width: 160, height: 120 }} />
      <Background variant="dots" color="#1a1a2e" gap={20} />
    </ReactFlow>
  );
}

export function PipelineEditor() {
  return (
    <ReactFlowProvider>
      <PipelineEditorInner />
    </ReactFlowProvider>
  );
}
```

### Backend Pipeline Apply Endpoint
```python
# pipeline_routes.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

class PipelineApplyRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]

class PresetSaveRequest(BaseModel):
    name: str
    nodes: list[dict]
    edges: list[dict]

@router.post("/apply")
async def apply_pipeline(req: PipelineApplyRequest, request: Request):
    """Validate and apply a pipeline configuration, triggering restart."""
    builder = PipelineBuilder()
    try:
        config = builder.build({"nodes": req.nodes, "edges": req.edges})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Store config for restart
    request.app.state.pending_pipeline_config = config

    # Trigger restart via existing mechanism
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})

    return {"status": "restarting"}

@router.get("/presets")
async def list_presets():
    """List available pipeline presets (built-in + user)."""
    ...

@router.post("/presets")
async def save_preset(req: PresetSaveRequest):
    """Save a named pipeline preset."""
    ...

@router.get("/presets/{name}")
async def load_preset(name: str):
    """Load a pipeline preset by name."""
    ...

@router.get("/node-catalog")
async def node_catalog():
    """Return available node types with their port definitions and param schemas.
    Auto-discovers from SLAMRegistry and MergeRegistry."""
    ...
```

### Graph Validation (Cycle Detection)
```typescript
// pipelineValidation.ts -- Kahn's algorithm for DAG validation
export function detectCycles(nodes: PipelineNode[], edges: PipelineEdge[]): string[] | null {
  const inDegree = new Map<string, number>();
  const adj = new Map<string, string[]>();

  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adj.set(node.id, []);
  }

  for (const edge of edges) {
    adj.get(edge.source)!.push(edge.target);
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
  }

  const queue = [...inDegree.entries()]
    .filter(([, deg]) => deg === 0)
    .map(([id]) => id);

  const sorted: string[] = [];
  while (queue.length > 0) {
    const node = queue.shift()!;
    sorted.push(node);
    for (const neighbor of adj.get(node) ?? []) {
      const newDeg = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, newDeg);
      if (newDeg === 0) queue.push(neighbor);
    }
  }

  if (sorted.length !== nodes.length) {
    // Nodes not in sorted are in cycles
    const cycleNodes = nodes
      .filter(n => !sorted.includes(n.id))
      .map(n => n.data.label);
    return cycleNodes;
  }
  return null;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `reactflow` (v11) | `@xyflow/react` (v12) | Jul 2024 | New package name, new import paths, server component support |
| `useNodesState`/`useEdgesState` | External store (Zustand) with `onNodesChange`/`onEdgesChange` | v12 | Better for complex apps; official recommendation for state outside React Flow |
| Custom edge animations | SVG `animateMotion` + BaseEdge | v12 examples | Simpler, more performant than requestAnimationFrame approaches |

**Deprecated/outdated:**
- `react-flow-renderer` package: Renamed to `reactflow`, then to `@xyflow/react`. Do NOT install old package names.
- `useNodesState`/`useEdgesState` for complex apps: Still works but external store (Zustand) is recommended when state needs to be shared across components.

## Open Questions

1. **How should PipelineBuilder handle filter/processing nodes that don't exist as registries yet?**
   - What we know: SLAM and Merge backends have registries. Filter nodes (voxel downsample, noise removal) are new concepts not yet implemented in the backend.
   - What's unclear: Whether filter nodes should have their own registry or be hardcoded definitions.
   - Recommendation: For Phase 14, define filter nodes as static frontend-only node types with parameter schemas. Backend PipelineBuilder treats them as configuration hints. A future phase can implement a FilterRegistry if needed. The graph editor should not be blocked on backend filter implementation.

2. **How should the backend node catalog endpoint enumerate processing/filter/splitter nodes?**
   - What we know: SLAM backends come from SLAMRegistry.list_backends(), merge strategies from MergeRegistry.list_strategies().
   - What's unclear: Where non-registry node definitions live.
   - Recommendation: Create a `NodeCatalog` class in `pipeline_builder.py` that aggregates registry-discovered nodes with statically-defined utility nodes (filters, splitters, combiners, parameter nodes, sensor inputs, viz outputs). Return all as a unified catalog from `GET /api/pipeline/node-catalog`.

3. **Should auto-layout be applied when loading a preset?**
   - What we know: User decisions say "manual placement only" is a discretion area.
   - Recommendation: Store node positions in preset JSON. On load, restore exact positions. Provide no auto-layout -- users position nodes manually. This avoids layout algorithm dependency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (backend), Vite build check (frontend) |
| Config file | pyproject.toml `[project.optional-dependencies] dev` |
| Quick run command | `python -m pytest tests/web/ -x -q --timeout=10` |
| Full suite command | `python -m pytest tests/ -x -q --timeout=30` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P14-01 | Pipeline graph JSON serialization/deserialization | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_apply_valid_config -x` | Wave 0 |
| P14-02 | Pipeline validation rejects cycles | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_reject_cycle -x` | Wave 0 |
| P14-03 | Pipeline validation rejects unconnected required ports | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_reject_unconnected -x` | Wave 0 |
| P14-04 | Preset CRUD (save, load, list, built-in vs user) | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_preset_crud -x` | Wave 0 |
| P14-05 | Node catalog includes registry backends + static nodes | unit | `python -m pytest tests/web/test_pipeline_routes.py::test_node_catalog -x` | Wave 0 |
| P14-06 | PipelineBuilder resolves graph to coordinator config | unit | `python -m pytest tests/coordination/test_pipeline_builder.py -x` | Wave 0 |
| P14-07 | Frontend TypeScript compiles without errors | build | `cd frontend && npx tsc --noEmit` | Existing |
| P14-08 | Frontend builds successfully | build | `cd frontend && npm run build` | Existing |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/web/test_pipeline_routes.py -x -q --timeout=10`
- **Per wave merge:** `python -m pytest tests/ -x -q --timeout=30 && cd frontend && npm run build`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/web/test_pipeline_routes.py` -- covers P14-01 through P14-05
- [ ] `tests/coordination/test_pipeline_builder.py` -- covers P14-06
- [ ] `data/presets/builtin/` directory with 3 default preset JSON files

## Sources

### Primary (HIGH confidence)
- [React Flow Custom Nodes](https://reactflow.dev/learn/customization/custom-nodes) - NodeProps, Handle component, nodeTypes registration
- [React Flow Handles](https://reactflow.dev/learn/customization/handles) - Handle props, multiple handles, isValidConnection per-handle
- [React Flow Connection Validation](https://reactflow.dev/examples/interaction/validation) - isValidConnection callback on ReactFlow component
- [React Flow Drag and Drop](https://reactflow.dev/examples/interaction/drag-and-drop) - onDrop, screenToFlowPosition, palette-to-canvas pattern
- [React Flow Animated Edges](https://reactflow.dev/examples/edges/animating-edges) - SVG animateMotion, BaseEdge, getBezierPath
- [React Flow v12 Release](https://xyflow.com/blog/react-flow-12-release) - New @xyflow/react package, migration details
- Existing codebase files: `slamStore.ts`, `ParameterPanel.tsx`, `ConfirmModal.tsx`, `RestartOverlay.tsx`, `slam_routes.py`, `registry.py`, `merge_registry.py`, `coordinator.py`

### Secondary (MEDIUM confidence)
- [@xyflow/react npm](https://www.npmjs.com/package/@xyflow/react) - Latest version ~12.10.x confirmed via npm search

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - @xyflow/react is the only credible React node-graph library; version verified via npm
- Architecture: HIGH - Patterns directly derived from official React Flow examples and existing codebase conventions
- Pitfalls: HIGH - nodeTypes remount and CSS import issues are extensively documented in React Flow community

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (React Flow is stable; project conventions well-established)
