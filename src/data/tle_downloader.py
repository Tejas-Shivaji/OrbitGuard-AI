"""TLE acquisition and provenance helpers for OrbitGuard AI.

Acquisition order:
    1. CelesTrak
    2. SatNOGS public database
    3. Local TLE cache

The downloader never fabricates orbital data. If no usable TLE is
available from the network or local cache, the satellite is marked
UNAVAILABLE.
"""

import json
import os
import re
from datetime import datetime, timezone

import requests


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
TARGETS_PATH = os.path.join(DATA_DIR, "targets.txt")
CACHE_PATH = os.path.join(DATA_DIR, "tle_cache.txt")

CELESTRAK_URL = (
    "https://celestrak.org/NORAD/elements/gp.php"
    "?CATNR={norad_id}&FORMAT=TLE"
)

SATNOGS_URL = (
    "https://db.satnogs.org/api/tle/"
    "?norad_cat_id={norad_id}"
)

REQUEST_TIMEOUT_SECONDS = 15

REQUEST_HEADERS = {
    "User-Agent": (
        "OrbitGuard-AI/1.0 "
        "(educational space-situational-awareness project)"
    )
}


def read_target_ids(path=TARGETS_PATH):
    """Read NORAD catalog IDs from targets.txt."""
    if not os.path.exists(path):
        return []

    target_ids = []

    with open(path, "r", encoding="utf-8") as target_file:
        for line in target_file:
            value = line.strip()

            if not value or value.startswith("#"):
                continue

            try:
                target_ids.append(int(value))
            except ValueError:
                continue

    return target_ids


def _extract_norad_id(line1):
    """Extract the NORAD catalog ID from TLE line 1."""
    if not line1:
        return None

    match = re.match(r"1\s+(\d+)[A-Z]?\s", line1.strip())

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def _normalise_tle_record(name, line1, line2, norad_id):
    """Build a normalized OrbitGuard satellite record."""
    return {
        "name": name.strip(),
        "norad_id": int(norad_id),
        "line1": line1.strip(),
        "line2": line2.strip(),
    }


def _validate_tle(name, line1, line2, expected_norad_id=None):
    """Validate the basic structure of a TLE record."""
    if not name or not line1 or not line2:
        return False

    line1 = line1.strip()
    line2 = line2.strip()

    if not line1.startswith("1 "):
        return False

    if not line2.startswith("2 "):
        return False

    if len(line1) < 60 or len(line2) < 60:
        return False

    norad_id = _extract_norad_id(line1)

    if norad_id is None:
        return False

    if expected_norad_id is not None and norad_id != int(
        expected_norad_id
    ):
        return False

    return True


def _parse_tle_text(text, expected_norad_id=None):
    """Parse the common three-line TLE format."""
    if not text:
        return None

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for index in range(len(lines) - 2):
        first = lines[index]
        second = lines[index + 1]
        third = lines[index + 2]

        # Standard:
        # 0 NAME
        # 1 LINE 1
        # 2 LINE 2
        if (
            first.startswith("0 ")
            and second.startswith("1 ")
            and third.startswith("2 ")
        ):
            name = first[2:].strip()
            line1 = second
            line2 = third

            if _validate_tle(
                name,
                line1,
                line2,
                expected_norad_id,
            ):
                norad_id = _extract_norad_id(line1)

                return _normalise_tle_record(
                    name,
                    line1,
                    line2,
                    norad_id,
                )

        # Standard CelesTrak output may also be:
        # NAME
        # LINE 1
        # LINE 2
        if (
            not first.startswith(("0 ", "1 ", "2 "))
            and second.startswith("1 ")
            and third.startswith("2 ")
        ):
            name = first
            line1 = second
            line2 = third

            if _validate_tle(
                name,
                line1,
                line2,
                expected_norad_id,
            ):
                norad_id = _extract_norad_id(line1)

                return _normalise_tle_record(
                    name,
                    line1,
                    line2,
                    norad_id,
                )

    return None


def _load_cache(path=CACHE_PATH):
    """Load cached TLE records from the existing three-line cache."""
    cache = {}

    if not os.path.exists(path):
        return cache

    with open(path, "r", encoding="utf-8") as cache_file:
        lines = [
            line.rstrip("\n")
            for line in cache_file
        ]

    index = 0

    while index < len(lines):
        line = lines[index].strip()

        if not line:
            index += 1
            continue

        # Existing cache format:
        # NORAD
        # NAME
        # LINE 1
        # LINE 2
        try:
            norad_id = int(line)
        except ValueError:
            index += 1
            continue

        if index + 3 >= len(lines):
            break

        name = lines[index + 1].strip()
        line1 = lines[index + 2].strip()
        line2 = lines[index + 3].strip()

        if _validate_tle(
            name,
            line1,
            line2,
            norad_id,
        ):
            cache[norad_id] = _normalise_tle_record(
                name,
                line1,
                line2,
                norad_id,
            )

        index += 4

    return cache


def _write_cache(cache, path=CACHE_PATH):
    """Write TLE cache using OrbitGuard's existing format."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as cache_file:
        for norad_id in sorted(cache):
            record = cache[norad_id]

            cache_file.write(
                f"{record['norad_id']}\n"
            )
            cache_file.write(
                f"{record['name']}\n"
            )
            cache_file.write(
                f"{record['line1']}\n"
            )
            cache_file.write(
                f"{record['line2']}\n"
            )


def _fresh_record(
    record,
    source,
    source_message,
    retrieved_at,
):
    """Attach source provenance to a freshly acquired TLE."""
    result = dict(record)

    result.update(
        {
            "tle_source_status": "FRESH",
            "tle_source": source,
            "tle_source_message": source_message,
            "tle_retrieved_at": retrieved_at,
        }
    )

    return result


def _cached_record(record):
    """Attach provenance to a locally cached TLE."""
    result = dict(record)

    result.update(
        {
            "tle_source_status": "CACHED",
            "tle_source": "Local TLE cache",
            "tle_source_message": (
                "Using previously downloaded TLE data."
            ),
            "tle_retrieved_at": "Unknown",
        }
    )

    return result


def _unavailable_record(
    norad_id,
    message,
):
    """Build a transparent unavailable record."""
    return {
        "name": f"NORAD {norad_id}",
        "norad_id": int(norad_id),
        "line1": "",
        "line2": "",
        "tle_source_status": "UNAVAILABLE",
        "tle_source": "None",
        "tle_source_message": message,
        "tle_retrieved_at": "Unknown",
    }


def _request_celestrak(norad_id):
    """Try to obtain a TLE from CelesTrak."""
    url = CELESTRAK_URL.format(
        norad_id=norad_id
    )

    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    record = _parse_tle_text(
        response.text,
        expected_norad_id=norad_id,
    )

    if record is None:
        raise ValueError(
            "CelesTrak returned no valid TLE."
        )

    return record


def _request_satnogs(norad_id):
    """Try to obtain the latest available TLE from SatNOGS."""
    url = SATNOGS_URL.format(
        norad_id=norad_id
    )

    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list) or not payload:
        raise ValueError(
            "SatNOGS returned no TLE records."
        )

    # Prefer the first returned record, which is the current
    # record returned by the API for this NORAD ID.
    candidate = payload[0]

    name = (
        candidate.get("tle0", "")
        .strip()
    )

    if name.startswith("0 "):
        name = name[2:].strip()

    line1 = candidate.get(
        "tle1",
        "",
    ).strip()

    line2 = candidate.get(
        "tle2",
        "",
    ).strip()

    if not _validate_tle(
        name,
        line1,
        line2,
        expected_norad_id=norad_id,
    ):
        raise ValueError(
            "SatNOGS returned an invalid TLE."
        )

    record = _normalise_tle_record(
        name,
        line1,
        line2,
        norad_id,
    )

    updated = candidate.get(
        "updated",
        "",
    )

    source_name = candidate.get(
        "tle_source",
        "SatNOGS public database",
    )

    message = (
        "TLE obtained through SatNOGS public database"
    )

    if source_name:
        message += (
            f"; underlying TLE source: {source_name}"
        )

    if updated:
        message += f"; SatNOGS updated: {updated}"

    return record, message


def _retrieve_tle(norad_id):
    """Retrieve a TLE using the fallback acquisition chain."""
    now = datetime.now(timezone.utc)
    retrieved_at = now.isoformat()

    celestrak_error = None

    print(
        f"Downloading TLE for NORAD {norad_id}..."
    )

    # ------------------------------------------------------------------
    # 1. CelesTrak
    # ------------------------------------------------------------------
    try:
        record = _request_celestrak(
            norad_id
        )

        print(
            f"✓ CelesTrak TLE retrieved for "
            f"NORAD {norad_id}."
        )

        return _fresh_record(
            record,
            "CelesTrak",
            "TLE retrieved successfully from CelesTrak.",
            retrieved_at,
        )

    except Exception as error:
        celestrak_error = str(error)

        print(
            f"⚠️ CelesTrak request failed: "
            f"{error}"
        )

    # ------------------------------------------------------------------
    # 2. SatNOGS
    # ------------------------------------------------------------------
    try:
        record, message = _request_satnogs(
            norad_id
        )

        print(
            f"✓ SatNOGS TLE retrieved for "
            f"NORAD {norad_id}."
        )

        return _fresh_record(
            record,
            "SatNOGS",
            message,
            retrieved_at,
        )

    except Exception as error:
        print(
            f"⚠️ SatNOGS request failed: "
            f"{error}"
        )

    return None


def download_satellites(
    target_ids=None,
    targets_path=TARGETS_PATH,
    cache_path=CACHE_PATH,
):
    """Download or load TLEs for all requested satellites.

    Returns only satellites with usable TLE data.
    Unavailable satellites are represented with provenance records
    in the returned list so the dashboard can report them explicitly.
    """
    if target_ids is None:
        target_ids = read_target_ids(
            targets_path
        )

    target_ids = [
        int(value)
        for value in target_ids
    ]

    cache = _load_cache(cache_path)

    satellites = []

    fresh_records = {}
    source_counts = {
        "FRESH": 0,
        "CACHED": 0,
        "UNAVAILABLE": 0,
        "UNKNOWN": 0,
    }

    for norad_id in target_ids:
        retrieved = _retrieve_tle(
            norad_id
        )

        if retrieved is not None:
            fresh_records[norad_id] = {
                key: retrieved[key]
                for key in (
                    "name",
                    "norad_id",
                    "line1",
                    "line2",
                )
            }

            satellites.append(
                retrieved
            )

            source_counts[
                retrieved["tle_source_status"]
            ] += 1

            continue

        # --------------------------------------------------------------
        # 3. Local cache fallback
        # --------------------------------------------------------------
        cached = cache.get(norad_id)

        if cached is not None:
            print(
                f"ℹ️ Using cached TLE for "
                f"NORAD {norad_id}."
            )

            cached_result = _cached_record(
                cached
            )

            satellites.append(
                cached_result
            )

            source_counts["CACHED"] += 1

            continue

        # --------------------------------------------------------------
        # 4. No usable TLE
        # --------------------------------------------------------------
            message = (
            "No usable TLE was available "
            "from CelesTrak, SatNOGS, "
            "or the local cache."
        )

        unavailable = _unavailable_record(
            norad_id,
            message,
        )

        satellites.append(
            unavailable
        )

        source_counts["UNAVAILABLE"] += 1

        print(
            f"❌ NORAD {norad_id}: "
            f"No usable TLE is available."
        )

    # Only valid newly retrieved TLEs are merged into the cache.
    #
    # Existing cached records are preserved, including records for
    # targets that could not be refreshed.
    merged_cache = dict(cache)
    merged_cache.update(fresh_records)

    if fresh_records:
        _write_cache(
            merged_cache,
            cache_path,
        )

    print(
        "ℹ️ TLE source summary: "
        f"{source_counts['FRESH']} fresh, "
        f"{source_counts['CACHED']} cached, "
        f"{source_counts['UNAVAILABLE']} unavailable."
    )

    return satellites


if __name__ == "__main__":
    records = download_satellites()

    print()
    print("OrbitGuard TLE acquisition summary")

    for record in records:
        print(
            f"{record['norad_id']:>6} | "
            f"{record['name']:<25} | "
            f"{record.get('tle_source_status', 'UNKNOWN'):<12} | "
            f"{record.get('tle_source', 'Unknown')}"
        )