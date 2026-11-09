from src.data.tle_downloader import download_satellites
from src.orbit.propagation import get_satellite_position


satellites = download_satellites("data/targets.txt")


print("\n🛰️ ORBITGUARD AI — MULTI-SATELLITE PROPAGATION")
print("=" * 65)


for satellite in satellites:

    result = get_satellite_position(
        satellite["name"],
        satellite["line1"],
        satellite["line2"]
    )

    print(f"\nSatellite: {result['name']}")
    print(
        f"Position: "
        f"({result['x_km']:.2f}, "
        f"{result['y_km']:.2f}, "
        f"{result['z_km']:.2f}) km"
    )

    print(
        f"Velocity: "
        f"({result['velocity_x_km_s']:.2f}, "
        f"{result['velocity_y_km_s']:.2f}, "
        f"{result['velocity_z_km_s']:.2f}) km/s"
    )