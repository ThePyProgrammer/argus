#!/usr/bin/env python3
"""BoxeR ZMQ PAIR worker — runs INSIDE subprocess_venvs/boxer/ Python.

Supersedes scripts/echo_detector_worker.py as the real Phase 5 BoxeR worker.
Same wire protocol (Phase 2 D-17 + Phase 5 D-02 boxes_3d extension).

Readiness contract: this worker BLOCKS on BoxeR model load BEFORE calling
sock.connect(). The bridge's wait_for_handshake() treats the ZMQ connect
completion as the ready signal (Open Risk #3 mitigation per 05-RESEARCH.md).
This means first-frame latency = model-load time + one-frame inference time;
SC#2 has no FPS budget for BoxeR so a 15 s first-frame is acceptable.

Usage (from the main argus process via SubprocessDetectorBridge):
    <subprocess_venvs/boxer/bin/python> scripts/boxer_worker.py --zmq <endpoint>

Wire protocol (reply):
    {ts, inference_ms, n_det, classes[int], scores[float], bboxes[list[list[float]]],
     boxes_3d: [{"tx","ty","tz","qx","qy","qz","qw","w","h","d"}, ...]}

The composer in src/perception/backends/boxer_backend.py reads this dict and
builds OrientedBox3D instances — the composer divides w/h/d by 2 to convert
D-02's FULL extents to OrientedBox3D.half_extents (D-02 gotcha line).

Open Risk #1 fallback: if `from boxer.model import load_boxer_pipeline` fails
at import time (BoxeR's public Python API doesn't match RESEARCH assumption),
this worker logs a clear error, sends one sentinel reply with n_det=0 +
an `extras` dict flagging the problem, and exits with code 2 so the bridge's
SubprocessDiedError path surfaces the diagnostic upward.
"""
# Phase 1 D-10 CARVE-OUT: subprocess worker scripts running in foreign venvs
# may produce wire-format quaternions directly. The composer in
# src/perception/backends/boxer_backend.py re-hydrates them via
# OrientedBox3D.to_wire() — the invariant is preserved in the argus main process.
# BoxeR's native output is a 3x3 rotation matrix; there is no
# quaternion-free wire representation that msgpack can transport across the
# subprocess boundary, so this cross-venv script handcrafts xyzw quaternions
# via scipy.spatial.transform.Rotation.from_matrix(...).as_quat() below.
# This is a scoped exception to the Phase 1 D-10 invariant ("OrientedBox3D
# is the sole quaternion construction site") — the rule governs code running
# inside the argus main process, not foreign-venv worker scripts.
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import msgpack
import numpy as np
import zmq

logger = logging.getLogger("boxer_worker")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [boxer_worker] %(message)s")

# Pinned SHA duplicated here for self-containment — must match
# src/perception/backends/boxer_backend.py's BOXER_SHA (Plan 08 creates that file).
BOXER_SHA = "df474128a76ba42b05bc81feca7ac1a53fab41af"


def _resolve_ckpts_dir() -> Path:
    """Return models/boxer/<BOXER_SHA>/ relative to repo root.

    The worker runs from the subprocess venv's bin/python, but its cwd is
    the main argus repo (the bridge Popen-spawns it without chdir). So
    Path("models") / "boxer" / BOXER_SHA is correct.
    """
    return Path("models") / "boxer" / BOXER_SHA


def _load_pipeline(ckpts_dir: Path):
    """Load the actual pinned upstream BoxerNet and OWLv2 APIs."""
    repo = Path(__file__).resolve().parents[1] / "subprocess_venvs" / "boxer" / "repo"
    sys.path.insert(0, str(repo))
    import torch
    torch.set_num_threads(min(8, os.cpu_count() or 2))
    import utils.demo_utils as paths
    paths.CKPT_PATH = str(ckpts_dir.resolve())
    from boxernet.boxernet import BoxerNet
    import owl.clip_tokenizer as tokenizer
    import owl.owl_wrapper as owl_module
    tokenizer._CKPT_PATH = str(ckpts_dir.resolve() / "owlv2-base-patch16-ensemble.pt")
    owl_module._CKPT_PATH = tokenizer._CKPT_PATH
    labels = {
        "chair": 56, "couch": 57, "potted plant": 58, "bed": 59,
        "dining table": 60, "toilet": 61, "tv": 62, "laptop": 63,
        "mouse": 64, "remote": 65, "keyboard": 66, "cell phone": 67,
        "refrigerator": 72, "book": 73, "clock": 74, "vase": 75,
        "person": 0, "backpack": 24, "bottle": 39, "cup": 41,
    }
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = BoxerNet.load_from_checkpoint(
        str(ckpts_dir / "boxernet_hw960in4x6d768-wssxpf9p.ckpt"), device=device,
    )
    owl = owl_module.OwlWrapper(
        device=device, text_prompts=list(labels), min_confidence=0.2,
        precision="float32", warmup=False,
    )
    logger.info("BoxerNet + OWLv2 loaded on %s", device)
    return _BoxerPipeline(model, owl, labels)


def _source_bbox(box, width, height, model_size):
    """Undo square resizing and upstream x1,x2,y1,y2 ordering."""
    return np.asarray(box, dtype=np.float64)[[0, 2, 1, 3]] * (
        np.array([width, height, width, height]) / model_size
    )


class _BoxerPipeline:
    def __init__(self, model, owl, labels):
        self.model, self.owl, self.labels = model, owl, labels

    def __call__(self, rgb, depth, params):
        import cv2
        import torch
        from types import SimpleNamespace
        from loaders.base_loader import BaseLoader
        from utils.tw.pose import PoseTW

        height, width = rgb.shape[:2]
        size = int(self.model.hw)
        image = cv2.resize(rgb, (size, size))
        tensor = BaseLoader.img_to_tensor(image)
        with torch.inference_mode():
            boxes, scores, classes, _ = self.owl.forward(
                tensor * 255, False, resize_to_HW=(size, size),
            )
            if len(boxes) == 0:
                return SimpleNamespace(boxes_3d=[])
            fx, fy, cx, cy = params["intrinsics"]
            camera = BaseLoader.pinhole_from_K(
                size, size, fx * size / width, fy * size / height,
                cx * size / width, cy * size / height, valid_radius=(size, size),
            )
            # MuJoCo camera axes are x-right/y-up/z-back; Boxer uses OpenCV.
            pose = np.asarray(params["camera_pose"], dtype=np.float32)
            rotation = pose[:3, :3] @ np.diag([1, -1, -1]).astype(np.float32)
            translation = pose[:3, 3]
            points = BaseLoader.sdp_from_depth(depth, fx, fy, cx, cy, rotation, translation)
            datum = {
                "img0": tensor, "cam0": camera,
                "T_world_rig0": PoseTW.from_Rt(torch.from_numpy(rotation), torch.from_numpy(translation)),
                "rotated0": torch.tensor([False]), "sdp_w": points, "bb2d": boxes,
            }
            obbs = self.model.forward(datum)["obbs_pr_w"].cpu()[0]
            result = []
            label_names = list(self.labels)
            for index, obb in enumerate(obbs):
                confidence = float(obb.prob.squeeze())
                if confidence < params.get("score_threshold", 0.3):
                    continue
                # Upstream uses x1,x2,y1,y2 in its resized image.
                bb = _source_bbox(boxes[index].cpu().numpy(), width, height, size)
                result.append(SimpleNamespace(
                    class_id=self.labels[label_names[int(classes[index])]],
                    score=(confidence + float(scores[index])) / 2,
                    bbox_2d=bb.tolist(), center=obb.bb3_center_world.numpy(),
                    extent=obb.bb3_diagonal.numpy(), R_world_box=obb.T_world_object.R.numpy(),
                ))
            return SimpleNamespace(boxes_3d=result)


def _run_inference(pipeline, rgb: np.ndarray, depth: np.ndarray | None, params: dict) -> dict:
    """Run one frame through BoxeR, return the D-02 reply dict.

    BoxeR's 3D convention: (center[3], extent[3] FULL, R_world_box 3x3).
    We convert the 3x3 rotation to xyzw quaternion via scipy — see the
    Phase 1 D-10 CARVE-OUT comment at the top of this file for why this
    is a legal exception to the "OrientedBox3D is the sole quaternion
    construction site" invariant.
    """
    from scipy.spatial.transform import Rotation as R  # subprocess venv ships scipy
    t0 = time.perf_counter()
    out = pipeline(rgb=rgb, depth=depth, params=params or {})
    inference_ms = (time.perf_counter() - t0) * 1000.0

    classes: list[int] = []
    scores: list[float] = []
    bboxes: list[list[float]] = []
    boxes_3d: list[dict] = []
    for b in out.boxes_3d:
        classes.append(int(b.class_id))
        scores.append(float(b.score))
        # bbox_2d is optional — fall back to empty if BoxeR doesn't expose it
        bb = getattr(b, "bbox_2d", None) or [0.0, 0.0, 0.0, 0.0]
        bboxes.append([float(v) for v in bb])
        # Phase 1 D-10 CARVE-OUT (see module-top comment): 3x3 R matrix ->
        # xyzw quaternion. Composer re-hydrates via OrientedBox3D.to_wire().
        quat_xyzw = R.from_matrix(np.asarray(b.R_world_box, dtype=np.float64)).as_quat()
        boxes_3d.append({
            "tx": float(b.center[0]), "ty": float(b.center[1]), "tz": float(b.center[2]),
            "qx": float(quat_xyzw[0]), "qy": float(quat_xyzw[1]),
            "qz": float(quat_xyzw[2]), "qw": float(quat_xyzw[3]),
            # D-02: FULL extent (not half). Composer divides by 2.
            "w": float(b.extent[0]), "h": float(b.extent[1]), "d": float(b.extent[2]),
        })

    return {
        "inference_ms": inference_ms,
        "n_det": len(boxes_3d),
        "classes": classes,
        "scores": scores,
        "bboxes": bboxes,
        "boxes_3d": boxes_3d,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BoxeR ZMQ PAIR worker (Phase 5 D-02).")
    ap.add_argument("--zmq", dest="zmq_endpoint", required=True,
                    help="ZMQ endpoint to connect to (e.g., ipc:///tmp/detector_bridge_<pid>_<id>).")
    args = ap.parse_args(argv)

    # --- Step 1: Load BoxeR pipeline (heavy — 5–15 s). ---
    # This MUST complete before sock.connect() so the bridge's handshake
    # treats socket-ready as worker-ready.
    ckpts_dir = _resolve_ckpts_dir()
    if not ckpts_dir.exists():
        logger.error(
            "Ckpts dir missing: %s. Run `make download-models-boxer` first.",
            ckpts_dir,
        )
        return 2

    pipeline = _load_pipeline(ckpts_dir)

    # --- Step 2: Connect ZMQ AFTER pipeline load (readiness signal). ---
    ctx = zmq.Context()
    sock = ctx.socket(zmq.PAIR)
    sock.connect(args.zmq_endpoint)
    logger.info("connected to bridge at %s (pipeline loaded=%s)", args.zmq_endpoint, pipeline is not None)

    if pipeline is None:
        # Diagnostic reply + exit (Open Risk #1 fallback). Bridge will
        # read one msgpack reply then observe Popen exit via poll().
        try:
            diagnostic = {
                "ts": 0.0,
                "inference_ms": 0.0,
                "n_det": 0,
                "classes": [],
                "scores": [],
                "bboxes": [],
                "boxes_3d": None,
            }
            # Wait for the bridge's first send before replying — respects the PAIR protocol.
            sock.recv_multipart()
            sock.send(msgpack.packb(diagnostic))
        finally:
            sock.close(linger=0)
            ctx.term()
        return 2

    # --- Step 3: Main recv/send loop. ---
    try:
        while True:
            parts = sock.recv_multipart()
            if not parts:
                continue
            header = msgpack.unpackb(parts[0], raw=False, strict_map_key=True)
            H, W = int(header["rgb_shape"][0]), int(header["rgb_shape"][1])
            rgb = np.frombuffer(parts[1], dtype=np.uint8).reshape(H, W, 3)
            depth = None
            if header.get("depth_shape") is not None:
                dH, dW = int(header["depth_shape"][0]), int(header["depth_shape"][1])
                depth = np.frombuffer(parts[2], dtype=np.float32).reshape(dH, dW)

            reply_core = _run_inference(pipeline, rgb, depth, header.get("params") or {})
            reply_core["ts"] = float(header.get("ts", 0.0))
            sock.send(msgpack.packb(reply_core))
    except (KeyboardInterrupt, zmq.ContextTerminated):
        pass
    except Exception as exc:  # noqa: BLE001 — worker must exit cleanly so bridge sees crash
        logger.exception("fatal error in recv loop: %s", exc)
        return 3
    finally:
        try:
            sock.close(linger=0)
        except Exception:  # noqa: BLE001
            pass
        try:
            ctx.term()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
