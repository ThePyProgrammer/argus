---
phase: 05-harness-docs-and-comparison-matrix
verified: 2026-05-01T07:26:28Z
status: gaps_found
score: 6/7 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The controller-family matrix includes concrete controller ids/placeholders and seams that match the actual codebase."
    status: partial
    reason: "The guide documents residual_policy as using the residual_baseline action-mode seam, but ControllerRegistry metadata for ResidualPolicyController advertises residual_joint_position, which is not one of the environment action modes. This leaves the future residual-controller boundary internally inconsistent."
    artifacts:
      - path: "docs/locomotion-benchmark.md"
        issue: "Residual RL matrix row says residual_policy uses residual_baseline."
      - path: "src/locomotion/controllers.py"
        issue: "ResidualPolicyController CAPABILITIES uses action_mode residual_joint_position."
      - path: "src/locomotion/actions.py"
        issue: "Registered environment action modes are velocity_command, joint_position, and residual_baseline; residual_joint_position is not available."
      - path: "tests/test_locomotion_benchmark_docs.py"
        issue: "Content guard only asserts tokens and does not catch the residual-policy action-mode mismatch."
    missing:
      - "Align the residual placeholder capability metadata with the documented public seam, or update the guide to document the actual supported vocabulary."
      - "Add a documentation guard or controller-metadata assertion that residual_policy documentation and implementation use the same action-mode string."
---

# Phase 5: Harness Docs and Comparison Matrix Verification Report

**Phase Goal:** Document the benchmark harness and make the supported/deferred controller-family boundary explicit for future locomotion work.
**Verified:** 2026-05-01T07:26:28Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A concise harness guide explains observation space, action modes, reward/metric definitions, scenario catalog, and CLI evaluation workflow. | VERIFIED | `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` contains `qpos`, `qvel`, `command`, `previous_action`, the three environment action modes, reward `0.0` wording, metric families, all five scenario ids, the smoke command, `--matrix-config`, `--from-run-dir`, and artifact descriptions. |
| 2 | A controller-family matrix states supported now versus deferred for analytical gait, residual RL, direct RL, MPC, WBC, ROS/hardware, and perception-conditioned locomotion. | FAILED | The required family/status rows exist, but the residual RL seam is not accurate against the implementation: the guide says `residual_baseline`; `ResidualPolicyController` metadata says `residual_joint_position`; `src/locomotion/actions.py` does not expose `residual_joint_position` as an action mode. |
| 3 | The documentation links `outputs/locomotion-rd-systems.md` as the rationale for v4 scope and accurately summarizes the current Argus method as analytical trot + MuJoCo position actuators. | VERIFIED | Guide lines 5-7 and matrix rows link `outputs/locomotion-rd-systems.md` and ADR-0019 and state: `Current Argus locomotion is analytical trot plus MuJoCo position actuators.` |
| 4 | A new developer can run the flat-ground analytical baseline smoke benchmark from the guide without reading the implementation first. | VERIFIED | Guide includes `uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202` with context explaining controller, scenario, seeds, and output directory. README repeats the command and links the guide. |
| 5 | README exposes the guide link, explicit flat-ground analytical smoke command, and artifact names. | VERIFIED | `/home/prannayag/pragnition/robotics/argus/README.md` links `docs/locomotion-benchmark.md`, includes the blessed command, and names `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md`. |
| 6 | The guide includes JSON matrix-config and saved-run regeneration examples plus output location and artifact purposes. | VERIFIED | Guide contains the required JSON matrix example, `uv run argus eval-locomotion --matrix-config path/to/matrix.json`, `uv run argus eval-locomotion --from-run-dir outputs/locomotion-evals/<timestamp>/`, and an artifact glossary. |
| 7 | Markdown content guards read Markdown, assert required guide/README/artifact/matrix/rationale tokens, and do not execute MuJoCo or the benchmark command. | VERIFIED | `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` uses pathlib `read_text` against README/guide and the spot-check passed: `5 passed`. The source guard constructs forbidden tokens and does not import subprocess. |

**Score:** 6/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | Canonical locomotion benchmark harness guide and controller-family matrix | PARTIAL | Exists and is substantive. It covers the required guide material, but the residual-policy matrix seam conflicts with controller metadata. |
| `/home/prannayag/pragnition/robotics/argus/README.md` | Compact locomotion benchmark command card and guide link | VERIFIED | Exists, links the canonical guide, contains the smoke command and artifact names, and does not duplicate the full matrix. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` | Pathlib-only Markdown content guards | VERIFIED | Exists, substantive, reads Markdown via pathlib, and passed under the configured virtualenv. Coverage is token-based and should be extended for the residual seam mismatch. |

Artifact verification via `gsd-sdk query verify.artifacts /home/prannayag/pragnition/robotics/argus/.planning/phases/05-harness-docs-and-comparison-matrix/05-01-PLAN.md` reported 3/3 planned artifacts present and non-stub. Manual goal-backward verification downgraded the guide to PARTIAL because one documented seam is contradicted by implementation metadata.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| README.md | docs/locomotion-benchmark.md | Markdown guide link | WIRED | `gsd-sdk query verify.key-links` found the required pattern. |
| docs/locomotion-benchmark.md | outputs/locomotion-rd-systems.md | R&D rationale link | WIRED | Required rationale path appears in guide prose and matrix rows. |
| docs/locomotion-benchmark.md | docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md | ADR-0019 scope rationale link | WIRED | Required ADR path appears in guide prose and matrix rows. |
| tests/test_locomotion_benchmark_docs.py | docs/locomotion-benchmark.md | pathlib read_text content assertions | WIRED | Test file defines `GUIDE` and reads it with `GUIDE.read_text`. |
| tests/test_locomotion_benchmark_docs.py | README.md | pathlib read_text content assertions | WIRED | Test file defines `README` and reads it with `README.read_text`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| docs/locomotion-benchmark.md | Documentation facts | Static Markdown cross-checked against `src/locomotion/actions.py` and `src/locomotion/controllers.py` | PARTIAL | Most documented constants match implementation; residual-policy seam does not. |
| README.md | Documentation facts | Static Markdown linking canonical guide | Yes for README scope | VERIFIED |
| tests/test_locomotion_benchmark_docs.py | Markdown text | `Path.read_text` from README and guide | Yes | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Markdown content guards pass without running MuJoCo benchmark | `cd /home/prannayag/pragnition/robotics/argus && .venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py -q` | `5 passed in 3.33s` | PASS |
| Controller/action metadata matches residual seam documentation | `cd /home/prannayag/pragnition/robotics/argus && .venv/bin/python - <<'PY' ... ControllerRegistry.list_controllers()` | action modes: `['joint_position', 'residual_baseline', 'velocity_command']`; `residual_policy False residual_joint_position` | FAIL |
| Requirement IDs appear in PLAN frontmatter and REQUIREMENTS.md | Python text check for `LOC-REPORT-01`, `LOC-REPORT-02`, `LOC-REPORT-03` | All three IDs found in both files | PASS |

The user-provided regression-gate context says the fresh fallback environment run passed with 1043 passed, 13 skipped, 8 deselected, and schema drift reported `drift_detected=false`. I did not treat that SUMMARY-adjacent claim as proof of the documentation seam; I checked the relevant code and Markdown directly.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOC-REPORT-01 | 05-01-PLAN.md | Developer can read a concise harness guide explaining observation space, action modes, reward/metric definitions, and scenario catalog. | SATISFIED | Guide covers observation keys, action modes, reward `0.0`, metric families, scenario catalog, CLI workflows, and artifacts. |
| LOC-REPORT-02 | 05-01-PLAN.md | Developer can see an explicit comparison matrix explaining which controller families are supported now versus intentionally deferred. | BLOCKED | Matrix exists with all required families/statuses, but the residual RL seam conflicts with implementation metadata, so the supported/deferred boundary is not fully accurate. |
| LOC-REPORT-03 | 05-01-PLAN.md | Developer can use the final report from `outputs/locomotion-rd-systems.md` as the rationale link for milestone scope. | SATISFIED | Guide links `outputs/locomotion-rd-systems.md` in rationale prose and matrix rows; it also links ADR-0019 and states the current method accurately. |

Orphaned Phase 5 requirements: none. `.planning/REQUIREMENTS.md` maps exactly LOC-REPORT-01, LOC-REPORT-02, and LOC-REPORT-03 to Phase 5, and all three are declared in the plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | 119-122 | `registered placeholder unavailable` / `Placeholder exists` | INFO | Intentional support-boundary wording required by LOC-REPORT-02; not a stub by itself. |
| `/home/prannayag/pragnition/robotics/argus/README.md` | 311 | `explicit placeholders` | INFO | Intentional README phrasing that unsupported controller families are placeholders. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` | 66 | `registered placeholder unavailable` | INFO | Content guard token for required matrix status. |

No TODO/FIXME/empty implementation blocker was found in the three phase files. The blocker is not placeholder wording; it is the residual action-mode seam mismatch between documentation and implementation metadata.

### Human Verification Required

None. This phase is documentation plus content guards; the decisive gap is statically observable in Markdown and Python metadata. Visual/manual review is optional but not needed to classify the phase.

### Gaps Summary

Phase 5 is close but not complete. The guide, README pointer, rationale links, smoke command, artifacts, and Markdown guards exist and work. However, the phase goal is specifically to make the supported/deferred controller-family boundary explicit for future locomotion work. The residual-policy row currently documents a seam (`residual_baseline`) that does not match the registered placeholder capability (`residual_joint_position`), and `residual_joint_position` is not an environment action mode. That turns the future residual-controller boundary into a contradictory instruction rather than an explicit boundary.

This matches the warning in `/home/prannayag/pragnition/robotics/argus/.planning/phases/05-harness-docs-and-comparison-matrix/05-REVIEW.md`, and it blocks LOC-REPORT-02 until the documentation and implementation vocabulary are aligned or an explicit override is accepted.

---

_Verified: 2026-05-01T07:26:28Z_
_Verifier: Claude (gsd-verifier)_
