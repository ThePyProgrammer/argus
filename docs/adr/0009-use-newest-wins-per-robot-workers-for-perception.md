# ADR-0009: Use Newest-Wins Per-Robot Workers for Perception

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Architecture Pattern |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` |
| Informed | Perception and coordination contributors |
| Supersedes | Shared detector drain loop for all robots |
| Superseded by |  |
| Related | ADR-0007, ADR-0013 |

## Context

Simulation produces frames faster than detector backends can process them, especially on CPU. v3.0 requirements call for each robot to run a `DetectorWorker` with a single-slot latest-frame queue and worker pool keyed by robot ID. Detection results must carry capture pose and timestamp so stale outputs are still placed in the correct world frame.

## Options Considered

1. **Per-robot worker with single-slot newest-wins queue** — each robot owns a worker and stale pending frames are overwritten.
2. **One shared detector worker** — simple and memory-efficient but slow robot A can block robot B.
3. **Unbounded or bounded FIFO queues** — preserve every frame but create stale detections and memory pressure.
4. **Status quo / do nothing** — keep implicit queueing behavior in the detector implementation.

## Decision

**In the context of** real-time simulation producing frames faster than CPU detectors consume them, **facing** stale detections and multi-robot fairness issues, **we decided for** per-robot workers with single-slot newest-wins backpressure **to achieve** bounded latency and independent robot pipelines, **accepting** that many frames will be intentionally dropped.

## Rationale

For live perception, the newest relevant frame is more valuable than a complete backlog. FIFO queues make results increasingly stale and visually misleading. Per-robot workers isolate one robot's detector latency from the others, while capture metadata preserves correctness for delayed results.

## Consequences

### Positive

- Queue size remains bounded under slow detector backends.
- Robot-specific detector state, metrics, and backend selection are possible.
- UI can surface freshness and queue-depth metrics honestly.

### Negative

- Dropped frames make offline replay and exact per-frame metrics incomplete unless captured elsewhere.
- Loading one heavy model per robot can waste memory if implemented naively.

### Neutral / Follow-up

- For N-robot heavy detection, batching across robots may become preferable to N model instances.
- Downstream consumers must use detection capture pose/time, not current robot pose.

## References

- `.planning/REQUIREMENTS.md` — DET-API-04 and DET-API-05
- `.planning/PROJECT.md` — Per-robot DetectorWorker decision
- `.planning/research/ARCHITECTURE.md` — Threading model
- `.planning/research/PITFALLS.md` — stale pose and throughput pitfalls
