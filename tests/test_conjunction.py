from src.orbit.tle_parser import load_tle_file
from src.orbit.propagation import get_satellite_position
from src.risk.conjunction import find_closest_approach


satellites = load_tle_file(
    "data/satellites.txt"
)

satellite_a = satellites[0]
satellite_b = satellites[1]


result = find_closest_approach(
    get_satellite_position,
    satellite_a,
    satellite_b,
    minutes=60,
    step_seconds=60
)


print("\n🛰️ ORBITGUARD CONJUNCTION ANALYSIS")
print("=" * 50)

print(
    f"Object A: {satellite_a['name']}"
)

print(
    f"Object B: {satellite_b['name']}"
)

print(
    f"\nClosest approach: "
    f"{result['closest_distance_km']:.3f} km"
)

print(
    f"Time of closest approach: "
    f"{result['closest_time']}"
)

print(
    f"Risk classification: "
    f"{result['risk']}"
)