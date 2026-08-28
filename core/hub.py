import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.channels.base import NotificationChannel
from core.db import NotificationDB

logger = logging.getLogger("gjallarhorn.hub")

VALID_SEVERITIES = ("low", "medium", "high", "critical")


class NotificationHub:
    """Central alerting hub: dedups/throttles repeated notifications and
    fans out the rest to the configured channels.

    This is the piece Gjallarhorn exists to centralize: Heimdall, Sleipnir
    and the other Asgard modules each used to reimplement their own
    (usually Telegram-only) notification logic. NotificationHub is the one
    place that logic now lives.
    """

    def __init__(
        self,
        channels: Dict[str, NotificationChannel],
        db: NotificationDB,
        dedup_window_seconds: int = 300,
        default_channels: Optional[List[str]] = None,
    ):
        self.channels = channels
        self.db = db
        self.dedup_window = timedelta(seconds=dedup_window_seconds)
        self.default_channels = default_channels or list(channels.keys())

    def notify(
        self,
        source: str,
        severity: str,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        severity = severity.lower()
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity '{severity}', must be one of {VALID_SEVERITIES}")

        now = datetime.now(timezone.utc)
        last_sent_at = self.db.get_last_sent_at(source, title)

        if last_sent_at is not None and (now - last_sent_at) < self.dedup_window:
            suppressed_count = self.db.record_suppressed(source, title, severity, message, when=now)
            logger.info(
                "Suppressed duplicate notification for (%s, %s) - suppressed %d time(s) so far",
                source,
                title,
                suppressed_count,
            )
            return {
                "status": "suppressed",
                "sent_to": [],
                "suppressed_count": suppressed_count,
            }

        target_channels = channels if channels else self.default_channels
        sent_to: List[str] = []

        for channel_name in target_channels:
            channel = self.channels.get(channel_name)
            if channel is None:
                logger.warning("Unknown channel '%s' requested, skipping.", channel_name)
                continue
            if not channel.is_configured():
                logger.info("Channel '%s' is not configured, skipping.", channel_name)
                continue
            try:
                if channel.send(title, message, severity):
                    sent_to.append(channel_name)
                else:
                    logger.warning("Channel '%s' failed to deliver the notification.", channel_name)
            except Exception as e:  # a misbehaving channel must never break the hub
                logger.warning("Channel '%s' raised an unexpected error: %s", channel_name, e)

        self.db.record_sent(source, title, severity, message, sent_to, when=now)

        return {"status": "sent", "sent_to": sent_to, "suppressed_count": 0}

    def get_history(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return self.db.get_history(limit=limit, offset=offset)
