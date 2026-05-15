# Research Plan: HuggingFace/PyTorch for Robotics as Future Direction for Argus

## Questions
1. What do practitioners mean by “HuggingFace for Robotics” or “PyTorch for Robotics,” and which concrete platforms, projects, or ecosystem moves are associated with that framing?
2. What reusable primitives are emerging for robotics ML workflows: datasets, policy/model hubs, simulation assets, benchmarks, eval harnesses, embodied-agent APIs, robot data standards, deployment tooling, and teleoperation/data collection pipelines?
3. Which existing projects best represent this direction, such as Hugging Face LeRobot, Open X-Embodiment / RT-X, NVIDIA Isaac/GR00T ecosystem, ROS/MoveIt/Gazebo integrations, RoboSuite/RoboCasa/RoboMimic, ManiSkill, RLBench, Isaac Lab, Genesis, PyTorch robotics libraries, and robot foundation model efforts?
4. What lessons from Hugging Face and PyTorch’s success in NLP/CV transfer to robotics, and where do they fail because robotics has hardware, safety, embodiment, real-time, sim-to-real, data heterogeneity, and evaluation constraints?
5. What gaps or unmet needs in the current robotics tooling landscape could Argus plausibly address as a robotics workbench?
6. What future product directions for Argus follow from this research, ranked by strategic value, feasibility, and fit with an R&D robotics workbench?
7. What architectural implications would those directions have for Argus: data model, plugin system, experiment tracking, robot/simulator adapters, model/policy registry, evaluation harness, provenance, UI workflows, and integration boundaries?

## Strategy
- Broad survey with 4 parallel researcher allocations, because the topic spans ecosystem/product strategy, research literature, tooling/codebases, and Argus-specific implications.
- Expected rounds: 1 broad round plus 1 targeted follow-up if claims are single-source, contradictions appear, or major ecosystem players are missing.
- Source types:
  - Primary docs and repositories for robotics frameworks/platforms.
  - Papers and benchmarks from 2020–2026, with emphasis on robot foundation models, imitation learning, embodied AI, open robotics datasets, and robot learning benchmarks.
  - Practitioner/product commentary around “HuggingFace for Robotics,” including the provided X post if accessible, but no critical claim should depend on a social post alone.
  - Current project code/docs for Argus to map findings into practical workbench directions.
- Researcher allocations:
  - T1 Ecosystem/Product: define the “HF/PyTorch for Robotics” thesis, map platforms and strategic patterns.
  - T2 Literature/Benchmarks: survey robot foundation model datasets, benchmarks, evals, and reusable research primitives.
  - T3 Tooling/Code: inspect open-source robotics ML stacks, APIs, data formats, and integration patterns.
  - T4 Argus Fit: inspect Argus docs/code and translate external lessons into concrete product/architecture opportunities.

## Acceptance Criteria
- [ ] All key questions answered with ≥2 independent sources where possible.
- [ ] Contradictions identified and addressed, especially around whether robotics is ready for centralized model/dataset hubs.
- [ ] No single-source claims on critical findings.
- [ ] Distinguish primary-source evidence from practitioner opinion and strategic inference.
- [ ] At least 10 high-quality sources, including primary docs/repos and peer-reviewed or arXiv research.
- [ ] At least 5 concrete, ranked future directions for Argus with rationale and implementation implications.
- [ ] URLs for final citations verified live before final delivery.

## Task Ledger
| ID | Owner | Task | Status | Output |
|---|---|---|---|---|
| T0 | lead | Create plan and get confirmation before research | done | outputs/.plans/hf-robotics-workbench.md |
| T1 | researcher | Ecosystem/product survey of “HuggingFace/PyTorch for Robotics” thesis and major players | done | outputs/hf-robotics-workbench-research-ecosystem.md |
| T2 | researcher | Research literature and benchmarks: datasets, foundation models, eval gaps, transferability | done | outputs/hf-robotics-workbench-research-literature.md |
| T3 | researcher | Tooling/code survey: APIs, repos, data standards, simulation/eval/teleop patterns | done | outputs/hf-robotics-workbench-research-tooling.md |
| T4 | researcher | Argus-fit analysis: inspect current Argus and map research to workbench directions | done | outputs/hf-robotics-workbench-research-argus.md |
| T5 | lead | Evaluate research outputs, identify gaps, run targeted follow-up if needed | done | outputs/.plans/hf-robotics-workbench.md |
| T6 | lead | Write cited draft with claim sweep | done | outputs/.drafts/hf-robotics-workbench-draft.md |
| T7 | lead | Verify citations, finalize report and provenance | done | outputs/hf-robotics-workbench.md; outputs/hf-robotics-workbench.provenance.md |

## Verification Log
| Item | Method | Status | Evidence |
|---|---|---|---|
| Meaning and use of “HuggingFace for Robotics” framing | Cross-read platform docs, practitioner-facing project pages, and ecosystem survey; X post inaccessible | pass with note | outputs/hf-robotics-workbench-research-ecosystem.md |
| Current capabilities of Hugging Face LeRobot and related HF robotics efforts | Direct docs/repo/Hub evidence cross-checked by ecosystem, literature, tooling, and Argus-fit researchers | pass | outputs/hf-robotics-workbench-research-ecosystem.md; outputs/hf-robotics-workbench-research-tooling.md |
| Major robotics datasets/model hubs/benchmarks and their maturity | Literature and tooling surveys cross-read across LeRobot, Open X, DROID, BridgeData, OpenVLA, Octo, ManiSkill, RoboCasa, RLBench, robomimic, Isaac Lab | pass | outputs/hf-robotics-workbench-research-literature.md; outputs/hf-robotics-workbench-research-tooling.md |
| PyTorch analogy and transfer limits | Cross-source synthesis from LeRobot/TorchRL/tooling reports plus robotics heterogeneity evidence | pass | outputs/hf-robotics-workbench-research-ecosystem.md; outputs/hf-robotics-workbench-research-tooling.md |
| Strategic gaps that Argus could fill | Triangulated external gaps with local Argus architecture/docs/code evidence | pass | outputs/hf-robotics-workbench-research-argus.md |
| Ranked Argus future directions | Evidence matrix and lead synthesis from four research files | pass | outputs/.drafts/hf-robotics-workbench-draft.md; outputs/hf-robotics-workbench.md |
| Final citation liveness | WebFetch cited URLs before final; inaccessible X post excluded from evidence | pass with notes | outputs/hf-robotics-workbench.provenance.md |

## Decision Log
- 2026-05-08: Selected slug `hf-robotics-workbench` to emphasize the strategic output: insights for Argus as a robotics workbench.
- 2026-05-08: Planned a 4-researcher broad survey because the question spans ecosystem strategy, research literature, tooling architecture, and Argus-specific product direction.
- 2026-05-08: Completed first research round. Evidence is sufficient for synthesis; no follow-up round needed before drafting. The provided X inspiration URL was inaccessible and will be treated only as prompt context, not evidence.
- 2026-05-08: Final report and provenance written. Citation verification passed with notes; final cited sources were fetched or identified, and inaccessible X content was excluded from evidence.
