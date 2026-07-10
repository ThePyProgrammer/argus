# Research Plan: Skill-Based Adaptation of Navigation Strategies

## Questions

1. What does the robotics and RL literature mean by skills, options, affordances, or behavior primitives for navigation and exploration?
2. Which approaches support online adaptation of navigation strategy selection without requiring immediate low-level motor-policy learning?
3. What evidence exists for model-based skill planning, hierarchical RL/options, contextual bandits, case-based retrieval, or meta-control in navigation/exploration tasks?
4. What state, action, outcome, and reward abstractions recur across successful skill-navigation systems?
5. How do papers evaluate skill-based navigation adaptation in simulation-first settings, and what metrics are credible for exploration progress, robustness, efficiency, and recovery?
6. What failure modes and guardrails are reported: skill thrashing, overfitting to layouts, unsafe exploration, reward hacking, poor transfer, non-reproducible claims, or brittle learned policies?
7. How should the existing Argus design spec at `docs/superpowers/specs/2026-05-14-exploration-skill-learning-design.md` be refined in light of the literature?

## Strategy

This is a broad survey across robotics navigation, hierarchical RL, model-based skill learning, and evaluation practice. Use 4 parallel researchers in one initial round, then a targeted second round only if critical claims remain single-sourced or contradictory.

Researcher allocations:

- T1 — Skill/options and hierarchical RL foundations for navigation: options framework, skill discovery, temporal abstraction, skill hierarchies, and navigation-relevant HRL.
- T2 — Model-based skill planning and outcome models: SkiMo-like methods, affordance/skill dynamics, model predictive skill planning, and reusable skill transition models.
- T3 — Navigation/exploration adaptation systems: frontier/exploration strategy selection, learned meta-control, contextual bandits, case-based or memory-based navigation, and multi-robot exploration if available.
- T4 — Evaluation, logging, and guardrails: simulation-first benchmarking, reproducibility, metrics, reward design, safety/guardrails, and failure modes for learned navigation/exploration strategies.

Expected rounds:

- Round 1: Broad evidence collection across the four dimensions.
- Round 2: Targeted gap-filling for contradictions, single-source claims, or missing recent literature.

## Acceptance Criteria

- [x] All key questions answered with at least 2 independent sources where the claim is critical.
- [x] At least 12 credible sources accepted, including foundational HRL/options work and recent robotics/navigation work.
- [x] Both user-referenced papers are identified, summarized, and positioned correctly.
- [x] Evidence distinguishes high-level strategy adaptation from low-level motor-policy learning.
- [x] Evaluation recommendations are grounded in robotics/RL benchmarking sources rather than vibes.
- [x] Contradictions or weak evidence are explicitly identified.
- [x] The final brief includes concrete spec-review refinements for Argus.

## Task Ledger

| ID | Owner | Task | Status | Output |
|---|---|---|---|---|
| T0 | lead | Write research plan and get user confirmation | done | outputs/.plans/navigation-skill-adaptation.md |
| T1 | researcher | Survey skill/options and hierarchical RL foundations for navigation | done | outputs/navigation-skill-adaptation-research-foundations.md |
| T2 | researcher | Survey model-based skill planning and outcome models | done | outputs/navigation-skill-adaptation-research-model-based.md |
| T3 | researcher | Survey navigation/exploration adaptation systems | done | outputs/navigation-skill-adaptation-research-navigation.md |
| T4 | researcher | Survey evaluation, logging, guardrails, and failure modes | done | outputs/navigation-skill-adaptation-research-evaluation.md |
| T5 | lead | Evaluate researcher outputs and run gap-filling if needed | done | plan verification log |
| T6 | lead | Write cited draft with claim sweep | done | outputs/.drafts/navigation-skill-adaptation-draft.md |
| T7 | lead | Verify citations and produce final report/provenance | done | outputs/navigation-skill-adaptation.md |
| T8 | lead | Refine existing design spec review recommendations based on findings | todo | docs/superpowers/specs/2026-05-14-exploration-skill-learning-design.md or review notes |

## Verification Log

| Item | Method | Status | Evidence |
|---|---|---|---|
| User paper 2411.02998 identity and relevance | Direct arXiv/source cross-read by T2 | verified | `outputs/navigation-skill-adaptation-research-model-based.md` [S16]: FraCOs, future hierarchy/generalization source |
| User paper 2207.07560 identity and relevance | Direct arXiv/source cross-read by T1/T2 | verified | `outputs/navigation-skill-adaptation-research-model-based.md` [S1] and foundations [S15]: SkiMo, central model-based skill planning source |
| Claim that high-level skills/options support longer-horizon planning | Cross-read foundations + model-based sources | verified | Options framework, HRL surveys, SkiMo, skill-effect planning in T1/T2 outputs |
| Claim that v1 should avoid low-level motor-policy learning | Cross-read navigation/evaluation sources + Argus ADRs | verified | Planner adaptation/switching and guardrail evidence in T3/T4; Argus ADR-0018/0019 defer motor-policy learning |
| Balanced-score metric recommendations | Cross-read navigation/evaluation sources | verified | T3 frontier/multi-robot exploration sources and T4 benchmark/reproducibility sources |
| Guardrails around promotion gates and fallback | Cross-read evaluation/failure sources | verified | T4 safety/reproducibility sources plus T3 planner-switching caveats |
| RL/options future path compatibility | Cross-read model-based + foundations sources | verified | T1 options/HRL and T2 SkiMo/skill-effect model staged path |

## Decision Log

- 2026-05-14: Scoped research to skill-based adaptation of navigation/exploration strategies, not general locomotion RL.
- 2026-05-14: Plan uses four disjoint research dimensions because the topic spans HRL foundations, model-based skill planning, navigation systems, and evaluation/guardrails.
- 2026-05-14: Round 1 completed with sufficient evidence; no second round needed because critical claims were cross-supported and contradictions were identified.
- 2026-05-14: Corrected paper positioning: arXiv:2207.07560 is SkiMo and central to future model-based skill planning; arXiv:2411.02998 is FraCOs and belongs in future hierarchy/generalization discussion.
