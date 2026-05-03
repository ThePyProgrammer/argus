# Phase 2: controller-plugin-baseline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 02-controller-plugin-baseline
**Areas discussed:** Protocol shape, Registry semantics, Bridge alignment, Metadata surface

---

## Protocol Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Pure action mapper | Controller gets observation, command, and dt, then returns a validated 12-joint target plus metadata. Keeps MuJoCo stepping and env action decoding outside controllers. | ✓ |
| Mode-aware mapper | Controller gets observation, command, dt, and action mode, then may return velocity, residual, or joint targets. More flexible, but muddies the protocol boundary. | |
| Bridge-context controller | Controller gets richer bridge/env context and can inspect simulator handles. Most powerful, but couples future controllers to MuJoCo internals. | |

**User's choice:** "you decide I guess" — Claude selected pure action mapper.
**Notes:** User explicitly selected stateful per-robot controller instances and a typed command object for velocity/command input.

---

## Controller State

| Option | Description | Selected |
|--------|-------------|----------|
| Stateful per robot | Each robot/env has its own controller instance with reset(seed=None), so TrotGaitController phase state is isolated and deterministic. | ✓ |
| Stateless function | All state lives outside the controller and is passed in every call. More explicit, but awkward for gait phase and future policy hidden state. | |
| Shared singleton | One controller instance shared globally. Minimal code, but unsafe for multi-robot and seeded reset behavior. | |

**User's choice:** Stateful per robot.
**Notes:** This matches current `MultiRobotBridge` behavior with one `TrotGaitController` per robot.

---

## Command Representation

| Option | Description | Selected |
|--------|-------------|----------|
| Typed command object | A small dataclass with vx, vy, yaw_rate, optional metadata. Clear names, easy tests, less shape confusion. | ✓ |
| Raw 3-vector | Use np.ndarray([vx, vy, yaw_rate]). Minimal and fast, but less self-documenting and easier to misuse. | |
| Observation-embedded | Put command inside the observation dict only. Fewer args, but makes command tracking and metadata less explicit. | |

**User's choice:** Typed command object.
**Notes:** Downstream planner should use an explicit command object/dataclass boundary.

---

## Registry Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Perception-style | Named registry with display, capabilities, parameter schema, available() probe, and explicit unavailable reasons. Fits placeholder controllers. | ✓ |
| SLAM-style | Simple named registry with default, list, create, and lazy class loading. Less code, but weaker placeholder/unavailable semantics. | |
| Static catalog | Hard-code controller entries in a dict. Fastest to implement, but less plugin-like for future controller families. | |

**User's choice:** Perception-style.
**Notes:** Placeholder controllers should be discoverable with explicit availability state.

---

## Capability Metadata

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal family contract | family, action_mode, requires_training, requires_model_path, supports_multi_robot, and deterministic. Enough for evaluation and placeholders without over-specifying. | |
| Full benchmark contract | Add observation schema expectations, command limits, parameter schema, CPU latency hint, and sim-only/hardware flags. Richer but may front-load too much design. | ✓ |
| Just id/family | Only controller id, display name, and family. Lowest friction but evaluation/docs will need follow-up decisions. | |

**User's choice:** Full benchmark contract.
**Notes:** CONTEXT.md expands this to full benchmark capability metadata required for planning.

---

## Placeholder Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| List but fail on create | residual/direct/MPC/WBC appear in list_backends with available=false and a precise reason; create() raises a clear unavailable error. | ✓ |
| Hide unavailable | Only show implemented controllers. Cleaner UI/CLI today, but weakens the explicit support matrix and future seams. | |
| Create stub object | Allow construction but raise when compute() is called. Easy placeholders, but violates the requirement to fail at selection time. | |

**User's choice:** List but fail on create.
**Notes:** This satisfies the roadmap requirement that unavailable implementations fail at selection time, not mid-run.

---

## Bridge Alignment

| Option | Description | Selected |
|--------|-------------|----------|
| Control boundary only | Replace direct TrotGaitController calls with controller instances, preserve public bridge lifecycles and return types. | |
| Add selection API | Also add bridge-level set_controller/select_controller APIs. More discoverable, but expands bridge API and may overlap with env/evaluation config. | |
| Refactor bridge loop | Move bridge stepping around controller abstractions more broadly. Cleaner architecture later, but higher risk to C2 runtime now. | ✓ |

**User's choice:** Refactor bridge loop.
**Notes:** Because this was high-blast-radius, a follow-up narrowed the implementation boundary.

---

## Bridge Refactor Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Shared control loop | Extract a shared controller dispatch/control-target application helper used by ArgusGo2Env, MuJoCoBridge, and MultiRobotBridge, while preserving their public APIs. | ✓ |
| Unified bridge base | Create a common base class for single/multi env stepping. Stronger refactor, but risks forcing unlike return types into one hierarchy. | |
| New runner layer | Introduce a separate locomotion runner object that owns controller selection and stepping. Cleaner for evaluation, but more new architecture. | |

**User's choice:** Shared control loop.
**Notes:** This keeps the user's bridge-loop refactor intent while avoiding a public bridge API rewrite.

---

## Existing C2 Controller Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Baseline only in C2 | Existing C2 bridges use the registered analytical baseline through the new seam, but no new UI/CLI selection for C2 yet. | ✓ |
| Config selection | Allow config/env var selection for C2 bridges. Useful for smoke tests, but unavailable placeholders need careful errors. | |
| Full selection path | Expose controller choice all the way to user-facing C2 controls. Likely scope creep for this phase. | |

**User's choice:** Baseline only in C2.
**Notes:** User-facing C2 controller selection is deferred.

---

## Metadata Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Benchmark metadata | controller_id, display name, family, action_mode, deterministic flag, parameter hash/config, and availability/capability summary. | ✓ |
| Minimal metadata | Only controller_id and action_mode. Enough for Phase 2 success criteria, but less useful for Phase 4 reproducibility. | |
| Full registry entry | Copy the entire registry listing into info. Complete, but noisy and risks bloating per-step info. | |

**User's choice:** Benchmark metadata.
**Notes:** Metadata should support Phase 4 reproducibility without copying full registry entries per step.

---

## Metadata Frequency

| Option | Description | Selected |
|--------|-------------|----------|
| Reset plus changes | Include full controller metadata in reset/episode info and whenever controller selection changes; per-step info carries only controller_id/action_mode. | ✓ |
| Every step full | Emit full benchmark metadata on every step. Simple for consumers, but noisy for JSONL and future metrics. | |
| Episode only | Emit only at reset/summary. Compact, but less robust for downstream per-step artifacts. | |

**User's choice:** Reset plus changes.
**Notes:** Compact per-step attribution is still required.

---

## Claude's Discretion

- Protocol shape was delegated to Claude; Claude selected the pure action-mapper seam based on codebase evidence and prior phase boundaries.
- Exact module/class naming and whether metadata is returned directly or wrapped in a result object remain planner discretion.

## Deferred Ideas

- User-facing C2 controller selection — future phase or later enhancement.
- Implementing residual RL, direct RL, MPC, WBC, ROS/hardware control, or perception-conditioned locomotion — out of scope for v4.0 Phase 2.
