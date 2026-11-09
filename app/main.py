import os
import sys
import math
import time
import json
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
    page_icon="🛰️",
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
# LIGHT UI POLISH
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        [data-testid="stMetric"] {
            background: rgba(25, 29, 38, 0.75);
            border: 1px solid rgba(120, 130, 150, 0.18);
            border-radius: 12px;
            padding: 12px 14px;
        }

        .orbitguard-card {
            background: linear-gradient(
                135deg,
                rgba(24, 29, 40, 0.95),
                rgba(15, 18, 26, 0.95)
            );
            border: 1px solid rgba(120, 130, 150, 0.18);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 10px;
        }

        .orbitguard-label {
            color: #9aa4b2;
            font-size: 0.82rem;
            margin-bottom: 4px;
        }

        .orbitguard-value {
            color: #f4f7fb;
            font-size: 1.45rem;
            font-weight: 700;
        }

        .orbitguard-muted {
            color: #8e98a8;
            font-size: 0.82rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HEADER
# ============================================================

header_left, header_right = st.columns([4, 1])

with header_left:
    st.title("🛰️ ORBITGUARD AI")
    st.caption(
        "Explainable Space Situational Awareness & Conjunction Screening"
    )
    st.markdown(
        """
        **Detect. Analyze. Explain. Protect.**

        OrbitGuard AI screens satellite pairs using TLE data,
        SGP4 orbital propagation, geometric separation analysis,
        and transparent mission-context intelligence.

        **Data-driven screening • Explainable attention scoring • Reproducible analysis**
        """
    )

with header_right:
    st.markdown(
        """
        <div class="orbitguard-card">
            <div class="orbitguard-label">SYSTEM MODE</div>
            <div class="orbitguard-value">SCREENING</div>
            <div class="orbitguard-muted">TLE + SGP4 + pairwise analysis</div>
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
def load_satellite_catalog():
    return download_satellites(
        targets_path=os.path.join(
            PROJECT_ROOT,
            "data",
            "targets.txt",
        )
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
        "FRESH": "🟢 FRESH",
        "CACHED": "🟡 CACHED",
        "UNAVAILABLE": "🔴 UNAVAILABLE",
        "UNKNOWN": "⚪ UNKNOWN",
    }
    return labels.get(status, f"⚪ {status}")


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown("## ⚙️ OrbitGuard Controls")

try:
    satellites = load_satellite_catalog()
except Exception as error:
    st.error(f"Unable to load satellite data: {error}")
    st.stop()

satellites = enrich_satellite_catalog(satellites)

source_counts = source_status_counts(satellites)

st.sidebar.markdown("### 📡 TLE Source Status")

if source_counts["UNAVAILABLE"] > 0:
    st.sidebar.error(
        f"{source_counts['UNAVAILABLE']} TLE record(s) unavailable"
    )
elif source_counts["CACHED"] > 0:
    st.sidebar.warning(
        f"{source_counts['CACHED']} TLE record(s) using cache"
    )
else:
    st.sidebar.success(
        f"{source_counts['FRESH']} TLE record(s) freshly loaded"
    )

st.sidebar.caption(
    "FRESH = source download succeeded • "
    "CACHED = source unavailable, local TLE reused"
)

satellite_names = [satellite["name"] for satellite in satellites]

selected_satellites = st.sidebar.multiselect(
    "🛰️ Satellites",
    satellite_names,
    default=satellite_names,
)

view_mode = st.sidebar.selectbox(
    "🌍 3D View Mode",
    [
        "Earth Focus (LEO)",
        "Full Orbital Context",
        "GEO Focus",
    ],
    index=0,
)

trajectory_duration = st.sidebar.slider(
    "🕐 Trajectory Duration (hours)",
    min_value=1,
    max_value=24,
    value=6,
)

indian_only = st.sidebar.checkbox(
    "🇮🇳 Indian Asset Watchlist",
    value=False,
    help="Filter the selected satellite list to assets identified by the OrbitGuard Indian satellite catalog.",
)

st.sidebar.divider()

if st.sidebar.button("🔄 Refresh TLE Data", use_container_width=True):
    load_satellite_catalog.clear()
    st.rerun()

st.sidebar.caption(
    "TLE cache refreshes every 15 minutes during normal use."
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
    "🎯 Focus Satellite",
    focus_options,
    index=0,
    key="orbitguard_focus_satellite",
    help="Select a currently visible satellite to emphasize its orbit and marker.",
)

# ============================================================
# 3D ORBITAL ENVIRONMENT
# ============================================================


st.subheader("🌍 3D Orbital Environment")

viz1, viz2, viz3 = st.columns(3)

with viz1:
    animation_enabled = st.checkbox(
        "▶ Enable orbital animation",
        value=True,
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
            width=512,
            height=256,
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
            f"🎯 {position['name']} spacecraft"
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
                    f"🎯 {satellite['name']} orbit"
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

current_positions = propagate_visualization_positions(
    visible_satellites,
    calculation_time,
)

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
                        label="▶ Play",
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
                        label="⏸ Pause",
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

st.subheader("📍 Current Satellite Positions")

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
st.subheader("🔎 Conjunction Risk Analysis")

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

screening_start = datetime.now(timezone.utc)
screening_wall_start = time.perf_counter()

# Reliability state: these values are always defined, even if screening
# encounters an exception.
screening_runtime_seconds = 0.0
screening_error = None
screening_results = []

selected_count = len(selected_objects)
propagated_count = len(propagation_ok_names.intersection(
    satellite["name"] for satellite in selected_objects
))

expected_pairs = propagated_count * (propagated_count - 1) // 2

with st.spinner("Running pairwise conjunction screening..."):
    try:
        screening_results = screen_all_pairs(
            selected_objects,
            start_time=screening_start,
            minutes=screening_minutes,
            step_seconds=screening_step,
        )
    except Exception as error:
        screening_error = str(error)

screening_runtime_seconds = time.perf_counter() - screening_wall_start

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

screening_end = datetime.now(timezone.utc)

audit_record = {
    "screening_id": screening_start.strftime("%Y%m%dT%H%M%S%fZ"),
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
        pd.Series(
            [
                record["tle_status"]
                for record in [
                    build_satellite_health(
                        satellite,
                        satellite["name"] in propagation_ok_names,
                        calculation_time,
                    )
                    for satellite in selected_objects
                ]
            ]
        ).value_counts().to_dict()
        if selected_objects
        else {}
    ),
    "screening_error": screening_error,
}

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

st.markdown("### 🛡️ Screening Integrity")

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

st.subheader("📋 Pair Screening Results")

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
    st.subheader("🎯 Selected Conjunction Event")

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

    st.subheader("📈 Distance vs Time — Closest Approach")

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

    st.subheader("⏱️ Time of Closest Approach")

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

    st.subheader("🧠 Explainable Screening Result")

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

    st.subheader("🧠 Mission Intelligence")

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

    st.subheader("🇮🇳 Mission Context")

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
st.subheader("🇮🇳 Indian Satellite Watchlist")

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
st.subheader("🩺 Data Quality & System Health")

health_records = [
    build_satellite_health(
        satellite,
        satellite["name"] in propagation_ok_names,
        calculation_time,
    )
    for satellite in selected_objects
]

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
st.subheader("📡 TLE Source Provenance")

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
st.subheader("🧾 Screening Audit Trail")

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
st.subheader("🛰️ Satellite Catalog")

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

st.divider()

footer1, footer2 = st.columns(2)

with footer1:
    st.caption(
        "🛰️ OrbitGuard AI — Explainable Collision-Risk Intelligence for Satellites"
    )

with footer2:
    st.caption(
        "SGP4 • TLE • Pairwise screening • TCA • Mission Intelligence • Data quality • TLE provenance • Audit trail"
    )
