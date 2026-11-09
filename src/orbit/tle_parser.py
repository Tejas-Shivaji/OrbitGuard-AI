def load_tle_file(filepath):
    """
    Load satellites from a simple 3-line TLE file.

    Format:
        Satellite Name
        TLE Line 1
        TLE Line 2
    """

    satellites = []

    with open(filepath, "r", encoding="utf-8") as file:
        lines = [
            line.strip()
            for line in file
            if line.strip()
        ]

    if len(lines) % 3 != 0:
        raise ValueError(
            "Invalid TLE file. Each satellite must have 3 lines."
        )

    for i in range(0, len(lines), 3):
        satellites.append({
            "name": lines[i],
            "line1": lines[i + 1],
            "line2": lines[i + 2]
        })

    return satellites