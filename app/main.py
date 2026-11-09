import os
import sys
import math
import time
import json
import hashlib
import base64
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from PIL import Image

# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# ORBITGUARD IMPORTS
# ============================================================

from src.data.tle_downloader import download_satellites
from src.orbit.propagation import get_satellite_position
from src.risk.conjunction import (
    screen_all_pairs,
    calculate_distance,
    CRITICAL_DISTANCE_KM,
    ELEVATED_DISTANCE_KM,
    WATCH_DISTANCE_KM,
)
from src.risk.intelligence import analyze_conjunction
from src.risk.indian_assets import is_indian_asset, indian_asset_type
from src.risk.mission_priority import get_mission_context, indian_asset_involvement
from src.risk.tle_health import build_satellite_health

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OrbitGuard AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_KM = 6371.0
TEXTURE_PATH = os.path.join(PROJECT_ROOT, "data", "earth_texture.jpg")

AUDIT_LOG_PATH = os.path.join(PROJECT_ROOT, "data", "screening_audit.jsonl")


def append_screening_audit(record):
    """Append one JSON Lines audit record without affecting screening results."""
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as audit_file:
        audit_file.write(
            json.dumps(record, ensure_ascii=False, default=str)
            + "\n"
        )


def load_recent_screening_audits(limit=10):
    """Load the most recent screening audit records for display."""
    if not os.path.exists(AUDIT_LOG_PATH):
        return []

    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as audit_file:
        lines = audit_file.readlines()

    records = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return records

# ============================================================
# USER-PROVIDED GALAXY VIDEO BACKDROP
# ============================================================

# The supplied galaxy clip is bundled locally. It is decorative only; all
# satellite positions, screening results and charts continue to use TLE/SGP4.
GALAXY_VIDEO_PATH = os.path.join(PROJECT_ROOT, "assets", "galaxy_background.mp4")

if os.path.isfile(GALAXY_VIDEO_PATH):
    with open(GALAXY_VIDEO_PATH, "rb") as galaxy_file:
        galaxy_video_b64 = base64.b64encode(galaxy_file.read()).decode("ascii")

    st.markdown(
        f"""
        <div class="og-video-backdrop" aria-hidden="true">
          <video autoplay muted loop playsinline preload="auto"
                 disablepictureinpicture>
            <source src="data:video/mp4;base64,{galaxy_video_b64}" type="video/mp4">
          </video>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.warning("Galaxy background video is missing: assets/galaxy_background.mp4")

# ============================================================
# ORBITGUARD HYBRID AEROSPACE DESIGN SYSTEM
# ============================================================

st.markdown(
    """
    <style>
        :root {
            --og-ink: #07111d;
            --og-ink-2: #0b1b2b;
            --og-panel: #102638;
            --og-panel-light: #d9f0ef;
            --og-cyan: #72d8d0;
            --og-cyan-bright: #9cf3e8;
            --og-yellow: #eaff43;
            --og-paper: #eaf5f4;
            --og-muted: #9cb4c4;
            --og-line: rgba(151, 198, 207, .20);
        }

        .stApp {
            background: transparent;
            color: var(--og-paper);
        }
        /* Keep the live Earth footage behind every Streamlit surface. */
        .og-video-backdrop {
            position: fixed;
            inset: 0;
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            z-index: 0;
            pointer-events: none;
            background: #05070b;
        }
        .og-video-backdrop video {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
            opacity: .72;
            filter: grayscale(1) contrast(1.12) brightness(.92);
        }
        .og-video-backdrop video::-webkit-media-controls {
            display: none !important;
        }
        .og-video-backdrop:after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(90deg, rgba(4,10,18,.34), rgba(4,10,18,.12) 50%, rgba(4,10,18,.38)),
                linear-gradient(180deg, rgba(4,10,18,.24), rgba(4,10,18,.52));
        }
        /* OrbitGuard sidebar information boxes */
        .og-sidebar-note {
            padding: 12px;
            margin: 8px 0;
            border-radius: 9px;
            background: #dceef7;
            border: 1px solid #8bbbd3;
            color: #102a3a !important;
            font-size: 13px;
            font-weight: 600;
            line-height: 1.6;
        }

        .og-sidebar-note.og-status {
            background: #e4f0dc;
            border-color: #a5c58d;
            color: #19351b !important;
        }

        .og-sidebar-note p,
        .og-sidebar-note span,
        .og-sidebar-note strong {
            color: inherit !important;
        }
        [data-testid="stAppViewContainer"] { background: transparent; }
        [data-testid="stMain"] { position: relative; z-index: 1; background: transparent; }
        [data-testid="stSidebar"] { z-index: 2; }

        [data-testid="stHeader"] {
            background: rgba(5, 14, 25, .42);
        }

        .block-container {
            max-width: 1680px;
            padding: 2rem clamp(1rem, 3vw, 3rem) 3.5rem;
        }

        h1, h2, h3, h4 {
            color: #f1fbfa !important;
            letter-spacing: -.035em;
        }
        h1 { font-weight: 850 !important; }
        h2, h3 { font-weight: 750 !important; }
        p, label, [data-testid="stMarkdownContainer"] {
            color: #c4d8df;
        }

        /* Hero header */
        .og-hero {
            position: relative;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 2rem;
            padding: 2.65rem 1.8rem 2.15rem;
            margin: 1.1rem 0 1.6rem;
            overflow: hidden;
            border: 1px solid rgba(114, 216, 208, .23);
            border-radius: 20px;
            background: linear-gradient(112deg, rgba(8, 25, 40, .82), rgba(8, 25, 40, .64) 64%, rgba(20, 48, 57, .72));
            backdrop-filter: blur(16px);
            box-shadow: 0 22px 60px rgba(0, 0, 0, .22);
        }
        .og-hero:after {
            content: "";
            position: absolute;
            width: 290px; height: 290px;
            right: 17%; top: -220px;
            border: 1px solid rgba(156, 243, 232, .22);
            border-radius: 50%;
            box-shadow: 0 0 0 28px rgba(156,243,232,.025), 0 0 0 58px rgba(156,243,232,.02);
            pointer-events: none;
        }
        .og-eyebrow, .og-kicker {
            color: var(--og-cyan) !important;
            font-size: .69rem;
            font-weight: 800;
            letter-spacing: .19em;
            text-transform: uppercase;
        }
        .og-brand {
            color: #f3fbfa;
            font-size: clamp(2rem, 4vw, 3.25rem);
            line-height: 1;
            font-weight: 900;
            letter-spacing: -.065em;
            margin: .55rem 0 .8rem;
        }
        .og-brand span { color: var(--og-yellow); }
        .og-subtitle {
            max-width: 700px;
            color: #b7ccd5;
            font-size: .94rem;
            line-height: 1.65;
        }
        .og-tagline {
            margin-top: 1rem;
            color: #e9f5f3;
            font-size: .76rem;
            font-weight: 750;
            letter-spacing: .12em;
            text-transform: uppercase;
        }
        .og-status-wrap {
            min-width: 225px;
            margin-top: 4.1rem;
            padding: 1.15rem 1.2rem;
            border: 1px solid rgba(234, 255, 67, .4);
            border-radius: 14px;
            background: linear-gradient(145deg, rgba(217,240,239,.12), rgba(217,240,239,.045));
            box-shadow: inset 3px 0 0 var(--og-yellow);
        }
        .og-status-label {
            color: #a9c3ca;
            font-size: .66rem;
            font-weight: 800;
            letter-spacing: .18em;
        }
        .og-status-value {
            color: var(--og-yellow);
            font-size: 1.45rem;
            font-weight: 900;
            letter-spacing: .06em;
            margin: .25rem 0;
        }
        .og-status-detail { color: #b8ced4; font-size: .72rem; }

        /* KPI and reusable panels */
        [data-testid="stMetric"] {
            min-height: 112px;
            padding: 1rem 1.1rem;
            border: 1px solid var(--og-line);
            border-radius: 14px;
            background: linear-gradient(145deg, rgba(19, 48, 65, .78), rgba(10, 29, 44, .76));
            backdrop-filter: blur(14px);
            box-shadow: 0 12px 28px rgba(0,0,0,.14);
        }
        [data-testid="stMetricLabel"] {
            color: #a9c5ce !important;
            font-size: .68rem !important;
            font-weight: 800 !important;
            letter-spacing: .13em;
            text-transform: uppercase;
        }
        [data-testid="stMetricValue"] {
            color: #f0fbf8 !important;
            font-weight: 850 !important;
        }
        [data-testid="stMetricDelta"] { font-size: .75rem !important; }
        .orbitguard-card {
            padding: 1.15rem 1.25rem;
            margin-bottom: .8rem;
            border: 1px solid var(--og-line);
            border-radius: 15px;
            background: linear-gradient(145deg, rgba(18, 45, 61, .78), rgba(9, 26, 41, .78));
            backdrop-filter: blur(14px);
            box-shadow: 0 12px 30px rgba(0,0,0,.17);
        }
        .orbitguard-status-card { margin-top: 0; }
        .orbitguard-label, .og-panel-label {
            color: #a6c1ca;
            font-size: .68rem;
            font-weight: 800;
            letter-spacing: .16em;
            text-transform: uppercase;
            margin-bottom: .4rem;
        }
        .orbitguard-value {
            color: var(--og-yellow);
            font-size: 1.5rem;
            font-weight: 900;
        }
        .orbitguard-muted { color: #a8c0ca; font-size: .76rem; }

        /* Sidebar and controls */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(9, 29, 44, .96) 0%, rgba(5, 17, 29, .97) 100%);
            backdrop-filter: blur(18px);
            border-right: 1px solid var(--og-line);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 { color: var(--og-cyan) !important; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #b8cbd2; }
        .stButton > button {
            min-height: 2.65rem;
            border: 1px solid rgba(114,216,208,.38);
            border-radius: 9px;
            color: #071722;
            background: var(--og-cyan);
            font-weight: 800;
            transition: .18s ease;
        }
        .stButton > button:hover {
            border-color: var(--og-yellow);
            color: #071722;
            background: var(--og-yellow);
            transform: translateY(-1px);
        }
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div {
            border-color: rgba(151,198,207,.28);
            border-radius: 9px;
            background: #102638;
        }
        [data-testid="stExpander"] {
            border: 1px solid var(--og-line);
            border-radius: 12px;
            background: rgba(14, 35, 51, .68);
            backdrop-filter: blur(12px);
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--og-line);
            border-radius: 12px;
            overflow: hidden;
        }
        hr { border-color: var(--og-line) !important; }
        [data-testid="stPlotlyChart"] {
            border: 1px solid rgba(114,216,208,.18);
            border-radius: 15px;
            overflow: hidden;
            background: rgba(5, 16, 27, .42);
            backdrop-filter: blur(10px);
        }
        [data-testid="stCaptionContainer"] { color: #8faab7; }

        /* ====================================================
           GALAXY-VIDEO CONTRAST PASS
           Keep the supplied monochrome galaxy visible while
           ensuring every dashboard label remains readable.
           ==================================================== */
        .og-video-backdrop video {
            opacity: .78;
            filter: grayscale(1) contrast(1.08) brightness(.72);
        }
        .og-video-backdrop:after {
            background:
                linear-gradient(90deg, rgba(1, 4, 9, .76), rgba(1, 4, 9, .62) 50%, rgba(1, 4, 9, .78)),
                linear-gradient(180deg, rgba(1, 4, 9, .62), rgba(1, 4, 9, .78));
        }
        /* Main copy: brighter white, stronger weight and subtle separation. */
        .stApp,
        [data-testid="stMain"] {
            color: #F7FAFF !important;
        }
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stText"],
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        label,
        .stRadio label,
        .stCheckbox label,
        .stSelectbox label,
        .stSlider label,
        .stMultiSelect label {
            color: #F1F5FC !important;
            text-shadow: 0 1px 3px rgba(0, 0, 0, .72);
        }
        h1, h2, h3, h4, h5, h6,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            color: #FFFFFF !important;
            text-shadow: 0 2px 8px rgba(0, 0, 0, .78);
        }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p,
        small, .og-subtitle, .og-status-detail,
        .orbitguard-muted {
            color: #D5E0EC !important;
            text-shadow: 0 1px 3px rgba(0, 0, 0, .85);
        }
        .og-eyebrow, .og-kicker, .og-status-label,
        .orbitguard-label, .og-panel-label {
            color: #9AF4E8 !important;
            text-shadow: 0 1px 4px rgba(0, 0, 0, .9);
        }
        /* More opaque glass surfaces prevent bright galaxy details
           from passing directly behind important numbers and labels. */
        .og-hero {
            background: linear-gradient(112deg, rgba(3, 10, 19, .94), rgba(5, 15, 26, .91) 64%, rgba(7, 22, 31, .93));
            border-color: rgba(154, 244, 232, .34);
        }
        .og-status-wrap,
        [data-testid="stMetric"],
        .orbitguard-card {
            background: linear-gradient(145deg, rgba(5, 15, 26, .94), rgba(7, 19, 31, .93));
            border-color: rgba(177, 205, 224, .30);
        }
        [data-testid="stExpander"],
        [data-testid="stPlotlyChart"] {
            background: rgba(4, 12, 21, .90);
            border-color: rgba(177, 205, 224, .28);
        }
        [data-testid="stMetricLabel"] {
            color: #D8E7F4 !important;
            text-shadow: none !important;
        }
        [data-testid="stMetricValue"] {
            color: #FFFFFF !important;
            text-shadow: 0 1px 4px rgba(0, 0, 0, .8);
        }
        [data-baseweb="select"] *,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea {
            color: #FFFFFF !important;
        }
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div {
            background: rgba(5, 15, 26, .96) !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label {
            color: #E3ECF5 !important;
        }
        /* High-contrast captions over the moving galaxy. */
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
            color: #F2F7FF !important;
            opacity: 1 !important;
            font-size: .88rem !important;
            font-weight: 600 !important;
            line-height: 1.65 !important;
            text-shadow: 0 1px 4px rgba(0, 0, 0, .98), 0 0 9px rgba(0, 0, 0, .92) !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            padding: .45rem .55rem !important;
            border-radius: 8px !important;
            background: rgba(2, 8, 15, .72) !important;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] {
            border: 1px solid rgba(255, 255, 255, .22) !important;
            border-radius: 11px !important;
            background: rgba(236, 244, 247, .96) !important;
            box-shadow: 0 8px 22px rgba(0, 0, 0, .22) !important;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] *,
        [data-testid="stSidebar"] [data-testid="stAlert"] p,
        [data-testid="stSidebar"] [data-testid="stAlert"] span {
            color: #071522 !important;
            font-weight: 750 !important;
            text-shadow: none !important;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] svg {
            color: #071522 !important;
            fill: #071522 !important;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] button {
            color: #071522 !important;
        }

        /* Stabilise Streamlit's native sidebar controls without overriding
           its built-in open/close width and transform animation. */
        [data-testid="stSidebar"] { z-index: 20 !important; }
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"] {
            z-index: 1002 !important;
            opacity: 1 !important;
            visibility: visible !important;
        }
        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stSidebarCollapsedControl"] button {
            min-width: 2.6rem !important;
            min-height: 2.6rem !important;
            border: 1px solid rgba(154, 244, 232, .42) !important;
            border-radius: 10px !important;
            color: #F7FAFF !important;
            background: rgba(3, 12, 22, .94) !important;
            box-shadow: 0 4px 18px rgba(0, 0, 0, .42) !important;
            transition: background-color .15s ease, border-color .15s ease !important;
        }
        [data-testid="stSidebarCollapseButton"] button:hover,
        [data-testid="stSidebarCollapsedControl"] button:hover {
            background: rgba(14, 43, 57, .98) !important;
            border-color: #9AF4E8 !important;
        }

        @media (max-width: 850px) {
            .block-container { padding: 1rem .8rem 2rem; }
            .og-hero { flex-direction: column; gap: .75rem; padding: 1.2rem; }
            .og-status-wrap { width: 100%; min-width: 0; margin-top: .4rem; }
            .og-video-backdrop video { opacity: .72; }
        }

        /* Improve Cached TLE information box readability */
        [data-testid="stSidebar"] [data-testid="stAlert"] {
            background-color: #dceef7 !important;
            border: 1px solid #8bbbd3 !important;
        }

        [data-testid="stSidebar"] [data-testid="stAlert"] p,
        [data-testid="stSidebar"] [data-testid="stAlert"] div,
        [data-testid="stSidebar"] [data-testid="stAlert"] span {
            color: #102a3a !important;
        }

        .og-sidebar-note {
            padding: 12px;
            margin: 8px 0;
            border-radius: 9px;
            background: #dceef7;
            border: 1px solid #8bbbd3;
            color: #102a3a !important;
            font-size: 13px;
            font-weight: 600;
            line-height: 1.6;
        }

        .og-sidebar-note.og-status-cache {
            background: #dceef7;
            color: #102a3a !important;
        }

        .og-sidebar-note.og-status-fresh {
            background: #e4f0dc;
            color: #19351b !important;
        }

        .og-sidebar-note.og-status-error {
            background: #f8dddd;
            color: #641b1b !important;
        }
        
        /* Screening metric cards */
        [data-testid="stMetric"] {
            background: rgba(7, 20, 34, 0.94);
            border: 1px solid rgba(105, 190, 210, 0.30);
            border-radius: 14px;
            padding: 18px 16px;
            min-height: 112px;
        }

        [data-testid="stMetricLabel"] {
            color: #c5d5e2 !important;
            font-size: 13px !important;
            font-weight: 600 !important;
        }

        [data-testid="stMetricValue"] {
            color: #f3f7ff !important;
            font-size: 27px !important;
            font-weight: 750 !important;
        }

        [data-testid="stMetricDelta"] {
            color: #71d8d0 !important;
        }

        /* Make button labels clearly readable */
        .stButton > button,
        .stButton > button p,
        [data-testid="stBaseButton-primary"],
        [data-testid="stBaseButton-primary"] p {
            color: #102a3a !important;
            -webkit-text-fill-color: #102a3a !important;
            text-shadow: none !important;
            font-weight: 700 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# MISSION HEADER
# ============================================================

header_left, header_right = st.columns([3.7, 1.15], gap="large", vertical_alignment="center")

with header_left:
    st.markdown(
        """
        <div class="og-hero">
          <div>
            <div class="og-eyebrow">SPACE SITUATIONAL AWARENESS / OPERATIONS</div>
            <div class="og-brand">ORBITGUARD <span>AI</span></div>
            <div class="og-subtitle">
              Explainable satellite tracking and conjunction screening powered by
              TLE data, SGP4 orbital propagation and transparent mission-context analysis.
            </div>
            <div class="og-tagline">Detect&nbsp; / &nbsp;Analyze&nbsp; / &nbsp;Explain&nbsp; / &nbsp;Protect</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown(
        """
        <div class="og-status-wrap">
          <div class="og-status-label">SYSTEM MODE</div>
          <div class="og-status-value">SCREENING</div>
          <div class="og-status-detail">TLE&nbsp; + &nbsp;SGP4&nbsp; + &nbsp;PAIRWISE ANALYSIS</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# EARTH TEXTURE
# ============================================================

@st.cache_data
def load_earth_texture(texture_path, width=300, height=150):
    image = Image.open(texture_path).convert("RGB")
    image = image.resize((width, height), Image.Resampling.LANCZOS)

    quantized = image.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
    )

    color_indices = np.array(quantized, dtype=np.uint8)
    palette = quantized.getpalette()

    colorscale = []
    for i in range(256):
        r = palette[i * 3]
        g = palette[i * 3 + 1]
        b = palette[i * 3 + 2]
        colorscale.append([i / 255, f"rgb({r},{g},{b})"])

    return color_indices, colorscale



# ============================================================
# DATA
# ============================================================

@st.cache_data(ttl=900)
def load_satellite_catalog(refresh=False):
    return download_satellites(
        targets_path=os.path.join(
            PROJECT_ROOT,
            "data",
            "targets.txt",
        ),
        refresh=refresh,
    )


def calculate_altitude(position):
    radius = math.sqrt(
        position["x_km"] ** 2
        + position["y_km"] ** 2
        + position["z_km"] ** 2
    )
    return radius - EARTH_RADIUS_KM


def enrich_satellite_catalog(satellites):
    """Add Indian-asset classification without changing source TLE data."""
    enriched = []

    for satellite in satellites:
        item = dict(satellite)
        item["is_indian_asset"] = is_indian_asset(item)
        item["asset_type"] = indian_asset_type(item)
        item["mission_context"] = get_mission_context(item)
        enriched.append(item)

    return enriched


def calculate_trajectory(satellite, start_time, duration_hours, points=120):
    times = np.linspace(0, duration_hours * 3600, points)

    x, y, z = [], [], []

    for seconds in times:
        current_time = start_time + timedelta(seconds=float(seconds))

        position = get_satellite_position(
            satellite["name"],
            satellite["line1"],
            satellite["line2"],
            current_time,
        )

        x.append(position["x_km"])
        y.append(position["y_km"])
        z.append(position["z_km"])

    return np.array(x), np.array(y), np.array(z)


@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def calculate_distance_timeline(
    satellite_a,
    satellite_b,
    start_time,
    minutes,
    step_seconds,
):
    total_seconds = minutes * 60
    sample_times = np.arange(
        0,
        total_seconds + step_seconds,
        step_seconds,
    )

    times_minutes = []
    distances = []

    for seconds in sample_times:
        current_time = start_time + timedelta(seconds=float(seconds))

        position_a = get_satellite_position(
            satellite_a["name"],
            satellite_a["line1"],
            satellite_a["line2"],
            current_time,
        )
        position_b = get_satellite_position(
            satellite_b["name"],
            satellite_b["line1"],
            satellite_b["line2"],
            current_time,
        )

        distances.append(calculate_distance(position_a, position_b))
        times_minutes.append(seconds / 60.0)

    return np.array(times_minutes), np.array(distances)


def source_status_counts(satellites):
    """Count TLE provenance states for the loaded catalog."""
    counts = {
        "FRESH": 0,
        "CACHED": 0,
        "UNAVAILABLE": 0,
        "UNKNOWN": 0,
    }

    for satellite in satellites:
        status = satellite.get("tle_source_status", "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1

    return counts


def format_source_status(status):
    labels = {
        "FRESH": " FRESH",
        "CACHED": " CACHED",
        "UNAVAILABLE": " UNAVAILABLE",
        "UNKNOWN": " UNKNOWN",
    }
    return labels.get(status, f" {status}")


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown("##  OrbitGuard Controls")

refresh_requested = st.session_state.pop(
    "orbitguard_refresh_tle_requested",
    False,
)

try:
    satellites = load_satellite_catalog(
        refresh=refresh_requested
    )
except Exception as error:
    st.error(f"Unable to load satellite data: {error}")
    st.stop()

satellites = enrich_satellite_catalog(satellites)

source_counts = source_status_counts(satellites)

st.sidebar.markdown("###  TLE Source Status")

if source_counts["UNAVAILABLE"] > 0:
    status_message = (
        f"{source_counts['UNAVAILABLE']} TLE record(s) unavailable"
    )
    status_class = "og-status-error"

elif source_counts["CACHED"] > 0:
    status_message = (
        f"{source_counts['CACHED']} TLE record(s) using cache"
    )
    status_class = "og-status-cache"

else:
    status_message = (
        f"{source_counts['FRESH']} TLE record(s) freshly loaded"
    )
    status_class = "og-status-fresh"

st.sidebar.markdown(
    f'<div class="og-sidebar-note {status_class}">'
    f'{status_message}</div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    '<div class="og-sidebar-note">'
    'FRESH = source download succeeded<br>'
    'CACHED = source unavailable, local TLE reused'
    '</div>',
    unsafe_allow_html=True,
)

satellite_names = [satellite["name"] for satellite in satellites]

selected_satellites = st.sidebar.multiselect(
    " Satellites",
    satellite_names,
    default=satellite_names,
)

view_mode = st.sidebar.selectbox(
    " 3D View Mode",
    [
        "Earth Focus (LEO)",
        "Full Orbital Context",
        "GEO Focus",
    ],
    index=0,
)

trajectory_duration = st.sidebar.slider(
    " Trajectory Duration (hours)",
    min_value=1,
    max_value=24,
    value=6,
)

indian_only = st.sidebar.checkbox(
    " Indian Asset Watchlist",
    value=False,
    help="Filter the selected satellite list to assets identified by the OrbitGuard Indian satellite catalog.",
)

st.sidebar.divider()

if st.sidebar.button(" Refresh TLE Data", use_container_width=True):
    load_satellite_catalog.clear()
    st.session_state["orbitguard_refresh_tle_requested"] = True
    st.session_state.pop("orbitguard_screening_cache", None)
    st.rerun()

st.sidebar.markdown(
    '<div class="og-sidebar-note">'
    'Cached TLE data is used on startup. '
    'Use Refresh TLE Data to check online sources.'
    '</div>',
    unsafe_allow_html=True,
)

# ============================================================
# CURRENT POSITIONS
# ============================================================

selected_objects = [
    satellite
    for satellite in satellites
    if satellite["name"] in selected_satellites
    and (not indian_only or satellite["is_indian_asset"])
]

calculation_time = datetime.now(timezone.utc)

positions = []
propagation_ok_names = set()

for satellite in selected_objects:
    try:
        position = get_satellite_position(
            satellite["name"],
            satellite["line1"],
            satellite["line2"],
            calculation_time,
        )

        position["norad_id"] = satellite["norad_id"]
        position["altitude_km"] = calculate_altitude(position)
        positions.append(position)
        propagation_ok_names.add(satellite["name"])

    except Exception as error:
        st.warning(
            f"Could not propagate {satellite['name']}: {error}"
        )


def matches_view_mode(position):
    altitude = position["altitude_km"]

    if view_mode == "Earth Focus (LEO)":
        return altitude < 2000
    if view_mode == "GEO Focus":
        return altitude > 30000

    # Full Orbital Context
    return True


display_positions = [
    position
    for position in positions
    if matches_view_mode(position)
]

display_names = [
    position["name"]
    for position in display_positions
]

# The focus selector only offers satellites that are actually visible
# after the selected-satellite, Indian-watchlist, and view-mode filters.
focus_options = ["Automatic"] + display_names
if st.session_state.get("orbitguard_focus_satellite") not in focus_options:
    st.session_state["orbitguard_focus_satellite"] = "Automatic"

focus_satellite_name = st.sidebar.selectbox(
    " Focus Satellite",
    focus_options,
    index=0,
    key="orbitguard_focus_satellite",
    help="Select a currently visible satellite to emphasize its orbit and marker.",
)

# ============================================================
# 3D ORBITAL ENVIRONMENT
# ============================================================


st.subheader(" 3D Orbital Environment")

viz1, viz2, viz3 = st.columns(3)

with viz1:
    animation_enabled = st.checkbox(
        " Enable orbital animation",
        value=False,
        key="orbitguard_animation_enabled",
    )

with viz2:
    animation_frames = st.slider(
        "Animation Frames",
        min_value=24,
        max_value=60,
        value=36,
        step=12,
        key="orbitguard_animation_frames",
    )

with viz3:
    simulation_step_seconds = st.slider(
        "Simulation Step",
        min_value=2,
        max_value=30,
        value=5,
        step=1,
        key="orbitguard_simulation_step",
        help="Smaller values produce smoother orbital motion.",
    )


def create_earth(rotation_degrees=0.0):
    """Create a textured Earth with a controllable visual rotation."""

    rotation = np.deg2rad(rotation_degrees)

    def rotate_xy(x_values, y_values):
        rotated_x = (
            x_values * np.cos(rotation)
            - y_values * np.sin(rotation)
        )
        rotated_y = (
            x_values * np.sin(rotation)
            + y_values * np.cos(rotation)
        )
        return rotated_x, rotated_y

    if not os.path.exists(TEXTURE_PATH):
        latitude = np.linspace(-np.pi / 2, np.pi / 2, 60)
        longitude = np.linspace(-np.pi, np.pi, 120)
        x = (
            EARTH_RADIUS_KM
            * np.cos(latitude)[:, None]
            * np.cos(longitude)[None, :]
        )
        y = (
            EARTH_RADIUS_KM
            * np.cos(latitude)[:, None]
            * np.sin(longitude)[None, :]
        )
        z = (
            EARTH_RADIUS_KM
            * np.sin(latitude)[:, None]
            * np.ones((1, len(longitude)))
        )
        x, y = rotate_xy(x, y)

        return go.Surface(
            x=x, y=y, z=z,
            colorscale="Earth",
            showscale=False,
            hoverinfo="skip",
            name="Earth",
            lighting=dict(
                ambient=0.42,
                diffuse=0.85,
                specular=0.28,
                roughness=0.62,
            ),
            lightposition=dict(x=10000, y=5000, z=10000),
        )

    try:
        texture, colorscale = load_earth_texture(
            TEXTURE_PATH,
            width=256,
            height=128,
        )
    except Exception:
        latitude = np.linspace(-np.pi / 2, np.pi / 2, 60)
        longitude = np.linspace(-np.pi, np.pi, 120)
        x = (
            EARTH_RADIUS_KM
            * np.cos(latitude)[:, None]
            * np.cos(longitude)[None, :]
        )
        y = (
            EARTH_RADIUS_KM
            * np.cos(latitude)[:, None]
            * np.sin(longitude)[None, :]
        )
        z = (
            EARTH_RADIUS_KM
            * np.sin(latitude)[:, None]
            * np.ones((1, len(longitude)))
        )
        x, y = rotate_xy(x, y)

        return go.Surface(
            x=x, y=y, z=z,
            colorscale="Earth",
            showscale=False,
            hoverinfo="skip",
            name="Earth",
            lighting=dict(
                ambient=0.42,
                diffuse=0.85,
                specular=0.28,
                roughness=0.62,
            ),
            lightposition=dict(x=10000, y=5000, z=10000),
        )

    height, width = texture.shape
    latitude = np.linspace(np.pi / 2, -np.pi / 2, height)
    longitude = np.linspace(-np.pi, np.pi, width)

    x = (
        EARTH_RADIUS_KM
        * np.cos(latitude)[:, None]
        * np.cos(longitude)[None, :]
    )
    y = (
        EARTH_RADIUS_KM
        * np.cos(latitude)[:, None]
        * np.sin(longitude)[None, :]
    )
    z = (
        EARTH_RADIUS_KM
        * np.sin(latitude)[:, None]
        * np.ones((1, width))
    )
    x, y = rotate_xy(x, y)

    return go.Surface(
        x=x,
        y=y,
        z=z,
        surfacecolor=texture,
        colorscale=colorscale,
        cmin=0,
        cmax=255,
        showscale=False,
        hoverinfo="skip",
        name="Earth",
        lighting=dict(
            ambient=0.40,
            diffuse=0.86,
            specular=0.30,
            roughness=0.60,
        ),
        lightposition=dict(x=10000, y=5000, z=10000),
    )


def create_atmosphere():
    radius = EARTH_RADIUS_KM * 1.028
    latitude = np.linspace(np.pi / 2, -np.pi / 2, 50)
    longitude = np.linspace(-np.pi, np.pi, 100)

    x = (
        radius
        * np.cos(latitude)[:, None]
        * np.cos(longitude)[None, :]
    )
    y = (
        radius
        * np.cos(latitude)[:, None]
        * np.sin(longitude)[None, :]
    )
    z = (
        radius
        * np.sin(latitude)[:, None]
        * np.ones((1, len(longitude)))
    )

    return go.Surface(
        x=x, y=y, z=z,
        colorscale=[
            [0, "rgb(70,150,255)"],
            [1, "rgb(130,210,255)"],
        ],
        opacity=0.09,
        showscale=False,
        hoverinfo="skip",
        name="Atmosphere",
        lighting=dict(
            ambient=0.82,
            diffuse=0.20,
            specular=0.48,
        ),
    )


def propagate_visualization_positions(
    satellites_for_view,
    frame_time,
):
    """Propagate satellites for the animated visualization."""

    frame_positions = []

    for satellite in satellites_for_view:
        try:
            position = get_satellite_position(
                satellite["name"],
                satellite["line1"],
                satellite["line2"],
                frame_time,
            )
            position["altitude_km"] = calculate_altitude(position)
            frame_positions.append(position)
        except Exception:
            continue

    return frame_positions


def create_spacecraft_traces(position, is_focus=False):
    """
    Create an exaggerated spacecraft glyph for visual clarity.

    This is a visualization symbol, not the physical size or attitude
    of the actual spacecraft.
    """

    x = position["x_km"]
    y = position["y_km"]
    z = position["z_km"]

    scale = max(
        250.0,
        min(
            900.0,
            math.sqrt(x * x + y * y + z * z) * 0.025,
        ),
    )

    body = scale * (0.38 if is_focus else 0.28)
    panel = scale * (1.25 if is_focus else 1.0)
    antenna = scale * (0.90 if is_focus else 0.70)

    body_trace = go.Scatter3d(
        x=[x - body, x + body],
        y=[y, y],
        z=[z, z],
        mode="lines+markers",
        line=dict(
            color="#22D3EE" if is_focus else None,
            width=8 if is_focus else 5,
        ),
        marker=dict(
            size=11 if is_focus else 7,
            symbol="diamond",
            color="#E6FCFF" if is_focus else None,
        ),
        name=(
            f" {position['name']} spacecraft"
            if is_focus
            else f"{position['name']} spacecraft"
        ),
        hovertemplate=(
            f"<b>{position['name']}</b>"
            "<br>Spacecraft marker"
            f"<br>Altitude: {position['altitude_km']:,.1f} km"
            "<extra></extra>"
        ),
        showlegend=True,
    )

    panels_trace = go.Scatter3d(
        x=[
            x - panel, x + panel, None,
            x - panel, x + panel,
        ],
        y=[y, y, None, y, y],
        z=[
            z - scale * 0.18,
            z + scale * 0.18,
            None,
            z + scale * 0.18,
            z - scale * 0.18,
        ],
        mode="lines",
        line=dict(
            color="#22D3EE" if is_focus else None,
            width=6 if is_focus else 3,
        ),
        hoverinfo="skip",
        showlegend=False,
    )

    antenna_trace = go.Scatter3d(
        x=[x, x],
        y=[y, y],
        z=[z, z + antenna],
        mode="lines+markers",
        line=dict(
            color="#22D3EE" if is_focus else None,
            width=5 if is_focus else 2,
        ),
        marker=dict(
            size=6 if is_focus else 5,
            symbol="circle",
            color="#E6FCFF" if is_focus else None,
        ),
        hoverinfo="skip",
        showlegend=False,
    )

    return [
        body_trace,
        panels_trace,
        antenna_trace,
    ]


visible_satellites = [
    satellite
    for satellite in selected_objects
    if satellite["name"] in display_names
]

fig = go.Figure()

fig.add_trace(create_earth(0.0))
fig.add_trace(create_atmosphere())

# Static orbital trails.
for satellite in visible_satellites:
    try:
        x, y, z = calculate_trajectory(
            satellite,
            calculation_time,
            trajectory_duration,
            points=160,
        )

        is_focus = (
            focus_satellite_name != "Automatic"
            and satellite["name"] == focus_satellite_name
        )

        # Draw a soft halo first so the crisp focus orbit remains visible
        # above it. Both traces use the same cyan hue.
        if is_focus:
            fig.add_trace(
                go.Scatter3d(
                    x=x,
                    y=y,
                    z=z,
                    mode="lines",
                    line=dict(color="#22D3EE", width=20),
                    opacity=0.16,
                    name=f"{satellite['name']} orbit glow",
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        fig.add_trace(
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="lines",
                line=dict(
                    color="#22D3EE" if is_focus else None,
                    width=8 if is_focus else 3,
                ),
                opacity=1.0 if is_focus else 0.48,
                name=(
                    f" {satellite['name']} orbit"
                    if is_focus
                    else f"{satellite['name']} orbit"
                ),
                hovertemplate=(
                    "<b>%{fullData.name}</b>"
                    "<br>X: %{x:.1f} km"
                    "<br>Y: %{y:.1f} km"
                    "<br>Z: %{z:.1f} km"
                    "<extra></extra>"
                ),
            )
        )
    except Exception as error:
        st.warning(
            f"Trajectory failed for {satellite['name']}: {error}"
        )

# These positions were already propagated above for the position summary.
# Reuse them for spacecraft markers instead of running SGP4 a second time.
current_positions = display_positions

dynamic_trace_indices = []

for position in current_positions:
    is_focus = (
        focus_satellite_name != "Automatic"
        and position["name"] == focus_satellite_name
    )

    for trace in create_spacecraft_traces(
        position,
        is_focus=is_focus,
    ):
        dynamic_trace_indices.append(len(fig.data))
        fig.add_trace(trace)

if animation_enabled and visible_satellites:
    frame_list = []

    # Use the visible slider value for the simulation time between frames.
    for frame_index in range(animation_frames):
        frame_seconds = frame_index * simulation_step_seconds
        frame_time = calculation_time + timedelta(
            seconds=frame_seconds
        )

        frame_positions = propagate_visualization_positions(
            visible_satellites,
            frame_time,
        )

        earth_rotation_degrees_per_second = 0.25

        earth_rotation_degrees = (
            earth_rotation_degrees_per_second * frame_seconds
        )

        frame_data = [
            create_earth(earth_rotation_degrees),
            create_atmosphere(),
        ]

        frame_spacecraft_count = 0

        for position in frame_positions:
            is_focus = (
                focus_satellite_name != "Automatic"
                and position["name"] == focus_satellite_name
            )

            spacecraft = create_spacecraft_traces(
                position,
                is_focus=is_focus,
            )

            frame_data.extend(spacecraft)
            frame_spacecraft_count += len(spacecraft)

        if frame_spacecraft_count == len(dynamic_trace_indices):
            frame_list.append(
                go.Frame(
                    data=frame_data,
                    traces=[0, 1, *dynamic_trace_indices],
                    name=f"orbit_frame_{frame_index}",
                )
            )

    fig.frames = frame_list

    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                x=0.015,
                y=0.02,
                xanchor="left",
                yanchor="bottom",
                buttons=[
                    dict(
                        label=" Play",
                        method="animate",
                        args=[
                            None,
                            {
                                "frame": {
                                    "duration": 200,
                                    "redraw": True,
                                },
                                "transition": {
                                    "duration": 0,
                                },
                                "fromcurrent": False,
                                "mode": "immediate",
                            },
                        ],
                    ),
                    dict(
                        label=" Pause",
                        method="animate",
                        args=[
                            [None],
                            {
                                "frame": {
                                    "duration": 0,
                                    "redraw": False,
                                },
                                "transition": {
                                    "duration": 0,
                                },
                                "mode": "immediate",
                            },
                        ],
                    ),
                ],
            )
        ]
    )

fig.update_layout(
    height=720,
    margin=dict(l=0, r=0, t=0, b=0),
    paper_bgcolor="#02040a",
    plot_bgcolor="#02040a",
    scene=dict(
        bgcolor="#02040a",
        xaxis=dict(
            title="",
            showbackground=False,
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showspikes=False,
        ),
        yaxis=dict(
            title="",
            showbackground=False,
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showspikes=False,
        ),
        zaxis=dict(
            title="",
            showbackground=False,
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showspikes=False,
        ),
        aspectmode="data",
        camera=dict(
            eye=dict(x=1.55, y=1.55, z=1.15),
            center=dict(x=0, y=0, z=0),
            up=dict(x=0, y=0, z=1),
            projection=dict(type="perspective"),
        ),
        dragmode="orbit",
        uirevision="orbitguard",
    ),
    legend=dict(
        bgcolor="rgba(5,8,15,0.84)",
        bordercolor="rgba(255,255,255,0.12)",
        borderwidth=1,
        font=dict(size=10),
    ),
)

st.plotly_chart(
    fig,
    width="stretch",
    key="orbitguard_3d_environment",
)

focus_label = (
    focus_satellite_name
    if focus_satellite_name != "Automatic"
    else "Automatic"
)

st.caption(
    f"SGP4 visualization epoch: "
    f"{calculation_time.strftime('%Y-%m-%d %H:%M:%S UTC')} "
    f"• View: {view_mode} "
    f"• Focus: {focus_label} "
    f"• Showing {len(current_positions)} of "
    f"{len(selected_objects)} selected satellites "
    f"• Simulation step: {simulation_step_seconds}s"
)

# ============================================================
# CURRENT POSITION SUMMARY
# ============================================================

st.subheader(" Current Satellite Positions")

if positions:
    position_table = pd.DataFrame(
        [
            {
                "Satellite": position["name"],
                "NORAD ID": position["norad_id"],
                "Indian Asset": (
                    "YES"
                    if next(
                        satellite["is_indian_asset"]
                        for satellite in satellites
                        if satellite["name"] == position["name"]
                    )
                    else "NO"
                ),
                "Altitude (km)": round(position["altitude_km"], 2),
                "X (km)": round(position["x_km"], 2),
                "Y (km)": round(position["y_km"], 2),
                "Z (km)": round(position["z_km"], 2),
            }
            for position in positions
        ]
    )

    st.dataframe(
        position_table,
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No satellite positions are available for the current selection.")

# ============================================================
# CONJUNCTION SCREENING
# ============================================================

st.divider()
st.subheader(" Conjunction Risk Analysis")

control1, control2, control3 = st.columns([1.1, 1.1, 1])

with control1:
    screening_minutes = st.slider(
        "Screening Window",
        min_value=30,
        max_value=360,
        value=180,
        step=30,
        format="%d min",
    )

with control2:
    screening_step = st.selectbox(
        "Propagation Step",
        [30, 60, 120],
        index=1,
        format_func=lambda value: f"{value} seconds",
    )

with control3:
    st.markdown("**Screening thresholds**")
    st.caption(
        f"Watch < {WATCH_DISTANCE_KM:g} km  •  "
        f"Elevated < {ELEVATED_DISTANCE_KM:g} km  •  "
        f"Critical < {CRITICAL_DISTANCE_KM:g} km"
    )

selected_count = len(selected_objects)
eligible_satellites = [
    satellite
    for satellite in selected_objects
    if satellite["name"] in propagation_ok_names
]
propagated_count = len(eligible_satellites)
expected_pairs = propagated_count * (propagated_count - 1) // 2

screening_signature = {
    "selected_satellites": [
        (satellite["name"], satellite.get("line1", ""), satellite.get("line2", ""))
        for satellite in selected_objects
    ],
    "eligible_satellites": [
        (satellite["name"], satellite.get("line1", ""), satellite.get("line2", ""))
        for satellite in eligible_satellites
    ],
    "minutes": screening_minutes,
    "step_seconds": screening_step,
}
screening_digest = hashlib.sha256(
    json.dumps(screening_signature, sort_keys=True).encode("utf-8")
).hexdigest()[:12]

force_screening = st.button(
    " Run Screening Now",
    key="orbitguard_run_screening_now",
)
st.caption(
    "The last scan is reused when the satellite TLEs and screening settings "
    "are unchanged. Run Screening Now to calculate a fresh screening epoch."
)

cached_screening = st.session_state.get("orbitguard_screening_cache")
cache_matches = (
    isinstance(cached_screening, dict)
    and cached_screening.get("signature") == screening_digest
)

if force_screening or not cache_matches:
    screening_start = datetime.now(timezone.utc)
    screening_wall_start = time.perf_counter()
    screening_error = None
    screening_results = []

    with st.spinner("Running pairwise conjunction screening..."):
        try:
            screening_results = screen_all_pairs(
                eligible_satellites,
                start_time=screening_start,
                minutes=screening_minutes,
                step_seconds=screening_step,
            )
        except Exception as error:
            screening_error = str(error)

    screening_runtime_seconds = time.perf_counter() - screening_wall_start
    screening_end = datetime.now(timezone.utc)

    st.session_state["orbitguard_screening_cache"] = {
        "signature": screening_digest,
        "start": screening_start,
        "end": screening_end,
        "results": screening_results,
        "runtime_seconds": screening_runtime_seconds,
        "error": screening_error,
    }
else:
    screening_start = cached_screening["start"]
    screening_end = cached_screening["end"]
    screening_results = cached_screening["results"]
    screening_runtime_seconds = cached_screening["runtime_seconds"]
    screening_error = cached_screening["error"]

returned_pairs = len(screening_results)

if screening_error:
    screening_integrity = "BLOCKED"
    screening_integrity_reason = (
        "The screening engine raised an exception before a complete "
        "pairwise result set could be produced."
    )
elif expected_pairs == 0:
    screening_integrity = "NOT APPLICABLE"
    screening_integrity_reason = (
        "At least two successfully propagated selected satellites are "
        "required for a pairwise conjunction screen."
    )
elif returned_pairs == expected_pairs:
    screening_integrity = "COMPLETE"
    screening_integrity_reason = (
        "All expected pairs among successfully propagated selected "
        "satellites returned a screening result."
    )
else:
    screening_integrity = "PARTIAL"
    screening_integrity_reason = (
        f"{returned_pairs} of {expected_pairs} expected eligible pairs "
        "returned results."
    )

if selected_count > propagated_count:
    screening_integrity = (
        "PARTIAL"
        if screening_integrity not in {"BLOCKED", "NOT APPLICABLE"}
        else screening_integrity
    )
    screening_integrity_reason += (
        f" {selected_count - propagated_count} selected satellite(s) "
        "failed local propagation and were not considered fully eligible."
    )

if screening_error:
    st.error(
        f"Screening could not complete: {screening_error}"
    )

non_nominal = [
    result
    for result in screening_results
    if result["risk_level"] != "NOMINAL"
]

closest_result = None

if screening_results:
    closest_result = min(
        screening_results,
        key=lambda result: result["minimum_distance_km"],
    )

health_records = [
    build_satellite_health(
        satellite,
        satellite["name"] in propagation_ok_names,
        calculation_time,
    )
    for satellite in selected_objects
]

screening_id = (
    f"{screening_start.strftime('%Y%m%dT%H%M%S%fZ')}-{screening_digest}"
)

audit_record = {
    "screening_id": screening_id,
    "screening_start_utc": screening_start.isoformat(),
    "screening_end_utc": screening_end.isoformat(),
    "screening_window_minutes": screening_minutes,
    "propagation_step_seconds": screening_step,
    "selected_satellites": [
        satellite["name"] for satellite in selected_objects
    ],
    "selected_count": selected_count,
    "propagated_count": propagated_count,
    "expected_pairs": expected_pairs,
    "returned_pairs": returned_pairs,
    "screening_integrity": screening_integrity,
    "screening_runtime_seconds": round(screening_runtime_seconds, 4),
    "non_nominal_events": len(non_nominal),
    "closest_separation_km": (
        round(closest_result["minimum_distance_km"], 4)
        if closest_result
        else None
    ),
    "tle_source_counts": source_counts,
    "tle_status_counts": (
        pd.Series([record["tle_status"] for record in health_records])
        .value_counts()
        .to_dict()
        if health_records
        else {}
    ),
    "screening_error": screening_error,
}

# A Streamlit widget change can rerun the whole script. Record each
# distinct scan once instead of appending duplicate audit rows on every rerun.
known_audit_ids = {
    record.get("screening_id")
    for record in load_recent_screening_audits(limit=100)
}
if screening_id not in known_audit_ids:
    append_screening_audit(audit_record)

# ============================================================
# KPI ROW
# ============================================================

st.markdown("### Screening Overview")

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric("Pairs Screened", len(screening_results))

with k2:
    st.metric(
        "Non-Nominal",
        len(non_nominal),
        delta=None,
    )

with k3:
    st.metric(
        "Closest Separation",
        (
            f"{closest_result['minimum_distance_km']:,.1f} km"
            if closest_result
            else "N/A"
        ),
    )

with k4:
    st.metric("Search Window", f"{screening_minutes} min")

st.markdown("###  Screening Integrity")

ri1, ri2, ri3, ri4 = st.columns(4)

with ri1:
    st.metric("Selected Satellites", selected_count)

with ri2:
    st.metric("Propagation OK", propagated_count)

with ri3:
    st.metric("Expected Eligible Pairs", expected_pairs)

with ri4:
    st.metric("Integrity Status", screening_integrity)

if screening_integrity == "COMPLETE":
    st.success(f"**COMPLETE:** {screening_integrity_reason}")
elif screening_integrity == "PARTIAL":
    st.warning(f"**PARTIAL:** {screening_integrity_reason}")
elif screening_integrity == "BLOCKED":
    st.error(f"**BLOCKED:** {screening_integrity_reason}")
else:
    st.info(f"**{screening_integrity}:** {screening_integrity_reason}")

st.caption(
    "Integrity status describes whether OrbitGuard produced the expected "
    "pairwise result set for the selected, successfully propagated satellites. "
    "It is a software/data-completeness indicator, not a collision-risk estimate."
)

# ============================================================
# RISK DISTRIBUTION
# ============================================================

if screening_results:
    risk_counts = (
        pd.DataFrame(screening_results)["risk_level"]
        .value_counts()
        .reindex(
            ["CRITICAL", "ELEVATED", "WATCH", "NOMINAL"],
            fill_value=0,
        )
        .reset_index()
    )

    risk_counts.columns = ["Risk Level", "Pairs"]

    risk_chart = px.bar(
        risk_counts,
        x="Pairs",
        y="Risk Level",
        orientation="h",
        text="Pairs",
        category_orders={
            "Risk Level": [
                "CRITICAL",
                "ELEVATED",
                "WATCH",
                "NOMINAL",
            ]
        },
    )

    risk_chart.update_traces(
        marker_line_width=0,
        textposition="outside",
    )

    risk_chart.update_layout(
        title="Conjunction Risk Distribution",
        height=300,
        margin=dict(l=20, r=40, t=60, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Number of pairs",
        yaxis_title="",
        showlegend=False,
    )

    st.plotly_chart(risk_chart, width="stretch")

# ============================================================
# SCREENING TABLE
# ============================================================

st.subheader(" Pair Screening Results")

if screening_results:

    total_events = len(screening_results)

    indian_events = sum(
        1
        for result in screening_results
        if result.get("indian_asset_involved", False)
    )

    elevated_events = sum(
        1
        for result in screening_results
        if analyze_conjunction(result)["screening_score"] >= 50
    )

    s1, s2, s3 = st.columns(3)

    with s1:
        st.metric("Total Events", total_events)

    with s2:
        st.metric("Indian-Asset Events", indian_events)

    with s3:
        st.metric("Elevated Attention", elevated_events)

    screening_table = pd.DataFrame(
        [
            {
                "Satellite A": result["satellite_a"],
                "Satellite B": result["satellite_b"],
                "Minimum Separation (km)": round(
                    result["minimum_distance_km"],
                    3,
                ),
                "Relative Velocity (km/s)": round(
                    result["relative_velocity_km_s"],
                    3,
                ),
                "TCA (min)": round(
                    result["time_to_tca_minutes"],
                    1,
                ),
                "TCA Status": (
                    "BOUNDARY"
                    if result["tca_at_boundary"]
                    else "INTERIOR"
                ),
                "Risk": result["risk_level"],
                "Attention Score": round(
                    analyze_conjunction(result)["screening_score"],
                    1,
                ),
                "Attention Band": analyze_conjunction(result)[
                    "attention_band"
                ],
                "Indian Asset": (
                    "YES"
                    if result.get(
                        "indian_asset_involved",
                        False,
                    )
                    else "NO"
                ),
                "Mission Category": result.get(
                    "mission_category",
                    "General satellite pair",
                ),
                "Protection Watch": result.get(
                    "protection_watch",
                    "STANDARD",
                ),
            }
            for result in screening_results
        ]
    )

    st.dataframe(
        screening_table,
        width="stretch",
        hide_index=True,
    )


# ============================================================
# SELECTED EVENT
# ============================================================

if screening_results:
    st.subheader(" Selected Conjunction Event")

    event_labels = [
        f"{result['satellite_a']} ↔ {result['satellite_b']}"
        for result in screening_results
    ]

    selected_label = st.selectbox(
        "Select a satellite pair",
        event_labels,
    )

    selected_index = event_labels.index(selected_label)
    selected_result = screening_results[selected_index]

    mission_context = indian_asset_involvement(
        selected_result,
        satellites,
    )

    satellite_a = next(
        satellite
        for satellite in satellites
        if satellite["name"] == selected_result["satellite_a"]
    )

    satellite_b = next(
        satellite
        for satellite in satellites
        if satellite["name"] == selected_result["satellite_b"]
    )

    e1, e2, e3, e4 = st.columns(4)

    with e1:
        st.metric(
            "Minimum Separation",
            f"{selected_result['minimum_distance_km']:,.3f} km",
        )

    with e2:
        st.metric(
            "Relative Velocity",
            f"{selected_result['relative_velocity_km_s']:.3f} km/s",
        )

    with e3:
        st.metric(
            "Time to TCA",
            f"{selected_result['time_to_tca_minutes']:.1f} min",
        )

    with e4:
        st.metric(
            "Screening Level",
            selected_result["risk_level"],
        )

    # ========================================================
    # DISTANCE VS TIME
    # ========================================================

    st.subheader(" Distance vs Time — Closest Approach")

    with st.spinner("Calculating separation timeline..."):
        timeline_minutes, timeline_distance = calculate_distance_timeline(
            satellite_a,
            satellite_b,
            screening_start,
            screening_minutes,
            screening_step,
        )

    distance_fig = go.Figure()

    distance_fig.add_trace(
        go.Scatter(
            x=timeline_minutes,
            y=timeline_distance,
            mode="lines",
            line=dict(width=3),
            name="Separation",
            hovertemplate=(
                "Time: %{x:.1f} min"
                "<br>Distance: %{y:,.2f} km"
                "<extra></extra>"
            ),
        )
    )

    distance_fig.add_hline(
        y=CRITICAL_DISTANCE_KM,
        line_dash="dash",
        annotation_text=f"Critical: {CRITICAL_DISTANCE_KM:g} km",
        annotation_position="top left",
    )

    distance_fig.add_hline(
        y=ELEVATED_DISTANCE_KM,
        line_dash="dash",
        annotation_text=f"Elevated: {ELEVATED_DISTANCE_KM:g} km",
        annotation_position="top left",
    )

    distance_fig.add_hline(
        y=WATCH_DISTANCE_KM,
        line_dash="dash",
        annotation_text=f"Watch: {WATCH_DISTANCE_KM:g} km",
        annotation_position="top left",
    )

    tca_minutes = selected_result["time_to_tca_minutes"]
    tca_distance = selected_result["minimum_distance_km"]

    distance_fig.add_trace(
        go.Scatter(
            x=[tca_minutes],
            y=[tca_distance],
            mode="markers",
            marker=dict(size=12, symbol="diamond"),
            name="TCA",
            hovertemplate=(
                "TCA: %{x:.1f} min"
                "<br>Minimum separation: %{y:,.3f} km"
                "<extra></extra>"
            ),
        )
    )

    distance_fig.update_layout(
        title=(
            f"{selected_result['satellite_a']} ↔ "
            f"{selected_result['satellite_b']}"
        ),
        xaxis_title="Time from Screening Start (minutes)",
        yaxis_title="Separation Distance (km)",
        height=500,
        hovermode="x unified",
        margin=dict(l=50, r=30, t=70, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(distance_fig, width="stretch")

    # ========================================================
    # TCA DETAILS
    # ========================================================

    st.subheader(" Time of Closest Approach")

    tca_time = selected_result["tca_time"]
    tca_col1, tca_col2, tca_col3 = st.columns(3)

    with tca_col1:
        st.metric(
            "TCA Time",
            tca_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

    with tca_col2:
        st.metric(
            "Minimum Separation",
            f"{selected_result['minimum_distance_km']:,.3f} km",
        )

    with tca_col3:
        boundary_status = (
            "Search Boundary"
            if selected_result["tca_at_boundary"]
            else "Inside Search Window"
        )
        st.metric("TCA Status", boundary_status)

    # ========================================================
    # EXPLAINABLE RESULT
    # ========================================================

    st.subheader(" Explainable Screening Result")

    distance = selected_result["minimum_distance_km"]
    relative_velocity = selected_result["relative_velocity_km_s"]
    risk = selected_result["risk_level"]

    if risk == "CRITICAL":
        explanation = (
            f"The predicted minimum geometric separation is "
            f"{distance:,.3f} km, below the "
            f"{CRITICAL_DISTANCE_KM:.1f} km critical screening threshold. "
            f"The relative velocity is {relative_velocity:.3f} km/s."
        )
    elif risk == "ELEVATED":
        explanation = (
            f"The predicted minimum geometric separation is "
            f"{distance:,.3f} km, below the "
            f"{ELEVATED_DISTANCE_KM:.1f} km elevated screening threshold. "
            f"The relative velocity is {relative_velocity:.3f} km/s."
        )
    elif risk == "WATCH":
        explanation = (
            f"The predicted minimum geometric separation is "
            f"{distance:,.3f} km, placing the pair inside the "
            f"{WATCH_DISTANCE_KM:.1f} km watch threshold."
        )
    else:
        explanation = (
            f"The predicted minimum geometric separation is "
            f"{distance:,.3f} km, outside the current geometric "
            f"screening thresholds."
        )

    st.info(explanation)

    st.warning(
        """
        **Scientific limitation:** OrbitGuard AI currently performs
        geometric conjunction screening using TLE-derived SGP4
        trajectories. The displayed risk levels are **screening
        classifications, not probabilities of collision**.

        Operational collision assessment would require additional
        information such as covariance, maneuver data, higher-fidelity
        propagation, uncertainty modeling and established conjunction
        assessment methods.
        """
    )

    # ========================================================
    # MISSION INTELLIGENCE
    # ========================================================

    st.subheader(" Mission Intelligence")

    intelligence = analyze_conjunction(selected_result)

    st.markdown("#### Operational Attention")

    mi1, mi2, mi3 = st.columns(3)

    with mi1:
        st.metric(
            "Screening Score",
            f"{intelligence['screening_score']:.2f} / 100",
        )

    with mi2:
        st.metric(
            "Attention Band",
            intelligence["attention_band"],
        )

    with mi3:
        st.metric(
            "Geometric Risk",
            intelligence["risk_level"],
        )

    st.markdown("#### Conjunction Geometry")

    g1, g2, g3, g4 = st.columns(4)

    with g1:
        st.metric(
            "Minimum Separation",
            f"{selected_result['minimum_distance_km']:.3f} km",
        )

    with g2:
        st.metric(
            "Relative Velocity",
            f"{selected_result['relative_velocity_km_s']:.3f} km/s",
        )

    with g3:
        st.metric(
            "Time to TCA",
            f"{selected_result['time_to_tca_minutes']:.1f} min",
        )

    with g4:
        st.metric(
            "TCA Status",
            (
                "BOUNDARY"
                if selected_result["tca_at_boundary"]
                else "INTERIOR"
            ),
        )

    st.markdown("#### Why did OrbitGuard assign this attention level?")

    for reason in intelligence["explanation_reasons"]:
        st.markdown(f"• {reason}")

    st.info(
        """
        **Interpretation:** The Mission Intelligence score is a
        transparent heuristic screening aid based on minimum separation,
        relative velocity and time-to-TCA urgency.

        It is **not a probability of collision** and should not be used
        by itself for operational collision-avoidance decisions.
        """
    )


    # ========================================================
    # MISSION CONTEXT
    # ========================================================

    st.subheader(" Mission Context")

    mc1, mc2, mc3 = st.columns(3)

    with mc1:
        st.metric(
            "Indian Asset Involved",
            "YES" if mission_context["indian_asset_involved"] else "NO",
        )

    with mc2:
        st.metric(
            "Mission Category",
            mission_context["mission_category"],
        )

    with mc3:
        st.metric(
            "Protection Watch",
            mission_context["protection_watch"],
        )

    st.markdown("#### Mission-aware interpretation")
    st.write(mission_context["explanation"])

    st.caption(
        "Mission context is a transparent asset-classification layer. "
        "It does not change orbital propagation, geometric separation, "
        "or collision probability."
    )

# ============================================================
# INDIAN SATELLITE WATCHLIST
# ============================================================

st.divider()
st.subheader(" Indian Satellite Watchlist")

indian_assets = [
    satellite
    for satellite in satellites
    if satellite["is_indian_asset"]
]

watch_col1, watch_col2, watch_col3 = st.columns(3)

with watch_col1:
    st.metric("Indian Assets Detected", len(indian_assets))

with watch_col2:
    indian_events = [
        result
        for result in screening_results
        if any(
            satellite["is_indian_asset"]
            for satellite in satellites
            if satellite["name"]
            in [result["satellite_a"], result["satellite_b"]]
        )
    ]
    st.metric("Indian-Asset Pairs", len(indian_events))

with watch_col3:
    st.metric(
        "Watchlist Mode",
        "ON" if indian_only else "OFF",
    )

if indian_assets:
    indian_table = pd.DataFrame(
        [
            {
                "Satellite": satellite["name"],
                "NORAD ID": satellite["norad_id"],
                "Asset Type": satellite["asset_type"],
                "Mission Context": satellite["mission_context"],
                "Watch Status": "ACTIVE",
            }
            for satellite in indian_assets
        ]
    )

    st.dataframe(
        indian_table,
        width="stretch",
        hide_index=True,
    )
else:
    st.info(
        "No Indian satellite is currently present in the loaded TLE catalog. "
        "The watchlist classifier is active, but the current target set "
        "contains no matching Indian asset."
    )

st.caption(
    "Indian-asset identification is a transparent catalog/classification "
    "layer. It does not change the underlying SGP4 geometry or imply a "
    "collision probability."
)

# ============================================================
# DATA QUALITY & SYSTEM HEALTH
# ============================================================

st.divider()
st.subheader(" Data Quality & System Health")

health_df = pd.DataFrame(
    [
        {
            "Satellite": record["satellite"],
            "NORAD ID": record["norad_id"],
            "TLE Epoch": (
                record["tle_epoch"].strftime("%Y-%m-%d %H:%M:%S UTC")
                if record["tle_epoch"]
                else "Unknown"
            ),
            "TLE Age (hours)": (
                round(record["tle_age_hours"], 1)
                if record["tle_age_hours"] is not None
                else None
            ),
            "TLE Status": record["tle_status"],
            "TLE Source": format_source_status(
                next(
                    (
                        satellite.get("tle_source_status", "UNKNOWN")
                        for satellite in selected_objects
                        if satellite["name"] == record["satellite"]
                    ),
                    "UNKNOWN",
                )
            ),
            "Source Message": next(
                (
                    satellite.get("tle_source_message", "")
                    for satellite in selected_objects
                    if satellite["name"] == record["satellite"]
                ),
                "",
            ),
            "Propagation": record["propagation_status"],
        }
        for record in health_records
    ]
)

system_health_status = (
    "HEALTHY"
    if (
        selected_count > 0
        and propagated_count == selected_count
        and returned_pairs == expected_pairs
        and screening_error is None
    )
    else "DEGRADED"
)

if system_health_status == "HEALTHY":
    st.success(
        "SYSTEM HEALTH: HEALTHY — all selected satellites propagated "
        "successfully and the expected conjunction pairs were screened."
    )
else:
    st.warning(
        "SYSTEM HEALTH: DEGRADED — one or more data, propagation, "
        "or screening checks require attention."
    )

h1, h2, h3, h4 = st.columns(4)

fresh_or_recent = sum(
    record["tle_status"] in {"FRESH", "RECENT"}
    for record in health_records
)
propagation_ok = sum(
    record["propagation_status"] == "OK"
    for record in health_records
)

with h1:
    st.metric("TLE Records", len(health_records))

with h2:
    st.metric("Fresh / Recent", fresh_or_recent)

with h3:
    st.metric("Propagation OK", propagation_ok)

with h4:
    st.metric("Screening Runtime", f"{screening_runtime_seconds:.2f} s")

st.dataframe(
    health_df,
    width="stretch",
    hide_index=True,
)

st.markdown("#### Screening Configuration")

configuration_df = pd.DataFrame(
    [
        {
            "Parameter": "Selected Satellites",
            "Value": str(selected_count),
        },
        {
            "Parameter": "Screening Window",
            "Value": f"{screening_minutes} minutes",
        },
        {
            "Parameter": "Propagation Step",
            "Value": f"{screening_step} seconds",
        },
        {
            "Parameter": "Calculation Time",
            "Value": calculation_time.strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
        },
        {
            "Parameter": "TLE Source",
            "Value": ", ".join(
                f"{status}: {count}"
                for status, count in source_status_counts(
                    selected_objects
                ).items()
            ),
        },
    ]
)

st.dataframe(
    configuration_df,
    width="stretch",
    hide_index=True,
)

st.markdown("#### Screening Integrity Details")

integrity_detail = pd.DataFrame(
    [
        {
            "Check": "Selected satellites",
            "Value": str(selected_count),
            "Status": "OK" if selected_count > 0 else "EMPTY",
        },
        {
            "Check": "Successfully propagated",
            "Value": str(propagated_count),
            "Status": (
                "OK"
                if propagated_count == selected_count
                else "INCOMPLETE"
            ),
        },
        {
            "Check": "Expected eligible pairs",
            "Value": str(expected_pairs),
            "Status": "OK" if expected_pairs > 0 else "NOT APPLICABLE",
        },
        {
            "Check": "Returned screening pairs",
            "Value": str(returned_pairs),
            "Status": (
                "OK"
                if returned_pairs == expected_pairs
                else "INCOMPLETE"
            ),
        },
        {
            "Check": "Screening runtime (s)",
            "Value": f"{screening_runtime_seconds:.3f}",
            "Status": "OK" if screening_error is None else "FAILED",
        },
        {
            "Check": "Overall integrity",
            "Value": screening_integrity,
            "Status": screening_integrity,
        },
    ]
)

st.dataframe(
    integrity_detail,
    width="stretch",
    hide_index=True,
)

st.caption(
    "TLE age is measured from the orbital epoch encoded in each TLE, "
    "not from the moment the file was downloaded. These indicators describe "
    "data recency and local propagation success; they are not estimates "
    "of orbital uncertainty or collision probability."
)

# ============================================================
# TLE SOURCE PROVENANCE
# ============================================================

st.divider()
st.subheader(" TLE Source Provenance")

source_table = pd.DataFrame(
    [
        {
            "Satellite": satellite["name"],
            "NORAD ID": satellite["norad_id"],
            "Source": satellite.get("tle_source", "Unknown"),
            "Status": format_source_status(
                satellite.get("tle_source_status", "UNKNOWN")
            ),
            "Retrieved UTC": satellite.get(
                "tle_retrieved_at",
                "Unknown",
            ),
            "Message": satellite.get(
                "tle_source_message",
                "",
            ),
        }
        for satellite in selected_objects
    ]
)

if not source_table.empty:
    st.dataframe(
        source_table,
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No selected satellites have TLE provenance records.")

st.caption(
    "CACHED means OrbitGuard could not obtain a fresh source response and "
    "reused the previously stored TLE. Cached data remains usable for local "
    "screening, but its provenance is explicitly shown."
)

# ============================================================
# SCREENING AUDIT TRAIL
# ============================================================

st.divider()
st.subheader(" Screening Audit Trail")

st.caption(
    "Each completed dashboard run appends a compact JSON Lines audit record "
    "to data/screening_audit.jsonl. The audit trail records configuration, "
    "coverage and timing metadata; it does not alter orbital calculations."
)

recent_audits = load_recent_screening_audits(limit=10)

if recent_audits:
    audit_table = pd.DataFrame(
        [
            {
                "Screening ID": record.get("screening_id", "Unknown"),
                "Start UTC": record.get("screening_start_utc", "Unknown"),
                "Window (min)": record.get("screening_window_minutes", "N/A"),
                "Step (s)": record.get("propagation_step_seconds", "N/A"),
                "Selected": record.get("selected_count", 0),
                "Expected Pairs": record.get("expected_pairs", 0),
                "Returned Pairs": record.get("returned_pairs", 0),
                "Integrity": record.get("screening_integrity", "Unknown"),
                "Runtime (s)": record.get(
                    "screening_runtime_seconds",
                    "N/A",
                ),
                "Non-Nominal": record.get("non_nominal_events", 0),
                "Closest (km)": record.get(
                    "closest_separation_km",
                    "N/A",
                ),
            }
            for record in reversed(recent_audits)
        ]
    )

    st.dataframe(
        audit_table,
        width="stretch",
        hide_index=True,
    )

    with st.expander("View latest audit record"):
        st.json(recent_audits[-1])
else:
    st.info("No screening audit records have been created yet.")

# ============================================================
# SATELLITE CATALOG
# ============================================================

st.divider()
st.subheader(" Satellite Catalog")

catalog_table = pd.DataFrame(
    [
        {
            "Satellite": satellite["name"],
            "NORAD ID": satellite["norad_id"],
            "Indian Asset": "YES" if satellite["is_indian_asset"] else "NO",
            "Asset Type": satellite["asset_type"],
        }
        for satellite in satellites
    ]
)

st.dataframe(
    catalog_table,
    width="stretch",
    hide_index=True,
)

# ============================================================
# FOOTER
# ============================================================

st.caption("Decorative background footage: user-provided monochrome galaxy video. The footage is visual ambience only; OrbitGuard telemetry is calculated independently from TLE and SGP4 data.")

st.divider()

footer1, footer2 = st.columns(2)

with footer1:
    st.caption(
        " OrbitGuard AI — Explainable Collision-Risk Intelligence for Satellites"
    )

with footer2:
    st.caption(
        "SGP4 • TLE • Pairwise screening • TCA • Mission Intelligence • Data quality • TLE provenance • Audit trail"
    )
