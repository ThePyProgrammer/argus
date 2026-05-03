# Phase 4: evaluation-runner-and-regression - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Provide a repeatable CLI benchmark runner that executes available locomotion controllers across scenario/seed matrices, exports per-step and per-episode artifacts with reproducibility metadata, generates aggregate comparison tables from saved artifacts, and adds an analytical-trot flat-ground regression gate. Phase 4 consumes the Phase 3 metric records and summaries; it does not redefine metric semantics, implement new controller families, add RL/MPC/WBC/ROS/hardware behavior, or build frontend visualization.

</domain>

<decisions>
## Implementation Decisions

### CLI Shape
- **D-01:** Add a dedicated `argus eval-locomotion` style subcommand under the existing installed `argus = src.main:main` entry point. Do not model evaluation as another `--control` runtime mode.
- **D-02:** Matrix inputs should be repeatable flags first, e.g. repeated `--controller`, `--scenario`, and `--seed` values, with optional matrix config-file support for larger saved matrices.
- **D-03:** CLI output should be quiet and artifact-focused by default, printing final artifact paths and the comparison table. Add `--verbose` for per-run progress rows and metric snippets.
- **D-04:** Validate all requested controller ids and availability before starting simulation. Placeholder controllers such as residual policy, direct policy, MPC, and WBC must fail fast with clear unavailable-controller errors rather than being skipped or failing mid-run.

### Export Layout
- **D-05:** Each invocation creates one self-contained timestamped run directory under `outputs/locomotion-evals/` containing the manifest, JSONL, CSV, summary, and Markdown comparison artifacts.
- **D-06:** JSONL export contains one row per environment step with run identifiers, compact metadata keys, and the nested `info["locomotion_metrics"]` payload from Phase 3. It is the time-series/debug artifact.
- **D-07:** CSV export is one flattened episode-summary row per controller/scenario/seed run. It should optimize for spreadsheet inspection and controller/scenario/seed comparisons rather than duplicating per-step JSONL.
- **D-08:** Reproducibility metadata lives in a top-level `manifest.json` with git commit, invocation args, matrix, environment/action config, timestamp, file list, and per-run metadata. Row-oriented artifacts should carry compact ids/keys rather than full repeated metadata.

### Comparison Table
- **D-09:** The default comparison table is a compact research-facing scorecard, not a full flattened metric dump. It should emphasize success rate/failure count, tracking RMSE, distance, stability, action smoothness/position-servo effort proxy, and contact/terrain proxy highlights.
- **D-10:** Aggregates include both per-controller overall rows and per-controller/per-scenario rows across seeds, so the top-level comparison remains simple while scenario-specific failures remain visible.
- **D-11:** Saved comparison artifacts are `summary.json` for machine-readable aggregates and a Markdown scorecard/table for human review. They must be regenerable from saved artifacts without rerunning simulation.
- **D-12:** Include metric direction metadata in `summary.json` and table labels such as `tracking_rmse ↓` and `success_rate ↑`. Do not invent a composite controller score in this phase.

### Regression Gate
- **D-13:** The analytical flat-ground baseline regression should be a threshold gate over fixed-seed runs, asserting no locomotion failure plus bounded tracking, stability, and distance metrics. Prefer robust thresholds over golden snapshot comparisons.
- **D-14:** The default regression uses a small fixed seed set, about 2–3 seeds, to catch seed-specific reset/schedule breakage without making routine pytest runs too slow.
- **D-15:** Test strategy should use fast fake-env/unit tests for runner, export, reload, and aggregation behavior, plus one marked real `ArgusGo2Env` analytical flat-ground smoke/regression test when MuJoCo assets are available.
- **D-16:** By default, any evaluated episode that terminates by locomotion failure makes the CLI/evaluation run exit nonzero after artifacts are written. This keeps the analytical regression meaningful and prevents failures from being silently ignored.

### Claude's Discretion
- Exact module names, parser helper structure, timestamp format, flattened CSV column names, default seed values, pytest marker name, and numeric regression thresholds are open to planner/researcher discretion, provided they satisfy the decisions above and preserve the existing project style.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 4 — Defines evaluation-runner-and-regression goal, dependencies, success criteria, and research flag.
- `.planning/REQUIREMENTS.md` §LOC-METRICS-05 / LOC-EVAL — Defines JSONL/CSV/summary exports, CLI matrix runner, aggregate comparison table, reproducibility metadata, and analytical baseline regression requirement.
- `.planning/PROJECT.md` §Current Milestone / Key Decisions — Locks benchmark-before-controller-sophistication, metrics-first evaluation, analytical baseline, and CLI/docs-first benchmark scope.
- `.planning/STATE.md` §Accumulated Context / Pending Todos — Captures Phase 4 current focus and locked v4.0 decisions.

### Prior phase dependency
- `.planning/phases/02-controller-plugin-baseline/02-CONTEXT.md` — Locks controller registry, unavailable placeholder semantics, metadata attribution, and analytical baseline behavior.
- `.planning/phases/03-locomotion-metrics-instrumentation/03-CONTEXT.md` — Locks per-step/per-episode metric surfaces, nested info payloads, failure semantics, and Phase 4 consumption of metric summaries.
- `.planning/phases/01-locomotion-env-contract/01-PATTERNS.md` — Existing `ArgusGo2Env`, scenario, action-mode, observation, reset/step, and MuJoCo test patterns.
- `.planning/phases/02-controller-plugin-baseline/02-PATTERNS.md` — Controller registry/dispatch, metadata, bridge preservation, and target-validation patterns.
- `.planning/phases/03-locomotion-metrics-instrumentation/03-PATTERNS.md` — Metrics collector/env integration, summary payload, and regression-test patterns.

### Architecture decisions and rationale
- `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` — ADR for reproducible Gymnasium harness, named scenarios, metadata, and per-step/per-episode metrics expectations.
- `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` — ADR requiring metrics and regression infrastructure before RL/MPC/WBC/controller-family work.
- `outputs/locomotion-rd-systems.md` — Research rationale for current analytical trot + MuJoCo position-servo baseline and deferred advanced controllers.
- `outputs/locomotion-rd-systems.provenance.md` — Provenance for the locomotion R&D report.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` — Existing installed CLI is `argus = "src.main:main"`; Phase 4 should extend this entry point rather than adding a second installed script unless planning proves a helper module is needed behind the subcommand.
- `src/main.py` — Current CLI uses `argparse` with `--control` runtime modes. The new evaluation path should be a distinct subcommand/branch so offline benchmarking does not get mixed into web/explore/multi runtime control modes.
- `src/locomotion/env.py` — `ArgusGo2Env` already owns reset/step, scenario sampling, controller selection, action mode, reproducibility info, `info["locomotion_metrics"]`, terminal `info["locomotion_metrics_summary"]`, and `last_locomotion_metrics_summary`.
- `src/locomotion/metrics.py` — `LocomotionMetricsCollector` defines validated metric families and episode summaries for command tracking, stability, action quality, and contact/terrain. Phase 4 should export these rather than recomputing metrics.
- `src/locomotion/controllers.py` — `ControllerRegistry` provides controller listing, creation, metadata, deterministic flag, parameter hash, availability, and explicit unavailable-controller errors.
- `src/locomotion/scenarios.py` — `list_scenarios()` and deterministic scenario sampling provide the named scenario matrix boundary.
- `tests/locomotion/test_argus_go2_env_metrics.py` and `tests/locomotion/test_locomotion_metrics_collector.py` — Existing tests show fake-env patterns, terminal summary expectations, and Phase 3 guards that intentionally deferred JSONL/CSV/evaluation-runner work to this phase.

### Established Patterns
- Use dataclass/config objects and absolute `src.*` imports.
- Validate ids, shapes, finite values, availability, and boundary inputs before starting work or mutating MuJoCo state.
- Keep Gymnasium `info` compact and nested; aggregate/export code should consume stable metric payloads instead of scattering top-level metric keys.
- Prefer focused pytest coverage with fake objects for fast unit behavior and a small number of real MuJoCo smoke/regression tests for end-to-end confidence.
- Current locomotion stack is MuJoCo position-servo based; exported effort/saturation metrics must preserve Phase 3 proxy labels.

### Integration Points
- CLI parser/entry point: `src/main.py::main()` / `parse_args()` under the `argus` script.
- Runner loop: instantiate `ArgusGo2Env(ArgusGo2EnvConfig(scenario_id=..., controller_id=..., action_mode=..., ...))`, call `reset(seed=...)`, step until terminated/truncated, and collect per-step info plus terminal summary.
- Export pipeline: write step JSONL, episode-summary CSV, `manifest.json`, `summary.json`, and Markdown scorecard into one run directory.
- Reload/comparison path: generate aggregate comparison tables from saved artifacts without creating a new environment or rerunning simulation.
- Regression path: pytest should exercise fake runner/export logic broadly and one marked analytical flat-ground real-env threshold gate narrowly.

</code_context>

<specifics>
## Specific Ideas

- User selected an `argus eval-locomotion` style subcommand and explicitly rejected modeling evaluation as another `--control` runtime mode.
- User wants both repeatable matrix flags and optional config-file input, with flags as the primary/default interface.
- User chose per-step JSONL, episode-summary CSV, top-level manifest metadata, and a compact scorecard table.
- User chose summary JSON plus Markdown for saved aggregate comparisons, with explicit metric direction labels and no composite score.
- User chose a fixed-seed threshold regression gate over golden snapshots, with fake-env unit coverage plus one real MuJoCo analytical smoke/regression.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-evaluation-runner-and-regression*
*Context gathered: 2026-05-01*
