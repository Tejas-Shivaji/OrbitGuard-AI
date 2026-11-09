"""Indian satellite classification for OrbitGuard AI.

This module deliberately uses a transparent name/NORAD catalog layer.
It does not modify TLEs or orbital propagation.
"""

# Known/commonly used Indian satellite naming families.
# Exact NORAD IDs can be added here as the target catalog expands.
INDIAN_NAME_KEYWORDS = (
    "IRNSS",
    "NAVIC",
    "CARTOSAT",
    "RISAT",
    "EOS",
    "RESOURCESAT",
    "OCEANSAT",
    "SCATSAT",
    "INSAT",
    "GSAT",
    "G SAT",
    "KALPANA",
    "EDUSAT",
    "SARAL",
    "MEGHA-TROPIQUES",
    "ASTROSAT",
    "CHANDRAYAAN",
    "MANGALYAAN",
    "MOM",
    "EMISAT",
    "MICROSAT",
    "HYSIS",
    "TES",
    "IMS",
)

# Optional explicit NORAD-ID registry for future expansion.
# Keep this set empty until the project target catalog is populated
# with verified Indian spacecraft IDs.
INDIAN_NORAD_IDS = set()


def _normalized_name(satellite):
    return str(satellite.get("name", "")).strip().upper()


def is_indian_asset(satellite):
    """Return True when the satellite matches the Indian asset catalog."""
    norad_id = satellite.get("norad_id")

    if norad_id is not None:
        try:
            if int(norad_id) in INDIAN_NORAD_IDS:
                return True
        except (TypeError, ValueError):
            pass

    name = _normalized_name(satellite)

    return any(keyword in name for keyword in INDIAN_NAME_KEYWORDS)


def indian_asset_type(satellite):
    """Return a simple mission category for an identified Indian asset."""
    if not is_indian_asset(satellite):
        return "Non-Indian / Unclassified"

    name = _normalized_name(satellite)

    if any(token in name for token in ("IRNSS", "NAVIC")):
        return "Navigation"
    if any(token in name for token in ("INSAT", "GSAT", "G SAT")):
        return "Communications"
    if any(
        token in name
        for token in (
            "CARTOSAT",
            "RISAT",
            "EOS",
            "RESOURCESAT",
            "OCEANSAT",
            "SCATSAT",
            "HYSIS",
            "TES",
            "IMS",
        )
    ):
        return "Earth Observation"
    if any(
        token in name
        for token in (
            "ASTROSAT",
            "SARAL",
            "MEGHA-TROPIQUES",
            "CHANDRAYAAN",
            "MANGALYAAN",
            "MOM",
        )
    ):
        return "Science / Exploration"
    if "EMISAT" in name:
        return "Technology / Electronic Intelligence"

    return "Indian Spacecraft"
