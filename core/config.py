import copy
import os
from typing import Any, Dict

import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "hub": {
        "dedup_window_seconds": 300,
        "default_channels": ["telegram", "webhook", "teams", "email"],
        "db_path": "gjallarhorn.db",
    },
    "telegram": {"bot_token": "", "chat_id": ""},
    "webhook": {"url": ""},
    "teams": {"url": ""},
    "jira": {
        "base_url": "",
        "email": "",
        "api_token": "",
        "project_key": "",
        "issue_type": "Bug",
    },
    "servicenow": {
        "instance": "",
        "username": "",
        "password": "",
        "table": "incident",
    },
    "smtp": {
        "host": "",
        "port": 587,
        "username": "",
        "password": "",
        "from_addr": "",
        "to_addrs": [],
        "use_tls": True,
    },
    "pagerduty": {"routing_key": ""},
    "opsgenie": {"api_key": "", "eu": False},
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Environment variables take precedence over config.yaml, which in turn
    takes precedence over the defaults. Never raises."""
    config = copy.deepcopy(config)

    if os.environ.get("GJALLARHORN_DEDUP_WINDOW_SECONDS"):
        try:
            config["hub"]["dedup_window_seconds"] = int(
                os.environ["GJALLARHORN_DEDUP_WINDOW_SECONDS"]
            )
        except ValueError:
            pass

    if os.environ.get("GJALLARHORN_DEFAULT_CHANNELS"):
        config["hub"]["default_channels"] = [
            c.strip()
            for c in os.environ["GJALLARHORN_DEFAULT_CHANNELS"].split(",")
            if c.strip()
        ]

    if os.environ.get("GJALLARHORN_DB_PATH"):
        config["hub"]["db_path"] = os.environ["GJALLARHORN_DB_PATH"]

    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram"]["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        config["telegram"]["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]

    if os.environ.get("WEBHOOK_URL"):
        config["webhook"]["url"] = os.environ["WEBHOOK_URL"]

    if os.environ.get("TEAMS_WEBHOOK_URL"):
        config["teams"]["url"] = os.environ["TEAMS_WEBHOOK_URL"]

    if os.environ.get("JIRA_BASE_URL"):
        config["jira"]["base_url"] = os.environ["JIRA_BASE_URL"]
    if os.environ.get("JIRA_EMAIL"):
        config["jira"]["email"] = os.environ["JIRA_EMAIL"]
    if os.environ.get("JIRA_API_TOKEN"):
        config["jira"]["api_token"] = os.environ["JIRA_API_TOKEN"]
    if os.environ.get("JIRA_PROJECT_KEY"):
        config["jira"]["project_key"] = os.environ["JIRA_PROJECT_KEY"].strip().upper()
    if os.environ.get("JIRA_ISSUE_TYPE"):
        config["jira"]["issue_type"] = os.environ["JIRA_ISSUE_TYPE"]

    if os.environ.get("SERVICENOW_INSTANCE"):
        config["servicenow"]["instance"] = os.environ["SERVICENOW_INSTANCE"].rstrip("/")
    if os.environ.get("SERVICENOW_USERNAME"):
        config["servicenow"]["username"] = os.environ["SERVICENOW_USERNAME"]
    if os.environ.get("SERVICENOW_PASSWORD"):
        config["servicenow"]["password"] = os.environ["SERVICENOW_PASSWORD"]
    if os.environ.get("SERVICENOW_TABLE"):
        config["servicenow"]["table"] = os.environ["SERVICENOW_TABLE"].strip().lower()

    if os.environ.get("SMTP_HOST"):
        config["smtp"]["host"] = os.environ["SMTP_HOST"]
    if os.environ.get("SMTP_PORT"):
        try:
            config["smtp"]["port"] = int(os.environ["SMTP_PORT"])
        except ValueError:
            pass
    if os.environ.get("SMTP_USERNAME"):
        config["smtp"]["username"] = os.environ["SMTP_USERNAME"]
    if os.environ.get("SMTP_PASSWORD"):
        config["smtp"]["password"] = os.environ["SMTP_PASSWORD"]
    if os.environ.get("SMTP_FROM"):
        config["smtp"]["from_addr"] = os.environ["SMTP_FROM"]
    if os.environ.get("SMTP_TO"):
        config["smtp"]["to_addrs"] = [
            a.strip() for a in os.environ["SMTP_TO"].split(",") if a.strip()
        ]
    if os.environ.get("SMTP_USE_TLS"):
        config["smtp"]["use_tls"] = os.environ["SMTP_USE_TLS"].lower() in (
            "1",
            "true",
            "yes",
        )

    if os.environ.get("PAGERDUTY_ROUTING_KEY"):
        config["pagerduty"]["routing_key"] = os.environ["PAGERDUTY_ROUTING_KEY"]

    if os.environ.get("OPSGENIE_API_KEY"):
        config["opsgenie"]["api_key"] = os.environ["OPSGENIE_API_KEY"]
    if os.environ.get("OPSGENIE_EU"):
        config["opsgenie"]["eu"] = os.environ["OPSGENIE_EU"].lower() in (
            "1",
            "true",
            "yes",
        )

    return config


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Loads config.yaml (if present), merges it over the defaults, then
    applies environment variable overrides on top. Never raises: a missing
    or malformed config.yaml simply falls back to defaults."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError("config.yaml must contain a mapping at the top level")
            config = _deep_merge(config, data)
    except FileNotFoundError:
        print(f"[CONFIG] {path} not found, using defaults + environment variables.")
    except (yaml.YAMLError, ValueError) as e:
        print(f"[CONFIG] Failed to parse {path} ({e}), using defaults + environment variables.")

    return _apply_env_overrides(config)
