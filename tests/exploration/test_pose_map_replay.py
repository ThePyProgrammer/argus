"""Independent labels distinguish pose, classification, and historical map error."""
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.pose_map_archive import ScanArchive, read_scans
from scripts.replay_pose_map import replay, corrected_points
from src.exploration.floor_filter import FloorFilter


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pose_map_replay"


def frozen(name):
    with np.load(FIXTURES / (name + ".npz"), allow_pickle=False) as data:
        for i, time_s in enumerate(data["times"]):
            start, end = data["offsets"][i:i+2]
            yield dict(time_s=time_s, points=data["points"][start:end], mask=data["masks"][start:end],
                       estimated=data["estimated"][i], truth=data["truth"][i])


def test_frozen_translation_error_does_not_become_floor_error():
    result = replay(frozen("translation_drift"))
    assert result["recorded_mask_disagreements"] == 0
    assert all(r[branch]["missed_floor"] == 0 for r in result["frames"] for branch in ("estimated", "known"))
    assert result["maps"]["estimated_oracle_floor"]["paired_placement_error_m"]["max"] == pytest.approx(.08)
    assert result["maps"]["known"]["paired_placement_error_m"]["max"] == 0
    assert result["maps"]["estimated"]["fixed_lattice"]["extra"] > 0


def test_frozen_narrow_view_and_low_obstacles_expose_classification_separately():
    result = replay(frozen("narrow_floor"))
    first, acquired, narrow = result["frames"]
    for branch in ("estimated", "known"):
        assert first[branch]["missed_floor"] == 50
        assert acquired[branch]["missed_floor"] == narrow[branch]["missed_floor"] == 0
        assert all(r[branch]["removed_raised"] == 0 for r in result["frames"])
        # A 6 mm feature is inside the existing 15 mm plane band. Report the
        # resolution limit honestly rather than adjusting the acceptance label.
        assert narrow[branch]["removed_low_obstacle"] == 50
    assert result["maps"]["estimated"]["retained_true_floor_samples"] == 0
    assert result["maps"]["estimated"]["paired_placement_error_m"]["max"] == 0
    assert result["maps"]["estimated"]["fixed_lattice"]["missing"] > 0


def test_frozen_map_history_remains_wrong_after_current_pose_recovers():
    result = replay(frozen("historical_placement"))
    assert result["frames"][-1]["camera_translation_error_m"] == 0
    assert result["frames"][-1]["observation_placement_m"]["max"] == 0
    assert result["maps"]["estimated_oracle_floor"]["paired_placement_error_m"]["max"] == pytest.approx(.08)
    assert result["maps"]["known_oracle_floor"]["paired_placement_error_m"]["max"] == 0


def test_archive_roundtrip_is_detached_lossless_and_checks_integrity(tmp_path):
    directory = tmp_path / "scans"
    archive = ScanArchive(directory, chunk_frames=2)
    scans = list(frozen("translation_drift"))
    before = [r["points"].copy() for r in scans]
    for row in scans:
        archive.append("robot_a", row["time_s"], row["points"], row["mask"], row["estimated"], row["truth"], FloorFilter(), .1)
        row["points"][:] = 99
    archive.finish(complete=True)
    actual = list(read_scans(directory, "robot_a"))
    for row, expected in zip(actual, before):
        np.testing.assert_array_equal(row["points"], expected)
    assert replay(actual)["recorded_mask_disagreements"] == 0
    manifest = json.loads((directory / "manifest.json").read_text())
    path = directory / manifest["chunks"][0]["file"]
    with path.open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        list(read_scans(directory, "robot_a"))


def test_pose_correction_preserves_inputs_and_uses_full_rotation():
    from scipy.spatial.transform import Rotation
    truth = np.eye(4)
    estimate = np.eye(4)
    estimate[:3, :3] = Rotation.from_euler("xyz", [.2, -.1, .3]).as_matrix()
    estimate[:3, 3] = [1, 2, 3]
    actual = np.array([[2., 0., 0.], [2., 1., .06]])
    points = actual @ estimate[:3, :3].T + estimate[:3, 3]
    before = points.copy()
    np.testing.assert_allclose(corrected_points(points, estimate, truth), actual, atol=1e-14)
    np.testing.assert_array_equal(points, before)


def test_partial_archive_keeps_flushed_and_pending_frames(tmp_path):
    archive = ScanArchive(tmp_path / "scans", chunk_frames=1)
    row = next(frozen("translation_drift"))
    archive.append("robot_a", row["time_s"], row["points"], row["mask"], row["estimated"], row["truth"], FloorFilter(), .1)
    archive.finish(complete=False)
    assert len(list(read_scans(tmp_path / "scans", "robot_a"))) == 1
    assert not json.loads((tmp_path / "scans" / "manifest.json").read_text())["complete"]


@pytest.mark.timeout(120)
def test_recording_leaves_real_episode_commands_and_body_trace_unchanged(tmp_path):
    from scripts.diagnose_exploration_floor import diagnose_floor
    plain = diagnose_floor("connected_rooms", 101, .04, tmp_path / "plain")
    recorded = diagnose_floor("connected_rooms", 101, .04, tmp_path / "recorded", record_scans=True)
    assert recorded["episode"]["commands"] == plain["episode"]["commands"]
    assert recorded["episode"]["trajectory"] == plain["episode"]["trajectory"]
    assert recorded["episode"]["result"]["coverage"] == plain["episode"]["result"]["coverage"]
    for rid in recorded["initial"]:
        scans = list(read_scans(tmp_path / "recorded" / "scans", rid))
        assert len(scans) == 4
        assert replay(scans)["recorded_mask_disagreements"] == 0
