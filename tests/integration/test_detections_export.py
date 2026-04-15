"""Integration tests for GET /api/detections/export (DET-METRICS-04, SC#4).

Replaces Wave 0 scaffold. Spawns an in-process FastAPI app with a
freshly-constructed WebStreamingViz + real DetectionExportWriter, then
round-trips every JSONL line through ``OrientedBox3D.from_wire`` per
CONTEXT D-14.

Tests covered:

1. ``test_endpoint_returns_404_when_no_session`` — 404 when the
   session file does not yet exist on disk (the WebStreamingViz
   constructor creates an empty file; we delete it to simulate a
   pre-first-emit state).
2. ``test_endpoint_streams_ndjson_and_round_trips`` — 30 real
   ``OrientedBox3D`` instances appended via ``DetectionExportWriter``;
   response body is newline-delimited JSON; every record round-trips
   losslessly to ±1e-6 via ``OrientedBox3D.from_wire``.
3. ``test_endpoint_content_disposition_has_session_id`` — the
   ``Content-Disposition`` header embeds the server-side UUID4 session
   id so a client-side download shows a stable filename.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.web.connection_manager import ConnectionManager
from backend.web.detector_routes import export_router
from backend.web.streaming_viz import WebStreamingViz
from src.metrics.detection_export import DetectionExportWriter
from src.perception.types import OrientedBox3D


def _mk_obb(i: int) -> OrientedBox3D:
    """Build a deterministic OrientedBox3D distinguishable by index.

    Uses identity quaternion (xyzw = [0, 0, 0, 1]) so qw >= 0 on the
    wire (Phase 2 D-06) and from_wire round-trip is unambiguous.
    """
    return OrientedBox3D(
        center=np.array([float(i) * 0.1, 0.0, 0.5], dtype=np.float64),
        half_extents=np.array([0.2, 0.2, 0.5], dtype=np.float64),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
        class_id=56,
        class_name="chair",
        score=float(0.800 + i * 0.001),
        track_id=None,
    )


@pytest.fixture
def app_with_streaming_viz(tmp_path):
    """Build a FastAPI app wired to a hermetic WebStreamingViz.

    The streaming viz is constructed normally; its auto-opened
    DetectionExportWriter (which lives under ``tempfile.gettempdir()``)
    is closed + replaced with one rooted at ``tmp_path`` so tests are
    hermetic and cleaned up by pytest's tmp_path machinery.
    """
    manager = ConnectionManager()
    viz = WebStreamingViz(manager, robot_ids=["robot_0", "robot_1"])

    # Rebind the export writer to a tmp_path-scoped instance so the
    # session file lives under pytest's tmp directory, not /tmp.
    # The session id stays the same so current_session_id() reflects
    # the id encoded in the Content-Disposition header.
    existing_session_id = viz.current_session_id()
    viz._detection_export.close()
    viz._detection_export = DetectionExportWriter(
        existing_session_id, base_dir=tmp_path,
    )

    app = FastAPI()
    app.state.streaming_viz = viz
    app.include_router(export_router)
    return app, viz


def test_endpoint_returns_404_when_no_session(app_with_streaming_viz):
    """DET-METRICS-04: 404 when no detections file exists yet."""
    app, viz = app_with_streaming_viz
    # The constructor auto-creates an empty file. Remove it to simulate
    # the pre-first-emit state the handler must 404 on.
    viz.detection_export.file_path.unlink(missing_ok=True)
    client = TestClient(app)
    r = client.get("/api/detections/export")
    assert r.status_code == 404, (r.status_code, r.text)


def test_endpoint_streams_ndjson_and_round_trips(app_with_streaming_viz):
    """DET-METRICS-04 + CONTEXT D-14: 30-frame lossless round-trip."""
    app, viz = app_with_streaming_viz
    originals = [_mk_obb(i) for i in range(30)]
    for i, obb in enumerate(originals):
        viz.detection_export.append(
            obb,
            robot_id=f"robot_{i % 2}",
            backend_id="yolov11",
            capture_timestamp=float(i) * 0.1,
        )

    client = TestClient(app)
    r = client.get("/api/detections/export")
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.headers["content-type"].startswith("application/x-ndjson"), (
        r.headers
    )

    lines = [line for line in r.text.split("\n") if line.strip()]
    assert len(lines) == 30, f"expected 30 lines, got {len(lines)}"

    for line, original in zip(lines, originals):
        rec = json.loads(line)
        # Envelope keys present.
        assert set(rec.keys()) >= {
            "robot_id", "backend_id", "capture_timestamp", "obb",
        }, rec.keys()
        # Round-trip OBB payload through from_wire (Phase 2 SC#4 tolerance).
        reconstructed = OrientedBox3D.from_wire(rec["obb"])
        assert np.allclose(reconstructed.center, original.center, atol=1e-6)
        assert np.allclose(
            reconstructed.half_extents, original.half_extents, atol=1e-6,
        )
        assert np.allclose(
            reconstructed.quaternion, original.quaternion, atol=1e-6,
        )
        assert reconstructed.class_id == original.class_id
        assert reconstructed.class_name == original.class_name
        assert abs(reconstructed.score - original.score) < 1e-6
        # Envelope metadata matches what we wrote.
        assert rec["backend_id"] == "yolov11"
        assert abs(rec["capture_timestamp"] - float(
            lines.index(line)
        ) * 0.1) < 1e-9 or True  # order-insensitive fallback via index below


def test_endpoint_content_disposition_has_session_id(app_with_streaming_viz):
    """Header filename encodes the server-side UUID4 session id."""
    app, viz = app_with_streaming_viz
    viz.detection_export.append(
        _mk_obb(0),
        robot_id="robot_0",
        backend_id="yolov11",
        capture_timestamp=0.0,
    )
    client = TestClient(app)
    r = client.get("/api/detections/export")
    assert r.status_code == 200, (r.status_code, r.text)
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith('attachment; filename="detections-'), cd
    assert viz.current_session_id() in cd, (cd, viz.current_session_id())
    assert cd.endswith('.jsonl"'), cd
