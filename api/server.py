import os
import secrets
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from core.channels import build_channels
from core.config import load_config
from core.db import NotificationDB
from core.hub import NotificationHub

app = FastAPI(
    title="Gjallarhorn Alerting Hub API",
    description="Centralized alerting hub for the Asgard Cybersecurity Suite",
    version="1.0.0",
)

config = load_config(os.environ.get("GJALLARHORN_CONFIG", "config.yaml"))

API_KEY = os.environ.get("GJALLARHORN_API_KEY")
if not API_KEY:
    API_KEY = secrets.token_urlsafe(24)
    print("[SECURITY WARNING] GJALLARHORN_API_KEY not set. Generated a random key for this run:")
    print(f"    {API_KEY}")
    print("    Set GJALLARHORN_API_KEY in your environment to use a stable key across restarts.")

db = NotificationDB(db_path=config["hub"]["db_path"])
channels = build_channels(config)
hub = NotificationHub(
    channels=channels,
    db=db,
    dedup_window_seconds=config["hub"]["dedup_window_seconds"],
    default_channels=config["hub"]["default_channels"],
)


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


class NotifyRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=200)
    severity: Literal["low", "medium", "high", "critical"]
    title: str = Field(..., min_length=1, max_length=300)
    message: str = Field(..., min_length=1, max_length=8192)
    channels: Optional[List[str]] = None


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Gjallarhorn Alerting Hub",
        "version": "1.0.0",
        "endpoints": ["/api/v1/notify", "/api/v1/notify/alertmanager", "/api/v1/history"],
    }


_SEVERITY_MAP = {
    "critical": "critical",
    "emergency": "critical",
    "high": "high",
    "warning": "medium",
    "warn": "medium",
    "info": "low",
    "none": "low",
}


class AlertmanagerWebhook(BaseModel):
    """Payload standard di Alertmanager (docs: prometheus-alertmanager/notifications)."""

    status: str = "firing"
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


@app.post("/api/v1/notify/alertmanager", dependencies=[Depends(require_api_key)])
def notify_alertmanager(payload: AlertmanagerWebhook) -> Dict[str, Any]:
    """Riceve webhook POST da Alertmanager e lo traduce nel canale Gjallarhorn."""
    accepted = 0
    results: List[Dict[str, Any]] = []
    if not payload.alerts:
        raise HTTPException(status_code=400, detail="No alerts to forward")
    for alert in payload.alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        severity = _SEVERITY_MAP.get(str(labels.get("severity", "warning")).lower(), "medium")
        title = (
            annotations.get("summary")
            or labels.get("alertname")
            or "Asgard alert"
        )
        message = annotations.get("description") or annotations.get("message") or ""
        try:
            results.append(
                hub.notify(
                    source="alertmanager",
                    severity=severity,
                    title=str(title),
                    message=str(message)[:8192],
                )
            )
            accepted += 1
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "forwarded": accepted, "results": results}


@app.post("/api/v1/notify", dependencies=[Depends(require_api_key)])
def notify(payload: NotifyRequest) -> Dict[str, Any]:
    try:
        result = hub.notify(
            source=payload.source,
            severity=payload.severity,
            title=payload.title,
            message=payload.message,
            channels=payload.channels,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.get("/api/v1/history", dependencies=[Depends(require_api_key)])
def history(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    return hub.get_history(limit=limit, offset=offset)


@app.get("/metrics")
def prometheus_metrics():
    from fastapi.responses import PlainTextResponse
    # get_history() returns {"total": <real COUNT(*)>, "items": <page>, ...}.
    # The previous version read stats["history"] (a key that never existed
    # in that dict) and reported 0 unconditionally; fixed to use the real
    # total instead of a page slice capped at `limit`.
    stats = db.get_history(limit=1)
    total_alerts = stats.get("total", 0)

    # len(channels) is always 6 - build_channels() always instantiates every
    # channel type regardless of configuration (see core/channels/__init__.py),
    # so that would always report "6 configured" even on a fresh install with
    # nothing set up. Count only channels that are actually usable.
    configured_channels = sum(1 for c in channels.values() if c.is_configured())

    metrics_text = f"""# HELP gjallarhorn_alerts_total Total notifications recorded in Gjallarhorn
# TYPE gjallarhorn_alerts_total counter
gjallarhorn_alerts_total {total_alerts}

# HELP gjallarhorn_configured_channels_total Number of notification channels with valid configuration
# TYPE gjallarhorn_configured_channels_total gauge
gjallarhorn_configured_channels_total {configured_channels}
"""
    return PlainTextResponse(content=metrics_text)

