from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from max_assist.utils import now


@dataclass
class Bucket:
    tokens: float
    updated: datetime


class RateLimiter:
    def __init__(self, per_second: float, burst: float) -> None:
        self.per_second = per_second
        self.burst = burst
        self.buckets: dict[Any, Bucket] = {}

    def allow(self, key: Any) -> bool:
        moment = now()
        bucket = self.buckets.get(key)
        if bucket is None:
            self.buckets[key] = Bucket(tokens=self.burst - 1, updated=moment)
            return True

        gained = (moment - bucket.updated).total_seconds() * self.per_second
        bucket.tokens = min(self.burst, bucket.tokens + gained)
        bucket.updated = moment
        if bucket.tokens < 1:
            return False

        bucket.tokens -= 1
        return True

    def prune(self, idle: timedelta) -> None:
        border = now() - idle
        self.buckets = {key: bucket for key, bucket in self.buckets.items() if bucket.updated >= border}
