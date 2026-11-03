"""Run a fresh exploration validation and always export its recorded video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.diagnose_exploration_floor import diagnose_floor
from scripts.render_exploration_video import render
from src.exploration.evaluation.scenarios import list_scenarios


def check_encoder():
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Run with: uv run --with imageio-ffmpeg python scripts/validate_exploration.py ...") from exc
    imageio_ffmpeg.get_ffmpeg_exe()


def validate(scenario: str, seed: int, horizon: float, output: Path):
    """Keep failed algorithm outcomes and render them just like horizon completions."""
    check_encoder()  # Fail before an expensive simulation if export is unavailable.
    output.mkdir(parents=True, exist_ok=False)
    status = {"scenario": scenario, "seed": seed, "horizon_s": horizon, "phase": "simulation"}
    status_path = output / "validation.json"

    def save():
        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    save()
    try:
        report = diagnose_floor(scenario, seed, horizon, output)
        status.update(phase="video", termination_reason=report["episode"]["result"]["termination_reason"])
        save()
        # This also verifies the reconstructed body trace before encoding.
        render(output / "diagnosis.json", output / "top-view.mp4")
        status.update(phase="complete", video="top-view.mp4", preview="top-view.png",
                      video_verification="top-view.json")
        save()
        return report
    except BaseException as exc:
        status.update(failed_phase=status["phase"], phase="failed",
                      error=f"{type(exc).__name__}: {exc}")
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=list_scenarios(), default="cluttered_room")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--horizon", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True, help="New attempt directory")
    args = parser.parse_args()
    report = validate(args.scenario, args.seed, args.horizon, args.output)
    print(json.dumps(report["episode"]["result"], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
