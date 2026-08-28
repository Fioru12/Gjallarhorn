from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    """Common interface every Gjallarhorn notification channel implements.

    A channel that is not configured (missing token, url, host, ...) must
    never raise: `is_configured()` lets the hub skip it cleanly, and `send()`
    itself must catch its own transport errors and return False rather than
    propagate an exception that would break the other channels' delivery.
    """

    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if this channel has enough configuration to attempt a send."""
        raise NotImplementedError

    @abstractmethod
    def send(self, title: str, message: str, severity: str) -> bool:
        """Sends a notification. Returns True on success, False on any failure.
        Must never raise."""
        raise NotImplementedError
