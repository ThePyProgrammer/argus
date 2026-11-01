# ADR-0020: Evaluate Exploration Against a Fixed Reference Area

| Field | Value |
| --- | --- |
| Status | Proposed |
| Date | 2026-11-01 |
| Category | Testing Strategy |
| Consulted | Exploration evaluation execution plan, current coverage tracker, Go2 platform metadata |
| Informed | Exploration, coordination, and evaluation contributors |
| Related | ADR-0003, ADR-0012, ADR-0018, ADR-0019 |

## Context

The existing exploration tracker reports frontier exhaustion and occupied-volume density. Those values are useful diagnostics but do not measure the fraction of an environment observed. A planner can exhaust its frontiers while leaving large areas unseen.

The planned study compares two robots using independent frontier selection, Voronoi bias, and joint assignment. Evaluation must not change its denominator or initial conditions in response to a method's performance.

## Options Considered

1. Continue using frontier exhaustion as coverage. This can reward failed discovery.
2. Measure visited robot positions. This measures traversal rather than camera observation.
3. Measure visible floor against a fixed reference region. This separates observation from planner state, with a narrower physical interpretation than full 3D mapping quality.

## Decision

Use cumulative visible reachable floor coverage against a finite, fixed reference grid. The reference component is selected by a scenario anchor before sampling spawns. All accepted spawn configurations must lie in that component. Its origin, resolution, area, geometry assumptions, and hashes are part of experiment provenance.

The first fixtures contain static, axis-aligned boxes only. Their analytical reference masks use a world-aligned square with half extent 0.40 m and a 0.60 m vertical clearance envelope. The square contains the rotating Go2 body dimensions currently declared by the platform. It is deliberately conservative at obstacle corners; it does not establish dynamic traversability or actual leg clearance. Unsupported geometry must be rejected rather than approximated silently.

The fixture validator compiles MJCF and checks every collision box against separately stored analytical bounds. It also verifies a common connected reference component, clear and non-overlapping spawn envelopes, and deterministic sampling of locations and headings. The future general reference extractor must be tested against these fixtures independently.

Coverage will be collected from camera observations using capture-time geometry. Reference masks, hidden obstacle data, and oracle coverage gradients must not reach planning. The current simulator-assisted pose assumptions remain in place and must be disclosed.

Use normalized coverage AUC over a fixed simulated-time horizon as the primary endpoint. Threshold success, threshold time, travel, duplicate observation, safety, and resource cost are secondary outputs. Algorithm failures remain in the evaluation. After terminal algorithm failure, freeze observed area for the remainder of the horizon. Retain infrastructure failures and linked retries in the attempt log.

The initial 300-second horizon, 90% threshold, sensor settings, and 0.10 m grid are development defaults. They are not a frozen study protocol. Choose the final operating points on pilot seeds before evaluating unseen initial conditions.

## Consequences

- Coverage has a denominator independent of frontier detection, map density, and episode outcomes.
- A separate measurement path makes accidental use of hidden geometry testable.
- Visible floor coverage does not measure full 3D reconstruction, map correctness, or hardware robustness.
- Static bounded fixtures omit moving objects and general mesh geometry. The first results must retain that scope.
- Existing dashboard metrics keep their current semantics. This decision does not relabel those metrics as observed-area coverage.
- The fixture contract is implemented first; the observation collector and batch evaluator remain follow-up work.

## References

- [Execution plan](../plans/exploration-evaluation.md)
- [Fixture definitions and analytical areas](../../data/benchmarks/exploration/README.md)
- [Scenario contracts](../../src/exploration/evaluation/scenarios.py)
- [Existing coverage tracker](../../src/exploration/coverage_tracker.py)
- [Go2 platform](../../src/bridge/platforms/go2.py)
