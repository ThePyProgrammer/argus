# Provenance: AGIBOT X2 Swarm Control and Simulation Development

- **Date:** 2026-04-30
- **Rounds:** 1 researcher round, plus lead citation verification and one targeted replacement for a dead MRTA citation
- **Sources consulted:** 71 unique sources across first-round research files and lead verification attempts
- **Sources accepted:** 42 final cited sources
- **Sources rejected:**
  - The Robot Report AGIBOT funding article: fetch returned HTTP 403 in first-round research, so no claims used.
  - The Robot Report AGIBOT mass-production article: fetch returned HTTP 403 in first-round research, so no claims used.
  - Original MRTA PDF link (`https://www.cs.cmu.edu/~gerkey/research/final_papers/mrta-taxonomy.pdf`): WebFetch returned 404 during verification.
  - SAGE DOI page for the MRTA paper (`https://journals.sagepub.com/doi/10.1177/0278364904045564`): WebFetch returned 403 during verification.
  - HumanoidSpecs/AIWiki redirect target: not used because X2-specific content was not retrieved.
- **Verification:** PASS WITH NOTES — all final citation URLs were checked with WebFetch on 2026-04-30. The final report avoids claims from dead or access-blocked sources. Some GitHub/Hugging Face pages expose less detail through WebFetch than through first-round repository inspection; those claims are phrased with appropriate caution. The AimDK_X2 boundaries/disclaimer page was reachable but detailed disclaimer text was not visible, so the final report does not rely on detailed legal/safety claims from it.
- **Plan:** outputs/.plans/agibot-x2-swarm.md
- **Research files:**
  - outputs/agibot-x2-swarm-research-platform.md
  - outputs/agibot-x2-swarm-research-assets.md
  - outputs/agibot-x2-swarm-research-literature.md
  - outputs/agibot-x2-swarm-research-methods.md
- **Draft:** outputs/.drafts/agibot-x2-swarm-draft.md
- **Final report:** outputs/agibot-x2-swarm.md

## Verification Summary

| Category | Result | Notes |
|---|---|---|
| Official AGIBOT/AimDK_X2 pages | PASS | Product page, specs, compute, sensors, SDK, interface, startup guide, FAQ, transition page, and boundaries page were reachable. |
| Asset/code repositories | PASS WITH NOTES | GitHub/Hugging Face pages were reachable; license and detailed file claims remain subject to repository-level audit before redistribution. |
| AGIBOT/humanoid literature | PASS | Final arXiv citations were reachable and matched the cited titles/topics. |
| MARL/simulation methodology | PASS WITH NOTES | Final arXiv/MuJoCo/ORCA citations were reachable. The inaccessible MRTA source was removed from the final reference set. |
| Critical negative claim: no public multi-X2 swarm baseline found | PASS WITH NOTES | Supported by first-round platform, asset, and literature searches; negative evidence cannot prove nonexistence, so the report phrases this as “no public demonstration found.” |
