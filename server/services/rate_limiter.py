"""
Simple sliding-window / token-bucket hybrid rate limiter.

•   allow()        -> True  (message may be processed)
                    -> False (message should be rejected / connection closed)
•   forget()       -> Remove all accounting for a key (call on disconnect)
"""
import time
from collections import deque, defaultdict
from typing import Deque, Dict

# -------- TUNE THESE CONSTANTS --------
WINDOW_SECONDS = 5          # length of the sliding window
MAX_MSG_PER_WIN = 5         # how many messages are allowed in that window
BAN_SECONDS = 30         # temporary ban once limit is exceeded
# --------------------------------------


class _Window:
    __slots__ = ("hits",)        # deque[float]

    def __init__(self) -> None:
        self.hits: Deque[float] = deque()


class RateLimiter:
    def __init__(self) -> None:
        self._wins: Dict[str, _Window] = defaultdict(_Window)
        self._banned_until: Dict[str, float] = {}

    def allow(self, key: str) -> bool:
        """Return False if the key should be blocked right now."""
        now = time.time()

        # Currently banned?
        ban_deadline = self._banned_until.get(key)
        if ban_deadline and now < ban_deadline:
            return False
        if ban_deadline:
            # ban expired ­– clean up
            del self._banned_until[key]

        win = self._wins[key].hits
        win.append(now)

        # drop hits that are outside the window
        while win and now - win[0] > WINDOW_SECONDS:
            win.popleft()

        if len(win) > MAX_MSG_PER_WIN:
            self._banned_until[key] = now + BAN_SECONDS
            win.clear()                      # optional: free memory
            return False
        return True

    def is_banned(self, key: str) -> bool:
        return self._banned_until.get(key, 0) > time.time()

    def forget(self, key: str) -> None:
        self._wins.pop(key, None)
