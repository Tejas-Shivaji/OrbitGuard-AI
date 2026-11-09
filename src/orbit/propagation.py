from sgp4.api import Satrec
from datetime import datetime, timezone
from functools import lru_cache


def datetime_to_julian_date(dt):
    """Convert a Python datetime to Julian Date."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    unix_time = dt.timestamp()

    return 2440587.5 + unix_time / 86400.0


@lru_cache(maxsize=512)
def _satrec_from_tle(line1, line2):
    """Parse each unique TLE once and reuse its SGP4 record."""
    return Satrec.twoline2rv(line1, line2)


def get_satellite_position(
    name,
    line1,
    line2,
    calculation_time=None
):
    """Calculate satellite position and velocity using SGP4."""

    satellite = _satrec_from_tle(line1, line2)

    if calculation_time is None:
        calculation_time = datetime.now(timezone.utc)
    elif calculation_time.tzinfo is None:
        calculation_time = calculation_time.replace(tzinfo=timezone.utc)
    else:
        calculation_time = calculation_time.astimezone(timezone.utc)

    julian_date = datetime_to_julian_date(calculation_time)

    jd_integer = int(julian_date)
    jd_fraction = julian_date - jd_integer

    error, position, velocity = satellite.sgp4(
        jd_integer,
        jd_fraction
    )

    if error != 0:
        raise RuntimeError(
            f"SGP4 calculation failed with error code: {error}"
        )

    x, y, z = position
    vx, vy, vz = velocity

    return {
        "name": name,
        "x_km": x,
        "y_km": y,
        "z_km": z,
        "velocity_x_km_s": vx,
        "velocity_y_km_s": vy,
        "velocity_z_km_s": vz,
        "calculated_at": calculation_time.isoformat()
    }