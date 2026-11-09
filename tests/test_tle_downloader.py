from src.data.tle_downloader import download_tle
from src.orbit.propagation import get_satellite_position


satellite = download_tle(25544)

result = get_satellite_position(
    satellite["name"],
    satellite["line1"],
    satellite["line2"]
)

print("\n🛰️ ORBITGUARD AI — LIVE ORBIT TEST")
print("=" * 50)
print(f"Satellite: {result['name']}")
print(f"X: {result['x_km']:.3f} km")
print(f"Y: {result['y_km']:.3f} km")
print(f"Z: {result['z_km']:.3f} km")
print(f"VX: {result['velocity_x_km_s']:.3f} km/s")
print(f"VY: {result['velocity_y_km_s']:.3f} km/s")
print(f"VZ: {result['velocity_z_km_s']:.3f} km/s")
print(f"Calculated at: {result['calculated_at']}")