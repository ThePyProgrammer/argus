# Executable route selection — Issue #8

## Development contract, frozen before new live outcomes

The planner will compare forward and backward waypoint following using a
bounded nominal forecast on the observed map. Each forecast command uses the
existing clearance guard, including command response, unknown center cells,
and stopping tails. Prediction must not mutate live guard or runner history.
Every real command is checked again. Geometry, map observations, clearance
allowances, retry counts, and blockage deadlines remain unchanged.

Route acceptance requires 0.15 m of predicted translation within four seconds;
turning or standing drift cannot meet that threshold. This is a local ranking
heuristic, not a whole-route or physical dynamics guarantee. The nominal
forecast uses the shared gait yaw/restart filter and the guard's acceleration
parameter. Its hypothetical observation times assume the frozen map remains
available; the first check enforces actual observation freshness. Real commands
always use actual sensor times.

Search remains capped at 32 goals and two travel directions per goal. Recovery
compares at most four existing primitives, their predicted directed-progress
endpoints and standing intervals, and four goals per endpoint. It prefers a
predicted navigable endpoint. If none is found, a bounded admitted sensing
motion may still reveal free space; that is explicitly not a successful escape.
Only observed translation on an installed route resets the blockage budget.

The frozen clutter-101 terminal fixture preserves the observed map, estimated
body pose, radius, configuration, and source hash. Its stationary settled
history is hypothetical; it does not reconstruct the recorded gait history.
It must reject the original turning proposals and select a later executable
backward route. Analytical fixtures cover stale inputs, unknown space, preview
isolation and recovery followed by navigation; physical fixtures cover actual
commanded progress and stopped traps.

Fresh paired development attempts will use clutter seeds 101/102 with requested
16-second horizons and connected rooms seed 101 for a five-second regression.
Compare with the preserved pose/map matrix and bounded-recovery runs. An
improved recoverable case must have accepted navigation translation spanning
at least two seconds and at least 0.30 m of net route displacement after the
old policy's first blockage, positive coverage gain, zero non-foot contacts,
and zero falls. Report every early failure and remaining trap. These are
development criteria; broader long-horizon acceptance remains Issue #11.

Use `scripts/validate_exploration.py` with new directories, hold runtime sources
unchanged through video export, and link every attempt's verified video. Report
actual/requested duration, initial/final coverage, movement, recovery, contact
severity, pose/floor diagnostics, and unresolved clearance rejections.
