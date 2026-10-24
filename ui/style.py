"""Colours and small display helpers shared by the UI."""

import streamlit as st

from teaching.palette import (ACCENT, AREA_LABELS, EVENT_SHADE, FIX_COLOR,  # noqa: F401
                              GREEN_PATH, HEALTHY, LAND, MUTED, OVERVIEW_PLACES, PLACES,
                              RED_PATH, SHIP_TRACK, STATE_COLORS, TRUTH)


def how_to_read(text: str, where=st) -> None:
    """One-line plain-language reading guide under a chart or number."""
    where.caption(f"**How to read this:** {text}")


def fmt_latlon(lat: float, lon: float) -> str:
    return f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
