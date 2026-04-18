"""Template-facing view helpers."""

from __future__ import annotations

from datetime import datetime


def format_duration(started_at: datetime | None, finished_at: datetime | None) -> str:
    """Format run duration as a short human-readable string."""
    if not started_at or not finished_at:
        return "-"
    seconds = int((finished_at - started_at).total_seconds())
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
