from pathlib import Path

import src.data.tle_downloader as downloader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cached_startup_does_not_make_network_requests(tmp_path, monkeypatch):
    source_cache = PROJECT_ROOT / "data" / "tle_cache.txt"
    test_cache = tmp_path / "tle_cache.txt"
    test_cache.write_text(source_cache.read_text(encoding="utf-8"), encoding="utf-8")

    def unexpected_network_call(_norad_id):
        raise AssertionError("Cached startup should not request network TLEs")

    monkeypatch.setattr(downloader, "_retrieve_tle", unexpected_network_call)

    satellites = downloader.download_satellites(
        target_ids=[25544],
        cache_path=str(test_cache),
        refresh=False,
    )

    assert len(satellites) == 1
    assert satellites[0]["norad_id"] == 25544
    assert satellites[0]["tle_source_status"] == "CACHED"


def test_tle_parser_rejects_wrong_norad_id():
    cache_lines = (PROJECT_ROOT / "data" / "tle_cache.txt").read_text(encoding="utf-8").splitlines()
    line1 = cache_lines[2]
    line2 = cache_lines[3]

    assert downloader._parse_tle_text(
        f"ISS (ZARYA)\n{line1}\n{line2}",
        expected_norad_id=99999,
    ) is None
