import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.webhook")


class WebhookChannel(NotificationChannel):
    """Posts a JSON payload to a generic webhook URL.

    The payload shape (`{"text": "..."}`) is compatible out of the box with
    both Slack incoming webhooks and Discord webhooks, which both accept a
    top-level "text" field.
    """

    name = "webhook"

    def __init__(self, url: str = ""):
        self.url = url

    def is_configured(self) -> bool:
        return bool(self.url)

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("Webhook channel not configured, skipping send.")
            return False

        payload = {
            "text": f"[{severity.upper()}] {title}\n{message}",
            "source": "gjallarhorn",
            "severity": severity,
            "title": title,
            "message": message,
        }

        try:
            resp = requests.post(self.url, json=payload, timeout=10)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(
                "Webhook endpoint returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to send webhook notification: %s", e)
            return False
