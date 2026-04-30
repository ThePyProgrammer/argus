# ADR-0011: Use CPU-Viable Model Tiers and Pinned Offline Checkpoints

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Technology Choice |
| Deciders | Project maintainers |
| Consulted | `.planning/REQUIREMENTS.md`, `.planning/research/STACK.md`, `.planning/research/PITFALLS.md`, `pyproject.toml` |
| Informed | Model integration and CI contributors |
| Supersedes | Unpinned model downloads and GPU-first backend assumptions |
| Superseded by |  |
| Related | ADR-0002, ADR-0008, ADR-0012 |

## Context

Argus runs on CPU-only MuJoCo simulation. v3.0 needs detector backends that fit that envelope: YOLOv11 as the fast baseline, RT-DETRv2 as a CPU-plausible transformer option, and BoxeR as an offline/reference-quality subprocess backend. Requirements also mandate pinned HuggingFace revisions and a `make download-models` flow for offline/CI use.

## Options Considered

1. **CPU-viable tiers with pinned offline checkpoints** — fast in-process baseline, transformer options where measured, heavy reference backends isolated and pinned.
2. **Always use SOTA GPU detectors** — optimize for accuracy regardless of local hardware.
3. **Download latest model revisions at runtime** — simplest integration but non-reproducible and network-dependent.
4. **Status quo / do nothing** — treat model loading and versions as backend implementation details.

## Decision

**In the context of** a CPU-only system with optional transformer backends, **facing** latency, dependency, and reproducibility risks, **we decided for** CPU-viable model tiers with pinned checkpoint revisions and local prefetch **to achieve** repeatable demos, offline CI, and honest latency expectations, **accepting** that some SOTA models remain out of scope or offline-only.

## Rationale

Model choice is an architecture constraint, not just an implementation detail. Unpinned model revisions and first-run downloads make results irreproducible. GPU-first backends would violate the platform boundary and starve the simulation.

## Consequences

### Positive

- CI and offline runs can fail fast with clear missing-model instructions.
- Latency/quality trade-offs are explicit in capabilities and metrics.
- Heavy or research-code backends can be present without becoming real-time regression targets.

### Negative

- Pinned revisions require maintenance when upstream models or processors change.
- Local model caches consume disk space.
- Some attractive detectors remain excluded until hardware constraints change.

### Neutral / Follow-up

- Networked model download tests should be marked separately from offline tests.
- License restrictions, especially BoxeR's CC-BY-NC-4.0, must stay visible.

## References

- `.planning/REQUIREMENTS.md` — DET-MODELS-02, DET-MODELS-03, DET-MODELS-07, DET-MODELS-08
- `.planning/research/STACK.md` — CPU latency tiers and model stack
- `.planning/research/PITFALLS.md` — HuggingFace revision drift and first-run download pitfalls
- `pyproject.toml` — perception optional dependencies
