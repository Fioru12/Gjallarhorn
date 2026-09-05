import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.teams")

# Colori in stile Teams (hex senza '#') per severità: i MessageCard li accettano
# come "themeColor" per dare un segnale visivo immediato nel pop-in.
SEVERITY_COLORS = {
    "critical": "b22222",
    "high": "ff8c00",
    "medium": "eab308",
    "low": "3b82f6",
}


class TeamsChannel(NotificationChannel):
    """Sends an Adaptive Card / MessageCard to a Microsoft Teams webhook.

    Works with the classic Teams "Incoming Webhook" connectors, which expect a
    ``MessageCard`` payload. Because the JSON shape differs from the generic
    ``{"text": ...}`` used by Slack/Discord, this channel is kept separate from
    ``WebhookChannel`` rather than being collapsed into it.
    """

    name = "teams"

    def __init__(self, url: str = ""):
        self.url = url

    def is_configured(self) -> bool:
        return bool(self.url)

    def _severity_color(self, severity: str) -> str:
        return SEVERITY_COLORS.get((severity or "").lower(), "3b82f6")

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("Teams channel not configured, skipping send.")
            return False

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": title,
            "themeColor": self._severity_color(severity),
            "title": f"[{severity.upper()}] {title}",
            "text": message,
        }

        try:
            resp = requests.post(self.url, json=payload, timeout=10)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(
                "Teams endpoint returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to send Teams notification: %s", e)
            return False