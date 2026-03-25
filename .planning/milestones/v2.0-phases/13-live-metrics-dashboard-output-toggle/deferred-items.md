# Deferred Items - Phase 13

## Pre-existing TypeScript Errors (out of scope)

1. `DetectionBoxes.ts(79,24)`: Property 'bbox' missing on Detection type
2. `SceneViewer.tsx(138,13)`: Detection[] type incompatibility (depth: number|null vs number|undefined)
3. `useWebSocket.ts(131,50)`: Detection type missing 'depth' property in detections handler cast
4. `useWebSocket.ts(167,14)`: 'crash_fallback' not in WSMessage type union (added in phase 12)

These errors predate phase 13 work and are not caused by metrics pipeline changes.
