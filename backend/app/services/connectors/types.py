"""Common connector types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ConnectorHealth:
    name: str
    ok: bool
    latency_ms: float = 0.0
    detail: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "latency_ms": round(float(self.latency_ms or 0.0), 2),
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

