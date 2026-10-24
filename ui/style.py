"""Colours and small display helpers shared by the UI."""

import streamlit as st

from marine_guard import State

STATE_COLORS = {
    State.TRUSTED: "#008300",
    State.DEGRADED: "#eda100",
    State.RECOVERING: "#2a78d6",
    State.LOST: "#eb6834",
    State.JAMMING: "#e34948",
    State.SPOOFING: "#6250d6",
}
RED_PATH = "#e34948"
GREEN_PATH = "#008300"
TRUTH = "#8a8986"
SHIP_TRACK = "#2a78d6"
HEALTHY = "#8a8986"
MUTED = "#a3a29c"
ACCENT = "#2a78d6"
FIX_COLOR = "#1baf7a"
LAND = "#d9cba3"
EVENT_SHADE = "rgba(150, 150, 150, 0.18)"

# (name, lat, lon, label position)
PLACES = (
    ("Helsinki", 60.1699, 24.9384, "top center"),
    ("Tallinn", 59.4370, 24.7536, "bottom center"),
    ("Kotka", 60.4664, 26.9458, "middle right"),
    ("Hamina", 60.5697, 27.1981, "top right"),
    ("Stockholm", 59.3293, 18.0686, "middle left"),
    ("Gdańsk", 54.3520, 18.6466, "bottom center"),
)
OVERVIEW_PLACES = tuple(p for p in PLACES if p[0] != "Hamina")
# (name, lat, lon, arrow dx, arrow dy in pixels; 0, 0 = no arrow)
AREA_LABELS = (
    ("Gulf of Finland", 59.85, 26.0, 40, 45),
    ("Gotland", 57.45, 18.55, 0, 0),
    ("Baltic Sea", 56.2, 19.6, 0, 0),
)


def how_to_read(text: str, where=st) -> None:
    """One-line plain-language reading guide under a chart or number."""
    where.caption(f"**How to read this:** {text}")


def fmt_latlon(lat: float, lon: float) -> str:
    return f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
