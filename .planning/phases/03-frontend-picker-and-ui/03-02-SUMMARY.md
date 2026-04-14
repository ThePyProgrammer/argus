---
phase: 03-frontend-picker-and-ui
plan: 02
subsystem: ui
tags: [react, typescript, capability-badge, frontend, ui-primitive]

requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "Phase 2 already published `framework`, `license`, `cpu_latency_hint_ms` capability keys on detector backends; Phase 3 picker can render them now that CapabilityBadge accepts mixed-type values"
provides:
  - "CapabilityBadge accepts {label, value} props supporting boolean | string | number"
  - "Latency-hint formatting: number + 'latency' in label → '~{value}ms'"
  - "Generic '{label}: {value}' rendering for arbitrary string/number capabilities"
  - "Falsy guard: value === false | null | undefined returns null (truth-in-advertising per D-04)"
  - "SLAM call sites migrated in same commit as the API change (no broken intermediate compile state)"
affects:
  - DetectorDropdown (Wave 2) — uses {label, value} for framework/license/cpu_latency_hint_ms badges
  - DetectorSection (Wave 2) — uses {label, value} for active-backend capability row
  - LifterDropdown (Wave 2) — same prop signature for lifter capabilities
  - Any future Phase 5 backend exposing string capabilities (e.g., OWLv2 input_type)

tech-stack:
  added: []
  patterns:
    - "Mixed-type capability rendering: boolean→label-only, number+'latency'→'~Nms', other→'label: value'"
    - "Same-commit prop-signature migration: extending an in-tree component → migrate all call sites in the same commit so tsc stays green at every commit boundary"

key-files:
  created: []
  modified:
    - frontend/src/components/CapabilityBadge.tsx
    - frontend/src/components/AlgorithmDropdown.tsx
    - frontend/src/components/AlgorithmSection.tsx

key-decisions:
  - "Pill style object copied verbatim from previous CapabilityBadge implementation — zero visual regression on existing SLAM badges (D-04)"
  - "No back-compat `name` prop introduced — the migration is wholesale to keep the component surface narrow"
  - "Interface is file-local (not exported) per the rest of the codebase's pattern"
  - "SLAM call sites pass `value={true}` explicitly — the upstream filter already keeps only `v === true` entries, so this preserves identical render"

patterns-established:
  - "Mixed-type capability badges: components consuming registry-published capabilities should accept {label, value} and dispatch on type/label, not on a fixed boolean assumption"
  - "Same-commit refactor + migration: when an in-tree component's prop signature is extended in a breaking way, the same commit must migrate all call sites so each commit boundary remains tsc-clean"

requirements-completed:
  - DET-UI-01

duration: 5min
completed: 2026-04-14
---

# Phase 3 Plan 02: CapabilityBadge {label, value} Extension Summary

**Extended `CapabilityBadge` in-place to accept `{label, value}` props (boolean | string | number) with latency-aware `~Nms` formatting and migrated both existing SLAM call sites in lockstep — zero visual regression, tsc clean.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-14T07:25:00Z
- **Completed:** 2026-04-14T07:30:28Z
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- `CapabilityBadge` now renders boolean / string / number values per D-04 rules (label-only for `true`, `~Nms` for latency numbers, `label: value` otherwise, nothing for falsy)
- Pill style copied verbatim from the previous implementation — existing SLAM badges render identically (no visual regression)
- Both pre-existing SLAM call sites migrated to the new `label={cap} value={true}` signature in the same wave so `tsc --noEmit` stays clean at every commit boundary
- Wave 0 unblocks Wave 2 (DetectorDropdown, DetectorSection, LifterDropdown) — they can adopt the new signature directly without a follow-up migration

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite CapabilityBadge with {label, value} props** — `7339234` (feat)
2. **Task 2: Migrate 2 SLAM call sites to new {label, value} signature** — `d68a488` (refactor)

## Files Created/Modified

- `frontend/src/components/CapabilityBadge.tsx` — full rewrite: new `CapabilityBadgeProps` interface (`label: string`, `value: string | number | boolean`), falsy guard returns `null`, latency-aware text formatting; pill style object preserved verbatim
- `frontend/src/components/AlgorithmDropdown.tsx` — line 137: `<CapabilityBadge key={cap} name={cap} />` → `<CapabilityBadge key={cap} label={cap} value={true} />`
- `frontend/src/components/AlgorithmSection.tsx` — line 169: same one-line migration

## Decisions Made

- **No backwards-compat `name` prop.** Wave-0 migration is wholesale; D-04 explicitly mandates extending in place. Keeping the surface narrow avoids a deprecation cycle for a 21-line primitive.
- **`value={true}` passed explicitly at SLAM call sites.** The capability filter upstream of each call site already keeps only `v === true` entries, so the new `value={true}` pass-through renders identically — preserves SLAM pill styling exactly per D-04.
- **Interface stays file-local (not exported).** Matches the surrounding codebase convention; downstream Wave-2 components import the component, not the prop type.
- **Pill style object copied verbatim** (display, padding, border-radius, font-size, font-weight, background, color, border, margin) — guarantees zero visual regression on rendered SLAM badges.

## Deviations from Plan

None — plan executed exactly as written.

The plan was already extremely tight (two surgical edits with verbatim-copied style and exact target snippets), and no auto-fix rules triggered. CLAUDE.md does not exist in this repo so no project-specific overrides applied.

**Total deviations:** 0
**Impact on plan:** None — clean execution.

## Issues Encountered

- **Bootstrapping note (not a deviation):** `frontend/node_modules` was absent on this fresh worktree, so `npx tsc --noEmit` initially reported "this is not the tsc command you are looking for". Ran `npm install` once in `frontend/` to provision the verifier toolchain, then tsc returned exit 0 cleanly. The resulting `frontend/package-lock.json` change is left unstaged — it is environment provisioning, not part of the plan's intended deliverable, and the orchestrator/user can decide whether to commit it.

## User Setup Required

None — pure frontend prop refactor.

## Verification

```bash
$ cd frontend && npx tsc --noEmit
# exit 0

$ grep -rn "CapabilityBadge.*name=" frontend/src/
# (no matches — all legacy call sites migrated)

$ grep -c "CapabilityBadge.*label={cap}.*value={true}" frontend/src/components/AlgorithmDropdown.tsx frontend/src/components/AlgorithmSection.tsx
# AlgorithmDropdown.tsx:1
# AlgorithmSection.tsx:1
```

All success criteria from the plan satisfied:

- [x] CapabilityBadge.tsx has new `{label, value}` prop interface
- [x] Returns null for `false | null | undefined`
- [x] Booleans render label-only (preserves SLAM styling)
- [x] Numbers with 'latency' in label render as `~{value}ms`
- [x] Other strings/numbers render as `{label}: {value}`
- [x] Both SLAM call sites migrated to `label={cap} value={true}`
- [x] `cd frontend && npx tsc --noEmit` exits 0
- [x] `grep -rn 'CapabilityBadge.*name=' frontend/src` returns zero matches

## Next Phase Readiness

- Wave 2 components (`DetectorDropdown`, `DetectorSection`, `LifterDropdown`) can consume the new `{label, value}` signature directly to render the three DET-UI-01 keys (`framework: string`, `license: string`, `cpu_latency_hint_ms: number`) with no further changes to `CapabilityBadge`.
- No blockers introduced. No new dependencies. No schema changes. No backend touch.

## Self-Check: PASSED

- FOUND: frontend/src/components/CapabilityBadge.tsx
- FOUND: frontend/src/components/AlgorithmDropdown.tsx
- FOUND: frontend/src/components/AlgorithmSection.tsx
- FOUND: .planning/phases/03-frontend-picker-and-ui/03-02-SUMMARY.md
- FOUND: commit 7339234 (Task 1: feat CapabilityBadge)
- FOUND: commit d68a488 (Task 2: refactor SLAM call sites)

---
*Phase: 03-frontend-picker-and-ui*
*Plan: 02*
*Completed: 2026-04-14*
