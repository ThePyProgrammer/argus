"""Every recorded live outcome must get a video, including failed algorithms."""

import json
from unittest.mock import Mock

import pytest

from scripts import validate_exploration as workflow
from scripts import diagnose_exploration_contacts as diagnosis


@pytest.mark.parametrize("outcome", ["horizon", "algorithm_error", "all_unreachable"])
def test_recorded_outcome_is_rendered_before_completion(tmp_path, monkeypatch, outcome):
    output = tmp_path / "attempt"
    monkeypatch.setattr(workflow, "check_encoder", lambda: None)
    calls = []
    def diagnose(*args):
        calls.append("simulation")
        return {"episode": {"result": {"termination_reason": outcome}}}
    def render(source, destination):
        calls.append("video")
        assert source == output / "diagnosis.json"
        assert destination == output / "top-view.mp4"
        assert json.loads((output / "validation.json").read_text())["phase"] == "video"
    monkeypatch.setattr(workflow, "diagnose_floor", diagnose)
    monkeypatch.setattr(workflow, "render", render)
    workflow.validate("cluttered_room", 101, 10, output)
    assert calls == ["simulation", "video"]
    status = json.loads((output / "validation.json").read_text())
    assert status["phase"] == "complete" and status["termination_reason"] == outcome


def test_video_failure_preserves_diagnosis_and_records_incomplete_attempt(tmp_path, monkeypatch):
    output = tmp_path / "attempt"
    monkeypatch.setattr(workflow, "check_encoder", lambda: None)
    def diagnose(*args):
        (output / "diagnosis.json").write_text("preserved trace")
        return {"episode": {"result": {"termination_reason": "horizon"}}}
    monkeypatch.setattr(workflow, "diagnose_floor", diagnose)
    monkeypatch.setattr(workflow, "render", Mock(side_effect=RuntimeError("encoder failed")))
    with pytest.raises(RuntimeError, match="encoder failed"):
        workflow.validate("cluttered_room", 101, 10, output)
    assert (output / "diagnosis.json").read_text() == "preserved trace"
    status = json.loads((output / "validation.json").read_text())
    assert status["phase"] == "failed" and status["failed_phase"] == "video"


def test_existing_attempt_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "check_encoder", lambda: None)
    diagnose = Mock()
    monkeypatch.setattr(workflow, "diagnose_floor", diagnose)
    with pytest.raises(FileExistsError):
        workflow.validate("cluttered_room", 101, 10, tmp_path)
    diagnose.assert_not_called()


def test_diagnostic_error_preserves_raw_contact_history(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    episode = MagicMock()
    episode.inspect.return_value = {"result": {"valid": False}, "contact_samples": [{"contacts": ["raw"]}]}
    episode.reliability.events.return_value = [{"kind": "falls"}]
    monkeypatch.setattr(diagnosis.ExplorationEpisode, "from_scenario", lambda *a, **kw: episode)
    with pytest.raises(RuntimeError, match="capture failed"):
        with diagnosis._recorded_episode("connected_rooms", 101, 5, tmp_path, {}):
            raise RuntimeError("capture failed")
    saved = json.loads((tmp_path / "diagnosis.json").read_text())
    assert saved["episode"]["contact_samples"] == [{"contacts": ["raw"]}]
    assert saved["reliability_events"] == [{"kind": "falls"}]
    episode.inspect.assert_called_once_with(include_history=True)
