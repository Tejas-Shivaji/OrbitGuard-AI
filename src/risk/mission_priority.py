"""Mission-context helpers for OrbitGuard AI.

This module adds a transparent mission/asset context layer. It does not
modify TLE data, SGP4 propagation, geometric screening, or collision
probability calculations.
"""

from src.risk.indian_assets import (
    is_indian_asset,
    indian_asset_type,
)


def get_mission_context(satellite):
    """Return a human-readable mission context for one catalog entry."""

    if not is_indian_asset(satellite):
        return "General satellite"

    asset_type = indian_asset_type(satellite)

    if not asset_type:
        asset_type = "Indian Spacecraft"

    return f"Indian {asset_type}"


def _satellite_is_indian(satellite):
    """Determine Indian-asset status from the complete satellite dictionary."""

    return is_indian_asset(satellite)


def _satellite_asset_type(satellite):
    """Return the Indian asset category for a satellite."""

    asset_type = indian_asset_type(satellite)

    return asset_type or "Indian Spacecraft"


def indian_asset_involvement(result, satellites):
    """Describe whether a conjunction event involves an identified Indian asset."""

    names = {
        result.get("satellite_a"),
        result.get("satellite_b"),
    }

    involved = [
        satellite
        for satellite in satellites
        if satellite.get("name") in names
        and _satellite_is_indian(satellite)
    ]

    if not involved:
        return {
            "indian_asset_involved": False,
            "indian_assets": [],
            "mission_category": "General satellite pair",
            "protection_watch": "STANDARD",
            "explanation": (
                "Neither member of the selected pair is currently identified "
                "by the Indian asset classification layer."
            ),
        }

    categories = sorted(
        {
            _satellite_asset_type(satellite)
            for satellite in involved
        }
    )

    names_text = ", ".join(
        satellite.get("name", "Unknown")
        for satellite in involved
    )

    category_text = ", ".join(categories)

    return {
        "indian_asset_involved": True,
        "indian_assets": [
            satellite.get("name", "Unknown")
            for satellite in involved
        ],
        "mission_category": category_text,
        "protection_watch": "ACTIVE",
        "explanation": (
            f"The selected conjunction involves the identified Indian "
            f"asset(s) {names_text}. The asset category is {category_text}. "
            "OrbitGuard keeps the underlying geometric screening unchanged "
            "while surfacing this event in the mission-protection context."
        ),
    }