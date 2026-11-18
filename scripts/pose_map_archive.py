"""Lossless diagnostic scan inputs; never read by navigation or SLAM."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np


class ScanArchive:
    def __init__(self, directory: Path, chunk_frames=100):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        self.chunk_frames = chunk_frames
        self.pending = {}
        self.last_time = {}
        self.manifest = {"version": 1, "complete": False, "robots": {}, "chunks": []}
        self._save()

    def _save(self):
        (self.directory / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def append(self, robot, time_s, points, mask, estimated, truth, config, resolution):
        if time_s <= self.last_time.get(robot, -float("inf")):
            raise ValueError("Scan times must increase independently for each robot")
        self.last_time[robot] = time_s
        metadata = {"floor_config": asdict(config), "map_resolution_m": resolution}
        if self.manifest["robots"].setdefault(robot, metadata) != metadata:
            raise ValueError("Diagnostic configuration changed during the archive")
        self.pending.setdefault(robot, []).append((float(time_s), np.asarray(points).copy(),
            np.asarray(mask, dtype=bool).copy(), np.asarray(estimated).copy(), np.asarray(truth).copy()))
        if len(self.pending[robot]) >= self.chunk_frames:
            self._flush(robot)

    def _flush(self, robot):
        rows = self.pending.get(robot, [])
        if not rows:
            return
        name = f"chunk-{len(self.manifest['chunks']):05d}.npz"
        path = self.directory / name
        np.savez_compressed(path, times=[r[0] for r in rows],
            offsets=np.r_[0, np.cumsum([len(r[1]) for r in rows])],
            points=np.concatenate([r[1] for r in rows]),
            masks=np.concatenate([r[2] for r in rows]),
            estimated=np.asarray([r[3] for r in rows]), truth=np.asarray([r[4] for r in rows]))
        self.manifest["chunks"].append({"file": name, "robot": robot, "frames": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.pending[robot] = []
        self._save()

    def finish(self, *, complete):
        for robot in self.pending:
            self._flush(robot)
        self.manifest["complete"] = bool(complete)
        self._save()


def read_scans(directory, robot):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["version"] != 1:
        raise ValueError("Unsupported scan archive version")
    previous = -float("inf")
    for entry in manifest["chunks"]:
        if entry["robot"] != robot:
            continue
        path = directory / entry["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Scan archive checksum mismatch: {path}")
        with np.load(path, allow_pickle=False) as data:
            if len(data["times"]) != entry["frames"]:
                raise ValueError("Scan frame count mismatch")
            for i, time_s in enumerate(data["times"]):
                if time_s <= previous:
                    raise ValueError("Scan archive timestamps are not increasing")
                previous = time_s
                start, end = data["offsets"][i:i+2]
                yield dict(time_s=float(time_s), points=data["points"][start:end].copy(),
                    mask=data["masks"][start:end].copy(), estimated=data["estimated"][i].copy(),
                    truth=data["truth"][i].copy())
