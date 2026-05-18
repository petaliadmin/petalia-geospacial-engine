from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def is_within_hours(dt: datetime, hours: int) -> bool:
    """Return True if dt is within the last `hours` hours from now."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return utcnow() - dt < timedelta(hours=hours)


def format_iso(dt: datetime) -> str:
    return dt.isoformat()


def days_ago(days: int) -> datetime:
    return utcnow() - timedelta(days=days)


def date_range_strings(days: int) -> tuple[str, str]:
    """Return (start_date, end_date) as YYYY-MM-DD strings for GEE queries."""
    end = utcnow()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
