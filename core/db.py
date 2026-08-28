import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_ISO = "%Y-%m-%dT%H:%M:%S.%f"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.strftime(_ISO)


def _from_iso(s: str) -> datetime:
    dt = datetime.strptime(s, _ISO)
    return dt.replace(tzinfo=timezone.utc)


class NotificationDB:
    """SQLite-backed persistence for the notification audit trail.

    One row per distinct (source, title) pair: repeated notifications for
    the same incident update that row rather than accumulating duplicates,
    which is what lets the dedup window in NotificationHub work across
    process restarts and lets `suppressed_count` act as a running tally.
    """

    def __init__(self, db_path: str = "gjallarhorn.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    channels_sent TEXT NOT NULL DEFAULT '[]',
                    last_sent_at TEXT,
                    last_seen_at TEXT NOT NULL,
                    suppressed_count INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(source, title)
                )
                """
            )
            self._conn.commit()

    def get_last_sent_at(self, source: str, title: str) -> Optional[datetime]:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_sent_at FROM notification_log WHERE source = ? AND title = ?",
                (source, title),
            ).fetchone()
        if row and row["last_sent_at"]:
            return _from_iso(row["last_sent_at"])
        return None

    def record_sent(
        self,
        source: str,
        title: str,
        severity: str,
        message: str,
        channels_sent: List[str],
        when: Optional[datetime] = None,
    ) -> None:
        now = _to_iso(when or _utcnow())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO notification_log
                    (source, title, severity, message, channels_sent, last_sent_at, last_seen_at, suppressed_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(source, title) DO UPDATE SET
                    severity=excluded.severity,
                    message=excluded.message,
                    channels_sent=excluded.channels_sent,
                    last_sent_at=excluded.last_sent_at,
                    last_seen_at=excluded.last_seen_at
                """,
                (source, title, severity, message, json.dumps(channels_sent), now, now),
            )
            self._conn.commit()

    def record_suppressed(
        self,
        source: str,
        title: str,
        severity: str,
        message: str,
        when: Optional[datetime] = None,
    ) -> int:
        """Records a suppressed (deduplicated) occurrence and returns the new
        suppressed_count for this (source, title) pair."""
        now = _to_iso(when or _utcnow())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO notification_log
                    (source, title, severity, message, channels_sent, last_sent_at, last_seen_at, suppressed_count)
                VALUES (?, ?, ?, ?, '[]', NULL, ?, 1)
                ON CONFLICT(source, title) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    suppressed_count = suppressed_count + 1
                """,
                (source, title, severity, message, now),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT suppressed_count FROM notification_log WHERE source = ? AND title = ?",
                (source, title),
            ).fetchone()
        return int(row["suppressed_count"]) if row else 0

    def get_history(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) AS c FROM notification_log"
            ).fetchone()["c"]
            rows = self._conn.execute(
                """
                SELECT id, source, title, severity, message, channels_sent,
                       last_sent_at, last_seen_at, suppressed_count
                FROM notification_log
                ORDER BY last_seen_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        items = []
        for row in rows:
            item = dict(row)
            item["channels_sent"] = json.loads(item["channels_sent"] or "[]")
            items.append(item)

        return {"total": total, "limit": limit, "offset": offset, "items": items}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
