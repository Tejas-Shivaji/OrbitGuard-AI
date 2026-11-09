# OrbitGuard-AI

An interactive satellite-tracking and orbital-intelligence dashboard built with Python, Streamlit, Plotly and SGP4.

## Features

- Interactive 3D Earth and satellite-orbit visualization
- TLE-based satellite tracking and SGP4 propagation
- Satellite selection, view filters and focus controls
- Pairwise conjunction screening and closest-approach summaries
- Distance-versus-time analysis for a selected pair
- Indian satellite asset watchlist and mission-context explanations
- TLE provenance, data-quality checks and screening audit trail

## Technology stack

- Python 3.10+
- Streamlit
- Plotly
- NumPy and Pandas
- Pillow
- Requests
- SGP4

## Installation

1. Clone or download this repository.
2. Create and activate a virtual environment.
3. Install runtime dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Start OrbitGuard-AI:

   ```bash
   python -m streamlit run app/main.py
   ```

On Windows, using `python -m streamlit` avoids relying on the standalone `streamlit.exe` launcher.

## Performance notes

- Normal startup uses the local TLE cache; online retrieval is reserved for missing records or a manual refresh.
- SGP4 satellite records are parsed once per unique TLE and reused for repeated propagation calls.
- Parsed SGP4 records are reused across orbit trails, current positions and conjunction calculations.
- The last conjunction screen and its distance timeline are reused across unrelated Streamlit reruns; a **Run Screening Now** control starts a fresh, exact-time scan.
- Orbital animation remains available but is disabled by default to keep the initial dashboard load lighter.

## Tests

Install the development dependencies and run the offline test suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests use the bundled TLE cache and deterministic mocked positions; they do not require live TLE downloads.

## Project structure

- `app/` — Streamlit dashboard
- `src/data/` — TLE acquisition, parsing and cache handling
- `src/orbit/` — TLE parsing and SGP4 propagation
- `src/risk/` — Conjunction screening, mission context and data quality
- `tests/` — Automated tests
- `data/` — TLE targets, local cache and visualization assets

## Scientific interpretation

Conjunction screening is a sampled geometric-separation analysis. The mission-attention score is a transparent heuristic. Neither is a validated probability-of-collision estimate.

## Author

Tejas G  
GitHub: https://github.com/Tejas-Shivaji

## Galaxy background video

The dashboard includes a decorative, locally bundled monochrome galaxy video at `assets/galaxy_background.mp4`. The video is visual ambience only; satellite propagation, conjunction screening, and mission intelligence continue to use the project's TLE/SGP4 and screening code. Keep the `assets` folder alongside `app`, `src`, and `data` when moving the project.
