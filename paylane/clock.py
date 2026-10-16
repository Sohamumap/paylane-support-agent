"""Fixed test clock. Every age check uses it, so the 30-day boundary gives the same answer on every run."""

from datetime import datetime, timezone

FIXED_NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)


def now() -> datetime:
    return FIXED_NOW


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp such as 2026-10-10T09:15:00Z into an aware UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
