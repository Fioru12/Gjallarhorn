import os
import socket
import datetime
from typing import Optional
from core.channels.base import NotificationChannel

SEVERITY_MAP_NUMERIC = {
    "low": 3,
    "medium": 6,
    "high": 8,
    "critical": 10
}

class SiemSyslogChannel(NotificationChannel):
    """
    SIEM Notification Channel that formats security alerts into
    Common Event Format (CEF) and Syslog RFC 5424 messages.
    """

    name = "siem_syslog"

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, format_type: str = "cef"):
        self.host = host or os.environ.get("GJALLARHORN_SIEM_HOST")
        self.port = port or int(os.environ.get("GJALLARHORN_SIEM_PORT", "514"))
        self.format_type = format_type.lower()

    def is_configured(self) -> bool:
        return bool(self.host and self.port)

    def format_cef(self, title: str, message: str, severity: str) -> str:
        sev_num = SEVERITY_MAP_NUMERIC.get(severity.lower(), 5)
        clean_title = title.replace("|", "\\|").replace("\n", " ")
        clean_msg = message.replace("|", "\\|").replace("\n", " ")
        return f"CEF:0|Asgard|Gjallarhorn|1.0.0|SECURITY_ALERT|{clean_title}|{sev_num}|msg={clean_msg}"

    def format_syslog_rfc5424(self, title: str, message: str, severity: str) -> str:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        clean_title = title.replace("\n", " ")
        clean_msg = message.replace("\n", " ")
        return f"<14>1 {timestamp} gjallarhorn.asgard Gjallarhorn - - - [{severity.upper()}] {clean_title}: {clean_msg}"

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            return False

        try:
            if self.format_type == "cef":
                payload = self.format_cef(title, message, severity)
            else:
                payload = self.format_syslog_rfc5424(title, message, severity)

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(payload.encode("utf-8"), (self.host, self.port))
            sock.close()
            return True
        except Exception:
            return False
