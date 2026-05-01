# Phase 5: harness-docs-and-comparison-matrix - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Document the completed v4.0 locomotion benchmark harness so a new developer can understand the Gymnasium-style environment, observation/action/reward/metric surfaces, scenario catalog, CLI evaluation workflow, saved artifacts, and controller-family support boundary. Phase 5 may add documentation and lightweight documentation-content tests only; it must not implement new controller families, change harness semantics, add frontend visualization, run training, add MPC/WBC/ROS/hardware behavior, or rework the Phase 4 evaluation runner beyond documentation-driven fixes if planning finds a factual mismatch.

</domain>

<decisions>
## Implementation Decisions

### Guide Placement
- **D-01:** Create a focused `docs/locomotion-benchmark.md` harness guide as the canonical user-facing document for Phase 5.
- **D-02:** Add a short README command card that links to `docs/locomotion-benchmark.md`, shows the blessed smoke benchmark command, and names the main artifact outputs. Do not turn the already-long README into the full guide.

### Smoke Benchmark Workflow
- **D-03:** The guide's first runnable benchmark must use explicit flags so defaults are visible: `uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202`.
- **D-04:** After the blessed smoke command, include one JSON matrix-config example and one saved-run regeneration example using `--from-run-dir`.
- **D-05:** The guide must explain where outputs land and what each artifact is for: `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md` under `outputs/locomotion-evals/<timestamp>/`.

### Controller-Family Matrix
- **D-06:** Use hard-boundary language in the controller-family matrix: analytical gait is supported now; residual RL, direct RL, MPC, WBC, ROS/hardware, and perception-conditioned locomotion are deferred/unavailable in v4.0 unless the code already exposes a placeholder seam.
- **D-07:** The matrix columns should be: controller family, status now, Argus hook/seam, why supported/deferred, prerequisite to unlock, and R&D rationale link.
- **D-08:** Include concrete controller ids/placeholders where they exist, current action modes/seams, and the `argus eval-locomotion` path. Avoid listing every internal class/function name in the matrix; implementation detail references belong in prose or canonical refs, not brittle table cells.
- **D-09:** The matrix must accurately summarize the current Argus method as analytical trot plus MuJoCo position actuators, grounded in `outputs/locomotion-rd-systems.md` and ADR-0019.

### Documentation Verification
- **D-10:** Add lightweight pytest-based documentation checks under `tests/` that read Markdown files and assert required content exists.
- **D-11:** The doc checks should assert at minimum: the README links the harness guide; the guide includes the explicit smoke command; artifact names are documented; the controller-family matrix includes analytical gait, residual RL, direct RL, MPC, WBC, ROS/hardware, and perception-conditioned locomotion; and `outputs/locomotion-rd-systems.md` is linked as rationale.
- **D-12:** Do not make documentation tests execute the smoke benchmark. Runtime benchmark behavior is already covered by Phase 4 evaluation tests and the baseline regression gate; Phase 5 checks should remain fast content guards.

### Claude's Discretion
- Exact section titles, prose tone, Markdown table formatting, test filename, and exact assert strings are open to planner/executor discretion, provided the guide stays concise, the README remains a short pointer, and the hard support/deferred boundary remains unambiguous.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 5 — Defines harness-docs-and-comparison-matrix goal, dependencies, success criteria, and light research flag.
- `.planning/REQUIREMENTS.md` §LOC-REPORT — Defines LOC-REPORT-01 through LOC-REPORT-03: harness guide, controller-family comparison matrix, and R&D rationale link.
- `.planning/PROJECT.md` §Current Milestone / Key Decisions — Locks benchmark-before-controller-sophistication, analytical trot baseline, metrics-first evaluation, future-controller seams, and CLI/docs-first benchmark scope.
- `.planning/STATE.md` §Accumulated Context — Captures current v4.0 state, locked benchmark decisions, and simulation/position-actuator constraints.

### Prior phase decisions
- `.planning/phases/04-evaluation-runner-and-regression/04-CONTEXT.md` — Locks CLI shape, matrix flags/config, export layout, comparison artifacts, metric direction labels, and regression gate behavior that the docs must describe accurately.
- `.planning/phases/03-locomotion-metrics-instrumentation/03-CONTEXT.md` — Locks metric surface, metric family names, failure semantics, action-quality proxy labels, and contact/terrain proxy expectations.
- `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md` — Locks controller registry, analytical baseline, placeholder unavailable semantics, controller metadata, and deferred controller-family boundaries.

### Architecture decisions and rationale
- `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` — ADR for Gymnasium harness, named scenarios, deterministic seeds, controller protocol/registry seams, machine-readable exports, and baseline regression.
- `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` — ADR requiring benchmark discipline before RL/MPC/WBC/ROS/hardware/controller-family work.
- `outputs/locomotion-rd-systems.md` — Research rationale for analytical trot + MuJoCo position-servo classification and future residual/direct RL, MPC, WBC, ROS/hardware, and perception-conditioned branches.
- `outputs/locomotion-rd-systems.provenance.md` — Provenance for the locomotion R&D report.

### Current implementation surfaces to document
- `README.md` — Add the short locomotion benchmark command card and link to the focused guide.
- `src/main.py` — Defines `argus eval-locomotion`, repeated `--controller`/`--scenario`/`--seed` flags, `--matrix-config`, `--from-run-dir`, output-root, action-mode, and failure-handling CLI options.
- `src/locomotion/evaluation.py` — Defines evaluation matrix/config contracts, artifact filenames, CSV/JSONL/summary/comparison generation, saved-run regeneration, and metric direction labels.
- `src/locomotion/env.py` — Defines `ArgusGo2Env`, reset/step contract, reward/info surfaces, and environment config that the guide must summarize.
- `src/locomotion/actions.py` — Defines action-mode/action-space behavior that the guide must summarize.
- `src/locomotion/scenarios.py` — Defines named scenarios and scenario sampling metadata that the guide must summarize.
- `src/locomotion/metrics.py` — Defines metric families, summaries, proxy labels, and failure semantics that the guide must summarize.
- `src/locomotion/controllers.py` — Defines controller registry entries, analytical baseline metadata, and unavailable placeholder semantics used by the matrix.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docs/` — Existing user-facing documentation location; `docs/locomotion-benchmark.md` should live here as the focused harness guide.
- `README.md` — Existing high-level onboarding document and command list; add only a compact benchmark command card with a link to avoid duplicating the guide.
- `src/main.py` — Current CLI already exposes `eval-locomotion` and its flags, so docs should describe this path rather than invent a new command shape.
- `src/locomotion/evaluation.py` — Artifact names, matrix config keys, summary/comparison regeneration, and metric direction labels are already centralized here.
- `src/locomotion/env.py`, `actions.py`, `scenarios.py`, `metrics.py`, and `controllers.py` — These define the observation/action/scenario/metric/controller facts the guide must reflect.
- `tests/locomotion/test_locomotion_evaluation_exports.py`, `tests/locomotion/test_locomotion_evaluation_runner.py`, `tests/locomotion/test_locomotion_baseline_regression.py`, and `tests/test_main_args.py` — Existing Phase 4 tests demonstrate CLI/export/regeneration behavior; Phase 5 doc tests should complement these without running simulation.

### Established Patterns
- User-facing Markdown belongs in `docs/` with README links for discoverability.
- Existing CLI examples use `uv run argus ...`; Phase 5 should use the same invocation style.
- Evaluation artifacts are timestamped under `outputs/locomotion-evals/` and are intended to support offline comparison without rerunning simulation.
- Current locomotion stack is analytical Go2 trot over MuJoCo position actuators; effort/saturation metrics are position-servo proxies and must be labeled that way.
- Future controller families are represented as explicit seams/placeholders and deferred scope, not partially implemented behavior.
- Fast pytest coverage is preferred for content/contract checks; real MuJoCo execution belongs in targeted locomotion regression tests, not Markdown content tests.

### Integration Points
- Add or update `docs/locomotion-benchmark.md` for the canonical harness guide.
- Update `README.md` with a short benchmark command card linking to the guide.
- Add a focused pytest file under `tests/` that reads the README and guide Markdown and checks required commands, artifacts, matrix families, and rationale links.
- Keep docs aligned with `src/main.py::parse_args()` / `run_eval_locomotion_mode()` and `src/locomotion/evaluation.py` artifact contracts.

</code_context>

<specifics>
## Specific Ideas

- User chose `Docs + README`: canonical focused guide in `docs/locomotion-benchmark.md` plus a README pointer.
- User chose `Short command card`: README should show a compact smoke command and artifact-output pointer, not a full mini-guide.
- User chose explicit smoke flags: `uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202`.
- User chose to include both matrix-config and saved-run regeneration examples in the guide.
- User chose `Hard boundary` matrix language for deferred controller families.
- User chose matrix columns focused on status, hook/seam, rationale, prerequisite, and R&D rationale link.
- User chose to include controller IDs and seams without turning the matrix into a brittle internals dump.
- User chose light pytest-based documentation checks and explicitly did not choose tests that execute the smoke benchmark.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-harness-docs-and-comparison-matrix*
*Context gathered: 2026-05-01*
