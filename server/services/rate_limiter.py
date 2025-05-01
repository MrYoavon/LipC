"""
Simple sliding-window / token-bucket hybrid rate limiter.

Provides methods to allow or block actions based on message rate, and
supports temporary bans when limits are exceeded.

Usage:
    limiter = RateLimiter()
    if limiter.allow(key):
        # process message
    else:
        # reject or close connection
    limiter.forget(key)  # clear state, e.g., on disconnect
"""
import time
from collections import deque, defaultdict
from typing import Deque, Dict

# -------- TUNE THESE CONSTANTS --------
WINDOW_SECONDS: int = 5        # length of the sliding window in seconds
MAX_MSG_PER_WIN: int = 60      # max messages allowed within the window
BAN_SECONDS: int = 30          # ban duration in seconds once limit exceeded
# --------------------------------------


class _Window:
    """
    Internal helper class to track timestamps of events within a sliding window.

    Attributes:
        hits (Deque[float]): Timestamps of recorded events.
    """
    __slots__ = ("hits",)

    def __init__(self) -> None:
        """
        Initialize an empty sliding-window buffer.

        Returns:
            None
        """
        self.hits: Deque[float] = deque()


class RateLimiter:
    """
    Hybrid rate limiter implementing sliding-window and token-bucket semantics.

    Provides methods to check if an action (e.g., message) is allowed based on
    recent frequency, ban keys temporarily when limits are exceeded, and clear
    per-key state.
    """

    def __init__(self) -> None:
        """
        Initialize the rate limiter.

        Sets up storage for per-key sliding windows and ban deadlines.

        Returns:
            None
        """
        self._wins: Dict[str, _Window] = defaultdict(_Window)
        self._banned_until: Dict[str, float] = {}

    def allow(self, key: str) -> bool:
        """
        Determine whether an action for `key` should be allowed.

        Args:
            key (str): Identifier for the client or resource being rate-limited.

        Returns:
            bool: True if action is allowed; False if rate limit exceeded or currently banned.
        """
        now = time.time()

        # Check existing ban
        ban_deadline = self._banned_until.get(key)
        if ban_deadline and now < ban_deadline:
            return False
        if ban_deadline:
            # Ban expired
            del self._banned_until[key]

        # Record the current event timestamp
        win = self._wins[key].hits
        win.append(now)

        # Remove timestamps outside the sliding window
        while win and now - win[0] > WINDOW_SECONDS:
            win.popleft()

        # Enforce maximum messages per window
        if len(win) > MAX_MSG_PER_WIN:
            # Temporarily ban the key
            self._banned_until[key] = now + BAN_SECONDS
            win.clear()  # Reset window
            return False
        return True

    def is_banned(self, key: str) -> bool:
        """
        Check whether `key` is currently under a temporary ban.

        Args:
            key (str): Identifier for the client or resource.

        Returns:
            bool: True if `key` is banned; False otherwise.
        """
        return self._banned_until.get(key, 0) > time.time()

    def forget(self, key: str) -> None:
        """
        Clear all rate-limiting state for `key`.

        Useful for cleaning up after a client disconnects.

        Args:
            key (str): Identifier for the client or resource.

        Returns:
            None
        """
        self._wins.pop(key, None)
