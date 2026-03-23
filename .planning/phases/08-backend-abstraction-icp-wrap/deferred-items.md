# Deferred Items - Phase 08

## Pre-existing Test Failures (not caused by Phase 08 changes)

1. `tests/exploration/test_coverage_tracker.py::TestExplorationConfig::test_default_values` - stuck_threshold_steps default changed from 100 to 30
2. `tests/exploration/test_path_planner.py::TestPathPlanner::test_path_through_gap` - pre-existing
3. `tests/exploration/test_path_planner.py::TestPathPlanner::test_start_on_occupied_finds_path` - pre-existing
4. `tests/integration/test_multi_mode.py::test_viz_update_interval` - AttributeError
5. `tests/integration/test_multi_robot_integration.py::test_coordinator_runs_without_crash` - pre-existing
6. `tests/integration/test_multi_robot_integration.py::test_incremental_merge_during_exploration` - pre-existing
7. `tests/integration/test_multi_robot_integration.py::test_two_robots_independent_data` - pre-existing
8. `tests/integration/test_multi_robot_integration.py::test_merged_voxels_from_both_robots` - pre-existing
9. `tests/web/test_streaming_viz.py::TestCameraFrame::test_encode_produces_header_bytes` - missing cv2 module
10. `tests/web/test_streaming_viz.py::TestCameraFrame::test_encode_decode_roundtrip` - missing cv2 module
