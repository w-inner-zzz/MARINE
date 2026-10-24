"""Section 1: what the receiver reports (the input), before any decision."""

import math
from typing import List, Optional

import plotly.graph_objects as go
import streamlit as st

from sim.runner import Row, Run
from sim.world import TRACKING_THRESHOLD_DBHZ

from teaching.captions import CAPTIONS

from .style import ACCENT, HEALTHY, MUTED, fmt_latlon, how_to_read

NORMAL_CN0_BAND = (35.0, 50.0)
HISTORY_S = 300


def _layout(fig: go.Figure, title: str, height: int = 280) -> go.Figure:
    fig.update_layout(height=height, title=dict(text=title, font=dict(size=14)),
                      margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.25))
    return fig


# ------------------------------------------------------------- snapshot


def satellite_table(row: Row) -> None:
    sats = row.epoch.satellites
    if not sats:
        st.info("The receiver reports no satellites at all this second.")
        return
    st.dataframe(
        [{"Satellite": s.id, "Azimuth (°)": round(s.azimuth_deg), "Elevation (°)":
          round(s.elevation_deg), "C/N0 (dB-Hz)": round(s.cn0_dbhz, 1),
          "Tracked": "yes" if s.tracked else "no"} for s in sats],
        hide_index=True, width="stretch", height=250,
    )
    how_to_read(CAPTIONS["satellite_table"])


def sky_plot(row: Row, normal: Optional[Row]) -> go.Figure:
    fig = go.Figure()
    if normal is not None:
        fig.add_trace(go.Scatterpolar(
            r=[90 - s.elevation_deg for s in normal.epoch.satellites],
            theta=[s.azimuth_deg for s in normal.epoch.satellites],
            mode="markers", name="healthy receiver",
            marker=dict(size=14, color="rgba(0,0,0,0)", line=dict(width=2, color=HEALTHY))))
    sats = row.epoch.satellites
    fig.add_trace(go.Scatterpolar(
        r=[90 - s.elevation_deg for s in sats], theta=[s.azimuth_deg for s in sats],
        mode="markers+text", text=[str(s.id) for s in sats], textposition="top center",
        name="this second",
        marker=dict(size=11, color=[ACCENT if s.tracked else MUTED for s in sats],
                    line=dict(width=2, color="white")),
        hovertemplate="Satellite %{text}<br>azimuth %{theta:.0f}°<extra></extra>"))
    fig.update_polars(
        radialaxis=dict(range=[0, 90], tickvals=[0, 30, 60, 90], ticktext=["90°", "60°", "30°", "0°"],
                        angle=225, tickangle=0, tickfont=dict(size=9)),
        angularaxis=dict(direction="clockwise", rotation=90, tickvals=[0, 90, 180, 270],
                         ticktext=["N", "E", "S", "W"]))
    return _layout(fig, "Sky plot: where the signals come from", 320)


def cn0_bars(row: Row, normal: Optional[Row]) -> go.Figure:
    sats = row.epoch.satellites
    fig = go.Figure()
    fig.add_hrect(y0=NORMAL_CN0_BAND[0], y1=NORMAL_CN0_BAND[1], fillcolor="#008300",
                  opacity=0.10, line_width=0)
    fig.add_trace(go.Bar(
        x=[str(s.id) for s in sats], y=[s.cn0_dbhz for s in sats], name="this second",
        marker=dict(color=[ACCENT if s.tracked else MUTED for s in sats], cornerradius=4),
        hovertemplate="Satellite %{x}: %{y:.1f} dB-Hz<extra></extra>"))
    if normal is not None:
        fig.add_trace(go.Scatter(
            x=[str(s.id) for s in normal.epoch.satellites],
            y=[s.cn0_dbhz for s in normal.epoch.satellites], mode="markers",
            name="healthy receiver",
            marker=dict(symbol="line-ew", size=26, line=dict(width=3, color=HEALTHY))))
    fig.add_hline(y=TRACKING_THRESHOLD_DBHZ, line_dash="dash", line_color=MUTED,
                  annotation_text="tracking threshold 28", annotation_position="bottom right")
    fig.add_annotation(text="normal band 35-50", xref="paper", x=0, y=NORMAL_CN0_BAND[1],
                       yanchor="bottom", showarrow=False, font=dict(size=11))
    fig.update_yaxes(range=[0, 60], title="C/N0 (dB-Hz)")
    fig.update_xaxes(title="satellite", type="category")
    return _layout(fig, "Signal strength (C/N0) per satellite", 320)


def numbers(row: Row, normal: Optional[Row]) -> None:
    res = row.result
    epoch = row.epoch
    c1, c2, c3, c4, c5 = st.columns(5)

    rise = epoch.agc_db - res.baseline_agc_db
    c1.metric("Noise floor", f"{epoch.agc_db:.1f} dB",
              delta=f"{rise:+.1f} dB vs learned normal {res.baseline_agc_db:.1f}",
              delta_color="inverse")
    how_to_read(CAPTIONS["noise_floor"], c1)

    count = res.satellite_count
    verdict = "enough" if count >= 5 else ("position only, no cross-check" if count >= 4
                                           else "no position")
    c2.metric("Satellites tracked", count, delta=f"need 4 for a fix, 5 to check: {verdict}",
              delta_color="off")
    how_to_read(CAPTIONS["satellite_count"], c2)

    hdop = res.hdop
    hdop_text = "none" if hdop is None or not math.isfinite(hdop) else f"{hdop:.1f}"
    quality = ("-" if hdop_text == "none" else "good" if hdop < 2 else
               "poor" if hdop > 5 else "fair")
    c3.metric("HDOP", hdop_text, delta=quality, delta_color="off")
    how_to_read(CAPTIONS["hdop"], c3)

    clock = epoch.gnss_time_error_s
    c4.metric("GNSS time error", "-" if clock is None else f"{clock * 1000:.1f} ms",
              delta=None if clock is None else
              f"{(clock - res.baseline_clock_s) * 1000:+.1f} ms vs normal", delta_color="off")
    how_to_read(CAPTIONS["time_error"], c4)

    if res.gnss_lat_deg is None:
        c5.metric("GNSS position", "none")
    else:
        c5.metric("GNSS position", f"{res.gnss_lat_deg:.4f}° N",
                  delta=f"{res.gnss_lon_deg:.4f}° E", delta_color="off")
    how_to_read(CAPTIONS["gnss_position"], c5)

    if normal is not None:
        st.caption(f"Healthy receiver at the same second: noise floor "
                   f"{normal.epoch.agc_db:.1f} dB, {normal.result.satellite_count} satellites, "
                   f"HDOP {normal.result.hdop:.1f}, GNSS {fmt_latlon(*normal.gnss_latlon)}.")


# --------------------------------------------------------- time series


def _window(run: Run, t: int) -> List[Row]:
    return list(run.rows[max(0, t - HISTORY_S):t + 1])


def cn0_history(rows: List[Row], normal_rows: Optional[List[Row]]) -> go.Figure:
    fig = go.Figure()
    ids = sorted({s.id for r in rows for s in r.epoch.satellites})
    times = [r.t for r in rows]
    for sat_id in ids:
        values = []
        for r in rows:
            match = [s.cn0_dbhz for s in r.epoch.satellites if s.id == sat_id]
            values.append(match[0] if match else None)
        fig.add_trace(go.Scatter(x=times, y=values, mode="lines", name=f"sat {sat_id}",
                                 line=dict(width=1, color=ACCENT), opacity=0.35,
                                 showlegend=False,
                                 hovertemplate=f"sat {sat_id}: %{{y:.1f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=times, y=[_mean_cn0(r) for r in rows], name="mean (tracked)",
                             line=dict(width=3, color=ACCENT)))
    if normal_rows:
        fig.add_trace(go.Scatter(x=[r.t for r in normal_rows],
                                 y=[_mean_cn0(r) for r in normal_rows],
                                 name="healthy mean", line=dict(width=2, dash="dash", color=HEALTHY)))
    fig.add_hline(y=TRACKING_THRESHOLD_DBHZ, line_dash="dot", line_color=MUTED)
    fig.update_yaxes(range=[0, 60], title="dB-Hz")
    return _layout(fig, "C/N0 of every satellite, last 5 minutes")


def _mean_cn0(row: Row) -> Optional[float]:
    values = [s.cn0_dbhz for s in row.epoch.tracked]
    return sum(values) / len(values) if values else None


def noise_history(rows: List[Row], normal_rows: Optional[List[Row]]) -> go.Figure:
    times = [r.t for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=[r.epoch.agc_db for r in rows], name="noise floor",
                             line=dict(width=2, color=ACCENT)))
    fig.add_trace(go.Scatter(x=times, y=[r.result.baseline_agc_db for r in rows],
                             name="learned normal", line=dict(width=1, color=MUTED)))
    fig.add_trace(go.Scatter(x=times, y=[r.result.baseline_agc_db + 3 for r in rows],
                             name="alarm (+3 dB)", line=dict(width=1, dash="dash", color="#e34948")))
    if normal_rows:
        fig.add_trace(go.Scatter(x=[r.t for r in normal_rows],
                                 y=[r.epoch.agc_db for r in normal_rows], name="healthy",
                                 line=dict(width=2, dash="dash", color=HEALTHY)))
    fig.update_yaxes(title="dB")
    return _layout(fig, "Noise floor, last 5 minutes")


def count_history(rows: List[Row], normal_rows: Optional[List[Row]]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[r.t for r in rows], y=[r.result.satellite_count for r in rows],
                             name="tracked", line=dict(width=2, color=ACCENT, shape="hv")))
    if normal_rows:
        fig.add_trace(go.Scatter(x=[r.t for r in normal_rows],
                                 y=[r.result.satellite_count for r in normal_rows],
                                 name="healthy", line=dict(width=2, dash="dash", color=HEALTHY,
                                                           shape="hv")))
    fig.add_hline(y=4, line_dash="dot", line_color=MUTED, annotation_text="4 = fix",
                  annotation_position="bottom left")
    fig.add_hline(y=5, line_dash="dash", line_color="#008300", annotation_text="5 = checkable",
                  annotation_position="top left")
    fig.update_yaxes(range=[0, 13], title="satellites")
    return _layout(fig, "Satellites tracked, last 5 minutes")


def jumps(rows: List[Row]) -> List[Optional[float]]:
    """Distance between consecutive GNSS positions (m per second)."""
    result, previous = [], None
    for r in rows:
        pos = r.gnss_position
        if pos is None or previous is None:
            result.append(None)
        else:
            result.append(math.hypot(pos[0] - previous[0], pos[1] - previous[1]))
        previous = pos
    return result


def jump_history(rows: List[Row], normal_rows: Optional[List[Row]]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[r.t for r in rows], y=jumps(rows), name="GNSS jump",
                             mode="lines", line=dict(width=2, color=ACCENT)))
    if normal_rows:
        fig.add_trace(go.Scatter(x=[r.t for r in normal_rows], y=jumps(normal_rows),
                                 name="healthy", line=dict(width=2, dash="dash", color=HEALTHY)))
    speed = rows[-1].sensors.speed_through_water_mps
    fig.add_hline(y=speed, line_dash="dot", line_color=MUTED,
                  annotation_text=f"ship speed ≈ {speed:.1f} m/s")
    fig.update_yaxes(title="metres per second", rangemode="tozero")
    return _layout(fig, "GNSS position jump per second, last 5 minutes")


# --------------------------------------------------------------- section


def render_inspector(run: Run, normal_run: Optional[Run], t: int) -> None:
    row = run.rows[t]
    normal = normal_run.rows[t] if normal_run is not None else None

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(sky_plot(row, normal), width="stretch")
        how_to_read(CAPTIONS["sky"])
    with c2:
        st.plotly_chart(cn0_bars(row, normal), width="stretch")
        how_to_read(CAPTIONS["cn0_bars"])

    satellite_table(row)
    numbers(row, normal)

    st.markdown("**The last 5 minutes**")
    rows = _window(run, t)
    normal_rows = _window(normal_run, t) if normal_run is not None else None
    h1, h2 = st.columns(2)
    with h1:
        st.plotly_chart(cn0_history(rows, normal_rows), width="stretch")
        how_to_read(CAPTIONS["cn0_history"])
        st.plotly_chart(count_history(rows, normal_rows), width="stretch")
        how_to_read(CAPTIONS["count_history"])
    with h2:
        st.plotly_chart(noise_history(rows, normal_rows), width="stretch")
        how_to_read(CAPTIONS["noise_history"])
        st.plotly_chart(jump_history(rows, normal_rows), width="stretch")
        how_to_read(CAPTIONS["jump_history"])
