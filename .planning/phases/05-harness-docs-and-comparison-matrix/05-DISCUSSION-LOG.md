# Phase 5: harness-docs-and-comparison-matrix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 05-harness-docs-and-comparison-matrix
**Areas discussed:** Guide location, Smoke benchmark, Matrix strictness, Doc tests

---

## Guide location

### Where should the Phase 5 harness guide live?

| Option | Description | Selected |
|--------|-------------|----------|
| Docs + README | Create a focused `docs/locomotion-benchmark.md` and add a short README pointer so the main README stays readable. | ✓ |
| README section | Put the guide directly in README for maximum visibility, but it will make an already-long README heavier. | |
| Docs only | Create a focused docs file without README changes; cleaner, but easier for a new developer to miss. | |

**User's choice:** Docs + README
**Notes:** Canonical guide should live in docs; README should point to it.

### How should the new README pointer behave?

| Option | Description | Selected |
|--------|-------------|----------|
| Short command card | Add one compact locomotion benchmark card under quick-start/commands with link, smoke command, and artifact outputs. | ✓ |
| TOC link only | Only add the docs link to the table of contents or docs index; minimal but less helpful for the success criterion. | |
| Full mini-guide | Add a several-paragraph README subsection; most visible, but duplicates the focused guide. | |

**User's choice:** Short command card
**Notes:** Keep README concise and avoid duplicating the focused guide.

---

## Smoke benchmark

### What should the guide treat as the blessed first smoke benchmark command?

| Option | Description | Selected |
|--------|-------------|----------|
| Default command | `uv run argus eval-locomotion` as the canonical first run; it uses analytical_trot, flat_ground, and default seeds. | |
| Explicit flags | Use `uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202` so the defaults are visible. | ✓ |
| Fast single seed | Use one seed and reduced steps for fastest onboarding, but it is less representative of the regression/evaluation path. | |

**User's choice:** Explicit flags
**Notes:** Defaults should be visible to a new developer.

### Which extra CLI examples should the guide include after the blessed smoke command?

| Option | Description | Selected |
|--------|-------------|----------|
| Config + regen | Include one JSON matrix-config example and one `--from-run-dir` regeneration example, because Phase 4 explicitly supports both. | ✓ |
| Regen only | Show saved-run comparison regeneration, but skip matrix config to keep the guide very short. | |
| None | Only document the smoke command and artifact paths; concise, but under-documents available workflow. | |

**User's choice:** Config + regen
**Notes:** Guide should include both larger matrix and offline regeneration workflows.

---

## Matrix strictness

### How strict should the controller-family support matrix be about unavailable families?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard boundary | Mark residual RL, direct RL, MPC, WBC, ROS/hardware, and perception-conditioned locomotion as deferred/unavailable with exact reason and prerequisite. | ✓ |
| Roadmap tone | Use friendlier future-direction language without strong unavailable labels; less harsh but weaker scope protection. | |
| Capability only | Only list what exists now and omit future families; concise but fails the explicit comparison requirement. | |

**User's choice:** Hard boundary
**Notes:** Matrix should prevent future-controller scope drift.

### What columns should the controller-family matrix use?

| Option | Description | Selected |
|--------|-------------|----------|
| Status + why | Family, Status now, Argus hook/seam, Why supported/deferred, Prerequisite to unlock, R&D rationale link. | ✓ |
| Simple table | Family, Supported now?, Notes. Easier to read, but less useful for planning future work. | |
| Deep research | Include pros/cons, toolchains, risks, prerequisites, and references per family; thorough but may duplicate the R&D report. | |

**User's choice:** Status + why
**Notes:** Matrix should be actionable without duplicating the R&D report.

### Should the matrix include concrete code/CLI symbols for each family?

| Option | Description | Selected |
|--------|-------------|----------|
| IDs and seams | Include controller ids/placeholders where they exist, current action modes, and the `argus eval-locomotion` path. | ✓ |
| Concepts only | Keep it conceptual and avoid code symbols; friendlier for readers but less actionable for implementers. | |
| Full internals | Include module/class/function names for every hook; precise, but likely to make docs brittle. | |

**User's choice:** IDs and seams
**Notes:** Include concrete IDs and seams, but avoid a brittle internals dump.

---

## Doc tests

### What kind of verification should Phase 5 add for these docs?

| Option | Description | Selected |
|--------|-------------|----------|
| Light doc tests | Add focused tests/checks that assert docs/README mention the smoke command, artifacts, controller matrix families, and R&D rationale link. | ✓ |
| Manual review | No automated doc tests; rely on plan verification and human review. Faster, but less guardrail for required content. | |
| Run command | Have tests execute the smoke benchmark from docs; strong but likely slow/flaky for routine docs validation. | |

**User's choice:** Light doc tests
**Notes:** Use fast content checks rather than running the benchmark.

### Where should the light doc checks live?

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest docs | Add a focused pytest file under `tests/` that reads Markdown files and asserts required strings/links, matching the existing pytest workflow. | ✓ |
| Script only | Add a standalone script or make target; useful manually but less integrated with existing test runs. | |
| Verifier only | Do not add source tests; rely on GSD verification to inspect docs after implementation. | |

**User's choice:** Pytest docs
**Notes:** Downstream planning should include a small Markdown-content pytest file.

---

## Claude's Discretion

- Exact section titles, prose tone, Markdown table formatting, test filename, and exact assert strings.

## Deferred Ideas

None.
