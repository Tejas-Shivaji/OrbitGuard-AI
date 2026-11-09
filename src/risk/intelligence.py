"""
OrbitGuard AI — Mission Intelligence Engine

Converts geometric conjunction-screening results into a
transparent, explainable screening assessment.

IMPORTANT:
This is NOT a probability-of-collision model.
The score is an explainable screening aid only.
"""

from math import isfinite

from src.risk.conjunction import (
    CRITICAL_DISTANCE_KM,
    ELEVATED_DISTANCE_KM,
    WATCH_DISTANCE_KM,
)


def clamp(value, minimum=0.0, maximum=100.0):
    """Keep a numeric value inside a defined range."""
    return max(minimum, min(maximum, value))


def distance_score(distance_km):
    """
    Convert minimum separation into a 0–100 screening contribution.

    Smaller separation produces a higher score.
    The thresholds come directly from conjunction.py.
    """

    if distance_km < CRITICAL_DISTANCE_KM:
        return 100.0

    if distance_km < ELEVATED_DISTANCE_KM:
        return (
            70.0
            + 30.0
            * (
                ELEVATED_DISTANCE_KM - distance_km
            )
            / (
                ELEVATED_DISTANCE_KM
                - CRITICAL_DISTANCE_KM
            )
        )

    if distance_km < WATCH_DISTANCE_KM:
        return (
            35.0
            + 35.0
            * (
                WATCH_DISTANCE_KM - distance_km
            )
            / (
                WATCH_DISTANCE_KM
                - ELEVATED_DISTANCE_KM
            )
        )

    return 0.0


def velocity_score(relative_velocity_km_s):
    """
    Provide a descriptive velocity contribution.

    This does NOT mean high relative velocity independently
    implies collision risk. It is only a transparent screening
    factor used alongside separation.
    """

    if relative_velocity_km_s <= 0:
        return 0.0

    if relative_velocity_km_s < 1.0:
        return 20.0

    if relative_velocity_km_s < 5.0:
        return 40.0

    if relative_velocity_km_s < 10.0:
        return 65.0

    return 80.0


def tca_urgency_score(time_to_tca_minutes):
    """
    Score how soon the predicted closest approach occurs.

    Smaller time-to-TCA produces a higher urgency contribution.
    """

    if time_to_tca_minutes < 0:
        return 0.0

    if time_to_tca_minutes <= 30:
        return 100.0

    if time_to_tca_minutes <= 60:
        return 80.0

    if time_to_tca_minutes <= 120:
        return 60.0

    if time_to_tca_minutes <= 240:
        return 40.0

    return 15.0


def calculate_screening_score(result):
    """
    Calculate a transparent screening score from 0–100.

    Weighted factors:
        60% minimum separation
        20% relative velocity
        20% time-to-TCA urgency

    This score is NOT probability of collision.
    """

    distance = float(result["minimum_distance_km"])
    velocity = float(result["relative_velocity_km_s"])
    time_to_tca = float(result["time_to_tca_minutes"])

    if not all(
        isfinite(value)
        for value in [distance, velocity, time_to_tca]
    ):
        raise ValueError(
            "Conjunction result contains a non-finite value."
        )

    separation_component = distance_score(distance)
    velocity_component = velocity_score(velocity)
    urgency_component = tca_urgency_score(time_to_tca)

    score = (
        separation_component * 0.60
        + velocity_component * 0.20
        + urgency_component * 0.20
    )

    return round(clamp(score), 2)


def get_score_band(score):
    """Return a descriptive screening band."""

    if score >= 75:
        return "HIGH ATTENTION"

    if score >= 50:
        return "ELEVATED ATTENTION"

    if score >= 25:
        return "MONITOR"

    return "LOW ATTENTION"


def generate_explanation(result):
    """
    Generate human-readable reasons from the screening result.
    """

    distance = result["minimum_distance_km"]
    velocity = result["relative_velocity_km_s"]
    time_to_tca = result["time_to_tca_minutes"]
    risk_level = result["risk_level"]

    score = calculate_screening_score(result)
    band = get_score_band(score)

    reasons = []

    if distance < CRITICAL_DISTANCE_KM:
        reasons.append(
            f"Minimum separation ({distance:.3f} km) "
            f"is below the critical threshold "
            f"of {CRITICAL_DISTANCE_KM:g} km."
        )

    elif distance < ELEVATED_DISTANCE_KM:
        reasons.append(
            f"Minimum separation ({distance:.3f} km) "
            f"is below the elevated threshold "
            f"of {ELEVATED_DISTANCE_KM:g} km."
        )

    elif distance < WATCH_DISTANCE_KM:
        reasons.append(
            f"Minimum separation ({distance:.3f} km) "
            f"is inside the watch threshold "
            f"of {WATCH_DISTANCE_KM:g} km."
        )

    else:
        reasons.append(
            f"Minimum separation ({distance:,.3f} km) "
            f"is outside the current geometric "
            f"screening thresholds."
        )

    if time_to_tca <= 60:
        reasons.append(
            f"TCA occurs relatively soon "
            f"({time_to_tca:.1f} minutes)."
        )
    elif time_to_tca <= 240:
        reasons.append(
            f"TCA occurs within the current "
            f"screening window ({time_to_tca:.1f} minutes)."
        )
    else:
        reasons.append(
            f"TCA occurs {time_to_tca:.1f} minutes "
            f"after the screening start."
        )

    reasons.append(
        f"Relative velocity at the sampled closest approach "
        f"is {velocity:.3f} km/s."
    )

    if result.get("tca_at_boundary"):
        reasons.append(
            "The closest approach occurs at the search-window "
            "boundary, so a longer window may be useful."
        )

    return {
        "score": score,
        "band": band,
        "risk_level": risk_level,
        "reasons": reasons,
    }


def analyze_conjunction(result):
    """
    Main public function.

    Returns the original conjunction information plus
    explainable mission-intelligence information.
    """

    analysis = generate_explanation(result)

    return {
        **result,
        "screening_score": analysis["score"],
        "attention_band": analysis["band"],
        "explanation_reasons": analysis["reasons"],
    }


if __name__ == "__main__":
    # Simple standalone demonstration.
    example_result = {
        "satellite_a": "Example A",
        "satellite_b": "Example B",
        "minimum_distance_km": 7.5,
        "relative_velocity_km_s": 8.7,
        "time_to_tca_minutes": 45.0,
        "tca_at_boundary": False,
        "risk_level": "WATCH",
    }

    analysis = analyze_conjunction(example_result)

    print("=" * 60)
    print("ORBITGUARD AI — MISSION INTELLIGENCE")
    print("=" * 60)
    print(f"Screening score : {analysis['screening_score']:.2f}/100")
    print(f"Attention band  : {analysis['attention_band']}")
    print(f"Risk level      : {analysis['risk_level']}")
    print()
    print("Explanation:")
    for reason in analysis["explanation_reasons"]:
        print(f"  • {reason}")