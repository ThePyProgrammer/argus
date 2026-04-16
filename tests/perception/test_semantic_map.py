"""SemanticMap with TTL (DET-STRETCH-03 SC#3).

Tests validate object insertion, TTL expiry, refresh behavior,
delta update ordering (expired_ids before internal cleanup -- Pitfall 3),
and configurable TTL.
"""
from __future__ import annotations

import pytest

from src.perception.semantic_map import SemanticMap


def _make_fused_detection(
    fused_track_id: int = 0,
    class_name: str = "chair",
    score: float = 0.9,
    center: list[float] | None = None,
) -> dict:
    """Helper: build a fused detection dict matching FusionManager output."""
    return {
        "fused_track_id": fused_track_id,
        "class_name": class_name,
        "score": score,
        "center": center or [1.0, 0.5, 0.8],
        "half_extents": [0.3, 0.4, 0.5],
        "quaternion": [0.0, 0.0, 0.0, 1.0],
        "robot_ids": ["robot_0"],
        "source_track_ids": [10],
    }


class TestInsertAndRetrieve:
    """Object inserted via update() appears in get_delta() active list."""

    def test_insert_object_and_retrieve(self) -> None:
        sm = SemanticMap()
        fd = _make_fused_detection(fused_track_id=1)
        sm.update([fd], sim_time=0.0)
        delta = sm.get_delta(sim_time=0.0)
        assert len(delta["active"]) == 1
        assert delta["active"][0]["fused_track_id"] == 1
        assert delta["active"][0]["class_name"] == "chair"
        assert delta["expired_ids"] == []

    def test_wire_format_completeness(self) -> None:
        sm = SemanticMap()
        fd = _make_fused_detection(fused_track_id=5)
        sm.update([fd], sim_time=0.0)
        delta = sm.get_delta(sim_time=0.0)
        obj = delta["active"][0]
        assert "fused_track_id" in obj
        assert "class_name" in obj
        assert "center" in obj
        assert "half_extents" in obj
        assert "quaternion" in obj
        assert "score" in obj
        assert "last_seen" in obj
        assert "ttl" in obj


class TestTTLExpiry:
    """SC#3: advance time past TTL, object appears in expired_ids."""

    def test_expired_object_in_expired_ids(self) -> None:
        sm = SemanticMap()  # default TTL = 10.0s
        sm.update([_make_fused_detection(fused_track_id=1)], sim_time=0.0)
        delta = sm.get_delta(sim_time=11.0)
        assert 1 in delta["expired_ids"]
        assert len(delta["active"]) == 0

    def test_not_expired_before_ttl(self) -> None:
        sm = SemanticMap()
        sm.update([_make_fused_detection(fused_track_id=1)], sim_time=0.0)
        delta = sm.get_delta(sim_time=9.0)
        assert len(delta["active"]) == 1
        assert delta["expired_ids"] == []


class TestRefreshResetsTTL:
    """Re-observing an object resets its last_seen, extending its life."""

    def test_refresh_resets_ttl(self) -> None:
        sm = SemanticMap()  # TTL = 10s
        sm.update([_make_fused_detection(fused_track_id=1)], sim_time=0.0)
        # Re-observe at t=5.0
        sm.update([_make_fused_detection(fused_track_id=1)], sim_time=5.0)
        # At t=11.0, only 6s since last observation -- still alive
        delta = sm.get_delta(sim_time=11.0)
        assert len(delta["active"]) == 1
        assert delta["expired_ids"] == []

    def test_refresh_updates_fields(self) -> None:
        sm = SemanticMap()
        sm.update(
            [_make_fused_detection(fused_track_id=1, score=0.8, center=[1.0, 1.0, 1.0])],
            sim_time=0.0,
        )
        sm.update(
            [_make_fused_detection(fused_track_id=1, score=0.95, center=[2.0, 2.0, 2.0])],
            sim_time=5.0,
        )
        delta = sm.get_delta(sim_time=5.0)
        obj = delta["active"][0]
        assert obj["score"] == pytest.approx(0.95)
        assert obj["center"] == [2.0, 2.0, 2.0]


class TestExpiredRemovedAfterDelta:
    """After get_delta() returns expired_ids, those objects are gone from internal dict."""

    def test_expired_removed_from_internal_dict(self) -> None:
        sm = SemanticMap()
        sm.update([_make_fused_detection(fused_track_id=1)], sim_time=0.0)
        # First delta: expires the object
        delta1 = sm.get_delta(sim_time=11.0)
        assert 1 in delta1["expired_ids"]
        # Second delta: object gone from both active and expired
        delta2 = sm.get_delta(sim_time=12.0)
        assert delta2["active"] == []
        assert delta2["expired_ids"] == []


class TestGetDeltaExpiredBeforeCleanup:
    """Pitfall 3: get_delta returns expired_ids BEFORE deleting from internal dict."""

    def test_expired_ids_in_response_before_cleanup(self) -> None:
        sm = SemanticMap()
        sm.update([_make_fused_detection(fused_track_id=42)], sim_time=0.0)
        delta = sm.get_delta(sim_time=11.0)
        # The key invariant: expired_ids contains 42 in the SAME response
        # that causes removal -- the caller sees the ID to emit removal
        assert 42 in delta["expired_ids"]


class TestDefaultTTL:
    """Default TTL is 10.0 seconds per D-12."""

    def test_default_ttl_10_seconds(self) -> None:
        sm = SemanticMap()
        assert sm._ttl == 10.0


class TestCustomTTL:
    """Custom TTL overrides default."""

    def test_custom_ttl(self) -> None:
        sm = SemanticMap(ttl=5.0)
        assert sm._ttl == 5.0

    def test_custom_ttl_expiry(self) -> None:
        sm = SemanticMap(ttl=3.0)
        sm.update([_make_fused_detection(fused_track_id=1)], sim_time=0.0)
        delta = sm.get_delta(sim_time=4.0)
        assert 1 in delta["expired_ids"]
        assert len(delta["active"]) == 0
