import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.servicenow")


class ServiceNowChannel(NotificationChannel):
    """Creates an incident on a ServiceNow instance via its REST Table API.

    Complements JiraChannel: ServiceNow is the common ticketing/ITSM platform
    in larger (or regulated) orgs, while Jira targets Atlassian shops. Both
    follow the same contract; a non-configured channel is skipped silently.

    Auth uses the Basic auth over the standard ``table`` API
    (``/api/now/table/incident``). A ``--caller id`` is auto-derived from the
    notification ``source`` when borrowing the short_description.
    """

    name = "servicenow"

    def __init__(
        self,
        instance: str = "",
        username: str = "",
        password: str = "",
        table: str = "incident",
    ):
        # instance: es. "https://dev12345.service-now.com"
        self.instance = instance.rstrip("/")
        self.username = username
        self.password = password
        self.table = table.strip().lower() or "incident"

    def is_configured(self) -> bool:
        return bool(self.instance and self.username and self.password)

    def _table_url(self) -> str:
        return f"{self.instance}/api/now/table/{self.table}"

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("ServiceNow channel not configured, skipping incident creation.")
            return False

        payload = {
            "short_description": f"[{severity.upper()}] {title}"[:160],
            "description": f"Severity: {severity.upper()}\n\n{message}\n\nAutomated security notification from Asgard (Gjallarhorn).",
            "urgency": "3",  # scala 1..3 (1 = più alta): mappiamo la severità sotto
            "contact_type": "alert",
        }
        if severity.lower() == "critical":
            payload["urgency"] = "1"
        elif severity.lower() == "high":
            payload["urgency"] = "2"

        try:
            resp = requests.post(
                self._table_url(),
                json=payload,
                auth=(self.username, self.password),
                timeout=10,
            )
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(
                "ServiceNow returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to create ServiceNow incident: %s", e)
            return False