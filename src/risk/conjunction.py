from itertools import combinations
import math
from datetime import datetime, timezone, timedelta

from src.orbit.propagation import get_satellite_position
from src.risk.mission_priority import indian_asset_involvement


# ============================================================
# RISK THRESHOLDS
# ============================================================

CRITICAL_DISTANCE_KM = 1.0
ELEVATED_DISTANCE_KM = 5.0
WATCH_DISTANCE_KM = 25.0


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def calculate_distance(position_a, position_b):
    """
    Calculate 3D Euclidean distance between two satellites.

    Input:
        position_a = dictionary containing x_km, y_km, z_km
        position_b = dictionary containing x_km, y_km, z_km

    Returns:
        Distance in kilometers.
    """

    dx = position_a["x_km"] - position_b["x_km"]
    dy = position_a["y_km"] - position_b["y_km"]
    dz = position_a["z_km"] - position_b["z_km"]

    return math.sqrt(
        dx**2 +
        dy**2 +
        dz**2
    )


# ============================================================
# RELATIVE VELOCITY
# ============================================================

def calculate_relative_velocity(position_a, position_b):
    """
    Calculate relative velocity magnitude between two satellites.

    Returns:
        Relative velocity in km/s.
    """

    dvx = (
        position_a["velocity_x_km_s"]
        - position_b["velocity_x_km_s"]
    )

    dvy = (
        position_a["velocity_y_km_s"]
        - position_b["velocity_y_km_s"]
    )

    dvz = (
        position_a["velocity_z_km_s"]
        - position_b["velocity_z_km_s"]
    )

    return math.sqrt(
        dvx**2 +
        dvy**2 +
        dvz**2
    )


# ============================================================
# RISK CLASSIFICATION
# ============================================================

def classify_risk(distance_km):
    """
    Classify geometric separation.

    IMPORTANT:
    This is a screening classification only.
    It is NOT probability of collision.
    """

    if distance_km < CRITICAL_DISTANCE_KM:

        return "CRITICAL"

    elif distance_km < ELEVATED_DISTANCE_KM:

        return "ELEVATED"

    elif distance_km < WATCH_DISTANCE_KM:

        return "WATCH"

    else:

        return "NOMINAL"


# ============================================================
# CLOSEST APPROACH
# ============================================================

def find_closest_approach(
    satellite_a,
    satellite_b,
    start_time,
    minutes=180,
    step_seconds=60
):
    """
    Search for the closest sampled approach between two satellites.

    Parameters
    ----------
    satellite_a : dict
        Satellite TLE dictionary.

    satellite_b : dict
        Satellite TLE dictionary.

    start_time : datetime
        Start of the screening window.

    minutes : int
        Screening duration in minutes.

    step_seconds : int
        Propagation interval in seconds.

    Returns
    -------
    dict
        Closest-approach screening result.
    """

    # --------------------------------------------------------
    # Ensure timezone-aware UTC time
    # --------------------------------------------------------

    if start_time.tzinfo is None:

        start_time = start_time.replace(
            tzinfo=timezone.utc
        )

    else:

        start_time = start_time.astimezone(
            timezone.utc
        )


    # --------------------------------------------------------
    # Search window
    # --------------------------------------------------------

    search_window_end = (
        start_time +
        timedelta(minutes=minutes)
    )


    # --------------------------------------------------------
    # Initialize closest approach
    # --------------------------------------------------------

    closest_distance = float("inf")

    closest_time = start_time

    closest_relative_velocity = 0.0


    # --------------------------------------------------------
    # Generate time samples
    # --------------------------------------------------------

    current_time = start_time

    while current_time <= search_window_end:

        position_a = get_satellite_position(
            satellite_a["name"],
            satellite_a["line1"],
            satellite_a["line2"],
            current_time
        )

        position_b = get_satellite_position(
            satellite_b["name"],
            satellite_b["line1"],
            satellite_b["line2"],
            current_time
        )


        # ----------------------------------------------------
        # Distance
        # ----------------------------------------------------

        distance = calculate_distance(
            position_a,
            position_b
        )


        # ----------------------------------------------------
        # Relative velocity
        # ----------------------------------------------------

        relative_velocity = calculate_relative_velocity(
            position_a,
            position_b
        )


        # ----------------------------------------------------
        # Update closest approach
        # ----------------------------------------------------

        if distance < closest_distance:

            closest_distance = distance

            closest_time = current_time

            closest_relative_velocity = (
                relative_velocity
            )


        # ----------------------------------------------------
        # Move to next sample
        # ----------------------------------------------------

        current_time += timedelta(
            seconds=step_seconds
        )


    # --------------------------------------------------------
    # Time to closest approach
    # --------------------------------------------------------

    time_to_tca = (
        closest_time - start_time
    )

    time_to_tca_minutes = (
        time_to_tca.total_seconds() / 60.0
    )


    # --------------------------------------------------------
    # Boundary detection
    # --------------------------------------------------------

    tca_at_boundary = (
        closest_time >= search_window_end
    )


    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    risk_level = classify_risk(
        closest_distance
    )


    # --------------------------------------------------------
    # Base geometric result
    # --------------------------------------------------------

    result = {

        "satellite_a":
            satellite_a["name"],

        "satellite_b":
            satellite_b["name"],

        "minimum_distance_km":
            closest_distance,

        "relative_velocity_km_s":
            closest_relative_velocity,

        "time_to_tca_minutes":
            time_to_tca_minutes,

        "tca_time":
            closest_time,

        "tca_at_boundary":
            tca_at_boundary,

        "risk_level":
            risk_level
    }


    return result


# ============================================================
# SCREEN ALL SATELLITE PAIRS
# ============================================================

def screen_all_pairs(
    satellites,
    start_time=None,
    minutes=180,
    step_seconds=60
):
    """
    Screen every unique satellite pair.

    Example with 4 satellites:

        4 satellites
        ↓
        4 × 3 / 2
        ↓
        6 unique pairs

    Returns:
        List of conjunction screening results sorted
        by minimum separation distance.

    Mission-context fields are added separately from
    the geometric screening calculation.
    """

    # --------------------------------------------------------
    # Default start time
    # --------------------------------------------------------

    if start_time is None:

        start_time = datetime.now(
            timezone.utc
        )


    # --------------------------------------------------------
    # Normalize timezone
    # --------------------------------------------------------

    if start_time.tzinfo is None:

        start_time = start_time.replace(
            tzinfo=timezone.utc
        )

    else:

        start_time = start_time.astimezone(
            timezone.utc
        )


    # --------------------------------------------------------
    # Generate unique pairs
    # --------------------------------------------------------

    satellite_pairs = combinations(
        satellites,
        2
    )


    results = []


    # --------------------------------------------------------
    # Analyze every pair
    # --------------------------------------------------------

    for satellite_a, satellite_b in satellite_pairs:

        result = find_closest_approach(
            satellite_a=satellite_a,
            satellite_b=satellite_b,
            start_time=start_time,
            minutes=minutes,
            step_seconds=step_seconds
        )


        # ----------------------------------------------------
        # Add mission / Indian-asset context
        # ----------------------------------------------------

        mission_context = indian_asset_involvement(
            result,
            satellites
        )

        result.update(
            {
                "indian_asset_involved":
                    mission_context["indian_asset_involved"],

                "mission_category":
                    mission_context["mission_category"],

                "protection_watch":
                    mission_context["protection_watch"],

                "mission_context_explanation":
                    mission_context["explanation"]
            }
        )


        results.append(result)


    # --------------------------------------------------------
    # Sort by closest separation
    # --------------------------------------------------------

    results.sort(
        key=lambda result:
        result["minimum_distance_km"]
    )


    return results


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    from src.data.tle_downloader import download_satellites

    satellites = download_satellites(
        targets_path="data/targets.txt"
    )

    results = screen_all_pairs(
        satellites,
        start_time=datetime.now(timezone.utc),
        minutes=180,
        step_seconds=60
    )


    print()
    print("=" * 75)
    print("ORBITGUARD AI — CONJUNCTION SCREENING")
    print("=" * 75)


    for result in results:

        boundary = (
            "BOUNDARY"
            if result["tca_at_boundary"]
            else "INTERIOR"
        )

        print()

        print(
            f"{result['satellite_a']} "
            f"↔ "
            f"{result['satellite_b']}"
        )

        print(
            f"  Minimum separation : "
            f"{result['minimum_distance_km']:,.3f} km"
        )

        print(
            f"  Relative velocity  : "
            f"{result['relative_velocity_km_s']:.3f} km/s"
        )

        print(
            f"  Time to TCA        : "
            f"{result['time_to_tca_minutes']:.1f} min"
        )

        print(
            f"  TCA status         : "
            f"{boundary}"
        )

        print(
            f"  Risk               : "
            f"{result['risk_level']}"
        )

        print(
            f"  Indian Asset       : "
            f"{'YES' if result['indian_asset_involved'] else 'NO'}"
        )

        print(
            f"  Mission Category   : "
            f"{result['mission_category']}"
        )

        print(
            f"  Protection Watch   : "
            f"{result['protection_watch']}"
        )

    print()
    print("=" * 75)
    print("Screening complete.")
    print("=" * 75)