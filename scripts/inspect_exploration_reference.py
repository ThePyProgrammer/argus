"""Validate benchmark references and export masks, metadata, and SVG diagnostics.

Run from the repository root with:
    uv run python scripts/inspect_exploration_reference.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

# Support direct execution from a checkout as well as an editable installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.exploration.evaluation.scenarios import DEFAULTS, list_scenarios, load_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=list_scenarios(), action="append")
    parser.add_argument("--resolution", type=float, default=DEFAULTS.evaluation_resolution_m)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/exploration-reference"))
    parser.add_argument("--probe", nargs=2, type=float, action="append", default=[], metavar=("X", "Y"))
    args = parser.parse_args(argv)
    # Prepare all results first so invalid input cannot leave a partial campaign.
    prepared = []
    for scenario_id in args.scenario or list_scenarios():
        scenario = load_scenario(scenario_id)
        reference = scenario.compiled_reference(args.resolution)
        if not np.array_equal(reference.mask, scenario.reference_mask(args.resolution)):
            raise ValueError(f"Compiled and analytical masks disagree: {scenario_id}")
        spawn_points = [*scenario.spawn_pool, *args.probe]
        for x, y in spawn_points:
            reference.check_spawn(x, y)
        prepared.append((scenario, reference, spawn_points))
    for scenario, reference, spawn_points in prepared:
        output = args.output_root / scenario.scenario_id
        reference.write_diagnostics(output, spawn_points=spawn_points)
        source = {"scenario_id": scenario.scenario_id, "scenario_sha256": scenario.scenario_sha256,
                  "scene_sha256": scenario.scene_sha256, "metadata_sha256": scenario.metadata_sha256}
        (output / "source.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
        metadata = reference.metadata()
        print(f'{scenario.scenario_id}: {metadata["cell_count"]} cells, '
              f'{metadata["area_m2"]:.2f} m2; {output / "reference.svg"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
