# Phase 6: React C2 Web Interface for Multi-Robot Visualization and Control - Research

**Researched:** 2026-03-18
**Domain:** Full-stack real-time web visualization (FastAPI + React + Three.js + WebSocket)
**Confidence:** HIGH

## Summary

This phase replaces the desktop Rerun + MuJoCo viewer with a unified browser-based Command & Control (C2) interface. The stack is FastAPI (Python backend with WebSocket support), React (frontend SPA), Three.js (3D rendering), and Zustand (state management). The backend hooks into the existing Coordinator loop to push simulation data over WebSocket, while the frontend renders the 3D scene, point cloud, camera feeds, and robot status in a mission-control layout.

The existing codebase provides a clean integration surface: `Coordinator.run()` already calls `viz.update()` every 2 steps with all necessary data (merged voxels, per-robot frames/poses/trajectories/coverage). The new `WebStreamingViz` replaces `MultiRobotVisualizer` at the same call site but pushes data over WebSocket instead of logging to Rerun. Scene assets are 1214 OBJ files (12MB) + 48 PNG textures (54MB) from `dimos/data/mujoco_sim/scene_office1/` -- these should be pre-converted to a single GLB file for efficient browser loading.

**Primary recommendation:** Use FastAPI with native WebSocket, Zustand for React state, Three.js directly (not react-three-fiber) for maximum control over BufferGeometry updates, and pre-convert OBJ scene to GLB for initial load performance.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Mission control layout: large 3D viewer as hero (~70% of screen), right sidebar with robot status cards, collapsible camera feed strip at the bottom
- Single-page application, no tabs -- everything visible at once
- Sidebar shows one status card per robot: colored dot (online/offline), name, coverage %, current action (exploring/idle/stuck), voxel count. Clicking a robot centers the 3D view on it
- Camera feed strip is collapsible with toggle -- collapsed gives more room to 3D viewer, expanded shows all robot camera feeds side by side with horizontal scroll
- Control panel in sidebar: start/stop exploration, pause/resume, simulation speed slider
- Three.js for in-browser 3D rendering with full orbit/zoom/pan interactivity
- MuJoCo office scene geometry (OBJ meshes + textures) exported and sent to client at startup -- loaded once as static Three.js meshes
- Merged point cloud rendered natively as Three.js Points/BufferGeometry, updated via WebSocket
- Point cloud color mode: toggle between per-robot tinting (blue/orange/palette) and true RGB camera colors. Default is per-robot tinting
- Fading trajectory trails per robot in Three.js -- same visual style as Phase 4 MuJoCo traces
- Robot positions shown as markers in the 3D scene (axis triads or colored spheres)
- WebSocket for all data transport (bidirectional -- backend pushes data, frontend sends commands)
- FastAPI backend with native WebSocket support, serves React build as static files, runs alongside simulation in single process
- Camera feeds: JPEG-compressed frames sent as binary WebSocket messages (~30KB per frame at 320x240)
- Point cloud sync: hybrid delta + periodic full sync. Normal updates send only new voxels since last push. Full cloud sync every N seconds for robustness against missed messages
- Generic message envelope: all messages have `{type, robot_id?, payload}`. Types include: `robot_list`, `pose_update`, `cloud_delta`, `cloud_full`, `camera_frame`, `stats`, `command`
- Dynamic robot registry: backend publishes robot list on WebSocket connect. All UI components auto-generate from this list
- Adding a new robot = adding to the backend registry. No frontend code change needed
- Color assignment: curated 8-color colorblind-safe palette. Robot 1 = blue, Robot 2 = orange (backward compatible), Robot 3+ assigned sequentially from palette
- Camera strip uses horizontal scroll when many robots -- each feed stays the same size, scroll to see more

### Claude's Discretion
- Three.js scene setup (lighting, camera defaults, orbit controls config)
- FastAPI WebSocket message serialization format (msgpack vs JSON for non-binary messages)
- React component architecture and state management (Context API vs Zustand vs Redux)
- Camera JPEG compression quality (balancing bandwidth vs visual quality)
- Point cloud delta tracking implementation (set diff vs timestamp-based)
- Full sync interval (every 5s, 10s, or based on cloud size)
- Scene mesh loading strategy (lazy vs eager, LOD levels)
- Exact colorblind-safe 8-color palette selection

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

This is a new phase (Phase 6) added to the roadmap after v1 completion. No formal requirement IDs exist in REQUIREMENTS.md. The following are derived from the CONTEXT.md decisions:

| ID | Description | Research Support |
|----|-------------|-----------------|
| C2-01 | FastAPI WebSocket backend serves React build and streams simulation data | FastAPI static file serving + WebSocket patterns |
| C2-02 | Three.js 3D scene renders office geometry loaded from pre-converted GLB | OBJ-to-GLB conversion, Three.js GLTFLoader |
| C2-03 | Real-time merged point cloud via Three.js Points/BufferGeometry over WebSocket | Three.js BufferGeometry dynamic update patterns |
| C2-04 | Per-robot camera feeds as JPEG binary WebSocket messages | FastAPI binary WS messages, cv2.imencode |
| C2-05 | Mission control layout with sidebar, 3D hero, collapsible camera strip | React component architecture, CSS grid layout |
| C2-06 | Dynamic robot registry -- UI adapts to N robots without code changes | Zustand store design, generic component patterns |
| C2-07 | Bidirectional control: start/stop/pause/speed commands from browser | WebSocket command messages, Coordinator integration |
| C2-08 | Point cloud color toggle (per-robot tint vs true RGB) | Three.js color attribute swapping |
| C2-09 | Fading trajectory trails per robot | Three.js Line2/LineSegments with alpha gradient |
| C2-10 | Hybrid delta + periodic full point cloud sync | Set-diff delta tracking, periodic full sync |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.110 | HTTP + WebSocket backend | Native WebSocket support via Starlette, async, serves static files, production-ready with uvicorn |
| uvicorn | >=0.27 | ASGI server | Standard FastAPI runner, handles async WebSocket connections efficiently |
| React | 18.x | Frontend SPA framework | Industry standard, component model fits dashboard layout |
| Three.js | r170+ | 3D rendering engine | User-locked decision. BufferGeometry + Points for point clouds, GLTFLoader for scene |
| Zustand | 4.x / 5.x | React state management | Best for real-time data -- selective subscriptions prevent re-render storms. Context API causes all consumers to re-render on any change, unsuitable for high-frequency WebSocket updates |
| TypeScript | 5.x | Frontend type safety | Catches message envelope shape errors at compile time |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| opencv-python-headless | >=4.0 | JPEG compression for camera feeds | Already in project deps. `cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])` |
| @react-three/drei | 9.x | Three.js helpers (OrbitControls, etc.) | Optional -- only if using react-three-fiber. Recommend raw Three.js for this project |
| gltfpack / obj2gltf | latest | Pre-convert OBJ scene to GLB | One-time build step to bundle 1214 OBJ + 48 PNG into single GLB |
| Vite | 6.x | React build tool | Fast dev server with HMR, produces optimized static build for FastAPI to serve |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Zustand | React Context API | Context causes full re-render on any state change -- fatal for 2Hz+ pose updates. Zustand's selective subscriptions are essential |
| Zustand | Redux Toolkit | Redux is heavier, more boilerplate. Zustand is lighter and equally capable for this use case |
| Three.js direct | react-three-fiber (R3F) | R3F adds React reconciliation overhead on every frame. For real-time point cloud updates, direct Three.js with imperative BufferGeometry.attributes.position.needsUpdate gives better control and performance |
| JSON messages | msgpack | JSON is ~25% larger but has native browser parsing (JSON.parse is C-optimized). msgpack needs a JS library and benchmarks show it can be slower for parse in browsers. **Recommendation: Use JSON** for structured messages, binary WebSocket frames only for JPEG camera data |
| OBJ loading at runtime | Pre-converted GLB | 1214 separate OBJ HTTP requests is unacceptable. Single GLB = one request, compressed, with textures embedded. **Must pre-convert** |

**Installation (Python backend):**
```bash
pip install fastapi uvicorn[standard]
```

**Installation (React frontend):**
```bash
npm create vite@latest c2-frontend -- --template react-ts
cd c2-frontend
npm install three zustand
npm install -D @types/three
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  web/                          # NEW -- FastAPI backend
    __init__.py
    server.py                   # FastAPI app, static file mount, WebSocket endpoint
    streaming_viz.py            # WebStreamingViz -- replaces MultiRobotVisualizer
    connection_manager.py       # Track active WebSocket clients
    message_types.py            # Pydantic models for message envelope
  c2-frontend/                  # NEW -- React/Vite project
    src/
      App.tsx                   # Root layout (CSS Grid: hero + sidebar + strip)
      stores/
        robotStore.ts           # Zustand store: robot registry, poses, stats
        controlStore.ts         # Zustand store: simulation control state
      components/
        SceneViewer.tsx         # Three.js canvas mount + scene management
        PointCloud.tsx          # BufferGeometry point cloud manager
        RobotMarker.tsx         # Per-robot 3D marker (sphere + axis triad)
        TrajectoryTrail.tsx     # Fading line segments per robot
        Sidebar.tsx             # Robot status cards + control panel
        RobotCard.tsx           # Single robot status card
        CameraStrip.tsx         # Collapsible camera feed row
        CameraFeed.tsx          # Single robot camera <img> from blob URL
        ControlPanel.tsx        # Start/stop/pause/speed controls
      hooks/
        useWebSocket.ts         # WebSocket connection + message dispatch
        useSceneLoader.ts       # GLB scene loading hook
      utils/
        palette.ts              # Colorblind-safe 8-color palette
        messageTypes.ts         # TypeScript interfaces for WS messages
    public/
      scene.glb                 # Pre-converted office scene (build artifact)
    vite.config.ts
    package.json
  viz/
    multi_robot_viz.py          # EXISTING -- kept for backward compat
  coordination/
    coordinator.py              # EXISTING -- add WebStreamingViz as viz option
```

### Pattern 1: WebSocket Message Envelope
**What:** All messages share a common shape for easy routing
**When to use:** Every message sent over the WebSocket connection

```typescript
// Frontend TypeScript interface
interface WSMessage {
  type: 'robot_list' | 'pose_update' | 'cloud_delta' | 'cloud_full'
      | 'camera_frame' | 'stats' | 'command';
  robot_id?: string;
  payload: unknown;
}

// Backend Python (Pydantic)
class WSMessage(BaseModel):
    type: str
    robot_id: str | None = None
    payload: dict | list
```

Camera frames are the exception: sent as raw binary WebSocket frames with a 1-byte type prefix + robot_id length byte + robot_id ASCII + JPEG bytes. This avoids base64 encoding overhead.

### Pattern 2: WebStreamingViz as Drop-In Replacement
**What:** New class with same `update()` signature as `MultiRobotVisualizer`, but pushes to WebSocket clients instead of Rerun
**When to use:** Swap in Coordinator constructor

```python
class WebStreamingViz:
    """Drop-in replacement for MultiRobotVisualizer that streams to browser."""

    def __init__(self, connection_manager: ConnectionManager):
        self._cm = connection_manager
        self._last_voxel_set: set[tuple[float, float, float]] = set()
        self._last_full_sync = 0.0
        self._full_sync_interval = 10.0  # seconds

    def update(
        self,
        merged_voxels: np.ndarray,
        robot_data: dict,
        frontier_cells: np.ndarray | None = None,
        voronoi_midpoint: np.ndarray | None = None,
        voronoi_direction: np.ndarray | None = None,
        total_coverage: float = 0.0,
        merge_count: int = 0,
    ) -> None:
        """Same signature as MultiRobotVisualizer.update()."""
        # Compute delta or full sync
        # Send pose updates
        # Send camera frames as binary
        # Send stats
        ...
```

### Pattern 3: Zustand Store with Selective Subscriptions
**What:** Robot state in Zustand with selector-based subscriptions to prevent re-render storms
**When to use:** All components consuming real-time data

```typescript
// stores/robotStore.ts
import { create } from 'zustand';

interface RobotState {
  robots: Map<string, RobotInfo>;
  pointCloud: Float32Array;
  pointColors: Uint8Array;
  colorMode: 'robot_tint' | 'true_rgb';
  setRobotList: (ids: string[]) => void;
  updatePose: (robotId: string, pose: number[]) => void;
  updateCloud: (positions: Float32Array, colors: Uint8Array) => void;
}

// Component uses selector -- only re-renders when THIS robot changes
const coverage = useRobotStore(s => s.robots.get(robotId)?.coverage);
```

### Pattern 4: FastAPI Background Task for Simulation
**What:** Simulation runs in a background thread; FastAPI event loop handles WebSocket I/O
**When to use:** Server startup

```python
import asyncio
import threading

@app.on_event("startup")
async def start_simulation():
    # Run MuJoCo simulation in a separate thread (it's CPU-bound)
    thread = threading.Thread(target=run_simulation_loop, daemon=True)
    thread.start()

async def run_simulation_loop():
    """Simulation loop that pushes data via ConnectionManager."""
    # ... coordinator.run() with WebStreamingViz
```

Actually, since MuJoCo simulation is CPU-bound and blocking, it MUST run in a separate thread. FastAPI's async event loop handles WebSocket connections. Communication between them uses `asyncio.Queue` or a shared buffer with locks.

### Pattern 5: Binary Camera Frame Protocol
**What:** Camera JPEG sent as binary WebSocket frame with minimal header
**When to use:** Every camera frame push

```
Binary frame layout:
[1 byte: message type = 0x01 for camera_frame]
[1 byte: robot_id string length]
[N bytes: robot_id as ASCII]
[remaining bytes: JPEG data]
```

Frontend decodes: `new Blob([jpegBytes], { type: 'image/jpeg' })` then `URL.createObjectURL(blob)`.

### Anti-Patterns to Avoid
- **Sending full point cloud every frame:** At 50k+ voxels, a full (N,3) float32 array is 600KB+. Use delta updates (new voxels only) with periodic full sync as fallback
- **Using React state for Three.js objects:** Three.js scene graph should be managed imperatively. React re-renders would destroy/recreate GPU buffers. Use refs and direct Three.js API calls
- **Loading 1214 OBJ files individually:** Each file = 1 HTTP request = connection overhead. Pre-convert to single GLB
- **JSON-encoding JPEG camera frames:** Base64 adds 33% overhead. Use binary WebSocket frames
- **Running MuJoCo in the async event loop:** MuJoCo `mj_step()` is blocking C code. It will freeze all WebSocket handling. Must use a separate thread

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket connection management | Custom socket server | FastAPI native WebSocket | Handles upgrade, ping/pong, disconnect, binary/text modes |
| 3D orbit camera controls | Custom mouse handlers | Three.js OrbitControls | Handles all edge cases: touch, zoom limits, damping, target tracking |
| GLB/GLTF loading | Custom OBJ parser in browser | Three.js GLTFLoader | Handles textures, materials, scene graph, GPU buffer creation |
| React state subscriptions | Custom pub/sub for WS data | Zustand selectors | Prevents re-render cascades, built-in shallow equality checks |
| JPEG compression | Custom encoder | cv2.imencode | Hardware-accelerated, quality parameter, handles color space |
| Scene mesh conversion | Runtime OBJ->mesh pipeline | gltfpack/obj2gltf (build step) | One-time conversion, massive runtime savings |

**Key insight:** The hardest part of this phase is not any single technology but the integration choreography -- simulation thread pushing data to async WebSocket handlers, binary+JSON mixed protocol, and keeping Three.js scene updates decoupled from React re-renders.

## Common Pitfalls

### Pitfall 1: React Re-Render Storm from High-Frequency State Updates
**What goes wrong:** Every WebSocket message updates React state, causing the entire component tree to re-render at 2-10Hz, killing frame rate
**Why it happens:** Using Context API or updating top-level state without selectors
**How to avoid:** Zustand with granular selectors. Three.js scene updated via refs, never via React state. Only sidebar/stats components subscribe to pose/stats data
**Warning signs:** Browser DevTools showing >16ms React commit times, Three.js FPS drops below 30

### Pitfall 2: Memory Leak from Unreleased Blob URLs
**What goes wrong:** Each camera frame creates a Blob URL via `URL.createObjectURL()`. Without cleanup, thousands of blobs accumulate
**Why it happens:** Forgetting `URL.revokeObjectURL(oldUrl)` before creating new one
**How to avoid:** In CameraFeed component, revoke previous URL in cleanup/before setting new one
**Warning signs:** Browser memory usage growing steadily over time

### Pitfall 3: WebSocket Backpressure
**What goes wrong:** Simulation pushes data faster than client can consume. WebSocket send buffer grows, server memory increases, eventually crashes
**Why it happens:** Slow client, large point clouds, or too many camera feeds
**How to avoid:** Use `asyncio.Queue` with maxsize between simulation thread and WebSocket sender. Drop oldest messages when queue full. Send camera frames at reduced rate (every 3rd frame)
**Warning signs:** Server memory growing, client lag increasing

### Pitfall 4: Three.js BufferGeometry Not Updating
**What goes wrong:** Point cloud appears static even though data arrives
**Why it happens:** Forgetting to set `geometry.attributes.position.needsUpdate = true` after modifying the typed array, or not calling `geometry.computeBoundingSphere()`
**How to avoid:** After every position array update: set needsUpdate, recompute bounding sphere. Pre-allocate max-size buffer and use `geometry.setDrawRange(0, actualCount)`
**Warning signs:** Points visible on first load but never change

### Pitfall 5: OBJ Loading Takes Forever
**What goes wrong:** Browser makes 1214 sequential HTTP requests to load OBJ files, taking 30+ seconds
**Why it happens:** Not pre-converting to a single GLB bundle
**How to avoid:** Pre-convert using `gltfpack` or `obj2gltf` as a build step. Serve single `scene.glb` (~10-20MB gzipped)
**Warning signs:** Network tab showing hundreds of pending requests

### Pitfall 6: Simulation Thread Deadlock with Async Event Loop
**What goes wrong:** Simulation thread tries to `await` something, or async handler tries to call blocking MuJoCo code
**Why it happens:** Mixing sync/async incorrectly across thread boundary
**How to avoid:** Simulation thread is pure sync -- writes to a shared buffer (with threading.Lock). Async WebSocket handler reads from buffer, never calls MuJoCo directly. Use `asyncio.run_coroutine_threadsafe()` only when needed
**Warning signs:** Server hangs, no WebSocket messages sent

## Code Examples

### FastAPI WebSocket Server with Static File Serving

```python
# src/web/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="C2 Interface")

# Serve React build
frontend_dir = Path(__file__).parent.parent / "c2-frontend" / "dist"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

# Also serve scene assets
scene_dir = Path(__file__).parent.parent.parent / "dimos" / "data" / "mujoco_sim" / "scene_office1"
app.mount("/assets", StaticFiles(directory=str(scene_dir)), name="scene_assets")

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast_json(self, data: dict):
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                pass

    async def broadcast_bytes(self, data: bytes):
        for ws in self.active:
            try:
                await ws.send_bytes(data)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send robot list on connect
    await ws.send_json({
        "type": "robot_list",
        "payload": {"robots": list(robot_registry.keys())}
    })
    try:
        while True:
            data = await ws.receive_json()
            if data["type"] == "command":
                handle_command(data["payload"])
    except WebSocketDisconnect:
        manager.disconnect(ws)
```

### Three.js Point Cloud with Dynamic Buffer Update

```typescript
// Imperative Three.js -- NOT React component state
class PointCloudManager {
  private geometry: THREE.BufferGeometry;
  private points: THREE.Points;
  private maxPoints = 100_000;
  private currentCount = 0;

  constructor(scene: THREE.Scene) {
    this.geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(this.maxPoints * 3);
    const colors = new Uint8Array(this.maxPoints * 3);
    this.geometry.setAttribute('position',
      new THREE.BufferAttribute(positions, 3));
    this.geometry.setAttribute('color',
      new THREE.BufferAttribute(colors, 3, true)); // normalized
    this.geometry.setDrawRange(0, 0);

    const material = new THREE.PointsMaterial({
      size: 0.05, vertexColors: true, sizeAttenuation: true
    });
    this.points = new THREE.Points(this.geometry, material);
    scene.add(this.points);
  }

  updateFull(positions: Float32Array, colors: Uint8Array) {
    const posAttr = this.geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = this.geometry.attributes.color as THREE.BufferAttribute;
    posAttr.array.set(positions);
    colAttr.array.set(colors);
    this.currentCount = positions.length / 3;
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    this.geometry.setDrawRange(0, this.currentCount);
    this.geometry.computeBoundingSphere();
  }

  appendDelta(newPositions: Float32Array, newColors: Uint8Array) {
    const posAttr = this.geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = this.geometry.attributes.color as THREE.BufferAttribute;
    const newCount = newPositions.length / 3;
    posAttr.array.set(newPositions, this.currentCount * 3);
    colAttr.array.set(newColors, this.currentCount * 3);
    this.currentCount += newCount;
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    this.geometry.setDrawRange(0, this.currentCount);
    this.geometry.computeBoundingSphere();
  }
}
```

### Camera Frame Binary Protocol (Backend)

```python
# src/web/streaming_viz.py
import cv2
import struct

def encode_camera_frame(robot_id: str, rgb: np.ndarray, quality: int = 70) -> bytes:
    """Encode camera frame as binary WebSocket message.

    Layout: [type:1][id_len:1][robot_id:N][jpeg_data:...]
    """
    _, jpeg_buf = cv2.imencode('.jpg', rgb, [cv2.IMWRITE_JPEG_QUALITY, quality])
    rid_bytes = robot_id.encode('ascii')
    header = struct.pack('BB', 0x01, len(rid_bytes))
    return header + rid_bytes + jpeg_buf.tobytes()
```

### Camera Frame Binary Protocol (Frontend)

```typescript
// hooks/useWebSocket.ts
function handleBinaryMessage(data: ArrayBuffer) {
  const view = new DataView(data);
  const msgType = view.getUint8(0);
  if (msgType === 0x01) { // camera_frame
    const idLen = view.getUint8(1);
    const robotId = new TextDecoder().decode(new Uint8Array(data, 2, idLen));
    const jpegData = new Uint8Array(data, 2 + idLen);
    const blob = new Blob([jpegData], { type: 'image/jpeg' });
    const url = URL.createObjectURL(blob);
    // Update store -- revoke old URL first
    useRobotStore.getState().setCameraUrl(robotId, url);
  }
}
```

### Delta Point Cloud Tracking (Backend)

```python
def compute_cloud_delta(
    current_voxels: np.ndarray,
    last_voxel_set: set[tuple[float, float, float]],
) -> tuple[np.ndarray, set[tuple[float, float, float]]]:
    """Compute new voxels since last push using set difference.

    Rounds voxel coordinates to 2 decimal places for stable hashing.
    Returns (delta_voxels, updated_set).
    """
    rounded = np.round(current_voxels, 2)
    current_set = set(map(tuple, rounded))
    new_keys = current_set - last_voxel_set
    if new_keys:
        delta = np.array(list(new_keys), dtype=np.float32)
    else:
        delta = np.empty((0, 3), dtype=np.float32)
    return delta, current_set
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OBJ files loaded individually | Pre-convert to GLB/glTF | Three.js r100+ (2018+) | Single request, compressed, embedded textures |
| React Context for all state | Zustand for high-frequency updates | 2023+ adoption | Eliminates re-render storms for real-time data |
| JSON for binary data over WS | Binary WebSocket frames | Always available | 33% bandwidth savings vs base64-encoded JSON |
| react-three-fiber for all 3D | Direct Three.js for perf-critical updates | Case-by-case | R3F reconciliation overhead matters at high update rates |

**Deprecated/outdated:**
- `THREE.Geometry` (removed in r125+) -- use `BufferGeometry` exclusively
- `THREE.OBJLoader` as runtime loader for large scenes -- pre-convert to GLB instead

## Discretion Recommendations

Based on research, here are recommendations for areas left to Claude's discretion:

### Message Serialization: JSON (not msgpack)
JSON.parse is native C-optimized in browsers. msgpack requires a JS library and benchmarks show it can be *slower* for parsing in V8. The bandwidth savings (~25%) don't justify the added dependency. Camera frames (the largest messages) use binary WebSocket frames regardless.

### State Management: Zustand
Zustand's selective subscription model is essential for this use case. Context API causes all consumers to re-render on any change -- fatal for 2Hz+ pose updates from multiple robots. Zustand is lighter than Redux with equivalent capability.

### Camera JPEG Quality: 70
At 320x240 resolution, quality=70 produces ~15-25KB frames (well under the 30KB target). Quality=50 shows visible artifacts. Quality=85 doubles size with minimal visual improvement.

### Point Cloud Delta Tracking: Set Diff
Round voxel coordinates to 2 decimal places, convert to tuple set, compute set difference. Simple, O(N) per update, and robust. Timestamp-based tracking requires more bookkeeping and is fragile if messages are missed.

### Full Sync Interval: 10 seconds
Balances robustness against missed deltas vs bandwidth. At 50k voxels, a full sync is ~600KB (50000 * 3 * 4 bytes). Every 10 seconds is manageable.

### Scene Mesh Loading: Eager, Single GLB
Pre-convert all 1214 OBJ + 48 PNG textures into a single GLB using `gltfpack` or `obj2gltf` as a build step. Load eagerly at startup with a progress indicator. No LOD needed -- the office scene is small enough for full-res rendering in browser.

### Colorblind-Safe 8-Color Palette: Okabe-Ito
The Okabe-Ito palette is the gold standard for scientific visualization, recommended by Nature Methods. It remains distinguishable across all common types of color vision deficiency.

| Index | Name | Hex | RGB | Assignment |
|-------|------|-----|-----|------------|
| 0 | Blue | #0072B2 | (0, 114, 178) | Robot 1 (backward-compat with existing blue) |
| 1 | Orange | #E69F00 | (230, 159, 0) | Robot 2 (backward-compat with existing orange) |
| 2 | Sky Blue | #56B4E9 | (86, 180, 233) | Robot 3 |
| 3 | Bluish Green | #009E73 | (0, 158, 115) | Robot 4 |
| 4 | Yellow | #F0E442 | (240, 228, 66) | Robot 5 |
| 5 | Vermillion | #D55E00 | (213, 94, 0) | Robot 6 |
| 6 | Reddish Purple | #CC79A7 | (204, 121, 167) | Robot 7 |
| 7 | Black | #000000 | (0, 0, 0) | Robot 8 |

Note: The existing project uses Blue (66,133,244) and Orange (255,152,0). The Okabe-Ito blue (0,114,178) and orange (230,159,0) are close enough to maintain visual continuity while being strictly colorblind-safe.

### Three.js Scene Setup
- **Lighting:** Ambient light (0.4 intensity) + directional light (0.8 intensity, position [10, 20, 15], casting shadows)
- **Camera:** PerspectiveCamera, FOV 60, near 0.1, far 1000. Initial position looking down at scene center from [0, 10, 10]
- **OrbitControls:** enableDamping=true, dampingFactor=0.1, minDistance=1, maxDistance=50. Target initially at scene center

## Open Questions

1. **OBJ-to-GLB Conversion Fidelity**
   - What we know: gltfpack and obj2gltf can convert OBJ to GLB. The scene has 1214 OBJ files referenced from a MuJoCo XML
   - What's unclear: Whether the MuJoCo XML material assignments map cleanly to OBJ MTL files, or if manual material mapping is needed
   - Recommendation: Try automated conversion first. If materials are wrong, export scene geometry from MuJoCo's renderer as a fallback

2. **Simulation Thread Communication**
   - What we know: MuJoCo is CPU-bound blocking code. FastAPI is async. They must run in separate threads
   - What's unclear: Exact latency of passing numpy arrays across thread boundary via shared buffer vs queue
   - Recommendation: Use a shared dataclass protected by `threading.Lock`. Simulation thread writes latest state; async handler reads on demand. Avoids queue backpressure entirely

3. **Go2 Robot Mesh in Browser**
   - What we know: The Go2 robot meshes are in `models/unitree_go2/assets/` as STL/OBJ files used by MuJoCo
   - What's unclear: Whether robot meshes need to be rendered in the 3D view (the user said "markers" -- axis triads or colored spheres)
   - Recommendation: Start with colored spheres for robot positions. Add full robot mesh rendering as optional enhancement

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (Python backend) + Vitest (frontend, if needed) |
| Config file | `pytest.ini` (exists) |
| Quick run command | `pytest tests/test_web_server.py tests/test_streaming_viz.py -x` |
| Full suite command | `pytest tests/ -x --timeout=30` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| C2-01 | FastAPI serves static files + WebSocket endpoint connects | unit | `pytest tests/test_web_server.py::test_ws_connect -x` | Wave 0 |
| C2-02 | Scene GLB conversion produces valid file | manual-only | Manual -- requires gltfpack binary | N/A |
| C2-03 | WebStreamingViz.update() produces correct cloud_delta messages | unit | `pytest tests/test_streaming_viz.py::test_cloud_delta -x` | Wave 0 |
| C2-04 | Camera frame binary encoding/decoding roundtrips correctly | unit | `pytest tests/test_streaming_viz.py::test_camera_frame_encode -x` | Wave 0 |
| C2-05 | React layout renders all panels | manual-only | Manual -- browser visual check | N/A |
| C2-06 | Robot registry message triggers UI generation for N robots | unit (backend) | `pytest tests/test_streaming_viz.py::test_robot_list_message -x` | Wave 0 |
| C2-07 | Command messages from frontend reach Coordinator | integration | `pytest tests/test_web_server.py::test_command_handling -x` | Wave 0 |
| C2-08 | Point cloud color toggle produces both color arrays | unit | `pytest tests/test_streaming_viz.py::test_color_modes -x` | Wave 0 |
| C2-09 | Trajectory trail data serialized correctly | unit | `pytest tests/test_streaming_viz.py::test_trajectory_message -x` | Wave 0 |
| C2-10 | Delta tracking correctly identifies new voxels | unit | `pytest tests/test_streaming_viz.py::test_delta_tracking -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_web_server.py tests/test_streaming_viz.py -x`
- **Per wave merge:** `pytest tests/ -x --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_web_server.py` -- covers C2-01, C2-07 (FastAPI WebSocket endpoint tests using httpx async client)
- [ ] `tests/test_streaming_viz.py` -- covers C2-03, C2-04, C2-06, C2-08, C2-09, C2-10 (WebStreamingViz unit tests)
- [ ] `pip install httpx` -- FastAPI test client dependency for async WebSocket testing
- [ ] Frontend tests are manual-only (browser visual verification) -- no Vitest/Jest setup needed for this phase

## Sources

### Primary (HIGH confidence)
- FastAPI official docs (https://fastapi.tiangolo.com/advanced/websockets/) -- WebSocket endpoint patterns, static file serving
- Three.js official docs (https://threejs.org/docs/) -- BufferGeometry, Points, GLTFLoader, OrbitControls
- Three.js forum (https://discourse.threejs.org/) -- BufferGeometry update patterns, OBJ loading performance
- Okabe-Ito palette (https://mk.bcgsc.ca/colorblind/palettes.mhtml) -- Colorblind-safe 8-color palette hex values

### Secondary (MEDIUM confidence)
- State Management in 2026: Redux vs Zustand vs Context API (https://medium.com/@abdurrehman1/state-management-in-2026-redux-vs-zustand-vs-context-api-ad5760bfab0b) -- Zustand vs Context performance comparison
- Performance Analysis of JSON vs MessagePack for WebSockets (https://dev.to/nate10/performance-analysis-of-json-buffer-custom-binary-protocol-protobuf-and-messagepack-for-websockets-2apn) -- msgpack vs JSON benchmarks
- gltfpack (https://meshoptimizer.org/gltf/) -- OBJ-to-GLB conversion and mesh optimization
- FastAPI + WebSockets + React patterns (https://medium.com/@suganthi2496/fastapi-websockets-react-real-time-features-for-your-modern-apps-b8042a10fd90) -- Full-stack integration patterns

### Tertiary (LOW confidence)
- None -- all findings verified with at least two sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- FastAPI, Three.js, Zustand are well-established with extensive documentation
- Architecture: HIGH -- Pattern follows existing Coordinator/Viz integration; WebSocket patterns are well-documented
- Pitfalls: HIGH -- Common issues (re-render storms, blob leaks, backpressure) documented across many sources
- Scene conversion: MEDIUM -- OBJ-to-GLB conversion is standard but MuJoCo-specific material mapping untested

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable technologies, 30-day validity)
