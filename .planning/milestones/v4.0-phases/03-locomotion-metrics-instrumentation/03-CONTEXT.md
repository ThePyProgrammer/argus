# Phase 3: locomotion-metrics-instrumentation - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Make locomotion behavior measurable across scenarios and controllers by computing command tracking, stability, action-quality, and terrain/contact metrics from `ArgusGo2Env`/MuJoCo state. Metrics must be available per step and per episode without coupling metric logic to the analytical trot controller. Phase 3 does not implement the Phase 4 CLI runner/export pipeline, new controller families, RL/MPC/WBC, ROS/hardware deployment, or frontend visualization.

</domain>

<decisions>
## Implementation Decisions

### Metric Surfaces
- **D-01:** Use a hybrid metrics surface: the environment owns or reuses a locomotion metrics collector, emits compact per-step metrics through Gymnasium `info`, and exposes episode-level aggregates for Phase 4 to export.
- **D-02:** Per-step `info` must use a nested `info["locomotion_metrics"]` payload grouped by metric family: command tracking, stability, action quality, and contact/terrain proxies. Do not scatter metric keys across top-level `info`.
- **D-03:** `reset()` starts a fresh episode metric buffer while preserving any explicit baseline/reference snapshot, matching the existing metrics-tracker pattern where baseline comparisons survive ordinary state resets.
- **D-04:** Phase 3 must define both per-step metric records and episode summaries now; Phase 4 should consume/export these definitions instead of redefining aggregation semantics.

### Failure Thresholds and Success Semantics
- **D-05:** Use a conservative locomotion failure gate: excessive roll/pitch, base height below threshold, or no meaningful progress/recovery after disturbance should count as failure.
- **D-06:** Failure thresholds should terminate the Gymnasium episode immediately by returning `terminated=True`, so distance-before-failure and failure counts are unambiguous.
- **D-07:** Scenario success rate in Phase 3 means surviving until episode truncation/max steps without triggering a failure threshold. Distance traveled and command-tracking quality remain separate metrics, not part of the success boolean.
- **D-08:** Roll, pitch, base-height, progress, and tolerance thresholds must live in configurable defaults through a metrics config/dataclass and be overridable through environment configuration. Do not hardcode them as unchangeable module constants.

### Contact and Terrain Proxies
- **D-09:** Contact metrics require an explicit validated Go2 foot/body/site/geom mapping. The planner should treat missing or ambiguous foot mapping as a clear implementation/test failure, not silently degrade to best-effort heuristics.
- **D-10:** Foot slip must be reported as per-foot world-frame XY velocity while the foot is in contact, plus aggregate slip summaries for the episode.
- **D-11:** Foot clearance must use swing-phase minimum and maximum clearance relative to a terrain/floor estimate, with per-foot records and episode aggregates.
- **D-12:** Contact timing must expose per-foot contact phase/boolean history, duty factor per foot, and aggregate gait symmetry/timing summaries at the episode level.

### Action Quality Metrics
- **D-13:** Action smoothness must include both per-step action delta norm and a second-difference/jerk proxy over 12-joint position targets, with per-step values and episode aggregates.
- **D-14:** Effort/energy must be implemented as a position-servo effort proxy using control-target movement, joint velocity, and optionally actuator control magnitude. It must be labeled as a non-torque proxy, not physical torque energy.
- **D-15:** Joint-limit violations must count both commanded targets outside configured joint limits and observed joint state (`qpos`) outside limits/tolerance, grouped per joint and summarized per episode.
- **D-16:** Actuator saturation must be interpreted as a near-limit position-servo proxy: targets near joint/action bounds and repeated clipping count toward saturation, clearly labeled as a proxy rather than torque actuator saturation.

### Claude's Discretion
- Exact module names and dataclass field names are open, but planning should prefer the existing local style: `src.*` absolute imports, dataclass configs, collector objects with bounded histories, and focused pytest coverage.
- The planner may choose the exact numeric default thresholds for roll/pitch/base-height/progress/saturation after code/research review, provided they are configurable and documented in tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 3 — Defines locomotion-metrics-instrumentation goal, dependencies, and success criteria.
- `.planning/REQUIREMENTS.md` §LOC-METRICS — Defines LOC-METRICS-01 through LOC-METRICS-04 for command tracking, stability, control quality, and contact/terrain proxies.
- `.planning/PROJECT.md` §Current Milestone / Key Decisions — Locks benchmark-before-controller-sophistication, metrics-first evaluation, analytical baseline, and CLI/docs-first benchmark scope.
- `.planning/STATE.md` §Accumulated Context / Blockers — Captures current v4.0 state and concerns around deterministic reset, position actuators, and contact/foot identity mapping.

### Prior phase dependency
- `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md` — Locks controller protocol, controller metadata surface, bridge/env seam, and future-controller deferrals that metrics must respect.
- `.planning/phases/01-locomotion-env-contract/01-PATTERNS.md` — Defines existing `ArgusGo2Env`, scenario, action-mode, observation, lifecycle, and MuJoCo test patterns.
- `.planning/phases/02-controller-plugin-baseline/02-PATTERNS.md` — Defines controller registry/dispatch, `ArgusGo2Env` metadata, bridge preservation, and target-validation patterns.

### Architecture decisions and rationale
- `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` — ADR for reproducible Gymnasium harness, named scenarios, metadata, and per-step/per-episode metrics expectations.
- `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` — ADR requiring metrics and regression infrastructure before RL/MPC/WBC/controller-family work.
- `outputs/locomotion-rd-systems.md` — Research rationale for current analytical trot + MuJoCo position-servo baseline and deferred advanced controllers.
- `outputs/locomotion-rd-systems.provenance.md` — Provenance for the locomotion R&D report.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/locomotion/env.py` — `ArgusGo2Env` already owns Gymnasium reset/step, scenario sample, command schedule, controller metadata, MuJoCo data/model handles, and `info`; metrics should integrate here without moving controller or MuJoCo ownership into controllers.
- `src/locomotion/observations.py` — Existing observation extraction provides `qpos`, `qvel`, command, and previous action arrays for command tracking, stability, smoothness, and joint-state metrics.
- `src/locomotion/controller_dispatch.py` — Existing dispatch validates 12-joint controller targets before writing to `data.ctrl`; action-quality metrics should use this validated target/control path.
- `src/locomotion/controllers.py` — Controller metadata and `ControllerResult` provide attribution context; metrics must remain controller-agnostic and use controller id/metadata only for attribution.
- `src/metrics/metrics_tracker.py` and `src/metrics/detection_metrics_tracker.py` — Existing collector patterns use per-robot state, bounded histories, reset methods, stats payloads, and baseline/GT-state separation.
- `src/metrics/ground_truth.py` and `src/metrics/mujoco_gt.py` — Existing ground-truth extraction patterns show how MuJoCo state can feed metric collectors and how to fail fast on malformed mappings.
- `src/bridge/sensor_types.py` — Quaternion conversion and `SensorFrame` ground-truth pose conventions can inform roll/pitch/base-motion derivation and future bridge-side reuse.

### Established Patterns
- Use collector classes for metrics instead of spreading history/aggregation logic through the environment.
- Keep Gymnasium `info` compact and structured; reset/episode info can include fuller metadata, while per-step info should be stable and loggable.
- Validate names, shapes, finite values, and mapping assumptions at boundaries before mutating MuJoCo state or recording benchmark metrics.
- Preserve existing non-Gym bridge behavior; metrics instrumentation should primarily target the benchmark environment and reusable collectors, not rewrite bridge public APIs.
- Current actuators are position-servo based; effort and saturation metrics must be explicitly labeled as proxies, not torque-control measurements.

### Integration Points
- `ArgusGo2Env.reset()` should initialize/reset the episode metric collector after scenario/controller reset and before first metric-bearing step.
- `ArgusGo2Env.step()` should record desired command, measured base motion, validated action target, previous action history, MuJoCo state/contact data, failure status, and compact `info["locomotion_metrics"]`.
- Failure thresholds should affect the existing Gymnasium five-tuple by setting `terminated=True`; max episode steps continue to use `truncated=True`.
- Phase 4 evaluation runner should consume the Phase 3 collector's per-step records and episode summary rather than duplicating metric calculations.

</code_context>

<specifics>
## Specific Ideas

- User selected the hybrid collector-plus-info surface, not collector-only or info-only.
- User selected conservative failure thresholds that terminate episodes immediately.
- User selected strict contact/foot mapping; contact metrics should not quietly fall back to fuzzy name heuristics.
- User selected position-servo-specific action-quality proxies and wants them labeled as proxies rather than physical torque/energy metrics.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-locomotion-metrics-instrumentation*
*Context gathered: 2026-04-30*
