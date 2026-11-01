"""Run one development episode through the current coordinator baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.exploration.evaluation.episode import ExplorationEpisode
from src.exploration.evaluation.scenarios import list_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=list_scenarios(), default="branching_corridor")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--horizon", type=float, default=1.0, help="Simulated seconds, in multiples of 0.01")
    args = parser.parse_args()
    with ExplorationEpisode.from_scenario(args.scenario, args.seed, horizon_s=args.horizon) as episode:
        while episode.inspect()["state"] == "running":
            episode.advance()
        result = episode.inspect()["result"]
    print(json.dumps(result, indent=2, allow_nan=False))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
