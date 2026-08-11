import json

from bbr.state.extensions import (
    update_health_status, write_artifact_fields, write_substate, write_timestamps,
)


def _state(path):
    path.write_text(json.dumps({"state": "READY", "transition_history": [{"to": "READY"}]}))


def test_write_artifact_fields_atomic(tmp_path):
    path = tmp_path / "state.json"; _state(path)
    write_artifact_fields(path, "v1", "gs://b/a", "0" * 64, "sig", "pub")
    assert json.loads(path.read_text())["artifact_version"] == "v1"
    assert not list(tmp_path.glob("state.json.*"))


def test_write_timestamps_partial_update(tmp_path):
    path = tmp_path / "state.json"; _state(path)
    write_timestamps(path, bootstrap_started_at="now")
    assert json.loads(path.read_text())["bootstrap_started_at"] == "now"


def test_write_substate_appends(tmp_path):
    path = tmp_path / "state.json"; _state(path)
    write_substate(path, "bootstrap_state", {"step": 1})
    write_substate(path, "bootstrap_state", {"step": 2})
    assert len(json.loads(path.read_text())["bootstrap_state"]) == 2


def test_update_health_status_overwrites(tmp_path):
    path = tmp_path / "state.json"; _state(path)
    update_health_status(path, "unhealthy", 1)
    update_health_status(path, "healthy", 3)
    assert json.loads(path.read_text())["health_state"]["consecutive_passes"] == 3


def test_atomic_write_preserves_transition_history(tmp_path):
    path = tmp_path / "state.json"; _state(path)
    write_timestamps(path, install_started_at="now")
    assert json.loads(path.read_text())["transition_history"] == [{"to": "READY"}]

