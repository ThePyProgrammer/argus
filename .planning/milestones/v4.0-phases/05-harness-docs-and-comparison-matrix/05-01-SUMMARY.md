---
phase: 05-harness-docs-and-comparison-matrix
plan: 01
subsystem: documentation
tags: [locomotion, benchmark, markdown, pytest, controller-matrix]

requires:
  - phase: 04-evaluation-runner-and-regression
    provides: CLI evaluation runner, artifact exports, saved-run regeneration, and baseline regression behavior documented by this plan
provides:
  - Canonical locomotion benchmark harness guide
  - README command card linking to the guide
  - Hard-boundary controller-family support/deferred matrix
  - Pathlib-only Markdown content guards for documentation drift
affects: [locomotion, evaluation-runner, controller-registry, developer-onboarding]

tech-stack:
  added: []
  patterns: [canonical-docs-guide, readme-command-card, markdown-content-guards]

key-files:
  created:
    - docs/locomotion-benchmark.md
    - tests/test_locomotion_benchmark_docs.py
  modified:
    - README.md

key-decisions:
  - "Kept README as a terse command card and made docs/locomotion-benchmark.md the canonical harness guide."
  - "Documented unsupported controller families with hard unavailable/deferred statuses instead of aspirational support language."
  - "Kept Phase 5 verification as pathlib Markdown content guards, not MuJoCo or CLI execution."

patterns-established:
  - "Docs-first benchmark onboarding: README points to canonical guide, while the guide owns detailed workflow and support boundaries."
  - "Content guard tests assert durable tokens for commands, artifacts, rationale links, and support matrix entries."

requirements-completed: [LOC-REPORT-01, LOC-REPORT-02, LOC-REPORT-03]

duration: 4min 20s
completed: 2026-05-01
---

# Phase 05 Plan 01: Harness Docs and Comparison Matrix Summary

**Canonical locomotion benchmark guide with explicit smoke workflow, artifact glossary, controller-family boundary matrix, and pathlib-only Markdown drift guards**

## Performance

- **Duration:** 4min 20s
- **Started:** 2026-05-01T07:10:15Z
- **Completed:** 2026-05-01T07:14:35Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created `docs/locomotion-benchmark.md` as the canonical Phase 5 harness guide covering `ArgusGo2Env`, observation/action surfaces, reward/metric wording, scenarios, CLI workflows, regeneration, and artifacts.
- Added a hard-boundary controller-family matrix distinguishing supported `analytical_trot` from unavailable placeholders and deferred families, grounded in `outputs/locomotion-rd-systems.md` and ADR-0019.
- Updated `README.md` with a compact guide link, blessed smoke command, and artifact names without copying the full matrix.
- Added fast pathlib-only pytest content guards that read Markdown and assert required workflow, artifact, matrix, and rationale tokens.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the canonical harness guide core** - `836a2d2` (docs)
2. **Task 2: Add the hard-boundary matrix and README command card** - `960d2e4` (docs)
3. **Task 3 RED: Add failing benchmark docs content guards** - `4663615` (test)
4. **Task 3 GREEN: Make benchmark docs guards pass** - `219b935` (test)

_Note: Task 3 followed the requested TDD flow with RED and GREEN commits._

## Files Created/Modified

- `docs/locomotion-benchmark.md` - Canonical benchmark harness guide, CLI examples, artifact glossary, and controller-family support/deferred matrix.
- `README.md` - Compact locomotion benchmark pointer linking to the guide, retaining the blessed smoke command and naming artifacts.
- `tests/test_locomotion_benchmark_docs.py` - Pathlib-only Markdown content guards for README and guide drift.

## Verification

- `test -f docs/locomotion-benchmark.md && grep ...` checks from Task 1 passed.
- Matrix and README grep checks from Task 2 passed.
- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/test_locomotion_benchmark_docs.py -q` passed: 5 passed.
- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/test_locomotion_benchmark_docs.py /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/test_main_args.py -q` passed: 11 passed.
- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/locomotion /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/bridge/test_sim_bridge.py /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/bridge/test_multi_bridge.py /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/test_main_args.py /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a00632de5d967aa69/tests/test_locomotion_benchmark_docs.py -q` passed: 251 passed.

## Decisions Made

- Kept detailed benchmark documentation in `docs/locomotion-benchmark.md`; README remains a compact pointer to avoid duplicate, drifting guidance.
- Used exact hard-boundary status language for controller families: `supported now`, `registered placeholder unavailable`, and `deferred/no runnable v4.0 implementation`.
- Used token-based Markdown content guards instead of exact paragraph matching, so harmless prose edits do not break tests while required facts remain protected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed content guard case sensitivity and self-source false positive**
- **Found during:** Task 3 (Add pathlib-only Markdown content guards)
- **Issue:** The initial RED/GREEN test implementation checked lower-case metric tokens against mixed-case guide text and flagged its own assertion strings while checking for forbidden command-execution tokens.
- **Fix:** Normalized guide text for metric-token checks and constructed forbidden token strings from fragments so the source guard checks meaningful accidental usage rather than its own assertions.
- **Files modified:** `tests/test_locomotion_benchmark_docs.py`
- **Verification:** `5 passed` for `tests/test_locomotion_benchmark_docs.py`.
- **Committed in:** `219b935`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** The fix preserved the planned content-only guard behavior and did not add runtime benchmark execution.

## Known Stubs

The stub scan found intentional documentation references to unavailable placeholders:

| File | Line | Reason |
|------|------|--------|
| `docs/locomotion-benchmark.md` | 119-122 | Required hard-boundary matrix documents registered unavailable placeholder controller ids for residual RL, direct RL, MPC, and WBC. |
| `tests/test_locomotion_benchmark_docs.py` | 66 | Content guard asserts the required `registered placeholder unavailable` status token. |
| `README.md` | 311 | Existing README prose accurately describes unsupported future controller families as explicit placeholders. |

These are not implementation stubs blocking the plan goal; they are the planned LOC-REPORT-02 support-boundary documentation.

## Threat Flags

None. The plan added documentation and Markdown-reading tests only; it introduced no new network endpoints, auth paths, file access beyond repository Markdown content, or trust-boundary schema changes.

## Issues Encountered

- The worktree does not contain its own `.venv`, so verification used the project virtualenv at `/home/prannayag/pragnition/robotics/argus/.venv/bin/python` against absolute worktree test paths.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 5 documentation is ready for orchestrator merge and central state/roadmap updates. The guide, README pointer, and content guards now cover LOC-REPORT-01, LOC-REPORT-02, and LOC-REPORT-03.

## Self-Check: PASSED

- Found `docs/locomotion-benchmark.md`
- Found `README.md`
- Found `tests/test_locomotion_benchmark_docs.py`
- Found `.planning/phases/05-harness-docs-and-comparison-matrix/05-01-SUMMARY.md`
- Found task commits `836a2d2`, `960d2e4`, `4663615`, and `219b935`

---
*Phase: 05-harness-docs-and-comparison-matrix*
*Completed: 2026-05-01*
