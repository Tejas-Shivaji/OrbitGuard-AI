# OrbitGuard-AI

An interactive satellite-tracking and orbital-intelligence dashboard built with **Python, Streamlit, Plotly, and SGP4**.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Open%20OrbitGuard--AI-0ea5a4?style=for-the-badge)](https://orbitguard-by-tejas.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)

## Overview

**OrbitGuard-AI** is a web-based dashboard for exploring satellite orbits and reviewing potential close approaches between tracked objects. It combines TLE-based orbital data, SGP4 propagation, interactive visualizations, and screening summaries in one interface.

The project is designed as an educational and analytical demonstration of satellite tracking and geometric conjunction screening. Its screening outputs should not be treated as operational collision warnings.

## Live Demo

Try the deployed application:

**https://orbitguard-by-tejas.streamlit.app/**

## Features

- **3D orbital visualization** — Explore Earth and satellite-orbit paths through an interactive Plotly view.
- **TLE-based satellite tracking** — Load Two-Line Element (TLE) data and propagate satellite positions using SGP4.
- **Satellite exploration controls** — Select satellites, apply view filters, and focus on tracked objects.
- **Conjunction screening** — Review pairwise geometric separation and closest-approach summaries.
- **Distance timeline** — Inspect distance-versus-time behaviour for a selected satellite pair.
- **Indian satellite watchlist** — Explore selected Indian satellite assets with mission-context explanations.
- **Data quality and provenance** — Review TLE-related checks and data provenance information.
- **Screening audit trail** — Maintain a record of screening activity.
- **Performance-conscious dashboard** — Reuse cached TLE and propagation data where appropriate to reduce repeated work.

## Technology Stack

| Area | Technologies |
|---|---|
| Language | Python |
| Dashboard | Streamlit |
| Visualization | Plotly |
| Orbital propagation | SGP4 |
| Data processing | NumPy, Pandas |
| Image handling | Pillow |
| HTTP requests | Requests |
| Testing | Pytest |

## Run Locally

### 1. Clone the repository

\`\`\`bash
git clone https://github.com/Tejas-Shivaji/OrbitGuard-AI.git
cd OrbitGuard-AI
\`\`\`

### 2. Create a virtual environment

**Windows (PowerShell):**

\`\`\`powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
\`\`\`

**macOS / Linux:**

\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
\`\`\`

### 3. Install dependencies

\`\`\`bash
python -m pip install -r requirements.txt
\`\`\`

### 4. Launch the dashboard

\`\`\`bash
python -m streamlit run app/main.py
\`\`\`

Open the local URL printed in your terminal by Streamlit.

> On Windows, using `python -m streamlit` avoids relying on the standalone `streamlit.exe` launcher.

## Run Tests

Install the development dependencies:

\`\`\`bash
python -m pip install -r requirements-dev.txt
\`\`\`

Run the test suite:

\`\`\`bash
python -m pytest -q
\`\`\`

The tests use the bundled TLE cache and deterministic mocked positions; they do not require live TLE downloads.

## Project Structure

\`\`\`text
OrbitGuard-AI/
├── app/
│   └── main.py
├── assets/
│   └── galaxy_background.mp4
├── data/
├── src/
│   ├── data/
│   ├── orbit/
│   └── risk/
├── tests/
├── requirements.txt
├── requirements-dev.txt
└── README.md
\`\`\`

- `app/` — Streamlit dashboard
- `assets/` — Visual assets
- `data/` — Satellite targets and local data files
- `src/data/` — TLE acquisition, parsing, and caching
- `src/orbit/` — TLE parsing and SGP4 propagation
- `src/risk/` — Screening, mission context, and data quality
- `tests/` — Automated tests

## Performance Notes

- Normal startup uses the local TLE cache; online retrieval is reserved for missing records or a manual refresh.
- SGP4 satellite records are parsed once per unique TLE and reused for repeated propagation calls.
- Parsed SGP4 records are reused across orbit trails, current positions, and conjunction calculations.
- The last conjunction screen and its distance timeline are reused across unrelated Streamlit reruns. **Run Screening Now** starts a fresh, exact-time scan.
- Orbital animation is available but disabled by default to keep the initial dashboard load lighter.

## Scientific Scope and Limitations

OrbitGuard-AI is an educational and analytical project.

- Conjunction screening is a **sampled geometric-separation analysis**.
- The mission-attention score is a **transparent heuristic**, not a validated machine-learning prediction.
- The dashboard does **not** calculate a validated probability of collision.
- Results depend on the quality, age, and availability of the input TLE data.
- The application is not intended for operational spaceflight decisions or as a substitute for authoritative conjunction-assessment services.

## Galaxy Background Asset

The dashboard includes a decorative, locally bundled monochrome galaxy video at `assets/galaxy_background.mp4`. It is used only for visual ambience; satellite propagation, conjunction screening, and mission intelligence use the project's TLE/SGP4 and screening code.

Keep the `assets` folder alongside `app`, `src`, and `data` when moving or deploying the project.

## Author

**Tejas G**

- GitHub: [@Tejas-Shivaji](https://github.com/Tejas-Shivaji)
- Project repository: [OrbitGuard-AI](https://github.com/Tejas-Shivaji/OrbitGuard-AI)
- Live application: [orbitguard-by-tejas.streamlit.app](https://orbitguard-by-tejas.streamlit.app/)

---

If you find an issue or have a suggestion, feel free to open an issue in the GitHub repository.
