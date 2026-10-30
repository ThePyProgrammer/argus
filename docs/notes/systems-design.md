# Systems design rationale

These notes collect the engineering principles from the former README. The [architecture guide](../ARCHITECTURE.md) describes the code; [ADRs](../adr/README.md) record the accepted decisions.

## Make coordinate frames explicit

Depth images become useful only after decoding, unprojection, frame conversion, filtering, and accumulation. MuJoCo, Open3D, and Three.js use different conventions, so an incorrect transform can invalidate an otherwise plausible visualization.

Argus exposes cloud transform settings for inspection and keeps detection geometry on the server. The browser renders the resulting world-frame geometry. This gives projection and box serialization a single implementation to validate.

See [ADR-0013](../adr/0013-use-server-owned-geometry-and-single-projection-path.md).

## Use simple baselines within explicit assumptions

Union-OR map merging marks a voxel occupied when any contributing map observes it. Set union is idempotent, commutative, and associative, making repeated merges predictable. It relies on a common coordinate frame and does not resolve conflicting observations or pose uncertainty.

Ground robots plan on a 2D occupancy projection of the 3D map. This reduces planning cost but loses vertical structure. Frontier detection operates on that grid, while soft region preferences reduce duplicated exploration without making region boundaries impassable.

These choices are baselines with known limits. Probabilistic fusion, richer planning, and larger-team allocation become useful when experiments expose a limitation of the baseline.

## Keep local iteration inexpensive

Robots share a MuJoCo simulation and use in-process coordination messages. Local callbacks avoid a network transport where the current runtime does not require one. CPU-oriented defaults and optional backends keep the entry point accessible.

Slow perception runs separately from simulation updates. Per-robot workers prefer recent frames over processing an ever-growing backlog. Subprocess isolation limits failures from heavy or native-code backends. These boundaries trade completeness of frame processing for timely observations and runtime continuity.

## Make system behavior inspectable

The browser brings camera feeds, geometry, trajectories, controls, and metrics together. Cloud deltas reduce repeated transmission; full updates restore synchronization. A visual pipeline editor exposes composition and parameters while backend contracts define valid operations.

The same separation applies to robot platforms: shared orchestration handles goals and planar commands, while platform implementations own assets, actuator mappings, joint control, and failure state. This makes additional embodiments possible without embedding their assumptions throughout the coordinator.
