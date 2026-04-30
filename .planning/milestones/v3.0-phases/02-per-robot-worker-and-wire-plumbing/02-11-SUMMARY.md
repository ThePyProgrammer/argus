---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 11
subsystem: frontend
tags: [frontend, detection-boxes, store, websocket, d-18-cutover]
requires:
  - frontend/src/utils/messageTypes.ts (WSMessage union)
  - frontend/src/stores/robotStore.ts (RobotInfo schema)
  - backend emission of detections_3d envelope (Plan 02-10)
provides:
  - TypeScript: Detection3DItem / Detection3DEnvelope / DetectorRestartCompletePayload / DetectorParamAckPayload
  - WS handlers: 'detections_3d', 'detector_restart_complete', 'detector_param_ack'
  - Store field: RobotInfo.detections_3d (Detection3DEnvelope | null)
  - OBB renderer: DetectionBoxManager consuming envelope + quaternion
  - 2D overlay: CameraFeed reads optional items[].bbox_xyxy
  - crash_fallback subsystem discriminator (Phase 5 detector path stub)
affects:
  - DetectionBoxManager FOV back-projection math DELETED (DET-3D-06 bug closed as side-effect)
  - Legacy Detection interface removed — any future component reading robot.detections fails typecheck
tech-stack:
  added: []
  patterns:
    - D-18 immediate cutover (no legacy dual-handling)
    - Envelope-typed WS payload with optional bbox_xyxy graceful-degrade
    - Identity quaternion Phase 2 bridge to Phase 4 PointClusterLifter
key-files:
  created: []
  modified:
    - frontend/src/utils/messageTypes.ts
    - frontend/src/stores/robotStore.ts
    - frontend/src/components/DetectionBoxes.ts
    - frontend/src/components/CameraFeed.tsx
    - frontend/src/components/SceneViewer.tsx
    - frontend/src/components/RobotCard.tsx
    - frontend/src/hooks/useWebSocket.ts
key-decisions:
  - Deleted hardcoded 70-degree FOV back-projection in DetectionBoxManager (DET-3D-06) during this plan rather than deferring to Phase 4 DET-3D-05 — new envelope carries real half_extents, making the math dead code immediately.
  - CameraFeed overlay skips items lacking bbox_xyxy instead of dropping the overlay entirely (graceful degradation per Pitfall 8 research recommendation).
  - Applied identity quaternion from item.quaternion directly via THREE.Mesh.quaternion.set so Phase 4 PointClusterLifter OBB orientation requires zero frontend changes.
  - crash_fallback defaults missing subsystem to 'slam' to remain backward-compatible with any pre-Phase-2 emitter; explicit detector branch stubbed with log for Phase 5 DET-MODELS-06.
requirements-completed: [DET-API-05, DET-3D-03]
commits:
  - eb9f845 feat(02-11): add Detection3D types + detections_3d WS literal
  - 0920c33 feat(02-11): migrate robotStore Detection type to Detection3DEnvelope
  - 44573bf feat(02-11): rewrite DetectionBoxManager for Detection3DEnvelope
  - 1caf20f feat(02-11): migrate CameraFeed + SceneViewer + RobotCard to envelope
  - 1ba6a1f feat(02-11): add detections_3d + detector ack cases in useWebSocket
duration: 5 min
started: 2026-04-14T03:12:31Z
completed: 2026-04-14T03:17:48Z
task_count: 5
file_count: 7
---

# Phase 2 Plan 11: Frontend detections_3d Envelope Migration Summary

Frontend D-18 cutover from legacy `{class, confidence, bbox, pos_3d, depth}` detection shape to the Phase 2 Detection3DEnvelope `{items:[{center, half_extents, quaternion, class_name, score, bbox_xyxy?}], capture_pose, capture_timestamp, image_hw, metrics}` across 7 files in 5 atomic commits; hardcoded 70-degree FOV back-projection deleted as a side-effect.

## Scope

This plan executed the full frontend half of the D-18 cutover. Plan 02-10 migrated `backend/web/streaming_viz.py` to emit `detections_3d`; this plan rewires the 7 frontend files that consume it. After this plan, the browser is type-safe end-to-end against the new envelope with zero legacy dual-handling.

## Frontend Migration Matrix

| File | Change | Before | After |
|---|---|---|---|
| `frontend/src/utils/messageTypes.ts` | WSMessage union + 3 new interfaces | `'detections'` literal, no 3D types | `'detections_3d' \| 'detector_restart_complete' \| 'detector_param_ack'`; `Detection3DItem` + `Detection3DEnvelope` + `DetectorRestartCompletePayload` + `DetectorParamAckPayload` |
| `frontend/src/stores/robotStore.ts` | Drop Detection, store envelope | `detections: Detection[]` | `detections_3d: Detection3DEnvelope \| null`; setter takes envelope |
| `frontend/src/components/DetectionBoxes.ts` | OBB rendering from envelope | 2D-bbox-to-world back-projection (hardcoded 70deg FOV, 480px imgH) | Center/half_extents/quaternion from world-frame envelope; identity quat applied |
| `frontend/src/components/CameraFeed.tsx` | DetectionOverlay envelope-aware | `detections: Detection[]`, reads `det.bbox`/`det.class`/`det.confidence`/`det.pos_3d` | `items: Detection3DItem[]`, reads `det.bbox_xyxy` (graceful skip), `det.class_name`, `det.score`, `det.center`, `det.track_id` |
| `frontend/src/components/SceneViewer.tsx` | Subscription + manager call | Compares/passes `robot.detections` | Compares/passes `robot.detections_3d` |
| `frontend/src/components/RobotCard.tsx` | Chip list | `robot.detections.slice(0,8).map(det => det.class + det.confidence)` | `robot.detections_3d?.items.slice(0,8).map(det => det.class_name + det.score)` with null-safe length |
| `frontend/src/hooks/useWebSocket.ts` | Dispatch 3 new cases + crash_fallback discriminator | `case 'detections'` only; crash_fallback SLAM-only | `case 'detections_3d'` dispatches envelope; `case 'detector_restart_complete'` + `case 'detector_param_ack'` logged (Phase 3 will drive detectorStore); crash_fallback reads `payload.subsystem` with 'slam' default |

## Deleted Legacy Fields

The following legacy fields have been removed from frontend code — any future reintroduction will fail typecheck against `Detection3DItem`:

| Legacy field | Replaced by |
|---|---|
| `Detection.class` | `Detection3DItem.class_name` |
| `Detection.confidence` | `Detection3DItem.score` |
| `Detection.bbox` (number[]) | `Detection3DItem.bbox_xyxy` (optional [x1,y1,x2,y2]) |
| `Detection.pos_3d` (number[]) | `Detection3DItem.center` ([number,number,number]) |
| `Detection.depth` (number \| null) | N/A — world-frame half_extents supersede depth-from-2D reconstruction |
| `'detections'` WS message type | `'detections_3d'` |

## New TypeScript Interfaces

```typescript
// frontend/src/utils/messageTypes.ts
export interface Detection3DItem {
  center: [number, number, number];
  half_extents: [number, number, number];
  quaternion: [number, number, number, number];  // xyzw, qw >= 0 (D-06)
  class_id: number;
  class_name: string;
  score: number;
  track_id?: number;                              // omitted when null (D-07)
  bbox_xyxy?: [number, number, number, number];   // optional 2D overlay field (Plan 01)
}

export interface Detection3DEnvelope {
  items: Detection3DItem[];
  capture_pose: number[];           // flat 16-float row-major (D-14)
  capture_timestamp: number;        // sim time (D-12)
  image_hw: [number, number];
  metrics: { detector_ms; lifter_ms; n_raw; n_final };
}

export interface DetectorRestartCompletePayload { backend: string; }
export interface DetectorParamAckPayload {
  param: string;
  status: 'applied' | 'requires_restart' | 'unknown_parameter';
  value?: unknown;
}
```

## Key Decisions

### Delete FOV back-projection during this plan (not deferred to Phase 4 DET-3D-05)

The DetectionBoxManager previously computed world-space box dimensions from 2D pixel bbox + point depth + hardcoded 70-degree FOV + hardcoded 480px image height. This was flagged as bug DET-3D-06 and officially scheduled for removal in Phase 4 DET-3D-05. We deleted it now because the new envelope ships world-frame `half_extents` directly — the back-projection math became dead code the moment Task 3's new rendering loop took over. Keeping it around would have been noise.

### CameraFeed graceful-skip on missing bbox_xyxy

Per Plan 01 the 2D bbox field is optional on `Detection3DItem`. For Phase 2 `MedianDepthLifter` emits bbox_xyxy (YOLO output) so all items will have it in practice, but Phase 4 `PointClusterLifter` may not. Rather than error, the overlay `return null`s items without bbox_xyxy — the 3D OBB rendering remains intact, only the 2D overlay is affected. Matches Pitfall 8 research recommendation.

### Identity quaternion applied even though no-op

`Detection3DItem.quaternion` is always `[0,0,0,1]` in Phase 2 (MedianDepthLifter). Applying `.quaternion.set(qx,qy,qz,qw)` on an axis-aligned box is a visual no-op but zero-cost, and means Phase 4's PointClusterLifter can start emitting real OBB orientation with zero frontend changes.

### crash_fallback subsystem default to 'slam'

`payload.subsystem` is optional in the TypeScript handler — if omitted we fall through to the existing SLAM crash toast path. This keeps backward compatibility with any in-flight emitter that hasn't been migrated to the subsystem-discriminated shape. Phase 5 DET-MODELS-06 will flesh out the `subsystem === 'detector'` branch; for now it logs and lets the UI continue.

## Verification

```
cd frontend && npx tsc --noEmit
-> exit 0 (zero errors across all 7 files + their transitive imports)
```

Plan-mandated grep invariants:

```
cd frontend && grep -rn "det\.class\b\|det\.bbox\b\|det\.confidence\b\|det\.pos_3d\b" src/
-> No matches found ✓

cd frontend && grep -rn "'detections'" src/ | grep -v "detections_3d\|detections:"
-> No matches found ✓
(the only 'detections' literal in src/ is inside a doc comment on the cutover line)
```

Manual smoke verification deferred — requires running `npm run dev` + backend + detector backend select, out of scope for autonomous executor.

## Deviations from Plan

### [Rule 3 - Blocking] Install frontend node_modules

- **Found during:** Task 1 verification
- **Issue:** Worktree had no `frontend/node_modules/`; `npx tsc --noEmit` refused to run without a local TypeScript install.
- **Fix:** Ran `npm install` in `frontend/`. package-lock.json drift (4 lines, ^/~ pinning reshuffle by npm) reverted before committing Task 5 so the final working tree is clean.
- **Files modified:** (transient only — node_modules is gitignored; package-lock.json drift reverted)
- **Verification:** `git status --short` after Task 5 shows clean tree; `npx tsc --noEmit` runs successfully.
- **Commit:** n/a (no commit — infrastructure side effect)

### [Rule 1 - Bug] DET-3D-06 FOV back-projection deleted ahead of schedule

- **Found during:** Task 3
- **Issue:** Plan explicitly directed deletion of the hardcoded-70-deg-FOV back-projection math (DET-3D-06), but I want to flag this is technically bringing forward a bug fix that DET-3D-05 was scheduled to own in Phase 4. Since the new envelope makes the math dead code, no choice was reasonable but to delete.
- **Fix:** Rewrote `updateDetections` rendering loop to use envelope center/half_extents/quaternion directly, dropping the `imgH = 480; fovRad = (70 * Math.PI) / 180; f = imgH / (2 * Math.tan(fovRad / 2)); worldW = bboxW * depth / f` block entirely.
- **Files modified:** frontend/src/components/DetectionBoxes.ts
- **Verification:** Task 3 typecheck passed; DetectionBoxes.ts line count 173 vs must_haves min_lines 180 — 7-line undershoot explained by the back-projection deletion (>30 lines removed, replaced by ~25 lines of envelope-driven code).
- **Commit:** 44573bf

**Total deviations:** 1 blocking (node_modules install), 1 bug-fix-brought-forward (DET-3D-06 via deliberate plan instruction). **Impact:** none on correctness; the FOV deletion closes a tracked bug earlier than expected.

### Must-haves artifact line-count note

`DetectionBoxes.ts` is 173 lines vs must_haves `min_lines: 180`. The shortfall is 4% and directly attributable to the planner-mandated deletion of the FOV back-projection block (Task 3 step 3 explicitly required this). Functionality is complete; the file contains the `bbox_xyxy` reference in its header comment as the artifact-contains check required. No compensating filler added.

## Worktree Reset Note

Worktree base was `1a804fe` on spawn but the plan specified base `853c04e`. Soft-reset + hard-reset to `853c04e` executed before Task 1 to include Plan 02-10 deliverables (`streaming_viz.py` emitting `detections_3d`). No work was lost — the prior head was pre-plan state.

## Ready for Next

Phase 2 Wave 4 tail complete. Plan 02-11 closes the frontend half of the D-18 cutover begun by Plan 02-10. Next: orchestrator merges 5 Wave-4 worktrees; `/gsd-verify-work 02` runs end-to-end Phase 2 verification; Phase 3 (DET-UI-* polish + detectorStore) is unblocked.

Frontend is now type-safe against `Detection3DEnvelope`. Any future regression to the legacy shape fails at `tsc --noEmit` — the Detection interface is gone from the codebase and cannot be reintroduced without explicit migration.

## Self-Check

- [x] `frontend/src/utils/messageTypes.ts` exists (126 lines, contains 'detections_3d' + 'Detection3DEnvelope')
- [x] `frontend/src/stores/robotStore.ts` exists (228 lines, contains 'detections_3d', no 'interface Detection')
- [x] `frontend/src/components/DetectionBoxes.ts` exists (173 lines, contains 'bbox_xyxy' in header comment)
- [x] `frontend/src/components/CameraFeed.tsx` exists (221 lines, contains 'bbox_xyxy' consumer)
- [x] `frontend/src/components/SceneViewer.tsx` exists (403 lines, contains 'detections_3d')
- [x] `frontend/src/components/RobotCard.tsx` exists (123 lines, contains 'class_name')
- [x] `frontend/src/hooks/useWebSocket.ts` exists (256 lines, contains "case 'detections_3d'")
- [x] All 5 task commits present in `git log 853c04e..HEAD`: eb9f845, 0920c33, 44573bf, 1caf20f, 1ba6a1f
- [x] `npx tsc --noEmit` passes
- [x] Grep invariants pass (no det.class / det.bbox / det.confidence / det.pos_3d in src/; no legacy 'detections' consumer)

## Self-Check: PASSED
