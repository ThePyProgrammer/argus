# ADR-0013: Use Server-Owned Geometry and a Single Projection Path

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Data Model |
| Deciders | Project maintainers |
| Consulted | `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/research/PITFALLS.md`, `README.md` |
| Informed | Perception, SLAM, and frontend contributors |
| Supersedes | Duplicate projection paths and hardcoded frontend/server FOV math |
| Superseded by |  |
| Related | ADR-0003, ADR-0010 |

## Context

Coordinate transforms are a primary failure mode in robotics perception. Argus previously had duplicate 2D-to-3D paths and frontend reconstruction logic that assumed a hardcoded FOV. v3.0 requirements establish a single projection entrypoint in `src/perception/geometry.py`, use real camera intrinsics, and make the server own geometry before sending OBBs to the frontend.

## Options Considered

1. **Server-owned geometry with one projection path** — consolidate unprojection and box construction around camera intrinsics and world poses.
2. **Keep separate detector, lifter, SLAM, and frontend projection code** — less migration now but persistent divergence.
3. **Frontend reconstructs geometry** — keep payloads smaller but duplicate camera math in TypeScript.
4. **Status quo / do nothing** — allow each feature to copy the projection code it needs.

## Decision

**In the context of** MuJoCo, Open3D, and Three.js using different coordinate conventions, **facing** drift from duplicate projection math, **we decided for** server-owned geometry with one projection path **to achieve** consistent world-frame perception outputs, **accepting** migration effort and stricter geometry tests.

## Rationale

The backend has the authoritative sensor frame, camera intrinsics, depth, and pose. Projection bugs should be fixed once there and covered by tests. The frontend should render geometry already expressed in the shared world frame.

## Consequences

### Positive

- Eliminates hidden frontend assumptions about FOV, image size, and camera convention.
- Makes OBB and point-cloud alignment testable in Python.
- Reduces the chance that new lifters copy stale projection logic.

### Negative

- Any geometry bug now affects all server-owned perception outputs.
- Frontend debugging requires inspecting server payloads rather than local projection math.

### Neutral / Follow-up

- Tests should compare projected points against SLAM clouds and MuJoCo scene expectations.
- Legacy sign-flip configuration should not be extended into new perception paths.

## References

- `.planning/REQUIREMENTS.md` — DET-3D-05 and DET-3D-06
- `.planning/PROJECT.md` — Single geometry path and OBB wire decisions
- `.planning/research/PITFALLS.md` — RGB-D convention drift and FOV hardcode pitfalls
- `README.md` — The Perception Problem
