"""Plan 07-04 target — DET-PIPELINE-05 SC#5.

Asserts PipelineBuilder.build populates new PipelineConfig fields
(detector_name/detector_params/lifter_name/lifter_params/tracker_name/tracker_params)
from a graph containing detector_yolov11 + detection3d_point_cluster +
tracker_none nodes. Mirror of tests/coordination/test_pipeline_builder.py
registry side-effect fixture pattern.
"""
import pytest

pytest.skip(
    "Wave 0 stub — DET-PIPELINE-05 SC#5 lockdown (implemented in Plan 07-04)",
    allow_module_level=True,
)


def test_pipeline_builder_populates_perception_fields() -> None:
    # TODO Plan 07-04: import PipelineBuilder, build a 3-node perception graph,
    # assert config.detector_name == "yolov11", config.lifter_name == "point_cluster",
    # config.tracker_name == "none".
    assert False, "implemented in Plan 07-04"


def test_unknown_detector_raises_value_error() -> None:
    # TODO Plan 07-04: assert ValueError on detector_bogusname node type.
    assert False, "implemented in Plan 07-04"


def test_unknown_lifter_raises_value_error() -> None:
    # TODO Plan 07-04: assert ValueError on detection3d_bogusname node type.
    assert False, "implemented in Plan 07-04"


def test_unknown_tracker_raises_value_error() -> None:
    # TODO Plan 07-04: assert ValueError on tracker_bogusname node type.
    assert False, "implemented in Plan 07-04"


def test_node_catalog_lists_perception_entries() -> None:
    # TODO Plan 07-04: NodeCatalog.get_catalog() includes detector_yolov11,
    # detection3d_point_cluster, tracker_none entries with category="perception".
    assert False, "implemented in Plan 07-04"
