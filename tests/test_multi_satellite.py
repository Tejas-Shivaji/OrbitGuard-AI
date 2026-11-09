from pathlib import Path

from src.data.tle_downloader import download_satellites, read_target_ids


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_configured_satellites_load_from_local_cache():
    target_ids = read_target_ids(PROJECT_ROOT / "data" / "targets.txt")
    satellites = download_satellites(
        target_ids=target_ids,
        cache_path=str(PROJECT_ROOT / "data" / "tle_cache.txt"),
        refresh=False,
    )

    assert len(satellites) == len(target_ids)
    assert all(satellite["tle_source_status"] == "CACHED" for satellite in satellites)
    assert all(satellite["line1"].startswith("1 ") for satellite in satellites)
    assert all(satellite["line2"].startswith("2 ") for satellite in satellites)
