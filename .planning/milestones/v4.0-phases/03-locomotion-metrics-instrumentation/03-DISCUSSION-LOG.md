# Phase 3: locomotion-metrics-instrumentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 03-locomotion-metrics-instrumentation
**Areas discussed:** Metric surfaces, Failure thresholds, Contact proxies, Action quality

---

## Metric Surfaces

### Exposure during `ArgusGo2Env.step()`

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid collector + info | Env owns/reuses a metrics collector, emits compact per-step metrics in `info`, and keeps episode aggregates for Phase 4 exports. | ✓ |
| Collector only | Cleaner `info`, but downstream callers must pull metrics from a separate object. | |
| Info only | Simple immediate consumption, but episode aggregation/export prep gets duplicated later. | |

**User's choice:** Hybrid collector + info
**Notes:** Locked as D-01.

### Per-step `info` shape

| Option | Description | Selected |
|--------|-------------|----------|
| Nested locomotion key | `info["locomotion_metrics"]` grouped by tracking, stability, action quality, and contact. | ✓ |
| Flat top-level keys | Simple for inspection but bloats `info` and risks collisions. | |
| Collector handle only | Minimal `info` but not self-contained per-step records. | |

**User's choice:** Nested locomotion key
**Notes:** Locked as D-02.

### Reset behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Episode reset, keep baseline | Clear current episode step buffers on reset, preserve explicit baseline/reference snapshots. | ✓ |
| Clear everything | Simpler but loses baseline/cross-episode diagnostics. | |
| Never reset automatically | Useful for continuous monitoring, bad for benchmark episodes. | |

**User's choice:** Episode reset, keep baseline
**Notes:** Locked as D-03.

### Aggregation scope

| Option | Description | Selected |
|--------|-------------|----------|
| Step + episode summary | Collector exposes both per-step records and episode summary; Phase 4 exports without redefining metric math. | ✓ |
| Raw steps only | Smaller Phase 3, but Phase 4 decides aggregation semantics later. | |
| Summary only | Smallest surface, but loses debugging and JSONL detail. | |

**User's choice:** Step + episode summary
**Notes:** Locked as D-04.

---

## Failure Thresholds

### Failure definition

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative fall gate | Terminate/fail on excessive roll/pitch, base height below threshold, or no meaningful progress after disturbance. | ✓ |
| Only hard falls | Fail only when base height/orientation clearly indicates a fall. | |
| Scenario-specific gates | Different thresholds per flat/slope/rough/push scenario. | |

**User's choice:** Conservative fall gate
**Notes:** Locked as D-05.

### Episode termination behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Terminate on failure | Set `terminated=True` when failure thresholds trip; Phase 4 can count failures and distance-before-failure cleanly. | ✓ |
| Mark only | Keep stepping and report failure flags in metrics. | |
| Configurable | Default terminate, but allow opt-out for debugging. | |

**User's choice:** Terminate on failure
**Notes:** Locked as D-06.

### Scenario success rate

| Option | Description | Selected |
|--------|-------------|----------|
| Survive full episode | Success means no failure before truncation/max episode, with distance and tracking stats reported separately. | ✓ |
| Scenario objective | Success depends on scenario-specific objectives like commanded distance or push recovery. | |
| Defer success rate | Let Phase 4 define success during evaluation aggregation. | |

**User's choice:** Survive full episode
**Notes:** Locked as D-07.

### Threshold configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable defaults | Project defaults live in a metrics config/dataclass, overridable through env config for benchmark tuning. | ✓ |
| Hardcoded constants | Simpler but threshold changes require code edits. | |
| Per-scenario defaults | Thresholds come from scenario specs. | |

**User's choice:** Configurable defaults
**Notes:** Locked as D-08.

---

## Contact Proxies

### Foot/contact mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Strict mapping required | Build/validate explicit Go2 foot body/site/geom mapping and fail tests clearly if mapping cannot be resolved. | ✓ |
| Best-effort mapping | Try name heuristics and emit unavailable metrics if mapping fails. | |
| Contact optional | Expose contact metrics only when mapping exists. | |

**User's choice:** Strict mapping required
**Notes:** Locked as D-09.

### Foot slip

| Option | Description | Selected |
|--------|-------------|----------|
| Contact-frame velocity | Measure foot world XY velocity while that foot is in contact, with per-foot and aggregate slip summaries. | ✓ |
| Displacement per contact | Track XY displacement from contact start to lift-off. | |
| Binary slip flag | Only report whether slip exceeded a threshold. | |

**User's choice:** Contact-frame velocity
**Notes:** Locked as D-10.

### Foot clearance

| Option | Description | Selected |
|--------|-------------|----------|
| Swing min/max height | Report per-foot swing-phase min/max clearance relative to terrain/floor estimate, with episode aggregates. | ✓ |
| Foot height only | Report raw foot z height each step. | |
| Threshold pass rate | Report percent of swing steps above a clearance threshold. | |

**User's choice:** Swing min/max height
**Notes:** Locked as D-11.

### Contact timing and duty factor

| Option | Description | Selected |
|--------|-------------|----------|
| Per-foot phases + aggregates | Per-foot contact boolean/timing history, duty factor per foot, and aggregate gait symmetry/timing episode summaries. | ✓ |
| Aggregate only | Only expose episode-level duty factor and contact timing summaries. | |
| Raw contacts only | Expose raw MuJoCo contact-derived flags and let Phase 4 aggregate. | |

**User's choice:** Per-foot phases + aggregates
**Notes:** Locked as D-12.

---

## Action Quality

### Smoothness

| Option | Description | Selected |
|--------|-------------|----------|
| Delta + jerk proxy | Track action delta norm per step and second-difference/jerk proxy, with per-step and episode aggregate values. | ✓ |
| Delta only | Measure change from previous 12-joint target only. | |
| Command smoothness | Measure high-level velocity command changes instead of joint-target changes. | |

**User's choice:** Delta + jerk proxy
**Notes:** Locked as D-13.

### Effort/energy proxy

| Option | Description | Selected |
|--------|-------------|----------|
| Position-servo proxy | Use control-target movement, joint velocity, and optionally actuator ctrl magnitude as an effort proxy, clearly labeled as non-torque energy. | ✓ |
| Ctrl magnitude only | Cheap but misleading if interpreted as physical energy. | |
| Defer effort metric | Avoid questionable energy claims until torque/dynamics data exists. | |

**User's choice:** Position-servo proxy
**Notes:** Locked as D-14.

### Joint-limit violations

| Option | Description | Selected |
|--------|-------------|----------|
| Target and state violations | Count commanded target outside configured joint limits and observed qpos outside limits/tolerance, grouped per joint and episode. | ✓ |
| Target only | Catches controller output issues before physics. | |
| State only | Measures actual robot state violations but may hide unsafe commands. | |

**User's choice:** Target and state violations
**Notes:** Locked as D-15.

### Actuator saturation proxy

| Option | Description | Selected |
|--------|-------------|----------|
| Near-limit proxy | Treat targets near joint/action bounds and repeated clipping as saturation proxy, clearly labeled as position-servo saturation. | ✓ |
| Ctrlrange only | Use MuJoCo actuator ctrlrange if present. | |
| Skip saturation | Avoid ambiguous metric now. | |

**User's choice:** Near-limit proxy
**Notes:** Locked as D-16.

---

## Claude's Discretion

- Exact module names and dataclass field names.
- Exact numeric default thresholds, subject to configurability and test coverage.

## Deferred Ideas

None — discussion stayed within phase scope.
