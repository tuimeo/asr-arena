"""
Per-key rate limiting.

Tracks usage by a hash of the key values (never stores plaintext keys).
Two limits:
  - Max calls per key per day (prevents runaway abuse)
  - Max calls per key per minute (prevents burst abuse)
"""

import hashlib
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field

MAX_CALLS_PER_KEY_PER_DAY = int(os.getenv("RATE_LIMIT_DAILY", "200"))
MAX_CALLS_PER_KEY_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))


@dataclass
class _KeyUsage:
    day_key: str = ""           # "2026-04-15"
    day_count: int = 0
    minute_timestamps: list = field(default_factory=list)


class RateLimiter:
    def __init__(
        self,
        max_per_day: int = MAX_CALLS_PER_KEY_PER_DAY,
        max_per_minute: int = MAX_CALLS_PER_KEY_PER_MINUTE,
    ):
        self.max_per_day = max_per_day
        self.max_per_minute = max_per_minute
        self._usage: dict[str, _KeyUsage] = defaultdict(_KeyUsage)

    def _hash_keys(self, keys: dict) -> str:
        """Hash all key values into a single fingerprint."""
        raw = "|".join(
            f"{provider}:{','.join(str(v) for v in sorted(pkeys.values()))}"
            for provider, pkeys in sorted(keys.items())
            if pkeys
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def check(self, keys: dict) -> str | None:
        """
        Check if the request is allowed.
        Returns None if allowed, or an error message string if rejected.
        """
        key_hash = self._hash_keys(keys)
        usage = self._usage[key_hash]
        now = time.time()
        today = time.strftime("%Y-%m-%d")

        # Reset daily counter
        if usage.day_key != today:
            usage.day_key = today
            usage.day_count = 0

        # Check daily limit
        if usage.day_count >= self.max_per_day:
            return f"该密钥今日调用已达上限 ({self.max_per_day} 次)，请明天再试"

        # Clean old timestamps (older than 60s)
        usage.minute_timestamps = [t for t in usage.minute_timestamps if now - t < 60]

        # Check per-minute limit
        if len(usage.minute_timestamps) >= self.max_per_minute:
            return f"请求过于频繁，每分钟最多 {self.max_per_minute} 次，请稍后再试"

        # Record this call
        usage.day_count += 1
        usage.minute_timestamps.append(now)
        return None


# Singleton
rate_limiter = RateLimiter()
