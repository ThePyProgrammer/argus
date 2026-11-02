"""Compare complete development episode exports using exact numeric equality.

Accepts smoke exports and contact diagnoses. Timing, memory, coverage, and
reliability measurements are excluded so collectors can be enabled in one run
and disabled in the other. Matching failed episodes still count as repeatable;
their outcome is reported separately from trace equality.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_episode(path: Path) -> dict:
    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON value: {value}")

    data = json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant)
    episode = data.get("episode", data)
    if episode["state"] != "finished" or episode["result"]["valid"] is not True:
        raise ValueError(f"{path}: requires a completed, valid episode export")
    for field in ("commands", "trajectory"):
        if not isinstance(episode[field], list) or not episode[field]:
            raise ValueError(f"{path}: missing or empty {field} history")
    result = episode["result"]
    if episode["trajectory"][-1]["elapsed_s"] != result["elapsed_s"]:
        raise ValueError(f"{path}: trajectory does not reach the reported end")
    return episode


def first_difference(left, right, path: str = "") -> dict | None:
    """Return the first differing field, including missing keys and list tails."""
    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            return {"path": path, "left_keys": sorted(left), "right_keys": sorted(right)}
        for key in sorted(left):
            difference = first_difference(left[key], right[key], f"{path}.{key}")
            if difference is not None:
                return difference
    elif isinstance(left, list) and isinstance(right, list):
        for i, (a, b) in enumerate(zip(left, right)):
            difference = first_difference(a, b, f"{path}[{i}]")
            if difference is not None:
                return difference
        if len(left) != len(right):
            return {"path": path, "left_length": len(left), "right_length": len(right)}
    elif left != right:
        return {"path": path, "left": left, "right": right}
    return None


def compare(left: dict, right: dict) -> dict:
    fields = ("termination_reason", "elapsed_s", "frame_dt", "settling_sim_seconds", "provenance")
    checks = {field: first_difference(left["result"][field], right["result"][field], field)
              for field in fields}
    checks.update({field: first_difference(left[field], right[field], field)
                   for field in ("commands", "trajectory", "events")})
    return {
        "equal": all(value is None for value in checks.values()),
        "comparison": "exact numeric equality of complete control and body-position histories",
        "outcomes": [episode["result"]["termination_reason"] for episode in (left, right)],
        "elapsed_s": [episode["result"]["elapsed_s"] for episode in (left, right)],
        "counts": {field: [len(episode[field]) for episode in (left, right)]
                   for field in ("commands", "trajectory")},
        "differences": {field: value for field, value in checks.items() if value is not None},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = compare(load_episode(args.left), load_episode(args.right))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    report["inputs"] = [str(args.left), str(args.right)]
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["equal"] else 1)


if __name__ == "__main__":
    main()
