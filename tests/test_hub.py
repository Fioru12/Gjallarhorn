import os
import tempfile
from unittest.mock import MagicMock

import pytest

from core.db import NotificationDB
from core.hub import NotificationHub


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass  # Windows may keep a brief lock on the sqlite file handle


def make_mock_channel(configured=True, send_result=True):
    channel = MagicMock()
    channel.is_configured.return_value = configured
    channel.send.return_value = send_result
    return channel


class TestDedupAndThrottling:
    def test_duplicate_within_window_is_sent_only_once(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        telegram = make_mock_channel()
        hub = NotificationHub(
            channels={"telegram": telegram},
            db=db,
            dedup_window_seconds=300,
            default_channels=["telegram"],
        )

        first = hub.notify("heimdall", "high", "Brute force", "message 1")
        second = hub.notify("heimdall", "high", "Brute force", "message 2")

        assert first["status"] == "sent"
        assert second["status"] == "suppressed"
        assert second["suppressed_count"] == 1
        # The channel must only have actually been called once.
        telegram.send.assert_called_once()

    def test_third_duplicate_increments_suppressed_counter(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        telegram = make_mock_channel()
        hub = NotificationHub(
            channels={"telegram": telegram},
            db=db,
            dedup_window_seconds=300,
            default_channels=["telegram"],
        )

        hub.notify("heimdall", "high", "Brute force", "m1")
        hub.notify("heimdall", "high", "Brute force", "m2")
        third = hub.notify("heimdall", "high", "Brute force", "m3")

        assert third["status"] == "suppressed"
        assert third["suppressed_count"] == 2
        telegram.send.assert_called_once()

    def test_different_title_is_not_deduplicated(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        telegram = make_mock_channel()
        hub = NotificationHub(
            channels={"telegram": telegram},
            db=db,
            dedup_window_seconds=300,
            default_channels=["telegram"],
        )

        hub.notify("heimdall", "high", "Brute force", "m1")
        result = hub.notify("heimdall", "high", "Port scan", "m2")

        assert result["status"] == "sent"
        assert telegram.send.call_count == 2

    def test_notification_after_window_expires_is_sent_again(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        telegram = make_mock_channel()
        hub = NotificationHub(
            channels={"telegram": telegram},
            db=db,
            dedup_window_seconds=0,  # window already expired immediately
            default_channels=["telegram"],
        )

        hub.notify("heimdall", "high", "Brute force", "m1")
        result = hub.notify("heimdall", "high", "Brute force", "m2")

        assert result["status"] == "sent"
        assert telegram.send.call_count == 2


class TestChannelDispatch:
    def test_unconfigured_channel_is_skipped_not_crashed(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        unconfigured = make_mock_channel(configured=False)
        hub = NotificationHub(
            channels={"telegram": unconfigured},
            db=db,
            default_channels=["telegram"],
        )

        result = hub.notify("source", "low", "Title", "Message")

        assert result["status"] == "sent"
        assert result["sent_to"] == []
        unconfigured.send.assert_not_called()

    def test_unknown_channel_name_is_skipped(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        hub = NotificationHub(channels={}, db=db, default_channels=[])

        result = hub.notify("source", "low", "Title", "Message", channels=["does-not-exist"])

        assert result["status"] == "sent"
        assert result["sent_to"] == []

    def test_channel_exception_does_not_break_other_channels(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        broken = MagicMock()
        broken.is_configured.return_value = True
        broken.send.side_effect = RuntimeError("boom")

        working = make_mock_channel()

        hub = NotificationHub(
            channels={"broken": broken, "working": working},
            db=db,
            default_channels=["broken", "working"],
        )

        result = hub.notify("source", "low", "Title", "Message")

        assert result["status"] == "sent"
        assert result["sent_to"] == ["working"]

    def test_explicit_channels_override_defaults(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        a = make_mock_channel()
        b = make_mock_channel()
        hub = NotificationHub(
            channels={"a": a, "b": b},
            db=db,
            default_channels=["a", "b"],
        )

        result = hub.notify("source", "low", "Title", "Message", channels=["b"])

        assert result["sent_to"] == ["b"]
        a.send.assert_not_called()
        b.send.assert_called_once()

    def test_invalid_severity_raises_value_error(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        hub = NotificationHub(channels={}, db=db, default_channels=[])
        with pytest.raises(ValueError):
            hub.notify("source", "apocalyptic", "Title", "Message")


class TestHistory:
    def test_history_returns_paginated_records(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        telegram = make_mock_channel()
        hub = NotificationHub(channels={"telegram": telegram}, db=db, default_channels=["telegram"])

        hub.notify("heimdall", "high", "Alert A", "m")
        hub.notify("heimdall", "medium", "Alert B", "m")

        result = hub.get_history(limit=1, offset=0)

        assert result["total"] == 2
        assert len(result["items"]) == 1
        assert result["limit"] == 1
        assert result["offset"] == 0

    def test_history_reflects_suppressed_count(self, temp_db_path):
        db = NotificationDB(db_path=temp_db_path)
        telegram = make_mock_channel()
        hub = NotificationHub(channels={"telegram": telegram}, db=db, default_channels=["telegram"])

        hub.notify("heimdall", "high", "Alert A", "m1")
        hub.notify("heimdall", "high", "Alert A", "m2")

        result = hub.get_history()
        item = next(i for i in result["items"] if i["title"] == "Alert A")
        assert item["suppressed_count"] == 1
