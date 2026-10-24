"""Section 4: what the boat must do (playbook for the current state)."""

import streamlit as st

from marine_guard import GuardResult, State

from .sources import link
from .style import STATE_COLORS

DISCLAIMER = ("Educational summary, not legal advice or an official procedure. Follow your "
              "company safety management system and the instructions of the flag state and "
              "coastal authority.")

RULE_SOURCES = {"COLREG": "colreg", "SOLAS": "solas_v"}


def _rule_with_link(rule: str) -> str:
    for prefix, key in RULE_SOURCES.items():
        if rule.startswith(prefix):
            return f"{rule} ({link(key, 'IMO')})"
    return rule


def render_playbook(res: GuardResult) -> None:
    a = res.action
    color = STATE_COLORS[res.state]
    st.markdown(f"<span style='color:{color};font-weight:700;font-size:1.2rem;'>"
                f"{res.state.value}</span> &nbsp; position from **{a.position_source}** · "
                f"autopilot **{a.autopilot_mode}** · speed **{a.recommended_speed_kn}** · "
                f"look-out **{a.lookout_level}**", unsafe_allow_html=True)
    for alert in a.alerts:
        st.warning(alert)
    if res.state == State.RECOVERING:
        st.progress(res.clean_seconds / res.clean_needed,
                    text=f"Clean for {res.clean_seconds} of {res.clean_needed} seconds")

    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"**Why it matters.** {a.why_it_matters}")
        st.markdown("**Steps for the bridge team**\n\n"
                    + "\n".join(f"{i}. {step}" for i, step in enumerate(a.steps, 1)))
    with right:
        with st.container(border=True):
            st.markdown("**Rules that still apply when GNSS fails**\n\n"
                        + "\n".join(f"- {_rule_with_link(r)}" for r in a.rules))
        st.markdown(
            "**Sources for the steps:** "
            f"{link('sma', 'Swedish Maritime Administration (as reported)')}; "
            f"{link('imo5037', 'IMO Circular Letter No. 5037 (Estonia and Finland)')}; "
            f"{link('fi_ee_warning', 'Finnish-Estonian warning')}; "
            f"{link('traficom_boating', 'Traficom advice for boaters')}.")
    st.info(DISCLAIMER)
