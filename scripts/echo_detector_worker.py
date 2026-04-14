#!/usr/bin/env python3
"""Standalone ZMQ PAIR echo worker for SubprocessDetectorBridge handshake test.

Permanent helper per Phase 2 CONTEXT.md D-15 — reusable as a dev harness for
Phase 5 BoxeR bring-up. NOT a test-only fixture. Checked into scripts/.

Usage:
    python scripts/echo_detector_worker.py --zmq ipc:///tmp/detector_bridge_12345_67890
    python scripts/echo_detector_worker.py --zmq ipc:///tmp/x --sleep-ms 100

Wire protocol (D-17):
    Incoming (from bridge):
        multipart frame = [msgpack(header), rgb_bytes, depth_bytes?]
        where header ∋ {"ts": float, ...}
    Outgoing (reply to bridge):
        msgpack({"ts": float, "inference_ms": float, "n_det": 0,
                 "classes": [], "scores": [], "bboxes": []})

The worker connects (PAIR client) to the endpoint the bridge has bound. It
echoes a fixed 0-detection reply for every received frame, optionally sleeping
``--sleep-ms`` to simulate a slow backend. Phase 5 replaces this with a real
BoxeR inference binary — the reply schema stays the same.

Exit paths:
  * ``KeyboardInterrupt`` or ``zmq.ContextTerminated`` → clean exit (0).
  * Any other exception propagates — the bridge will observe the Popen exit
    code via its crash-detection path (Popen.poll() in send_frame).
"""

from __future__ import annotations

import argparse
import sys
import time

import msgpack
import zmq


def main() -> int:
    ap = argparse.ArgumentParser(
        description="ZMQ PAIR echo worker for SubprocessDetectorBridge (D-15, D-17).",
    )
    ap.add_argument(
        "--zmq",
        dest="zmq_endpoint",
        required=True,
        help="ZMQ endpoint to connect to (e.g., ipc:///tmp/detector_bridge_<pid>_<id>).",
    )
    ap.add_argument(
        "--sleep-ms",
        dest="sleep_ms",
        type=int,
        default=0,
        help="Simulate slow backend: sleep this many ms per frame before replying.",
    )
    args = ap.parse_args()

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PAIR)
    sock.connect(args.zmq_endpoint)
    try:
        while True:
            parts = sock.recv_multipart()
            if not parts:
                continue
            header = msgpack.unpackb(parts[0], raw=False)
            if args.sleep_ms:
                time.sleep(args.sleep_ms / 1000.0)
            reply = msgpack.packb(
                {
                    "ts": float(header.get("ts", 0.0)) if isinstance(header, dict) else 0.0,
                    "inference_ms": float(args.sleep_ms),
                    "n_det": 0,
                    "classes": [],
                    "scores": [],
                    "bboxes": [],
                }
            )
            sock.send(reply)  # single-part reply — the header IS the whole reply.
    except (KeyboardInterrupt, zmq.ContextTerminated):
        pass
    finally:
        try:
            sock.close(linger=0)
        except Exception:
            pass
        try:
            ctx.term()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
