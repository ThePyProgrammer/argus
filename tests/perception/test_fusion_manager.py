"""DetectionFusionManager cross-robot fusion (DET-STRETCH-02 SC#2)."""
import pytest


@pytest.mark.skip(reason="Phase 8 Plan 05 -- FusionManager implementation")
def test_two_robots_same_chair_within_radius_fuse():
    """SC#2: two robots detecting same chair within 0.5m produce single fused entry."""


@pytest.mark.skip(reason="Phase 8 Plan 05 -- FusionManager implementation")
def test_two_robots_different_locations_no_fuse():
    """Detections >0.5m apart remain separate fused entries."""


@pytest.mark.skip(reason="Phase 8 Plan 05 -- FusionManager implementation")
def test_class_gate_prevents_cross_class_fusion():
    """Chair and table at same location are NOT fused."""


@pytest.mark.skip(reason="Phase 8 Plan 05 -- FusionManager implementation")
def test_highest_confidence_is_representative():
    """Fused entry picks highest-confidence detection as representative OBB."""


@pytest.mark.skip(reason="Phase 8 Plan 05 -- FusionManager implementation")
def test_single_robot_passthrough():
    """With one robot, all detections pass through as single-source fused entries."""
