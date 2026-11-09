from src.data.tle_downloader import download_satellites
from src.orbit.propagation import get_satellite_position
from src.risk.conjunction import screen_all_pairs


satellites = download_satellites(
    "data/targets.txt"
)


print("\n🛰️ ORBITGUARD AI — CONJUNCTION SCREENING")
print("=" * 70)


results = screen_all_pairs(
    get_satellite_position,
    satellites,
    minutes=180,
    step_seconds=60
)


print("\n📊 CLOSEST APPROACHES")
print("=" * 70)


for result in results:

    print(
        f"\n{result['satellite_a']} "
        f"↔ "
        f"{result['satellite_b']}"
    )

    print(
        f"Minimum separation: "
        f"{result['closest_distance_km']:.3f} km"
    )

    print(
        f"Relative velocity: "
        f"{result['relative_velocity_km_s']:.3f} km/s"
    )

    print(
        f"Time to TCA: "
        f"{result['time_to_tca_minutes']:.1f} minutes"
    )

    if result["tca_at_boundary"]:
        print("⚠️ TCA: Outside current search window")
    else:
        print("✅ TCA: Within search window")

    print(
        f"Time: "
        f"{result['closest_time']}"
    )

    print(
        f"Risk: "
        f"{result['risk']}"
    )