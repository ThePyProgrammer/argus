# Research Plan: AGIBOT X2 Swarm Control and Simulation Development

## Questions
1. What is publicly known about the AGIBOT X2 humanoid platform, including morphology, actuators, compute stack, SDK availability, simulation assets, model files, and development tooling?
2. What prior works, demos, repositories, papers, benchmarks, or datasets use AGIBOT humanoids or closely related AGIBOT/Galbot humanoid assets?
3. Which robot description assets are available or inferable for AGIBOT X2-based humanoid simulation: URDF/MJCF, meshes, USD, Isaac Sim/Isaac Lab assets, MuJoCo assets, ROS/ROS 2 packages, teleoperation files, and calibration data?
4. What swarm-control approaches are relevant to multiple humanoid robots, especially multi-agent RL, decentralized control, task allocation, formation control, communication constraints, and sim-to-real transfer?
5. What simulation-training considerations matter for AGIBOT X2 humanoids: physics engine selection, contact modeling, actuator modeling, observation/action design, domain randomization, terrain/tasks, curriculum, safety constraints, and evaluation protocols?
6. What practical engineering risks should be noted before training or deploying a swarm of AGIBOT X2 robots: asset licensing, incomplete specs, sim fidelity gaps, compute needs, synchronization, networking, collision avoidance, safety, and reproducibility?

## Strategy
- This is a broad, multi-faceted research topic requiring 4 parallel research dimensions in the first round.
- Researcher allocations:
  - T1 Platform and public ecosystem: AGIBOT X2 specifications, product pages, SDKs, docs, press, official repositories, manufacturer claims.
  - T2 Assets and code: GitHub/GitLab/ROS/Isaac/MuJoCo repositories, URDF/MJCF/USD/mesh assets, AGIBOT/Galbot package names, licensing and file usefulness.
  - T3 Prior works and datasets: academic papers, arXiv, conference papers, benchmark/dataset references involving AGIBOT humanoids or directly comparable humanoid platforms.
  - T4 Swarm and simulation methodology: multi-humanoid control, MARL, sim-to-real, humanoid locomotion/control training practices applicable to X2.
- Expected rounds:
  - Round 1: Broad discovery across the four dimensions.
  - Round 2: Targeted gap filling only if source verification exposes dead links, unsupported critical claims, or missing evidence.
- Lead researcher will synthesize the final report, verify source URLs, downgrade unsupported claims, and record provenance.

## Acceptance Criteria
- [x] All key questions answered with at least 2 independent sources where available.
- [x] Publicly available AGIBOT X2-specific facts separated from inferences based on related AGIBOT/humanoid platforms.
- [x] Asset usefulness assessed with concrete file/repository names, formats, license notes, and simulation compatibility.
- [x] Swarm-control recommendations grounded in humanoid/MARL/sim-to-real literature, not only generic robotics claims.
- [x] Contradictions identified and addressed.
- [x] No single-source claims on critical findings unless explicitly labeled as single-source/unverified.
- [x] Final report includes practical simulation-training checklist and risk register.
- [x] Source URLs in final citations fetched or otherwise verified before delivery.

## Task Ledger
| ID | Owner | Task | Status | Output |
|---|---|---|---|---|
| T0 | lead | Create research plan and obtain user confirmation | done | outputs/.plans/agibot-x2-swarm.md |
| T1 | researcher-platform | Find official/public AGIBOT X2 platform information, SDK/tooling references, manufacturer documentation, and ecosystem context | done | outputs/agibot-x2-swarm-research-platform.md |
| T2 | researcher-assets | Locate AGIBOT X2/AGIBOT humanoid simulation assets and code repositories; assess file formats, usefulness, maturity, and licensing | done | outputs/agibot-x2-swarm-research-assets.md |
| T3 | researcher-literature | Survey prior works using AGIBOT humanoids and comparable humanoid robots for learning/control; collect papers, datasets, benchmarks | done | outputs/agibot-x2-swarm-research-literature.md |
| T4 | researcher-methods | Survey swarm-control and simulation-training methods relevant to multi-humanoid robot training and sim-to-real transfer | done | outputs/agibot-x2-swarm-research-methods.md |
| T5 | lead | Evaluate round-1 outputs, identify gaps, contradictions, and single-source claims | done | outputs/.plans/agibot-x2-swarm.md |
| T6 | lead / targeted researcher | Run targeted second-round searches if required | skipped | Not required; one dead MRTA source was removed/replaced during citation verification |
| T7 | lead | Write cited draft and claim sweep | done | outputs/.drafts/agibot-x2-swarm-draft.md |
| T8 | lead | Verify citations, finalize report and provenance | done | outputs/agibot-x2-swarm.md; outputs/agibot-x2-swarm.provenance.md |

## Verification Log
| Item | Method | Status | Evidence |
|---|---|---|---|
| AGIBOT X2 specifications and availability | Cross-read official sources plus third-party aggregators; independent Robot Report fetch failed 403 and was not used for claims | pass with notes | outputs/agibot-x2-swarm-research-platform.md |
| Availability of AGIBOT X2-specific simulation assets | Direct repo/source discovery; inspect file lists, licenses, and formats | pass with notes | outputs/agibot-x2-swarm-research-assets.md |
| Prior AGIBOT humanoid works | Cross-check papers/repos/datasets and publication metadata | pass with notes | outputs/agibot-x2-swarm-research-literature.md |
| Applicability of swarm/MARL methods to humanoid X2 training | Cross-read robotics literature and identify assumptions/limits | pass | outputs/agibot-x2-swarm-research-methods.md |
| Sim-to-real training recommendations | Cross-source from humanoid RL, legged RL, and physics simulation literature | pass | outputs/agibot-x2-swarm-research-literature.md; outputs/agibot-x2-swarm-research-methods.md |
| Critical gap: no public multi-X2 swarm baseline | Negative evidence from platform/assets/literature searches | pass with notes | outputs/agibot-x2-swarm-research-platform.md; outputs/agibot-x2-swarm-research-literature.md |
| Critical gap: official X2 SDK/assets are gated or not publicly released as complete simulation stack | Official docs plus repo search | pass with notes | outputs/agibot-x2-swarm-research-platform.md; outputs/agibot-x2-swarm-research-assets.md |
| Final cited URLs | WebFetch/live-source verification; dead MRTA links rejected and final reference set verified | pass with notes | outputs/agibot-x2-swarm.provenance.md |

## Decision Log
- 2026-04-30: Topic classified as complex multi-domain research; plan uses 4 first-round researcher agents with disjoint scopes.
- 2026-04-30: Slug selected as `agibot-x2-swarm` to cover both platform and multi-robot control focus.
- 2026-04-30: First-round reports are sufficient for synthesis. No targeted second round is needed unless citation verification finds dead/unusable sources.
- 2026-04-30: Final report will clearly distinguish AGIBOT X2 Ultra-specific evidence from related AgiBot G1/G2/X1 and general humanoid/MARL literature.
- 2026-04-30: Citation verification rejected inaccessible MRTA links and removed them from the final report; cooperative MARL review and verified CTDE sources remain.
