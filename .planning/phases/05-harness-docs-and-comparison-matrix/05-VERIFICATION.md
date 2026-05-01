---
phase: 05-harness-docs-and-comparison-matrix
verified: 2026-05-01T16:18:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/7
  gaps_closed:
    - "The residual-policy controller-family seam now matches across docs, ControllerRegistry metadata, and public action-mode vocabulary."
  gaps_remaining: []
  regressions: []
---

# Phase 5: Harness Docs and Comparison Matrix Verification Report

**Phase Goal:** Document the benchmark harness and make the supported/deferred controller-family boundary explicit for future locomotion work.
**Verified:** 2026-05-01T16:18:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A concise harness guide explains observation space, action modes, reward/metric definitions, scenario catalog, and CLI evaluation workflow. | VERIFIED | `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` covers the smoke command, Gymnasium reset/step surface, observation keys `qpos`, `qvel`, `command`, `previous_action`, action modes `velocity_command`, `joint_position`, `residual_baseline`, reward `0.0`, metric families, all five scenario ids, matrix-config workflow, saved-run regeneration, and artifacts. |
| 2 | A controller-family matrix states supported now versus deferred for analytical gait, residual RL, direct RL, MPC, WBC, ROS/hardware, and perception-conditioned locomotion. | VERIFIED | The guide contains the required matrix header and rows for all seven families with `supported now`, `registered placeholder unavailable`, or `deferred/no runnable v4.0 implementation`. The previous residual seam mismatch is closed: `src/locomotion/controllers.py` now has `_placeholder_capabilities("residual_policy", "residual_baseline")`, and the guide row says `residual-over-baseline seam via `residual_baseline` action mode`. |
| 3 | The documentation links `outputs/locomotion-rd-systems.md` as the rationale for v4 scope and accurately summarizes the current Argus method as analytical trot + MuJoCo position actuators. | VERIFIED | The guide links `outputs/locomotion-rd-systems.md` and `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` and states exactly: `Current Argus locomotion is analytical trot plus MuJoCo position actuators.` |
| 4 | A new developer can run the flat-ground analytical baseline smoke benchmark from the guide without reading the implementation first. | VERIFIED | The guide and README both contain `uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202`; the guide explains the supported `analytical_trot` controller, `flat_ground` scenario, seeds `101` and `202`, and output directory. |
| 5 | README exposes the guide link, explicit flat-ground analytical smoke command, and artifact names. | VERIFIED | `/home/prannayag/pragnition/robotics/argus/README.md` links `docs/locomotion-benchmark.md`, includes the blessed smoke command, and names `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md`. |
| 6 | The guide includes JSON matrix-config and saved-run regeneration examples plus output location and artifact purposes. | VERIFIED | The guide includes the required JSON matrix-config example, `uv run argus eval-locomotion --matrix-config path/to/matrix.json`, `uv run argus eval-locomotion --from-run-dir outputs/locomotion-evals/<timestamp>/`, output directory `outputs/locomotion-evals/<timestamp>/`, and artifact glossary. |
| 7 | Markdown content guards read Markdown, assert required guide/README/artifact/matrix/rationale tokens, cross-check residual-policy metadata, and do not execute MuJoCo or the benchmark command. | VERIFIED | `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` uses pathlib `read_text`, includes `test_residual_policy_documentation_matches_registry_action_mode`, imports `ControllerRegistry` and `available_action_modes` inside that metadata/string test, and source guard prohibits command/runtime execution tokens. Spot-check passed: `18 passed`. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | Canonical locomotion benchmark harness guide and controller-family matrix | VERIFIED | Exists, substantive, contains the guide material, exact smoke command, matrix examples, artifact glossary, rationale links, current-method sentence, and controller-family matrix. Residual row now matches registry metadata. |
| `/home/prannayag/pragnition/robotics/argus/README.md` | Compact locomotion benchmark command card and guide link | VERIFIED | Exists, remains compact, links the guide, includes the smoke command, and names all five evaluation artifacts without duplicating the full matrix. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` | Pathlib-only Markdown content guards | VERIFIED | Exists, substantive, reads README/guide via `Path.read_text`, checks required tokens, includes residual registry/doc cross-check, and avoids subprocess or benchmark execution. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py` | Residual placeholder capability metadata aligned to public residual-over-baseline seam | VERIFIED | `ResidualPolicyController.CAPABILITIES` uses `_placeholder_capabilities("residual_policy", "residual_baseline")`; registry spot-check confirms `residual_policy.available=False` and `action_mode=residual_baseline`. |
| `/home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_controller_registry.py` | Registry regression check for residual placeholder action-mode vocabulary | VERIFIED | Contains `test_residual_placeholder_advertises_public_residual_baseline_action_mode`, asserts `action_mode == "residual_baseline"`, membership in `available_action_modes()`, and unavailable status. |

`gsd-sdk query verify.artifacts` reported all artifacts passing for both `/home/prannayag/pragnition/robotics/argus/.planning/phases/05-harness-docs-and-comparison-matrix/05-01-PLAN.md` and `/home/prannayag/pragnition/robotics/argus/.planning/phases/05-harness-docs-and-comparison-matrix/05-02-PLAN.md`.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| README.md | docs/locomotion-benchmark.md | Markdown guide link | WIRED | `gsd-sdk query verify.key-links` found `docs/locomotion-benchmark.md` in README. |
| docs/locomotion-benchmark.md | outputs/locomotion-rd-systems.md | R&D rationale link | WIRED | Required rationale path appears in guide prose and matrix rows. |
| docs/locomotion-benchmark.md | docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md | ADR-0019 scope rationale link | WIRED | Required ADR path appears in guide prose and matrix rows. |
| tests/test_locomotion_benchmark_docs.py | docs/locomotion-benchmark.md | pathlib read_text content assertions | WIRED | Test file defines `GUIDE` and reads it with `GUIDE.read_text`. |
| tests/test_locomotion_benchmark_docs.py | README.md | pathlib read_text content assertions | WIRED | Test file defines `README` and reads it with `README.read_text`. |
| src/locomotion/controllers.py | src/locomotion/actions.py | residual_policy capability action_mode uses available action-mode vocabulary | WIRED | Registry spot-check verifies `residual_policy` action mode is `residual_baseline` and it appears in `available_action_modes()`. |
| tests/locomotion/test_locomotion_controller_registry.py | src/locomotion/controllers.py | ControllerRegistry residual_policy metadata assertion | WIRED | Test reads `ControllerRegistry.list_controllers()` and asserts residual metadata. |
| tests/test_locomotion_benchmark_docs.py | docs/locomotion-benchmark.md | guide text assertion for residual_policy row | WIRED | Test reads guide text and asserts the residual row phrase using the registry-derived action mode. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| docs/locomotion-benchmark.md | Documentation facts | Static Markdown cross-checked against `src/locomotion/actions.py` and `src/locomotion/controllers.py` | Yes | VERIFIED |
| README.md | Documentation facts | Static Markdown linking canonical guide | Yes for README scope | VERIFIED |
| tests/test_locomotion_benchmark_docs.py | Markdown text and residual registry metadata | `README.read_text`, `GUIDE.read_text`, `ControllerRegistry.list_controllers()`, `available_action_modes()` | Yes | VERIFIED |
| tests/locomotion/test_locomotion_controller_registry.py | Residual metadata | `ControllerRegistry.list_controllers()` and `available_action_modes()` | Yes | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Documentation and registry guards pass | `cd /home/prannayag/pragnition/robotics/argus && /home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/test_locomotion_benchmark_docs.py tests/locomotion/test_locomotion_controller_registry.py -q` | `18 passed in 3.62s` | PASS |
| Residual placeholder remains unavailable while advertising public residual seam | Python snippet importing `available_action_modes`, `ControllerRegistry`, and `UnavailableControllerError` | `action_modes= ['joint_position', 'residual_baseline', 'velocity_command']`; `residual_policy.available= False`; `residual_policy.action_mode= residual_baseline`; create raises `UnavailableControllerError` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOC-REPORT-01 | 05-01-PLAN.md | Developer can read a concise harness guide explaining observation space, action modes, reward/metric definitions, and scenario catalog. | SATISFIED | Guide covers observation keys, action modes, reward `0.0`, metric families, scenario catalog, CLI workflows, and artifacts. |
| LOC-REPORT-02 | 05-01-PLAN.md, 05-02-PLAN.md | Developer can see an explicit comparison matrix explaining which controller families are supported now versus intentionally deferred. | SATISFIED | Matrix exists with all required families/statuses. The previous residual RL seam mismatch is fixed in both registry metadata and doc guard coverage. |
| LOC-REPORT-03 | 05-01-PLAN.md | Developer can use the final report from `outputs/locomotion-rd-systems.md` as the rationale link for milestone scope. | SATISFIED | Guide links `outputs/locomotion-rd-systems.md` in rationale prose and matrix rows; it also links ADR-0019 and states the current method accurately. |

Orphaned Phase 5 requirements: none. `/home/prannayag/pragnition/robotics/argus/.planning/REQUIREMENTS.md` maps exactly LOC-REPORT-01, LOC-REPORT-02, and LOC-REPORT-03 to Phase 5, and the plan frontmatter accounts for them.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `/home/prannayag/pragnition/robotics/argus/docs/locomotion-benchmark.md` | 119-122 | `registered placeholder unavailable` / `Placeholder exists` | INFO | Intentional support-boundary wording required by LOC-REPORT-02; not a blocker. |
| `/home/prannayag/pragnition/robotics/argus/README.md` | 311 | `explicit placeholders` | INFO | Intentional README phrasing that unsupported controller families are placeholders. |
| `/home/prannayag/pragnition/robotics/argus/src/locomotion/controllers.py` | 376, 381, 451, 464, 469, 475, 481, 487 | Placeholder capability helpers and unavailable placeholder metadata | INFO | Intentional controller registry seam from Phase 2/5; placeholders remain unavailable by design and are tested as such. |
| `/home/prannayag/pragnition/robotics/argus/tests/test_locomotion_benchmark_docs.py` | 66 | `registered placeholder unavailable` | INFO | Content guard token for required matrix status. |

No TODO/FIXME/empty implementation blocker was found in the phase files. The placeholder language is the explicit support/deferred boundary, not an accidental stub.

### Human Verification Required

None. This phase is documentation plus metadata/content guards; the decisive claims are statically observable and covered by fast pytest checks.

### Gaps Summary

No blocking gaps remain. The prior verification gap was real: the guide claimed the residual-policy seam was `residual_baseline` while registry metadata advertised `residual_joint_position`. That is now closed. The codebase evidence shows one consistent residual boundary across the guide, `ControllerRegistry` metadata, public action-mode vocabulary, and regression guards.

---

_Verified: 2026-05-01T16:18:00Z_
_Verifier: Claude (gsd-verifier)_
