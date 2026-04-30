# ADR-0010: Use Canonical Server-Owned OBB Wire Format

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Data Model |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/research/PITFALLS.md`, `.planning/research/ARCHITECTURE.md` |
| Informed | Perception, WebSocket, and frontend rendering contributors |
| Supersedes | Client-side 3D box reconstruction from 2D bbox, depth, and FOV |
| Superseded by |  |
| Related | ADR-0007, ADR-0013 |

## Context

The old frontend reconstructed 3D wire boxes from 2D bounding boxes, depth, and a hardcoded FOV. v3.0 replaces this with real oriented 3D boxes produced server-side. Planning records lock a canonical wire format: `center[3]`, `half_extents[3]`, `quaternion[4]` in xyzw order with `qw >= 0`, plus class, score, and optional `track_id`.

## Options Considered

1. **Canonical server-owned OBB wire format** — all backends and lifters serialize through one dataclass and frontend renders verbatim.
2. **Backend-specific payloads** — let each model/lifter emit its natural orientation/box format.
3. **Client-side reconstruction** — keep deriving 3D dimensions in Three.js from 2D boxes and depth.
4. **Status quo / do nothing** — retain legacy `bbox + pos_3d + depth` payloads as the main contract.

## Decision

**In the context of** multiple detectors and lifters producing 3D boxes, **facing** coordinate and quaternion convention drift across Python, Open3D, scipy, WebSockets, and Three.js, **we decided for** one canonical server-owned OBB wire format **to achieve** consistent rendering and testable round trips, **accepting** that all producers must adapt to this format.

## Rationale

Geometry belongs on the server because it has camera intrinsics, depth, pose, and backend context. The frontend should be a renderer, not a second geometry engine. A canonical quaternion order and positive hemisphere avoid invisible convention bugs and noisy payload diffs.

## Consequences

### Positive

- Frontend rendering can be dumb and consistent across backends.
- OBB round-trip tests can lock wire compatibility.
- Inline quaternion construction can be forbidden outside the canonical conversion path.

### Negative

- Existing frontend geometry code must be deleted or rewritten.
- Producers with native matrices, Euler angles, or different quaternion conventions need adapter code.

### Neutral / Follow-up

- Backends and lifters should call `OrientedBox3D.to_wire()` rather than building payload dicts inline.
- TypeScript tuple types should preserve array lengths for centers, extents, and quaternions.

## References

- `.planning/PROJECT.md` — OBB wire format locked decision
- `.planning/REQUIREMENTS.md` — DET-3D-03 through DET-3D-06
- `.planning/research/PITFALLS.md` — OBB orientation sign/parameterization drift
- `.planning/research/ARCHITECTURE.md` — Proposed `detections_3d` payload
