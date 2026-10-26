"""In-memory sliding-window login throttle (per process).

Failures are counted per (email, ip) and per ip. Reaching the limit locks that key for ``lockout_seconds``; a successful
login clears the (email, ip) key. Kept in memory on purpose: it is a brake on password guessing / email enumeration, not
an audit log, and the deployment runs a single backend process.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class LoginThrottle:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fails: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}

    def _keys(self, email: str, ip: str) -> list[tuple[str, int]]:
        return [(f"e:{email}|{ip}", 1), (f"i:{ip}", 4)]  # (key, limit multiplier)

    def retry_after(self, email: str, ip: str, *, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self._lock:
            waits = [self._locked_until.get(k, 0.0) - now for k, _ in self._keys(email, ip)]
        wait = max(waits)
        return int(wait) + 1 if wait > 0 else 0

    def failure(self, email: str, ip: str, *, limit: int, lockout: int, now: float | None = None) -> int | None:
        """Record a failed attempt. -> attempts left for the (email, ip) key (None once locked)."""
        now = time.time() if now is None else now
        left: int | None = None
        with self._lock:
            for key, mult in self._keys(email, ip):
                q = self._fails.setdefault(key, deque())
                while q and q[0] < now - lockout:
                    q.popleft()
                q.append(now)
                if len(q) >= limit * mult:
                    self._locked_until[key] = now + lockout
                    q.clear()
                    left = None if key.startswith("e:") else left
                elif key.startswith("e:"):
                    left = limit - len(q)
        return left

    def success(self, email: str, ip: str) -> None:
        with self._lock:
            self._fails.pop(f"e:{email}|{ip}", None)
            self._locked_until.pop(f"e:{email}|{ip}", None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()
            self._locked_until.clear()


login_throttle = LoginThrottle()
