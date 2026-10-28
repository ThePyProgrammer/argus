import math

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.web.spawn_routes import StartupSpawnSelection, router


def client_for(defaults=None):
    app = FastAPI()
    app.include_router(router)
    selection = StartupSpawnSelection('office', defaults or {'robot_a': (0., 0., 0.73)})
    app.state.startup_spawn = selection
    return TestClient(app), selection


def test_confirmation_preserves_platform_height_and_releases_startup_once():
    client, selection = client_for()
    assert client.get('/api/spawn').json()['awaiting_selection'] is True
    assert not selection.ready.is_set()
    response = client.post('/api/spawn', json={'positions': {'robot_a': [2.5, -1.25]}})
    assert response.status_code == 200
    assert selection.positions == {'robot_a': (2.5, -1.25, 0.73)}
    assert selection.ready.is_set()
    assert client.get('/api/spawn').json()['awaiting_selection'] is False
    assert client.post('/api/spawn', json={'positions': {'robot_a': [0, 0]}}).status_code == 409


@pytest.mark.parametrize('positions', [{}, {'robot_b': [0, 0]}, {'robot_a': [0, 0, 0]}, {'robot_a': [1001, 0]}])
def test_invalid_selection_does_not_release_simulation(positions):
    client, selection = client_for()
    assert client.post('/api/spawn', json={'positions': positions}).status_code == 422
    assert not selection.ready.is_set()


def test_overlapping_robots_are_rejected():
    client, selection = client_for({'robot_a': (0, 0, .3), 'robot_b': (5, 0, .3)})
    response = client.post('/api/spawn', json={'positions': {'robot_a': [1, 1], 'robot_b': [1.1, 1]}})
    assert response.status_code == 422
    assert not selection.ready.is_set()


def test_non_finite_positions_cannot_release_simulation():
    _, selection = client_for()
    with pytest.raises(ValueError):
        selection.choose({'robot_a': (math.nan, 0)})
    assert not selection.ready.is_set()


def test_restart_selection_works_without_startup_picker_and_preserves_height():
    from unittest.mock import Mock
    client, selection = client_for({'robot_a': (0, 0, .73), 'robot_b': (5, 0, .73)})
    client.app.state.startup_spawn = None
    client.app.state.restart_spawn = selection
    callback = Mock()
    client.app.state.command_callback = callback
    assert client.get('/api/spawn/restart').json()['robot_ids'] == ['robot_a', 'robot_b']
    callback.assert_not_called()
    assert client.post('/api/spawn/restart', json={'positions': {'robot_a': [1, 1]}}).status_code == 422
    callback.assert_not_called()
    response = client.post('/api/spawn/restart', json={'positions': {'robot_a': [1, 1], 'robot_b': [3, 4]}})
    assert response.status_code == 200
    callback.assert_called_once_with({'action': 'restart', 'positions': {'robot_a': (1, 1, .73), 'robot_b': (3, 4, .73)}})
    assert not selection.ready.is_set()  # reusable on later restarts


def test_restart_rejects_overlap_and_pending_startup():
    from unittest.mock import Mock
    client, selection = client_for({'robot_a': (0, 0, .3), 'robot_b': (5, 0, .3)})
    client.app.state.restart_spawn = selection
    client.app.state.command_callback = Mock()
    body = {'positions': {'robot_a': [1, 1], 'robot_b': [1.1, 1]}}
    assert client.post('/api/spawn/restart', json=body).status_code == 409
    selection.ready.set()
    assert client.post('/api/spawn/restart', json=body).status_code == 422
    client.app.state.command_callback.assert_not_called()


def test_spawn_status_previews_match_bridge_heading_order_and_remain_available():
    from backend.web.spawn_routes import set_simulation_status
    client, selection = client_for({'robot_a': (0, 0, .3), 'robot_b': (5, 0, .3)})
    response = client.post('/api/spawn', json={'positions': {'robot_b': [3, 4], 'robot_a': [1, 2]}})
    status = response.json()['status']
    assert status['phase'] == 'loading'
    assert status['positions']['robot_a'] == [1, 2, .3]
    assert status['headings'] == {'robot_a': 0., 'robot_b': math.pi}
    assert client.get('/api/spawn/status').json() == status
    set_simulation_status(client.app, 'ready', 'Simulation ready')
    ready = client.get('/api/spawn/status').json()
    assert ready['phase'] == 'ready'
    assert ready['positions'] == status['positions']
