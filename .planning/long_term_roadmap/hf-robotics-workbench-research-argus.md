# Argus Fit Research: “HuggingFace/PyTorch for Robotics” as a Robotics Workbench Direction

Task: T4  
Date: 2026-05-08  
Scope: Inspect the current Argus repository first, then use external sources only where needed to compare against the emerging “HuggingFace/PyTorch for Robotics” direction. No implementation was attempted.

## Executive Summary

Argus is already closer to a robotics workbench than to a single robotics demo. The local evidence shows a simulation-native, browser-first, MuJoCo-based multi-robot system with registries for SLAM, perception, merge strategies, detection, lifting, tracking, robot platforms, and locomotion controllers; a React Flow pipeline editor; a Gymnasium-style locomotion benchmark harness; pinned model artifacts; and machine-readable evaluation outputs.

A “HuggingFace/PyTorch for Robotics” direction should not mean Argus tries to become a general global model hub. That lane is already occupied by Hugging Face LeRobot, the Hugging Face Hub, Open X-Embodiment/RT-X-style cross-robot datasets, Isaac Lab, ManiSkill, robosuite, robomimic, and PyTorch/TorchRL primitives. For Argus, the high-fit interpretation is narrower and sharper:

> Argus can become a local robotics experiment workbench that makes robot policies, perception backends, datasets, scenarios, and evaluation artifacts swappable, inspectable, reproducible, and UI-operable inside a controlled multi-robot MuJoCo environment.

The best near-term product direction is to extend Argus’s existing registry + typed DAG + benchmark artifact pattern into a policy/dataset/evaluation workbench: import/export LeRobot-style datasets, register policy artifacts as first-class backends, compare them through scenario/seed matrices, visualize their behavior in the browser, and keep CPU/offline/reproducibility constraints explicit.

## 1. Local Evidence from Code and Docs

### 1.1 Current product shape

Argus describes itself as “a simulation-native robotics research workbench for multi-robot autonomy” that connects MuJoCo robot swarms to a real-time browser command center and reproducible benchmark harnesses, with pluggable robot platforms, SLAM backends, perception pipelines, coordination strategies, and locomotion controllers (`/home/prannayag/pragnition/robotics/argus/README.md:7`). The quick workflows are simulation, static viewing, autonomous exploration, and locomotion evaluation (`/home/prannayag/pragnition/robotics/argus/README.md:17-24`).

The current architecture summary is even more precise: Argus is a local, simulation-first multi-robot perception workbench where MuJoCo runs simulated Unitree Go2 robots, Python coordinates exploration/perception, FastAPI streams over WebSockets, and React/Three.js renders command-and-control, maps, detections, metrics, and pipeline editing (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:3`). It explicitly frames the product as repeatable comparison of exploration, SLAM, detection, lifting, tracking, fusion, streaming, and UI behavior under controlled simulation assumptions (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:7`).

The project state confirms the shipped shape: multi-robot MuJoCo simulation, independent SLAM pipelines, frontier exploration, Voronoi coordination, real-time map merging, browser C2, pluggable SLAM/perception, pipeline editor, detection/lifting/tracking/semantic layers, and a Gymnasium-style locomotion benchmark wrapper (`/home/prannayag/pragnition/robotics/argus/.planning/PROJECT.md:15-41`).

### 1.2 Existing “workbench primitives”

Argus already has several primitives that map directly to a robotics workbench model:

- **Protocol/registry plugin system.** ADR-0006 says Argus uses runtime-checkable Protocols plus registries for SLAM, detection, lifting, tracking, and merge strategy comparison, with metadata/capabilities/parameter schemas surfaced to the UI (`/home/prannayag/pragnition/robotics/argus/docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:15-32`).
- **Typed visual pipeline editor.** ADR-0014 establishes a React Flow typed DAG for pipeline editing so users can inspect and configure detector, lifter, tracker, map, and visualization stages (`/home/prannayag/pragnition/robotics/argus/docs/adr/0014-use-react-flow-typed-dag-for-pipeline-editing.md:15-32`). The frontend loads registry-backed pipeline nodes from `/api/pipeline/node-catalog` when switching to pipeline view (`/home/prannayag/pragnition/robotics/argus/frontend/src/App.tsx:38-56`).
- **Server-driven node catalog.** `NodeCatalog.get_catalog()` combines static nodes with registry-discovered SLAM, merge, detector, lifter, and tracker nodes (`/home/prannayag/pragnition/robotics/argus/src/coordination/pipeline_builder.py:186-260`).
- **Hot-apply/restart distinction.** The pipeline REST route can hot-apply detector/lifter/tracker changes when topology and structural fields are unchanged; other changes trigger restart (`/home/prannayag/pragnition/robotics/argus/backend/web/pipeline_routes.py:69-209`). This is directly relevant for a policy/model workbench because not every graph change can be safely hot-swapped.
- **Pinned model artifacts.** ADR-0011 requires CPU-viable model tiers, pinned checkpoints, local prefetch, and offline/CI expectations (`/home/prannayag/pragnition/robotics/argus/docs/adr/0011-use-cpu-viable-model-tiers-and-pinned-offline-checkpoints.md:15-32`). The model layout documents HuggingFace snapshot use, immutable SHA directories, and artifact ownership by scripts (`/home/prannayag/pragnition/robotics/argus/models/README.md:1-55`).
- **Torch/PyTorch-aware backend discipline.** The perception protocol keeps heavy imports out of module scope, mandates warmup, exposes capabilities/parameter schemas, and provides a `TorchBackendMixin` to enforce `eval()` and `torch.inference_mode()` (`/home/prannayag/pragnition/robotics/argus/src/perception/protocol.py:1-24`, `/home/prannayag/pragnition/robotics/argus/src/perception/protocol.py:157-207`).
- **Benchmark-first locomotion environment.** `ArgusGo2Env` follows Gymnasium reset/step shape (`/home/prannayag/pragnition/robotics/argus/src/locomotion/env.py:39-183`), and the evaluation module validates controller/scenario/seed matrices and writes artifacts (`/home/prannayag/pragnition/robotics/argus/src/locomotion/evaluation.py:79-216`). The docs list `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md` as evaluation artifacts (`/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md:100-110`).
- **Robot platform abstraction.** ADR-0015 proposes isolating model assets, actuator mapping, sensor mapping, command modes, reset/state extraction, footprint, and failure detection behind a robot platform abstraction (`/home/prannayag/pragnition/robotics/argus/docs/adr/0015-introduce-robot-platform-abstraction.md:15-56`). The current code already has platform registry exports for Go2 and AGIBOT X2 (`/home/prannayag/pragnition/robotics/argus/src/bridge/platforms/__init__.py:1-23`) and a `RobotPlatform` Protocol (`/home/prannayag/pragnition/robotics/argus/src/bridge/platforms/base.py:24-44`).
- **MCP control/query surface.** Argus exposes tools for status, detections, scene descriptions, commands, and coverage through an MCP JSON-RPC endpoint (`/home/prannayag/pragnition/robotics/argus/src/mcp/server.py:1-13`, `/home/prannayag/pragnition/robotics/argus/src/mcp/server.py:40-90`).

### 1.3 Current constraints and explicit non-goals

The architecture imposes constraints that should shape any “HF/PyTorch for Robotics” expansion:

- MuJoCo CPU simulation is the platform boundary; hardware, GPU-first, or UE/SimWorld assumptions are not part of the main path without a new ADR (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:84`).
- World-frame map fusion relies on MuJoCo ground-truth poses; default behavior should not quietly reintroduce pose-estimation-dependent merge correctness (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:85`).
- Heavy/crashy backends must be isolated behind subprocess bridges (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:90`).
- Model choices must fit CPU tiers, pinned checkpoints, and offline/CI expectations (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:93`).
- Fake metrics are forbidden; use MuJoCo ground truth or mark metrics unavailable (`/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:94`).
- RL policy training is explicitly out of scope for v4.0; the milestone built the benchmark harness, not trained policies (`/home/prannayag/pragnition/robotics/argus/.planning/PROJECT.md:58`).
- ROS 2 and hardware deployment remain future architecture work, not current product scope (`/home/prannayag/pragnition/robotics/argus/.planning/PROJECT.md:60`).

These constraints are not blockers. They are the product boundary. Argus should compete by being reproducible, inspectable, and local, not by chasing every GPU-heavy robotics foundation model.

## 2. External Comparison Sources Used

### 2.1 Hugging Face LeRobot

LeRobot’s GitHub page says it aims to provide models, datasets, and tools for real-world robotics in PyTorch, with a goal of lowering the barrier to robotics through shared datasets and pretrained models ([LeRobot GitHub](https://github.com/huggingface/lerobot)). The LeRobot docs describe a hardware-agnostic, Python-native interface for robotics control, a unified robot API, standardized dataset format, policies, and evaluation workflows ([LeRobot docs](https://huggingface.co/docs/lerobot/)). The docs/repo describe `LeRobotDataset` as using Parquet plus MP4/images for synchronized robot data and supporting Hugging Face Hub loading and dataset operations ([LeRobot dataset docs](https://huggingface.co/docs/lerobot/lerobot-dataset-v3)). The Hugging Face LeRobot organization page visibly hosts robotics models, datasets, spaces, collections, and robot URDF assets ([LeRobot HF org](https://huggingface.co/lerobot)).

Implication for Argus: LeRobot is the most direct “HuggingFace for robotics” benchmark. Argus should interoperate with it rather than imitate its global hub role.

### 2.2 Open X-Embodiment / RT-X

Open X-Embodiment/RT-X assembles a large real-robot dataset across many embodiments, labs, datasets, and skills, and asks whether cross-robot policies can generalize across robots, tasks, and environments ([Open X-Embodiment project](https://robotics-transformer-x.github.io/), [paper](https://arxiv.org/abs/2310.08864), [GitHub](https://github.com/google-deepmind/open_x_embodiment)).

Implication for Argus: Robotics ML is moving toward cross-embodiment datasets and reusable policies, but the evaluation and embodiment-mapping problem is hard. Argus’s robot platform abstraction and scenario/seed harness are the local mechanisms needed before cross-embodiment policy comparison can be honest.

### 2.3 Isaac Lab

Isaac Lab is an open-source platform for robot simulation and training, emphasizing robot learning workflows, environments, RL/imitation hooks, and high-throughput simulation ([Isaac Lab docs](https://isaac-sim.github.io/IsaacLab/)).

Implication for Argus: Isaac Lab owns the GPU-scale synthetic training lane. Argus should not compete on throughput. It should compete on browser-operable multi-robot perception/coordination experiments and CPU-first reproducibility.

### 2.4 ManiSkill

ManiSkill presents itself as a unified open-source platform for robot simulation and training, with manipulation tasks, GPU-parallel simulation, visual data collection, RL/imitation/VLA baselines, and real-to-sim evaluation support ([ManiSkill docs](https://maniskill.readthedocs.io/en/latest/)).

Implication for Argus: ManiSkill reinforces that modern robotics workbenches bundle tasks, data, policies, baselines, and evaluation. Argus currently has tasks/scenarios and evaluation for locomotion, but not a generalized dataset/policy workbench.

### 2.5 robosuite and robomimic

robosuite is a MuJoCo-based modular simulation framework and benchmark for robot learning ([robosuite](https://robosuite.ai/)). robomimic is a framework for robot learning from demonstration with demonstration datasets and imitation-learning workflows ([robomimic](https://robomimic.github.io/)).

Implication for Argus: Argus shares MuJoCo and benchmark DNA with these systems, but its distinctive surface is multi-robot exploration/perception with browser command-and-control, not table-top manipulation alone.

### 2.6 TorchRL / PyTorch primitives

TorchRL provides PyTorch-first abstractions for RL, including environments, collectors, replay buffers, trainers, and reusable RL modules ([TorchRL docs](https://docs.pytorch.org/rl/main/index.html)).

Implication for Argus: “PyTorch for Robotics” should mean stable tensor/data/control interfaces and reusable training/evaluation plumbing, not just importing `torch`. Argus already has a Gymnasium seam and Torch inference discipline; the missing piece is a first-class policy/dataset artifact boundary.

## 3. Evidence Table

| Claim | Source | Confidence |
|---|---|---:|
| Argus is currently a simulation-native multi-robot robotics workbench with browser C2 and reproducible benchmarks. | `/home/prannayag/pragnition/robotics/argus/README.md:7-24`; `/home/prannayag/pragnition/robotics/argus/docs/ARCHITECTURE.md:3-12` | High |
| Argus’s main architectural seam is registry-backed pluggability for robotics algorithms. | `/home/prannayag/pragnition/robotics/argus/docs/adr/0006-use-protocol-registry-pattern-for-pluggable-backends.md:15-32`; `/home/prannayag/pragnition/robotics/argus/src/perception/registry.py:135-218` | High |
| Argus already exposes a typed visual DAG for pipeline composition. | `/home/prannayag/pragnition/robotics/argus/docs/adr/0014-use-react-flow-typed-dag-for-pipeline-editing.md:15-32`; `/home/prannayag/pragnition/robotics/argus/src/coordination/pipeline_builder.py:186-260`; `/home/prannayag/pragnition/robotics/argus/frontend/src/App.tsx:38-56` | High |
| Argus has CPU/offline/pinned model constraints that should govern HF/PyTorch integration. | `/home/prannayag/pragnition/robotics/argus/docs/adr/0011-use-cpu-viable-model-tiers-and-pinned-offline-checkpoints.md:15-32`; `/home/prannayag/pragnition/robotics/argus/models/README.md:36-55` | High |
| Argus has a Gymnasium-style locomotion benchmark harness, but not an RL training pipeline. | `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md:19-47`; `/home/prannayag/pragnition/robotics/argus/.planning/PROJECT.md:58` | High |
| LeRobot is the clearest external example of “HF for robotics”: shared datasets, pretrained policies, PyTorch tooling, hardware-agnostic robot APIs, and Hub integration. | [LeRobot GitHub](https://github.com/huggingface/lerobot); [LeRobot docs](https://huggingface.co/docs/lerobot/); [LeRobot HF org](https://huggingface.co/lerobot) | High |
| Open X-Embodiment/RT-X shows momentum toward cross-embodiment robotics datasets and policies, but also highlights embodiment/data heterogeneity. | [Open X-Embodiment project](https://robotics-transformer-x.github.io/); [arXiv paper](https://arxiv.org/abs/2310.08864); [GitHub](https://github.com/google-deepmind/open_x_embodiment) | High |
| Isaac Lab and ManiSkill occupy the high-throughput simulation/training/benchmark lane more than Argus currently does. | [Isaac Lab docs](https://isaac-sim.github.io/IsaacLab/); [ManiSkill docs](https://maniskill.readthedocs.io/en/latest/) | Medium |
| robosuite/robomimic show that MuJoCo + benchmarks + imitation-learning datasets are established reusable robotics ML patterns. | [robosuite](https://robosuite.ai/); [robomimic](https://robomimic.github.io/) | Medium |
| Argus’s best-fit opportunity is not a global hub, but a local experiment workbench that interoperates with hubs and makes policies/datasets/evals inspectable. | Synthesis from all local evidence plus external comparison | Medium-High |

## 4. Current Extension Points

### 4.1 Policy/controller registry

Argus already has a controller registry seam for locomotion, with analytical trot supported and residual/direct RL/MPC/WBC placeholders documented as unavailable (`/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md:112-124`). This is the natural entry point for learned policy artifacts.

What is missing: a policy artifact schema that says what observation keys, action mode, robot platform, scenario assumptions, normalization, checkpoint revision, runtime backend, and safety limits a policy expects.

### 4.2 Dataset import/export boundary

Argus writes evaluation artifacts today, but not robot-learning datasets. The locomotion harness emits per-step metrics and episode summaries (`/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md:100-110`). The simulation loop also has sensor frames, robot poses, commands, detections, coverage, and maps available internally. Those are enough to define episodes for imitation/RL analysis.

What is missing: a stable episode schema and import/export adapters, especially for LeRobot-like Parquet + MP4/images layouts.

### 4.3 Pipeline editor as workbench UI

The React Flow DAG currently composes perception/SLAM pipeline nodes. The same pattern could represent policy inputs/outputs, dataset recorders, evaluators, and safety filters. The existing server-backed node catalog avoids a hardcoded frontend-only graph.

What is missing: new node categories and lifecycle semantics for “record,” “replay,” “policy,” “evaluator,” “dataset,” and “artifact exporter.”

### 4.4 Robot platform abstraction

The platform abstraction is the right foundation for cross-embodiment work because policy compatibility is inseparable from robot state/action spaces. Go2 and AGIBOT X2 registration already exists in code, even though ADR-0015 remains proposed.

What is missing: platform-level observation/action metadata that can be consumed by policy registries, dataset schemas, and UI validation.

### 4.5 MCP as automation surface

The current MCP endpoint exposes status, detections, commands, and coverage. A workbench direction could expose dataset recording, evaluation launch, artifact inspection, policy selection, and scenario matrix control to agents.

What is missing: a carefully constrained experiment-control API. Without guardrails, MCP becomes a second hidden UI with weaker validation.

## 5. Gaps Against a “HF/PyTorch for Robotics” Direction

### 5.1 Dataset standardization gap

Argus has evaluation artifacts, sensor streams, and metrics, but no documented robotics dataset format. LeRobot’s value proposition depends heavily on standardized datasets and Hub sharing. Argus would need an episode schema before it can meaningfully import/export demonstrations, policy rollouts, failure cases, or benchmark submissions.

### 5.2 Policy artifact gap

Argus has controller seams and Torch inference discipline, but not a general learned-policy artifact registry. Current locomotion placeholders are useful seams, not runnable policy integrations. A policy registry should be separate from a controller registry if policies can drive different action modes, consume different observations, or require preprocessing.

### 5.3 Training pipeline gap

Argus intentionally does not ship RL policy training in v4.0. That is fine. But a robotics workbench must decide whether it is:

1. an evaluator/visualizer of externally trained policies;
2. a local fine-tuning/training environment;
3. a data-collection environment;
4. all of the above.

Trying to jump straight to all three would violate the current CPU-first/offline discipline.

### 5.4 Cross-embodiment gap

Open X-Embodiment-style robotics depends on mapping observations/actions across robot embodiments. Argus has the right platform abstraction direction, but the Go2 locomotion env is still specifically `ArgusGo2Env`. A general `ArgusRobotEnv` or platform-specific env registry would be needed before “policies across Go2 and X2” becomes more than marketing.

### 5.5 Evaluation credibility gap

Argus has strong instincts here: fake mAP is forbidden and locomotion evaluation is seeded and artifact-backed. The gap is breadth. There is no unified evaluation story for perception-policy interaction, data collection quality, imitation-policy success, VLA-style task success, or multi-robot coordination policies.

### 5.6 Hub/interoperability gap

Argus already downloads pinned HuggingFace model snapshots for detectors, but it does not yet treat external datasets/models/environments as first-class importable/exportable workbench objects. The direction should add adapters, not unpinned runtime downloads.

## 6. Concrete Argus Opportunities Ranked by Fit

### 1. Policy artifact registry and evaluator for existing locomotion seams

**Fit:** Very high  
**Strategic value:** High  
**Feasibility:** High-Medium  
**Why:** This extends what Argus already built: Gymnasium-style env, controller registry, scenario/seed matrix, metrics, and artifacts. It also respects the v4.0 decision that training is out of scope while evaluation is in scope.

**Shape:** Add a first-class learned-policy artifact concept for residual/direct policies. Each artifact declares robot platform, action mode, observation schema, checkpoint path/revision, framework, normalization, latency expectations, and promotion criteria against analytical baseline.

**Architecture implications:**
- Add `PolicyProtocol`/`PolicyRegistry` rather than bloating controller protocols.
- Reuse pinned checkpoint layout under `models/<policy-slug>/<sha>/`.
- Extend evaluation matrix with `policy_id` and policy artifact metadata.
- Keep subprocess isolation available for heavy PyTorch/VLA policies.

**Risks:** Policy artifact metadata can become vague unless schema validation is strict. GPU-required policies could erode the CPU-first boundary.

### 2. LeRobot-compatible episode export/import for Argus rollouts

**Fit:** Very high  
**Strategic value:** High  
**Feasibility:** Medium  
**Why:** LeRobot is the external hub-standard direction most aligned with “HF for Robotics.” Argus has rich simulation rollouts and metrics but lacks dataset packaging. Exporting Argus episodes lets Argus participate in the broader robotics dataset ecosystem without becoming the hub.

**Shape:** Export synchronized RGB/depth frames, robot state, actions/commands, scenario metadata, robot platform metadata, detections, coverage, and success/failure labels into a versioned dataset layout. Start with export only; import/replay later.

**Architecture implications:**
- Define `ArgusEpisodeSchema` with versioning.
- Add dataset writer as an artifact exporter, not as hidden simulation side effects.
- Keep video/image encoding choices explicit.
- Add provenance: git commit, scenario seed, platform, model revisions, active pipeline graph.

**Risks:** Dataset schemas are sticky. A sloppy first schema will haunt the project. Depth, coordinate frames, and action semantics must be explicit.

### 3. Experiment/run browser for evaluations and datasets

**Fit:** High  
**Strategic value:** High  
**Feasibility:** Medium-High  
**Why:** Argus already writes locomotion eval directories but exposes them mainly through CLI/docs. The product is browser-first; the workbench needs a run browser for comparing policies, datasets, and pipeline graphs.

**Shape:** UI panels for saved runs, manifests, scenario/seed matrices, scorecards, per-step traces, metric overlays, and replay links.

**Architecture implications:**
- Treat `outputs/locomotion-evals/*/manifest.json` as a stable API or define a read model.
- Add backend routes for run discovery and artifact loading.
- Avoid letting frontend compute robotics metrics; render server-produced summaries.

**Risks:** Artifact schema drift. Large files can make the UI slow if loaded naively.

### 4. Dataset recorder/replay nodes in the React Flow pipeline editor

**Fit:** High  
**Strategic value:** Medium-High  
**Feasibility:** Medium  
**Why:** The typed DAG is one of Argus’s differentiators. Adding dataset record/replay nodes turns the UI from “algorithm picker” into “experiment graph.”

**Shape:** Node types for recording sensor/state/action streams, replaying saved episodes, exporting artifacts, and attaching evaluators. A user can visually see: sensor -> perception -> policy -> action -> metrics -> dataset writer.

**Architecture implications:**
- Add node categories: dataset, policy, evaluator, artifact.
- Extend port types for observations, actions, episodes, metrics, and artifacts.
- Make lifecycle explicit: live-only, restart-required, replay-only, offline-only.

**Risks:** Graph semantics may get too general and turn into a half-baked workflow engine. Keep nodes tied to concrete Argus runtime capabilities.

### 5. Policy-ready platform metadata for Go2 and X2

**Fit:** High  
**Strategic value:** Medium-High  
**Feasibility:** Medium  
**Why:** Cross-embodiment policy work requires platform-level observation/action definitions. Argus already has the beginning of a platform registry.

**Shape:** Each platform declares observation spaces, action modes, actuator names, command limits, safety constraints, sensor streams, camera specs, and policy compatibility tags.

**Architecture implications:**
- Extend `RobotPlatformMetadata` and platform registry outputs.
- Connect platform metadata to policy artifact validation.
- Replace Go2-specific env assumptions gradually with platform-aware env factories.

**Risks:** Overgeneralizing before X2 is real. Follow ADR-0015’s advice: support Go2 and X2, then generalize only where both need it.

### 6. HuggingFace Hub adapter with pinned/offline mode

**Fit:** Medium-High  
**Strategic value:** Medium  
**Feasibility:** Medium  
**Why:** Argus already uses HuggingFace snapshots for detector checkpoints. A hub adapter could fetch policy/dataset artifacts while preserving reproducibility.

**Shape:** A CLI/tooling layer that resolves `repo_id@revision` into local immutable artifact directories, records metadata, and blocks unpinned downloads by default.

**Architecture implications:**
- Generalize `scripts/download_models.py` patterns.
- Add artifact manifests with source URL, revision, license, hashes, and expected files.
- Mark network tests separately, consistent with `pytest.ini` network marker.

**Risks:** Runtime downloads would violate current invariants. License and model-card metadata can be incomplete or misleading.

### 7. MCP experiment automation tools

**Fit:** Medium  
**Strategic value:** Medium  
**Feasibility:** Medium  
**Why:** Argus already exposes MCP tools. Agent-driven robotics workbench workflows could ask for status, run evaluations, compare artifacts, and inspect failures.

**Shape:** Add tools like `list_runs`, `start_eval`, `get_eval_summary`, `record_episode`, and `compare_policies` after the underlying run/dataset APIs are stable.

**Architecture implications:**
- MCP should wrap existing validated backend APIs, not bypass them.
- Long-running jobs need state, cancellation, and artifact references.

**Risks:** Safety and trust boundary. MCP should not become a remote-control backdoor for arbitrary experiment mutation.

### 8. Training integration through external frameworks, not native first

**Fit:** Medium  
**Strategic value:** Medium-High  
**Feasibility:** Low-Medium  
**Why:** Training is attractive, but Argus’s current strengths are evaluation, visualization, and controlled simulation. Native RL training would add substantial complexity.

**Shape:** Start with export/import and evaluation of policies trained by LeRobot/TorchRL/other stacks. Later, add optional training adapters that consume Argus datasets and write policy artifacts.

**Architecture implications:**
- Keep training outside the main simulation loop.
- Use subprocess/job isolation.
- Define promotion gates against benchmark matrices.

**Risks:** Training stacks pull in GPUs, large dependencies, long jobs, and non-determinism. This is the easiest path to bloating Argus beyond its product boundary.

## 7. Architecture Implications

### 7.1 Data model

Argus needs a versioned episode/run data model that links:

- scenario id and seed;
- robot platform id and metadata;
- active pipeline graph and backend revisions;
- observations: RGB, depth, proprioception, command, previous action, detections, map/coverage summaries;
- actions: velocity command, joint positions, residuals, policy outputs;
- metrics: per-step and aggregate;
- artifacts: videos, JSONL, CSV, summaries, model/dataset provenance.

This should not be buried in whatever a writer happens to emit. It should be a contract.

### 7.2 Plugin system

The registry pattern should expand, but only with small Protocols:

- `PolicyProtocol`: load artifact, warmup, infer action, reset, metrics, apply params.
- `DatasetWriterProtocol`: record step/episode and finalize artifacts.
- `DatasetReaderProtocol`: replay/sampling interface.
- `EvaluatorProtocol`: consume episode/run and produce metrics.

Do not inflate existing detector/controller protocols to cover datasets and policies.

### 7.3 Experiment tracking and provenance

The locomotion `manifest.json` pattern is the right seed. A general workbench needs manifests for every run/dataset/policy evaluation. Required fields should include git commit, command invocation, scenario matrix, platform metadata, active pipeline graph, model artifact revisions, policy artifact revisions, and environment/package versions.

### 7.4 Robot/simulator adapters

Argus should preserve MuJoCo as the default boundary. Any future ROS/hardware adapter should be a separate ADR and adapter layer. The correct near-term move is not ROS deployment; it is making simulated platform metadata honest enough that external policies/datasets can be validated before execution.

### 7.5 Model/policy registry

Perception model registry and policy registry should be parallel but separate. Perception models consume sensor frames and produce detections/semantic outputs. Policies consume observation vectors/images/state and produce actions/commands. Their lifecycles, latency budgets, and safety implications differ.

### 7.6 Evaluation harness

The locomotion matrix evaluator should become the pattern for other evaluation families:

- locomotion controller/policy evaluation;
- perception evaluation with real labels when available or MuJoCo ground-truth proxies when legitimate;
- multi-robot coordination evaluation: coverage rate, overlap, merge latency, path efficiency, stuck recovery;
- policy-conditioned exploration evaluation: coverage and task progress under policy control.

### 7.7 UI workflows

The browser UI should evolve from live C2 + pipeline editor into a workbench with three modes:

1. **Live run:** inspect active robots, maps, detections, commands, policy outputs.
2. **Pipeline/workflow:** configure graph nodes and artifacts.
3. **Runs/datasets:** browse, replay, compare, export.

The UI should render server-owned geometry and server-produced metrics, consistent with current architecture.

### 7.8 Integration boundaries

Argus should integrate with Hugging Face/LeRobot at the artifact boundary:

- import/export datasets;
- import pinned policies/checkpoints;
- write model/dataset cards or metadata summaries;
- avoid unpinned runtime downloads;
- avoid depending on cloud availability for local experiments.

## 8. Risks

### 8.1 Product dilution

Trying to be LeRobot, Isaac Lab, ManiSkill, robosuite, robomimic, and a browser C2 all at once will make Argus worse. Argus’s defensible wedge is local multi-robot simulation, perception/coordination observability, and reproducible comparison.

### 8.2 GPU creep

External robotics ML increasingly assumes GPUs. Argus’s ADRs are CPU-first. GPU-only policies should be optional and clearly unavailable on CPU, not quietly made default.

### 8.3 Schema lock-in

Dataset and policy schemas will become long-lived contracts. Version them from day one and keep coordinate frames, action semantics, and timing explicit.

### 8.4 False benchmark confidence

Simulation can make bad policies look good. Argus should continue its current honesty: use ground truth where legitimate, mark unavailable metrics honestly, and keep promotion criteria explicit.

### 8.5 UI graph overreach

React Flow can become a visual programming trap. The graph should describe Argus-supported runtime/dataflow concepts, not arbitrary workflows.

### 8.6 Dependency and license sprawl

Hub integration brings licenses, model cards, dataset terms, binary weights, and transitive dependencies. The existing `models/README.md` and ADR-0011 discipline should be generalized before more artifacts arrive.

### 8.7 Safety boundary drift

Policies are not detectors. A bad detector is annoying; a bad policy controls motion. Even in simulation, policy execution should have command limits, failure detection, and clear stop/recovery behavior.

## 9. Recommended Direction

The most coherent next milestone is:

> **Argus Policy/Data Workbench v1:** make Argus able to evaluate and inspect learned policy artifacts and export LeRobot-compatible simulated episodes, while preserving CPU-first, pinned, reproducible local workflows.

Suggested milestone slices:

1. Define episode/run/policy artifact schemas and ADR.
2. Add policy artifact registry for locomotion seams, initially evaluation-only.
3. Export Argus rollout episodes in a LeRobot-compatible or LeRobot-adjacent format.
4. Extend evaluation manifests and comparison outputs for policy artifacts.
5. Add a browser run/dataset comparison surface.
6. Only then consider training adapters.

## 10. Bottom Line

“HuggingFace/PyTorch for Robotics” for Argus should mean **artifact-centered robotics experimentation**: datasets, policies, robot platforms, scenarios, pipelines, metrics, and runs all become typed, inspectable, reproducible objects. Argus already has the architectural habits for this: registries, typed DAGs, pinned models, Gymnasium-style evaluation, browser C2, and ADR-backed constraints. The gap is not philosophical. It is the missing artifact/data/policy layer.
