# Research methodology

This note preserves the research rationale previously embedded in the README. Implementation decisions are recorded in the [ADRs](../adr/README.md).

## Coordination as the research question

Multiple robots can observe different parts of an environment and share discoveries. Whether this improves exploration depends on redundant coverage, travel costs, communication, and coordination. Speedup must be measured; it does not follow automatically from adding robots.

Argus brings these components into one experimental runtime so changes to coordination can be studied alongside perception, planning, and system performance.

## Ground truth as a controlled variable

MuJoCo supplies known robot and camera poses. Using them as a shared world reference removes inter-robot registration from the baseline experiment. Synthetic depth and known starting conditions also reduce uncertainty while developing exploration and coordination.

These assumptions define what an experiment can establish. They help isolate system behavior, but do not demonstrate robustness to localization error, noisy sensors, or hardware dynamics. Individual SLAM backends may still accumulate estimation error. Future experiments can introduce uncertainty one source at a time and compare against the controlled baseline.

See [ADR-0003](../adr/0003-use-ground-truth-world-poses-to-remove-map-alignment-as-a-variable.md).

## Pluggability as an experimental method

Small protocols and registries let implementations change while the surrounding runtime stays stable. A backend comparison is more informative when scene, robot, inputs, and evaluation conditions remain fixed.

The recurring pattern is to define an interface, register implementations, retain a baseline, expose selection, and measure behavior under recorded conditions. Interface compatibility alone does not make two algorithms scientifically comparable; their inputs and assumptions must also be reported.

## Evaluation before complexity

The Go2 analytical trot provides a deterministic comparator for future controllers. Its Gymnasium-style harness records scenarios, seeds, and metrics before introducing learned or model-based control. Joint-position actuation is the current control boundary; effort proxies are not torque or energy measurements.

Metrics should answer a defined question and retain the evidence needed to inspect failures. Simulator ground truth supports evaluation, but it also assists the current mapping baseline. Reports must disclose both uses. Optimizing a dashboard metric without checking the underlying behavior risks rewarding the wrong result.

See the [locomotion benchmark guide](../locomotion-benchmark.md) and [metric policy](../adr/0012-forbid-fake-map-and-use-mujoco-ground-truth-metrics.md).
