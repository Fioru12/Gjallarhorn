"""Tests for main.py's CLI wiring - previously 0% covered by any test."""
import pytest
import main


def test_test_notify_hub_url_path_calls_client_notify(monkeypatch, capsys):
    calls = {}

    def fake_notify(hub_url, api_key, source, severity, title, message, channels):
        calls.update(locals())
        return True

    monkeypatch.setattr("gjallarhorn_client.notify", fake_notify)
    with pytest.raises(SystemExit) as exc:
        main.test_notify(
            source="heimdall", severity="high", title="t", message="m",
            channels=["telegram"], hub_url="http://localhost:8090",
            api_key="k", config_path="config.yaml",
        )
    assert exc.value.code == 0
    assert calls["hub_url"] == "http://localhost:8090"
    assert calls["source"] == "heimdall"
    out = capsys.readouterr().out
    assert "OK" in out


def test_test_notify_hub_url_path_exits_1_on_failure(monkeypatch):
    monkeypatch.setattr("gjallarhorn_client.notify", lambda **kw: False)
    with pytest.raises(SystemExit) as exc:
        main.test_notify(
            source="heimdall", severity="high", title="t", message="m",
            channels=None, hub_url="http://localhost:8090",
            api_key=None, config_path="config.yaml",
        )
    assert exc.value.code == 1


def test_test_notify_local_dispatch_path_wires_hub_correctly(monkeypatch, capsys, tmp_path):
    """No --hub-url: must build channels from config and call
    NotificationHub.notify() with the same source/severity/title/message."""
    calls = {}

    fake_config = {"hub": {"db_path": str(tmp_path / "g.db"), "dedup_window_seconds": 300, "default_channels": ["telegram"]}}

    class FakeHub:
        def __init__(self, channels, db, dedup_window_seconds, default_channels):
            calls["channels"] = channels
            calls["dedup_window_seconds"] = dedup_window_seconds
            calls["default_channels"] = default_channels

        def notify(self, source, severity, title, message, channels):
            calls["notify_args"] = (source, severity, title, message, channels)
            return {"status": "sent", "sent_to": ["telegram"], "suppressed_count": 0}

    monkeypatch.setattr("core.config.load_config", lambda path: fake_config)
    monkeypatch.setattr("core.channels.build_channels", lambda config: {"telegram": object()})
    monkeypatch.setattr("core.db.NotificationDB", lambda db_path: object())
    monkeypatch.setattr("core.hub.NotificationHub", FakeHub)

    main.test_notify(
        source="heimdall", severity="critical", title="Alert", message="msg",
        channels=None, hub_url=None, api_key=None, config_path="config.yaml",
    )

    assert calls["notify_args"] == ("heimdall", "critical", "Alert", "msg", None)
    out = capsys.readouterr().out
    assert "Status: sent" in out
    assert "telegram" in out


def test_main_dispatches_test_notify_parses_comma_separated_channels(monkeypatch):
    calls = {}
    monkeypatch.setattr(main, "test_notify", lambda **kw: calls.update(kw))
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "test-notify", "--source", "heimdall", "--severity", "high",
         "--title", "t", "--message", "m", "--channels", "telegram, webhook"],
    )
    main.main()
    assert calls["channels"] == ["telegram", "webhook"]


def test_main_dispatches_serve_subcommand(monkeypatch):
    calls = {}
    monkeypatch.setattr(main, "serve", lambda host, port, config_path: calls.update(locals()))
    monkeypatch.setattr("sys.argv", ["main.py", "serve", "--host", "127.0.0.1", "--port", "9999"])
    main.main()
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 9999


def test_serve_sets_config_env_and_calls_uvicorn(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: calls.update(locals()))
    monkeypatch.delenv("GJALLARHORN_CONFIG", raising=False)
    main.serve(host="0.0.0.0", port=8090, config_path=str(tmp_path / "config.yaml"))
    assert calls["app"] == "api.server:app"
    assert calls["host"] == "0.0.0.0"
    import os
    assert os.environ["GJALLARHORN_CONFIG"] == str(tmp_path / "config.yaml")
