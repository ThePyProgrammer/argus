# Argus Build Strategy: Scaling Into a Robotics R&D Workbench

## Thesis

Argus should be built as a **local robotics R&D workbench**, not as a simulator clone, model hub clone, or hardware deployment stack. Its job is to make robotics experiments observable, reproducible, comparable, and eventually portable.

The product wedge is not “run robots.” Plenty of tools do that. The wedge is:

> Argus turns robot behavior into typed research artifacts: scenarios, platforms, policies, datasets, episodes, runs, metrics, pipeline graphs, and provenance.

If Argus keeps that center of gravity, it can scale without becoming a pile of robotics demos.

## What Argus Should Become

Argus should become the place where a robotics researcher can:

1. choose a robot platform and scenario;
2. configure perception, SLAM, coordination, locomotion, and policy components;
3. run controlled simulations across seeds and scenarios;
4. record episodes and evaluation artifacts;
5. compare policies and backends honestly;
6. inspect failures visually in the browser;
7. export datasets or policy-evaluation artifacts to external ecosystems;
8. later, train policies or deploy to hardware through guarded adapters.

This is closer to a robotics lab notebook plus experiment bench than to a pure runtime.

## Build Principles

### 1. Artifacts first, algorithms second

Every serious capability should produce or consume a typed artifact. If a feature cannot say what artifact it creates, reads, compares, or validates, it probably does not belong in the core roadmap yet.

Core artifacts should include:

- `RobotPlatform`
- `Scenario`
- `PipelineGraph`
- `Episode`
- `DatasetRef`
- `PolicyRef`
- `EvalRun`
- `MetricSet`
- `ArtifactManifest`

This is the foundation for reproducibility and interoperability.

### 2. Evaluation before training

Do not rush into RL/VLA training. Training is expensive, slow, dependency-heavy, and easy to make impressive but scientifically weak.

Argus should first become excellent at answering:

- What did this policy do?
- Under which scenario, seed, robot, and pipeline?
- What failed?
- Was it better than the baseline?
- Can I replay and inspect the evidence?

Only after that should Argus grow training adapters.

### 3. Local-first, CPU-first defaults

Argus’s current strength is fast local iteration. Preserve that.

GPU-heavy policies, Isaac Lab, LeRobot training, VLA inference, and ROS/hardware bridges can exist later as optional adapters. They should not become assumptions in the main path.

Default Argus should remain usable without cloud services, unpinned downloads, or a GPU-only stack.

### 4. Registries over switch statements

Argus already benefits from small Protocols and registries. Keep extending that pattern, but do not inflate existing protocols.

Add new small registries when concepts are genuinely different:

- perception backend registry;
- SLAM backend registry;
- merge strategy registry;
- controller registry;
- future policy registry;
- future dataset adapter registry;
- future evaluator registry;
- future simulator adapter registry.

Do not turn one mega-plugin interface into a junk drawer.

### 5. Browser as observability surface, not robotics authority

The browser should make experiments understandable. It should not own robotics math, metric semantics, projection geometry, policy compatibility, or dataset schemas.

The backend owns robotics truth. The frontend renders and operates it.

### 6. Provenance is a feature

Every run should know:

- git commit;
- command invocation;
- scenario and seed;
- robot platform and platform metadata;
- active pipeline graph;
- backend IDs and versions;
- model/policy artifact revisions;
- dataset source and revision;
- metric definitions;
- environment/package versions where relevant.

A result without provenance is a demo, not research.

### 7. Hardware is a new safety boundary

ROS 2, MoveIt, and real robots should come later and require explicit architecture work. They should not sneak in through a generic adapter.

A policy that controls simulated motion is already riskier than a detector. A policy that controls hardware changes the entire trust model.

## Capability Roadmap

### Layer 0: Architecture governance

Purpose: keep the system from drifting as robotics scope expands.

Capabilities:

- ADR for Argus as a policy/data/evaluation workbench.
- Versioned contracts for `Episode`, `DatasetRef`, `PolicyRef`, `EvalRun`, and `RobotPlatform` metadata.
- Explicit boundaries for simulation, evaluation, training, and deployment.
- Rules for pinned external artifacts and license/provenance metadata.

Exit criteria:

- New robotics capabilities have a named artifact contract.
- The architecture says what is still out of scope.
- No training or hardware feature can bypass the evaluation/provenance layer.

### Layer 1: EvalRun and run browser

Purpose: make existing benchmark output a first-class product surface.

Capabilities:

- Stable `EvalRun` manifest contract.
- Backend route for discovering runs.
- Backend route for loading summaries and comparison artifacts.
- Browser run list and detail view.
- Scenario/seed matrix comparison.
- Links to JSONL/CSV/summary/comparison artifacts.
- Baseline regression markers.

Why this comes first:

Argus already emits evaluation artifacts. Turning them into a stable API and UI gives immediate R&D value without adding new robotics complexity.

### Layer 2: Episode and dataset layer

Purpose: make robot experience reusable.

Capabilities:

- Versioned `Episode` schema.
- Simulation rollout recorder.
- Per-step state/action/observation records.
- RGB/depth media references.
- Multi-robot episode metadata.
- Scenario, seed, platform, controller, perception pipeline, and map provenance.
- Argus-native dataset layout.
- Tiny sample datasets for tests.

Why this matters:

This is the bridge from “Argus runs simulations” to “Argus produces reusable robotics data.” It is also the prerequisite for LeRobot-style interoperability.

### Layer 3: Policy registry and evaluation-only policy support

Purpose: make learned policies swappable and inspectable.

Capabilities:

- `PolicyProtocol` with load, warmup, reset, infer, and close lifecycle.
- `PolicyRegistry` parallel to controller/perception registries.
- `PolicyRef` metadata with observation schema, action schema, robot compatibility, runtime backend, checkpoint revision, control rate, command bounds, and safety behavior.
- Compatibility validation before execution.
- Policy evaluation through existing locomotion scenario matrices.
- Analytical baseline comparison.

Important constraint:

Start with evaluation-only local policies. Do not build native training yet.

### Layer 4: Policy/data workbench UI

Purpose: make artifacts visible and comparable in the browser.

Capabilities:

- Run browser.
- Policy detail view.
- Dataset/episode detail view.
- Per-step trace viewer.
- Video or frame replay where available.
- Metric overlays.
- Failure summaries.
- Comparison cards for baseline vs policy.

Product goal:

A user should be able to answer “why did this policy fail?” without reading raw JSONL first.

### Layer 5: Pipeline graph evolves into experiment graph

Purpose: extend the existing React Flow pipeline editor without turning it into a generic workflow engine.

Capabilities:

- Dataset recorder node.
- Episode replay node.
- Policy node.
- Safety filter node.
- Evaluator node.
- Artifact exporter node.
- Explicit lifecycle tags: live, restart-required, offline-only, replay-only.

Guardrail:

Only add graph nodes backed by real Argus runtime concepts. Do not build a visual programming toy.

### Layer 6: Hugging Face / LeRobot interoperability

Purpose: connect Argus to the emerging robotics artifact ecosystem.

Capabilities:

- Pinned Hugging Face artifact resolver.
- `repo_id@revision` support.
- Local immutable artifact cache.
- License, source, hash, and expected-file manifests.
- LeRobot-compatible export from Argus episodes where feasible.
- LeRobot import/replay after Argus-native episode schema stabilizes.
- Optional model/dataset card generation.

Why after internal schemas:

Adapters are only clean when the internal contracts are stable. Otherwise Argus will inherit every external schema change as local architecture churn.

### Layer 7: External training adapters

Purpose: let Argus produce policies through external training systems without making training the core runtime.

Capabilities:

- Job wrapper abstraction.
- LeRobot training adapter.
- TorchRL/skrl/SB3 adapters where useful.
- Dataset-to-policy lineage tracking.
- Training output promoted into `PolicyRef` artifacts.
- Promotion gates against fixed evaluation matrices.

Guardrail:

Training jobs should run outside the live simulation loop and write artifacts back into Argus. The simulation runtime should not become a training framework.

### Layer 8: Simulator and benchmark adapters

Purpose: broaden benchmark coverage after artifacts are stable.

Capabilities:

- Gymnasium adapter generalization.
- ManiSkill adapter for manipulation benchmarks.
- RoboSuite/RoboMimic adapter for imitation-learning datasets and baselines.
- Isaac Lab adapter as optional GPU/NVIDIA path.
- Gazebo adapter for ROS-adjacent simulation tests.
- Benchmark registry with capability tags.

Guardrail:

Adapters must map into Argus artifacts. They should not redefine what a run, episode, policy, or platform means.

### Layer 9: Guarded deployment and hardware

Purpose: move toward real robots only after simulation evaluation is credible.

Capabilities:

- ROS 2 adapter.
- MoveIt adapter where relevant.
- Hardware platform metadata.
- Command bounds.
- Deadman switch semantics.
- Dry-run mode.
- Deployment logs.
- Sim-before-hardware promotion gates.

Required before starting:

A fresh ADR. Hardware is not just another backend.

## Recommended Milestone Sequence

### Milestone A: Research artifact foundation

Build:

- `EvalRun` contract;
- run discovery API;
- browser run browser;
- stable comparison summaries;
- provenance expansion for existing locomotion evaluations.

This is the highest-leverage next milestone because it converts existing v4.0 work into a visible R&D product surface.

### Milestone B: Episode recording

Build:

- `Episode` schema;
- simulation rollout recorder;
- Argus-native dataset layout;
- tiny sample dataset fixtures;
- export metadata for robot/platform/scenario/pipeline provenance.

This makes Argus a data-producing workbench.

### Milestone C: Policy evaluation

Build:

- `PolicyRef` schema;
- `PolicyProtocol`;
- policy registry;
- local policy artifact loading;
- compatibility checks;
- evaluation through locomotion scenarios.

This makes Argus a policy evaluation bench without pretending to be a training stack.

### Milestone D: Workbench UI expansion

Build:

- policy/run/dataset detail views;
- replay and trace surfaces;
- metric comparison cards;
- failure inspection workflow.

This turns artifacts into product value.

### Milestone E: LeRobot bridge

Build:

- pinned Hub artifact resolver;
- LeRobot-compatible export;
- import/replay path;
- model/dataset card metadata where useful.

This makes Argus part of the broader robotics ecosystem without surrendering its local-first discipline.

### Milestone F: External training adapters

Build:

- training job wrappers;
- LeRobot/TorchRL/SB3 integration;
- dataset-to-policy lineage;
- promotion gates.

This comes only after Argus can judge policies well.

### Milestone G: Simulator and hardware expansion

Build:

- optional simulator adapters;
- ROS/hardware architecture;
- guarded deployment path.

This comes last because it has the largest blast radius.

## What Not To Build Yet

Do not make these the next core milestone:

- native RL training;
- large VLA inference as default path;
- ROS 2 hardware control;
- Isaac Lab as a hard dependency;
- generic visual workflow automation;
- cloud-hosted experiment management;
- unpinned Hugging Face downloads at runtime;
- frontend-owned robotics math;
- simulator adapter sprawl before artifact contracts exist.

These can all be useful later. Built too early, they will turn Argus into an integration swamp.

## The Near-Term Bet

The best next bet is:

> **Argus Research Artifact Foundation:** stabilize run manifests, expose them in the browser, and define the episode/policy/data contracts that future robotics AI work will use.

That milestone is not as flashy as training a policy. It is more important. It turns Argus from a capable robotics simulation app into a system that can accumulate research value over time.

## Success Metrics

Argus is scaling correctly if:

- every experimental claim links to a run artifact;
- every run has scenario, seed, platform, backend, model, and git provenance;
- policies cannot run unless their observation/action/platform contracts validate;
- datasets can be replayed or inspected without guessing their schema;
- the browser can explain failures better than raw logs;
- external tools integrate through adapters, not by invading core runtime assumptions;
- new research directions add artifacts and evaluators before they add demos.

Argus is drifting if:

- results are only screenshots or videos;
- policies are just Python scripts with hidden assumptions;
- training jobs produce checkpoints without evaluation lineage;
- frontend code starts owning robotics geometry;
- GPU/cloud dependencies become required for the default path;
- hardware control arrives before safety/provenance boundaries.

## Bottom Line

Build Argus like an R&D instrument, not a demo platform.

The enduring architecture is not “MuJoCo plus web UI.” It is:

```text
robot platform + scenario + pipeline + policy + episode + metrics + provenance = comparable robotics evidence
```

If every future capability strengthens that equation, Argus can grow into a serious robotics R&D system without losing its current clarity.
