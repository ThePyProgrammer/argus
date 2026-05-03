# Phase 2: controller-plugin-baseline - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Put locomotion controllers behind a common protocol and registry so the existing analytical trot becomes the default benchmark comparator, future residual/direct/MPC/WBC controller families have explicit unavailable extension seams, and single-robot plus multi-robot control paths share controller dispatch where practical. This phase does not implement RL policies, MPC, WBC, ROS/hardware deployment, or frontend controller selection.

</domain>

<decisions>
## Implementation Decisions

### Controller Protocol Shape
- **D-01:** Use a pure action-mapper protocol: controller instances receive an environment observation, a typed command object, and `dt`, then return a validated 12-element Go2 joint-position/action target plus controller metadata.
- **D-02:** Keep MuJoCo stepping, reset lifecycle, scenario handling, action decoding, and bridge/environment resource ownership outside the controller protocol.
- **D-03:** Controllers are stateful per robot/environment instance and expose reset behavior, so gait phase state and future policy hidden state are isolated per robot and can be reset deterministically.
- **D-04:** Represent velocity commands with a typed command object/dataclass carrying `vx`, `vy`, `yaw_rate`, and optional metadata instead of raw arrays or observation-embedded commands.

### Registry and Placeholder Semantics
- **D-05:** Use a perception-style registry for locomotion controllers: named entries, display names, default controller id, lazy loading, `available()` probing, capability metadata, parameter schemas, and explicit unavailable reasons.
- **D-06:** Every controller entry declares a full benchmark capability contract: family, action mode, deterministic flag, supported observation/command expectations, command limits, parameter schema, CPU latency hint, sim-only/hardware applicability, training/model-path requirements, multi-robot support, and relevant reproducibility metadata.
- **D-07:** Register residual policy, direct policy, MPC, and WBC as discoverable placeholder entries with `available=false` and precise reasons. Selecting/creating one fails immediately with a clear unavailable-controller error; placeholders must not construct objects that fail later in `compute()`.
- **D-08:** The analytical trot is the default registered baseline controller and delegates to existing `TrotGaitController.compute(vx, vy, omega, dt)` for behavior-equivalent 12-joint targets.

### Bridge and Environment Alignment
- **D-09:** Refactor the bridge loop only enough to extract a shared controller dispatch/control-target application helper used by `ArgusGo2Env`, `MuJoCoBridge`, and `MultiRobotBridge` where practical.
- **D-10:** Preserve existing public bridge lifecycles and return types: single-robot bridge still returns a `SensorFrame`, multi-robot bridge still returns `dict[str, SensorFrame]`, and existing C2/non-Gym runtime paths keep booting.
- **D-11:** Existing C2/non-Gym bridge paths use the registered analytical baseline through the new seam, but Phase 2 does not add user-facing C2 controller selection.
- **D-12:** Avoid evaluation-only controller dispatch branches; the shared seam should serve both benchmark environment usage and bridge runtime usage without duplicating control-loop logic.

### Controller Metadata Surface
- **D-13:** Emit benchmark controller metadata sufficient for future evaluation reproducibility: `controller_id`, display name, family, action mode, deterministic flag, parameter hash/config summary, and capability/availability summary.
- **D-14:** Include full controller metadata in reset/episode info and whenever controller selection changes. Per-step info should carry only compact fields such as `controller_id` and `action_mode` unless a change occurs.
- **D-15:** Controller selection metadata must be available to downstream metrics/evaluation artifacts so Phase 4 can attribute every action and episode to the controller that produced it.

### Claude's Discretion
- The exact class/module names are open, but planning should prefer the existing project style: absolute `src.*` imports, dataclass configuration objects, Protocol-style contracts, pytest unit tests, and registry tests modeled on SLAM/perception registries.
- The planner may decide whether metadata is returned directly from `compute()` or attached by a wrapper/result object, as long as the protocol remains a pure action-mapper and downstream `info` contains the required fields.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 2 — Defines controller-plugin-baseline goal, dependencies, success criteria, and out-of-scope controller families.
- `.planning/REQUIREMENTS.md` §LOC-CTRL — Defines LOC-CTRL-01 through LOC-CTRL-04 and v4.0 out-of-scope boundaries.
- `.planning/PROJECT.md` §Current Milestone / Key Decisions — Locks benchmark-before-sophistication, analytical trot baseline, future-controller seams, and CLI/docs-first benchmark scope.
- `.planning/STATE.md` §Accumulated Context — Captures locked v4.0 decisions and concerns around controller/action seams and MuJoCo position-actuator assumptions.

### Prior phase dependency
- `.planning/phases/01-locomotion-env-contract/01-RESEARCH.md` — Defines Phase 1 environment/action-mode assumptions that Phase 2 must integrate with.
- `.planning/phases/01-locomotion-env-contract/01-PATTERNS.md` — Maps existing locomotion, action, observation, and bridge patterns relevant to the controller seam.
- `.planning/phases/01-locomotion-env-contract/01-VALIDATION.md` — Provides current locomotion validation strategy and test commands that Phase 2 should extend.

### Architecture decisions and rationale
- `docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md` — Existing architectural decision for protocol/registry-based pluggable backends.
- `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` — ADR for the Gymnasium-style benchmark harness boundary.
- `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` — ADR for benchmarking analytical locomotion before implementing new controller families.
- `outputs/locomotion-rd-systems.md` — Research rationale describing current analytical trot + MuJoCo position-servo baseline and deferred RL/MPC/WBC scope.
- `outputs/locomotion-rd-systems.provenance.md` — Provenance for the locomotion R&D report.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/locomotion/gait_controller.py` — Existing `TrotGaitController.compute(vx, vy, omega, dt) -> np.ndarray` is the analytical baseline implementation to wrap, not rewrite.
- `src/locomotion/gait_params.py` — Existing gait parameter dataclass style can inform controller parameter schemas/config summaries.
- `src/bridge/sim_bridge.py` — Single-robot bridge already buffers velocity, converts via `TrotGaitController`, accepts optional direct 12-joint action, and writes to `data.ctrl`.
- `src/bridge/multi_bridge.py` — Multi-robot bridge already keeps one gait controller per robot and applies 12-joint controls through per-robot actuator indices.
- `src/bridge/sensor_types.py` — Existing `BridgeProtocol` documents the single-vs-multi bridge API distinction that Phase 2 must preserve.
- `src/slam/registry.py` and `src/perception/registry.py` — Registry patterns for named backend discovery, lazy class loading, defaults, capabilities, parameter schemas, availability, and explicit errors.
- `tests/locomotion/test_gait_controller.py`, `tests/slam/test_registry.py`, and `tests/perception/test_registry.py` — Test patterns for output shape, deterministic controller behavior, registry creation/listing, capability validation, and unavailable backend reporting.

### Established Patterns
- Use central registries for plugin-like backends rather than scattered conditionals.
- Use lazy imports/class paths in registries so optional heavy implementations do not load during registry import.
- Use per-instance state for runtime components; multi-robot bridge already maintains per-robot gait instances.
- Validate names, shapes, finite values, capabilities, and unavailable implementations at selection/creation boundaries.
- Preserve bridge public behavior when adding benchmark abstractions; existing web/C2 paths depend on current bridge lifecycle and return shapes.

### Integration Points
- Replace hard-coded `TrotGaitController()` usage in `MuJoCoBridge` and `MultiRobotBridge` with registered analytical baseline controller instances through a shared controller dispatch/control-target helper.
- Integrate with Phase 1 `ArgusGo2Env` action-mode and info surfaces so env/evaluation metadata can include controller identity and compact per-step attribution.
- Extend locomotion tests with controller protocol/registry tests and bridge equivalence tests showing analytical baseline output remains behavior-equivalent on flat-ground smoke paths.

</code_context>

<specifics>
## Specific Ideas

- User selected the higher-refactor bridge option, narrowed to a shared control-loop/controller-dispatch helper rather than a public bridge API rewrite.
- User selected full benchmark capability metadata, not a minimal id/family contract.
- User selected reset-plus-changes metadata emission: full metadata at reset/episode and controller-selection changes, compact controller id/action mode per step.

</specifics>

<deferred>
## Deferred Ideas

- User-facing C2 controller selection is deferred; Phase 2 keeps C2 on the registered analytical baseline through the new seam.
- Implementing residual RL, direct RL, MPC, WBC, ROS/hardware control, or perception-conditioned locomotion remains out of scope.

</deferred>

---

*Phase: 02-controller-plugin-baseline*
*Context gathered: 2026-04-30*
