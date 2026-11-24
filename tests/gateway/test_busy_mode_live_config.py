"""display.busy_input_mode is re-read from config.yaml per message: no gateway restart needed."""

import pytest

import gateway.run as gateway_run
from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import SessionSource
from gateway.run import GatewayRunner


def _runner(*, multiplex: bool = False, startup_mode: str = "interrupt") -> GatewayRunner:
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(multiplex_profiles=multiplex)
    runner._busy_input_mode = startup_mode
    runner._busy_text_mode = "queue" if startup_mode == "queue" else "interrupt"
    return runner


def _source(profile: str | None = None) -> SessionSource:
    return SessionSource(platform=Platform.TELEGRAM, chat_id="c", chat_type="dm", user_id="u", profile=profile)


def _write_config(home, text: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(text, encoding="utf-8")


@pytest.fixture
def bridged(monkeypatch):
    """Simulate the startup bridge having copied ``busy_input_mode: interrupt`` into env."""
    monkeypatch.setattr(gateway_run, "_BRIDGED_ENV_VALUES", {})
    monkeypatch.delenv("HERMES_GATEWAY_BUSY_INPUT_MODE", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_BUSY_TEXT_MODE", raising=False)
    gateway_run._bridge_section_to_env({"busy_input_mode": "interrupt"}, gateway_run._DISPLAY_ENV_BRIDGE)
    yield


def test_edited_config_beats_the_startup_env_copy(bridged, tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_gateway_config_home", lambda: tmp_path)
    _write_config(tmp_path, "display:\n  busy_input_mode: queue\n")
    runner = _runner()

    assert runner._effective_busy_input_mode(_source()) == "queue"
    assert runner._effective_busy_text_mode(_source()) == "queue"

    _write_config(tmp_path, "display:\n  busy_input_mode: steer\n")
    assert runner._effective_busy_input_mode(_source()) == "steer"


def test_operator_env_override_still_wins(bridged, tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_gateway_config_home", lambda: tmp_path)
    _write_config(tmp_path, "display:\n  busy_input_mode: queue\n")
    monkeypatch.setenv("HERMES_GATEWAY_BUSY_INPUT_MODE", "steer")  # set by hand, not by the bridge
    runner = _runner(startup_mode="steer")

    assert runner._effective_busy_input_mode(_source()) == "steer"


def test_no_value_in_file_keeps_the_startup_mode(bridged, tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_gateway_config_home", lambda: tmp_path)
    _write_config(tmp_path, "display:\n  show_reasoning: true\n")
    runner = _runner(startup_mode="queue")

    assert runner._effective_busy_input_mode(_source()) == "queue"


def test_routed_profile_reads_its_own_edited_file(bridged, monkeypatch):
    from hermes_constants import get_hermes_home
    home = get_hermes_home() / "profiles" / "research"
    _write_config(home, "display:\n  busy_input_mode: interrupt\n")
    runner = _runner(multiplex=True)
    runner._snapshot_profile_busy_modes("research", {"display": {"busy_input_mode": "interrupt"}})

    assert runner._effective_busy_input_mode(_source("research")) == "interrupt"
    _write_config(home, "display:\n  busy_input_mode: queue\n")
    assert runner._effective_busy_input_mode(_source("research")) == "queue"
