# ADR-0005: Use Browser-Based Command and Control with WebSocket Streaming

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `README.md`, `frontend/package.json`, `pyproject.toml` |
| Informed | Frontend and visualization contributors |
| Supersedes | Rerun-first operator UI for the main workflow |
| Superseded by |  |
| Related | ADR-0004, ADR-0013, ADR-0014 |

## Context

Argus needs a real-time command-and-control interface that users can open locally in a browser. The project chose WebStreamingViz over Rerun for the primary workflow because browser access avoids a desktop visualization dependency and supports integrated controls, metrics, camera feeds, 3D map viewing, and pipeline editing.

## Options Considered

1. **Browser C2 with FastAPI WebSocket streaming** — stream robot state, maps, camera frames, detections, and metrics to React/Three.js.
2. **Rerun desktop viewer as the primary UI** — use a strong robotics visualization tool but outside the browser control surface.
3. **Terminal-only or script-driven operation** — keep visualization and control minimal.
4. **Status quo / do nothing** — maintain multiple competing visualization paths without a primary interface.

## Decision

**In the context of** a multi-robot simulation that needs live control, visualization, metrics, and pipeline editing, **facing** the limits of desktop-only tools and terminal workflows, **we decided for** browser-based command and control using FastAPI WebSockets, React, Three.js, React Flow, and Zustand **to achieve** a single integrated operator surface, **accepting** the burden of maintaining a custom frontend and streaming protocol.

## Rationale

The browser UI is where the system's value is visible: multiple robots, map deltas, camera frames, detection overlays, backend selection, metrics, and graph editing. Rerun remains useful for debugging, but the product architecture centers the web dashboard.

## Consequences

### Positive

- Users can operate Argus through `localhost:8000` without a separate desktop app.
- The same UI can expose simulation control, perception state, and architecture-level pipeline configuration.
- WebSocket message contracts become explicit integration points between backend and frontend.

### Negative

- The team owns frontend performance, WebGL resource management, and wire compatibility.
- Browser rendering constraints shape backend payload rates and formats.

### Neutral / Follow-up

- Streaming payloads should be rate-limited and rounded where possible.
- Debug-only visualization paths should not become alternative sources of truth for operator behavior.

## References

- `.planning/PROJECT.md` — Key Decisions: WebStreamingViz over Rerun
- `README.md` — Streaming Architecture and Frontend sections
- `frontend/package.json` — React, Three.js, React Flow, Zustand stack
- `pyproject.toml` — FastAPI, Uvicorn, WebSocket optional dependencies
