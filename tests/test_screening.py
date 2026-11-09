from datetime import datetime, timezone

import src.risk.conjunction as conjunction


def test_screen_all_pairs_returns_each_unique_pair(monkeypatch):
    start = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    satellites = [
        {"name": "TEST-A", "norad_id": 1, "line1": "1 A", "line2": "2 A"},
        {"name": "TEST-B", "norad_id": 2, "line1": "1 B", "line2": "2 B"},
        {"name": "TEST-C", "norad_id": 3, "line1": "1 C", "line2": "2 C"},
    ]

    def fake_position(name, line1, line2, calculation_time):
        index = ord(name[-1]) - ord("A")
        return {
            "name": name,
            "x_km": float(index * 100),
            "y_km": 0.0,
            "z_km": 0.0,
            "velocity_x_km_s": 1.0,
            "velocity_y_km_s": 0.0,
            "velocity_z_km_s": 0.0,
        }

    monkeypatch.setattr(conjunction, "get_satellite_position", fake_position)

    results = conjunction.screen_all_pairs(
        satellites,
        start_time=start,
        minutes=0,
        step_seconds=60,
    )

    assert len(results) == 3
    assert {
        frozenset((result["satellite_a"], result["satellite_b"]))
        for result in results
    } == {
        frozenset(("TEST-A", "TEST-B")),
        frozenset(("TEST-A", "TEST-C")),
        frozenset(("TEST-B", "TEST-C")),
    }
    assert all("indian_asset_involved" in result for result in results)
