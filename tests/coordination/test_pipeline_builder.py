"""Unit tests for PipelineBuilder, PipelineConfig, and NodeCatalog."""

import pytest

from src.coordination.pipeline_builder import (
    PipelineBuilder,
    PipelineConfig,
    NodeCatalog,
)
from src.slam.registry import SLAMRegistry
from src.coordination.merge_registry import MergeRegistry


@pytest.fixture(autouse=True)
def _reset_registries():
    """Clear and re-register mock backends for each test."""
    SLAMRegistry._clear()
    MergeRegistry._clear()
    SLAMRegistry.register(
        "icp", "ICP Odometry", "src.slam.backends.icp_backend.ICPBackend"
    )
    MergeRegistry.register(
        "icp_union", "ICP Union", "src.coordination.merge_strategies.icp_union.ICPUnionStrategy"
    )
    yield
    SLAMRegistry._clear()
    MergeRegistry._clear()


def _make_valid_graph() -> dict:
    """Build a minimal valid graph: sensor -> slam -> merger -> viz_output."""
    return {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}},
            {"id": "slam_1", "type": "slam_icp", "params": {}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}},
            {"id": "viz_1", "type": "viz_output", "params": {}},
        ],
        "edges": [
            {
                "source": "sensor_1",
                "sourceHandle": "image_out",
                "target": "slam_1",
                "targetHandle": "image_in",
            },
            {
                "source": "slam_1",
                "sourceHandle": "cloud_out",
                "target": "merger_1",
                "targetHandle": "cloud_in",
            },
            {
                "source": "slam_1",
                "sourceHandle": "pose_out",
                "target": "merger_1",
                "targetHandle": "pose_in",
            },
            {
                "source": "merger_1",
                "sourceHandle": "merged_out",
                "target": "viz_1",
                "targetHandle": "cloud_in",
            },
        ],
    }


def test_build_valid_graph():
    """A graph with sensor->slam->merger->viz_output produces a PipelineConfig."""
    builder = PipelineBuilder()
    config = builder.build(_make_valid_graph())

    assert isinstance(config, PipelineConfig)
    assert config.backend_name == "icp"
    assert isinstance(config.backend_params, dict)
    assert config.merger_name == "icp_union"
    assert isinstance(config.merger_params, dict)


def test_reject_cycle():
    """A graph with A->B->A edges raises ValueError mentioning 'cycle'."""
    graph = {
        "nodes": [
            {"id": "a", "type": "sensor_rgbd", "params": {}},
            {"id": "b", "type": "slam_icp", "params": {}},
        ],
        "edges": [
            {
                "source": "a",
                "sourceHandle": "image_out",
                "target": "b",
                "targetHandle": "image_in",
            },
            {
                "source": "b",
                "sourceHandle": "pose_out",
                "target": "a",
                "targetHandle": "image_in",
            },
        ],
    }
    builder = PipelineBuilder()
    with pytest.raises(ValueError, match="(?i)cycle"):
        builder.build(graph)


def test_reject_unknown_node():
    """A graph with node type 'nonexistent_backend' raises ValueError."""
    graph = {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}},
            {"id": "slam_1", "type": "slam_nonexistent_backend", "params": {}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}},
            {"id": "viz_1", "type": "viz_output", "params": {}},
        ],
        "edges": [
            {
                "source": "sensor_1",
                "sourceHandle": "image_out",
                "target": "slam_1",
                "targetHandle": "image_in",
            },
            {
                "source": "slam_1",
                "sourceHandle": "cloud_out",
                "target": "merger_1",
                "targetHandle": "cloud_in",
            },
            {
                "source": "merger_1",
                "sourceHandle": "merged_out",
                "target": "viz_1",
                "targetHandle": "cloud_in",
            },
        ],
    }
    builder = PipelineBuilder()
    with pytest.raises(ValueError, match="(?i)unknown"):
        builder.build(graph)


def test_reject_unconnected_required():
    """A SLAM node with no image input connected raises ValueError."""
    graph = {
        "nodes": [
            {"id": "slam_1", "type": "slam_icp", "params": {}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}},
            {"id": "viz_1", "type": "viz_output", "params": {}},
        ],
        "edges": [
            {
                "source": "slam_1",
                "sourceHandle": "cloud_out",
                "target": "merger_1",
                "targetHandle": "cloud_in",
            },
            {
                "source": "merger_1",
                "sourceHandle": "merged_out",
                "target": "viz_1",
                "targetHandle": "cloud_in",
            },
        ],
    }
    builder = PipelineBuilder()
    with pytest.raises(ValueError, match="(?i)(unconnected|required|missing)"):
        builder.build(graph)


def test_parameter_node_override():
    """A param_scalar node connected to a slam node overrides the param value."""
    graph = {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}},
            {"id": "param_1", "type": "param_scalar", "params": {"value": 0.05}},
            {"id": "slam_1", "type": "slam_icp", "params": {"voxel_size": 0.1}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}},
            {"id": "viz_1", "type": "viz_output", "params": {}},
        ],
        "edges": [
            {
                "source": "sensor_1",
                "sourceHandle": "image_out",
                "target": "slam_1",
                "targetHandle": "image_in",
            },
            {
                "source": "param_1",
                "sourceHandle": "value_out",
                "target": "slam_1",
                "targetHandle": "voxel_size",
            },
            {
                "source": "slam_1",
                "sourceHandle": "cloud_out",
                "target": "merger_1",
                "targetHandle": "cloud_in",
            },
            {
                "source": "slam_1",
                "sourceHandle": "pose_out",
                "target": "merger_1",
                "targetHandle": "pose_in",
            },
            {
                "source": "merger_1",
                "sourceHandle": "merged_out",
                "target": "viz_1",
                "targetHandle": "cloud_in",
            },
        ],
    }
    builder = PipelineBuilder()
    config = builder.build(graph)
    assert config.backend_params["voxel_size"] == 0.05


def test_node_catalog():
    """NodeCatalog.get_catalog() returns static + registry-discovered nodes."""
    catalog = NodeCatalog.get_catalog()

    types = [entry["type"] for entry in catalog]

    # Static nodes must be present
    assert "sensor_rgbd" in types
    assert "filter_voxel_downsample" in types
    assert "viz_output" in types

    # Registry-discovered SLAM backend
    assert "slam_icp" in types

    # Registry-discovered merge strategy
    assert "merger_icp_union" in types

    # Check structure of a catalog entry
    sensor = next(e for e in catalog if e["type"] == "sensor_rgbd")
    assert "label" in sensor
    assert "category" in sensor
    assert "inputs" in sensor
    assert "outputs" in sensor
