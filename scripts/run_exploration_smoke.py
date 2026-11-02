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
    parser.add_argument("--output", type=Path, help="Save result and command/body histories as JSON")
    parser.add_argument("--no-collect", action="store_true", help="Disable measurements for command-trace comparison")
    args = parser.parse_args()
    with ExplorationEpisode.from_scenario(args.scenario, args.seed, horizon_s=args.horizon,
                                         collect=not args.no_collect) as episode:
        while episode.inspect()["state"] == "running":
            episode.advance()
        result = episode.inspect()["result"]
        if args.output is not None:
            snapshot = episode.inspect(include_history=True)
            snapshot["reliability_events"] = episode.reliability.events() if episode.collect else []
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(snapshot, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
