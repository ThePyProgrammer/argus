# ICP pose-chain support — scoped Issue #9 fix

November 26, 2026. This follows the
[executable-route validation](exploration-executable-routes-validation.md).

## Frozen scope and acceptance criteria

The preserved clutter-102 route attempt reaches 89.816 mm peak planar error
for A while raw registration remains accepted. Its alignment rank falls from
six to five before the large error. Registration acceptance is therefore not
sufficient evidence for navigation or continued global-map insertion.

`icp_observability_chain_v1` adds a necessary numerical support check. It is
**not a pose accuracy bound**, calibrated covariance, or complete resolution
of Issue #9. The existing solver's six-direction rank threshold is unchanged.
Full-rank drift, accumulated placement error, and range-dependent effects of
attitude uncertainty still require a calibrated uncertainty treatment.

The backend publishes `pose_map_support` separately from `accepted` and raw
tracking status. States are `seeded`, `observable`, `unavailable`, `invalid`,
`unobservable_motion`, and `unobservable_history`. Rank is a dimensionless
integer; observation and first-loss times are simulation seconds. Translation,
attitude, and historical-map bounds are explicitly unavailable (`null`), with
field names specifying metres and radians. Freshness uses the existing
`motion_observation_max_age_s`; no clearance radius or margin changes.

The explicit initial pose permits the first map seed. Accepted relative motion
with fewer than six supported directions permanently invalidates the chain.
A later full-rank relative alignment cannot restore the missing history.
Rejected registration retains the old reference and can recover through a
later supported match. Missing, malformed, or stale support blocks motion and
map insertion. The consumer retains history loss across backend resets and new
waypoint targets: restart localization and the map together to recover.

Only ICP currently declares this contract. Other backends retain their existing
behavior and are outside this fix. Raw ICP diagnostics remain available after
support loss; new points are withheld from both its global cloud and the
exploration occupancy/floor pipeline. The execution guard issues a stop, and
navigation reports `pose_history_unobservable`. An unaffected teammate may
continue. Ground truth remains diagnostic-only.

Before fresh live outcomes, acceptance is fixed as follows:

- Analytical wall-parallel motion must remain accepted by raw registration
  while failing numerical support, with no subsequent map insertion. A later
  full-rank increment must not repair the history. Missing/stale support and
  backend-only reset must not bypass the navigation consumer.
- Reproduce cluttered_room seed 102 for a 16-second requested horizon, with
  scan recording. Compare against preserved `executable-routes/clutter-s102-live-02`:
  commands must match until the first unsupported update, then the affected
  robot must stop and withhold scans. Report actual duration, coverage cost,
  contacts, falls, and pose/retained-map diagnostics, including residual errors.
- Run connected_rooms seed 101 for 5 seconds and cluttered_room seed 101 for
  16 seconds as regression cases. These are previously seen development cases,
  **not held-out accuracy calibration**. Report any conservative stop explicitly.
- Preserve every attempt and its verified top-view video, including early
  navigation failures. No parameter retuning between these attempts.

The complete uncertainty budget and broader held-out/long-horizon evaluation
remain open under Issues #9 and #11 respectively.
