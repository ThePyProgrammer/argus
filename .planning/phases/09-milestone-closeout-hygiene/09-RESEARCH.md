# Phase 09: milestone-closeout-hygiene - Research

**Researched:** 2026-05-03 [VERIFIED: currentDate]
**Domain:** GSD milestone governance metadata, open artifact audit cleanup, and validation/Nyquist hygiene [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:239-248]
**Confidence:** HIGH [VERIFIED: local GSD audit output and planning files]

## User Constraints

No CONTEXT.md exists for this phase; no locked decisions, discretion areas, or deferred ideas were supplied. [VERIFIED: `gsd-sdk query init.phase-op "9"` returned `has_context: false`]

## Project Constraints (from CLAUDE.md)

- Root project `CLAUDE.md` contains only placeholder project instructions and adds no actionable implementation directive. [VERIFIED: /home/prannayag/pragnition/robotics/argus/CLAUDE.md:1-3]
- Checked-in `.claude/CLAUDE.md` also contains only placeholder project instructions and adds no actionable implementation directive. [VERIFIED: system-reminder project CLAUDE.md]
- Project skill `desloppify` exists under `.claude/skills/desloppify`; it applies to code quality/debt work, but Phase 09 is governance metadata/artifact cleanup rather than source-code health scanning. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.claude/skills/desloppify/SKILL.md:1-8]
- If Phase 09 implementation touches source-code cleanup beyond planning metadata, the planner should account for the skill's scan-plan-execute-rescan workflow rather than doing untracked ad hoc code-health changes. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.claude/skills/desloppify/SKILL.md:18-31]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOC-ENV-01 | Developer can run a Gymnasium-style `ArgusGo2Env` wrapper with `reset(seed=...)` and `step(action)` returning observation, reward, terminated, truncated, and info. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:15] | Phase 1 verification already marks LOC-ENV-01 satisfied; Phase 09 should update stale validation metadata to reflect that status, not re-implement the environment. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-VERIFICATION.md:29-35] |
| LOC-CTRL-01 | Developer can register locomotion controllers behind a common protocol that maps environment observation plus command into actuator/action output. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:22] | Phase 2 verification already marks LOC-CTRL-01 satisfied; Phase 09 should update stale validation metadata to reflect that status. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/02-controller-plugin-baseline/02-VERIFICATION.md:22-28] |
| LOC-METRICS-01 | Evaluation captures command tracking error for forward velocity, lateral velocity, and yaw rate. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:29] | Phase 3 verification already marks LOC-METRICS-01 satisfied; Phase 09 should update stale validation metadata to reflect passed metrics verification. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/03-locomotion-metrics-instrumentation/03-VERIFICATION.md:27-35] |
| LOC-EVAL-01 | Developer can run a CLI evaluation command that executes a controller across a scenario matrix and fixed seed list. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:37] | Phase 6 verification already marks LOC-EVAL-01 satisfied; Phase 09 should update stale validation metadata and preserve the Phase 6 evidence trail. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:43-45] |
</phase_requirements>

## Summary

Phase 09 is a governance closeout phase, not a feature implementation phase. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:239-248] The core planning problem is to reconcile stale validation/Nyquist metadata in Phase 1, 2, 3, and 6 `VALIDATION.md` files with later successful `VERIFICATION.md` evidence, and then clear every open item reported by `gsd-sdk query audit-open`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:123-141] [VERIFIED: `gsd-sdk query audit-open`]

The current closeout blocker set is concrete: three debug sessions remain in `awaiting_human_verify`, and five quick-task summaries are present but scan as incomplete because their frontmatter lacks `status: complete`. [VERIFIED: `gsd-sdk query audit-open`] The GSD audit implementation treats debug sessions as open unless frontmatter status is `resolved` or `complete`, and treats quick tasks as incomplete unless a recognized summary file has frontmatter `status: complete`. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:19-23] [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:80-145]

**Primary recommendation:** Plan a metadata-only cleanup wave that updates the four stale `VALIDATION.md` files from their corresponding passed `VERIFICATION.md` reports, marks quick-task summaries `status: complete`, and either marks the three debug sessions `resolved` with their existing resolution evidence or explicitly moves them out of the v4.0 closeout path before re-running `gsd-sdk query audit-open`. [VERIFIED: local planning files and GSD audit implementation]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Validation/Nyquist metadata reconciliation | Planning/Governance Docs | Test Infrastructure | The stale state lives in `.planning/phases/*/*-VALIDATION.md`, while the source of truth is passed verification reports and pytest command evidence. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:123-141] |
| Open artifact audit cleanup | GSD Planning Artifact Layer | Git/Repository Metadata | `/gsd-complete-milestone` runs `gsd-sdk query audit-open` before milestone close, and the audit scanner reads `.planning/debug` and `.planning/quick` artifact frontmatter. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-80] [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:19-145] |
| Debug session closeout | Planning/Governance Docs | Human Verification Boundary | Debug templates allow `awaiting_human_verify` and `resolved`, but the closeout audit treats only `resolved` or `complete` as non-open. [VERIFIED: /home/prannayag/.claude/get-shit-done/templates/DEBUG.md:9-15] [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59] |
| Quick-task record repair | Planning/Governance Docs | GSD Audit Scanner | Quick task summary files exist, but the scanner reports them as incomplete unless frontmatter `status` equals `complete`. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:109-145] |
| Milestone close gate | GSD CLI Workflow | Planning/Governance Docs | The milestone completion workflow requires `audit-open` to be clear or acknowledged before continuing. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-80] |

## Standard Stack

### Core

| Tool / File Type | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| `gsd-sdk` | `v0.1.0` | Query phase context and run `audit-open` closeout checks. | It is the registered GSD CLI used by the milestone completion workflow. [VERIFIED: `gsd-sdk --version`; /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-45] |
| Markdown with YAML frontmatter | N/A | Store validation, debug, quick-task, and milestone metadata. | GSD audit and templates parse artifact state from Markdown frontmatter. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59] [VERIFIED: /home/prannayag/.claude/get-shit-done/templates/summary.md:9-46] |
| `uv` | `0.10.10` | Run project-supported Python test commands for validation evidence where needed. | Existing Phase 6 verification used `uv run python -m pytest` for the quick and full locomotion gates. [VERIFIED: `uv --version`; /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:90-92] |
| `pytest` | `9.0.2` local CLI; project declares `pytest>=8.0.0` in dev extras | Validate locomotion and bridge behavior if metadata updates need fresh evidence. | The phase verification reports use pytest as the evidence mechanism. [VERIFIED: `pytest --version`; /home/prannayag/pragnition/robotics/argus/pyproject.toml:41-45] |
| Git | `2.54.0` | Confirm no unintended source-code changes and preserve artifact edits. | The repository is a git repo and milestone governance files are versioned. [VERIFIED: `git --version`; environment gitStatus] |

### Supporting

| Tool / File | Version | Purpose | When to Use |
|-------------|---------|---------|-------------|
| `.planning/v4.0-MILESTONE-AUDIT.md` | Audited 2026-05-02T15:11:09Z | Source of the validation metadata debt list and prior milestone audit findings. | Use before editing validation files to avoid inventing scope. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:1-35] |
| `*-VERIFICATION.md` reports | Phase-specific | Source of passed evidence that should drive `VALIDATION.md` metadata updates. | Use as the evidence source for status, commands, and sign-off rows. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-VERIFICATION.md:1-16] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:1-16] |
| `.planning/debug/*.md` | N/A | Debug session lifecycle artifacts. | Update only when the file already contains root-cause, fix, and verification evidence or when explicitly deferring out of closeout. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/debug/point-cloud-rotation.md:72-77] |
| `.planning/quick/*/*-SUMMARY.md` | N/A | Quick-task completion summaries. | Add/repair `status: complete` when the summary already contains completion evidence. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/quick/260317-hat-update-readme-md-with-proper-project-pla/260317-hat-SUMMARY.md:35-84] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Directly repairing artifact frontmatter | Acknowledge all open items during `/gsd-complete-milestone` | Acknowledgement documents deferred debt instead of making `audit-open` clean; Phase 09 success criterion requires no open items that block milestone closure. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:47-80] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248] |
| Re-running full product implementation checks for every requirement | Use passed verification reports as metadata source and run focused gates only if edits alter evidence claims | Phase 09 is governance hygiene; reimplementation would be scope creep because requirements are already checked and verified. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md:5] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:43-48] |
| Editing scanner logic to ignore these artifacts | Repair the artifacts to match documented scanner contract | Scanner behavior is part of the closeout gate; changing it would hide debt rather than close it. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:1-8] |

**Installation:** No new package installation is required for this phase. [VERIFIED: phase scope is planning metadata cleanup in /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:239-248]

**Version verification:** No npm packages are recommended for Phase 09. [VERIFIED: Standard Stack above]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 09 planner input
  |
  v
Read roadmap + requirements + v4 audit
  |
  v
Identify two closeout blockers
  |-- validation/Nyquist metadata debt --> compare VALIDATION.md to VERIFICATION.md evidence --> update frontmatter/rows/sign-off
  |
  |-- open artifact audit items --------> inspect audit-open JSON + artifact files
                                      |-- debug sessions --> resolved/complete or documented deferral path
                                      |-- quick tasks ----> repair SUMMARY frontmatter status
  |
  v
Run focused validation checks if evidence changed
  |
  v
Run `gsd-sdk query audit-open`
  |
  |-- open items remain --> iterate on exact reported artifacts
  |
  |-- no open items ----> ready for `/gsd-complete-milestone`
```

This diagram reflects the Phase 09 success criteria and GSD closeout workflow. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248] [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-80]

### Recommended Project Structure

```text
.planning/
├── phases/
│   ├── 01-locomotion-env-contract/01-VALIDATION.md
│   ├── 02-controller-plugin-baseline/02-VALIDATION.md
│   ├── 03-locomotion-metrics-instrumentation/03-VALIDATION.md
│   ├── 06-repair-evaluation-runner-semantics/06-VALIDATION.md
│   └── 09-milestone-closeout-hygiene/09-RESEARCH.md
├── debug/
│   ├── point-cloud-below-ground.md
│   ├── point-cloud-rotation.md
│   └── voxel-becomes-pointcloud-closeup.md
├── quick/
│   └── */*-SUMMARY.md
└── v4.0-MILESTONE-AUDIT.md
```

These are the planning artifacts implicated by Phase 09 and the current audit output. [VERIFIED: `find .planning ...`; `gsd-sdk query audit-open`]

### Pattern 1: Evidence-Driven Validation Metadata Repair

**What:** Update stale `VALIDATION.md` metadata from passed `VERIFICATION.md` evidence, preserving the original validation strategy while changing only rows that are stale after execution. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:123-141]

**When to use:** Use for Phase 1, 2, 3, and 6 validation files because the v4.0 audit explicitly lists those phases as partial/stale while their verification reports are passed. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:11-21]

**Example:**

```yaml
# Source: GSD validation frontmatter and passed verification reports
status: passed
nyquist_compliant: true
wave_0_complete: true
```

Use the exact evidence command from the corresponding `*-VERIFICATION.md` when documenting why a stale row changed. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:88-95]

### Pattern 2: Scanner-Contract Artifact Closure

**What:** Make artifact frontmatter satisfy the actual scanner predicates rather than guessing what the closeout command wants. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:19-145]

**When to use:** Use for the three debug sessions and five quick-task summaries reported by `audit-open`. [VERIFIED: `gsd-sdk query audit-open`]

**Example:**

```yaml
# Source: .planning/debug template plus audit scanner
status: resolved
updated: 2026-05-03T00:00:00Z
```

For quick tasks, the scanner specifically expects `status: complete`, not merely a `completed:` date. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145]

### Pattern 3: Closeout Gate as Acceptance Test

**What:** Treat `gsd-sdk query audit-open` as the acceptance test for artifact closure because `/gsd-complete-milestone` runs that query before milestone close. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-80]

**When to use:** Run after each batch of artifact metadata repair, and require the final output to show no open items that block closure. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248]

### Anti-Patterns to Avoid

- **Changing product code to satisfy metadata debt:** Phase 09 blockers are planning metadata and open artifact statuses, not unsatisfied runtime requirements. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:43-48]
- **Marking `nyquist_compliant: true` without evidence:** The stale validation issue is precisely about metadata drifting away from evidence, so every validation row update should cite the relevant passed verification report or fresh command. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:123-135]
- **Using `awaiting_human_verify` for closeout-complete debug sessions:** The scanner treats that status as open. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59]
- **Assuming `completed:` means quick-task complete:** The scanner ignores `completed:` unless `status: complete` is present in summary frontmatter. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145]
- **Editing `.planning/STATE.md` deferred items as the primary solution:** Deferral is an acknowledgement path in `/gsd-complete-milestone`, but Phase 09 success criteria require open blockers to be resolved, closed, or explicitly moved out of the v4.0 closeout path. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:59-75] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting closeout blockers | Custom grep over `.planning` | `gsd-sdk query audit-open` | The GSD milestone close workflow uses `audit-open` and its scanner predicates are explicit. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-80] |
| Deciding debug completion statuses | New status vocabulary | Existing `resolved` or `complete` statuses | The debug template and scanner already define valid lifecycle/non-open statuses. [VERIFIED: /home/prannayag/.claude/get-shit-done/templates/DEBUG.md:9-15] [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59] |
| Deciding quick-task completion semantics | New audit exemption file | `status: complete` in each quick-task summary frontmatter | The scanner explicitly reads summary frontmatter status and skips only `complete`. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145] |
| Reconstructing verification truth manually | New prose-only status narrative | Existing `*-VERIFICATION.md` reports and targeted pytest command evidence | Passed verification reports already contain score, status, evidence, and commands. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:1-16] |
| Closing milestone by bypassing audit | Manual milestone archive edits | `/gsd-complete-milestone` after `audit-open` is clean | The documented workflow gates closeout on open artifact audit first. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:40-80] |

**Key insight:** The dangerous part of this phase is not technical complexity; it is lying to the governance system by changing statuses without matching evidence. Use the scanner's rules and existing verification artifacts as the source of truth. [VERIFIED: local audit implementation and phase verification files]

## Current Artifact Inventory

| Artifact Category | Items Found | Current Blocking Reason | Planner Action |
|------------------|-------------|-------------------------|----------------|
| Stale validation metadata | Phase 1, 2, 3, and 6 `VALIDATION.md` files | v4.0 audit lists them as partial/stale despite later verification passing. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:123-141] | Update frontmatter, Wave 0 rows, task status rows, sign-off, and evidence text from matching `VERIFICATION.md` reports. |
| Debug sessions | `point-cloud-below-ground`, `point-cloud-rotation`, `voxel-becomes-pointcloud-closeup` | All three have `status: awaiting_human_verify`, which audit treats as open. [VERIFIED: `gsd-sdk query audit-open`] | Mark resolved only if existing resolution and verification text is sufficient, or move/document out of v4.0 closeout path. |
| Quick tasks | `260317-hat`, `260324-euj`, `260324-ffy`, `260324-gov`, `260324-hb0` | Summary files exist but lack `status: complete`, so audit reports `status: missing`/incomplete. [VERIFIED: `gsd-sdk query audit-open`; /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145] | Add `status: complete` to summary frontmatter when completion evidence is present. |

## Common Pitfalls

### Pitfall 1: Treating verification reports and validation plans as interchangeable

**What goes wrong:** A planner may overwrite validation strategy files wholesale with verification reports. [VERIFIED: local file roles]

**Why it happens:** Both files contain test commands and requirement maps, but `VALIDATION.md` is the sampling contract while `VERIFICATION.md` is the post-execution evidence report. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-VALIDATION.md:10-24] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-VERIFICATION.md:18-31]

**How to avoid:** Preserve the validation structure and only update stale status/frontmatter/checkbox/evidence rows. [VERIFIED: v4 audit describes stale metadata, not missing verification]

**Warning signs:** Large unrelated rewrites to `VALIDATION.md` files or removal of per-task validation maps. [VERIFIED: validation files contain per-task maps]

### Pitfall 2: Closing debug sessions without human-verification nuance

**What goes wrong:** Debug files get marked resolved even when they explicitly say manual visual verification is still needed. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/debug/voxel-becomes-pointcloud-closeup.md:47-52]

**Why it happens:** `audit-open` treats `awaiting_human_verify` as open, creating pressure to flip the status. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59]

**How to avoid:** For each debug file, use the existing `Resolution` section: if verification is automated and complete, mark `resolved`; if visual verification is genuinely pending, explicitly move it out of the v4.0 closeout path or document a deferred decision rather than pretending it is verified. [VERIFIED: debug files Resolution sections]

**Warning signs:** Status changes with no `updated` timestamp and no change to `Resolution.verification`. [VERIFIED: debug template requires updated timestamp and resolution fields]

### Pitfall 3: Adding `completed:` but not `status: complete` to quick summaries

**What goes wrong:** The summary looks complete to a human but still fails `audit-open`. [VERIFIED: current audit reports five quick tasks despite their summaries containing completion text]

**Why it happens:** The scanner checks `fm.status`, not `fm.completed`, when deciding quick-task completeness. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145]

**How to avoid:** Add `status: complete` in YAML frontmatter for each completed quick summary. [VERIFIED: scanner predicate]

**Warning signs:** `gsd-sdk query audit-open` still lists quick tasks after metadata edits. [VERIFIED: audit-open current behavior]

### Pitfall 4: Letting Phase 8 state leak into Phase 9 planning

**What goes wrong:** Planner assumes Phase 8 is unfinished because `ROADMAP.md` still has an older progress line while `STATE.md` says 8 completed phases and Phase 09 is current. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:270-271] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/STATE.md:9-15]

**Why it happens:** Roadmap progress text can lag after execution while phase artifacts may already exist. [VERIFIED: phase 08 verification and summaries found by file discovery]

**How to avoid:** Before execution, planner should query `gsd-sdk query roadmap.analyze` or inspect phase summaries/verification rather than relying on one stale progress table. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:82-94]

**Warning signs:** Plans that include Phase 8 controller seam work inside Phase 9 despite Phase 9's explicit governance-only success criteria. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:239-248]

## Code Examples

Verified patterns from local GSD sources:

### Debug session non-open status

```yaml
# Source: /home/prannayag/.claude/get-shit-done/templates/DEBUG.md and audit.cjs
status: resolved
trigger: "Point cloud voxels may not be rotated based on the robot dog's facing direction, causing voxels to be placed at incorrect world positions."
created: 2026-03-24T00:00:00Z
updated: 2026-05-03T00:00:00Z
```

The audit scanner ignores debug sessions only when `status` is `resolved` or `complete`. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59]

### Quick task complete status

```yaml
# Source: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs quick-task scanner
status: complete
phase: quick
plan: 260324-ffy
subsystem: frontend
```

The quick-task scanner skips a task only when summary frontmatter status equals `complete`. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145]

### Validation metadata after execution

```yaml
# Source: passed verification reports plus stale validation audit
status: passed
nyquist_compliant: true
wave_0_complete: true
```

Use this pattern only where the corresponding phase verification report has passed and Wave 0 rows are now backed by created tests or explicit evidence. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-VERIFICATION.md:1-16]

### Final closeout acceptance command

```bash
# Source: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md
gsd-sdk query audit-open
```

This command is the Phase 09 acceptance gate because the roadmap success criteria require no blocking open items. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Treat validation metadata as advisory after verification | Keep validation/Nyquist metadata consistent with passed verification evidence | Phase 09 cleanup scope was added after the 2026-05-02 v4 audit | Milestone closeout should not require acknowledging stale governance debt. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/STATE.md:71-78] |
| Leave open debug/quick artifacts to be acknowledged during milestone close | Repair, resolve, close, or move open artifacts before `/gsd-complete-milestone` | Phase 09 roadmap success criteria | `audit-open` should return no closeout blockers. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248] |
| Rely on human-readable completion prose | Use machine-readable frontmatter `status` values that scanner consumes | Current GSD audit implementation | Human-complete summaries can still block closeout if frontmatter is missing. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145] |

**Deprecated/outdated:**
- `awaiting_human_verify` as a closeout-ready debug status is not sufficient for milestone closure because the audit scanner reports it as open. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:56-59]
- Quick-task summaries without `status: complete` are not closeout-ready even when they contain `completed:` timestamps and self-check text. [VERIFIED: /home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs:126-145]
- Phase 6 `nyquist_compliant: false` is stale relative to its passed verification report and v4 audit note. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VALIDATION.md:1-8] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md:20]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

No `[ASSUMED]` claims are used in this research. [VERIFIED: this document]

## Open Questions (RESOLVED)

1. **Should `voxel-becomes-pointcloud-closeup` be marked resolved or explicitly deferred?** [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/debug/voxel-becomes-pointcloud-closeup.md:47-52]
   - What we know: The debug file has root cause, fix, changed files, and TypeScript compile verification. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/debug/voxel-becomes-pointcloud-closeup.md:47-52]
   - What was unclear: The file says manual visual verification in browser is still needed. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/debug/voxel-becomes-pointcloud-closeup.md:51]
   - RESOLVED: Plan 02 must not silently mark this artifact resolved. It must either require manual browser verification and record that evidence, or record an explicit out-of-v4 closeout disposition in `.planning/debug/voxel-becomes-pointcloud-closeup.md` before the final audit gate. [VERIFIED: audit scanner and roadmap success criteria]

2. **Should the quick-task scanner status be repaired in files only, or should STATE.md also be reconciled?** [VERIFIED: current STATE quick-task table and audit output]
   - What we know: `STATE.md` already lists some quick tasks as completed, while `audit-open` still reports the quick summary artifacts incomplete. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/STATE.md:86-96] [VERIFIED: `gsd-sdk query audit-open`]
   - What was unclear: `STATE.md` does not list `260317-hat`, but the quick artifact exists and audits as incomplete. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/quick/260317-hat-update-readme-md-with-proper-project-pla/260317-hat-SUMMARY.md:35-84]
   - RESOLVED: Repair quick-task summary frontmatter first because `audit-open` consumes `status: complete` from the summary files. Update `.planning/STATE.md` only if final audit/bookkeeping requires reconciliation; STATE edits are not the primary scanner fix. [VERIFIED: audit.cjs scanner]

3. **Should validation metadata updates include fresh pytest runs or cite existing verification reports only?** [VERIFIED: existing verification reports contain commands and pass results]
   - What we know: Phase 1, 2, 3, and 6 verification reports already passed with commands and evidence. [VERIFIED: corresponding `*-VERIFICATION.md` files]
   - What was unclear: The planner may choose to run current quick/full gates again to avoid relying on older evidence. [VERIFIED: current date and verification dates]
   - RESOLVED: Use the existing passed verification reports as the evidence source for metadata reconciliation, then run the final `gsd-sdk query audit-open` closeout gate. Fresh pytest is optional and should be run only if execution changes evidence claims rather than merely reconciling metadata. [VERIFIED: Environment Availability section]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `gsd-sdk` | `audit-open`, phase context, milestone close workflow | Yes | `v0.1.0` | None; this is the closeout gate tool. [VERIFIED: `gsd-sdk --version`] |
| `uv` | Project-supported test execution | Yes | `0.10.10` | Use existing verification reports if fresh tests are not required. [VERIFIED: `uv --version`] |
| `python` | Local CLI Python | Available but unsupported for project runtime | `3.14.4`; project requires `>=3.10,<3.13` | Use `uv run python` to resolve a supported interpreter/environment. [VERIFIED: `python --version`; /home/prannayag/pragnition/robotics/argus/pyproject.toml:5] |
| `pytest` | Test evidence | Yes | `9.0.2` | Use `uv run python -m pytest` for project-consistent execution. [VERIFIED: `pytest --version`] |
| `git` | Artifact change review | Yes | `2.54.0` | None needed. [VERIFIED: `git --version`] |

**Missing dependencies with no fallback:** None identified for metadata cleanup. [VERIFIED: environment probes]

**Missing dependencies with fallback:** Local `/usr/bin/python` is outside the project's declared range, but `uv` is available and has been used in Phase 6 verification. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml:5] [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md:90-92]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest; project dev extra declares `pytest>=8.0.0`; local CLI is `pytest 9.0.2`. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml:41-45] [VERIFIED: `pytest --version`] |
| Config file | `pyproject.toml` contains pytest marker configuration; `pytest.ini` also exists. [VERIFIED: /home/prannayag/pragnition/robotics/argus/pyproject.toml:47-52] [VERIFIED: file discovery] |
| Quick run command | `gsd-sdk query audit-open` for closeout artifacts; optional product sanity: `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_locomotion_evaluation_runner.py -q` [VERIFIED: current test files exist] |
| Full suite command | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` [VERIFIED: prior Phase 6 verification used this command and passed] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| LOC-ENV-01 | Env reset/step Gymnasium-style contract remains satisfied while validation metadata is repaired. [VERIFIED: requirement and verification report] | governance + regression | `gsd-sdk query audit-open`; optional `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q` | Yes [VERIFIED: file discovery] |
| LOC-CTRL-01 | Controller protocol/registry validation metadata reflects passed Phase 2 evidence. [VERIFIED: requirement and verification report] | governance + regression | `gsd-sdk query audit-open`; optional `uv run python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/locomotion/test_locomotion_controller_protocol.py -q` | Yes [VERIFIED: file discovery] |
| LOC-METRICS-01 | Command-tracking metrics validation metadata reflects passed Phase 3 evidence. [VERIFIED: requirement and verification report] | governance + regression | `gsd-sdk query audit-open`; optional `uv run python -m pytest tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_argus_go2_env_metrics.py -q` | Yes [VERIFIED: file discovery] |
| LOC-EVAL-01 | CLI evaluation runner validation metadata reflects passed Phase 6 evidence. [VERIFIED: requirement and verification report] | governance + regression | `gsd-sdk query audit-open`; optional `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` | Yes [VERIFIED: file discovery] |

### Sampling Rate

- **Per task commit:** Run `gsd-sdk query audit-open` after any batch that changes debug or quick artifacts. [VERIFIED: closeout workflow uses audit-open]
- **Per wave merge:** Run `gsd-sdk query audit-open` and inspect the four touched `VALIDATION.md` files for consistent frontmatter/status rows. [VERIFIED: Phase 09 success criteria]
- **Phase gate:** `gsd-sdk query audit-open` must report no open items that block milestone closure. [VERIFIED: /home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md:244-248]

### Wave 0 Gaps

- [ ] No new product test files are required for Phase 09 because all four referenced requirements already have existing tests and passed verification reports. [VERIFIED: `tests/locomotion` file discovery and phase verification reports]
- [ ] Add or update a planning-artifact checklist inside the Phase 09 plan so executor verifies every changed `VALIDATION.md`, debug file, and quick summary against `audit-open`. [VERIFIED: audit-open current output]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | Phase 09 edits planning metadata and does not add authentication flows. [VERIFIED: phase scope in ROADMAP.md:239-248] |
| V3 Session Management | No | Phase 09 does not add browser/server session behavior. [VERIFIED: phase scope in ROADMAP.md:239-248] |
| V4 Access Control | No | Phase 09 does not add authorization paths. [VERIFIED: phase scope in ROADMAP.md:239-248] |
| V5 Input Validation | Yes | Use `gsd-sdk query audit-open` structured output and existing sanitized scanner fields; do not inject raw unsanitized artifact content into STATE.md or closeout docs. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:77-80] |
| V6 Cryptography | No | Phase 09 does not add cryptographic behavior. [VERIFIED: phase scope in ROADMAP.md:239-248] |

### Known Threat Patterns for Planning Metadata Cleanup

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Raw artifact content injection into closeout documentation | Tampering | Use sanitized `audit-open` structured fields only when summarizing deferred or closed items. [VERIFIED: /home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md:77-80] |
| False status closure | Repudiation | Require matching resolution/evidence text and final `audit-open` output for every status change. [VERIFIED: debug template and audit scanner] |
| Scope creep into product code | Tampering | Treat Phase 09 as metadata/artifact cleanup unless a verification command proves a product regression requiring a separate bugfix. [VERIFIED: phase scope in ROADMAP.md:239-248] |
| Path confusion while editing artifacts | Tampering | Use absolute paths and GSD phase directory from `init.phase-op`; current phase dir is `.planning/phases/09-milestone-closeout-hygiene`. [VERIFIED: `gsd-sdk query init.phase-op "9"`] |

## Sources

### Primary (HIGH confidence)

- `/home/prannayag/pragnition/robotics/argus/.planning/ROADMAP.md` — Phase 09 scope, success criteria, and requirement IDs. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` — LOC requirement descriptions and traceability. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/STATE.md` — current milestone history and Phase 09 readiness context. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/v4.0-MILESTONE-AUDIT.md` — validation/Nyquist metadata debt and audit routing. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/01-locomotion-env-contract/01-VERIFICATION.md` — passed LOC-ENV evidence. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/02-controller-plugin-baseline/02-VERIFICATION.md` — passed LOC-CTRL evidence. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/03-locomotion-metrics-instrumentation/03-VERIFICATION.md` — passed LOC-METRICS evidence. [VERIFIED: file read]
- `/home/prannayag/pragnition/robotics/argus/.planning/phases/06-repair-evaluation-runner-semantics/06-VERIFICATION.md` — passed LOC-EVAL evidence. [VERIFIED: file read]
- `/home/prannayag/.claude/get-shit-done/bin/lib/audit.cjs` — actual `audit-open` scanner predicates. [VERIFIED: file read]
- `/home/prannayag/.claude/get-shit-done/workflows/complete-milestone.md` — milestone closeout pre-close audit workflow. [VERIFIED: file read]
- `gsd-sdk query audit-open` — current open artifact inventory. [VERIFIED: command output]

### Secondary (MEDIUM confidence)

- Project `CLAUDE.md` and `.claude/skills/desloppify/SKILL.md` — project instructions and code-health skill applicability. [VERIFIED: file read]
- `pyproject.toml`, `pytest.ini`, and test file discovery — current validation infrastructure. [VERIFIED: file read and file discovery]

### Tertiary (LOW confidence)

- None. [VERIFIED: this research]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tool versions and scanner behavior were verified locally. [VERIFIED: environment probes and audit.cjs]
- Architecture: HIGH — phase scope and closeout workflow are local GSD artifacts, not external library assumptions. [VERIFIED: ROADMAP.md and complete-milestone.md]
- Pitfalls: HIGH — each pitfall maps to an observed current blocker or scanner predicate. [VERIFIED: audit-open output and audit.cjs]

**Research date:** 2026-05-03 [VERIFIED: currentDate]
**Valid until:** 2026-06-02 for local governance scanner behavior, unless GSD tooling is upgraded before then. [VERIFIED: gsd-sdk version currently v0.1.0]
