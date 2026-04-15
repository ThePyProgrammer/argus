"""Unit tests for src/metrics/detection_export.py::DetectionExportWriter.

Covers CONTEXT D-11 / D-12 + RESEARCH Pitfall 6 (line-buffered append) and
Open Question 4 (lock-protected rotation). The threat model (T-6-02) is
exercised indirectly: tests never pass user-shaped session_id strings with
path-traversal tokens; the writer composes paths via `tempfile.gettempdir() /
argus_sessions / <session_id>` and this file asserts the directory layout.

Test matrix:
    1. test_writer_creates_session_directory — directory + empty file on init.
    2. test_append_writes_one_line_per_call — one call == one JSON line.
    3. test_envelope_keys — top-level = {robot_id, backend_id,
       capture_timestamp, obb}; obb = 7 to_wire() keys.
    4. test_rotate_opens_new_file — old file preserved, new session dir + file
       appears, session_id property updates.
    5. test_round_trip_via_from_wire — real OrientedBox3D round-trips via
       OrientedBox3D.from_wire to ±1e-6.
    6. test_rotate_is_thread_safe — append + rotate in parallel does not crash
       and does not produce malformed JSON lines (no lost-write guarantee).
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from src.metrics.detection_export import DetectionExportWriter
from src.perception.types import OrientedBox3D


# ---------------------------------------------------------------------------
# Fake OBB used for tests 1-4 to keep them decoupled from OrientedBox3D
# construction. Must expose only the `to_wire()` contract.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeOBB:
    """Minimal shape-compat stand-in; only `to_wire()` is exercised."""

    def to_wire(self) -> dict[str, Any]:
        return {
            "center": [1.0, 2.0, 3.0],
            "half_extents": [0.2, 0.3, 0.4],
            "quaternion": [0.0, 0.0, 0.0, 1.0],
            "class_id": 56,
            "class_name": "chair",
            "score": 0.87,
            "track_id": None,
        }


# ---------------------------------------------------------------------------
# Test 1 — session directory + empty file on init
# ---------------------------------------------------------------------------


def test_writer_creates_session_directory(tmp_path):
    session_id = "abc123"
    writer = DetectionExportWriter(session_id=session_id, base_dir=tmp_path)
    try:
        session_dir = tmp_path / "argus_sessions" / session_id
        assert session_dir.is_dir(), "session directory should be created"
        file_path = session_dir / "detections.jsonl"
        assert file_path.is_file(), "detections.jsonl should exist (may be empty)"
        assert writer.session_id == session_id
        assert writer.file_path == file_path
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Test 2 — append writes exactly one JSON line per call
# ---------------------------------------------------------------------------


def test_append_writes_one_line_per_call(tmp_path):
    writer = DetectionExportWriter(session_id="s1", base_dir=tmp_path)
    try:
        obb = FakeOBB()
        writer.append(obb, robot_id="robot_0", backend_id="yolov11", capture_timestamp=12.345)
        writer.append(obb, robot_id="robot_1", backend_id="yolov11", capture_timestamp=12.5)
    finally:
        writer.close()

    content = (tmp_path / "argus_sessions" / "s1" / "detections.jsonl").read_text()
    lines = [ln for ln in content.split("\n") if ln.strip()]
    assert len(lines) == 2, f"expected 2 lines, got {len(lines)}"
    for ln in lines:
        parsed = json.loads(ln)  # must be valid JSON
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Test 3 — envelope + OBB wire keys
# ---------------------------------------------------------------------------


def test_envelope_keys(tmp_path):
    writer = DetectionExportWriter(session_id="s2", base_dir=tmp_path)
    try:
        writer.append(FakeOBB(), robot_id="robot_0", backend_id="yolov11", capture_timestamp=0.0)
    finally:
        writer.close()

    line = (tmp_path / "argus_sessions" / "s2" / "detections.jsonl").read_text().splitlines()[0]
    parsed = json.loads(line)

    # Top-level envelope keys
    assert set(parsed.keys()) == {"robot_id", "backend_id", "capture_timestamp", "obb"}
    assert parsed["robot_id"] == "robot_0"
    assert parsed["backend_id"] == "yolov11"
    assert parsed["capture_timestamp"] == 0.0

    # OBB wire keys (7 required per OrientedBox3D.to_wire contract)
    obb = parsed["obb"]
    expected_obb_keys = {
        "center",
        "half_extents",
        "quaternion",
        "class_id",
        "class_name",
        "score",
        "track_id",
    }
    assert set(obb.keys()) == expected_obb_keys


# ---------------------------------------------------------------------------
# Test 4 — rotate opens a fresh file without deleting the old one (D-12)
# ---------------------------------------------------------------------------


def test_rotate_opens_new_file(tmp_path):
    writer = DetectionExportWriter(session_id="old", base_dir=tmp_path)
    try:
        writer.append(FakeOBB(), robot_id="r0", backend_id="yolov11", capture_timestamp=1.0)
        old_path = writer.file_path
        assert old_path.is_file()

        writer.rotate("new-session")
        assert writer.session_id == "new-session"
        new_path = writer.file_path
        assert new_path != old_path
        assert new_path.is_file()

        # Old file is preserved (D-12: not auto-deleted).
        assert old_path.is_file()

        writer.append(FakeOBB(), robot_id="r0", backend_id="yolov11", capture_timestamp=2.0)
    finally:
        writer.close()

    old_lines = [ln for ln in old_path.read_text().splitlines() if ln.strip()]
    new_lines = [ln for ln in new_path.read_text().splitlines() if ln.strip()]
    assert len(old_lines) == 1
    assert len(new_lines) == 1

    assert json.loads(old_lines[0])["capture_timestamp"] == 1.0
    assert json.loads(new_lines[0])["capture_timestamp"] == 2.0


# ---------------------------------------------------------------------------
# Test 5 — real OrientedBox3D round-trip via from_wire (±1e-6)
# ---------------------------------------------------------------------------


def test_round_trip_via_from_wire(tmp_path):
    # Random-ish but deterministic OBB with non-trivial quaternion (qw>=0).
    original = OrientedBox3D(
        center=np.array([1.234, -2.345, 0.678], dtype=np.float64),
        half_extents=np.array([0.10, 0.20, 0.30], dtype=np.float64),
        quaternion=np.array([0.182574, 0.365148, 0.547723, 0.730297], dtype=np.float64),
        class_id=7,
        class_name="chair",
        score=0.93,
        track_id=42,
    )

    writer = DetectionExportWriter(session_id="rt", base_dir=tmp_path)
    try:
        writer.append(
            original,
            robot_id="robot_0",
            backend_id="yolov11",
            capture_timestamp=9.87,
        )
    finally:
        writer.close()

    line = (tmp_path / "argus_sessions" / "rt" / "detections.jsonl").read_text().splitlines()[0]
    parsed = json.loads(line)
    reconstructed = OrientedBox3D.from_wire(parsed["obb"])

    assert np.allclose(reconstructed.center, original.center, atol=1e-6)
    assert np.allclose(reconstructed.half_extents, original.half_extents, atol=1e-6)
    assert np.allclose(reconstructed.quaternion, original.quaternion, atol=1e-6)
    assert reconstructed.class_id == original.class_id
    assert reconstructed.class_name == original.class_name
    assert abs(reconstructed.score - original.score) < 1e-6
    assert reconstructed.track_id == original.track_id


# ---------------------------------------------------------------------------
# Test 6 — thread-safe rotate vs append (smoke)
# ---------------------------------------------------------------------------


def test_rotate_is_thread_safe(tmp_path):
    writer = DetectionExportWriter(session_id="t0", base_dir=tmp_path)
    stop = threading.Event()
    errors: list[BaseException] = []

    def appender():
        try:
            obb = FakeOBB()
            for i in range(50):
                if stop.is_set():
                    return
                writer.append(obb, robot_id="r0", backend_id="yolov11", capture_timestamp=float(i))
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    def rotator():
        try:
            for i in range(50):
                if stop.is_set():
                    return
                writer.rotate(f"t{i + 1}")
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_a = pool.submit(appender)
            f_r = pool.submit(rotator)
            f_a.result(timeout=10)
            f_r.result(timeout=10)
    finally:
        stop.set()
        writer.close()

    assert errors == [], f"thread workers raised: {errors}"

    # Every produced JSONL line across every session directory must parse.
    sessions_root = tmp_path / "argus_sessions"
    for session_dir in sessions_root.iterdir():
        jsonl = session_dir / "detections.jsonl"
        if not jsonl.exists():
            continue
        for raw in jsonl.read_text().splitlines():
            if not raw.strip():
                continue
            # Each line must parse — no truncated / half-flushed lines.
            parsed = json.loads(raw)
            assert set(parsed.keys()) == {
                "robot_id",
                "backend_id",
                "capture_timestamp",
                "obb",
            }


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
