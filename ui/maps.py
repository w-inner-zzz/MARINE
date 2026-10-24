"""Maps on latitude/longitude axes, drawn from the real land mask and the
depth chart (no internet map tiles needed).

Red path: what GNSS reported while it was not trusted (what a GNSS-following
autopilot would have believed). Green path: the guard's backup track.
Grey dotted: ground truth, visible only in the simulation.
"""

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np
import plotly.graph_objects as go

from sim.analysis import Danger, Detection, downsample, not_trusted
from sim.runner import Row, Run

from .style import (AREA_LABELS, FIX_COLOR, GREEN_PATH, LAND, OVERVIEW_PLACES, PLACES, RED_PATH,
                    SHIP_TRACK, STATE_COLORS, TRUTH, fmt_latlon)

SEA_SCALE = [[0.0, "#d6eaf8"], [1.0, "#1b4f72"]]


def _equal_distance_axes(fig: go.Figure, lat: float, lat_range, lon_range, height: int) -> None:
    """Latitude/longitude axes where 1 km looks the same in both directions."""
    fig.update_xaxes(range=list(lon_range), title="longitude (° E)", showgrid=True,
                     constrain="domain")
    fig.update_yaxes(range=list(lat_range), title="latitude (° N)", showgrid=True,
                     scaleanchor="x", scaleratio=1 / math.cos(math.radians(lat)),
                     constrain="domain")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.12), plot_bgcolor="#d6eaf8")


def _land_layer(lats, lons, land) -> go.Heatmap:
    z = np.where(land, 1.0, np.nan)
    return go.Heatmap(x=lons, y=lats, z=z, colorscale=[[0, LAND], [1, LAND]],
                      showscale=False, hoverinfo="skip", name="land")


def _labels(fig: go.Figure, lat_range, lon_range, areas: bool, places=PLACES) -> None:
    def inside(lat, lon):
        return lat_range[0] <= lat <= lat_range[1] and lon_range[0] <= lon <= lon_range[1]

    places = [p for p in places if inside(p[1], p[2])]
    if places:
        fig.add_trace(go.Scatter(
            x=[p[2] for p in places], y=[p[1] for p in places], mode="markers+text",
            text=[p[0] for p in places], textposition=[p[3] for p in places], name="places",
            marker=dict(size=7, color="#333333"), showlegend=False, hoverinfo="text"))
    if areas:
        for name, lat, lon, ax, ay in AREA_LABELS:
            if inside(lat, lon):
                fig.add_annotation(x=lon, y=lat, text=f"<i>{name}</i>", showarrow=bool(ax or ay),
                                   ax=ax, ay=ay, arrowcolor="#1b4f72",
                                   font=dict(color="#1b4f72", size=12))


def _path(rows: Sequence[Row], pick, keep) -> Tuple[List, List]:
    """Lon/lat lists of the rows where keep(row), with gaps between segments."""
    lats, lons = [], []
    for r in rows:
        point = pick(r) if keep(r) else None
        if point is None:
            if lats and lats[-1] is not None:
                lats.append(None)
                lons.append(None)
            continue
        lats.append(point[0])
        lons.append(point[1])
    return lons, lats


def _circle(run: Run, row: Row) -> Tuple[List[float], List[float]]:
    x, y = row.result.position
    r = row.result.uncertainty_m
    points = [run.frame.to_latlon(x + r * math.cos(a), y + r * math.sin(a))
              for a in np.linspace(0, 2 * math.pi, 60)]
    return [p[1] for p in points], [p[0] for p in points]


def _note(fig: go.Figure, lat: float, lon: float, text: str, color: str, ax: int, ay: int) -> None:
    """A boxed label with a short arrow, readable over land and sea."""
    fig.add_annotation(x=lon, y=lat, text=text, ax=ax, ay=ay, showarrow=True,
                       arrowcolor=color, font=dict(size=11, color=color),
                       bgcolor="rgba(255,255,255,0.88)", bordercolor=color, borderpad=3)


def _ship(fig: go.Figure, row: Row) -> None:
    lat, lon = row.guard_latlon
    color = STATE_COLORS[row.result.state]
    fig.add_trace(go.Scatter(
        x=[lon], y=[lat], mode="markers", name="ship (guard position)",
        marker=dict(symbol="arrow", size=22, angle=row.sensors.heading_deg, color=color,
                    line=dict(width=1, color="white"))))
    _note(fig, lat, lon, f"ship {fmt_latlon(lat, lon)}", "#222222", 60, 35)


def _tracks(fig: go.Figure, run: Run, rows: Sequence[Row]) -> None:
    lons, lats = _path(rows, lambda r: r.true_latlon, lambda r: True)
    fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", name="ground truth "
                             "(visible only in the simulation)",
                             line=dict(color=TRUTH, width=1.5, dash="dot")))
    lons, lats = _path(rows, lambda r: r.guard_latlon, lambda r: not not_trusted(r))
    fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", name="ship track (GNSS trusted)",
                             line=dict(color=SHIP_TRACK, width=2.5)))
    lons, lats = _path(rows, lambda r: r.gnss_latlon, not_trusted)
    if any(v is not None for v in lats):
        fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", name="RED: what GNSS reported "
                                 "(where a GNSS autopilot would think it is)",
                                 line=dict(color=RED_PATH, width=2.5)))
    lons, lats = _path(rows, lambda r: r.guard_latlon, not_trusted)
    if any(v is not None for v in lats):
        fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", name="GREEN: guard backup "
                                 "track (dead reckoning + radar + depth)",
                                 line=dict(color=GREEN_PATH, width=2.5)))
    for kind, symbol in (("radar", "triangle-down"), ("depth", "diamond")):
        fixes = [r for r in rows if kind in r.result.fixes]
        if fixes:
            fig.add_trace(go.Scatter(
                x=[r.guard_latlon[1] for r in fixes], y=[r.guard_latlon[0] for r in fixes],
                mode="markers", name=f"{kind} fix applied",
                marker=dict(symbol=symbol, size=8, color=FIX_COLOR,
                            line=dict(width=1, color="white"))))


def _events(fig: go.Figure, detections: Sequence[Detection], danger: Optional[Danger],
            t: float) -> None:
    shown = [d for d in detections if d.t <= t]
    if shown:
        fig.add_trace(go.Scatter(
            x=[d.latlon[1] for d in shown], y=[d.latlon[0] for d in shown],
            mode="markers", name="detection",
            marker=dict(symbol="star", size=14, color=[STATE_COLORS[d.state] for d in shown],
                        line=dict(width=1, color="white"))))
        for i, d in enumerate(shown[-3:]):
            _note(fig, d.latlon[0], d.latlon[1], f"⚑ {d.state.value} at {d.t:.0f} s: {d.reason}",
                  STATE_COLORS[d.state], -40, -40 - 28 * i)
    if danger is not None and danger.t <= t:
        fig.add_trace(go.Scatter(
            x=[danger.latlon[1]], y=[danger.latlon[0]], mode="markers",
            name="grounding risk if GNSS had been trusted",
            marker=dict(symbol="x", size=16, color=RED_PATH, line=dict(width=2))))
        _note(fig, danger.latlon[0], danger.latlon[1],
              f"⚠ grounding risk if GNSS had been trusted ({danger.what})", RED_PATH, 0, 40)


def _bounds(points: List[Tuple[float, float]], margin_deg: float, min_span_deg: float,
            width_to_height: float = 1.8):
    """A view around the points, widened to roughly the shape of the plot."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    lat_c, lon_c = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
    shrink = math.cos(math.radians(lat_c))  # a degree of longitude is shorter
    lat_half = max((max(lats) - min(lats)) / 2 + margin_deg, min_span_deg / 2)
    lon_half = max((max(lons) - min(lons)) / 2 + margin_deg / shrink, min_span_deg)
    lon_half = max(lon_half, lat_half * width_to_height / shrink)
    lat_half = max(lat_half, lon_half * shrink / width_to_height)
    return (lat_c - lat_half, lat_c + lat_half), (lon_c - lon_half, lon_c + lon_half)


def _chart_background(fig: go.Figure, run: Run, lat_range, lon_range) -> None:
    chart = run.chart
    if not hasattr(chart, "grid"):
        return
    grid = chart.grid
    lats, lons = grid.cell_centres()
    r = (lats >= lat_range[0] - 0.01) & (lats <= lat_range[1] + 0.01)
    c = (lons >= lon_range[0] - 0.01) & (lons <= lon_range[1] + 0.01)
    if not r.any() or not c.any():
        return
    step = max(1, int(max(r.sum(), c.sum()) / 250))
    sub_lats, sub_lons = lats[r][::step], lons[c][::step]
    depth = grid.depth[np.ix_(r, c)][::step, ::step]
    land = chart.land[np.ix_(r, c)][::step, ::step]
    label = "SYNTHETIC depth (m)" if grid.synthetic else "depth (m), EMODnet"
    fig.add_trace(go.Heatmap(
        x=sub_lons, y=sub_lats, z=np.where(land, np.nan, depth), colorscale=SEA_SCALE,
        zmin=0, zmax=100, name="depth chart", colorbar=dict(title=label, len=0.6),
        hovertemplate="depth %{z:.0f} m<extra></extra>"))
    fig.add_trace(_land_layer(sub_lats, sub_lons, land))


def route_map(run: Run, t: int, detections, danger, every: int) -> go.Figure:
    rows = downsample(run.rows[:t + 1], every)
    now = run.rows[t]
    fig = go.Figure()
    drawn = [r.true_latlon for r in rows] + [r.guard_latlon for r in rows]
    drawn += [r.gnss_latlon for r in rows if not_trusted(r) and r.gnss_latlon]
    lat_range, lon_range = _bounds(drawn, margin_deg=0.03, min_span_deg=0.08)
    _chart_background(fig, run, lat_range, lon_range)
    _tracks(fig, run, rows)
    lons, lats = _circle(run, now)
    fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", fill="toself", name="uncertainty",
                             line=dict(color=GREEN_PATH, width=1), fillcolor="rgba(0,131,0,0.2)",
                             showlegend=False))
    _events(fig, detections, danger, now.t)
    _ship(fig, now)
    _labels(fig, lat_range, lon_range, areas=False)
    _equal_distance_axes(fig, now.true_latlon[0], lat_range, lon_range, 560)
    fig.update_layout(title=dict(text="Route map (zoomed)", font=dict(size=14)))
    return fig


def closeup_map(run: Run, t: int, detections, danger) -> go.Figure:
    """A few kilometres around the ship, where the uncertainty circle is visible."""
    rows = list(run.rows[max(0, t - 600):t + 1])
    now = run.rows[t]
    fig = go.Figure()
    half_m = max(800.0, 3 * now.result.uncertainty_m)
    lat, lon = now.guard_latlon
    dlat = math.degrees(half_m / 6371000.0)
    dlon = dlat / math.cos(math.radians(lat))
    lat_range, lon_range = (lat - dlat * 0.7, lat + dlat * 0.7), (lon - dlon, lon + dlon)
    _tracks(fig, run, rows)
    lons, lats = _circle(run, now)
    fig.add_trace(go.Scatter(x=lons, y=lats, mode="lines", fill="toself",
                             name=f"uncertainty ±{now.result.uncertainty_m:.0f} m",
                             line=dict(color=GREEN_PATH, width=1),
                             fillcolor="rgba(0,131,0,0.2)"))
    _events(fig, detections, danger, now.t)
    _ship(fig, now)
    _equal_distance_axes(fig, lat, lat_range, lon_range, 420)
    fig.update_layout(title=dict(text=f"Close-up: ±{half_m / 1000:.1f} km around the ship",
                                 font=dict(size=14)), showlegend=False)
    return fig


def overview_map(run: Run, t: int) -> go.Figure:
    from sim.baltic import overview_land  # loads the land mask

    lats, lons, land = overview_land()
    now = run.rows[t]
    fig = go.Figure()
    fig.add_trace(_land_layer(lats, lons, land))
    route = downsample(run.rows, 300)
    fig.add_trace(go.Scatter(x=[r.true_latlon[1] for r in route],
                             y=[r.true_latlon[0] for r in route], mode="lines",
                             name="voyage", line=dict(color=SHIP_TRACK, width=3)))
    fig.add_trace(go.Scatter(x=[now.true_latlon[1]], y=[now.true_latlon[0]], mode="markers",
                             name="ship", marker=dict(size=10, color=STATE_COLORS[now.result.state],
                                                      line=dict(width=1, color="white"))))
    lat_range, lon_range = (53.5, 66.0), (9.0, 31.0)
    _labels(fig, lat_range, lon_range, areas=True, places=OVERVIEW_PLACES)
    _equal_distance_axes(fig, 59.0, lat_range, lon_range, 420)
    fig.update_layout(title=dict(text="Overview: the Baltic Sea", font=dict(size=14)),
                      showlegend=False)
    return fig
