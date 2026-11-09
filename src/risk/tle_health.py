"""Data quality and system-health helpers for OrbitGuard AI.

These checks describe the age of the TLE epoch and the success of local
propagation. They are quality indicators, not estimates of orbital accuracy.
"""

from datetime import datetime, timezone


def parse_tle_epoch(line1):
    """Parse the TLE epoch field from line 1 into a timezone-aware UTC datetime."""
    if not line1 or len(line1) < 32:
        return None

    try:
        epoch_year = int(line1[18:20])
        epoch_day = float(line1[20:32])

        year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year

        return datetime(year, 1, 1, tzinfo=timezone.utc) + __import__("datetime").timedelta(
            days=epoch_day - 1.0
        )
    except (TypeError, ValueError, OverflowError):
        return None


def tle_age_hours(satellite, reference_time=None):
    """Return age of the TLE epoch in hours."""
    epoch = parse_tle_epoch(satellite.get("line1", ""))

    if epoch is None:
        return None

    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    return (reference_time - epoch).total_seconds() / 3600.0


def tle_quality_status(age_hours):
    """Classify TLE age for display only."""
    if age_hours is None:
        return "UNKNOWN"

    if age_hours < 24:
        return "FRESH"

    if age_hours < 72:
        return "RECENT"

    if age_hours < 168:
        return "AGING"

    return "OLD"


def build_satellite_health(satellite, propagation_ok, reference_time=None):
    """Build a transparent per-satellite data-quality record."""
    age_hours = tle_age_hours(satellite, reference_time)
    epoch = parse_tle_epoch(satellite.get("line1", ""))

    return {
        "satellite": satellite.get("name", "Unknown"),
        "norad_id": satellite.get("norad_id", "Unknown"),
        "tle_epoch": epoch,
        "tle_age_hours": age_hours,
        "tle_status": tle_quality_status(age_hours),
        "propagation_status": "OK" if propagation_ok else "FAILED",
    }
