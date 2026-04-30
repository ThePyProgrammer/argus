# ADR-0007: Split 2D Detection from 3D Lifting

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `.planning/REQUIREMENTS.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/FEATURES.md` |
| Informed | Perception, metrics, pipeline, and frontend contributors |
| Supersedes | Monolithic YOLO + median-depth detection path |
| Superseded by |  |
| Related | ADR-0006, ADR-0010, ADR-0014 |

## Context

The pre-v3.0 detector path conflated 2D object detection, 2D-to-3D projection, backend lifecycle, queueing, and wire serialization. v3.0 requirements explicitly introduce separate `DetectorProtocol` and `Detection3DProtocol` registries, with `outputs_3d_natively` for end-to-end backends that can bypass a lifter.

## Options Considered

1. **Two-stage detector + lifter pipeline** — compose `DetectorProtocol` with `Detection3DProtocol`.
2. **Single detector protocol returning 3D boxes** — every detector owns detection and lifting.
3. **Keep median-depth projection as part of YOLO** — only wrap the existing behavior.
4. **Status quo / do nothing** — leave perception as one hardcoded module.

## Decision

**In the context of** a perception milestone that must support multiple detectors and real oriented 3D boxes, **facing** entangled 2D and 3D responsibilities, **we decided for** a two-stage detector/lifter architecture **to achieve** independent backend composition and clean pipeline editor nodes, **accepting** the added interface boundary between stages.

## Rationale

2D detection and 3D lifting evolve independently. YOLO, RT-DETRv2, and BoxeR-like models should not each reimplement the same geometry. Separating the stages gives Argus an NxM composition matrix: detector backends can be paired with lifters, while truly 3D-native backends opt out through capabilities.

## Consequences

### Positive

- Lifters can be tested and improved independently from detector models.
- Pipeline editor nodes map naturally to detector, lifter, tracker, and semantic map stages.
- Legacy median-depth behavior remains available as a named lifter rather than an implicit default.

### Negative

- Payloads between stages must carry capture pose, timestamp, intrinsics, and typed detection data.
- Backend authors must understand whether they produce 2D detections, 3D boxes, or both.

### Neutral / Follow-up

- 3D-native backends should set `outputs_3d_natively` and use the canonical OBB wire format.
- Pipeline validation must distinguish `Detections2D` from `Detections3D`.

## References

- `.planning/REQUIREMENTS.md` — DET-API-01 through DET-API-03
- `.planning/research/ARCHITECTURE.md` — Two-stage perception pipeline
- `.planning/research/FEATURES.md` — Table stakes T1, T8, T9, T14
