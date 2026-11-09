from datetime import datetime, timezone
from pathlib import Path
import math

from src.data.tle_downloader import _load_cache
from src.orbit.propagation import get_satellite_position


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_sgp4_returns_finite_position_and_velocity():
    satellites = _load_cache(str(PROJECT_ROOT / "data" / "tle_cache.txt"))
    satellite = satellites[25544]

    position = get_satellite_position(
        satellite["name"],
        satellite["line1"],
        satellite["line2"],
        datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc),
    )

    for key in (
        "x_km", "y_km", "z_km",
        "velocity_x_km_s", "velocity_y_km_s", "velocity_z_km_s",
    ):
        assert math.isfinite(position[key])
