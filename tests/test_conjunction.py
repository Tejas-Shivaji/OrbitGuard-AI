from datetime import datetime, timezone

import src.risk.conjunction as conjunction


def test_find_closest_approach_uses_sampled_minimum(monkeypatch):
    start = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    satellite_a = {"name": "TEST-A", "line1": "1 A", "line2": "2 A"}
    satellite_b = {"name": "TEST-B", "line1": "1 B", "line2": "2 B"}

    def fake_position(name, line1, line2, calculation_time):
        seconds = (calculation_time - start).total_seconds()
        x = 0.0 if name == "TEST-A" else 10.0 - (seconds / 6.0)
        return {
            "name": name,
            "x_km": x,
            "y_km": 0.0,
            "z_km": 0.0,
            "velocity_x_km_s": 0.0 if name == "TEST-A" else -1.0 / 6.0,
            "velocity_y_km_s": 0.0,
            "velocity_z_km_s": 0.0,
        }

    monkeypatch.setattr(conjunction, "get_satellite_position", fake_position)

    result = conjunction.find_closest_approach(
        satellite_a,
        satellite_b,
        start_time=start,
        minutes=2,
        step_seconds=60,
    )

    assert result["minimum_distance_km"] == 0.0
    assert result["time_to_tca_minutes"] == 1.0
    assert result["risk_level"] == "CRITICAL"
    assert result["tca_time"] == start.replace(minute=1)
