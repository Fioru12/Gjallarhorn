import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.telegram")

_SEVERITY_EMOJI = {
    "low": "[i]",
    "medium": "[*]",
    "high": "[!]",
    "critical": "[!!]",
}


class TelegramChannel(NotificationChannel):
    """Sends alert notifications to a Telegram chat via the Bot API.

    Same underlying approach as Heimdall's TelegramNotifier, but corrected:
    no `parse_mode` is sent at all, since plain text needs none and
    "TEXT" (used previously in Heimdall) is not a valid Telegram parse mode.
    """

    name = "telegram"

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("Telegram channel not configured, skipping send.")
            return False

        emoji = _SEVERITY_EMOJI.get(severity.lower(), "[*]")
        text = f"{emoji} GJALLARHORN [{severity.upper()}]\n{title}\n\n{message}"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            logger.warning(
                "Telegram API returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to send Telegram notification: %s", e)
            return False
