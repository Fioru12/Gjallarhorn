import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.opsgenie")

# Priorita' Opsgenie P1 (max) -> P5 (min) mappate dalla severita' Asgard.
_PRIORITY_MAP = {
    "critical": "P1",
    "high": "P2",
    "medium": "P3",
    "low": "P5",
}


class OpsgenieChannel(NotificationChannel):
    """Crea alert Opsgenie via Alert API (api.opsgenie.com o .eu).

    Auth: header `Authorization: GenieKey <api_key>`. Accettato come successo
    solo HTTP 202 (la API risponde 202 + requestId in async). `alias` = title
    troncato a 512ch (limite API) per deduplicare alert ripetuti.
    """

    name = "opsgenie"

    def __init__(self, api_key: str = "", eu: bool = False):
        self.api_key = api_key
        self.eu = eu

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def _alerts_url(self) -> str:
        base = "https://api.eu.opsgenie.com" if self.eu else "https://api.opsgenie.com"
        return base + "/v2/alerts"

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("Opsgenie channel not configured, skipping send.")
            return False

        payload = {
            "message": f"[{severity.upper()}] {title}",
            "description": message,
            "priority": _PRIORITY_MAP.get((severity or "").lower(), "P3"),
            "alias": title[:512],
            "tags": ["gjallarhorn", (severity or "medium").lower()],
        }

        try:
            resp = requests.post(
                self._alerts_url, json=payload,
                headers={"Authorization": f"GenieKey {self.api_key}"},
                timeout=10,
            )
            if resp.status_code == 202:
                return True
            logger.warning(
                "Opsgenie endpoint returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to send Opsgenie notification: %s", e)
            return False
