from unittest.mock import MagicMock, patch

from core.channels.email_smtp import SMTPChannel
from core.channels.telegram import TelegramChannel
from core.channels.webhook import WebhookChannel


class TestTelegramChannel:
    def test_not_configured_skips_without_network_call(self):
        channel = TelegramChannel(bot_token="", chat_id="")
        assert channel.is_configured() is False
        with patch("core.channels.telegram.requests.post") as mock_post:
            result = channel.send("Title", "Message", "high")
        assert result is False
        mock_post.assert_not_called()

    def test_configured_sends_without_parse_mode(self):
        channel = TelegramChannel(bot_token="TOKEN", chat_id="12345")
        assert channel.is_configured() is True

        mock_response = MagicMock(status_code=200)
        with patch("core.channels.telegram.requests.post", return_value=mock_response) as mock_post:
            result = channel.send("Alert Title", "Alert body", "critical")

        assert result is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "api.telegram.org/botTOKEN/sendMessage" in args[0]
        payload = kwargs["json"]
        assert payload["chat_id"] == "12345"
        assert "parse_mode" not in payload
        assert "Alert Title" in payload["text"]

    def test_send_returns_false_on_non_200(self):
        channel = TelegramChannel(bot_token="TOKEN", chat_id="12345")
        mock_response = MagicMock(status_code=400, text="Bad Request")
        with patch("core.channels.telegram.requests.post", return_value=mock_response):
            assert channel.send("T", "M", "low") is False

    def test_send_never_raises_on_network_error(self):
        import requests

        channel = TelegramChannel(bot_token="TOKEN", chat_id="12345")
        with patch("core.channels.telegram.requests.post", side_effect=requests.ConnectionError("boom")):
            assert channel.send("T", "M", "low") is False


class TestWebhookChannel:
    def test_not_configured_skips(self):
        channel = WebhookChannel(url="")
        assert channel.is_configured() is False
        with patch("core.channels.webhook.requests.post") as mock_post:
            assert channel.send("T", "M", "medium") is False
        mock_post.assert_not_called()

    def test_configured_posts_json(self):
        channel = WebhookChannel(url="https://hooks.example.com/xyz")
        mock_response = MagicMock(status_code=200)
        with patch("core.channels.webhook.requests.post", return_value=mock_response) as mock_post:
            result = channel.send("Title", "Body", "high")
        assert result is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://hooks.example.com/xyz"
        assert "text" in kwargs["json"]

    def test_send_never_raises_on_network_error(self):
        import requests

        channel = WebhookChannel(url="https://hooks.example.com/xyz")
        with patch("core.channels.webhook.requests.post", side_effect=requests.Timeout("timeout")):
            assert channel.send("T", "M", "low") is False


class TestSMTPChannel:
    def test_not_configured_skips(self):
        channel = SMTPChannel(host="", to_addrs=[])
        assert channel.is_configured() is False
        with patch("core.channels.email_smtp.smtplib.SMTP") as mock_smtp:
            assert channel.send("T", "M", "low") is False
        mock_smtp.assert_not_called()

    def test_configured_sends_email(self):
        channel = SMTPChannel(
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="secret",
            from_addr="user@example.com",
            to_addrs=["ops@example.com"],
            use_tls=True,
        )
        assert channel.is_configured() is True

        mock_server = MagicMock()
        mock_smtp_cm = MagicMock()
        mock_smtp_cm.__enter__.return_value = mock_server
        with patch("core.channels.email_smtp.smtplib.SMTP", return_value=mock_smtp_cm) as mock_smtp:
            result = channel.send("Title", "Body", "critical")

        assert result is True
        mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=10)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.sendmail.assert_called_once()

    def test_send_never_raises_on_smtp_error(self):
        import smtplib

        channel = SMTPChannel(
            host="smtp.example.com",
            from_addr="user@example.com",
            to_addrs=["ops@example.com"],
        )
        with patch("core.channels.email_smtp.smtplib.SMTP", side_effect=smtplib.SMTPException("boom")):
            assert channel.send("T", "M", "low") is False
