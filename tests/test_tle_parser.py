from src.orbit.tle_parser import load_tle_file


satellites = load_tle_file("data/satellites.txt")

print("\n🛰️ TLE LOADER TEST")
print("=" * 40)

for satellite in satellites:
    print(f"Satellite: {satellite['name']}")
    print(f"TLE 1: {satellite['line1']}")
    print(f"TLE 2: {satellite['line2']}")