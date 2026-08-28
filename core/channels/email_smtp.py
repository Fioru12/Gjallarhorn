import logging
import smtplib
from email.mime.text import MIMEText
from typing import List

from core.channels.base import NotificationChannel

logger = logging.getLogger("gjallarhorn.channels.email")


class SMTPChannel(NotificationChannel):
    """Sends alert notifications by e-mail over SMTP."""

    name = "email"

    def __init__(
        self,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: List[str] = None,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr or username
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        return bool(self.host and self.from_addr and self.to_addrs)

    def send(self, title: str, message: str, severity: str) -> bool:
        if not self.is_configured():
            logger.info("Email channel not configured, skipping send.")
            return False

        msg = MIMEText(message)
        msg["Subject"] = f"[Gjallarhorn][{severity.upper()}] {title}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            return True
        except (smtplib.SMTPException, OSError) as e:
            logger.warning("Failed to send email notification: %s", e)
            return False
