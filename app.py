"""Baltic GNSS trust monitor - a teaching app. Run: streamlit run app.py

Plain words first, then the details: Monitor tab (input -> checks -> decision
-> what the boat does -> maps), Simple tab, Derivations tab.
"""

import time
from typing import List, Optional

import plotly.graph_objects as go
import streamlit as st

from marine_guard import GuardConfig
from sim.analysis import Danger, Detection, detections, downsample, first_danger, path_errors
from sim.runner import Run, run_scenario, summarize
from sim.scenarios import SCENARIOS, VOYAGE_SCENARIOS
from ui.briefing import render_briefing
from ui.decision import render_checks, render_decision
from ui.derivations import render_derivations
from ui.inspector import render_inspector
from ui.maps import closeup_map, overview_map, route_map
from ui.playbook import render_playbook
from ui.simple import render_simple
from ui.style import EVENT_SHADE, GREEN_PATH, RED_PATH, STATE_COLORS, TRUTH, how_to_read

MODES = {"Baltic voyage (3 hours)": True, "Short test run (15 minutes)": False}


# ------------------------------------------------------------------ data


@st.cache_resource(show_spinner="Simulating the voyage (first time only)...")
def load_run(key: str, voyage: bool) -> Run:
    """Full per-second record; kept as a shared resource because it is large."""
    return run_scenario(key, voyage=voyage)


@st.cache_data(show_spinner=False)
def map_events(key: str, voyage: bool):
    run = load_run(key, voyage)
    return detections(run), first_danger(run)


@st.cache_data(show_spinner=False)
def error_series(key: str, voyage: bool) -> dict:
    """Downsampled error-over-time data for plotting."""
    run = load_run(key, voyage)
    rows = downsample(run.rows, 10 if voyage else 1)
    return {"t": [r.t for r in rows],
            "guard": [max(r.guard_error, 0.1) for r in rows],
            "naive": [max(r.naive_error, 0.1) for r in rows]}


@st.cache_data(show_spinner="Simulating every scenario (first time only)...")
def comparison(voyage: bool) -> List[dict]:
    def seconds(v: Optional[float]) -> str:
        return "-" if v is None else f"{v:.0f} s"

    table = []
    for key, sc in (VOYAGE_SCENARIOS if voyage else SCENARIOS).items():
        run = load_run(key, voyage)
        s, paths = summarize(run), path_errors(run)
        table.append({
            "Scenario": sc.title,
            "First detection": seconds(s.detection_s),
            "Back to TRUSTED after event": seconds(s.back_to_trusted_s),
            "Worst error, guard (m)": round(s.worst_guard_error_m, 1),
            "Worst error, naive GNSS (m)": round(s.worst_naive_error_m, 1),
            "Red path worst (m)": round(paths.red_worst_m, 1),
            "Green path worst (m)": round(paths.green_worst_m, 1),
        })
    return table


# ---------------------------------------------------------------- charts


def error_chart(key: str, voyage: bool, run: Run, t: float) -> go.Figure:
    data = error_series(key, voyage)
    sc = run.scenario
    fig = go.Figure()
    if sc.event_start is not None:
        fig.add_vrect(x0=sc.event_start, x1=sc.event_end, fillcolor=EVENT_SHADE,
                      line_width=0, annotation_text="event", annotation_position="top left")
    fig.add_trace(go.Scatter(x=data["t"], y=data["naive"], name="naive GNSS (believes everything)",
                             line=dict(color=RED_PATH, width=2)))
    fig.add_trace(go.Scatter(x=data["t"], y=data["guard"], name="guard",
                             line=dict(color=GREEN_PATH, width=2)))
    fig.add_vline(x=t, line_color=TRUTH, line_width=1)
    fig.update_yaxes(type="log", title="position error (m, log scale)")
    fig.update_xaxes(title="time (s)")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
                      title=dict(text="Position error over time: guard vs naive GNSS",
                                 font=dict(size=14)),
                      legend=dict(orientation="h", y=1.15, x=1, xanchor="right"))
    return fig


# ------------------------------------------------------------- controls


def _reset() -> None:
    st.session_state.t = 0
    st.session_state.playing = False


def _jump(t: float) -> None:
    st.session_state.t = int(t)
    st.session_state.playing = False


def sidebar(cfg: GuardConfig):
    with st.sidebar:
        st.header("Baltic GNSS trust monitor")
        mode = st.radio("Mode", list(MODES), on_change=_reset)
        voyage = MODES[mode]
        scenarios = VOYAGE_SCENARIOS if voyage else SCENARIOS
        key = st.selectbox("Scenario", list(scenarios), on_change=_reset,
                           format_func=lambda k: scenarios[k].title)
        sc = scenarios[key]
        st.caption(f"{sc.description} ({sc.event_text})")
        steps = [1, 10, 30, 60, 120] if voyage else [1, 2, 5, 10, 20]
        step = st.select_slider("Playback: seconds per tick", steps, value=steps[2])
        if st.button("⏸ Pause" if st.session_state.playing else "▶ Play", width="stretch"):
            st.session_state.playing = not st.session_state.playing
        compare = st.toggle("Compare with a healthy receiver", value=False)
        st.divider()
        if voyage:
            st.markdown(f"**Start:** {cfg.origin_lat_deg:.2f}° N, {cfg.origin_lon_deg:.2f}° E, "
                        "heading east at 12 knots.")
    return key, voyage, step, compare


def data_labels(run: Run) -> None:
    chart = run.chart
    if hasattr(chart, "grid"):
        if chart.grid.synthetic:
            st.warning("**Depth chart: SYNTHETIC.** Real bathymetry (EMODnet) could not be "
                       "downloaded, so the seabed depths are generated and are NOT real "
                       "survey data. Run `python -m sim.bathymetry download` with internet "
                       "access to use real data. The coastline and land come from a real "
                       "land mask (global-land-mask, about 1 km resolution).")
        else:
            st.success("Depth chart: real EMODnet bathymetry. Land: real land mask "
                       "(global-land-mask, about 1 km resolution).")
    else:
        st.info("Short test run: synthetic straight coast and synthetic seabed, the same "
                "world the automated tests use.")


def key_moments(run: Run, events: List[Detection]) -> None:
    sc = run.scenario
    moments = []
    if sc.event_start is not None:
        moments.append(("Event starts", sc.event_start))
    moments += [(f"Detected: {d.state.value}", d.t) for d in events[:2]]
    if sc.event_end is not None:
        moments.append(("Event ends", sc.event_end))
        back = summarize(run).back_to_trusted_s
        if back is not None:
            moments.append(("Trusted again", sc.event_end + back))
    if moments:
        cols = st.columns(len(moments))
        for col, (label, t) in zip(cols, moments):
            col.button(f"{label} ({t:.0f} s)", on_click=_jump, args=(t,), width="stretch")


# ------------------------------------------------------------------ page


def monitor_tab(key: str, voyage: bool, step: int, compare: bool) -> None:
    run = load_run(key, voyage)
    last = len(run.rows) - 1
    events, danger = map_events(key, voyage)
    data_labels(run)
    key_moments(run, events)
    if st.session_state.playing:  # advance before the slider widget is created
        st.session_state.t = min(st.session_state.t + step, last)
        if st.session_state.t >= last:
            st.session_state.playing = False
    t = st.slider("Time (s) - pick any second of the voyage", 0, last, key="t")
    row = run.rows[t]
    res = row.result
    st.markdown(f"At **t = {t} s** the guard says <span style='color:"
                f"{STATE_COLORS[res.state]};font-weight:700'>{res.state.value}</span>. "
                "Below: what the receiver reports, how each check judges it, the decision, "
                "and what the boat should do.", unsafe_allow_html=True)

    st.header("1. What the receiver reports (the input)")
    st.markdown("Before deciding anything, look at the raw input: which satellites are "
                "heard, how loud, from where, and what position the receiver claims.")
    normal_run = load_run("normal", voyage) if compare and key != "normal" else None
    render_inspector(run, normal_run, t)

    st.header("2. The checks")
    render_checks(res)

    st.header("3. The decision")
    render_decision(res)

    st.header("4. What the boat must do")
    render_playbook(res)

    st.header("5. Where the ship is")
    st.markdown("**Red**: what GNSS reported while it could not be trusted (the path a "
                "GNSS-following autopilot would believe). **Green**: the guard's backup "
                "track, navigating without GNSS. **Grey dotted**: the real track, which only "
                "a simulation can know. While GNSS is trusted only the blue ship track is "
                "drawn.")
    st.plotly_chart(route_map(run, t, events, danger, every=10 if voyage else 2),
                    width="stretch")
    if danger is not None and danger.t <= row.t:
        st.error(f"⚠ Grounding risk if GNSS had been trusted: at t = {danger.t:.0f} s the "
                 f"reported (red) position was {danger.what}, while the real ship was "
                 f"{danger.off_by_m / 1000:.1f} km away in open water.")
    how_to_read("Latitude runs up, longitude across; both axes are scaled so 1 km looks "
                "the same either way. Stars mark the moments the guard raised an alarm, with "
                "the check that decided. A red ✕ marks where trusting GNSS would have led "
                "towards land or shallow water.")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(closeup_map(run, t, events, danger), width="stretch")
        how_to_read("The green circle is the guard's uncertainty: the ship should be "
                    "somewhere inside it. It grows on dead reckoning and shrinks with each "
                    "radar (▼) or depth (◆) fix.")
    with right:
        if voyage:
            st.plotly_chart(overview_map(run, t), width="stretch")
            how_to_read("The whole Baltic. The blue line is this voyage in the Gulf of "
                        "Finland.")
        else:
            st.info("The Baltic overview is shown in Baltic voyage mode.")

    st.header("6. How well did it do?")
    st.plotly_chart(error_chart(key, voyage, run, row.t), width="stretch")
    how_to_read("Distance between the reported position and the real one, on a log scale "
                "(each grid line is 10 times more). The guard (green) should stay low while "
                "the naive receiver (red) runs away during the event.")
    if st.button("Compare all scenarios (simulates each once)"):
        st.session_state.show_comparison = True
    if st.session_state.get("show_comparison"):
        st.dataframe(comparison(voyage), hide_index=True, width="stretch")

    if st.session_state.playing:
        time.sleep(0.4)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Baltic GNSS trust monitor", layout="wide")
    st.session_state.setdefault("t", 0)
    st.session_state.setdefault("playing", False)
    cfg = GuardConfig()
    key, voyage, step, compare = sidebar(cfg)

    st.title("Can we trust the satellite position? A Baltic Sea GNSS guard")
    with st.expander("Why the Baltic Sea? (start here)", expanded=False):
        render_briefing()

    monitor, simple, derivations = st.tabs(["Monitor", "Simple explanation", "Derivations"])
    with simple:
        render_simple(cfg)
    with derivations:
        run = load_run(key, voyage)
        render_derivations(cfg, run.rows[min(st.session_state.t, len(run.rows) - 1)])
    with monitor:
        monitor_tab(key, voyage, step, compare)


if __name__ == "__main__":
    main()
