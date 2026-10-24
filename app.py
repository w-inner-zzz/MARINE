"""Streamlit viewer for the GNSS trust monitor. Run: streamlit run app.py"""

import math
import time
from typing import List, Optional

import plotly.graph_objects as go
import streamlit as st

from marine_guard import GuardResult, State
from sim.runner import Run, Row, run_scenario, summarize
from sim.scenarios import SCENARIOS
from sim.world import KNOT_MPS, TRACKING_THRESHOLD_DBHZ

STATE_COLORS = {
    State.TRUSTED: "#008300",
    State.DEGRADED: "#eda100",
    State.RECOVERING: "#2a78d6",
    State.LOST: "#eb6834",
    State.JAMMING: "#e34948",
    State.SPOOFING: "#6250d6",
}
TRUE_COLOR = "#52514e"
GNSS_COLOR = "#e87ba4"
GUARD_COLOR = "#2a78d6"
FIX_COLOR = "#1baf7a"
MUTED = "#a3a29c"
EVENT_SHADE = "rgba(150, 150, 150, 0.18)"

NORMAL_CN0_BAND = (35.0, 50.0)
FOLLOW_HALF_WIDTH_M = 500.0


# ------------------------------------------------------------------ data


@st.cache_resource(show_spinner="Simulating scenario...")
def load_run(key: str) -> Run:
    return run_scenario(key)


@st.cache_data(show_spinner="Simulating all scenarios...")
def comparison_rows() -> List[dict]:
    def seconds(value: Optional[float]) -> str:
        return "-" if value is None else f"{value:.0f} s"

    rows = []
    for key, scenario in SCENARIOS.items():
        s = summarize(load_run(key))
        rows.append({
            "Scenario": scenario.title,
            "First detection": seconds(s.detection_s),
            "Back to TRUSTED after event": seconds(s.back_to_trusted_s),
            "Worst error, guard (m)": round(s.worst_guard_error_m, 1),
            "Worst error, naive GNSS (m)": round(s.worst_naive_error_m, 1),
            "Seconds not trusted": s.seconds_not_trusted,
        })
    return rows


# ---------------------------------------------------------------- banner


def what_is_happening(res: GuardResult) -> str:
    a = res.action
    if res.state == State.TRUSTED:
        return f"Satellite position is trusted; the autopilot is on '{a.autopilot_mode}'."
    if res.state == State.RECOVERING:
        return (f"Signals look clean again ({res.clean_seconds}/{res.clean_needed} s); "
                f"still navigating on {a.position_source}.")
    return (f"Navigating on {a.position_source}; autopilot '{a.autopilot_mode}', "
            f"speed {a.recommended_speed_kn.lower()}.")


def why(res: GuardResult) -> str:
    failed = [c for c in res.checks if c.passed is False]
    if not failed:
        return f"All {len(res.checks)} checks pass. {res.reason}"
    names = ", ".join(c.name for c in failed)
    return f"{len(failed)} of {len(res.checks)} checks fail ({names}). {res.reason}"


def render_banner(res: GuardResult) -> None:
    color = STATE_COLORS[res.state]
    st.markdown(
        f"""
        <div style="border-left: 14px solid {color}; padding: 0.6rem 1rem;
                    background: {color}1f; border-radius: 6px; margin-bottom: 0.5rem;">
          <div style="font-size: 1.7rem; font-weight: 700; color: {color};">
            {res.state.value}
            <span style="font-size: 1rem; font-weight: 400; opacity: 0.85;">
              &nbsp;t = {res.timestamp:.0f} s &middot; uncertainty {res.uncertainty_m:.0f} m
            </span>
          </div>
          <div><b>What is happening:</b> {what_is_happening(res)}</div>
          <div><b>Why:</b> {why(res)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- charts


def _compact(fig: go.Figure, height: int, title: str) -> go.Figure:
    fig.update_layout(height=height, title=dict(text=title, font=dict(size=14)),
                      margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
    return fig


def sky_plot(row: Row) -> go.Figure:
    sats = row.epoch.satellites
    fig = go.Figure(go.Scatterpolar(
        r=[90 - s.elevation_deg for s in sats],
        theta=[s.azimuth_deg for s in sats],
        mode="markers+text",
        text=[str(s.id) for s in sats],
        textposition="top center",
        marker=dict(size=12, color=[GUARD_COLOR if s.tracked else MUTED for s in sats],
                    line=dict(width=2, color="white")),
        hovertemplate="Sat %{text}<br>azimuth %{theta:.0f} deg<extra></extra>",
    ))
    fig.update_polars(
        radialaxis=dict(range=[0, 90], tickvals=[0, 30, 60, 90],
                        ticktext=["90", "60", "30", "0"], showticklabels=True),
        angularaxis=dict(direction="clockwise", rotation=90,
                         tickvals=[0, 90, 180, 270], ticktext=["N", "E", "S", "W"]),
    )
    title = "Sky: where signals come from" if sats else "Sky: no satellites"
    return _compact(fig, 300, title)


def cn0_bars(row: Row) -> go.Figure:
    sats = row.epoch.satellites
    fig = go.Figure(go.Bar(
        x=[str(s.id) for s in sats],
        y=[s.cn0_dbhz for s in sats],
        marker=dict(color=[GUARD_COLOR if s.tracked else MUTED for s in sats],
                    cornerradius=4),
        hovertemplate="Sat %{x}: %{y:.1f} dB-Hz<extra></extra>",
    ))
    fig.add_hrect(y0=NORMAL_CN0_BAND[0], y1=NORMAL_CN0_BAND[1], fillcolor=STATE_COLORS[State.TRUSTED],
                  opacity=0.12, line_width=0, annotation_text="normal 35-50",
                  annotation_position="outside top left")
    fig.add_hline(y=TRACKING_THRESHOLD_DBHZ, line_dash="dash", line_color=MUTED,
                  annotation_text="tracking threshold 28", annotation_position="bottom right")
    fig.update_yaxes(range=[0, 60], title="C/N0 (dB-Hz)")
    fig.update_xaxes(title="satellite", type="category")
    return _compact(fig, 300, "Signal strength per satellite")


def noise_gauge(res: GuardResult, row: Row) -> go.Figure:
    check = res.checks[0]  # noise floor check: value = rise above normal
    agc = row.epoch.agc_db
    baseline = agc - check.value
    alarm = baseline + check.threshold
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=agc, number=dict(suffix=" dB"),
        gauge=dict(
            axis=dict(range=[baseline - 5, baseline + 20]),
            bar=dict(color=STATE_COLORS[State.JAMMING] if agc > alarm else GUARD_COLOR),
            steps=[dict(range=[baseline - 5, alarm], color="rgba(0,131,0,0.15)")],
            threshold=dict(line=dict(color=STATE_COLORS[State.JAMMING], width=3), value=alarm),
        ),
    ))
    return _compact(fig, 200, f"Noise floor (normal {baseline:.1f}, alarm {alarm:.1f})")


def satellite_count(res: GuardResult) -> go.Figure:
    count = res.satellite_count
    fig = go.Figure(go.Bar(
        x=[count], y=["tracked"], orientation="h",
        marker=dict(color=GUARD_COLOR if count >= 5 else STATE_COLORS[State.LOST], cornerradius=4),
        text=[str(count)], textposition="outside", hoverinfo="skip",
    ))
    fig.add_vline(x=4, line_dash="dot", line_color=MUTED,
                  annotation_text="4 = fix", annotation_position="top left")
    fig.add_vline(x=5, line_dash="dash", line_color=STATE_COLORS[State.TRUSTED],
                  annotation_text="5 = checkable", annotation_position="top right")
    fig.update_xaxes(range=[0, 13], dtick=1)
    return _compact(fig, 200, "Satellites tracked")


def hdop_gauge(res: GuardResult) -> go.Figure:
    value = res.hdop if res.hdop is not None and math.isfinite(res.hdop) else None
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=min(value, 10) if value is not None else 0,
        number=dict(valueformat=".1f", suffix="" if value is not None else " (none)"),
        gauge=dict(
            axis=dict(range=[0, 10]),
            bar=dict(color=GUARD_COLOR),
            steps=[dict(range=[0, 2], color="rgba(0,131,0,0.15)"),
                   dict(range=[5, 10], color="rgba(227,73,72,0.15)")],
        ),
    ))
    title = "HDOP (good < 2, poor > 5)"
    if value is not None and value > 10:
        title += f": {value:.0f}!"
    return _compact(fig, 200, title)


def boat_map(run: Run, upto: int, follow: bool) -> go.Figure:
    rows = run.rows[:upto + 1]
    now = rows[-1]
    res = now.result
    fig = go.Figure()

    # Land north of the coast line.
    fig.add_hrect(y0=run.config.coast_y, y1=run.config.coast_y + 5000,
                  fillcolor="#c9b88f", opacity=0.35, line_width=0)
    fig.add_hline(y=run.config.coast_y, line_color="#8a7a52",
                  annotation_text="coast", annotation_position="bottom left")

    gnss = [r for r in rows if r.gnss_position is not None]
    fig.add_trace(go.Scatter(
        x=[r.gnss_position[0] for r in gnss], y=[r.gnss_position[1] for r in gnss],
        mode="markers", name="GNSS reported", marker=dict(size=4, color=GNSS_COLOR)))
    fig.add_trace(go.Scatter(
        x=[r.true_position[0] for r in rows], y=[r.true_position[1] for r in rows],
        mode="lines", name="true track", line=dict(color=TRUE_COLOR, width=2)))
    fig.add_trace(go.Scatter(
        x=[r.guard_position[0] for r in rows], y=[r.guard_position[1] for r in rows],
        mode="lines", name="guard output", line=dict(color=GUARD_COLOR, width=2, dash="dash")))

    for kind, symbol in (("radar", "triangle-down"), ("depth", "diamond")):
        fixes = [r for r in rows if kind in r.result.fixes]
        if fixes:
            fig.add_trace(go.Scatter(
                x=[r.guard_position[0] for r in fixes], y=[r.guard_position[1] for r in fixes],
                mode="markers", name=f"{kind} fix",
                marker=dict(symbol=symbol, size=9, color=FIX_COLOR,
                            line=dict(width=1, color="white"))))

    # Uncertainty circle around the guard position.
    cx, cy = res.position
    angles = [2 * math.pi * k / 72 for k in range(73)]
    fig.add_trace(go.Scatter(
        x=[cx + res.uncertainty_m * math.cos(a) for a in angles],
        y=[cy + res.uncertainty_m * math.sin(a) for a in angles],
        mode="lines", name=f"uncertainty {res.uncertainty_m:.0f} m", fill="toself",
        line=dict(color=STATE_COLORS[res.state], width=1),
        fillcolor=STATE_COLORS[res.state] + "33"))

    fig.add_trace(go.Scatter(
        x=[cx], y=[cy], mode="markers", name="boat",
        marker=dict(symbol="arrow", size=20, angle=now.sensors.heading_deg,
                    color=STATE_COLORS[res.state], line=dict(width=1, color="white"))))

    if follow:
        fig.update_xaxes(range=[cx - FOLLOW_HALF_WIDTH_M, cx + FOLLOW_HALF_WIDTH_M])
        fig.update_yaxes(range=[cy - FOLLOW_HALF_WIDTH_M * 0.6, cy + FOLLOW_HALF_WIDTH_M * 0.6])
    else:
        fig.update_yaxes(range=[-500, run.config.coast_y + 400])
    fig.update_yaxes(scaleanchor="x", scaleratio=1, title="north (m)")
    fig.update_xaxes(title="east (m)")
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=40, b=10),
                      title=dict(text="Map", font=dict(size=14)),
                      legend=dict(orientation="h", y=-0.15))
    return fig


def error_chart(run: Run, t: float) -> go.Figure:
    rows = run.rows
    times = [r.t for r in rows]
    fig = go.Figure()
    sc = run.scenario
    if sc.event_start is not None:
        fig.add_vrect(x0=sc.event_start, x1=sc.event_end, fillcolor=EVENT_SHADE,
                      line_width=0, annotation_text="event", annotation_position="top left")
    fig.add_trace(go.Scatter(x=times, y=[max(r.naive_error, 0.1) for r in rows],
                             name="naive GNSS", line=dict(color=GNSS_COLOR, width=2)))
    fig.add_trace(go.Scatter(x=times, y=[max(r.guard_error, 0.1) for r in rows],
                             name="guard", line=dict(color=GUARD_COLOR, width=2)))
    fig.add_vline(x=t, line_color=TRUE_COLOR, line_width=1)
    fig.update_yaxes(type="log", title="position error (m)")
    fig.update_xaxes(title="time (s)")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
                      title=dict(text="Position error: guard vs naive GNSS", font=dict(size=14)),
                      legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
    return fig


# --------------------------------------------------------- text panels


def render_checks(res: GuardResult) -> None:
    def fmt(v: Optional[float]) -> str:
        return "-" if v is None else f"{v:.2f}"

    mark = {True: "✅", False: "❌", None: "➖"}
    st.dataframe(
        [{"": mark[c.passed], "Check": c.name, "Value": fmt(c.value),
          "Threshold": fmt(c.threshold), "If it fails": c.verdict_if_failed,
          "Explanation": c.text} for c in res.checks],
        hide_index=True, width="stretch",
    )


def render_action(res: GuardResult) -> None:
    a = res.action
    color = STATE_COLORS[res.state]
    st.markdown(f"#### Boat action <span style='color:{color}'>({res.state.value})</span>",
                unsafe_allow_html=True)
    st.markdown(
        f"- **Position source:** {a.position_source}\n"
        f"- **Autopilot:** {a.autopilot_mode}\n"
        f"- **Speed:** {a.recommended_speed_kn}\n"
        f"- **Lookout:** {a.lookout_level}"
    )
    if res.state == State.RECOVERING:
        st.progress(res.clean_seconds / res.clean_needed,
                    text=f"Clean for {res.clean_seconds}/{res.clean_needed} s")
    for alert in a.alerts:
        st.warning(alert)
    st.markdown("**Crew:**\n" + "\n".join(f"1. {step}" for step in a.crew_instructions))


LEARN_TEXT = f"""
**GNSS** - satellite navigation (GPS, Galileo, ...). The receiver measures its distance
to each satellite and solves for position.

**Why 4, and why 5 satellites?** A fix has four unknowns: east, north, up and the
receiver's clock error, so it needs 4 satellites. A 5th gives a spare measurement, so the
answer can be cross-checked. The guard requires 5.

**C/N0 (dB-Hz)** - signal strength of one satellite. Healthy signals are about 35-50 and
differ from each other because satellites are at different heights in the sky. The
receiver loses a satellite below {TRACKING_THRESHOLD_DBHZ:.0f}.

**Noise floor / AGC (dB)** - how much background radio noise the receiver hears. A jammer
raises it sharply.

**HDOP** - how much the satellite geometry magnifies errors. Satellites spread around the
sky give under 2 (good); all from one direction gives over 5 (poor).

**Jamming** - drowning the signals in noise: noise floor up, signals down, satellites lost.

**Spoofing** - transmitting fake satellite signals to move the reported position. Fakes
come from one transmitter, so they are too strong, too similar and from one direction.
Smart spoofing looks normal and drags the position slowly; it is caught only because the
position disagrees with dead reckoning.

**Dead reckoning** - position from compass heading, speed through the water and the
learned sea current. It drifts, so its uncertainty circle grows every second.

**Sea current** - water moving under the ship. Learned from GNSS while it is trusted.

**Radar fix** - the measured range to the straight coast gives the north coordinate.

**Depth-profile fix** - the last 60 s of depth soundings are slid east and west over the
chart until they match, which gives the east coordinate (only where the seabed varies).

**Fuse** - combining two estimates, trusting the more accurate one more.

**Gate** - the largest believable gap between GNSS and dead reckoning:
3 x uncertainty + 10 m. Beyond it, GNSS is lying; beyond half of it, GNSS is degraded.

**States** - TRUSTED: use GNSS. DEGRADED: blend GNSS with dead reckoning. JAMMING,
SPOOFING, LOST: ignore GNSS and navigate on backup. RECOVERING: signals look clean but
GNSS is trusted again only after 60 clean seconds (10 after DEGRADED).

**Naive GNSS** - a receiver that believes every fix and holds the last one when there is
none. Speed: 1 kn = {KNOT_MPS} m/s.
"""


# ------------------------------------------------------------------ page


def _reset_time() -> None:
    st.session_state.t = 0
    st.session_state.playing = False


def main() -> None:
    st.set_page_config(page_title="GNSS trust monitor", layout="wide")
    st.session_state.setdefault("t", 0)
    st.session_state.setdefault("playing", False)

    with st.sidebar:
        st.header("GNSS trust monitor")
        key = st.selectbox("Scenario", list(SCENARIOS), on_change=_reset_time,
                           format_func=lambda k: SCENARIOS[k].title)
        st.caption(SCENARIOS[key].description)
        step = st.select_slider("Playback speed (s per tick)", [1, 2, 5, 10, 20], value=5)
        label = "⏸ Pause" if st.session_state.playing else "▶ Play"
        if st.button(label, width="stretch"):
            st.session_state.playing = not st.session_state.playing
        follow = st.checkbox("Follow the boat on the map", value=True)

    run = load_run(key)
    last = len(run.rows) - 1
    if st.session_state.playing:
        st.session_state.t = min(st.session_state.t + step, last)
        if st.session_state.t >= last:
            st.session_state.playing = False

    t = st.slider("Time (s)", 0, last, key="t")
    row = run.rows[t]
    res = row.result

    render_banner(res)

    left, right = st.columns([2, 1])
    with left:
        st.plotly_chart(boat_map(run, t, follow), width="stretch")
    with right:
        render_action(res)

    c1, c2 = st.columns(2)
    c1.plotly_chart(sky_plot(row), width="stretch")
    c2.plotly_chart(cn0_bars(row), width="stretch")

    g1, g2, g3 = st.columns(3)
    g1.plotly_chart(noise_gauge(res, row), width="stretch")
    g2.plotly_chart(satellite_count(res), width="stretch")
    g3.plotly_chart(hdop_gauge(res), width="stretch")

    st.markdown("#### Check ladder (first failing check decides)")
    render_checks(res)

    st.plotly_chart(error_chart(run, row.t), width="stretch")

    with st.expander("Learn: what every term means"):
        st.markdown(LEARN_TEXT)

    st.markdown("#### All scenarios compared")
    st.dataframe(comparison_rows(), hide_index=True, width="stretch")

    if st.session_state.playing:
        time.sleep(0.4)
        st.rerun()


if __name__ == "__main__":
    main()
