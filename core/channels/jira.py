import logging

import requests

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.jira")

_DEFAULT_ISSUE_TYPE = "Bug"


class JiraChannel(NotificationChannel):
    """Creates a Jira issue from a notification via the Jira Cloud REST API.

    This is a ticketing channel: instead of a one-way message it opens (or
    references) an issue in a project, so a critical alert can be tracked to
    resolution. Auth uses a Jira Cloud API token (Jira "API token" generated
    in the Atlassian account) sent as Basic auth with the account email.

    Follows the same contract as every other channel: never raises, returns
    True only on a 2xx response.
    """

    name = "jira"

    def __init__(
        self,
        base_url: str = "",
        email: str = "",
        api_token: str = "",
        project_key: str = "",
        issue_type: str = _DEFAULT_ISSUE_TYPE,
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key.strip().upper()
        self.issue_type = issue_type or _DEFAULT_ISSUE_TYPE

    def is_configured(self) -> bool:
        return bool(
            self.base_url and self.email and self.api_token and self.project_key
        )

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("Jira channel not configured, skipping ticket creation.")
            return False

        url = f"{self.base_url}/rest/api/2/issue"
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": f"[{severity.upper()}] {title}",
                "description": f"*Severity:* {severity.upper()}\n\n{message}\n\n_Automated security notification from Asgard._",
                "issuetype": {"name": self.issue_type},
            }
        }
        auth = (self.email, self.api_token)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        try:
            resp = requests.post(url, json=payload, auth=auth, headers=headers, timeout=10)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(
                "Jira returned status %s: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logger.warning("Failed to create Jira ticket: %s", e)
            return False