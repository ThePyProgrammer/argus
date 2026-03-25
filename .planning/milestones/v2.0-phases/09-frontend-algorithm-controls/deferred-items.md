# Deferred Items - Phase 09

## Pre-existing TypeScript Errors (out of scope)

- `src/components/DetectionBoxes.ts(79)`: Property 'bbox' does not exist on Detection type
- `src/components/SceneViewer.tsx(135)`: Detection[] type incompatibility (depth: null vs undefined)
- `src/hooks/useWebSocket.ts(119)`: Detection type missing 'depth' property

These errors predate Phase 09 and are unrelated to SLAM algorithm controls work.
