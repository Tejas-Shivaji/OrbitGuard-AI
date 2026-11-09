from pathlib import Path

from src.orbit.tle_parser import load_tle_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_tle_file_reads_three_line_records():
    satellites = load_tle_file(str(PROJECT_ROOT / "data" / "satellites.txt"))

    assert len(satellites) == 1
    assert satellites[0]["name"] == "ISS (ZARYA)"
    assert satellites[0]["line1"].startswith("1 ")
    assert satellites[0]["line2"].startswith("2 ")
