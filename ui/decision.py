"""Section 2 (the checks, as cards) and section 3 (the decision banner)."""

import html
from typing import Optional

import streamlit as st

from marine_guard import CheckResult, GuardResult

from teaching.captions import SECTION_TEXT
from teaching.decision_text import deciding_check, what_is_happening, why
from teaching.explanations import explain

from .style import STATE_COLORS

STATUS = {True: ("✅", "passed"), False: ("❌", "failed"), None: ("➖", "skipped")}

def _number(v: Optional[float]) -> str:
    if v is None:
        return "-"
    return f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}"


def _card(check: CheckResult, index: int, deciding: bool, color: str) -> str:
    icon, word = STATUS[check.passed]
    texts = {k: html.escape(v) for k, v in explain(check).items()}
    border = f"3px solid {color}" if deciding else "1px solid rgba(128,128,128,0.35)"
    background = f"{color}14" if deciding else "transparent"
    badge = (f"<span style='background:{color};color:white;border-radius:4px;"
             f"padding:1px 6px;font-size:0.8rem;margin-left:8px;'>decided the verdict</span>"
             if deciding else "")
    return f"""
<div style="border:{border};background:{background};border-radius:8px;
            padding:0.55rem 0.8rem;margin-bottom:0.5rem;">
  <div style="font-weight:600;">{index}. {icon} {html.escape(check.name)}
    <span style="font-weight:400;opacity:0.75;"> &middot; {word} &middot; value
    {_number(check.value)} / threshold {_number(check.threshold)}
    &middot; if it fails: {check.verdict_if_failed}</span>{badge}</div>
  <div style="margin-top:0.25rem;"><b>What we measured:</b> {texts['measured']}</div>
  <div><b>What it means:</b> {texts['means']}</div>
  <div><b>If it fails, what that suggests:</b> {texts['if_fails']}</div>
</div>"""


def render_checks(res: GuardResult) -> None:
    deciding = deciding_check(res)
    color = STATE_COLORS[res.state]
    st.markdown(SECTION_TEXT["checks"])
    cards = [_card(c, i + 1, c is deciding, color) for i, c in enumerate(res.checks)]
    st.markdown("".join(cards), unsafe_allow_html=True)


def render_decision(res: GuardResult) -> None:
    color = STATE_COLORS[res.state]
    lat_text = f"{res.lat_deg:.4f}° N, {res.lon_deg:.4f}° E"
    st.markdown(
        f"""
<div style="border-left:14px solid {color};padding:0.6rem 1rem;background:{color}1f;
            border-radius:6px;margin-bottom:0.5rem;">
  <div style="font-size:1.7rem;font-weight:700;color:{color};">{res.state.value}
    <span style="font-size:1rem;font-weight:400;opacity:0.85;">&nbsp;t = {res.timestamp:.0f} s
    &middot; position {lat_text} &plusmn; {res.uncertainty_m:.0f} m</span></div>
  <div><b>What is happening:</b> {html.escape(what_is_happening(res))}</div>
  <div><b>Why:</b> {html.escape(why(res))}</div>
</div>""",
        unsafe_allow_html=True,
    )
