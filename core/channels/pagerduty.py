import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.pagerduty")

EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"

# PagerDuty Events API v2 accetta solo questi valori di severity.
_SEVERITY_MAP = {
    "critical": "critical",
    "high": "error",
    "medium": "warning",
    "low": "info",
}


class PagerDutyChannel(NotificationChannel):
    """Trigga incidenti PagerDuty via Events API v2 (routing key di integrazione).

    `event_action` e' sempre "trigger": la severita' Asgard viene mappata su
    quella PagerDuty (critical->critical, high->error, medium->warning,
    low->info). `dedup_key=title` cosi' un alert ripetuto non apre doubloni
    ma deduplica lato PagerDuty, in aggiunta al dedup locale dell'hub.
    """

    name = "pagerduty"

    def __init__(self, routing_key: str = ""):
        self.routing_key = routing_key

    def is_configured(self) -> bool:
        return bool(self.routing_key)

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("PagerDuty channel not configured, skipping send.")
            return False

        payload = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": title,
            "payload": {
                "summary": f"[{severity.upper()}] {title}",
                "source": "gjallarhorn",
                "severity": _SEVERITY_MAP.get((severity or "").lower(), "info"),
                "custom_details": {"message": message},
            },
        }

        try:
            resp = requests.post(EVENTS_API_URL, json=payload, timeout=10)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(
                "PagerDuty endpoint returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to send PagerDuty notification: %s", e)
            return False
