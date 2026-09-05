from typing import Any, Dict

from core.channels.base import NotificationChannel
from core.channels.telegram import TelegramChannel
from core.channels.webhook import WebhookChannel
from core.channels.teams import TeamsChannel
from core.channels.jira import JiraChannel
from core.channels.servicenow import ServiceNowChannel
from core.channels.email_smtp import SMTPChannel

__all__ = [
    "NotificationChannel",
    "TelegramChannel",
    "WebhookChannel",
    "TeamsChannel",
    "JiraChannel",
    "ServiceNowChannel",
    "SMTPChannel",
    "build_channels",
]


def build_channels(config: Dict[str, Any]) -> Dict[str, NotificationChannel]:
    """Builds the standard set of Gjallarhorn channels from a config dict.

    A channel is always instantiated, even if unconfigured: NotificationHub
    checks `is_configured()` before dispatching and simply skips (with a
    log line) any channel that isn't set up, so a missing Telegram token or
    SMTP host never crashes the hub.
    """
    tg_cfg = config.get("telegram", {}) or {}
    webhook_cfg = config.get("webhook", {}) or {}
    smtp_cfg = config.get("smtp", {}) or {}
    teams_cfg = config.get("teams", {}) or {}
    jira_cfg = config.get("jira", {}) or {}
    servicenow_cfg = config.get("servicenow", {}) or {}

    return {
        "telegram": TelegramChannel(
            bot_token=tg_cfg.get("bot_token", ""),
            chat_id=tg_cfg.get("chat_id", ""),
        ),
        "webhook": WebhookChannel(
            url=webhook_cfg.get("url", ""),
        ),
        "teams": TeamsChannel(
            url=teams_cfg.get("url", ""),
        ),
        "jira": JiraChannel(
            base_url=jira_cfg.get("base_url", ""),
            email=jira_cfg.get("email", ""),
            api_token=jira_cfg.get("api_token", ""),
            project_key=jira_cfg.get("project_key", ""),
            issue_type=jira_cfg.get("issue_type", "Bug"),
        ),
        "servicenow": ServiceNowChannel(
            instance=servicenow_cfg.get("instance", ""),
            username=servicenow_cfg.get("username", ""),
            password=servicenow_cfg.get("password", ""),
            table=servicenow_cfg.get("table", "incident"),
        ),
        "email": SMTPChannel(
            host=smtp_cfg.get("host", ""),
            port=int(smtp_cfg.get("port", 587) or 587),
            username=smtp_cfg.get("username", ""),
            password=smtp_cfg.get("password", ""),
            from_addr=smtp_cfg.get("from_addr", ""),
            to_addrs=smtp_cfg.get("to_addrs") or [],
            use_tls=bool(smtp_cfg.get("use_tls", True)),
        ),
    }
