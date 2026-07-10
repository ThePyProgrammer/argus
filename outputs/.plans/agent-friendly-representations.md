# Research Plan: Agent-Friendly World Representations for Multi-Robot Swarms

## Questions
1. What role do 3D digital twins, point clouds, meshes, occupancy grids, neural radiance fields, and Gaussian splats actually play in the end-to-end perception-cognition-action loop for multi-robot swarms?
2. What kinds of world representations are currently usable by agentic AI systems such as LLMs, VLMs, embodied agents, planners, and tool-using agents?
3. How do existing systems translate low-level 3D geometry into agent-friendly abstractions such as objects, affordances, topology, semantic maps, scene graphs, task graphs, beliefs, or constraints?
4. What evidence exists that LLMs/VLMs can reason over 3D representations directly versus through derived symbolic, semantic, or language-mediated layers?
5. In swarm settings, how should representations handle partial observability, uncertainty, distributed sensing, map fusion, dynamic environments, communication limits, and heterogeneous robot capabilities?
6. What architecture patterns best connect multi-robot perception to cognition and action without forcing agents to “understand” raw point clouds or Gaussian splats?
7. What are the failure modes and open research gaps for agent-friendly representations in real deployments?

## Strategy
- Treat the core issue as a representation-interface problem: raw 3D assets are not usually the cognition substrate; they are metric/spatial evidence from which agent-facing abstractions are derived.
- Run a broad, multi-domain survey with 4 parallel researchers in the first round:
  - T1: robotics and multi-robot mapping representations, including occupancy maps, semantic maps, topological maps, scene graphs, and distributed SLAM/map fusion.
  - T2: 3D digital twins, point clouds, NeRFs, and Gaussian splats in robotics/swarm contexts, focusing on why they are built and what downstream modules consume them.
  - T3: LLM/VLM/embodied-agent interfaces to spatial worlds, including 3D scene graphs, language-grounded maps, simulators, tool APIs, and planner-readable abstractions.
  - T4: systems architecture for perception-cognition-action loops in multi-robot autonomy, including uncertainty, communication, dynamic worlds, and action grounding.
- Expected rounds: 1 broad round, then 0-1 targeted follow-up rounds for contradictions or thinly supported claims.
- Source priorities:
  - Peer-reviewed robotics/AI papers and arXiv preprints from roughly 2018-2026.
  - Survey papers on semantic SLAM, multi-robot SLAM, scene graphs, embodied AI, VLM navigation, neural mapping, and digital twins.
  - System papers with end-to-end architectures, not just representation demos.
  - Documentation or technical reports for practical systems if they expose representation interfaces.
- Synthesis target: explain what the 3D digital twin is for, what it is not for, and what intermediate representation stack makes it usable by agentic AI.

## Acceptance Criteria
- [ ] All key questions answered with ≥2 independent sources where possible.
- [ ] The report distinguishes raw geometric representations from agent-facing cognitive representations.
- [ ] Claims about LLM/VLM direct 3D reasoning versus mediated reasoning are sourced and not overstated.
- [ ] Multi-robot-specific constraints are covered rather than treating the problem as single-robot mapping.
- [ ] At least one architecture pattern is proposed with explicit perception-cognition-action interfaces.
- [ ] Contradictions or gaps in the literature are identified and addressed.
- [ ] No single-source claims on critical findings.
- [ ] Final cited report includes provenance and verification notes.

## Task Ledger
| ID | Owner | Task | Status | Output |
|---|---|---|---|---|
| T1 | researcher | Survey multi-robot mapping and semantic/topological representation literature. | done | outputs/agent-friendly-representations-research-mapping.md |
| T2 | researcher | Analyze 3D digital twin, point cloud, NeRF, and Gaussian splat usage in robotics/swarm perception pipelines. | done | outputs/agent-friendly-representations-research-3d-twins.md |
| T3 | researcher | Survey LLM/VLM/embodied-agent interfaces to 3D/spatial worlds and agent-readable abstractions. | done | outputs/agent-friendly-representations-research-agent-interfaces.md |
| T4 | researcher | Identify end-to-end perception-cognition-action architecture patterns and swarm-specific constraints. | done | outputs/agent-friendly-representations-research-architecture.md |
| T5 | lead | Synthesize research into draft report with claim sweep. | done | outputs/.drafts/agent-friendly-representations-draft.md |
| T6 | lead | Verify citations, resolve unsupported claims, and publish final report plus provenance. | done | outputs/agent-friendly-representations.md; outputs/agent-friendly-representations.provenance.md |

## Verification Log
| Item | Method | Status | Evidence |
|---|---|---|---|
| Raw 3D assets are typically not the direct reasoning substrate for LLM-like agents. | Cross-read robotics and embodied-agent sources. | pass | T2, T3: T2 says modules consume projections/API outputs; T3 finds mediated abstractions dominate. |
| Scene graphs / semantic maps / topological maps form common agent-facing layers. | Cross-read mapping and embodied-agent sources. | pass | T1, T3: Hydra/DSG/ConceptGraphs/VLMaps evidence. |
| Digital twins are useful as shared state, simulation, inspection, and planning evidence even if agents consume abstractions. | Cross-read digital twin and architecture sources. | pass_with_notes | T2, T4: strong for collision/resource/fleet interfaces; closed-loop swarm twin evidence is thinner. |
| Swarm representation design must account for uncertainty, partial observability, bandwidth, and distributed map fusion. | Cross-read multi-robot SLAM and systems sources. | pass | T1, T4: Kimera-Multi, Swarm-SLAM, decentralized belief planning, Open-RMF/resource scheduling. |
| Direct LLM/VLM reasoning over 3D point clouds/splats remains limited or mediated by encoders/tools. | Source verification and contradiction check. | pass_with_notes | T3: 3D-LLM/LEO are more direct but still feature-mediated; splats not dominant as agent interfaces. |
| Proposed architecture pattern is grounded in cited systems rather than invented unsupported taxonomy. | Claim sweep against all research files. | pass | Final architecture synthesizes OctoMap/Voxblox, DSG/Hydra, Kimera-Multi/Swarm-SLAM/COVINS, SayCan/VoxPoser/LLM+P, Open-RMF, and belief/resource-planning sources. |

## Decision Log
- 2026-05-15: Chose slug `agent-friendly-representations` to match the session focus and keep outputs concise.
- 2026-05-15: Framed the research around representation interfaces rather than asking whether one representation is universally best, because the user’s core confusion is how low-level 3D world models become usable in the perception-cognition-action loop.
- 2026-05-15: First research round completed with four files and 61 cited source entries across mapping, 3D twins, agent interfaces, and architecture. No second broad round needed; follow-up verification will happen during citation/source sweep.
