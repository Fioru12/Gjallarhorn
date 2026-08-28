from unittest.mock import MagicMock, patch

import requests

from gjallarhorn_client import notify


class TestGjallarhornClient:
    def test_unreachable_hub_returns_false_without_raising(self):
        with patch("gjallarhorn_client.requests.post", side_effect=requests.ConnectionError("refused")):
            result = notify(
                hub_url="http://localhost:9999",
                api_key="key",
                source="test",
                severity="high",
                title="Title",
                message="Message",
            )
        assert result is False

    def test_timeout_returns_false_without_raising(self):
        with patch("gjallarhorn_client.requests.post", side_effect=requests.Timeout("timed out")):
            result = notify(
                hub_url="http://localhost:9999",
                api_key="key",
                source="test",
                severity="high",
                title="Title",
                message="Message",
            )
        assert result is False

    def test_successful_call_returns_true(self):
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status.return_value = None
        with patch("gjallarhorn_client.requests.post", return_value=mock_response) as mock_post:
            result = notify(
                hub_url="http://localhost:8090/",
                api_key="secret-key",
                source="heimdall",
                severity="critical",
                title="Title",
                message="Message",
                channels=["telegram"],
            )
        assert result is True
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:8090/api/v1/notify"
        assert kwargs["headers"]["X-API-Key"] == "secret-key"
        assert kwargs["json"]["channels"] == ["telegram"]

    def test_http_error_status_returns_false(self):
        mock_response = MagicMock(status_code=401)
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        with patch("gjallarhorn_client.requests.post", return_value=mock_response):
            result = notify(
                hub_url="http://localhost:8090",
                api_key="wrong-key",
                source="test",
                severity="low",
                title="Title",
                message="Message",
            )
        assert result is False

    def test_invalid_severity_returns_false_without_network_call(self):
        with patch("gjallarhorn_client.requests.post") as mock_post:
            result = notify(
                hub_url="http://localhost:8090",
                api_key="key",
                source="test",
                severity="apocalyptic",
                title="Title",
                message="Message",
            )
        assert result is False
        mock_post.assert_not_called()
