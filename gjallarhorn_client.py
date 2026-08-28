"""Gjallarhorn client - drop this single file into any other Asgard module
to send alerts to a centralized Gjallarhorn hub instead of reimplementing
Telegram/webhook/SMTP notification logic locally.

Example (used from another Asgard module, e.g. Heimdall or Sleipnir):

    from gjallarhorn_client import notify

    ok = notify(
        hub_url="http://localhost:8090",
        api_key=os.environ["GJALLARHORN_API_KEY"],
        source="heimdall",
        severity="high",
        title="SSH Brute-Force Attack Detected",
        message="203.0.113.50 attempted 12 failed logins as 'root' in 60s.",
    )
    if not ok:
        # notify() never raises - it already logged a warning for us.
        # Fall back to local logging, retry later, etc.
        pass
"""

import logging
from typing import List, Optional

import requests

logger = logging.getLogger("gjallarhorn_client")

VALID_SEVERITIES = ("low", "medium", "high", "critical")


def notify(
    hub_url: str,
    api_key: str,
    source: str,
    severity: str,
    title: str,
    message: str,
    channels: Optional[List[str]] = None,
    timeout: float = 5.0,
) -> bool:
    """Sends a notification to a Gjallarhorn hub.

    Returns True if the hub accepted the notification (HTTP 2xx), False on
    any error - unreachable hub, timeout, non-2xx response, bad input.
    Never raises: callers can call this fire-and-forget without a
    try/except of their own.
    """
    if severity.lower() not in VALID_SEVERITIES:
        logger.warning("Invalid severity '%s', not sending notification.", severity)
        return False

    payload = {
        "source": source,
        "severity": severity.lower(),
        "title": title,
        "message": message,
    }
    if channels:
        payload["channels"] = channels

    url = f"{hub_url.rstrip('/')}/api/v1/notify"

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.warning("Could not deliver notification to Gjallarhorn hub at %s: %s", url, e)
        return False
