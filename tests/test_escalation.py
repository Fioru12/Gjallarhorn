import os
import sys
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.channels.pagerduty import PagerDutyChannel
from core.channels.opsgenie import OpsgenieChannel
from core.channels import build_channels


def test_pagerduty_not_configured_skips():
    ch = PagerDutyChannel()
    assert ch.is_configured() is False
    with patch("core.channels.pagerduty.requests.post") as m:
        assert ch.send("t", "m", "critical") is False
        m.assert_not_called()


def test_pagerduty_trigger_payload_and_severity_map():
    ch = PagerDutyChannel(routing_key="RK")
    with patch("core.channels.pagerduty.requests.post", return_value=MagicMock(status_code=202)) as m:
        assert ch.send("Disk on fire", "boom", "critical") is True
        payload = m.call_args[1]["json"]
        assert m.call_args[0][0] == "https://events.pagerduty.com/v2/enqueue"
        assert payload["routing_key"] == "RK"
        assert payload["event_action"] == "trigger"
        assert payload["payload"]["severity"] == "critical"
    with patch("core.channels.pagerduty.requests.post", return_value=MagicMock(status_code=202)) as m:
        ch.send("t", "m", "high")
        assert m.call_args[1]["json"]["payload"]["severity"] == "error"


def test_pagerduty_non_2xx_and_exception_are_false():
    ch = PagerDutyChannel(routing_key="RK")
    with patch("core.channels.pagerduty.requests.post", return_value=MagicMock(status_code=400, text="bad")):
        assert ch.send("t", "m", "high") is False
    with patch("core.channels.pagerduty.requests.post", side_effect=requests.ConnectionError("down")):
        assert ch.send("t", "m", "high") is False


def test_opsgenie_not_configured_skips():
    ch = OpsgenieChannel()
    assert ch.is_configured() is False
    with patch("core.channels.opsgenie.requests.post") as m:
        assert ch.send("t", "m", "critical") is False
        m.assert_not_called()


def test_opsgenie_202_only_and_priority_map():
    ch = OpsgenieChannel(api_key="K")
    with patch("core.channels.opsgenie.requests.post", return_value=MagicMock(status_code=202)) as m:
        assert ch.send("DB down", "boom", "critical") is True
        assert m.call_args[0][0] == "https://api.opsgenie.com/v2/alerts"
        assert m.call_args[1]["headers"] == {"Authorization": "GenieKey K"}
        assert m.call_args[1]["json"]["priority"] == "P1"
    eu = OpsgenieChannel(api_key="K", eu=True)
    with patch("core.channels.opsgenie.requests.post", return_value=MagicMock(status_code=202)) as m:
        eu.send("t", "m", "low")
        assert m.call_args[0][0] == "https://api.eu.opsgenie.com/v2/alerts"
        assert m.call_args[1]["json"]["priority"] == "P5"
    with patch("core.channels.opsgenie.requests.post", return_value=MagicMock(status_code=200, text="ok")):
        assert ch.send("t", "m", "high") is False


def test_build_channels_registers_both(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "RK")
    monkeypatch.setenv("OPSGENIE_API_KEY", "OK")
    from core.config import load_config
    channels = build_channels(load_config(path="nonexistent.yaml"))
    assert channels["pagerduty"].is_configured() is True
    assert channels["opsgenie"].is_configured() is True
